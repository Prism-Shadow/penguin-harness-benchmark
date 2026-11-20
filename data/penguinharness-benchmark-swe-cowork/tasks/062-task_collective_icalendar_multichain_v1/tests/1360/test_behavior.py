from datetime import datetime, timedelta
import inspect
import time

import pytest


def test_1360():
    from icalendar.prop import vWeekday
    assert vWeekday("-1MO").ical_value == "-1MO"
