import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


def load_setup():
    path = Path(__file__).resolve().parents[1] / 'native/conftest.py'
    spec = importlib.util.spec_from_file_location('quality_native_setup', str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup = load_setup()


def test_common_setup_keeps_late_cli_registration_possible(monkeypatch):
    class Configuration:
        def __init__(self):
            self.parsed = False
            self.defaults = {}

        def __call__(self, args):
            self.parsed = True

        def register(self, name, default):
            if self.parsed:
                raise RuntimeError('arguments already parsed: cannot register CLI option')
            self.defaults[name] = default

    configuration = Configuration()
    common = ModuleType('st2common')
    common.config = SimpleNamespace(
        register_opts=lambda ignore_errors=False: configuration.register('debug', False))
    oslo = ModuleType('oslo_config')
    oslo.cfg = SimpleNamespace(CONF=configuration)
    monkeypatch.setitem(sys.modules, 'st2common', common)
    monkeypatch.setitem(sys.modules, 'oslo_config', oslo)
    setup.configured_runtime.__wrapped__()
    assert configuration.defaults['debug'] is False
    configuration.register('scheduler.logging', 'conf/logging.scheduler.conf')
    assert configuration.defaults['scheduler.logging'] == 'conf/logging.scheduler.conf'


def test_configuration_errors_are_not_suppressed(monkeypatch):
    def register_opts(**kwargs):
        if not kwargs.get('ignore_errors'):
            raise RuntimeError('broken production option')

    common = ModuleType('st2common')
    common.config = SimpleNamespace(register_opts=register_opts)
    oslo = ModuleType('oslo_config')
    oslo.cfg = SimpleNamespace(CONF=lambda args: None)
    monkeypatch.setitem(sys.modules, 'st2common', common)
    monkeypatch.setitem(sys.modules, 'oslo_config', oslo)
    with pytest.raises(RuntimeError, match='broken production option'):
        setup.configured_runtime.__wrapped__()


@pytest.fixture
def database_api(monkeypatch):
    events = []
    state = SimpleNamespace(fail_drop=None, fail_connect=False, drops=0, events=events)

    def drop_database(name):
        events.append(('drop', name))
        state.drops += 1
        if state.drops == state.fail_drop:
            raise RuntimeError('drop failed')

    client = SimpleNamespace(drop_database=drop_database)

    def connect(name, host):
        events.append(('connect', name, host))
        if state.fail_connect:
            raise RuntimeError('connect failed')
        return client

    package = ModuleType('mongoengine')
    package.Document = type('Document', (), {})
    connection = ModuleType('mongoengine.connection')
    connection.connect = connect
    connection.disconnect = lambda: events.append(('disconnect',))
    package.connection = connection
    monkeypatch.setitem(sys.modules, 'mongoengine', package)
    monkeypatch.setitem(sys.modules, 'mongoengine.connection', connection)
    common = ModuleType('mongoengine.base.common')
    common._document_registry = {}
    monkeypatch.setitem(sys.modules, 'mongoengine.base', ModuleType('mongoengine.base'))
    monkeypatch.setitem(sys.modules, 'mongoengine.base.common', common)
    state.client = client
    state.documents = common._document_registry
    state.document_class = package.Document
    return state


def test_database_uses_connection_api_and_isolates_each_case(database_api):
    for unused in range(2):
        fixture = setup.isolated_database.__wrapped__()
        assert next(fixture) is database_api.client
        with pytest.raises(StopIteration):
            next(fixture)
    assert database_api.events == [
        ('disconnect',), ('connect', 'task_quality_072', 'mongomock://localhost'),
        ('drop', 'task_quality_072'), ('drop', 'task_quality_072'), ('disconnect',),
    ] * 2


def test_database_teardown_runs_after_test_failure(database_api):
    fixture = setup.isolated_database.__wrapped__()
    next(fixture)
    with pytest.raises(ValueError, match='behavior failed'):
        fixture.throw(ValueError('behavior failed'))
    assert database_api.events[-2:] == [('drop', 'task_quality_072'), ('disconnect',)]


@pytest.mark.parametrize('failed_drop', [1, 2])
def test_disconnect_runs_even_when_database_drop_fails(database_api, failed_drop):
    database_api.fail_drop = failed_drop
    fixture = setup.isolated_database.__wrapped__()
    with pytest.raises(RuntimeError, match='drop failed'):
        next(fixture)
        next(fixture)
    assert database_api.events[-1] == ('disconnect',)


def test_database_connection_errors_fail_closed(database_api):
    database_api.fail_connect = True
    with pytest.raises(RuntimeError, match='connect failed'):
        next(setup.isolated_database.__wrapped__())
    assert database_api.drops == 0


@pytest.fixture
def cached_documents(database_api):
    class CachedDocument(database_api.document_class):
        _meta = {'db_alias': 'default'}
        _collection = [{'itemized': True, 'status': 'running'}]

        @classmethod
        def rows(cls):
            if cls._collection is None:
                cls._collection = []
            return cls._collection

        @classmethod
        def drop_collection(cls):
            database_api.events.append(('drop_collection', cls.__name__))
            cls._collection = None

    class OtherAlias(CachedDocument):
        _meta = {'db_alias': 'other'}

        @classmethod
        def drop_collection(cls):
            raise AssertionError('must not touch another connection alias')

    class AbstractDocument(CachedDocument):
        _meta = {'abstract': True}

        @classmethod
        def drop_collection(cls):
            raise AssertionError('abstract document has no collection')

    database_api.documents.update({
        'CachedDocument': CachedDocument,
        'OtherAlias': OtherAlias,
        'AbstractDocument': AbstractDocument,
        'EmbeddedDocument': type('EmbeddedDocument', (), {}),
    })
    return CachedDocument


def test_database_isolation_clears_cached_documents(database_api, cached_documents):
    for itemized in (True, False, True):
        fixture = setup.isolated_database.__wrapped__()
        next(fixture)
        assert cached_documents.rows() == []
        cached_documents.rows().append({'itemized': itemized, 'status': 'running'})
        with pytest.raises(StopIteration):
            next(fixture)
        assert cached_documents._collection is None
    assert database_api.events.count(('drop_collection', 'CachedDocument')) == 6


def test_teardown_includes_models_imported_during_case(database_api, cached_documents):
    database_api.documents.pop('CachedDocument')
    fixture = setup.isolated_database.__wrapped__()
    next(fixture)
    database_api.documents['CachedDocument'] = cached_documents
    with pytest.raises(ValueError, match='behavior failed'):
        fixture.throw(ValueError('behavior failed'))
    assert cached_documents._collection is None
    assert database_api.events[-1] == ('disconnect',)


def test_collection_cleanup_failure_still_disconnects(database_api, cached_documents,
                                                     monkeypatch):
    fixture = setup.isolated_database.__wrapped__()
    next(fixture)

    def fail_drop():
        raise RuntimeError('collection cleanup failed')

    monkeypatch.setattr(cached_documents, 'drop_collection', fail_drop)
    with pytest.raises(RuntimeError, match='collection cleanup failed'):
        next(fixture)
    assert database_api.events[-1] == ('disconnect',)
