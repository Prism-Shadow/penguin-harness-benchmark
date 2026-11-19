from test_support import load_config


def test_agentic_medium_mode_has_a_bounded_cycle_budget():
    module = load_config()
    assert module is not None
    mode = module.get_mode("medium")
    assert mode.max_orchestrator_cycles >= 1
    assert mode.max_parallel_agents == 1
