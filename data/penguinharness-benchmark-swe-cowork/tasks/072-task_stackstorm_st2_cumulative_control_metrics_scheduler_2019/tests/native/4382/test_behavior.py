def test_scheduler_config_exposes_logging_path():
    from st2actions.scheduler import config

    assert config.get_logging_config_path() == 'conf/logging.scheduler.conf'
    assert config.cfg.CONF.scheduler.logging == 'conf/logging.scheduler.conf'
