"""Iter 130 — Guppy MA presets for the 3-MA Crossover indicator."""


SRC = open("/app/frontend/src/components/StrategyBuilder.jsx").read()


def test_triple_ma_presets_constant_defined():
    """A `TRIPLE_MA_PRESETS` array must exist alongside INDICATOR_TEMPLATES."""
    assert "const TRIPLE_MA_PRESETS = [" in SRC


def test_all_expected_guppy_presets_present():
    """Every advertised preset must be in the array with its ribbon periods."""
    expected = [
        ("guppy-short", ["fast_period: 3", "medium_period: 8", "slow_period: 21"]),
        ("guppy-balanced", ["fast_period: 5", "medium_period: 13", "slow_period: 21"]),
        ("guppy-hybrid", ["fast_type: 'EMA'", "medium_type: 'WMA'", "slow_type: 'TMA'",
                          "fast_period: 5", "medium_period: 13", "slow_period: 21"]),
        ("guppy-long", ["fast_period: 30", "medium_period: 50", "slow_period: 60"]),
        ("golden-cross", ["fast_period: 50", "medium_period: 100", "slow_period: 200"]),
        ("default", ["fast_period: 5", "medium_period: 13", "slow_period: 34"]),
    ]
    for pid, needles in expected:
        assert f"id: '{pid}'" in SRC, f"missing preset id: {pid}"
        for n in needles:
            assert n in SRC, f"preset {pid} missing param '{n}'"


def test_preset_row_only_shows_for_triple_ma_crossover():
    """The preset row must be conditionally rendered — the presets are
    irrelevant for other indicators and should not clutter their UI."""
    # Guard on indicator === 'TRIPLE_MA_CROSSOVER'
    assert "condition.indicator === 'TRIPLE_MA_CROSSOVER'" in SRC
    # Render loop uses the presets constant
    assert "TRIPLE_MA_PRESETS.map" in SRC


def test_preset_buttons_seed_all_six_parameters():
    """Clicking a preset must merge all six parameter keys into the
    condition's parameters, not just some of them."""
    # onClick spreads `preset.params` into the parameters object
    assert "...preset.params" in SRC or "...preset[\"params\"]" in SRC
    # And crucially it also preserves existing parameters via spread
    assert "...condition.parameters" in SRC


def test_preset_buttons_carry_testids_for_automation():
    """Every preset button carries a data-testid so the testing agent can
    drive taps precisely."""
    assert "data-testid={`triple-ma-preset-${preset.id}`}" in SRC
    assert "data-testid={`triple-ma-presets-${condition.id}`}" in SRC
