from runtime_cases import coordinator_routes


def test_legacy_startup_resync():
    from integration_cases import run_isolated
    run_isolated("legacy_startup_resync")

def test_coordinator_routes():
    coordinator_routes()


def test_mp_entrypoint_help():
    from integration_cases import run_isolated
    run_isolated("mp_entrypoint_help")


def test_mp_startup_shutdown():
    from integration_cases import run_isolated
    run_isolated("mp_startup_shutdown")


def test_mp_blend_startup_shutdown():
    from integration_cases import run_isolated
    run_isolated("mp_blend_startup_shutdown")


def test_mp_cpu_production_wiring():
    from integration_cases import run_isolated
    run_isolated("mp_cpu_production_wiring")


def test_legacy_l2_routes():
    from integration_cases import run_isolated
    run_isolated("legacy_l2_routes")


def test_legacy_blend_and_configuration():
    from integration_cases import run_isolated
    run_isolated('legacy_blend_and_configuration')


def test_legacy_prefetch_transport():
    from integration_cases import run_isolated
    run_isolated('legacy_prefetch_transport')
