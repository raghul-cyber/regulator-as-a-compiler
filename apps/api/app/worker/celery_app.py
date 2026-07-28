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
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
)

from celery.signals import worker_init, before_task_publish, task_prerun
from app.core.logging_config import setup_logging_and_sentry, request_id_var

@worker_init.connect
def on_worker_init(**kwargs):
    setup_logging_and_sentry()

@before_task_publish.connect
def on_before_task_publish(headers=None, **kwargs):
    headers = headers or {}
    req_id = request_id_var.get()
    if req_id != "-":
        headers["x-request-id"] = req_id

@task_prerun.connect
def on_task_prerun(task_id, task, *args, **kwargs):
    import logging
    logging.info(f"Task request context: {task.request}")
    headers = getattr(task.request, 'headers', None) or task.request.get('headers') or {}
    req_id = headers.get("x-request-id")
    if req_id:
        request_id_var.set(req_id)


