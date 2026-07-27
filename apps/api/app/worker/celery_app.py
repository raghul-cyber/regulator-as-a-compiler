import os
from celery import Celery
from kombu import Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "rac_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker.tasks"]
)

celery_app.conf.task_queues = (
    Queue("ingestion", routing_key="ingestion"),
    Queue("compliance", routing_key="compliance"),
    Queue("reports", routing_key="reports"),
    Queue("notifications", routing_key="notifications"),
)

celery_app.conf.task_routes = {
    "app.worker.tasks.task_run_ingestion": {"queue": "ingestion", "routing_key": "ingestion"},
    "app.worker.tasks.task_check_compliance": {"queue": "compliance", "routing_key": "compliance"},
    "app.worker.tasks.task_generate_report": {"queue": "reports", "routing_key": "reports"},
    "app.worker.tasks.task_dispatch_notification": {"queue": "notifications", "routing_key": "notifications"},
}

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour max
)

from celery.signals import worker_init
from app.core.logging_config import setup_logging_and_sentry

@worker_init.connect
def on_worker_init(**kwargs):
    setup_logging_and_sentry()

