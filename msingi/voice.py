"""CUE Assistance speech helpers (server-side only)."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def msingi_configured() -> bool:
    key = getattr(settings, "MSINGI_API_KEY", "") or ""
    if not isinstance(key, str):
        key = str(key)
    return bool(key.strip())


def synthesize_speech(text: str, *, voice_id: str | None = None) -> bytes | None:
    """
    POST /v1/audio/speech → WAV bytes.
    Keeps payloads short so TTS returns faster.
    """
    api_key = getattr(settings, "MSINGI_API_KEY", "") or ""
    if not isinstance(api_key, str):
        api_key = str(api_key)
    api_key = api_key.strip()
    if not api_key:
        return None
    base = (getattr(settings, "MSINGI_BASE_URL", "") or "https://api.msingiai.com").rstrip("/")
    voice = (voice_id or getattr(settings, "MSINGI_VOICE_ID", "female3") or "female3").strip()
    payload_text = (text or "").strip()
    if not payload_text:
        return None
    # Shorter text = much faster TTS for chat replies
    if len(payload_text) > 320:
        payload_text = payload_text[:317].rsplit(" ", 1)[0] + "…"

    try:
        resp = requests.post(
            f"{base}/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"text": payload_text, "voice_id": voice},
            timeout=12,
        )
        if not resp.ok:
            logger.warning("Msingi TTS HTTP %s: %s", resp.status_code, resp.text[:300])
            return None
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "audio" not in ctype and not resp.content.startswith(b"RIFF"):
            logger.warning("Msingi TTS unexpected content-type: %s", ctype)
            return None
        return resp.content
    except Exception:
        logger.exception("Msingi TTS request failed")
        return None
