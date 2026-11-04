"""Isolated local PostgreSQL migration, immutable-history and pg_dump/restore exercise.

Run with PG_QA_DSN pointing at the local maintenance database. Creates and removes
only two uniquely named shiftproof_qa_* databases; existing application data is untouched.
"""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import AuditLog, FileAsset, Organization, User

dsn = os.environ["PG_QA_DSN"]
parts = urlsplit(dsn)
if parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("This verification script requires an isolated local PostgreSQL server.")
names = [f"shiftproof_qa_{uuid4().hex[:12]}" for _ in range(2)]
created = []
engines = []
with psycopg.connect(dsn, autocommit=True) as administration:
    try:
        for name in names:
            administration.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created.append(name)
        urls = [urlunsplit((parts.scheme, parts.netloc, f"/{name}", "", "")) for name in names]
        env = {
            **os.environ,
            "DATABASE_URL": urls[0].replace("postgresql://", "postgresql+psycopg://"),
            "APP_ENV": "test",
        }
        for action, target in (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
            subprocess.run([sys.executable, "-m", "alembic", action, target], env=env, check=True)
        source = create_engine(env["DATABASE_URL"])
        engines.append(source)
        with tempfile.TemporaryDirectory(prefix="shiftproof-restore-") as directory:
            root = Path(directory)
            content = b"Controlled recovery verification evidence"
            source_file = root / "evidence" / "recovery.dat"
            source_file.parent.mkdir()
            source_file.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            with Session(source) as db:
                org = Organization(
                    code="ORG-RECOVERY", name="Recovery verification", industry="manufacturing"
                )
                db.add(org)
                db.flush()
                user = User(
                    organization_id=org.id, name="Recovery verifier", role="worker", employee_code="RECOVERY"
                )
                db.add(user)
                db.flush()
                asset = FileAsset(
                    organization_id=org.id,
                    owner_id=user.id,
                    name="recovery.dat",
                    storage_key="recovery.dat",
                    mime_type="application/octet-stream",
                    kind="test",
                    byte_size=len(content),
                    sha256=digest,
                )
                db.add(asset)
                event = AuditLog(
                    organization_id=org.id,
                    actor_role="system",
                    action="recovery.verification",
                    entity_type="organization",
                    entity_id=org.id,
                )
                db.add(event)
                db.commit()
                event_id = event.id
            for statement in (
                "UPDATE audit_logs SET action='tampered' WHERE id=:id",
                "DELETE FROM audit_logs WHERE id=:id",
            ):
                try:
                    with source.begin() as connection:
                        connection.execute(text(statement), {"id": event_id})
                except DBAPIError:
                    pass
                else:
                    raise AssertionError("Historical mutation was not blocked")
            dump = root / "database.dump"
            subprocess.run(
                ["pg_dump", "--dbname", urls[0], "--format=custom", "--file", str(dump)], check=True
            )
            subprocess.run(
                ["tar", "-czf", str(root / "evidence.tar.gz"), "-C", str(root), "evidence"], check=True
            )
            subprocess.run(
                ["pg_restore", "--dbname", urls[1], "--no-owner", "--single-transaction", str(dump)],
                check=True,
            )
            recovered = root / "recovered"
            recovered.mkdir()
            subprocess.run(["tar", "-xzf", str(root / "evidence.tar.gz"), "-C", str(recovered)], check=True)
            target = create_engine(urls[1].replace("postgresql://", "postgresql+psycopg://"))
            engines.append(target)
            with Session(target) as db:
                asset = db.query(FileAsset).one()
                assert (
                    hashlib.sha256((recovered / "evidence" / asset.storage_key).read_bytes()).hexdigest()
                    == asset.sha256
                )
                assert db.query(AuditLog).one().action == "recovery.verification"
                assert db.query(Organization).one().code == "ORG-RECOVERY"
                assert db.execute(text("SELECT version_num FROM alembic_version")).scalar() == "1fb3dfb60f1f"
            print(
                "PASS: PostgreSQL migration round trip, immutable history, database restore, evidence checksum."
            )
    finally:
        for engine in engines:
            engine.dispose()
        for name in created:
            administration.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
