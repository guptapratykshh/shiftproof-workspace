import subprocess
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.services import storage


def production(**changes):
    return Settings(_env_file=None, **dict({
        'app_env': 'production', 'cookie_secure': True, 'mail_mode': 'smtp',
        'frontend_url': 'https://example.org', 'allowed_origins': ['https://example.org'],
        'smtp_user': 'sender', 'smtp_password': 'test-only', 'smtp_starttls': True,
    }, **changes))


def test_production_rejects_insecure_configuration(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    assert production().cookie_secure
    for change in ({'allowed_origins': ['*']}, {'allowed_origins': ['http://example.org']},
                   {'smtp_starttls': False}, {'storage_mode': 's3', 's3_bucket': ''},
                   {'storage_mode': 'misspelled'}, {'s3_key_prefix': '../evidence'}):
        with pytest.raises(ValidationError):
            production(**change)


def test_a_container_header_does_not_bypass_media_validation(monkeypatch):
    def failed(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ['ffprobe'])
    monkeypatch.setattr(storage.subprocess, 'run', failed)
    for fake in (b'\x1a\x45\xdf\xa3fake', b'RIFFxxxxWAVEfake', b'OggSfake', b'xxxxftypxxxx'):
        with pytest.raises(HTTPException) as failure:
            storage.validate_bytes(fake, 'audio/webm', 'audio')
        assert failure.value.status_code == 422


def test_s3_prefix_is_consistent_for_writes_reads_checks_and_deletes(monkeypatch):
    import io
    settings = get_settings()
    for key, value in {'storage_mode':'s3', 's3_bucket':'test-private', 's3_key_prefix':'evidence/'}.items():
        monkeypatch.setattr(settings, key, value)
    calls = []
    def call(**kwargs):
        calls.append(kwargs)
        return {'Body': io.BytesIO(b'audio'), 'ContentLength': 5}
    monkeypatch.setattr(storage, 's3', lambda: SimpleNamespace(
        put_object=call, get_object=call, head_object=call, delete_object=call))
    asset = SimpleNamespace(storage_key='organization/recording', byte_size=5)
    storage.put_bytes(asset.storage_key, b'audio', 'audio/wav')
    assert storage.read_bytes(asset) == b'audio'
    assert storage.asset_available(asset)
    storage.delete_bytes(asset)
    assert all(item['Key'] == 'evidence/organization/recording' for item in calls)
    assert calls[0]['ServerSideEncryption'] == 'AES256'


def test_real_media_works_but_a_disguised_playlist_cannot_read_another_file(tmp_path):
    from test_voice import wav_bytes
    source = tmp_path / 'private.wav'
    source.write_bytes(wav_bytes())
    assert storage.validate_bytes(source.read_bytes(), 'audio/wav', 'audio')[1] == 'audio/wav'
    assert storage.wav_for_transcription(source.read_bytes()).startswith(b'RIFF')
    playlist = f"ffconcat version 1.0\nfile '{source}'\n".encode()
    with pytest.raises(HTTPException):
        storage.validate_bytes(playlist, 'audio/wav', 'audio')
    with pytest.raises(ValueError):
        storage.wav_for_transcription(playlist)


def test_old_local_workers_cannot_claim_production_jobs_or_expired_leases(environment, monkeypatch):
    from datetime import timedelta
    from app.db import now
    from app.models import BackgroundJob
    from app.services.common import enqueue, record_dict
    s = environment
    settings = get_settings()
    monkeypatch.setattr(settings, 'job_namespace', 'aws')
    with s.db.begin() as db:
        job = enqueue(db, 'test', 'same-request', {})
        identity = job.id
        assert job.status == 'aws:queued'
        assert record_dict(job)['status'] == 'queued'
        assert enqueue(db, 'test', 'same-request', {}).id == identity
    monkeypatch.setattr(settings, 'job_namespace', '')
    assert s.worker.claim() is None
    monkeypatch.setattr(settings, 'job_namespace', 'aws')
    claimed = s.worker.claim()
    assert claimed[0] == identity
    with s.db.begin() as db:
        job = db.get(BackgroundJob, identity)
        assert job.status == 'aws:processing'
        assert record_dict(job)['status'] == 'processing'
        job.leased_until = now() - timedelta(seconds=1)
    monkeypatch.setattr(settings, 'job_namespace', '')
    assert s.worker.claim() is None
    monkeypatch.setattr(settings, 'job_namespace', 'aws')
    claimed = s.worker.claim()
    s.worker.execute(*claimed)
    with s.db() as db:
        job = db.get(BackgroundJob, identity)
        assert job.status == 'aws:queued'
        assert record_dict(job)['status'] == 'queued'
