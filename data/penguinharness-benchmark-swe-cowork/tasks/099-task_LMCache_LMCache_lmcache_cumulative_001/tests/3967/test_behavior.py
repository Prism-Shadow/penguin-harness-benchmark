from runtime_cases import timeout_bridge

def test_timeout_bridge():
    timeout_bridge()


def test_timeout_wait_boundaries():
    from integration_cases import run_isolated
    run_isolated("timeout_wait_boundaries")
