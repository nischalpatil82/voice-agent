"""
core/voice.py — Microphone input using Whisper-first transcription.
Falls back to Google Speech Recognition when Whisper is unavailable.
"""

import logging
import os
import tempfile

_RECOGNIZER = None
_MICROPHONE = None
_WHISPER_MODEL = None

LOG = logging.getLogger(__name__)


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _dedupe_terms(terms, limit=None):
    seen = set()
    unique = []
    for term in terms:
        cleaned = " ".join(str(term or "").split()).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
        if limit and len(unique) >= limit:
            break
    return unique


def build_voice_guidance(config, items):
    """Build hotwords and an initial prompt from project config and catalog items."""
    terms = list(getattr(config, "VOICE_HINT_TERMS", []))
    product_limit = getattr(config, "VOICE_HINT_PRODUCT_LIMIT", 8)

    for item in items[:product_limit]:
        terms.append(item.get("name"))
        terms.extend(item.get("keywords", [])[:2])

    unique_terms = _dedupe_terms(terms, getattr(config, "VOICE_HOTWORD_LIMIT", 24))

    prompt = getattr(config, "VOICE_INITIAL_PROMPT", "").strip()
    prompt_limit = getattr(config, "VOICE_PROMPT_TERM_LIMIT", 10)
    prompt_terms = ", ".join(unique_terms[:prompt_limit])
    if prompt_terms:
        prompt = f"{prompt} Key terms: {prompt_terms}." if prompt else f"Key terms: {prompt_terms}."

    return unique_terms, prompt or None


def _get_voice_stack(sr):
    global _RECOGNIZER, _MICROPHONE
    if _RECOGNIZER is None:
        _RECOGNIZER = sr.Recognizer()
        _RECOGNIZER.dynamic_energy_threshold = True
        _RECOGNIZER.pause_threshold = float(os.getenv("VOICE_AGENT_PAUSE_THRESHOLD", "0.55"))
    if _MICROPHONE is None:
        _MICROPHONE = sr.Microphone()
    return _RECOGNIZER, _MICROPHONE


def _normalize_language(language):
    value = str(language or "en-US").strip()
    if not value:
        return "en"
    return value.split("-")[0].lower()


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    from faster_whisper import WhisperModel

    model_name = os.getenv("VOICE_WHISPER_MODEL", "small")
    compute_type = os.getenv("VOICE_WHISPER_COMPUTE", "int8")
    device = os.getenv("VOICE_WHISPER_DEVICE", "cpu")
    LOG.info("[Voice] Loading Whisper model=%s device=%s compute=%s", model_name, device, compute_type)
    _WHISPER_MODEL = WhisperModel(model_name, device=device, compute_type=compute_type)
    return _WHISPER_MODEL


def _format_hotwords(hotwords):
    if not hotwords:
        return None
    if isinstance(hotwords, str):
        return hotwords.strip() or None
    if isinstance(hotwords, (list, tuple, set)):
        return ", ".join(_dedupe_terms(hotwords)) or None
    return str(hotwords).strip() or None


def _transcribe_with_whisper(audio, language, initial_prompt=None, hotwords=None):
    try:
        model = _get_whisper_model()
    except Exception as exc:
        LOG.debug("[Voice] Whisper unavailable: %s", exc)
        return None

    wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(wav_bytes)

        segments, _info = model.transcribe(
            tmp_path,
            language=_normalize_language(language),
            task="transcribe",
            vad_filter=True,
            beam_size=_env_int("VOICE_AGENT_VOICE_BEAM_SIZE", 2),
            best_of=_env_int("VOICE_AGENT_VOICE_BEST_OF", 2),
            patience=_env_float("VOICE_AGENT_VOICE_PATIENCE", 1.0),
            temperature=_env_float("VOICE_AGENT_VOICE_TEMPERATURE", 0.0),
            no_speech_threshold=_env_float("VOICE_AGENT_VOICE_NO_SPEECH_THRESHOLD", 0.45),
            log_prob_threshold=_env_float("VOICE_AGENT_VOICE_LOG_PROB_THRESHOLD", -1.2),
            condition_on_previous_text=False,
            initial_prompt=initial_prompt,
            hotwords=_format_hotwords(hotwords),
            vad_parameters={
                "min_silence_duration_ms": _env_int("VOICE_AGENT_VAD_MIN_SILENCE_MS", 180),
                "speech_pad_ms": _env_int("VOICE_AGENT_VAD_SPEECH_PAD_MS", 180),
            },
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        return text or None
    except Exception as exc:
        LOG.debug("[Voice] Whisper transcription failed: %s", exc)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

def listen(language="en-US", initial_prompt=None, hotwords=None):
    try:
        import speech_recognition as sr
    except ImportError:
        print("  [Voice] speechrecognition not installed. Run: pip install speechrecognition pyaudio")
        return None

    r, mic = _get_voice_stack(sr)
    with mic as source:
        print(f"  Listening... (language: {language})")
        ambient_seconds = _env_float("VOICE_AGENT_AMBIENT_NOISE_SECONDS", 0.5)
        if ambient_seconds > 0:
          r.adjust_for_ambient_noise(source, duration=ambient_seconds)
        try:
            audio = r.listen(
                source,
                timeout=_env_float("VOICE_AGENT_LISTEN_TIMEOUT_SECONDS", 6.0),
                phrase_time_limit=_env_float("VOICE_AGENT_PHRASE_TIME_LIMIT_SECONDS", 10.0),
            )
            text = _transcribe_with_whisper(audio, language, initial_prompt=initial_prompt, hotwords=hotwords)
            if text:
                print(f'  You said: "{text}"')
                return text

            text = r.recognize_google(audio, language=language)
            print(f'  You said: "{text}"')
            return text
        except sr.WaitTimeoutError:
            print("  No speech detected.")
        except sr.UnknownValueError:
            print("  Could not understand audio.")
        except sr.RequestError as e:
            print(f"  Speech API error: {e}")
        except Exception as e:
            print(f"  Voice error: {e}")
    return None
