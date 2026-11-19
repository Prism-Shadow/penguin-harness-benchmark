from datetime import datetime, timedelta
import inspect
import time

import pytest


def test_1434():
    from icalendar import Component
    jcal = ["vcalendar", [], [["vevent", [["rdate", {}, "period", ["2000-01-01T00:00:00", "2000-01-02T00:00:00"]]], []]]]
    result = Component.from_jcal(jcal)
    event = result.walk("VEVENT")[0]
    assert event["RDATE"].params["VALUE"] == "PERIOD"
