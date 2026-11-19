from test_support import load_config


def test_go_agentic_bridge_keeps_ultra_mode_configured():
    module = load_config()
    assert module is not None
    mode = module.get_mode("ultra")
    assert mode.max_orchestrator_cycles >= mode.max_agent_cycles
