from datetime import datetime, timedelta
import inspect
import time

import pytest


def test_1359():
    from icalendar.prop import vPeriod
    value = (datetime(2000, 1, 1), timedelta(days=2))
    assert vPeriod(value).ical_value == value
