from integration_support import run_production_case

def test_wiki_runner_lifecycle():
    run_production_case('test_wiki_runner_lifecycle')

def test_wiki_map_failure_is_retryable():
    run_production_case('test_wiki_map_failure_is_retryable')


def test_wiki_graph_write_failure_is_reported():
    run_production_case('test_wiki_graph_write_failure_is_reported')
