"""Voice Engine for JARVIS — cross-platform speech recognition and TTS.

Supports:
  - Windows: pyttsx3 / Windows SAPI / Google TTS / ElevenLabs
  - Linux/Android: espeak / pico2wave / Google TTS / ElevenLabs
  - Browser-based: Web Speech API (via frontend)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
from enum import Enum
from typing import Any, Callable, Dict, Optional

from ultron.platform import is_windows, is_posix
from ultron.tools.base import Tool

logger = logging.getLogger("ultron.tools.voice")


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class VoiceEngine:
    """Voice engine for speech recognition and text-to-speech."""

    def __init__(self) -> None:
        self._state = VoiceState.IDLE
        self._tts_engine = None
        self._lock = threading.Lock()
        self._on_state_change: Optional[Callable[[VoiceState], None]] = None
        self._interrupt_event = threading.Event()
        self._active_playback: Optional[subprocess.Popen] = None

    @property
    def state(self) -> VoiceState:
        return self._state

    def set_state_callback(self, callback: Callable[[VoiceState], None]) -> None:
        self._on_state_change = callback

    def _set_state(self, state: VoiceState) -> None:
        with self._lock:
            self._state = state
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception:
                pass

    def interrupt(self) -> None:
        self._interrupt_event.set()
        with self._lock:
            self._state = VoiceState.IDLE
        if self._on_state_change:
            try:
                self._on_state_change(VoiceState.IDLE)
            except Exception:
                pass

    def _clear_interrupt(self) -> None:
        self._interrupt_event.clear()

    def speak(self, text: str) -> Dict[str, Any]:
        """Speak text aloud — tries platform-appropriate TTS engines."""
        self._clear_interrupt()
        self._set_state(VoiceState.SPEAKING)
        try:
            from ultron.config import load_dotenv
            dotenv = load_dotenv()

            # 1. Try Google AI Studio TTS (free, high quality, cross-platform)
            google_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not google_key:
                google_key = dotenv.get("GEMINI_API_KEY", "").strip()
            if google_key:
                result = self._speak_google_tts(text, google_key)
                if result.get("spoken"):
                    self._set_state(VoiceState.IDLE)
                    return result

            # 2. Try ElevenLabs (requires paid plan for library voices)
            eleven_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
            if not eleven_key:
                eleven_key = dotenv.get("ELEVENLABS_API_KEY", "").strip()
            if eleven_key:
                result = self._speak_elevenlabs(text, eleven_key)
                if result.get("spoken"):
                    self._set_state(VoiceState.IDLE)
                    return result

            # 3. Platform-specific local TTS
            if is_windows():
                return self._speak_windows_local(text)
            return self._speak_posix_local(text)
        except Exception as e:
            self._set_state(VoiceState.ERROR)
            return {"error": str(e), "spoken": False}

    def _init_tts(self) -> bool:
        """Initialize the pyttsx3 TTS engine. Returns True on success."""
        try:
            import pyttsx3
            if self._tts_engine is None:
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty('rate', 175)
                self._tts_engine.setProperty('volume', 1.0)
            return True
        except ImportError:
            self._tts_engine = None
            return False
        except Exception as e:
            logger.warning("TTS init failed: %s", e)
            self._tts_engine = None
            return False

    def _speak_windows_local(self, text: str) -> Dict[str, Any]:
        """Windows local TTS: pyttsx3 then SAPI fallback."""
        # Try pyttsx3
        if self._init_tts():
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
                self._set_state(VoiceState.IDLE)
                return {"spoken": True, "text": text, "engine": "pyttsx3"}
            except Exception as e:
                logger.warning("pyttsx3 failed: %s", e)
                self._tts_engine = None

        # Windows SAPI fallback
        return self._speak_sapi(text)

    def _speak_sapi(self, text: str) -> Dict[str, Any]:
        """Fallback TTS using Windows SAPI via PowerShell."""
        try:
            escaped = text.replace("'", "''")
            script = (
                f"$voice = New-Object -ComObject SAPI.SpVoice; "
                f"$voice.Speak('{escaped}')"
            )
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            self._active_playback = proc
            while proc.poll() is None:
                if self._interrupt_event.is_set():
                    proc.kill()
                    self._active_playback = None
                    self._set_state(VoiceState.IDLE)
                    return {"spoken": False, "interrupted": True}
                try:
                    proc.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    continue
            self._active_playback = None
            self._set_state(VoiceState.IDLE)
            return {"spoken": True, "text": text, "engine": "windows_sapi"}
        except Exception as e:
            self._active_playback = None
            self._set_state(VoiceState.ERROR)
            return {"error": str(e), "spoken": False}

    def _speak_posix_local(self, text: str) -> Dict[str, Any]:
        """Linux/Android local TTS: espeak, pico2wave, or termux-tts-speak."""
        engines = [
            (["termux-tts-speak", text], "termux_tts"),
            (["espeak", text], "espeak"),
            (["pico2wave", "-w", "/tmp/tts_out.wav", text], "pico2wave"),
            (["festival", "--tts"], "festival"),
        ]

        for cmd, engine_name in engines:
            try:
                if engine_name == "pico2wave":
                    # pico2wave writes to a file, then we play it
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=10,
                    )
                    if result.returncode == 0 and os.path.exists("/tmp/tts_out.wav"):
                        self._play_audio_posix("/tmp/tts_out.wav")
                        os.unlink("/tmp/tts_out.wav")
                        self._set_state(VoiceState.IDLE)
                        return {"spoken": True, "text": text, "engine": engine_name}
                elif engine_name == "festival":
                    proc = subprocess.Popen(
                        cmd, stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    proc.communicate(input=text.encode(), timeout=10)
                    self._set_state(VoiceState.IDLE)
                    return {"spoken": True, "text": text, "engine": engine_name}
                else:
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    self._active_playback = proc
                    while proc.poll() is None:
                        if self._interrupt_event.is_set():
                            proc.kill()
                            self._active_playback = None
                            self._set_state(VoiceState.IDLE)
                            return {"spoken": False, "interrupted": True}
                        try:
                            proc.wait(timeout=0.1)
                        except subprocess.TimeoutExpired:
                            continue
                    self._active_playback = None
                    self._set_state(VoiceState.IDLE)
                    return {"spoken": True, "text": text, "engine": engine_name}
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug("%s failed: %s", engine_name, e)
                continue

        self._set_state(VoiceState.IDLE)
        return {"spoken": False, "error": "No TTS engine available. Install espeak or termux-api."}

    def _play_audio_posix(self, path: str) -> None:
        """Play audio file on Linux/Android."""
        for cmd in [["termux-media-player", "play", path],
                     ["mpv", "--no-video", path],
                     ["aplay", path],
                     ["ffplay", "-nodisp", "-autoexit", path]]:
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._active_playback = proc
                while proc.poll() is None:
                    if self._interrupt_event.is_set():
                        proc.kill()
                        self._active_playback = None
                        return
                    try:
                        proc.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        continue
                self._active_playback = None
                return
            except FileNotFoundError:
                continue

    def _play_audio(self, tmp_path: str, interrupt_check: Optional[Callable[[], bool]] = None) -> bool:
        """Play audio via Windows MediaPlayer with optional interrupt support."""
        if not is_windows():
            self._play_audio_posix(tmp_path)
            return not self._interrupt_event.is_set()

        escaped = tmp_path.replace("'", "''")
        script = (
            f"$player = New-Object System.Media.MediaPlayer; "
            f"$player.uri = [Uri]::new('{escaped}'); "
            f"$player.Play(); "
            f"Start-Sleep -Milliseconds 500; "
            f"$deadline = (Get-Date).AddMinutes(5); "
            f"while ($player.Position -lt $player.NaturalDuration.TimeSpan -and (Get-Date) -lt $deadline) "
            f"{{ Start-Sleep -Milliseconds 200 }}; "
            f"$player.Close()"
        )
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            self._active_playback = proc
            while proc.poll() is None:
                if self._interrupt_event.is_set():
                    proc.kill()
                    with self._lock:
                        self._state = VoiceState.IDLE
                    self._active_playback = None
                    return False
                try:
                    proc.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    continue
            self._active_playback = None
            return True
        except Exception as e:
            self._active_playback = None
            logger.warning("MediaPlayer playback failed: %s", e)
            return False

    def _speak_google_tts(self, text: str, api_key: str) -> Dict[str, Any]:
        """Text-to-speech via Google AI Studio Gemini TTS (free tier)."""
        try:
            import httpx

            model = os.environ.get("GOOGLE_TTS_MODEL", "gemini-2.5-flash-preview-tts")
            voice = os.environ.get("GOOGLE_TTS_VOICE", "Kore")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            headers = {"Content-Type": "application/json"}
            params = {"key": api_key}

            styled_text = f"Say in a calm, professional, British-accented tone: {text}"

            payload = {
                "contents": [{"parts": [{"text": styled_text}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": voice}
                        }
                    },
                },
            }

            response = httpx.post(url, json=payload, headers=headers, params=params, timeout=30.0)
            if response.status_code != 200:
                return {"spoken": False, "error": f"Google TTS error {response.status_code}"}

            data = response.json()
            audio_data = None
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        import base64
                        audio_data = base64.b64decode(part["inlineData"]["data"])
                        break

            if not audio_data:
                return {"spoken": False, "error": "No audio data in Google TTS response"}

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                tmp_path = f.name

            if not self._play_audio(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return {"spoken": False, "interrupted": True}

            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            return {"spoken": True, "text": text, "engine": "google_tts", "voice": voice}
        except ImportError:
            return {"spoken": False, "error": "httpx not installed for Google TTS"}
        except Exception as e:
            logger.warning("Google TTS failed: %s", e)
            return {"spoken": False, "error": str(e)}

    def _speak_elevenlabs(self, text: str, api_key: str) -> Dict[str, Any]:
        """Text-to-speech via ElevenLabs API."""
        try:
            import httpx

            voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            model_id = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            }

            response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
            if response.status_code != 200:
                return {"spoken": False, "error": f"ElevenLabs API error {response.status_code}"}

            audio_data = response.content
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                tmp_path = f.name

            if not self._play_audio(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return {"spoken": False, "interrupted": True}

            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            return {"spoken": True, "text": text, "engine": "elevenlabs", "voice_id": voice_id}
        except ImportError:
            return {"spoken": False, "error": "httpx not installed for ElevenLabs"}
        except Exception as e:
            return {"spoken": False, "error": str(e)}

    def listen(self, timeout: int = 10) -> Dict[str, Any]:
        """Listen for speech and return recognized text."""
        self._set_state(VoiceState.LISTENING)
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()

            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                self._set_state(VoiceState.IDLE)
                return {"text": "", "success": False, "no_speech": True,
                        "error": "No speech detected — speak within the timeout and try again."}
            except OSError as e:
                self._set_state(VoiceState.ERROR)
                return {"text": "", "success": False, "error": f"No microphone available: {e}"}

            self._set_state(VoiceState.PROCESSING)

            try:
                text = recognizer.recognize_google(audio)
                self._set_state(VoiceState.IDLE)
                return {"text": text, "engine": "google", "success": True}
            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                self._set_state(VoiceState.IDLE)
                return {"text": "", "success": False,
                        "error": f"Speech recognition service unavailable: {e}"}

            self._set_state(VoiceState.IDLE)
            return {"text": "", "success": False,
                    "error": "Could not understand audio — try speaking clearly and closer to the microphone"}

        except ImportError as e:
            self._set_state(VoiceState.ERROR)
            return {"text": "", "success": False, "error": f"speech_recognition not installed: {e}"}
        except Exception as e:
            self._set_state(VoiceState.ERROR)
            return {"text": "", "success": False, "error": str(e) or "Unknown voice error"}


# Global voice engine instance
_voice_engine: Optional[VoiceEngine] = None


def get_voice_engine() -> VoiceEngine:
    global _voice_engine
    if _voice_engine is None:
        _voice_engine = VoiceEngine()
    return _voice_engine


class Speak(Tool):
    """Speak text aloud using TTS."""
    name = "speak"
    description = "Speak the given text aloud using text-to-speech."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to speak aloud."},
        },
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "spoken": {"type": "boolean"},
            "text": {"type": "string"},
            "engine": {"type": "string"},
        },
    }
    mutates = True

    def run(self, text: str, **_: Any) -> Dict[str, Any]:
        engine = get_voice_engine()
        return engine.speak(text)


class Listen(Tool):
    """Listen for voice input and return recognized text."""
    name = "listen"
    description = "Listen for voice input from the microphone and return the recognized text."
    parameters = {
        "type": "object",
        "properties": {
            "timeout": {"type": "integer", "description": "Max seconds to wait for speech.", "default": 10},
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "success": {"type": "boolean"},
            "engine": {"type": "string"},
        },
    }

    def run(self, timeout: int = 10, **_: Any) -> Dict[str, Any]:
        engine = get_voice_engine()
        return engine.listen(timeout=timeout)


class GetVoiceState(Tool):
    """Get current voice engine state."""
    name = "get_voice_state"
    description = "Get the current state of the voice engine (idle, listening, processing, speaking)."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "state": {"type": "string"},
        },
    }

    def run(self, **_: Any) -> Dict[str, Any]:
        engine = get_voice_engine()
        return {"state": engine.state.value}


__all__ = [
    "VoiceState",
    "VoiceEngine",
    "get_voice_engine",
    "Speak",
    "Listen",
    "GetVoiceState",
]
