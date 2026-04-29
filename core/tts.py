"""
core/tts.py — Text-to-speech helpers for CLI playback and server audio responses.
Uses edge-tts for high-quality neural voice synthesis.
"""

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
import subprocess

import edge_tts

LOG = logging.getLogger(__name__)


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalize_tts_text(text: str) -> str:
    """Convert response text into something that reads naturally through TTS."""
    msg = str(text or "")
    replacements = {
        "₹": "rupees ",
        "Rs.": "rupees ",
        "Rs ": "rupees ",
        "Rs": "rupees ",
        "&": " and ",
        "→": " to ",
        "🛒": " cart ",
        "✅": " ok ",
        "😊": "",
        "👋": " goodbye ",
        "💎": "",
        "🌙": "",
        "☀️": "",
    }
    for old, new in replacements.items():
        msg = msg.replace(old, new)

    msg = re.sub(r"\b([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\b", lambda m: m.group(1).replace(",", ""), msg)
    msg = re.sub(r"\s+", " ", msg)
    return msg.strip()


def _get_voice(voice_hint: str | None = None) -> str:
    """Determine best edge-tts voice based on hint and defaults."""
    hint = str(voice_hint or os.getenv("VOICE_AGENT_TTS_VOICE_HINT", "")).strip().lower()
    
    if "us" in hint or "aria" in hint or "american" in hint:
        return "en-US-AriaNeural"
    if "uk" in hint or "british" in hint or "sonia" in hint:
        return "en-GB-SoniaNeural"
    if "prabhat" in hint or "male" in hint:
        return "en-IN-PrabhatNeural"
        
    # Default to Indian English Female
    return "en-IN-NeerjaNeural"


def speak(text: str, voice_hint: str | None = None, wait: bool = True) -> None:
    """Speak text out loud on the local machine (for debugging/CLI)."""
    if not _env_bool("VOICE_AGENT_SPEAK", True):
        return

    msg = normalize_tts_text(text)
    if not msg:
        return

    voice = _get_voice(voice_hint)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        async def _save():
            communicate = edge_tts.Communicate(msg, voice)
            await communicate.save(tmp_path)

        asyncio.run(_save())
        
        # Play the audio on Windows
        if os.name == 'nt':
            # Use PowerShell to seamlessly play MP3 without opening a media player window
            play_script = f'(New-Object Media.SoundPlayer "{tmp_path}").PlaySync()'
            subprocess.run(["powershell", "-c", play_script], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            # Mac/Linux fallback
            subprocess.run(["afplay" if sys.platform == "darwin" else "aplay", tmp_path])

    except Exception as exc:
        LOG.error(f"[TTS] Speak failed: {exc}", exc_info=True)
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


def synthesize_audio_bytes(text: str, voice_hint: str | None = None) -> bytes:
    """Synthesize text into MP3 bytes for HTTP responses."""
    msg = normalize_tts_text(text)
    if not msg:
        return b""

    voice = _get_voice(voice_hint)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        async def _save():
            communicate = edge_tts.Communicate(msg, voice)
            await communicate.save(tmp_path)

        asyncio.run(_save())
        return Path(tmp_path).read_bytes()
    except Exception as exc:
        LOG.error(f"[TTS] Synthesize failed: {exc}", exc_info=True)
        return b""
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass