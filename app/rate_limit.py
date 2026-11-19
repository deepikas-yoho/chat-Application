from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models import RateLimitEvent


def enforce_rate_limit(db: Session, key_fingerprint: str) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=settings.rate_limit_window_seconds)

    count = db.scalar(
        select(func.count(RateLimitEvent.id)).where(
            RateLimitEvent.api_key_fingerprint == key_fingerprint,
            RateLimitEvent.created_at >= cutoff,
        )
    ) or 0

    if count >= settings.rate_limit_messages:
        oldest = db.scalar(
            select(func.min(RateLimitEvent.created_at)).where(
                RateLimitEvent.api_key_fingerprint == key_fingerprint,
                RateLimitEvent.created_at >= cutoff,
            )
        )
        retry_after = max(
            1, int((oldest + timedelta(seconds=settings.rate_limit_window_seconds) - now).total_seconds())
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    db.add(RateLimitEvent(api_key_fingerprint=key_fingerprint, created_at=now))
    db.commit()
