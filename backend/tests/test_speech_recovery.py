"""Recover generated speech without changing or resurrecting source evidence."""

from datetime import timedelta

import pytest
from botocore.exceptions import ClientError
from conftest import expect
from sqlalchemy import select
from test_voice import execute, wav_bytes
from test_workflows import as_super, as_worker

from app.config import get_settings
from app.db import now
from app.models import BackgroundJob, DepartmentMembership, FileAsset
from app.services.storage import asset_available


def cached_speech(s, monkeypatch, handover=False):
    from app.integrations.gnani import client

    calls = []
    monkeypatch.setattr(get_settings(), "gnani_api_key", "test-only")
    monkeypatch.setattr(client, "speak", lambda text, language: (calls.append(text), wav_bytes())[1])
    as_super(s) if handover else as_worker(s)
    if handover:
        item = expect(
            s.client.post(
                "/api/v1/handovers",
                json={
                    "department_id": s.dept.id,
                    "shift_id": s.shift.id,
                    "shift_date": now().date().isoformat(),
                },
            ),
            201,
        )
        version = expect(
            s.client.post(
                f"/api/v1/handovers/{item['id']}/publish",
                json={
                    "notes": "Do not release the batch. Inspection is pending.",
                    "changes": "Initial handover",
                    "version": item["version"],
                },
            ),
            201,
        )
        endpoint, payload = f"/api/v1/handover-audio/{version['id']}", {"language": "en-IN"}
    else:
        endpoint = "/api/v1/report-readback"
        payload = {"department_id": s.dept.id, "text": "Inspection is pending.", "language": "en-IN"}
    queued = expect(s.client.post(endpoint, json=payload), 202)
    job = execute(s, queued["id"])
    assert job["status"] == "succeeded"
    with s.db() as db:
        asset = db.get(FileAsset, job["result"]["asset_id"])
        path = get_settings().storage_directory / asset.storage_key
    return endpoint, payload, job, asset, path, calls


@pytest.mark.parametrize("handover", [False, True])
def test_missing_cached_audio_is_rebuilt_locally_with_the_same_script(setup, monkeypatch, handover):
    s = setup
    endpoint, payload, job, asset, path, calls = cached_speech(s, monkeypatch, handover)
    path.unlink()
    assert s.client.get(f"/api/v1/files/{asset.id}").status_code == 503
    response = expect(s.client.post(f"/api/v1/jobs/{job['id']}/retry"))
    assert response["status"] == "processing" and response["result"] == {}
    fixed = expect(s.client.get(f"/api/v1/jobs/{job['id']}"))
    assert fixed["status"] == "succeeded"
    assert fixed["result"]["asset_id"] != asset.id
    assert fixed["result"]["script"] == job["result"]["script"]
    assert s.client.get("/api/v1/files/" + fixed["result"]["asset_id"]).content == wav_bytes()
    assert calls == [job["result"]["script"]] * 2
    assert expect(s.client.post(endpoint, json=payload), 202)["id"] == job["id"]
    expect(s.client.post(f"/api/v1/jobs/{job['id']}/retry"))
    assert len(calls) == 2


def test_opening_the_handover_again_repairs_a_missing_cache(setup, monkeypatch):
    s = setup
    endpoint, payload, job, asset, path, calls = cached_speech(s, monkeypatch, True)
    path.write_bytes(b"truncated")
    assert not asset_available(asset)
    expect(s.client.post(endpoint, json=payload), 202)
    fixed = expect(s.client.get(f"/api/v1/jobs/{job['id']}"))
    assert fixed["status"] == "succeeded" and fixed["result"]["asset_id"] != asset.id
    assert len(calls) == 2


@pytest.mark.parametrize("blocked", ["deleted", "expired_audio", "expired_source", "revoked", "other_worker"])
def test_recovery_preserves_retention_and_access(setup, monkeypatch, blocked):
    s = setup
    _, _, job, asset, path, calls = cached_speech(s, monkeypatch)
    path.unlink()
    with s.db.begin() as db:
        if blocked == "deleted":
            db.get(FileAsset, asset.id).deleted_at = now()
        elif blocked == "expired_audio":
            db.get(FileAsset, asset.id).retention_until = now() - timedelta(days=1)
        elif blocked == "expired_source":
            db.get(BackgroundJob, job["id"]).created_at = now() - timedelta(days=400)
        elif blocked == "revoked":
            member = db.scalar(
                select(DepartmentMembership).where(DepartmentMembership.user_id == s.worker.id)
            )
            member.active = False
    if blocked == "other_worker":
        as_worker(s, "W-02")
    result = s.client.post(f"/api/v1/jobs/{job['id']}/retry")
    assert result.status_code in {403, 410}
    assert len(calls) == 1


def test_storage_outage_does_not_regenerate_healthy_audio(setup, monkeypatch):
    from app.api import media

    s = setup
    _, _, job, _, _, calls = cached_speech(s, monkeypatch)

    def unavailable(_):
        raise PermissionError("private details must not be exposed")

    monkeypatch.setattr(media, "asset_available", unavailable)
    result = s.client.post(f"/api/v1/jobs/{job['id']}/retry")
    assert result.status_code == 503 and "private details" not in result.text
    assert len(calls) == 1


def test_failed_local_repair_can_be_retried_on_the_same_server(setup, monkeypatch):
    from app.integrations.gnani import client

    s = setup
    _, _, job, _, path, _ = cached_speech(s, monkeypatch)
    path.unlink()

    def unavailable(*_):
        raise client.ProviderUnavailable("Speech is temporarily unavailable.")

    monkeypatch.setattr(client, "speak", unavailable)
    expect(s.client.post(f"/api/v1/jobs/{job['id']}/retry"))
    assert expect(s.client.get(f"/api/v1/jobs/{job['id']}"))["status"] == "failed"
    monkeypatch.setattr(client, "speak", lambda *_: wav_bytes())
    expect(s.client.post(f"/api/v1/jobs/{job['id']}/retry"))
    assert expect(s.client.get(f"/api/v1/jobs/{job['id']}"))["status"] == "succeeded"


def test_storage_probe_distinguishes_missing_s3_objects_from_denied_access(monkeypatch):
    from types import SimpleNamespace

    from app.services import storage

    monkeypatch.setattr(get_settings(), "storage_mode", "s3")
    asset = SimpleNamespace(storage_key="private/key", byte_size=44)
    monkeypatch.setattr(storage, "s3", lambda: SimpleNamespace(head_object=lambda **_: {"ContentLength": 44}))
    assert asset_available(asset)

    def missing(**_):
        raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")

    monkeypatch.setattr(storage, "s3", lambda: SimpleNamespace(head_object=missing))
    assert not asset_available(asset)

    def denied(**_):
        raise ClientError({"Error": {"Code": "AccessDenied"}}, "HeadObject")

    monkeypatch.setattr(storage, "s3", lambda: SimpleNamespace(head_object=denied))
    with pytest.raises(ClientError):
        asset_available(asset)
