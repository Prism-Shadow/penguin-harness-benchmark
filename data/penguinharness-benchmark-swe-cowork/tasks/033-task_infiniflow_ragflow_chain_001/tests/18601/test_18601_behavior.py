from test_support import load_model_meta


def test_provider_model_meta_plain_api_key_remains_unchanged():
    module = load_model_meta()
    assert module is not None
    assert module.Base("plain")._get_api_key() == "plain"
