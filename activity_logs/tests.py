import pytest
from activity_logs.services import log_action
from activity_logs.models import ActivityLog


@pytest.mark.django_db
def test_log_action_creates_row():
    log_action(action="TEST_ACTION", description="hello", category="SYSTEM")
    assert ActivityLog.objects.count() == 1
    assert ActivityLog.objects.first().action == "TEST_ACTION"