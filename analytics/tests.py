import pytest
from datetime import date, timedelta
from analytics.services import analytics_summary


@pytest.mark.django_db
def test_analytics_summary_empty():
    end = date.today()
    start = end - timedelta(days=7)
    result = analytics_summary(start, end)
    assert result["total_consumption"] == 0
    assert result["leak_events"] == 0
    assert result["period"]["start"] == start