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


@shared_task()
def healthcheck() -> dict[str, str]:
    """Simple heartbeat task used by Celery Beat to verify worker health."""
    now = datetime.now(timezone.utc).isoformat()
    return {"status": "ok", "timestamp": now}


async def _cleanup_expired_tokens() -> None:
    """Remove expired activation, reset, and refresh tokens from the database."""

    async with get_db_contextmanager() as session:
        now = datetime.now(timezone.utc)
        await session.execute(delete(ActivationTokenModel).where(ActivationTokenModel.expires_at < now))

        await session.commit()


@shared_task()
def cleanup_expired_tokens() -> str:
    """Celery wrapper that runs the expired token cleanup asynchronously."""

    asyncio.run(_cleanup_expired_tokens())
    return "expired tokens cleaned"


__all__ = ["healthcheck", "cleanup_expired_tokens"]
