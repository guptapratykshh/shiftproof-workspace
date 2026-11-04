"""Protect published versions and audit history at the database boundary.

Revision ID: 8d73a014be2c
Revises: 03697da140ec
"""

from alembic import op

revision = "8d73a014be2c"
down_revision = "03697da140ec"
branch_labels = None
depends_on = None

TABLES = (
    "report_versions",
    "handover_versions",
    "handover_items",
    "task_history",
    "task_verifications",
    "alert_history",
    "report_reviews",
    "audit_logs",
)


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION shiftproof_immutable_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Historical records are immutable; append a new version or event'; END; $$"
        )
        for table in TABLES:
            op.execute(
                f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION shiftproof_immutable_history()"
            )
    elif dialect == "sqlite":
        for table in TABLES:
            for operation in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER protect_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'Historical records are immutable'); END"
                )


def downgrade():
    dialect = op.get_bind().dialect.name
    for table in TABLES:
        if dialect == "postgresql":
            op.execute(f"DROP TRIGGER IF EXISTS protect_{table} ON {table}")
        elif dialect == "sqlite":
            for operation in ("update", "delete"):
                op.execute(f"DROP TRIGGER IF EXISTS protect_{table}_{operation}")
    if dialect == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS shiftproof_immutable_history()")
