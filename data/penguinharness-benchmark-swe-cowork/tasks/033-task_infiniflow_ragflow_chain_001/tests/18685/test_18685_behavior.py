from test_support import load_model_utils


def test_model_type_normalization_deduplicates_legacy_aliases():
    module = load_model_utils()
    assert module is not None
    assert callable(getattr(module, "normalize_model_types", None))
    assert module.normalize_model_types(["speech2text", "asr", "vision", "vision"]) == ["asr", "vision"]
