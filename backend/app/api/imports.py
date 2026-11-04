import csv
import io
import zipfile
from datetime import timedelta

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import Department, ImportBatch, Shift, Team, User
from ..schemas import Input, WorkerInput
from ..security import current_user, department_ids, fail, scoped
from ..services.common import audit
from ..services.workforce import require_workforce, save_worker

router = APIRouter(tags=["Workforce import"])
HEADERS = [
    "full_name",
    "employee_id",
    "primary_department",
    "additional_departments",
    "teams",
    "skills",
    "shift",
    "contact_number",
]


@router.get("/worker-imports/template")
def template(user: User = Depends(current_user)):
    if user.role == "worker":
        fail(403, "Workforce management access is required.")
    return Response(
        ",".join(HEADERS) + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="shiftproof-workers.csv"'},
    )


def parse_rows(content: bytes, filename: str):
    if len(content) > 2 * 1024 * 1024:
        fail(413, "The import file must be no larger than 2 MB.")
    try:
        if filename.lower().endswith(".csv"):
            return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        if not filename.lower().endswith(".xlsx"):
            fail(415, "Use a UTF-8 CSV or XLSX workbook.")
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > 20 * 1024 * 1024:
                fail(413, "The expanded workbook is too large.")
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        sheet = workbook.active
        if sheet.max_row > 501 or sheet.max_column > 20:
            fail(413, "Import at most 500 workers using the supplied columns.")
        rows = list(sheet.iter_rows(values_only=True))
        workbook.close()
        return [
            dict(
                zip([str(cell or "").strip() for cell in rows[0]], [str(cell or "").strip() for cell in row])
            )
            for row in rows[1:]
        ]
    except (UnicodeError, csv.Error, zipfile.BadZipFile, ValueError, IndexError, KeyError):
        fail(422, "This file could not be read. Download and fill in the import template.")


@router.post("/worker-imports/preview", status_code=201)
async def preview(
    file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if user.role == "worker":
        fail(403, "Workforce management access is required.")
    rows = parse_rows(await file.read(2 * 1024 * 1024 + 1), file.filename or "")
    if not rows or len(rows) > 500:
        fail(422, "Include between 1 and 500 workers.")
    allowed = department_ids(db, user)
    departments = {
        item.name.casefold(): item.id
        for item in db.scalars(
            select(Department).where(
                Department.organization_id == user.organization_id,
                Department.active.is_(True),
                Department.id.in_(allowed),
            )
        )
    }
    teams = list(
        db.scalars(select(Team).where(Team.organization_id == user.organization_id, Team.active.is_(True)))
    )
    shifts = {
        item.name.casefold(): item.id
        for item in db.scalars(
            select(Shift).where(Shift.organization_id == user.organization_id, Shift.active.is_(True))
        )
    }
    existing = set(
        db.scalars(
            select(User.employee_code).where(
                User.organization_id == user.organization_id, User.role == "worker"
            )
        )
    )
    seen, output = set(), []
    for index, row in enumerate(rows, start=2):
        errors, values = [], None
        row = {key: str(value or "").strip() for key, value in row.items() if key}
        if any(value.startswith(("=", "+", "@")) for value in row.values()):
            errors.append("Formula-like values are not accepted.")
        primary = departments.get(row.get("primary_department", "").casefold())
        if not primary:
            errors.append("Primary department is missing, inactive or unavailable.")
        department_list = [primary] if primary else []
        for name in row.get("additional_departments", "").split(";"):
            if name.strip():
                identifier = departments.get(name.strip().casefold())
                if identifier:
                    department_list.append(identifier)
                else:
                    errors.append(f"Additional department not found: {name[:80]}")
        team_ids = []
        for name in row.get("teams", "").split(";"):
            if name.strip():
                matches = [
                    team
                    for team in teams
                    if team.department_id in department_list
                    and team.name.casefold() == name.strip().casefold()
                ]
                if len(matches) != 1:
                    errors.append(f"Team is missing or ambiguous: {name[:80]}")
                else:
                    team_ids.append(matches[0].id)
        code = row.get("employee_id") or None
        if code and (code in existing or code in seen):
            errors.append("Employee ID is duplicated in the organization or this upload.")
        if code:
            seen.add(code)
        shift = shifts.get(row.get("shift", "").casefold())
        if row.get("shift") and not shift:
            errors.append("Shift does not exist or is inactive.")
        if not errors:
            try:
                for dept in department_list:
                    require_workforce(db, user, dept)
                values = WorkerInput(
                    name=row.get("full_name", ""),
                    employee_code=code,
                    phone=row.get("contact_number", ""),
                    department_ids=list(dict.fromkeys(department_list)),
                    primary_department_id=primary,
                    team_ids=team_ids,
                    skills=[v.strip() for v in row.get("skills", "").split(";") if v.strip()],
                    shift_id=shift,
                ).model_dump(mode="json")
            except ValidationError as error:
                errors += [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
        output.append({"row": index, "input": row, "valid": not errors, "errors": errors, "values": values})
    item = ImportBatch(
        organization_id=user.organization_id,
        created_by=user.id,
        rows=output,
        expires_at=now() + timedelta(hours=2),
    )
    db.add(item)
    db.flush()
    return {
        "id": item.id,
        "rows": output,
        "valid": sum(row["valid"] for row in output),
        "invalid": sum(not row["valid"] for row in output),
        "expires_at": item.expires_at,
    }


class Confirm(Input):
    confirm_valid_rows_only: bool = False


@router.post("/worker-imports/{record_id}/confirm")
def confirm(
    record_id: str, values: Confirm, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = scoped(db, ImportBatch, record_id, user)
    if item.created_by != user.id:
        fail(403, "Only the person who previewed this import can confirm it.")
    if item.status == "confirmed":
        return item.result
    if item.expires_at <= now():
        fail(410, "This preview expired. Upload again to validate current memberships.")
    invalid = sum(not row["valid"] for row in item.rows)
    if invalid and not values.confirm_valid_rows_only:
        fail(422, "Correct invalid rows or explicitly confirm importing valid rows only.")
    changed = db.execute(
        update(ImportBatch)
        .where(ImportBatch.id == item.id, ImportBatch.status == "preview")
        .values(status="confirming")
    )
    if changed.rowcount != 1:
        fail(409, "This import is already being confirmed.")
    result = []
    for row in item.rows:
        if row["valid"]:
            worker = save_worker(db, user, WorkerInput.model_validate(row["values"]))
            result.append(
                {
                    "row": row["row"],
                    "id": worker["id"],
                    "name": worker["name"],
                    "employee_code": worker["employee_code"],
                    "activation_url": worker["activation_url"],
                }
            )
    item.status, item.result = (
        "confirmed",
        {"created": len(result), "skipped_invalid": invalid, "workers": result},
    )
    audit(
        db,
        user,
        user.organization_id,
        "workers.imported",
        "import_batch",
        item.id,
        after={"created": len(result), "skipped_invalid": invalid},
    )
    return item.result
