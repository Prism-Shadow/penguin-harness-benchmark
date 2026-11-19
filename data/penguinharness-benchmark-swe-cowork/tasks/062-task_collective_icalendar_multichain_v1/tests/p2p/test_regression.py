from icalendar import Calendar, Event, vCalAddress, vText
from icalendar.caselessdict import CaselessDict


def test_minimal_calendar_parse():
    calendar = Calendar.from_ical(
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Regression//EN\r\nEND:VCALENDAR\r\n"
    )
    assert calendar.name == "VCALENDAR"


def test_event_summary_caseless_lookup():
    event = Event()
    event.add("summary", "Release review")
    assert str(event["SUMMARY"]) == "Release review"
    assert str(event["summary"]) == "Release review"


def test_caseless_dict_access():
    values = CaselessDict()
    values["content-type"] = "text/calendar"
    assert values["CONTENT-TYPE"] == "text/calendar"
    assert "Content-Type" in values


def test_cal_address_round_trip():
    address = vCalAddress("MAILTO:calendar@example.test")
    assert vCalAddress.from_ical(address.to_ical()) == address


def test_text_round_trip():
    text = vText("Release review")
    assert vText.from_ical(text.to_ical()) == text

