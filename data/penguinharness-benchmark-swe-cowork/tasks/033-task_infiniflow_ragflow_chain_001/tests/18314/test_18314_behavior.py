from test_support import load_model_meta


def test_localai_resolves_json_api_key_for_authorization():
    module = load_model_meta()
    assert module is not None
    assert module.LocalAI('{"api_key":"sk-local"}')._get_api_key() == "sk-local"
