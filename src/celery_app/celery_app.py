"""Celery application configuration and beat schedule."""

from celery import Celery
from celery.schedules import crontab

from config import get_settings
from celery_app import default_app_name

settings = get_settings()

celery = Celery(
    default_app_name,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["celery_app.tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.CELERY_TIMEZONE,
)

celery.conf.beat_schedule = {
    "healthcheck-every-5-minutes": {
        "task": "celery_app.tasks.healthcheck",
        "schedule": crontab(minute="*/5"),
    },
    "cleanup-expired-tokens-hourly": {
        "task": "celery_app.tasks.cleanup_expired_tokens",
        "schedule": crontab(minute=0, hour="*"),
    },
}

__all__ = ["celery"]
