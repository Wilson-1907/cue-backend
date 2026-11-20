from .models import Notification


def create_notification(
    title,
    message,
    notification_type,
    severity="INFO",
    *,
    audience=Notification.Audience.INTERNAL,
    is_pinned=False,
    user=None,
):
    notif = Notification.objects.create(
        title=title,
        message=message,
        notification_type=notification_type,
        severity=severity,
        audience=audience or Notification.Audience.INTERNAL,
        is_pinned=bool(is_pinned),
        created_by=user,
    )
    try:
        from config.broadcast import broadcast_notification

        broadcast_notification(notif)
    except Exception:
        pass
    return notif
