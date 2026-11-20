from datetime import datetime, timedelta
import inspect
import time

import pytest


def test_1349():
    from icalendar import vBinary
    with pytest.raises(ValueError, match="Not valid base 64"):
        vBinary.from_ical("!!!!dGV4dA==@@@@")
