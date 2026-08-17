from webinar import ics_export
from webinar.models import Webinar


def test_missing_end_time_gets_valid_one_hour_duration():
    webinar = Webinar(
        source="talkit",
        title="테스트 웨비나",
        url="https://example.com/event",
        start_kst="2026-08-20T14:00:00+09:00",
    )
    lines = ics_export._event_lines(webinar, "20260817T000000Z")
    assert "DTSTART:20260820T050000Z" in lines
    assert "DTEND:20260820T060000Z" in lines
