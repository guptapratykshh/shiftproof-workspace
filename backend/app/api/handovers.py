from datetime import date

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import (
    Handover,
    HandoverItem,
    HandoverItemAcknowledgement,
    HandoverRecipient,
    HandoverVersion,
    Shift,
    User,
)
from ..schemas import Input
from ..security import current_user, fail, require_department, scoped
from ..services import handovers as service
from ..services.common import audit, record_dict

router = APIRouter(tags=["Handovers"])


@router.get("/handovers")
def handovers(user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    return [
        record_dict(item, {"draft"})
        for item in db.scalars(
            service.handover_query(db, user)
            .order_by(Handover.shift_date.desc(), Handover.created_at.desc())
            .limit(200)
        )
    ]


class Draft(Input):
    department_id: str
    shift_id: str
    incoming_shift_id: str | None = None
    shift_date: date
    notes: str = Field(default="", max_length=10000)


@router.post("/handovers", status_code=201)
def draft(values: Draft, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    require_department(db, user, values.department_id, "publish")
    for shift_id in [values.shift_id, values.incoming_shift_id]:
        if shift_id:
            scoped(db, Shift, shift_id, user)
    item = db.scalar(
        select(Handover).where(
            Handover.department_id == values.department_id,
            Handover.shift_id == values.shift_id,
            Handover.shift_date == values.shift_date.isoformat(),
        )
    )
    if item:
        return record_dict(item)
    item = Handover(
        organization_id=user.organization_id,
        department_id=values.department_id,
        shift_id=values.shift_id,
        incoming_shift_id=values.incoming_shift_id,
        shift_date=values.shift_date.isoformat(),
        created_by=user.id,
        draft={"notes": values.notes},
    )
    db.add(item)
    db.flush()
    item.draft = service.compile_draft(db, item)
    audit(db, user, user.organization_id, "handover.drafted", "handover", item.id)
    db.flush()
    return record_dict(item)


@router.get("/handovers/{record_id}")
def detail(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    item = service.visible_handover(db, user, record_id)
    versions = []
    for version in db.scalars(
        select(HandoverVersion)
        .where(HandoverVersion.handover_id == item.id)
        .order_by(HandoverVersion.number.desc())
    ):
        items = []
        for source in db.scalars(select(HandoverItem).where(HandoverItem.version_id == version.id)):
            acks = db.scalars(
                select(HandoverItemAcknowledgement).where(HandoverItemAcknowledgement.item_id == source.id)
            ).all()
            items.append({**record_dict(source), "acknowledgements": [record_dict(ack) for ack in acks]})
        versions.append(
            {
                **record_dict(version),
                "items": items,
                "recipients": [
                    record_dict(recipient)
                    for recipient in db.scalars(
                        select(HandoverRecipient).where(HandoverRecipient.version_id == version.id)
                    )
                ],
            }
        )
    return {**record_dict(item, {"draft"} if user.role == "worker" else set()), "versions": versions}


class Publish(Input):
    notes: str = Field(default="", max_length=10000)
    changes: str = Field(min_length=3, max_length=3000)
    version: int


class SaveDraft(Input):
    notes: str = Field(default="", max_length=10000)
    version: int


@router.put("/handovers/{record_id}/draft")
def save_draft(
    record_id: str, values: SaveDraft, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    item = service.visible_handover(db, user, record_id)
    require_department(db, user, item.department_id, "publish")
    if item.version != values.version:
        fail(409, "This draft changed. Refresh before saving.")
    item.draft = {**item.draft, "notes": values.notes}
    item.draft = service.compile_draft(db, item)
    audit(db, user, user.organization_id, "handover.draft.updated", "handover", item.id)
    db.flush()
    return record_dict(item)


@router.post("/handovers/{record_id}/publish", status_code=201)
def publish(
    record_id: str, values: Publish, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    item = service.visible_handover(db, user, record_id)
    require_department(db, user, item.department_id, "publish")
    if item.version != values.version:
        fail(409, "This handover changed. Review the latest draft before publishing.")
    item.draft = {**item.draft, "notes": values.notes}
    return record_dict(service.publish(db, item, user, values.changes))


class Acknowledgement(Input):
    version_id: str
    item_id: str | None = None


@router.post("/handovers/{record_id}/acknowledge")
def acknowledge(
    record_id: str, values: Acknowledgement, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    handover = service.visible_handover(db, user, record_id)
    version = scoped(db, HandoverVersion, values.version_id, user)
    if version.handover_id != handover.id:
        fail(404, "This version does not belong to this handover.")
    recipient = db.scalar(
        select(HandoverRecipient).where(
            HandoverRecipient.version_id == version.id, HandoverRecipient.user_id == user.id
        )
    )
    if not recipient:
        fail(403, "Only an intended recipient can acknowledge this handover.")
    if values.item_id:
        item = scoped(db, HandoverItem, values.item_id, user)
        if item.version_id != version.id or not item.critical:
            fail(422, "Choose a critical item in this exact version.")
        ack = db.scalar(
            select(HandoverItemAcknowledgement).where(
                HandoverItemAcknowledgement.item_id == item.id, HandoverItemAcknowledgement.user_id == user.id
            )
        )
        if not ack:
            ack = HandoverItemAcknowledgement(
                organization_id=user.organization_id, item_id=item.id, user_id=user.id
            )
            db.add(ack)
            audit(
                db,
                user,
                user.organization_id,
                "handover.item.acknowledged",
                "handover",
                handover.id,
                after={"version_id": version.id, "item_id": item.id},
            )
    elif not recipient.acknowledged_at:
        recipient.acknowledged_at = now()
        audit(
            db,
            user,
            user.organization_id,
            "handover.acknowledged",
            "handover",
            handover.id,
            after={"version_id": version.id},
        )
    return {"status": "acknowledged", "version_id": version.id, "item_id": values.item_id}
