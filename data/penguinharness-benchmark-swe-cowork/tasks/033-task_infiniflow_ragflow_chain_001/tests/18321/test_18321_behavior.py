from test_support import load_model_meta


def test_ollama_resolves_json_api_key_for_authorization():
    module = load_model_meta()
    assert module is not None
    assert module.Ollama('{"api_key":"sk-ollama"}')._get_api_key() == "sk-ollama"
