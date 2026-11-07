"""Persist report conversations and explicit department comparison links."""

from alembic import op
import sqlalchemy as sa
from app.db import UTCDateTime

revision = "9c402fe381a1"
down_revision = "1fb3dfb60f1f"
branch_labels = None
depends_on = None


def common(mutable=False):
    columns = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    ]
    if mutable:
        columns.append(sa.Column("updated_at", UTCDateTime(), nullable=False))
    return columns


def upgrade():
    op.create_table(
        "department_links",
        *common(True),
        sa.Column("source_department_id", sa.String(36), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("receiving_department_id", sa.String(36), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("organization_id", "source_department_id", "receiving_department_id"),
    )
    op.create_table(
        "report_conversations",
        *common(True),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("client_request_id", sa.String(80), nullable=False),
        sa.Column("language", sa.String(30), nullable=False),
        sa.Column("clarification_id", sa.String(36), sa.ForeignKey("clarifications.id")),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id")),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("author_id", "client_request_id"),
    )
    op.create_table(
        "conversation_turns",
        *common(),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("report_conversations.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("file_assets.id")),
        sa.Column("transcript_id", sa.String(36), sa.ForeignKey("transcripts.id")),
        sa.Column("extraction_id", sa.String(36), sa.ForeignKey("ai_extractions.id")),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.UniqueConstraint("conversation_id", "revision", "role"),
    )
    for table, columns in {
        "department_links": ["source_department_id", "receiving_department_id"],
        "report_conversations": ["author_id", "department_id", "report_id"],
        "conversation_turns": ["conversation_id"],
    }.items():
        for column in ["organization_id", "created_at", *columns]:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in ["conversation_turns", "report_conversations", "department_links"]:
        op.drop_table(table)
