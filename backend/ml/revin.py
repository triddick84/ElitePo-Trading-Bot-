"""Iter 146 — Reversible Instance Normalization (RevIN).

Source: TQNet framework (mql5.com/en/articles/19157) & the RevIN paper.
Financial time series have severe distribution shifts (regime changes,
volatility bursts, news). RevIN normalises each analysis window on the fly
by subtracting the window mean and dividing by its std, then denormalises
predictions by reversing that transform. This is the single most effective
"stabiliser" cited by the TQNet paper.

Kept in numpy only so it's importable everywhere (no torch dependency).

Two shapes are supported:
    * `apply(x)`     – single 1D series of shape `(L,)` or 2D `(L, C)`.
    * `apply_batch(x)` – batched `(B, L, C)`.

Statistics are stashed on the returned `RevInState` so callers can invert.

Usage:
    state = RevIn().fit_transform(window)         # normalised
    yhat_norm = model.predict(state.x_norm)
    yhat = state.invert(yhat_norm)                # back on original scale
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

import numpy as np

ArrayLike = Union[np.ndarray, list, tuple]


@dataclass
class RevInState:
    """Captured stats + a helper to invert the transform."""
    mean: np.ndarray            # shape (C,) or scalar
    std: np.ndarray             # shape (C,) or scalar
    x_norm: np.ndarray          # the transformed data
    eps: float
    orig_shape: Tuple[int, ...]

    def invert(self, y_norm: ArrayLike) -> np.ndarray:
        """Undo the transform on a prediction that was made in the
        normalised space. Works for y with the same channel-dim as x.
        """
        y = np.asarray(y_norm, dtype=np.float64)
        # Broadcasting: mean/std are per-channel; y can be any (..., C) shape.
        return y * self.std + self.mean


class RevIn:
    """Reversible Instance Normalization layer.

    Parameters
    ----------
    eps : float
        Small constant to avoid division-by-zero on flat windows. TQNet
        uses 1e-5; we default to 1e-6 for tighter forex precision.
    affine : bool
        If True, apply a learnable per-channel affine after normalisation.
        Because we don't have a training loop here, `affine=True` just uses
        externally-provided (gamma, beta) — sensible defaults are (1, 0).
    """

    def __init__(self, eps: float = 1e-6, affine: bool = False,
                 gamma: Optional[ArrayLike] = None,
                 beta: Optional[ArrayLike] = None) -> None:
        self.eps = float(eps)
        self.affine = bool(affine)
        self.gamma = None if gamma is None else np.asarray(gamma, dtype=np.float64)
        self.beta = None if beta is None else np.asarray(beta, dtype=np.float64)

    # ------------------------------------------------------------------
    def fit_transform(self, x: ArrayLike) -> RevInState:
        """Compute per-channel mean/std and return normalised data + state."""
        arr = np.asarray(x, dtype=np.float64)
        orig_shape = arr.shape

        if arr.ndim == 1:
            mean = float(arr.mean())
            std = float(arr.std())
            std = std if std > self.eps else self.eps
            norm = (arr - mean) / std
        elif arr.ndim == 2:
            # (L, C) — normalise per-channel
            mean = arr.mean(axis=0)
            std = arr.std(axis=0)
            std = np.where(std > self.eps, std, self.eps)
            norm = (arr - mean) / std
        elif arr.ndim == 3:
            # (B, L, C) — normalise per (batch-instance, channel)
            mean = arr.mean(axis=1, keepdims=True)             # (B, 1, C)
            std = arr.std(axis=1, keepdims=True)               # (B, 1, C)
            std = np.where(std > self.eps, std, self.eps)
            norm = (arr - mean) / std
        else:
            raise ValueError(f"RevIn.fit_transform: unsupported ndim {arr.ndim}")

        if self.affine:
            g = self.gamma if self.gamma is not None else 1.0
            b = self.beta if self.beta is not None else 0.0
            norm = norm * g + b

        return RevInState(
            mean=np.asarray(mean), std=np.asarray(std),
            x_norm=norm, eps=self.eps, orig_shape=orig_shape,
        )

    # ------------------------------------------------------------------
    def transform(self, x: ArrayLike, state: RevInState) -> np.ndarray:
        """Apply a previously-fit transform to new data of the same shape.
        Useful when the same window's stats should normalise a downstream
        forecast horizon."""
        arr = np.asarray(x, dtype=np.float64)
        norm = (arr - state.mean) / state.std
        if self.affine:
            g = self.gamma if self.gamma is not None else 1.0
            b = self.beta if self.beta is not None else 0.0
            norm = norm * g + b
        return norm

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        return f"RevIn(eps={self.eps}, affine={self.affine})"


# ---------------------------------------------------------------------------
# Sanity self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:  # pragma: no cover — module-level dev helper
    rng = np.random.default_rng(42)
    x = rng.normal(1.234, 5.678, size=(64, 3))
    r = RevIn()
    st = r.fit_transform(x)
    # After normalisation each channel should have mean~0, std~1
    assert np.allclose(st.x_norm.mean(axis=0), 0.0, atol=1e-10)
    assert np.allclose(st.x_norm.std(axis=0), 1.0, atol=1e-10)
    # Invert must recover the original data
    recovered = st.invert(st.x_norm)
    assert np.allclose(recovered, x, atol=1e-8)
    return True


if __name__ == "__main__":  # pragma: no cover
    print("[RevIn] self-test:", _self_test())
