"""Objectives registered from the database drive the scheme and labels."""

from syncfit_ai import options
from syncfit_ai.routine import _scheme
from syncfit_ai.supplements import _reason


def teardown_function():
    options.set_objectives([])


def test_new_objective_uses_its_database_scheme():
    options.set_objectives([{"value": "MOBILITY", "labels": {"en": "Mobility", "es": "Movilidad"},
                             "meta": {"sets": 2, "reps": 15, "rest_compound": 45, "rest_iso": 30}}])
    assert _scheme("MOBILITY") == {"sets": 2, "reps": 15, "rest_compound": 45, "rest_iso": 30}
    assert "Movilidad" in _reason("SAFE", "MOBILITY", "ES")["es"]


def test_unknown_objective_falls_back_and_db_overrides_builtin():
    assert _scheme("NOPE") == _scheme("HYPERTROPHY")
    options.set_objectives([{"value": "STRENGTH", "meta": {"sets": 5}}])
    assert _scheme("STRENGTH")["sets"] == 5 and _scheme("STRENGTH")["reps"] == 5
