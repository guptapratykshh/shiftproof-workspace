import secrets

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import DepartmentMembership, DeviceSession, Organization, TeamMembership, User
from ..schemas import (
    ActivateInput,
    Input,
    Login,
    PreferenceInput,
    RecoverInput,
    Registration,
    TokenInput,
    password_policy,
)
from ..security import current_user, fail, hash_secret, verify_secret
from ..services import authentication as service
from ..services.common import audit, record_dict

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=202)
def register(values: Registration, request: Request, db: Session = Depends(get_db, scope="function")):
    return service.register(db, values, request)


@router.post("/verify")
def verify(values: TokenInput, db: Session = Depends(get_db, scope="function")):
    return service.verify_registration(db, values.token)


@router.post("/login/{role}")
def login(role: str, values: Login, request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    return service.login(db, role, values, request, response)


@router.post("/activate")
def activate(values: ActivateInput, db: Session = Depends(get_db, scope="function")):
    return service.activate(db, values)


@router.get("/activation")
def activation_info(token: str, db: Session = Depends(get_db, scope="function")):
    from ..models import Invitation
    from ..security import digest
    from ..db import now

    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == digest(token)))
    if not invitation or invitation.used_at or invitation.expires_at <= now():
        fail(400, "This link is invalid or expired.")
    user = db.get(User, invitation.user_id)
    return {
        "role": user.role,
        "name": user.name,
        "kind": invitation.kind,
        "organizationId": db.get(Organization, user.organization_id).code,
    }


@router.post("/recover", status_code=202)
def recover(values: RecoverInput, request: Request, db: Session = Depends(get_db, scope="function")):
    service.throttle(db, f"recover:{request.client.host if request.client else 'unknown'}", 10)
    query = select(User).where(
        User.email == str(values.email).lower(), User.role == values.role, User.active.is_(True)
    )
    if values.role == "supervisor":
        organization = db.scalar(
            select(Organization).where(Organization.code == values.organizationId.upper())
        )
        query = query.where(User.organization_id == (organization.id if organization else ""))
    user = db.scalar(query)
    if user:
        service.issue_invitation(db, user, user, "password_reset")
    return {
        "status": "recovery_requested",
        "delivery": "local_outbox" if get_settings().mail_mode == "file" else "smtp_queued",
    }


@router.get("/me")
def me(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    departments = db.scalars(
        select(DepartmentMembership).where(
            DepartmentMembership.user_id == user.id, DepartmentMembership.active.is_(True)
        )
    ).all()
    teams = db.scalars(
        select(TeamMembership).where(TeamMembership.user_id == user.id, TeamMembership.active.is_(True))
    ).all()
    if not user.offline_key:
        db.execute(
            update(User)
            .where(User.id == user.id, User.offline_key.is_(None))
            .values(offline_key=secrets.token_hex(32))
        )
        db.refresh(user, ["offline_key"])
    from ..security import policy_value

    return {
        "user": record_dict(user),
        "organization": record_dict(db.get(Organization, user.organization_id)),
        "memberships": [record_dict(item) for item in departments],
        "teamMemberships": [record_dict(item) for item in teams],
        "offlineKey": user.offline_key,
        "session": {
            "expiresAt": request.state.session.expires_at,
            "idleMinutes": policy_value(db, user.organization_id, "security").get(
                "idle_minutes", 60 if user.role == "worker" else 120
            ),
        },
    }


@router.post("/logout")
def logout(
    request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    request.state.session.revoked = True
    response.delete_cookie("shiftproof_session", path="/")
    response.delete_cookie("shiftproof_csrf", path="/")
    audit(db, user, user.organization_id, "session.ended", "user", user.id)
    return {"status": "signed_out"}


@router.get("/sessions")
def sessions(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    return [
        {**record_dict(item), "current": item.id == request.state.session.id}
        for item in db.scalars(
            select(DeviceSession).where(DeviceSession.user_id == user.id, DeviceSession.revoked.is_(False))
        )
    ]


@router.delete("/sessions/{session_id}")
def revoke(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    session = db.scalar(
        select(DeviceSession).where(DeviceSession.id == session_id, DeviceSession.user_id == user.id)
    )
    if not session:
        fail(404, "Session not found.")
    session.revoked = True
    return {"status": "revoked"}


@router.put("/preferences")
def preferences(values: PreferenceInput, user: User = Depends(current_user)):
    user.preferences = {**user.preferences, **values.model_dump()}
    return user.preferences


class ChangeSecret(Input):
    current: str
    replacement: str
    confirm: str


@router.put("/password")
def change_secret(
    values: ChangeSecret, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    old_hash = user.pin_hash if user.role == "worker" else user.password_hash
    if not verify_secret(values.current, old_hash):
        fail(400, "Your current password or PIN is incorrect.")
    if values.replacement != values.confirm:
        fail(422, "Confirmation does not match.")
    if user.role == "worker":
        if (
            len(values.replacement) != 6
            or not values.replacement.isascii()
            or not values.replacement.isdigit()
        ):
            fail(422, "Choose a six-digit PIN.")
        user.pin_hash = hash_secret(values.replacement)
    else:
        try:
            password_policy(values.replacement)
        except ValueError as error:
            fail(422, str(error))
        user.password_hash = hash_secret(values.replacement)
    db.execute(
        update(DeviceSession)
        .where(DeviceSession.user_id == user.id, DeviceSession.id != request.state.session.id)
        .values(revoked=True)
    )
    audit(db, user, user.organization_id, "credential.changed", "user", user.id)
    return {"status": "updated"}
