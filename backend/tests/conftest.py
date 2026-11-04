import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Department, DepartmentMembership, Organization, Shift, Team, TeamMembership, User
from app.security import hash_secret

PASSWORD = "Testing-account-123"
PIN = "583719"


@pytest.fixture
def environment(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    engine = make_engine(url)
    schema = f"test_{uuid4().hex}" if engine.dialect.name == "postgresql" else None
    if schema:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine.dispose()

        @event.listens_for(engine, "connect")
        def search_path(connection, _):
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema}"')

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def session():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = session
    monkeypatch.setattr(get_settings(), "storage_directory", tmp_path / "evidence")
    monkeypatch.setattr(get_settings(), "gnani_api_key", "")
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    import app.worker as worker

    monkeypatch.setattr(worker, "SessionLocal", factory)
    client = TestClient(app)
    yield SimpleNamespace(client=client, db=factory, worker=worker, tmp=tmp_path)
    client.close()
    app.dependency_overrides.clear()
    if schema:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


def login(client, role, email="", code="ORG-TEST", employee="W-01"):
    response = client.post(
        f"/api/v1/auth/login/{role}",
        json={
            "email": email,
            "password": PASSWORD,
            "organizationId": code,
            "employeeId": employee,
            "pin": PIN,
        },
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = client.cookies.get("shiftproof_csrf")
    return response.json()


def expect(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


@pytest.fixture
def setup(environment):
    with environment.db.begin() as db:
        org = Organization(
            code="ORG-TEST",
            name="Test Factory",
            industry="manufacturing",
            active=True,
            settings={"profile_completed": True},
        )
        other_org = Organization(
            code="ORG-OTHER", name="Other Factory", industry="manufacturing", active=True
        )
        db.add_all([org, other_org])
        db.flush()
        dept = Department(organization_id=org.id, name="Production")
        other = Department(organization_id=org.id, name="Maintenance")
        foreign = Department(organization_id=other_org.id, name="Foreign")
        shift = Shift(
            organization_id=org.id, name="Morning", starts_at="06:00", ends_at="14:00", days=list(range(7))
        )
        db.add_all([dept, other, foreign, shift])
        db.flush()
        team = Team(organization_id=org.id, department_id=dept.id, name="Line A")
        admin = User(
            organization_id=org.id,
            name="Admin",
            email="admin@example.com",
            role="organization",
            password_hash=hash_secret(PASSWORD),
            active=True,
            verified=True,
        )
        supervisor = User(
            organization_id=org.id,
            name="Supervisor",
            email="supervisor@example.com",
            role="supervisor",
            password_hash=hash_secret(PASSWORD),
            active=True,
            verified=True,
        )
        worker = User(
            organization_id=org.id,
            name="Worker One",
            employee_code="W-01",
            role="worker",
            pin_hash=hash_secret(PIN),
            active=True,
            verified=True,
        )
        worker2 = User(
            organization_id=org.id,
            name="Worker Two",
            employee_code="W-02",
            role="worker",
            pin_hash=hash_secret(PIN),
            active=True,
            verified=True,
        )
        foreign_supervisor = User(
            organization_id=other_org.id,
            name="Foreign Supervisor",
            email="foreign@example.com",
            role="supervisor",
            password_hash=hash_secret(PASSWORD),
            active=True,
            verified=True,
        )
        db.add_all([team, admin, supervisor, worker, worker2, foreign_supervisor])
        db.flush()
        permissions = ["view", "manage", "review", "publish", "workforce", "evidence"]
        db.add_all(
            [
                DepartmentMembership(
                    organization_id=org.id,
                    user_id=supervisor.id,
                    department_id=dept.id,
                    primary=True,
                    permissions=permissions,
                ),
                DepartmentMembership(
                    organization_id=org.id,
                    user_id=worker.id,
                    department_id=dept.id,
                    primary=True,
                    permissions=["view"],
                ),
                DepartmentMembership(
                    organization_id=org.id,
                    user_id=worker2.id,
                    department_id=dept.id,
                    primary=True,
                    permissions=["view"],
                ),
                DepartmentMembership(
                    organization_id=other_org.id,
                    user_id=foreign_supervisor.id,
                    department_id=foreign.id,
                    primary=True,
                    permissions=permissions,
                ),
                TeamMembership(organization_id=org.id, user_id=worker.id, team_id=team.id),
                TeamMembership(organization_id=org.id, user_id=worker2.id, team_id=team.id),
            ]
        )
    for name, value in locals().copy().items():
        if name in {
            "org",
            "other_org",
            "dept",
            "other",
            "foreign",
            "shift",
            "team",
            "admin",
            "supervisor",
            "worker",
            "worker2",
            "foreign_supervisor",
        }:
            setattr(environment, name, value)
    environment.jobs = __import__("app.worker", fromlist=["claim"])
    return environment
