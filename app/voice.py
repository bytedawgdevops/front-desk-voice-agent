"""
ElevenLabs text-to-speech with disk cache.

Returns a cache-relative URL path to the audio file, or None on any failure.
The caller is responsible for serving the cache directory as static files.
"""

import hashlib
import logging
import pathlib

import httpx

from app.config import (
    AUDIO_CACHE_DIR,
    ELEVENLABS_API_KEY,
    ELEVENLABS_MODEL,
    ELEVENLABS_VOICE_ID,
)

logger = logging.getLogger(__name__)

_ELEVENLABS_URL = 'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
_TIMEOUT = 2.0


def _cache_path(text: str) -> pathlib.Path:
    digest = hashlib.sha256(text.encode()).hexdigest()
    directory = pathlib.Path(AUDIO_CACHE_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f'{digest}.mp3'


def speak(text: str) -> str | None:
    """
    Convert text to speech via ElevenLabs and return a URL path to the audio.

    The audio is cached on disk keyed by SHA-256 of the text, so repeated
    phrases (greetings, common replies) are served from disk without hitting
    the API again.

    Returns None on any failure — missing config, network error, bad status,
    or timeout — so the caller can fall back to browser speechSynthesis.
    """
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        return None

    cached = _cache_path(text)
    if cached.exists():
        return f'/audio/{cached.name}'

    url = _ELEVENLABS_URL.format(voice_id=ELEVENLABS_VOICE_ID)
    headers = {
        'xi-api-key':   ELEVENLABS_API_KEY,
        'Content-Type': 'application/json',
        'Accept':       'audio/mpeg',
    }
    payload = {
        'text':       text,
        'model_id':   ELEVENLABS_MODEL,
        'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75},
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        cached.write_bytes(response.content)
        return f'/audio/{cached.name}'
    # Any ElevenLabs failure falls back to browser speech; never break a call.
    except Exception as exc:  # noqa: BLE001
        logger.warning('ElevenLabs failed: %s', exc)
        return None
