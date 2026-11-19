from test_support import load_model_meta


def test_provider_metadata_plain_key_is_stable():
    module = load_model_meta()
    assert module is not None
    assert module.Base("plain")._get_api_key() == "plain"
