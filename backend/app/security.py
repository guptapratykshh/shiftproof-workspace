import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db, now
from .models import Department, DepartmentMembership, DeviceSession, OrganizationPolicy, Takeover, User

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("nonexistent-account-comparison-732")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(value: str) -> str:
    return hasher.hash(value)


def verify_secret(value: str, encoded: str | None) -> bool:
    try:
        valid = hasher.verify(encoded or DUMMY_HASH, value)
        return bool(encoded) and valid
    except (VerificationError, InvalidHashError):
        return False


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get("shiftproof_session", "")
    session = db.scalar(select(DeviceSession).where(DeviceSession.token_hash == digest(raw))) if raw else None
    if not session or session.revoked or session.expires_at <= now():
        fail(401, "Your session has ended. Please sign in again.")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        fail(401, "This account is not active.")
    expected_account = request.headers.get("X-Account-ID")
    if expected_account and expected_account != user.id:
        fail(
            401,
            "The signed-in account changed on this shared device. Sign in as the original reporter to continue.",
        )
    policy = policy_value(db, user.organization_id, "security")
    idle_minutes = int(policy.get("idle_minutes", 60 if user.role == "worker" else 120))
    if session.last_seen + timedelta(minutes=idle_minutes) <= now():
        fail(401, "Your session expired after inactivity. Please sign in again.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(digest(csrf), session.csrf_hash):
            fail(403, "The request could not be verified. Refresh the page and try again.")
    # Passive polling and SSE must not keep an unattended shared device signed in.
    activity = request.headers.get("X-User-Activity")
    passive = request.url.path.endswith(("/events", "/notifications", "/workspace/context", "/auth/me"))
    if activity == "1" or (activity is None and not passive):
        session.last_seen = now()
    request.state.session = session
    return user


def admin(user: User):
    if user.role != "organization":
        fail(403, "Organization administrator access is required.")


def scoped(db: Session, model, record_id: str, user: User):
    record = db.scalar(
        select(model).where(model.id == record_id, model.organization_id == user.organization_id)
    )
    if record is None:
        fail(404, "This record is unavailable.")
    return record


def policy_value(db: Session, organization_id: str, key: str) -> dict:
    policy = db.scalar(
        select(OrganizationPolicy).where(
            OrganizationPolicy.organization_id == organization_id, OrganizationPolicy.key == key
        )
    )
    return policy.value if policy else {}


def department_ids(db: Session, user: User, permission: str = "view") -> list[str]:
    if user.role == "organization" and permission == "view":
        return list(
            db.scalars(select(Department.id).where(Department.organization_id == user.organization_id))
        )
    if user.role == "organization":
        return list(
            db.scalars(
                select(Takeover.department_id).where(
                    Takeover.user_id == user.id,
                    Takeover.organization_id == user.organization_id,
                    Takeover.revoked_at.is_(None),
                    Takeover.expires_at > now(),
                )
            )
        )
    memberships = db.scalars(
        select(DepartmentMembership).where(
            DepartmentMembership.user_id == user.id,
            DepartmentMembership.organization_id == user.organization_id,
            DepartmentMembership.active.is_(True),
        )
    ).all()
    return [
        membership.department_id
        for membership in memberships
        if permission == "view" or (user.role == "supervisor" and permission in membership.permissions)
    ]


def require_department(
    db: Session, user: User, department_id: str, permission: str = "view", active: bool = False
):
    department = scoped(db, Department, department_id, user)
    if department_id not in department_ids(db, user, permission):
        fail(403, "You do not have permission for this department and action.")
    if active and not department.active:
        fail(409, "This department is inactive.")
    return department
