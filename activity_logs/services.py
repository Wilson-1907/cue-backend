from .models import ActivityLog

def log_action(user=None, device=None, action="", description="",
               category="SYSTEM", ip_address=None):
    return ActivityLog.objects.create(
        user=user, device=device, action=action, description=description,
        category=category, ip_address=ip_address,
    )