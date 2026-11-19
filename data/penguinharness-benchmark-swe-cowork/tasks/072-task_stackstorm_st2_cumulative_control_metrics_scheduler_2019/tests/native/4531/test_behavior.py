from types import SimpleNamespace


def test_orquesta_runner_propagates_pack_context(monkeypatch):
    from orquesta_runner import orquesta_runner as runner_module
    from st2common.util import api

    monkeypatch.setattr(api, 'get_full_public_api_url', lambda: 'https://st2.invalid/v1')
    runner = runner_module.OrquestaRunner.__new__(runner_module.OrquestaRunner)
    runner.execution = SimpleNamespace(
        id='execution-1',
        context={'user': 'workflow-owner', 'pack': 'network_automation'},
    )

    context = runner._construct_st2_context()

    assert context['st2']['pack'] == 'network_automation'
    assert context['parent']['pack'] == 'network_automation'
