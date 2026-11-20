import pytest
from notifications.models import Notification
from notifications.services import create_notification


@pytest.mark.django_db
def test_create_notification():
    n = create_notification(
        title="Hello", message="World",
        notification_type="SYSTEM", severity="INFO",
    )
    assert Notification.objects.count() == 1
    assert n.title == "Hello"
    assert n.is_read is False