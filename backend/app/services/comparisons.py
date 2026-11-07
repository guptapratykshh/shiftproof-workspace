"""Server-only matching; callers expose only authorized comparison summaries."""

from datetime import timedelta

from sqlalchemy import or_, select

from ..models import Department, DepartmentLink, Organization, Report, ReportVersion
from .contradictions import compare


def linked_departments(db, organization_id, department_id):
    links = list(
        db.scalars(
            select(DepartmentLink).where(
                DepartmentLink.organization_id == organization_id,
                DepartmentLink.active.is_(True),
                or_(
                    DepartmentLink.source_department_id == department_id,
                    DepartmentLink.receiving_department_id == department_id,
                ),
            )
        )
    )
    active = {
        d.id
        for d in db.scalars(
            select(Department).where(
                Department.organization_id == organization_id, Department.active.is_(True)
            )
        )
    }
    return [
        link
        for link in links
        if link.source_department_id in active and link.receiving_department_id in active
    ]


def candidates(db, report, fields):
    links = linked_departments(db, report.organization_id, report.department_id)
    departments = {report.department_id}
    for link in links:
        departments.update([link.source_department_id, link.receiving_department_id])
    # Explicit transfers can span shifts/days. Ordinary observations retain the
    # existing 24-hour candidate window and stricter period matching.
    query = select(Report).where(
        Report.organization_id == report.organization_id, Report.department_id.in_(list(departments))
    )
    if getattr(report, "id", None):
        query = query.where(Report.id != report.id)
    if not fields.get("transfer_reference"):
        query = query.where(
            Report.occurred_at >= report.occurred_at - timedelta(hours=24),
            Report.occurred_at <= report.occurred_at + timedelta(hours=24),
        )
    reports = list(db.scalars(query.order_by(Report.created_at.desc())))
    if not reports:
        return []
    latest = {r.id: r.latest_version for r in reports}
    versions = {
        v.report_id: v
        for v in db.scalars(select(ReportVersion).where(ReportVersion.report_id.in_(list(latest))))
        if v.number == latest[v.report_id]
    }
    timezone = db.get(Organization, report.organization_id).timezone
    result = []
    for other in reports:
        version = versions.get(other.id)
        if not version:
            continue
        cross = other.department_id != report.department_id
        findings = compare(fields, version.fields, report, other, timezone, cross_department=cross)
        if not findings:
            continue
        owner = report.department_id
        if cross:
            link = next(
                link
                for link in links
                if {link.source_department_id, link.receiving_department_id}
                == {other.department_id, report.department_id}
            )
            owner = link.receiving_department_id
        result.append(
            {"report": other, "version": version, "findings": findings, "owner_department_id": owner}
        )
    return result
