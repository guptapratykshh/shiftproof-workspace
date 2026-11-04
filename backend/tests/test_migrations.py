import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import AuditLog, Organization


def test_fresh_migration_cycle_and_database_history_protection(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    env = {**os.environ, "DATABASE_URL": url, "APP_ENV": "test"}

    def alembic(*args):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args], env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    alembic("upgrade", "head")
    alembic("downgrade", "base")
    alembic("upgrade", "head")
    engine = create_engine(url)
    with Session(engine) as db:
        org = Organization(code="ORG-MIGRATION", name="Migration test", industry="manufacturing")
        db.add(org)
        db.flush()
        event = AuditLog(
            organization_id=org.id,
            actor_role="system",
            action="migration.test",
            entity_type="organization",
            entity_id=org.id,
        )
        db.add(event)
        db.commit()
        event_id = event.id
    for operation in (
        "UPDATE audit_logs SET action='tampered' WHERE id=:id",
        "DELETE FROM audit_logs WHERE id=:id",
    ):
        with pytest.raises(DBAPIError):
            with engine.begin() as connection:
                connection.execute(text(operation), {"id": event_id})
    with Session(engine) as db:
        assert db.scalar(select(AuditLog.action).where(AuditLog.id == event_id)) == "migration.test"
    engine.dispose()
