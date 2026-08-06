"""
Strategy Presets — Iter 91.

Ready-made custom-strategy templates users can drop into their account with
one click. Each preset is a plain dict shaped like the payload
`POST /api/custom-strategies` expects, so `apply_preset()` can just forward
it to `CustomStrategyService.create_strategy(...)`.

Presets ship UNPUBLISHED (drafts). The user reviews / tweaks / publishes.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# 1) ICHIMOKU CLOUD BREAK
# ---------------------------------------------------------------------------
# Rationale
# ---------
# Classic Ichimoku-Kinko-Hyo trend-follow rules distilled for binary options:
#
#   CALL  → Tenkan-sen > Kijun-sen  (bullish momentum crossover)
#        AND Close > Senkou Span A  (price broke ABOVE the cloud)
#        AND Close > Senkou Span B  (cloud is fully below price)
#
#   PUT   → Tenkan-sen < Kijun-sen  (bearish momentum crossover)
#        AND Close < Senkou Span A  (price broke BELOW the cloud)
#        AND Close < Senkou Span B  (cloud is fully above price)
#
# These three-condition AND groups drop clean into the CustomStrategyExecutor
# (Iter 90 added the ICHIMOKU indicator so every field below is now live).

ICHIMOKU_CLOUD_BREAK: Dict[str, Any] = {
    "preset_id": "ichimoku-cloud-break",
    "name": "Ichimoku Cloud Break",
    "description": (
        "Classic Ichimoku trend-continuation setup — enters CALL only when "
        "the Tenkan crosses above the Kijun AND price sits above both cloud "
        "boundaries (Senkou A + B). Mirror-image PUT rules for the downside. "
        "Best on 30s-5m timeframes on trending OTC pairs."
    ),
    "category": "trend",
    "tags": ["ichimoku", "cloud", "breakout", "trend-follow"],
    "timeframes": ["30s", "1m", "5m"],
    "assets": [
        "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC",
        "AUDUSD_OTC", "EURJPY_OTC", "GBPJPY_OTC",
    ],
    "markets": ["otc"],
    "min_confidence": 70.0,
    "max_signals_per_hour": 6,
    "cooldown_seconds": 45,
    "call_conditions": [
        {
            "id": "cg-call-1",
            "logical_operator": "AND",
            "conditions": [
                {
                    "id": "c-call-tenkan-gt-kijun",
                    "indicator": "ICHIMOKU",
                    "parameters": {
                        "tenkan_period": 9,
                        "kijun_period": 26,
                        "senkou_b_period": 52,
                    },
                    "output": "tenkan",
                    "operator": ">",
                    "compare_to": "indicator",
                    "compare_value": {
                        "indicator": "ICHIMOKU",
                        "parameters": {
                            "tenkan_period": 9,
                            "kijun_period": 26,
                            "senkou_b_period": 52,
                        },
                        "output": "kijun",
                    },
                    "reversal": False,
                },
                {
                    "id": "c-call-close-gt-senkou-a",
                    "indicator": "PRICE",
                    "parameters": {"type": "close"},
                    "output": "value",
                    "operator": ">",
                    "compare_to": "indicator",
                    "compare_value": {
                        "indicator": "ICHIMOKU",
                        "parameters": {
                            "tenkan_period": 9,
                            "kijun_period": 26,
                            "senkou_b_period": 52,
                        },
                        "output": "senkou_a",
                    },
                    "reversal": False,
                },
                {
                    "id": "c-call-close-gt-senkou-b",
                    "indicator": "PRICE",
                    "parameters": {"type": "close"},
                    "output": "value",
                    "operator": ">",
                    "compare_to": "indicator",
                    "compare_value": {
                        "indicator": "ICHIMOKU",
                        "parameters": {
                            "tenkan_period": 9,
                            "kijun_period": 26,
                            "senkou_b_period": 52,
                        },
                        "output": "senkou_b",
                    },
                    "reversal": False,
                },
            ],
        }
    ],
    "put_conditions": [
        {
            "id": "cg-put-1",
            "logical_operator": "AND",
            "conditions": [
                {
                    "id": "c-put-tenkan-lt-kijun",
                    "indicator": "ICHIMOKU",
                    "parameters": {
                        "tenkan_period": 9,
                        "kijun_period": 26,
                        "senkou_b_period": 52,
                    },
                    "output": "tenkan",
                    "operator": "<",
                    "compare_to": "indicator",
                    "compare_value": {
                        "indicator": "ICHIMOKU",
                        "parameters": {
                            "tenkan_period": 9,
                            "kijun_period": 26,
                            "senkou_b_period": 52,
                        },
                        "output": "kijun",
                    },
                    "reversal": False,
                },
                {
                    "id": "c-put-close-lt-senkou-a",
                    "indicator": "PRICE",
                    "parameters": {"type": "close"},
                    "output": "value",
                    "operator": "<",
                    "compare_to": "indicator",
                    "compare_value": {
                        "indicator": "ICHIMOKU",
                        "parameters": {
                            "tenkan_period": 9,
                            "kijun_period": 26,
                            "senkou_b_period": 52,
                        },
                        "output": "senkou_a",
                    },
                    "reversal": False,
                },
                {
                    "id": "c-put-close-lt-senkou-b",
                    "indicator": "PRICE",
                    "parameters": {"type": "close"},
                    "output": "value",
                    "operator": "<",
                    "compare_to": "indicator",
                    "compare_value": {
                        "indicator": "ICHIMOKU",
                        "parameters": {
                            "tenkan_period": 9,
                            "kijun_period": 26,
                            "senkou_b_period": 52,
                        },
                        "output": "senkou_b",
                    },
                    "reversal": False,
                },
            ],
        }
    ],
}


# Registry — future presets go here. Keys must be URL-safe.
ALL_PRESETS: Dict[str, Dict[str, Any]] = {
    ICHIMOKU_CLOUD_BREAK["preset_id"]: ICHIMOKU_CLOUD_BREAK,
}


def list_presets() -> List[Dict[str, Any]]:
    """Compact list-view of every preset (no full condition tree)."""
    return [
        {
            "preset_id": p["preset_id"],
            "name": p["name"],
            "description": p["description"],
            "category": p.get("category", "custom"),
            "tags": p.get("tags", []),
            "timeframes": p["timeframes"],
            "assets": p["assets"],
            "call_conditions_count": sum(
                len(g.get("conditions", [])) for g in p["call_conditions"]
            ),
            "put_conditions_count": sum(
                len(g.get("conditions", [])) for g in p["put_conditions"]
            ),
        }
        for p in ALL_PRESETS.values()
    ]


def get_preset_payload(preset_id: str, user_id: str = "default_user") -> Dict[str, Any]:
    """
    Return the full strategy payload for a preset — shaped exactly like
    `POST /api/custom-strategies` expects. Adds user_id + drops
    preset-only metadata (`preset_id`, `category`, `tags`).
    """
    src = ALL_PRESETS.get(preset_id)
    if src is None:
        raise KeyError(f"Unknown preset_id: {preset_id!r}")
    payload = {k: v for k, v in src.items()
               if k not in ("preset_id", "category", "tags")}
    payload["user_id"] = user_id
    payload["name"] = f"{src['name']} (Preset)"
    # Preset-cloned strategies start as unpublished drafts
    payload["is_published"] = False
    return payload
