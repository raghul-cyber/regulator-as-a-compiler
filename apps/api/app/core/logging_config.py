import logging
import sys
import json
from contextvars import ContextVar
from typing import Any, Dict
from app.core.config import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

try:
    from pythonjsonlogger import jsonlogger
    class CustomJSONFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
            super().add_fields(log_record, record, message_dict)
            log_record["level"] = record.levelname
            log_record["logger"] = record.name
            log_record["request_id"] = request_id_var.get()
            log_record["timestamp"] = self.formatTime(record, self.datefmt)
except ImportError:
    class CustomJSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "request_id": request_id_var.get(),
            }
            if record.exc_info:
                log_obj["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_obj)

def setup_logging_and_sentry():
    # 1. Setup Sentry
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.celery import CeleryIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENVIRONMENT,
                traces_sample_rate=1.0,
                integrations=[
                    FastApiIntegration(),
                    CeleryIntegration(),
                    SqlalchemyIntegration(),
                ],
            )
            logging.info("Sentry initialized successfully.")
        except Exception as e:
            logging.warning(f"Failed to initialize Sentry: {e}")

    # 2. Configure JSON Logging
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJSONFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    
    # Silence chatty third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
