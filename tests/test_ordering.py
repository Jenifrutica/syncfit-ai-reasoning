from syncfit_ai import order_routine


def entry(name, role="MAIN", impact="MEDIUM", groups=None, blocked=False):
    return {
        "exercise_original": name,
        "role": role,
        "impact": impact,
        "muscle_groups": groups or ["GLUTES"],
        "blocked": blocked,
    }


def test_activation_and_warmup_come_first():
    entries = [
        entry("iso-curl", groups=["BICEPS"]),
        entry("main-squat", groups=["QUADS", "GLUTES", "CORE"]),
        entry("band-activation", role="ACTIVATION"),
        entry("mobility", role="WARMUP"),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries)]
    assert ordered[0] == "band-activation"
    assert ordered[1] == "mobility"
    assert ordered.index("main-squat") < ordered.index("iso-curl")


def test_compounds_before_isolation():
    entries = [
        entry("lateral-raise", groups=["SHOULDERS"]),
        entry("bench-press", groups=["CHEST", "SHOULDERS", "TRICEPS"]),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries)]
    assert ordered == ["bench-press", "lateral-raise"]


def test_ovulatory_prioritises_low_impact():
    entries = [
        entry("box-jumps", impact="HIGH", groups=["QUADS", "GLUTES"]),
        entry("goblet-squat", impact="LOW", groups=["QUADS", "GLUTES"]),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries, "OVULATORY")]
    assert ordered[0] == "goblet-squat"


def test_luteal_promotes_isolation():
    entries = [
        entry("back-squat", impact="HIGH", groups=["QUADS", "GLUTES", "CORE"]),
        entry("leg-curl", impact="LOW", groups=["HAMSTRINGS"]),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries, "LUTEAL")]
    assert ordered[0] == "leg-curl"


def test_blocked_exercises_last():
    entries = [
        entry("blocked-squat", blocked=True, groups=["QUADS", "GLUTES", "CORE"]),
        entry("plank", groups=["ABS"]),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries)]
    assert ordered[-1] == "blocked-squat"
