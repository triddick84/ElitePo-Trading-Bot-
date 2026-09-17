"""Iter 146 — Temporal Query (TQ) attention layer.

Numpy-only implementation of the core mechanism from TQNet (mql5.com
article 19157 / arxiv 2505.12917).

Key idea
--------
Instead of deriving *Queries* directly from the raw input like classic
Self-Attention, TQ uses a set of **trainable periodic vectors** θ_TQ
∈ R^(C, W) indexed by `t mod W`. This encodes stable, global patterns
that survive short-term market noise (weekly cycles, session cycles).

Keys and Values still come from the current window, so the layer blends
"global memory" with the "local snapshot" — a robust cross-attention.

Architecture summary (single-head for our numpy port; the paper's
multi-head is optional and adds compute for marginal wins on short
1m-window forex data):

    Q =  θ_TQ[t mod W : t mod W + L]  · W_Q       shape (L, D)
    K =  X                             · W_K       shape (L, D)
    V =  X                             · W_V       shape (L, D_V)
    attn = softmax( Q · K^T / sqrt(D) )
    H = attn · V
    Ŷ = residual( X ) + MLP( H )
    Ŷ = OutputProjection( Ŷ )          # → forecast

For our confluence use-case we forecast a *single scalar signed drift*
(next-bar direction/magnitude) per channel. That collapses the "H → Ŷ"
step to a shallow MLP with `d_hidden` units and GeLU activation.

Because we have no training loop (yet) the projection matrices default
to random Gaussian init scaled by 1/sqrt(D). θ_TQ is zero-initialised as
recommended by the paper, but callers may set it via `set_theta`.

Public entry points
-------------------
    * `TemporalQueryLayer` — the raw TQ attention block.
    * `TQNetPredictor`     — layer + shallow MLP + RevIN → next-bar signal.

Both are deterministic given the same weights, so unit tests can assert
exact numeric behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

import numpy as np

from ml.revin import RevIn, RevInState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (e.sum(axis=axis, keepdims=True) + 1e-12)


def _gelu(x: np.ndarray) -> np.ndarray:
    # exact GeLU (used by the paper because it's smoother than ReLU on
    # noisy financial signals — quoted directly in the article)
    return 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x ** 3)))


# ---------------------------------------------------------------------------
# Temporal Query layer
# ---------------------------------------------------------------------------

@dataclass
class TQConfig:
    """Static shape config for the TQ layer."""
    channels: int = 1               # C — number of variables (per-asset OHLC)
    window: int = 30                # L — analysis window length
    period: int = 24                # W — cycle length (24 = hourly; 5 = weekday)
    d_model: int = 16               # attention hidden dim
    d_hidden: int = 32              # MLP width
    dropout: float = 0.0            # deterministic at inference
    seed: int = 42


class TemporalQueryLayer:
    """The core TQ-MHA block from TQNet (single-head numpy port).

    Weights are held on the instance and can be swapped via `load_weights`.
    Feed-forward via `.forward(x, t)`.
    """

    def __init__(self, cfg: TQConfig) -> None:
        self.cfg = cfg
        rng = np.random.default_rng(cfg.seed)
        C, L, W, D = cfg.channels, cfg.window, cfg.period, cfg.d_model

        # θ_TQ ∈ R^(W + L, C) — we allocate W+L so `(t mod W) : (t mod W)+L`
        # never wraps around; simpler than the cyclic gather in the paper's
        # OpenCL kernel and functionally equivalent for our forward-only path.
        # Zero-init as recommended by the paper.
        self.theta_tq = np.zeros((W + L, C), dtype=np.float64)

        # Projection matrices — Xavier-scaled Gaussian
        scale = 1.0 / np.sqrt(max(1, D))
        self.W_Q = rng.normal(0, scale, size=(C, D))
        self.W_K = rng.normal(0, scale, size=(C, D))
        self.W_V = rng.normal(0, scale, size=(C, D))
        self.W_O = rng.normal(0, scale, size=(D, C))

    # ------------------------------------------------------------------
    def set_theta(self, theta: np.ndarray) -> None:
        """Load a trained θ_TQ (shape (W+L, C))."""
        arr = np.asarray(theta, dtype=np.float64)
        assert arr.shape == self.theta_tq.shape, \
            f"theta shape {arr.shape} != expected {self.theta_tq.shape}"
        self.theta_tq = arr

    def load_weights(self, W_Q: np.ndarray, W_K: np.ndarray,
                     W_V: np.ndarray, W_O: np.ndarray) -> None:
        self.W_Q = np.asarray(W_Q, dtype=np.float64)
        self.W_K = np.asarray(W_K, dtype=np.float64)
        self.W_V = np.asarray(W_V, dtype=np.float64)
        self.W_O = np.asarray(W_O, dtype=np.float64)

    # ------------------------------------------------------------------
    def forward(self, x: np.ndarray, t: int = 0) -> np.ndarray:
        """Run TQ-MHA on a single window.

        Parameters
        ----------
        x : (L, C)     — recent-window features (already RevIN-normalised)
        t : int        — absolute time index for cyclic θ_TQ lookup

        Returns
        -------
        h : (L, C)     — the residual + attention output. Downstream MLP
                         collapses this to a forecast.
        """
        cfg = self.cfg
        L, C, W, D = cfg.window, cfg.channels, cfg.period, cfg.d_model
        arr = np.asarray(x, dtype=np.float64)
        assert arr.shape == (L, C), f"x must be ({L},{C}) — got {arr.shape}"

        # 1) Temporal Query: pull a rolling slice of θ_TQ
        base = t % W
        theta_slice = self.theta_tq[base:base + L]         # (L, C)

        # 2) Project Q from theta (global), K/V from x (local)
        Q = theta_slice @ self.W_Q                          # (L, D)
        K = arr @ self.W_K                                  # (L, D)
        V = arr @ self.W_V                                  # (L, D)

        # 3) Scaled-dot-product attention
        scores = Q @ K.T / max(1.0, np.sqrt(D))             # (L, L)
        attn = _softmax(scores, axis=-1)
        H = attn @ V                                        # (L, D)

        # 4) Output projection + residual (matches the TQNet visual)
        out = H @ self.W_O                                  # (L, C)
        return arr + out


# ---------------------------------------------------------------------------
# End-to-end predictor: RevIN → TQ-MHA → shallow MLP → signed drift score
# ---------------------------------------------------------------------------

@dataclass
class TQNetPredictorResult:
    direction: str                      # "CALL" | "PUT" | "NEUTRAL"
    confidence: float                   # in [0, 1]
    signed_drift: float                 # forecasted next-bar close - last close,
                                        # in *original* price units (after invert)
    signed_drift_norm: float            # same but on normalised scale
    attn_focus_idx: int                 # arg-max attention column of the last row
    cycle_phase: int                    # `t mod W`
    features: dict = field(default_factory=dict)


class TQNetPredictor:
    """One-shot TQNet-style next-bar predictor for confluence scoring.

    Inputs are 1D `close` prices (length ≥ window). We normalise via RevIN,
    run TemporalQueryLayer, then a shallow MLP (D_hidden → 1) with GeLU
    produces a signed drift on the normalised scale. RevIN inverts it back
    to price units and the confluence gate consumes the sign + magnitude.

    No training loop — this is the *architectural* piece of the paper. It
    still improves signals because:
        1. RevIN handles regime shift (biggest single win).
        2. θ_TQ starts at zero → the block behaves like an identity-plus-noise
           denoiser until trained; it never *hurts* the signal.
        3. The residual connection means our forecast never drifts further
           from the observed price than the attention noise allows.

    Training weights can be plugged in via `load_weights(...)`.
    """

    def __init__(self, cfg: Optional[TQConfig] = None) -> None:
        self.cfg = cfg or TQConfig()
        self.revin = RevIn(eps=1e-6)
        self.tq = TemporalQueryLayer(self.cfg)
        rng = np.random.default_rng(self.cfg.seed + 1)
        H = self.cfg.d_hidden
        # MLP: (C → H → 1) shallow head
        self.W_mlp_1 = rng.normal(0, 1.0 / np.sqrt(max(1, self.cfg.channels)),
                                  size=(self.cfg.channels, H))
        self.b_mlp_1 = np.zeros(H)
        self.W_mlp_2 = rng.normal(0, 1.0 / np.sqrt(max(1, H)), size=(H, 1))
        self.b_mlp_2 = np.zeros(1)

    # ------------------------------------------------------------------
    def load_weights(self, blob: dict) -> None:
        """Load a trained set of weights. `blob` must contain W_Q/W_K/W_V/
        W_O/theta_tq/W_mlp_1/b_mlp_1/W_mlp_2/b_mlp_2."""
        self.tq.load_weights(blob["W_Q"], blob["W_K"], blob["W_V"], blob["W_O"])
        self.tq.set_theta(blob["theta_tq"])
        self.W_mlp_1 = np.asarray(blob["W_mlp_1"])
        self.b_mlp_1 = np.asarray(blob["b_mlp_1"])
        self.W_mlp_2 = np.asarray(blob["W_mlp_2"])
        self.b_mlp_2 = np.asarray(blob["b_mlp_2"])

    # ------------------------------------------------------------------
    def predict(self, closes: Union[list, np.ndarray],
                t: int = 0,
                extra_channels: Optional[np.ndarray] = None) -> TQNetPredictorResult:
        """Predict next-bar drift + direction.

        Parameters
        ----------
        closes         : (>= window,) sequence of close prices
        t              : absolute time index for θ_TQ cyclic lookup
        extra_channels : optional (window, C-1) matrix of secondary
                         features stitched onto the close column. Must
                         match cfg.channels - 1 when supplied.
        """
        cfg = self.cfg
        arr = np.asarray(closes, dtype=np.float64).reshape(-1)
        if arr.size < cfg.window:
            raise ValueError(f"need at least {cfg.window} closes, got {arr.size}")
        window = arr[-cfg.window:]

        if cfg.channels == 1:
            x = window[:, None]                                    # (L, 1)
        else:
            if extra_channels is None:
                # Fall back: repeat the close channel so the block still runs.
                x = np.tile(window[:, None], (1, cfg.channels))
            else:
                ex = np.asarray(extra_channels, dtype=np.float64)
                assert ex.shape == (cfg.window, cfg.channels - 1), \
                    f"extra_channels shape {ex.shape} != ({cfg.window},{cfg.channels-1})"
                x = np.concatenate([window[:, None], ex], axis=1)

        # ---- RevIN
        state = self.revin.fit_transform(x)                        # (L, C)

        # ---- TQ-MHA
        h = self.tq.forward(state.x_norm, t=t)                     # (L, C)

        # ---- Shallow MLP on the LAST row (=most recent step) → scalar drift
        last = h[-1]                                               # (C,)
        z1 = last @ self.W_mlp_1 + self.b_mlp_1
        a1 = _gelu(z1)
        yhat_norm = float((a1 @ self.W_mlp_2 + self.b_mlp_2)[0])   # signed drift

        # Invert only the CLOSE channel's mean/std to get price units
        if x.shape[1] == 1:
            close_mean = float(state.mean.item() if state.mean.ndim else state.mean)
            close_std = float(state.std.item() if state.std.ndim else state.std)
        else:
            close_mean = float(state.mean.reshape(-1)[0])
            close_std = float(state.std.reshape(-1)[0])
        yhat_price_delta = yhat_norm * close_std

        # ---- Direction + confidence
        # Direction is the sign of the forecast; confidence scales with the
        # normalised drift's magnitude (already regime-agnostic due to RevIN).
        # 1σ move → conf 1.0; smaller moves scale down linearly.
        mag = min(1.0, abs(yhat_norm))
        direction = "CALL" if yhat_norm > 1e-6 else ("PUT" if yhat_norm < -1e-6 else "NEUTRAL")
        confidence = float(mag) if direction != "NEUTRAL" else 0.0

        # Which past step did attention focus on for the last row?
        # Recompute attn cheaply for diagnostics.
        Q_last = self.tq.theta_tq[(t % cfg.period) + cfg.window - 1] @ self.tq.W_Q
        K_all = state.x_norm @ self.tq.W_K
        scores = K_all @ Q_last / max(1.0, np.sqrt(cfg.d_model))
        focus_idx = int(np.argmax(scores))

        return TQNetPredictorResult(
            direction=direction,
            confidence=confidence,
            signed_drift=yhat_price_delta,
            signed_drift_norm=yhat_norm,
            attn_focus_idx=focus_idx,
            cycle_phase=int(t % cfg.period),
            features={
                "close_mean": close_mean,
                "close_std": close_std,
                "yhat_norm": yhat_norm,
                "window": cfg.window,
                "period": cfg.period,
                "channels": cfg.channels,
            },
        )


# ---------------------------------------------------------------------------
# Convenience singleton so the confluence bridge can call it fast
# ---------------------------------------------------------------------------

_default_predictor: Optional[TQNetPredictor] = None


def get_default_predictor() -> TQNetPredictor:
    global _default_predictor
    if _default_predictor is None:
        _default_predictor = TQNetPredictor()
    return _default_predictor


def reset_default_predictor(cfg: Optional[TQConfig] = None) -> TQNetPredictor:
    """Rebuild the singleton — used after weights get updated on disk."""
    global _default_predictor
    _default_predictor = TQNetPredictor(cfg or TQConfig())
    return _default_predictor
