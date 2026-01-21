"""Background tasks handled by Celery workers."""

import asyncio
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import delete

from database import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    get_db_contextmanager,
)
from database.session_postgresql import SyncPostgresqlSessionLocal


@shared_task()
def healthcheck() -> dict[str, str]:
    """Simple heartbeat task used by Celery Beat to verify worker health."""
    now = datetime.now(timezone.utc).isoformat()
    return {"status": "ok", "timestamp": now}


@shared_task()
def cleanup_expired_tokens() -> str:
    now = datetime.now(timezone.utc)

    with SyncPostgresqlSessionLocal() as session:
        session.execute(delete(ActivationTokenModel).where(ActivationTokenModel.expires_at < now))
        session.execute(delete(PasswordResetTokenModel).where(PasswordResetTokenModel.expires_at < now))
        session.execute(delete(RefreshTokenModel).where(RefreshTokenModel.expires_at < now))
        session.commit()

    return "expired tokens cleaned"


__all__ = ["healthcheck", "cleanup_expired_tokens"]
