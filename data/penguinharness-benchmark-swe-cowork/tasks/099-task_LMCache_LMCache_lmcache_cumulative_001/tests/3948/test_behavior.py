def test_production_3948(operator_case):
    operator_case("webhook", "TestCacheBlendAdmission")


def test_registered_operator_process(operator_process_case):
    operator_process_case()
