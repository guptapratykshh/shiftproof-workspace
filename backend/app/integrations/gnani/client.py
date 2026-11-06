import io
import json
import re
import time
import wave

import httpx

from ...config import get_settings


class ProviderUnavailable(ValueError):
    pass


def transcribe(audio: bytes, language: str, request_id: str, *, keyterms=None, topic=""):
    settings = get_settings()
    if not settings.gnani_api_key:
        raise ProviderUnavailable(
            "Speech transcription is not configured. Your recording is saved; you can type your update."
        )
    try:
        with httpx.Client(timeout=55) as client:
            response = client.post(
                "https://api.vachana.ai/stt/v3",
                headers={"X-API-Key-ID": settings.gnani_api_key, "X-API-Request-ID": request_id},
                files={"audio_file": ("recording.wav", audio, "audio/wav")},
                data={
                    "model": settings.gnani_stt_model,
                    "language_code": language,
                    "format": "codemix",
                    **({"keyterms": json.dumps(keyterms, ensure_ascii=False)} if keyterms else {}),
                    **({"topic": topic} if topic else {}),
                },
            )
            response.raise_for_status()
            data = response.json()
        if (
            not isinstance(data, dict)
            or data.get("success") is not True
            or not isinstance(data.get("transcript"), str)
        ):
            raise ValueError()
        if not data["transcript"].strip():
            return {"text": "", "language": language, "model": settings.gnani_stt_model, "metadata": {}}
        return {
            "text": data["transcript"][:20000],
            "language": data.get("detected_language_code", language),
            "model": data.get("model", settings.gnani_stt_model),
            "metadata": {
                key: data[key]
                for key in ("request_id", "processing_time", "end_to_end_latency")
                if key in data
            },
        }
    except (httpx.HTTPError, ValueError, TypeError):
        raise ProviderUnavailable(
            "Speech transcription is temporarily unavailable or returned an unreadable result. Retry or type your update."
        ) from None


def speech_chunks(text: str, limit: int = 650) -> list[str]:
    """Bound provider requests without dropping words or reordering the script."""
    chunks = []
    while len(text) > limit:
        boundaries = list(re.finditer(r"(?<=[.!?।])\s+|\n+", text[:limit]))
        end = boundaries[-1].end() if boundaries else 0
        if end < limit // 3:
            spaces = list(re.finditer(r"\s+", text[:limit]))
            end = spaces[-1].end() if spaces else limit
        chunks.append(text[:end])
        text = text[end:]
    if text:
        chunks.append(text)
    return chunks


def speak(text: str, language: str = "auto"):
    settings = get_settings()
    if not settings.gnani_api_key:
        raise ProviderUnavailable(
            "Spoken playback is not configured. You can still review the written update."
        )
    if not text.strip() or len(text) > 5000:
        raise ProviderUnavailable(
            "This update is too long for spoken playback. Review it in writing; no text was omitted."
        )
    try:
        deadline = time.monotonic() + 120
        output = io.BytesIO()
        expected_format = None
        with httpx.Client(timeout=55) as client, wave.open(output, "wb") as joined:
            # Sequential requests also suit accounts with a single active TTS slot.
            for chunk in speech_chunks(text):
                if not chunk.strip():
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError()
                response = client.post(
                    "https://api.vachana.ai/api/v1/tts/inference",
                    headers={"X-API-Key-ID": settings.gnani_api_key},
                    timeout=min(55, remaining),
                    json={
                        "text": chunk,
                        "model": settings.gnani_tts_model,
                        "voice": settings.gnani_tts_voice,
                        "language": language,
                        "speed": settings.gnani_tts_speed,
                        "audio_config": {
                            "encoding": "linear_pcm",
                            "container": "wav",
                            "num_channels": 1,
                            "sample_rate": 16000,
                            "sample_width": 2,
                        },
                    },
                )
                response.raise_for_status()
                with wave.open(io.BytesIO(response.content), "rb") as audio:
                    audio_format = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
                    if expected_format is None:
                        expected_format = audio_format
                        joined.setnchannels(audio_format[0])
                        joined.setsampwidth(audio_format[1])
                        joined.setframerate(audio_format[2])
                    if audio_format != expected_format or audio.getcomptype() != "NONE":
                        raise ValueError()
                    frames = audio.readframes(audio.getnframes())
                    frame_width = audio_format[0] * audio_format[1]
                    declared_bytes = audio.getnframes() * frame_width
                    # Gnani can return a complete HTTP body with a streaming WAV
                    # length sentinel. Rebuild its header from actual PCM bytes.
                    open_length = declared_bytes in {0xFFFFFFFF, 0xFFFFFFFE}
                    if (
                        not frames
                        or len(frames) % frame_width
                        or (not open_length and len(frames) != declared_bytes)
                    ):
                        raise ValueError()
                    joined.writeframes(frames)
                if time.monotonic() > deadline:
                    raise ValueError()
        return output.getvalue()
    except (httpx.HTTPError, ValueError, wave.Error, EOFError):
        raise ProviderUnavailable(
            "Spoken playback is temporarily unavailable. Your written update is safe; try again or review it in writing."
        ) from None
