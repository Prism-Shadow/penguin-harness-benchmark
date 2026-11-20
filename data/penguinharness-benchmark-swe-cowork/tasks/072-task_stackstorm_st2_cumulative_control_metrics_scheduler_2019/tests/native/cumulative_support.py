import copy
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest


@pytest.fixture
def cumulative_database():
    from mongoengine.connection import connect, disconnect
    from conftest import clear_database

    uri = os.environ.get('TASK072_MONGO_URI', 'mongomock://localhost')
    real = uri != 'mongomock://localhost'
    if real:
        parsed = urlparse(uri)
        assert parsed.scheme == 'mongodb' and parsed.hostname == '127.0.0.1'
        assert not parsed.username and not parsed.password and not parsed.query
    disconnect()
    connection = connect('task_quality_072', host=uri, serverSelectionTimeoutMS=3000)
    if real:
        connection.admin.command('ping')
    try:
        clear_database(connection)
        yield SimpleNamespace(real=real, uri=uri)
    finally:
        try:
            clear_database(connection)
        finally:
            disconnect()


@pytest.fixture
def cumulative(monkeypatch, cumulative_database, tmpdir):
    from oslo_config import cfg
    from st2common.models.db.action import ActionDB
    from st2common.models.db.runner import RunnerTypeDB
    from st2common.persistence.action import Action
    from st2common.persistence.runner import RunnerType
    from st2common.services import coordination
    from st2common.transport.publishers import PoolPublisher
    from st2common.util import date

    state = SimpleNamespace(
        clock=[date.add_utc_tz(datetime.datetime(2020, 1, 1))], messages=[],
        database=cumulative_database, scratch=str(tmpdir), restarts=0)

    def capture(publisher, payload, exchange, routing_key=''):
        state.messages.append((exchange.name, routing_key, copy.deepcopy(payload)))

    monkeypatch.setattr(PoolPublisher, 'publish', capture)
    monkeypatch.setattr(date, 'get_datetime_utc_now', lambda: state.clock[0])
    cfg.CONF.set_override('url', 'file://' + str(tmpdir.mkdir('coordination')),
                          group='coordination')
    state.coordination_url = cfg.CONF.coordination.url
    previous = coordination.COORDINATOR
    coordination.COORDINATOR = None
    try:
        coordination.get_coordinator()
        for name, module, params in [
                ('orquesta', 'orquesta_runner', {'notify': {'type': 'array', 'default': []}}),
                ('local-shell-cmd', 'local_runner', {})]:
            RunnerType.add_or_update(RunnerTypeDB(
                name=name, runner_module=module, runner_parameters=params), publish=False)
        for name, runner in [('workflow', 'orquesta'), ('leaf', 'local-shell-cmd')]:
            Action.add_or_update(ActionDB(
                pack='quality072', name=name, entry_point='unused.yaml',
                runner_type={'name': runner}, parameters={}), publish=False)
        yield state
    finally:
        if coordination.COORDINATOR is not None:
            coordination.coordinator_teardown(coordination.COORDINATOR)
        coordination.COORDINATOR = previous
        cfg.CONF.clear_override('url', group='coordination')


def start_workflow(state, items, delay=0, concurrency=2):
    from st2common.models.db.liveaction import LiveActionDB
    from st2common.persistence.workflow import WorkflowExecution
    from st2common.services import action, workflows

    state.messages[:] = []
    state.delivered = 0
    definition = {
        'version': '1.0',
        'tasks': {
            'fanout': {
                'with': {'items': '<% ' + json.dumps(items) + ' %>', 'concurrency': concurrency},
                'action': 'quality072.leaf', 'delay': delay,
                'next': [{'when': '<% succeeded() %>', 'do': 'successor'}]},
            'successor': {'action': 'quality072.leaf'}}}
    notify = {'on-complete': {'message': 'task finished', 'routes': ['quality072.notify']}}
    root_live, root_execution = action.request(LiveActionDB(
        action='quality072.workflow', parameters={'notify': ['fanout', 'successor']},
        context={'user': 'alice', 'api_user': 'delegate'}))
    workflow = workflows.request(
        definition, root_execution,
        {'st2': {'user': 'alice', 'api_user': 'delegate', 'pack': 'quality072'}},
        notify_cfg=notify)
    workflow = WorkflowExecution.get_by_id(str(workflow.id))
    assert workflow.notify == {'config': notify, 'tasks': ['fanout', 'successor']}
    assert workflow.context['st2']['workflow_execution_id'] == str(workflow.id)
    assert workflow.state['contexts'][0]['st2']['workflow_execution_id'] == str(workflow.id)
    workflows.request_next_tasks(workflow)
    state.workflow = workflow
    state.root_execution = root_execution
    return workflow


def children(state, task_id=None):
    from st2common.persistence.liveaction import LiveAction

    values = list(LiveAction.query(workflow_execution=str(state.workflow.id)))
    if task_id is not None:
        values = [value for value in values if value.context['orquesta']['task_id'] == task_id]
    return sorted(values, key=lambda value: value.context['orquesta'].get('item_id', -1))


def deliver_requests(state):
    from st2actions.scheduler.entrypoint import SchedulerEntrypoint
    from st2common.models.db.liveaction import LiveActionDB
    from st2common.persistence.execution_queue import ActionExecutionSchedulingQueue

    entrypoint = SchedulerEntrypoint(None, [])
    pending = list(state.messages[state.delivered:])
    state.delivered = len(state.messages)
    for exchange, status, payload in pending:
        if (exchange == 'st2.liveaction.status' and status == 'requested'
                and isinstance(payload, LiveActionDB) and payload.workflow_execution):
            entrypoint.process(payload)
    expected = {str(value.id) for value in children(state) if value.status in ('requested', 'delayed')}
    actual = {value.liveaction_id for value in ActionExecutionSchedulingQueue.query()}
    assert actual == expected


def scheduled(state):
    return [payload for exchange, status, payload in state.messages
            if exchange == 'st2.liveaction.status' and status == 'scheduled']


def poll(monkeypatch, max_ticks=None):
    import eventlet
    from st2actions.scheduler import config
    from st2actions.scheduler.handler import ActionExecutionSchedulingQueueHandler
    from st2common.persistence.execution_queue import ActionExecutionSchedulingQueue

    if max_ticks is None:
        max_ticks = ActionExecutionSchedulingQueue.count() + 1
    driver = ActionExecutionSchedulingQueueHandler()
    original_sleep = eventlet.greenthread.sleep
    original_spawn = eventlet.GreenPool.spawn
    ticks = []
    workers = []
    scheduler_thread = None

    def tick(interval=0):
        if eventlet.getcurrent() is scheduler_thread:
            ticks.append(interval)
            if len(ticks) == max_ticks:
                driver.shutdown()
            return original_sleep(0)
        return original_sleep(interval)

    def observe_spawn(pool, callback, *args, **kwargs):
        worker = original_spawn(pool, callback, *args, **kwargs)
        workers.append(worker)
        return worker

    with monkeypatch.context() as clock_patch:
        clock_patch.setattr(eventlet.greenthread, 'sleep', tick)
        clock_patch.setattr(eventlet.GreenPool, 'spawn', observe_spawn)
        with eventlet.Timeout(10):
            scheduler_thread = eventlet.spawn(driver.run)
            try:
                scheduler_thread.wait()
                for worker in workers:
                    worker.wait()
            finally:
                driver.shutdown()
    assert len(ticks) == max_ticks, (ticks, max_ticks)


def complete(liveaction, result):
    from st2common.persistence.execution import ActionExecution
    from st2common.services import action

    action.update_status(liveaction, 'succeeded', result=result)
    return ActionExecution.query(liveaction__id=str(liveaction.id)).first()


def restarted_poll(state):
    state.restarts += 1
    output = Path(state.scratch) / ('restart-' + str(state.restarts) + '.json')
    command = [sys.executable, str(Path(__file__).resolve()), state.database.uri,
               state.coordination_url, state.clock[0].strftime('%Y-%m-%dT%H:%M:%S.%f'), str(output)]
    subprocess.check_call(command, timeout=30)
    return json.loads(output.read_text())


def restart_main():
    from mongoengine.connection import connect, disconnect
    from oslo_config import cfg
    from st2common import config
    from st2common.services import coordination
    from st2common.transport.publishers import PoolPublisher
    from st2common.util import date

    uri, lock_url, instant, output = sys.argv[1:]
    assert urlparse(uri).hostname == '127.0.0.1'
    config.register_opts()
    cfg.CONF.set_override('url', lock_url, group='coordination')
    connection = connect('task_quality_072', host=uri, serverSelectionTimeoutMS=3000)
    connection.admin.command('ping')
    clock = date.add_utc_tz(datetime.datetime.strptime(instant, '%Y-%m-%dT%H:%M:%S.%f'))
    captured = []

    def capture(publisher, payload, exchange, routing_key=''):
        if exchange.name == 'st2.liveaction.status' and routing_key == 'scheduled':
            captured.append(str(payload.id))

    try:
        with pytest.MonkeyPatch.context() as boundary:
            boundary.setattr(PoolPublisher, 'publish', capture)
            boundary.setattr(date, 'get_datetime_utc_now', lambda: clock)
            poll(boundary)
        Path(output).write_text(json.dumps(captured) + '\n')
    finally:
        if coordination.COORDINATOR is not None:
            coordination.coordinator_teardown(coordination.COORDINATOR)
        disconnect()


if __name__ == '__main__':
    restart_main()
