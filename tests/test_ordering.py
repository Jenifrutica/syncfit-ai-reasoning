from syncfit_ai import order_routine


def entry(name, role="MAIN", impact="MEDIUM", groups=None, blocked=False, compound=None, pattern=None):
    item = {
        "exercise_original": name,
        "role": role,
        "impact": impact,
        "muscle_groups": groups or ["GLUTES"],
        "blocked": blocked,
    }
    if compound is not None:
        item["compound"] = compound
    if pattern is not None:
        item["movement_pattern"] = pattern
    return item


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


def test_luteal_keeps_compounds_first():
    # No evidence supports inverting the order in the luteal phase.
    entries = [
        entry("leg-curl", impact="LOW", groups=["HAMSTRINGS"], compound=False),
        entry("back-squat", impact="HIGH", groups=["QUADS", "GLUTES", "CORE"], compound=True),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries, "LUTEAL")]
    assert ordered[0] == "back-squat"


def test_unilateral_between_compounds_and_accessories():
    entries = [
        entry("biceps-curl", groups=["BICEPS"], compound=False),
        entry("bulgarian-split-squat", groups=["QUADS", "GLUTES"], compound=True, pattern="lunge"),
        entry("back-squat", groups=["QUADS", "GLUTES", "CORE"], compound=True, pattern="squat"),
        entry("lateral-raise", groups=["SHOULDERS"], compound=False),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries)]
    assert ordered == ["back-squat", "bulgarian-split-squat", "biceps-curl", "lateral-raise"]


def test_unilateral_isolation_stays_an_accessory():
    entries = [
        entry("glute-kickback", groups=["GLUTES"], compound=False, pattern="glute_kickback"),
        entry("split-squat", groups=["QUADS", "GLUTES"], compound=True, pattern="lunge"),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries)]
    assert ordered == ["split-squat", "glute-kickback"]


def test_blocked_exercises_last():
    entries = [
        entry("blocked-squat", blocked=True, groups=["QUADS", "GLUTES", "CORE"]),
        entry("plank", groups=["ABS"]),
    ]
    ordered = [e["exercise_original"] for e in order_routine(entries)]
    assert ordered[-1] == "blocked-squat"
