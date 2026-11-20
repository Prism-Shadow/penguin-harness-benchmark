def test_production_4206(operator_case):
    operator_case("webhook", "TestPayloadStaging")


def test_legacy_engine_defaults(operator_case):
    operator_case("resources", "TestLegacyEngineDefaults")
