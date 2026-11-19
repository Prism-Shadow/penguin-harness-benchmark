from test_support import load_config


def test_parallel_agent_mode_exposes_web_search_capability():
    module = load_config()
    assert module is not None
    assert "hybrid_search" in module.get_mode("high").available_tools
