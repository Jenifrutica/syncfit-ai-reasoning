from syncfit_ai import FakeClient
from syncfit_ai.analyze import analyze_machine, analyze_symptoms


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
