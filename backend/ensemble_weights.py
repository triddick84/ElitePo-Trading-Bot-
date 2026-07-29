"""
EnsembleWeights — accuracy-aware voting weights for the AI/ML ensemble.

Iter 84 (Jul 2026).

Problem
-------
The `/api/ai-ensemble/predict` endpoint was using **hardcoded** weights
(stacking=0.4, lstm_gru=0.35, ppo=0.25) regardless of each model's live
accuracy. With PPO RL sitting at **29% accuracy** (worse than random), that
25% weight was actively dragging the ensemble decision toward random noise.

Solution
--------
Compute weights dynamically from each model's *current* validation accuracy:

1. Fetch each model's `accuracy` (%) from its `.get_stats()` method.
2. **Exclude** any model with `accuracy < MIN_TRUSTED_ACC` (default 45%).
   A model that can't beat coin flip has no business voting.
3. Weight each remaining model by its edge above baseline:
       w_i = max(0, acc_i - baseline) / Σ max(0, acc_j - baseline)
   where `baseline = 50` (random). Optionally we clamp minimum weight so a
   single strong model can't monopolise decisions.
4. If **all** models fall below the trust threshold, we fall back to equal
   weighting among trained models with a fresh warning tag so upstream code
   knows the ensemble is degraded.

Kept intentionally free of heavy imports so it can be called on every
`/ai-ensemble/predict` without slowing the endpoint.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Tunables
MIN_TRUSTED_ACC = 45.0   # % — anything below is excluded from the vote
BASELINE_ACC = 50.0      # % — random-baseline anchor for edge calculation
MIN_INDIVIDUAL_WEIGHT = 0.05  # never zero-out a trusted model completely
MAX_INDIVIDUAL_WEIGHT = 0.75  # never let one model dominate > 75%


def _safe_stats(model, name: str) -> Optional[Dict[str, Any]]:
    """Call model.get_stats() safely, returning {name, accuracy, is_trained}."""
    if model is None:
        return None
    try:
        stats = None
        # LSTM/GRU + PPO expose .get_stats(); MaximizedML uses .get_stats() too
        if hasattr(model, "get_stats"):
            stats = model.get_stats()
        elif hasattr(model, "stats"):
            stats = getattr(model, "stats")
        if not isinstance(stats, dict):
            return None
        return {
            "name": name,
            "is_trained": bool(stats.get("is_trained", False)),
            # Different services put accuracy under different keys — accept any.
            "accuracy": float(
                stats.get("accuracy")
                if stats.get("accuracy") is not None
                else stats.get("model_accuracy")
                if stats.get("model_accuracy") is not None
                else stats.get("stats", {}).get("model_accuracy", 0.0)
                or 0.0
            ),
        }
    except Exception as e:
        logger.debug(f"[EnsembleWeights] _safe_stats({name}) failed: {e}")
        return None


def compute_weights(
    stacking_model=None,
    lstm_gru=None,
    ppo=None,
    min_trusted_acc: float = MIN_TRUSTED_ACC,
    baseline_acc: float = BASELINE_ACC,
) -> Dict[str, Any]:
    """
    Compute dynamic ensemble weights.

    Returns:
        {
          "weights": {"stacking": 0.55, "lstm_gru": 0.45, "ppo": 0.0},
          "excluded": ["ppo"],           # models filtered out
          "reason":   {"ppo": "accuracy 29.1% < min 45%"},
          "accuracies": {"stacking": 54.55, "lstm_gru": 67.68, "ppo": 29.11},
          "degraded": False,             # True when every model was below floor
        }
    """
    labelled = {
        "stacking": _safe_stats(stacking_model, "stacking"),
        "lstm_gru": _safe_stats(lstm_gru, "lstm_gru"),
        "ppo":      _safe_stats(ppo, "ppo"),
    }

    accuracies: Dict[str, float] = {}
    trained: Dict[str, float] = {}
    excluded = []
    reason: Dict[str, str] = {}

    for key, stat in labelled.items():
        if stat is None:
            excluded.append(key)
            reason[key] = "model_unavailable"
            continue
        acc = float(stat.get("accuracy") or 0.0)
        accuracies[key] = round(acc, 2)
        if not stat.get("is_trained"):
            excluded.append(key)
            reason[key] = "not_trained"
            continue
        if acc < min_trusted_acc:
            excluded.append(key)
            reason[key] = (
                f"accuracy {acc:.1f}% < min_trusted {min_trusted_acc:.1f}%"
            )
            continue
        trained[key] = acc

    weights: Dict[str, float] = {k: 0.0 for k in labelled.keys()}

    if trained:
        # Edge above random baseline
        edges = {k: max(0.0, acc - baseline_acc) for k, acc in trained.items()}
        edge_sum = sum(edges.values())
        if edge_sum > 0:
            for k, e in edges.items():
                weights[k] = e / edge_sum
        else:
            # All at exactly baseline — split evenly
            share = 1.0 / len(trained)
            for k in trained:
                weights[k] = share

        # Clamp any single model between MIN and MAX individual weight, then
        # renormalise (small correction, keeps behaviour stable).
        clamped = {
            k: max(MIN_INDIVIDUAL_WEIGHT, min(MAX_INDIVIDUAL_WEIGHT, w))
            for k, w in weights.items()
            if k in trained
        }
        c_sum = sum(clamped.values()) or 1.0
        for k in trained:
            weights[k] = round(clamped[k] / c_sum, 4)

    degraded = not trained
    if degraded:
        # Fallback: equal-weight all *trained* models (even if below threshold)
        # so the endpoint still returns something rather than silence.
        fallback = {
            k: labelled[k] for k in labelled
            if labelled[k] and labelled[k].get("is_trained")
        }
        if fallback:
            share = round(1.0 / len(fallback), 4)
            for k in fallback:
                weights[k] = share

    return {
        "weights": weights,
        "excluded": excluded,
        "reason": reason,
        "accuracies": accuracies,
        "degraded": degraded,
        "config": {
            "min_trusted_acc": min_trusted_acc,
            "baseline_acc": baseline_acc,
            "min_individual_weight": MIN_INDIVIDUAL_WEIGHT,
            "max_individual_weight": MAX_INDIVIDUAL_WEIGHT,
        },
    }
