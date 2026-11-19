from types import SimpleNamespace


def test_metric_key_includes_stackstorm_and_configured_prefix(monkeypatch):
    from st2common.metrics import utils

    monkeypatch.setattr(
        utils.cfg,
        'CONF',
        SimpleNamespace(metrics=SimpleNamespace(prefix='edge')),
    )

    assert utils.get_full_key_name('scheduler.requests') == 'st2.edge.scheduler.requests'

    utils.cfg.CONF.metrics.prefix = ''
    assert utils.get_full_key_name('scheduler.requests') == 'st2.scheduler.requests'
