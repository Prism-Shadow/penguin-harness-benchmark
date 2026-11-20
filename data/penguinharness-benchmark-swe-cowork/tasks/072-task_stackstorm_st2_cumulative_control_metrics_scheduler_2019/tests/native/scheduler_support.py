import copy
import datetime
from types import SimpleNamespace

import pytest


def query_rows(rows, **filters):
    selected = [copy.deepcopy(value) for value in rows
                if ('handling' not in filters or value.handling == filters['handling']) and
                ('scheduled_start_timestamp__lte' not in filters or
                 value.scheduled_start_timestamp <= filters['scheduled_start_timestamp__lte'])]
    selected.sort(key=lambda value: value.scheduled_start_timestamp)
    return selected[:filters.get('limit', len(selected))]


@pytest.fixture
def scheduler(monkeypatch):
    import eventlet
    from st2actions.scheduler import config
    from st2actions.scheduler import handler as scheduler_handler
    from st2common.constants import action as action_constants
    from st2common.exceptions import db as db_exceptions
    from st2common.persistence.execution_queue import ActionExecutionSchedulingQueue
    from st2common.persistence.liveaction import LiveAction
    from st2common.services import action, policies
    from st2common.util import action_db, date

    clock = [date.add_utc_tz(datetime.datetime(2020, 1, 1))]
    row = SimpleNamespace(id='queue-1', liveaction_id='live-1', handling=False,
                          scheduled_start_timestamp=clock[0], rev=0)
    state = SimpleNamespace(rows={row.id: row}, clock=clock, published=[],
                            conflicts=0, delay=True, constants=action_constants)
    state.liveaction = SimpleNamespace(id='live-1', status=action_constants.LIVEACTION_STATUS_REQUESTED)

    class Results(list):
        def first(self):
            return self[0] if self else None

    def query(**filters):
        return Results(query_rows(state.rows.values(), **filters))

    def save(value, publish=False):
        current = state.rows[value.id]
        if state.conflicts or value.rev != current.rev:
            state.conflicts = max(0, state.conflicts - 1)
            raise db_exceptions.StackStormDBObjectWriteConflictError(value)
        value.rev += 1
        state.rows[value.id] = copy.deepcopy(value)
        return value

    def update_status(value, status, publish=False):
        state.liveaction.status = status
        return copy.deepcopy(state.liveaction)

    def apply_policy(value):
        if state.delay:
            value.status = action_constants.LIVEACTION_STATUS_POLICY_DELAYED
        return value

    monkeypatch.setattr(ActionExecutionSchedulingQueue, 'query', query)
    monkeypatch.setattr(ActionExecutionSchedulingQueue, 'add_or_update', save)
    monkeypatch.setattr(ActionExecutionSchedulingQueue, 'delete', lambda value: state.rows.pop(value.id))
    monkeypatch.setattr(LiveAction, 'publish_status', lambda value: state.published.append(copy.deepcopy(value)))
    monkeypatch.setattr(action_db, 'get_liveaction_by_id', lambda value: copy.deepcopy(state.liveaction))
    monkeypatch.setattr(action, 'update_status', update_status)
    monkeypatch.setattr(policies, 'apply_pre_run_policies', apply_policy)
    monkeypatch.setattr(date, 'get_datetime_utc_now', lambda: clock[0])
    monkeypatch.setattr(eventlet, 'GreenPool',
                        lambda size: SimpleNamespace(spawn=lambda callback, *args: callback(*args)))

    def poll():
        handler = scheduler_handler.ActionExecutionSchedulingQueueHandler()
        monkeypatch.setattr(eventlet.greenthread, 'sleep', lambda interval: handler.shutdown())
        handler.run()

    state.poll = poll
    return state
