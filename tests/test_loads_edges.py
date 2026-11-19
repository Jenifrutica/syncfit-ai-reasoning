"""Edge cases of the load helpers in syncfit_ai.loads."""

from syncfit_contracts import EnergyLevel, ExerciseLoad

from syncfit_ai.loads import apply_baseline_loads, load_multiplier, suggested_weight


def test_without_core_result_only_the_energy_counts():
    assert load_multiplier(None) == 1.0
    assert load_multiplier(None, "MODERATE") == 0.95
    assert load_multiplier(None, EnergyLevel.NO_ENERGY) == 0.88


def test_unknown_energy_and_negative_base_are_neutral():
    assert load_multiplier(None, "SLEEPY") == 1.0
    assert suggested_weight(-5.0, None, "ENERGY") == 0.0
