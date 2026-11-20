def test_production_4274(operator_case):
    operator_case("resources", "TestAESGCMSerialization")

def test_generated_aesgcm_schema(operator_case):
    operator_case("resources", "TestAESGCMSchema")
