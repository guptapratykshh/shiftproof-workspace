"""Run with DATABASE_URL and TEST_DATABASE_URL selecting an empty shiftproof_test_* database."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.db import Base, make_engine, make_session_factory
from app.models import AuditLog, BackgroundJob, Department, Organization, User


@pytest.fixture
def mongo(environment):
    if not hasattr(environment.db, "engine") or environment.db.engine.dialect.name != "mongodb":
        pytest.skip("Requires an isolated MongoDB database")
    return environment


def organization():
    return Organization(code="ORG-MONGO", name="Mongo test", industry="manufacturing")


def test_native_persistence_precision_rollback_and_constraints(mongo):
    timestamp = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    with mongo.db.begin() as db:
        org = organization()
        org.created_at = timestamp
        db.add(org)
        db.add_all(
            [
                User(organization_id=org.id, role="worker", name="A"),
                User(organization_id=org.id, role="worker", name="B"),
            ]
        )
    native = mongo.db.engine.database
    assert native.organizations.find_one({"_id": org.id})["created_at"] == timestamp.isoformat(
        timespec="microseconds"
    )
    with mongo.db() as db:
        assert db.get(Organization, org.id).created_at == timestamp
        db.get(Organization, org.id).name = "Rolled back"
        db.add(Department(organization_id=org.id, name="Rolled back"))
        db.flush()
        db.rollback()
        assert db.get(Organization, org.id).name == "Mongo test"
    assert native.departments.count_documents({}) == 0
    with pytest.raises(IntegrityError), mongo.db.begin() as db:
        db.add(organization())
    with pytest.raises(IntegrityError), mongo.db.begin() as db:
        db.add(Department(organization_id=str(uuid4()), name="Missing parent"))
    with mongo.db.begin() as db:
        event = AuditLog(
            organization_id=org.id,
            actor_role="system",
            action="test",
            entity_type="organization",
            entity_id=org.id,
        )
        db.add(event)
    with pytest.raises(ValueError, match="immutable"), mongo.db.begin() as db:
        db.get(AuditLog, event.id).action = "changed"
    with pytest.raises(ValueError, match="immutable"), mongo.db.begin() as db:
        db.delete(db.get(AuditLog, event.id))
    with pytest.raises(IntegrityError), mongo.db.begin() as db:
        db.delete(db.get(Organization, org.id))


def test_concurrent_updates_and_job_claims(mongo):
    with mongo.db.begin() as db:
        org = organization()
        db.add(org)
        job = BackgroundJob(kind="test", dedupe_key="one-job", payload={})
        db.add(job)
    with mongo.db() as first, mongo.db() as second:
        a, b = first.get(Organization, org.id), second.get(Organization, org.id)
        a.name, b.name = "First", "Second"
        first.commit()
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    barrier = Barrier(2)

    def claim():
        barrier.wait()
        try:
            return mongo.worker.claim()
        except StaleDataError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim(), range(2)))
    assert sum(result is not None for result in claims) == 1
    with mongo.db() as db:
        assert db.get(BackgroundJob, job.id).attempts == 1


def test_migration_is_verified_resumable_and_never_overwrites(mongo, monkeypatch):
    from app import migrate_to_mongo

    source = f"sqlite:///{mongo.tmp / 'source.db'}"
    sql = make_engine(source)
    Base.metadata.create_all(sql)
    with make_session_factory(sql).begin() as db:
        org = organization()
        db.add(org)
    sql.dispose()
    monkeypatch.setattr(migrate_to_mongo, "engine", mongo.db.engine)
    assert migrate_to_mongo.migrate(source, dry_run=True)["records"] == 1
    assert mongo.db.engine.database.organizations.count_documents({}) == 0
    assert migrate_to_mongo.migrate(source)["status"] == "verified"
    assert migrate_to_mongo.migrate(source)["status"] == "verified"
    with mongo.db.begin() as db:
        db.get(Organization, org.id).name = "Preserve this edit"
    with pytest.raises(ValueError, match="differs"):
        migrate_to_mongo.migrate(source)
    with mongo.db() as db:
        assert db.scalar(select(Organization)).name == "Preserve this edit"


def test_bson_backup_restore_preserves_records_and_indexes(mongo):
    from app.mongo_backup import backup, restore

    with mongo.db.begin() as db:
        db.add(organization())
    engine = mongo.db.engine
    destination = mongo.tmp / "mongo.tar.gz"
    assert backup(engine.database, destination)["records"] == 1
    with pytest.raises(ValueError, match="empty"):
        restore(engine.database, destination)
    recovery = engine.client[engine.database.name + "_recovery"]
    try:
        assert restore(recovery, destination)["status"] == "verified"
        assert list(recovery.organizations.find({})) == list(engine.database.organizations.find({}))
        assert recovery.organizations.index_information()["uq_code"]["unique"]
    finally:
        engine.client.drop_database(recovery.name)
