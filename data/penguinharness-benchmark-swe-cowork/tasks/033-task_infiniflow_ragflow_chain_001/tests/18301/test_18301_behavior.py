from test_support import load_model_meta


def test_provider_metadata_keeps_empty_key_empty():
    module = load_model_meta()
    assert module is not None
    assert module.Base("")._get_api_key() == ""
