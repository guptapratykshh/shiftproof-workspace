from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import Organization, User
from ..security import current_user, fail
from ..services.analytics import aggregate

router = APIRouter(tags=["Analytics"])


@router.get("/analytics")
def analytics(
    start: date | None = None,
    end: date | None = None,
    department_id: str | None = None,
    team_id: str | None = None,
    shift_id: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    status: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    if user.role == "worker":
        fail(403, "Operational analytics are for authorized supervisors and administrators.")
    zone = ZoneInfo(db.get(Organization, user.organization_id).timezone)
    today = now().astimezone(zone).date()
    start, end = start or today - timedelta(days=29), end or today
    if end < start or (end - start).days > 365:
        fail(422, "Choose an ordered date range of at most 366 days.")
    beginning, ending = datetime.combine(start, time.min, zone), datetime.combine(end, time.max, zone)
    filters = {
        "department_id": department_id,
        "team_id": team_id,
        "shift_id": shift_id,
        "priority": priority,
        "category": category,
        "status": status,
    }
    data = aggregate(db, user, beginning, ending, filters)
    duration = timedelta(days=(end - start).days + 1)
    previous = aggregate(db, user, beginning - duration, ending - duration, filters)
    return {
        **data,
        "previous_metrics": previous["metrics"],
        "period": {"start": start, "end": end, "timezone": str(zone)},
        "previous_period": {"start": start - duration, "end": end - duration},
    }
