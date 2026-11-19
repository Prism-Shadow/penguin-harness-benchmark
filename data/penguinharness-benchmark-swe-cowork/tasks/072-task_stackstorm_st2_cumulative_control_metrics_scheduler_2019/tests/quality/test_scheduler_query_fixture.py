import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'scheduler_support', ROOT / 'tests/native/scheduler_support.py')
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)


def test_query_deadline_is_optional_and_inclusive():
    now = datetime.datetime(2020, 1, 1)
    due = SimpleNamespace(handling=False, scheduled_start_timestamp=now)
    future = SimpleNamespace(handling=False, scheduled_start_timestamp=now + datetime.timedelta(seconds=1))
    claimed = SimpleNamespace(handling=True, scheduled_start_timestamp=now)
    rows = [future, due, claimed]
    assert SUPPORT.query_rows(rows, handling=False, scheduled_start_timestamp__lte=now) == [due]
    assert SUPPORT.query_rows(rows, handling=False) == [due, future]
    assert SUPPORT.query_rows(rows, handling=False, limit=1) == [due]
    assert SUPPORT.query_rows(rows, scheduled_start_timestamp__lte=now) == [due, claimed]
    assert SUPPORT.query_rows(rows) == [due, claimed, future]
    assert SUPPORT.query_rows(rows, handling=False)[0] is not due
    assert rows == [future, due, claimed]
