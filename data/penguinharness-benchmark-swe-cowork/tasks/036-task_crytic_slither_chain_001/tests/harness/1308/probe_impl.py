from repair_checks import contract_fixture

def check_1308():
    for kind in ("library", "contract", "interface"):
        contract, _ = contract_fixture(kind)
        assert contract.contract_kind == kind
