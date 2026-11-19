from test_support import load_config


def test_high_mode_allows_four_parallel_research_agents():
    module = load_config()
    assert module is not None
    assert module.get_mode("high").max_parallel_agents == 4
