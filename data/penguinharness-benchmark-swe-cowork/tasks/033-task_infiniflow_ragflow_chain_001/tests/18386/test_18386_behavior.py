from test_support import load_model_meta


def test_base_model_meta_resolves_json_api_key_without_regressing_plain_keys():
    module = load_model_meta()
    assert module is not None
    assert module.Base('{"api_key":"sk-base"}')._get_api_key() == "sk-base"
    assert module.Base("plain")._get_api_key() == "plain"
