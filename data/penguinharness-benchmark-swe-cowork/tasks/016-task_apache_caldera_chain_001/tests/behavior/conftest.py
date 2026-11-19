import copy

import pytest


@pytest.fixture
def services(tmp_path, monkeypatch):
    from app.service.data_svc import DataService
    from app.service.file_svc import FileSvc
    from app.utility.base_service import BaseService
    from app.utility.base_world import BaseWorld

    saved_config = copy.deepcopy(BaseWorld._app_configuration)
    saved_services = BaseService._services.copy()
    monkeypatch.chdir(tmp_path)
    for directory in ('payloads', 'abilities', 'results'):
        (tmp_path / 'data' / directory).mkdir(parents=True)
    BaseWorld.clear_config()
    BaseService._services.clear()
    BaseWorld.apply_config('main', {
        'crypt_salt': 'isolated-test-salt', 'encryption_key': 'isolated-test-key',
        'encrypt_files': False, 'app.knowledge_svc.module': 'missing.module',
    })
    BaseWorld.apply_config('agents', {'deployments': []})
    BaseWorld.apply_config('payloads', {'standard_payloads': {}, 'special_payloads': {}, 'extensions': {}})

    class Auth:
        async def get_permissions(self, request):
            return (BaseWorld.Access.RED, BaseWorld.Access.APP)

    class Events:
        def __init__(self):
            self.records = []

        async def fire_event(self, **event):
            self.records.append(event)

    try:
        data = DataService()
        events = Events()
        BaseService._services['event_svc'] = events
        yield {'data_svc': data, 'file_svc': FileSvc(), 'auth_svc': Auth(), 'event_svc': events}
    finally:
        BaseWorld._app_configuration = saved_config
        BaseService._services.clear()
        BaseService._services.update(saved_services)
