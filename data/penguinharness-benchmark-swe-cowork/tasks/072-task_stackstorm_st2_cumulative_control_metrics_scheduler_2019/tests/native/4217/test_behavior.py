from types import SimpleNamespace


def test_runner_loader_accepts_one_name_and_underscore_alias(monkeypatch):
    from stevedore.exception import NoMatches
    from st2common.runners import base

    calls = []
    plugin = SimpleNamespace(get_runner=lambda **kwargs: ('loaded', kwargs))

    def get_plugin(namespace, name, invoke_on_load=False):
        calls.append((namespace, name, invoke_on_load))
        if name == 'demo_runner':
            raise NoMatches('underscore alias')
        return plugin

    monkeypatch.setattr(base, 'get_plugin_instance', get_plugin)
    monkeypatch.setattr(base, 'get_available_plugins', lambda namespace: ['demo-runner'])

    result = base.get_runner('demo_runner', config={'region': 'test'})

    assert result == ('loaded', {'config': {'region': 'test'}})
    assert [entry[1] for entry in calls] == ['demo_runner', 'demo-runner']
