import pytest


@pytest.fixture(scope='session', autouse=True)
def configured_runtime():
    from st2common import config

    config.register_opts()


def clear_database(connection):
    from mongoengine import Document
    from mongoengine.base.common import _document_registry

    for document in list(_document_registry.values()):
        if (issubclass(document, Document)
                and not document._meta.get('abstract')
                and document._meta.get('db_alias', 'default') == 'default'):
            document.drop_collection()
    connection.drop_database('task_quality_072')


@pytest.fixture
def isolated_database():
    from mongoengine.connection import connect, disconnect

    disconnect()
    connection = connect('task_quality_072', host='mongomock://localhost')
    try:
        clear_database(connection)
        yield connection
    finally:
        try:
            clear_database(connection)
        finally:
            disconnect()
