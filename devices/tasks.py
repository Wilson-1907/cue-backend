# devices/tasks.py
from celery import shared_task
from devices.services import sweep_disconnected_devices

@shared_task
def heartbeat_sweep():
    return sweep_disconnected_devices()

