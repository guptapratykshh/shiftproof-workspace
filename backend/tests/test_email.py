import smtplib
import ssl
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.config import Settings, get_settings
from app.models import BackgroundJob
from conftest import PASSWORD, expect


@pytest.mark.parametrize("mode,delivery", [("file", "local_outbox"), ("smtp", "smtp_queued")])
def test_registration_reports_transport_without_claiming_delivery(environment, monkeypatch, mode, delivery):
    monkeypatch.setattr(get_settings(), "mail_mode", mode)
    result = expect(environment.client.post("/api/v1/auth/register", json={
        "fullName": "Mail Test",
        "organizationName": "Mail Test Organization",
        "organizationType": "manufacturing",
        "email": "mail-test@example.com",
        "password": PASSWORD,
    }), 202)
    assert result == {"status": "verification_required", "delivery": delivery}
    with environment.db() as db:
        job = db.scalar(select(BackgroundJob).where(BackgroundJob.kind == "email"))
        assert job.status == "queued"
        assert job.payload["to"] == "mail-test@example.com"


def test_recovery_transport_does_not_reveal_account_existence(setup, monkeypatch):
    monkeypatch.setattr(get_settings(), "mail_mode", "file")
    existing = expect(setup.client.post("/api/v1/auth/recover", json={
        "email": "admin@example.com", "role": "organization",
    }), 202)
    missing = expect(setup.client.post("/api/v1/auth/recover", json={
        "email": "missing@example.com", "role": "organization",
    }), 202)
    assert existing == missing == {"status": "recovery_requested", "delivery": "local_outbox"}


@pytest.mark.parametrize("reject_login", [False, True])
def test_smtp_requires_verified_tls_and_propagates_authentication_failure(monkeypatch, reject_login):
    from app import worker

    settings = Settings(
        _env_file=None, mail_mode="smtp", smtp_host="smtp.example.com", smtp_port=587,
        smtp_starttls=True, smtp_user="sender@example.com", smtp_password="test-app-password",
        mail_from="ShiftProof <sender@example.com>",
    )
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    calls = []

    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.com", 587, 30)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def starttls(self, *, context):
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            calls.append("tls")

        def login(self, user, password):
            assert calls == ["tls"]
            assert (user, password) == ("sender@example.com", "test-app-password")
            calls.append("login")
            if reject_login:
                raise smtplib.SMTPAuthenticationError(535, b"Authentication refused")

        def send_message(self, message):
            assert calls == ["tls", "login"]
            assert message["To"] == "recipient@example.com"
            assert message["Date"]
            assert "verification" in message.get_content()
            calls.append("send")

    monkeypatch.setattr(worker.smtplib, "SMTP", SMTP)
    job = SimpleNamespace(id="test-mail", payload={
        "to": "recipient@example.com", "subject": "Verify your email", "text": "A verification link.",
    })
    if reject_login:
        with pytest.raises(smtplib.SMTPAuthenticationError):
            worker.email(job)
        assert calls == ["tls", "login"]
    else:
        assert worker.email(job) == {"delivery": "smtp_accepted"}
        assert calls == ["tls", "login", "send"]


def test_authenticated_smtp_cannot_start_without_a_password():
    with pytest.raises(ValidationError, match="SMTP_PASSWORD is required"):
        Settings(_env_file=None, mail_mode="smtp", smtp_user="sender@example.com", smtp_password="")


def test_file_delivery_stays_local_and_private(tmp_path, monkeypatch):
    from app import worker

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(worker, "get_settings", lambda: Settings(_env_file=None, mail_mode="file"))
    job = SimpleNamespace(id="local-mail", payload={
        "to": "recipient@example.com", "subject": "Verify your email", "text": "Local verification link.",
    })
    assert worker.email(job) == {"delivery": "local_outbox"}
    message = tmp_path / "data/outbox/local-mail.eml"
    assert "Local verification link." in message.read_text()
    assert message.stat().st_mode & 0o777 == 0o600
