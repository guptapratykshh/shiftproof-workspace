import hashlib
import json
import os
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import new_id, now
from ..models import FileAsset, User
from ..security import fail, policy_value


def s3():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def put_bytes(key: str, content: bytes, mime: str):
    settings = get_settings()
    if settings.storage_mode == "s3":
        s3().put_object(
            Bucket=settings.s3_bucket, Key=key, Body=content, ContentType=mime, ServerSideEncryption="AES256"
        )
    else:
        path = settings.storage_directory / key
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
            output.write(content)


def read_bytes(asset: FileAsset):
    settings = get_settings()
    if settings.storage_mode == "s3":
        return s3().get_object(Bucket=settings.s3_bucket, Key=asset.storage_key)["Body"].read()
    return (settings.storage_directory / asset.storage_key).read_bytes()


def asset_available(asset: FileAsset):
    """Distinguish a missing/truncated file from a storage service outage."""
    settings = get_settings()
    if settings.storage_mode == "s3":
        try:
            metadata = s3().head_object(Bucket=settings.s3_bucket, Key=asset.storage_key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return metadata["ContentLength"] == asset.byte_size
    try:
        return (settings.storage_directory / asset.storage_key).stat().st_size == asset.byte_size
    except FileNotFoundError:
        return False


def delete_bytes(asset: FileAsset):
    settings = get_settings()
    if settings.storage_mode == "s3":
        s3().delete_object(Bucket=settings.s3_bucket, Key=asset.storage_key)
    else:
        (settings.storage_directory / asset.storage_key).unlink(missing_ok=True)


def media_probe(content: bytes):
    with tempfile.NamedTemporaryFile() as media:
        media.write(content)
        media.flush()
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", media.name],
                capture_output=True,
                timeout=15,
                check=True,
            )
            return json.loads(result.stdout)
        except (subprocess.SubprocessError, FileNotFoundError, ValueError):
            # Fallback for standard media container signatures
            if (
                content.startswith(b"\x1a\x45\xdf\xa3")  # WebM / Matroska
                or (content[:4] == b"RIFF" and content[8:12] == b"WAVE")  # WAV
                or content.startswith(b"OggS")  # OGG
                or (len(content) > 12 and b"ftyp" in content[:32])  # MP4 / M4A
            ):
                return {"streams": [{"codec_type": "audio"}]}
            fail(422, "This audio or video could not be read. Try another file.")


def validate_bytes(content: bytes, declared: str, kind: str):
    if not content or len(content) > get_settings().max_upload_bytes:
        fail(413, "Choose a non-empty file no larger than 25 MB.")
    if kind in {"photo", "logo"}:
        mime = (
            "image/png"
            if content.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/jpeg"
            if content.startswith(b"\xff\xd8\xff")
            else "image/webp"
            if content[:4] == b"RIFF" and content[8:12] == b"WEBP"
            else None
        )
        if not mime:
            fail(415, "Use a PNG, JPEG or WebP image.")
        # Decode pixels to reject malformed/polyglot images, remove metadata and normalize format.
        from PIL import Image, UnidentifiedImageError
        from io import BytesIO

        try:
            with Image.open(BytesIO(content)) as original:
                if original.width * original.height > 24_000_000:
                    fail(413, "Image resolution is too large.")
                output = BytesIO()
                original.convert("RGB").save(output, format="JPEG", quality=90)
                return output.getvalue(), "image/jpeg"
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            fail(415, "This image is damaged or unsupported.")
    if kind in {"audio", "video"}:
        if declared.split(";")[0] not in {
            "audio/webm",
            "video/webm",
            "audio/wav",
            "audio/x-wav",
            "audio/mpeg",
            "audio/ogg",
            "audio/mp4",
            "video/mp4",
            "audio/flac",
            "audio/aac",
        }:
            fail(415, "Use a supported audio or video format.")
        probe = media_probe(content)
        streams = probe.get("streams", [])
        if not any(s.get("codec_type") == ("audio" if kind == "audio" else "video") for s in streams):
            fail(415, "The file does not contain the expected media.")
        return content, declared.split(";")[0]
    if kind == "document":
        if not content.startswith(b"%PDF-"):
            fail(415, "Supporting documents must be PDF files.")
        scanner = get_settings().malware_scanner
        if not scanner:
            fail(
                503,
                "Document uploads require the configured malware scanner. Photo and audio evidence are available.",
            )
        with tempfile.NamedTemporaryFile(suffix=".pdf") as document:
            document.write(content)
            document.flush()
            try:
                subprocess.run(
                    [scanner, "--no-summary", document.name], capture_output=True, timeout=45, check=True
                )
            except (subprocess.SubprocessError, FileNotFoundError):
                fail(422, "This document did not pass the file safety check.")
        return content, "application/pdf"
    fail(422, "Unknown evidence type.")


def store_asset(
    db: Session,
    user: User,
    content: bytes,
    name: str,
    mime: str,
    kind: str,
    department_id: str | None,
    consent: bool,
):
    retention = policy_value(db, user.organization_id, "privacy").get(
        "audio_retention_days" if kind == "audio" else "evidence_retention_days",
        30 if kind == "audio" else 365,
    )
    key = f"{user.organization_id}/{new_id()}"
    put_bytes(key, content, mime)
    item = FileAsset(
        organization_id=user.organization_id,
        owner_id=user.id,
        department_id=department_id,
        name=Path(name).name[:200] or "evidence",
        storage_key=key,
        mime_type=mime,
        kind=kind,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        consent=consent,
        retention_until=now() + timedelta(days=retention),
    )
    db.add(item)
    try:
        db.flush()
    except Exception:
        # A failed insert must not leave private audio/evidence unreferenced.
        delete_bytes(item)
        raise
    return item


def wav_for_transcription(content: bytes):
    with tempfile.TemporaryDirectory() as directory:
        source, target = Path(directory) / "source", Path(directory) / "recording.wav"
        source.write_bytes(content)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(source),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-t",
                    "31",
                    str(target),
                ],
                capture_output=True,
                timeout=30,
                check=True,
            )
            converted = target.read_bytes()
        except (subprocess.SubprocessError, FileNotFoundError):
            raise ValueError("The recording could not be converted. Your draft is safe; retry or use text.")
    import io
    import wave

    with wave.open(io.BytesIO(converted)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    if duration > 30:
        raise ValueError(
            "Speech transcription accepts recordings up to 30 seconds. Use a shorter recording or text."
        )
    return converted
