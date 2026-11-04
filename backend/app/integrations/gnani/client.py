import httpx

from ...config import get_settings


class ProviderUnavailable(ValueError):
    pass


def transcribe(audio: bytes, language: str, request_id: str):
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
                data={"model": settings.gnani_stt_model, "language_code": language, "format": "codemix"},
            )
            response.raise_for_status()
            data = response.json()
        if (
            not isinstance(data, dict)
            or data.get("success") is not True
            or not isinstance(data.get("transcript"), str)
            or not data["transcript"].strip()
        ):
            raise ValueError()
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


def speak(text: str):
    settings = get_settings()
    if not settings.gnani_api_key:
        raise ProviderUnavailable("Handover audio is not configured. The written handover remains available.")
    try:
        with httpx.Client(timeout=55) as client:
            response = client.post(
                "https://api.vachana.ai/api/v1/tts/inference",
                headers={"X-API-Key-ID": settings.gnani_api_key},
                json={
                    "text": text[:5000],
                    "model": settings.gnani_tts_model,
                    "audio_config": {
                        "encoding": "linear_pcm",
                        "container": "wav",
                        "num_channels": 1,
                        "sample_rate": 48000,
                        "sample_width": 2,
                    },
                },
            )
            response.raise_for_status()
        # The documented endpoint returns full audio. Reject undocumented response shapes.
        if response.content[:4] != b"RIFF" or response.content[8:12] != b"WAVE":
            raise ValueError()
        return response.content
    except (httpx.HTTPError, ValueError):
        raise ProviderUnavailable(
            "Handover audio is unavailable or the provider response needs verification. Use the written handover."
        ) from None
