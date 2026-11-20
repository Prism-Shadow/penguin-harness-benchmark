from test_support import load_stats


def test_agentic_usage_stats_record_calls_and_tokens():
    module = load_stats()
    assert module is not None
    stats = module.LLMUsageStats()
    stats.record_call("research")
    stats.record_usage("research", {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5})
    row = stats.snapshot()["research"]
    assert row["calls"] == 1
    assert row["total_tokens"] == 5


def test_usage_accumulates_by_phase_and_snapshot_is_detached():
    module = load_stats()
    stats = module.LLMUsageStats()
    assert stats.snapshot() == {}
    stats.record_usage('alpha', None)
    stats.record_call('alpha')
    stats.record_call('alpha')
    stats.record_usage('alpha', {'total_tokens': 4})
    stats.record_usage('alpha', {'prompt_tokens': 2, 'completion_tokens': 5, 'total_tokens': 7})
    stats.record_call('beta')
    snapshot = stats.snapshot()
    assert snapshot['alpha']['calls'] == 2
    assert snapshot['alpha']['total_tokens'] == 11
    assert snapshot['beta']['total_tokens'] == 0
    snapshot['alpha']['calls'] = 100
    assert stats.snapshot()['alpha']['calls'] == 2
