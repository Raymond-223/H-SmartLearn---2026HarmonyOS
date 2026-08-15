"""Time helpers shared by persistence models.

SQLAlchemy columns are currently timezone-naive for SQLite/PostgreSQL portability,
so UTC is normalized and the timezone marker is removed at the boundary.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
