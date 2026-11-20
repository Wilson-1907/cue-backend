# monitoring/tasks.py
from celery import shared_task
from monitoring.models import Pipeline

@shared_task
def evaluate_all_pipelines():
    from leak_detection.services import evaluate_pipeline
    for p in Pipeline.objects.all():
        evaluate_pipeline(p)