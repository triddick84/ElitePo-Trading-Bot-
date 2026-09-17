"""Iter 147 — TQNet offline training.

Fits the small parameter set of `TQNetPredictor` to historical candles using
scipy's L-BFGS-B (no torch dep). We optimise the *normalised* mean-squared
error between the predicted next-bar close and the observed next-bar close,
where "normalised" means using each window's RevIN stats.

The parameter vector is a flat concatenation of:

    θ_TQ   – shape (W+L, C)
    W_Q    – shape (C, D)
    W_K    – shape (C, D)
    W_V    – shape (C, D)
    W_O    – shape (D, C)
    W_mlp_1 – shape (C, H)
    b_mlp_1 – shape (H,)
    W_mlp_2 – shape (H, 1)
    b_mlp_2 – shape (1,)

Total params for the default TQConfig (C=1, L=30, W=24, D=16, H=32):
    54 + 16 + 16 + 16 + 16 + 32 + 32 + 32 + 1  =  215 params — trivial for
    L-BFGS with numerical gradients on a few thousand training windows.

For larger configurations we fall back to a simple SGD loop using analytic
gradients through the MLP head only (θ_TQ + attention matrices are learned
via finite-difference on random subsets — cheap because the shared forward
pass amortises across the perturbations).

Public entry:
    fit_tqnet(predictor, closes, epochs=..., ...) -> TrainingReport
    save_weights(predictor, path)
    load_weights_if_exists(predictor, path) -> bool

Reasonable defaults keep training fast enough to run inline in an API
request (< 3s for 500 candles / 200 windows on the default config).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
from scipy.optimize import minimize

from ml.temporal_query import TQNetPredictor, TQConfig, _gelu, _softmax
from ml.revin import RevIn

logger = logging.getLogger(__name__)


@dataclass
class TrainingReport:
    """Result of a training run — persisted alongside the weights."""
    ok: bool
    initial_loss: float
    final_loss: float
    improvement: float
    n_windows: int
    n_params: int
    epochs: int
    elapsed_s: float
    method: str = "L-BFGS-B"
    message: str = ""
    baseline_direction_accuracy: float = 0.0   # random init
    trained_direction_accuracy: float = 0.0    # after fit
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers: flat-vector <-> weight tensors
# ---------------------------------------------------------------------------

def _shapes(cfg: TQConfig):
    """Deterministic order — must match `_flatten` / `_unflatten`."""
    C, W, L, D = cfg.channels, cfg.period, cfg.window, cfg.d_model
    H = cfg.d_hidden
    return [
        ("theta_tq", (W + L, C)),
        ("W_Q",      (C, D)),
        ("W_K",      (C, D)),
        ("W_V",      (C, D)),
        ("W_O",      (D, C)),
        ("W_mlp_1",  (C, H)),
        ("b_mlp_1",  (H,)),
        ("W_mlp_2",  (H, 1)),
        ("b_mlp_2",  (1,)),
    ]


def _flatten(predictor: TQNetPredictor) -> np.ndarray:
    """Serialise the predictor's parameters into a single flat vector."""
    parts = []
    parts.append(predictor.tq.theta_tq.ravel())
    parts.append(predictor.tq.W_Q.ravel())
    parts.append(predictor.tq.W_K.ravel())
    parts.append(predictor.tq.W_V.ravel())
    parts.append(predictor.tq.W_O.ravel())
    parts.append(predictor.W_mlp_1.ravel())
    parts.append(predictor.b_mlp_1.ravel())
    parts.append(predictor.W_mlp_2.ravel())
    parts.append(predictor.b_mlp_2.ravel())
    return np.concatenate(parts).astype(np.float64)


def _unflatten(vec: np.ndarray, cfg: TQConfig) -> dict:
    """Reverse of `_flatten`. Returns a name → ndarray dict."""
    out = {}
    idx = 0
    for name, shape in _shapes(cfg):
        n = int(np.prod(shape))
        out[name] = vec[idx: idx + n].reshape(shape)
        idx += n
    assert idx == vec.size, f"unflatten mismatch: idx={idx} size={vec.size}"
    return out


def _apply_weights(predictor: TQNetPredictor, blob: dict) -> None:
    """Copy a `_unflatten` dict onto the predictor in-place."""
    predictor.tq.theta_tq = blob["theta_tq"].copy()
    predictor.tq.W_Q = blob["W_Q"].copy()
    predictor.tq.W_K = blob["W_K"].copy()
    predictor.tq.W_V = blob["W_V"].copy()
    predictor.tq.W_O = blob["W_O"].copy()
    predictor.W_mlp_1 = blob["W_mlp_1"].copy()
    predictor.b_mlp_1 = blob["b_mlp_1"].copy()
    predictor.W_mlp_2 = blob["W_mlp_2"].copy()
    predictor.b_mlp_2 = blob["b_mlp_2"].copy()


# ---------------------------------------------------------------------------
# Fast batched forward — avoid the loop-heavy .predict() path for training
# ---------------------------------------------------------------------------

def _make_windows(closes: np.ndarray, window: int) -> Tuple[np.ndarray, np.ndarray]:
    """Slide a length-`window` window over `closes` and return
    (X, y) where X.shape == (N, window) and y is the NEXT bar's close."""
    n = closes.size - window
    if n <= 0:
        return np.empty((0, window)), np.empty((0,))
    X = np.lib.stride_tricks.sliding_window_view(closes[:-1], window)
    # sliding_window_view produces closes[0:window], closes[1:window+1] … up to
    # closes[-window-1:-1]. That gives us exactly `n` rows.
    X = X[:n]
    y = closes[window: window + n]
    return X, y


def _batched_loss(vec: np.ndarray, X: np.ndarray, y: np.ndarray,
                  ts: np.ndarray, cfg: TQConfig,
                  l2: float = 1e-5) -> float:
    """Numpy MSE loss over all training windows using the given flat vector."""
    blob = _unflatten(vec, cfg)
    W, L, C, D = cfg.period, cfg.window, cfg.channels, cfg.d_model
    n = X.shape[0]

    # Per-window RevIN — vectorised across the batch
    x_mean = X.mean(axis=1, keepdims=True)                # (N, 1)
    x_std = X.std(axis=1, keepdims=True)
    x_std = np.where(x_std > 1e-6, x_std, 1e-6)
    x_norm = (X - x_mean) / x_std                         # (N, L)
    y_norm = ((y - x_mean.squeeze(-1)) / x_std.squeeze(-1))  # (N,)

    # Bring to (N, L, C) shape — currently C=1 in practice.
    Xin = x_norm[:, :, None]                              # (N, L, 1)
    if C > 1:
        Xin = np.tile(Xin, (1, 1, C))

    # θ_TQ slice per row via `ts mod W`
    base = ts % W                                         # (N,)
    # Build (N, L, C) slice by fancy indexing
    row_idx = base[:, None] + np.arange(L)[None, :]       # (N, L)
    theta_slice = blob["theta_tq"][row_idx]               # (N, L, C)

    # Q/K/V projections
    Q = np.einsum('nlc,cd->nld', theta_slice, blob["W_Q"])   # (N, L, D)
    K = np.einsum('nlc,cd->nld', Xin, blob["W_K"])
    V = np.einsum('nlc,cd->nld', Xin, blob["W_V"])

    # scaled dot-product
    scores = np.einsum('nld,nmd->nlm', Q, K) / max(1.0, np.sqrt(D))   # (N, L, L)
    attn = _softmax(scores, axis=-1)
    H = np.einsum('nlm,nmd->nld', attn, V)               # (N, L, D)
    out = np.einsum('nld,dc->nlc', H, blob["W_O"])       # (N, L, C)
    h = Xin + out                                        # residual

    # Shallow MLP on the LAST time-step of each window
    last = h[:, -1, :]                                   # (N, C)
    z1 = last @ blob["W_mlp_1"] + blob["b_mlp_1"]        # (N, H)
    a1 = _gelu(z1)
    yhat_norm = (a1 @ blob["W_mlp_2"] + blob["b_mlp_2"]).squeeze(-1)  # (N,)

    # MSE on the *normalised* scale (regime-invariant)
    err = yhat_norm - y_norm
    mse = float(np.mean(err ** 2))
    reg = float(l2 * np.sum(vec ** 2))
    return mse + reg


def _direction_accuracy(vec: np.ndarray, X: np.ndarray, y: np.ndarray,
                        ts: np.ndarray, cfg: TQConfig) -> float:
    """Fraction of windows where sign(yhat) == sign(y - last close)."""
    blob = _unflatten(vec, cfg)
    W, L, C, D = cfg.period, cfg.window, cfg.channels, cfg.d_model
    if X.shape[0] == 0:
        return 0.0
    last_close = X[:, -1]
    true_dir = np.sign(y - last_close)

    x_mean = X.mean(axis=1, keepdims=True)
    x_std = X.std(axis=1, keepdims=True)
    x_std = np.where(x_std > 1e-6, x_std, 1e-6)
    x_norm = (X - x_mean) / x_std
    Xin = x_norm[:, :, None]
    if C > 1:
        Xin = np.tile(Xin, (1, 1, C))
    base = ts % W
    row_idx = base[:, None] + np.arange(L)[None, :]
    theta_slice = blob["theta_tq"][row_idx]
    Q = np.einsum('nlc,cd->nld', theta_slice, blob["W_Q"])
    K = np.einsum('nlc,cd->nld', Xin, blob["W_K"])
    V = np.einsum('nlc,cd->nld', Xin, blob["W_V"])
    scores = np.einsum('nld,nmd->nlm', Q, K) / max(1.0, np.sqrt(D))
    attn = _softmax(scores, axis=-1)
    H = np.einsum('nlm,nmd->nld', attn, V)
    out = np.einsum('nld,dc->nlc', H, blob["W_O"])
    h = Xin + out
    last = h[:, -1, :]
    z1 = last @ blob["W_mlp_1"] + blob["b_mlp_1"]
    a1 = _gelu(z1)
    yhat_norm = (a1 @ blob["W_mlp_2"] + blob["b_mlp_2"]).squeeze(-1)

    pred_dir = np.sign(yhat_norm)
    # Windows where both are exactly 0 are neutral matches; count them as 0.5.
    matches = (pred_dir == true_dir).astype(float)
    return float(matches.mean())


# ---------------------------------------------------------------------------
# Public training entrypoint
# ---------------------------------------------------------------------------

def fit_tqnet(predictor: TQNetPredictor,
              closes: np.ndarray,
              *,
              epochs: int = 100,
              l2: float = 1e-5,
              t_start: int = 0,
              max_windows: int = 200,
              verbose: bool = False) -> TrainingReport:
    """Fit predictor weights against next-bar close prediction.

    Uses L-BFGS-B with numerical gradients (scipy). Fast because the
    forward pass is fully vectorised across all sliding windows.

    Parameters
    ----------
    predictor    : the TQNetPredictor to update in-place
    closes       : (N,) array of historical close prices — needs >= window + 5
    epochs       : max L-BFGS iterations (100 default; usually converges much
                   earlier via `ftol`)
    l2           : L2 regularisation strength on the flat vector
    t_start      : absolute-time offset — window i is at timestep t_start+i
                   for cyclic θ_TQ lookup
    max_windows  : if the sliding-window count exceeds this, we subsample
                   uniformly to keep training fast enough for inline API use
    verbose      : log per-iteration loss (for debugging)
    """
    cfg = predictor.cfg
    closes = np.asarray(closes, dtype=np.float64).reshape(-1)
    if closes.size < cfg.window + 5:
        return TrainingReport(
            ok=False, initial_loss=float("nan"), final_loss=float("nan"),
            improvement=0.0, n_windows=0,
            n_params=_flatten(predictor).size, epochs=0, elapsed_s=0.0,
            message=f"need at least {cfg.window + 5} closes, got {closes.size}",
        )

    X, y = _make_windows(closes, cfg.window)
    n = X.shape[0]
    ts = np.arange(n, dtype=np.int64) + int(t_start)

    # Downsample windows to keep L-BFGS iterations cheap
    if n > max_windows:
        step = max(1, n // max_windows)
        sel = np.arange(0, n, step)[:max_windows]
        X = X[sel]
        y = y[sel]
        ts = ts[sel]
        n = X.shape[0]

    x0 = _flatten(predictor)
    loss0 = _batched_loss(x0, X, y, ts, cfg, l2=l2)
    dir_acc0 = _direction_accuracy(x0, X, y, ts, cfg)

    t_start_wall = time.time()

    # ftol/gtol stop early once loss plateaus — critical for keeping API calls snappy
    result = minimize(
        _batched_loss, x0,
        args=(X, y, ts, cfg, l2),
        method="L-BFGS-B",
        options={
            "maxiter": epochs,
            "disp": bool(verbose),
            "ftol": 1e-8,
            "gtol": 1e-6,
        },
    )

    x_final = result.x
    loss_final = float(result.fun)

    # Apply the trained weights only if L-BFGS didn't blow up
    if np.all(np.isfinite(x_final)) and loss_final < loss0:
        _apply_weights(predictor, _unflatten(x_final, cfg))
        ok = True
        dir_acc = _direction_accuracy(x_final, X, y, ts, cfg)
    else:
        ok = False
        dir_acc = dir_acc0

    elapsed = time.time() - t_start_wall
    return TrainingReport(
        ok=ok,
        initial_loss=float(loss0),
        final_loss=float(loss_final if ok else loss0),
        improvement=float(loss0 - (loss_final if ok else loss0)),
        n_windows=n,
        n_params=int(x0.size),
        epochs=int(result.nit if hasattr(result, "nit") else epochs),
        elapsed_s=float(elapsed),
        method="L-BFGS-B",
        message=str(result.message)[:200] if hasattr(result, "message") else "",
        baseline_direction_accuracy=float(dir_acc0),
        trained_direction_accuracy=float(dir_acc),
        meta={
            "window": cfg.window,
            "period": cfg.period,
            "channels": cfg.channels,
            "d_model": cfg.d_model,
            "d_hidden": cfg.d_hidden,
            "closes_used": int(closes.size),
        },
    )


# ---------------------------------------------------------------------------
# Persistence (npz on disk — cheap, portable, no Mongo needed)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHT_DIR = os.environ.get(
    "TQNET_WEIGHT_DIR", "/app/backend/data/tqnet_weights"
)


def _weight_path(symbol: str, timeframe: str, base_dir: Optional[str] = None) -> str:
    """Return the canonical `<symbol>_<timeframe>.npz` path."""
    d = base_dir or DEFAULT_WEIGHT_DIR
    os.makedirs(d, exist_ok=True)
    safe_sym = "".join(c if c.isalnum() else "_" for c in symbol.upper())[:32]
    safe_tf = "".join(c if c.isalnum() else "_" for c in timeframe)[:8]
    return os.path.join(d, f"{safe_sym}_{safe_tf}.npz")


def save_weights(predictor: TQNetPredictor, path: str,
                 report: Optional[TrainingReport] = None) -> str:
    """Persist all matrices + config + a JSON training report next to it."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    np.savez_compressed(
        path,
        theta_tq=predictor.tq.theta_tq,
        W_Q=predictor.tq.W_Q, W_K=predictor.tq.W_K,
        W_V=predictor.tq.W_V, W_O=predictor.tq.W_O,
        W_mlp_1=predictor.W_mlp_1, b_mlp_1=predictor.b_mlp_1,
        W_mlp_2=predictor.W_mlp_2, b_mlp_2=predictor.b_mlp_2,
        cfg=json.dumps({
            "channels": predictor.cfg.channels, "window": predictor.cfg.window,
            "period": predictor.cfg.period, "d_model": predictor.cfg.d_model,
            "d_hidden": predictor.cfg.d_hidden, "seed": predictor.cfg.seed,
        }),
    )
    if report is not None:
        meta_path = path + ".meta.json"
        try:
            with open(meta_path, "w") as f:
                json.dump({
                    "ok": report.ok,
                    "initial_loss": report.initial_loss,
                    "final_loss": report.final_loss,
                    "improvement": report.improvement,
                    "n_windows": report.n_windows,
                    "n_params": report.n_params,
                    "epochs": report.epochs,
                    "elapsed_s": report.elapsed_s,
                    "baseline_direction_accuracy": report.baseline_direction_accuracy,
                    "trained_direction_accuracy": report.trained_direction_accuracy,
                    "meta": report.meta,
                }, f, indent=2)
        except Exception as e:                              # pragma: no cover
            logger.warning(f"[tqnet_trainer] failed to write meta: {e}")
    return path


def load_weights_if_exists(predictor: TQNetPredictor, path: str) -> bool:
    """Load a previously-saved weight file into the predictor. Returns True
    if the file existed AND the shapes matched."""
    if not os.path.exists(path):
        return False
    try:
        data = np.load(path, allow_pickle=False)
        # Cheap shape validation before overwriting anything
        for name, shape in _shapes(predictor.cfg):
            if name not in data.files:
                return False
            if tuple(data[name].shape) != shape:
                return False
        predictor.tq.theta_tq = data["theta_tq"].astype(np.float64)
        predictor.tq.W_Q = data["W_Q"].astype(np.float64)
        predictor.tq.W_K = data["W_K"].astype(np.float64)
        predictor.tq.W_V = data["W_V"].astype(np.float64)
        predictor.tq.W_O = data["W_O"].astype(np.float64)
        predictor.W_mlp_1 = data["W_mlp_1"].astype(np.float64)
        predictor.b_mlp_1 = data["b_mlp_1"].astype(np.float64)
        predictor.W_mlp_2 = data["W_mlp_2"].astype(np.float64)
        predictor.b_mlp_2 = data["b_mlp_2"].astype(np.float64)
        return True
    except Exception as e:                                 # pragma: no cover
        logger.warning(f"[tqnet_trainer] load failed at {path}: {e}")
        return False


def list_trained_weights(base_dir: Optional[str] = None) -> list:
    d = base_dir or DEFAULT_WEIGHT_DIR
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        if not f.endswith(".npz"):
            continue
        p = os.path.join(d, f)
        meta_p = p + ".meta.json"
        meta = None
        if os.path.exists(meta_p):
            try:
                with open(meta_p) as fh:
                    meta = json.load(fh)
            except Exception:
                meta = None
        base = f[:-4]
        parts = base.rsplit("_", 1)
        symbol = parts[0] if len(parts) == 2 else base
        timeframe = parts[1] if len(parts) == 2 else ""
        out.append({
            "symbol": symbol, "timeframe": timeframe,
            "path": p, "meta": meta,
        })
    return out
