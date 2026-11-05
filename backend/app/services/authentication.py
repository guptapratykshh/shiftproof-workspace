from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy import case, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import now
from ..models import AuthThrottle, DeviceSession, Invitation, Organization, PendingRegistration, User
from ..schemas import ActivateInput, Login, Registration
from ..security import digest, fail, hash_secret, token, verify_secret
from .common import audit, enqueue


def throttle(db: Session, key: str, limit: int = 8):
    """Persist failed-attempt budgets even when the surrounding request is rejected."""
    hashed = digest(key)
    if db.bind.dialect.name == "mongodb":
        if db.throttle(hashed, limit) is None:
            fail(429, "Too many attempts. Please wait 15 minutes before trying again.")
        return
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    timestamp = now()
    expired = AuthThrottle.reset_at <= timestamp
    statement = (
        insert(AuthThrottle)
        .values(key=hashed, attempts=1, reset_at=timestamp + timedelta(minutes=15))
        .on_conflict_do_update(
            index_elements=[AuthThrottle.key],
            set_={
                "attempts": case((expired, 1), else_=AuthThrottle.attempts + 1),
                "reset_at": case((expired, timestamp + timedelta(minutes=15)), else_=AuthThrottle.reset_at),
            },
            where=expired | (AuthThrottle.attempts < limit),
        )
        .returning(AuthThrottle.attempts)
    )
    attempts = db.scalar(statement)
    db.commit()
    if attempts is None:
        fail(429, "Too many attempts. Please wait 15 minutes before trying again.")


def register(db: Session, values: Registration, request: Request):
    email = str(values.email).lower()
    throttle(db, f"register:{request.client.host if request.client else 'unknown'}", 20)
    if db.scalar(select(User.id).where(User.email == email, User.role == "organization")):
        fail(409, "An account already uses these details. Sign in or recover your account.")
    registration = db.scalar(select(PendingRegistration).where(PendingRegistration.email == email))
    if registration and registration.verified_at:
        fail(409, "An account already uses these details.")
    raw = token()
    fields = dict(
        name=values.fullName,
        organization_name=values.organizationName,
        industry=values.organizationType,
        phone=values.phone,
        password_hash=hash_secret(values.password),
        token_hash=digest(raw),
        expires_at=now() + timedelta(hours=24),
    )
    if registration:
        for key, value in fields.items():
            setattr(registration, key, value)
    else:
        registration = PendingRegistration(email=email, **fields)
        db.add(registration)
    db.flush()
    url = f"{get_settings().frontend_url}/verify-email?token={raw}"
    enqueue(
        db,
        "email",
        f"registration:{registration.id}:{digest(raw)[:12]}",
        {
            "to": email,
            "subject": "Verify your ShiftProof organization email",
            "text": f"Verify your email to create your organization's workspace:\n\n{url}\n\nThis link expires in 24 hours. Ignore this email if you did not request an account.",
        },
    )
    return {
        "status": "verification_required",
        "delivery": "local_outbox" if get_settings().mail_mode == "file" else "smtp_queued",
    }


def verify_registration(db: Session, raw: str):
    registration = db.scalar(select(PendingRegistration).where(PendingRegistration.token_hash == digest(raw)))
    if not registration or registration.verified_at or registration.expires_at <= now():
        fail(400, "This verification link is invalid or has expired.")
    consumed = db.execute(
        update(PendingRegistration)
        .where(PendingRegistration.id == registration.id, PendingRegistration.verified_at.is_(None))
        .values(verified_at=now())
    )
    if consumed.rowcount != 1:
        fail(409, "This verification link has already been used.")
    organization = Organization(
        code="ORG-" + token()[:10].upper().replace("_", "X").replace("-", "Y"),
        name=registration.organization_name,
        industry=registration.industry,
        contact=registration.phone,
        settings={"contact_email": registration.email},
    )
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        role="organization",
        name=registration.name,
        email=registration.email,
        phone=registration.phone,
        password_hash=registration.password_hash,
        active=True,
        verified=True,
    )
    db.add(user)
    db.flush()
    audit(db, user, organization.id, "organization.registered", "organization", organization.id)
    return {"status": "verified", "organizationId": organization.code}


def start_session(db: Session, user: User, request: Request, response: Response):
    settings = get_settings()
    previous = request.cookies.get("shiftproof_session")
    if previous:
        db.execute(
            update(DeviceSession).where(DeviceSession.token_hash == digest(previous)).values(revoked=True)
        )
    raw, csrf = token(), token()
    hours = settings.worker_session_hours if user.role == "worker" else settings.session_hours
    session = DeviceSession(
        organization_id=user.organization_id,
        user_id=user.id,
        token_hash=digest(raw),
        csrf_hash=digest(csrf),
        expires_at=now() + timedelta(hours=hours),
        last_seen=now(),
        device=request.headers.get("user-agent", "")[:200],
    )
    db.add(session)
    response.set_cookie(
        "shiftproof_session",
        raw,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=hours * 3600,
        path="/",
    )
    response.set_cookie(
        "shiftproof_csrf",
        csrf,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=hours * 3600,
        path="/",
    )
    organization = db.get(Organization, user.organization_id)
    redirect = (
        "/workspace/onboarding" if user.role == "organization" and not organization.active else "/workspace"
    )
    audit(db, user, user.organization_id, "session.started", "user", user.id)
    return {"status": "authenticated", "redirectPath": redirect}


def login(db: Session, role: str, values: Login, request: Request, response: Response):
    if role not in {"organization", "supervisor", "worker"}:
        fail(404, "Unknown sign-in option.")
    identity = values.employeeId if role == "worker" else values.email.lower()
    ip = request.client.host if request.client else "unknown"
    throttle(db, f"ip-login:{ip}", 60)
    account_bucket = f"login:{role}:{values.organizationId.upper()}:{identity.casefold()}"
    throttle(db, account_bucket)
    query = select(User).where(User.role == role)
    if role == "organization":
        query = query.where(User.email == values.email.lower())
    else:
        organization = db.scalar(
            select(Organization).where(Organization.code == values.organizationId.strip().upper())
        )
        query = query.where(User.organization_id == (organization.id if organization else ""))
        query = (
            query.where(User.employee_code == values.employeeId)
            if role == "worker"
            else query.where(User.email == values.email.lower())
        )
    user = db.scalar(query)
    encoded = (user.pin_hash if role == "worker" else user.password_hash) if user else None
    valid = verify_secret(values.pin if role == "worker" else values.password, encoded)
    if not user or not valid or not user.active or not user.verified:
        fail(401, "We couldn’t sign you in with those details. Check them and try again.")
    db.execute(update(AuthThrottle).where(AuthThrottle.key == digest(account_bucket)).values(attempts=0))
    return start_session(db, user, request, response)


def activate(db: Session, values: ActivateInput):
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == digest(values.token)))
    if not invitation or invitation.used_at or invitation.expires_at <= now():
        fail(400, "This activation or recovery link is invalid or expired.")
    user = db.get(User, invitation.user_id)
    if user.role == "worker" and values.pin is None:
        fail(422, "Choose a six-digit PIN for this worker account.")
    if user.role != "worker" and values.password is None:
        fail(422, "Choose a password for this account.")
    consumed = db.execute(
        update(Invitation)
        .where(Invitation.id == invitation.id, Invitation.used_at.is_(None))
        .values(used_at=now())
    )
    if consumed.rowcount != 1:
        fail(409, "This link has already been used.")
    if user.role == "worker":
        user.pin_hash = hash_secret(values.pin)
    else:
        user.password_hash = hash_secret(values.password)
    # Reset links do not reactivate accounts that administrators have deactivated.
    if invitation.kind in {"invitation", "worker_activation"}:
        user.active = True
        user.verified = True
    db.execute(update(DeviceSession).where(DeviceSession.user_id == user.id).values(revoked=True))
    audit(db, user, user.organization_id, f"account.{invitation.kind}.completed", "user", user.id)
    return {
        "status": "activated",
        "role": user.role,
        "organizationId": db.get(Organization, user.organization_id).code,
    }


def issue_invitation(db: Session, actor: User, user: User, kind: str = "invitation") -> str:
    raw = token()
    # Invalidate previous outstanding links for the same purpose.
    db.execute(
        update(Invitation)
        .where(Invitation.user_id == user.id, Invitation.kind == kind, Invitation.used_at.is_(None))
        .values(used_at=now())
    )
    invitation = Invitation(
        organization_id=user.organization_id,
        user_id=user.id,
        invited_by=actor.id,
        kind=kind,
        token_hash=digest(raw),
        expires_at=now() + timedelta(hours=24 if "reset" in kind else 72),
    )
    db.add(invitation)
    db.flush()
    url = f"{get_settings().frontend_url}/activate?token={raw}"
    if user.email:
        enqueue(
            db,
            "email",
            f"invitation:{invitation.id}",
            {
                "to": user.email,
                "subject": "Your ShiftProof account",
                "text": f"Set up or recover your ShiftProof account using this private link:\n\n{url}\n\nOrganization ID: {db.get(Organization, user.organization_id).code}\nIf you did not request access, contact your organization administrator.",
            },
            user.organization_id,
            actor.id,
        )
    return url
