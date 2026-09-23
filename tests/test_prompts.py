from syncfit_ai.prompts import build_system_prompt, build_user_prompt
from syncfit_ai.prompts.system import RESPONSE_SCHEMA


def test_system_prompt_is_deterministic_kernel():
    prompt = build_system_prompt()
    assert "NOT a chatbot" in prompt
    assert "JSON" in prompt
    assert "k_load" in prompt
    assert RESPONSE_SCHEMA in prompt


def test_user_prompt_contains_request_data(ovulatory_request):
    prompt = build_user_prompt(ovulatory_request)
    assert "OVULATORY" in prompt
    assert "0.72" in prompt
    assert "Heavy back squat" in prompt
    assert "Plyometric box jumps" in prompt
    assert ovulatory_request.session_id in prompt
