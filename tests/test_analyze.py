from syncfit_ai import FakeClient
from syncfit_ai.analyze import (
    analyze_machine,
    analyze_symptoms,
    interpret_symptom_text,
    sanitize_symptom_analysis,
)


def test_analyze_machine_returns_localized_info():
    response = {
        "inferred_type": "MACHINE",
        "name": {"en": "Hip thrust machine", "es": "Maquina de hip thrust", "zh": "臀推机"},
        "purpose": {"en": "Glutes", "es": "Gluteos", "zh": "臀部"},
        "exercise_ids": ["hip-thrust"],
        "weight_factor": 1.4,
    }
    client = FakeClient(response=response)
    info = analyze_machine("maquina de hip thrust", "gluteos", "ES", client=client)
    assert info["inferred_type"] == "MACHINE"
    assert info["name"]["en"] == "Hip thrust machine"
    assert info["exercise_ids"] == ["hip-thrust"]
    assert info["weight_factor"] == 1.4
    # The prompt carries the requested language and the machine name.
    assert "language=ES" in client.calls[0]["user"]
    assert "maquina de hip thrust" in client.calls[0]["user"]


def test_analyze_symptoms_passes_payload():
    client = FakeClient(response={"absolute_contraindication": False, "guidance": "ok", "avoid": []})
    result = analyze_symptoms([{"id": "cramps", "level": 4}], "EN", client=client)
    assert result["absolute_contraindication"] is False
    assert "cramps" in client.calls[0]["user"]


def test_analyze_machine_drops_invalid_values():
    response = {
        "inferred_type": "spaceship",
        "name": {"en": "Leg press"},
        "exercise_ids": ["leg-press", None, ""],
        "weight_factor": "1.4x",
    }
    info = analyze_machine("leg press", client=FakeClient(response=response))
    assert "inferred_type" not in info
    assert "weight_factor" not in info
    assert info["exercise_ids"] == ["leg-press"]
    assert info["name"]["en"] == "Leg press"


def test_analyze_machine_normalizes_valid_values():
    response = {"inferred_type": "cable", "weight_factor": "0.8", "exercise_ids": ["cable-row"]}
    info = analyze_machine("cable row", client=FakeClient(response=response))
    assert info["inferred_type"] == "CABLE"
    assert info["weight_factor"] == 0.8


def test_analyze_machine_rejects_out_of_range_factor():
    info = analyze_machine("x", client=FakeClient(response={"weight_factor": 50}))
    assert "weight_factor" not in info
    assert info["exercise_ids"] == []


def test_sanitize_symptom_analysis_keeps_only_known_values():
    raw = {
        "symptom_ids": ["knee_pain", "invented", "knee_pain"],
        "severity": {"knee_pain": 12, "invented": 5},
        "avoid_patterns": ["lunge", "fake_pattern"],
        "guidance": "  evita impacto  ",
        "absolute_contraindication": True,
    }
    out = sanitize_symptom_analysis(raw, {"knee_pain"}, {"lunge", "squat"})
    assert out["symptom_ids"] == ["knee_pain"]
    assert out["severity"] == {"knee_pain": 10}
    assert out["avoid_patterns"] == ["lunge"]
    assert out["guidance"] == "evita impacto"
    assert out["absolute_contraindication"] is True


def test_interpret_symptom_text_filters_by_modality():
    client = FakeClient(
        response={
            "symptom_ids": ["knee_pain", "dilation"],
            "severity": {"knee_pain": 6},
            "avoid_patterns": ["lunge"],
            "guidance": "ok",
        }
    )
    out = interpret_symptom_text(
        "me duele la rodilla", language="ES", modality="MENSTRUAL_CYCLE", client=client
    )
    assert out["symptom_ids"] == ["knee_pain"]
    assert out["avoid_patterns"] == ["lunge"]
    # Gestational-only symptoms are not even offered to the model.
    assert "dilation" not in client.calls[0]["user"]
