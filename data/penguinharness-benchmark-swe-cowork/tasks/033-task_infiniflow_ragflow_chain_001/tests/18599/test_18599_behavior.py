from test_support import load_model_meta


def test_gpustack_provider_uses_the_shared_model_list_contract():
    module = load_model_meta()
    assert module is not None
    provider = getattr(module, "GPUStack", None)
    assert provider is not None
    instance = provider("key", "https://models.example/v1")
    assert instance._get_model_list_url() == "https://models.example/v1/models"
