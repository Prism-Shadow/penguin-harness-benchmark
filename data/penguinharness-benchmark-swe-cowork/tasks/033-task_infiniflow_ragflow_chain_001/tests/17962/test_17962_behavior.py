from test_support import load_ladder


def test_sufficiency_ladder_selects_full_answer_for_confident_evidence():
    module = load_ladder()
    assert module is not None
    result = module.sufficiency_ladder(
        auto_sufficient=True,
        auto_confidence=0.95,
        missing=[],
        contradictions=[],
        agent_confidence=0.90,
        c_high=0.75,
        c_low=0.45,
        llm_floor=0.55,
        allows_reconcile=False,
        cycle=0,
        max_cycles=3,
    )
    assert result.action == module.ANSWER
    assert result.should_continue is False


def test_ladder_thresholds_veto_and_cycle_exhaustion():
    module = load_ladder()
    args = dict(auto_sufficient=True, auto_confidence=0.8, missing=[], contradictions=[],
                agent_confidence=0.75, c_high=0.75, c_low=0.45, llm_floor=0.55,
                allows_reconcile=True, cycle=0, max_cycles=2)
    cases = [
        ({}, 'ANSWER', False),
        ({'agent_confidence': 0.749}, 'ANSWER_WITH_CAVEAT', False),
        ({'agent_confidence': 0.45}, 'ANSWER_WITH_CAVEAT', False),
        ({'agent_confidence': 0.449}, 'RECONCILE', True),
        ({'auto_confidence': 0.549}, 'RECONCILE', True),
        ({'auto_confidence': 0.55}, 'ANSWER', False),
        ({'auto_confidence': 0.1, 'cycle': 1}, 'ANSWER_WITH_CAVEAT', False),
        ({'agent_confidence': 0.1, 'allows_reconcile': False}, 'ANSWER_WITH_CAVEAT', False),
        ({'auto_sufficient': False, 'missing': ['date']}, 'GAP', True),
        ({'auto_sufficient': False}, 'UNANSWERABLE', False),
        ({'contradictions': ['date conflict']}, 'ANSWER_WITH_CAVEAT', False),
        ({'hard_violations': {'claim-9'}}, 'ANSWER_WITH_CAVEAT', False),
    ]
    for changes, action, continuation in cases:
        result = module.sufficiency_ladder(**(args | changes))
        assert result.action == action
        assert result.should_continue is continuation
        if action == 'ANSWER_WITH_CAVEAT':
            assert result.caveat
