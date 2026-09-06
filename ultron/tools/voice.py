"""Voice Engine for JARVIS — speech recognition and text-to-speech.

Provides:
  - Speech-to-text via system microphone (Windows Speech Recognition)
  - Text-to-speech via pyttsx3 or Windows SAPI
  - Voice state management
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

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
        self._speech_recognizer = None
        self._lock = threading.Lock()
        self._on_state_change: Optional[Callable[[VoiceState], None]] = None

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

    def _init_tts(self):
        """Initialize text-to-speech engine."""
        if self._tts_engine is not None:
            return True
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty('rate', 175)
            self._tts_engine.setProperty('volume', 1.0)
            voices = self._tts_engine.getProperty('voices')
            if voices:
                for v in voices:
                    if 'david' in v.name.lower() or 'male' in v.name.lower():
                        self._tts_engine.setProperty('voice', v.id)
                        break
            return True
        except ImportError:
            logger.warning("pyttsx3 not installed. Using Windows SAPI fallback.")
            return False
        except Exception as e:
            logger.warning("Failed to init pyttsx3: %s", e)
            return False

    def speak(self, text: str) -> Dict[str, Any]:
        """Speak text aloud."""
        self._set_state(VoiceState.SPEAKING)
        try:
            if self._init_tts() and self._tts_engine:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
                self._set_state(VoiceState.IDLE)
                return {"spoken": True, "text": text, "engine": "pyttsx3"}
            else:
                # Windows SAPI fallback
                return self._speak_sapi(text)
        except Exception as e:
            self._set_state(VoiceState.ERROR)
            return {"error": str(e), "spoken": False}

    def _speak_sapi(self, text: str) -> Dict[str, Any]:
        """Fallback TTS using Windows SAPI via PowerShell."""
        try:
            # Escape text for PowerShell
            escaped = text.replace("'", "''")
            script = (
                f"$voice = New-Object -ComObject SAPI.SpVoice; "
                f"$voice.Speak('{escaped}')"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                timeout=30,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._set_state(VoiceState.IDLE)
            return {"spoken": True, "text": text, "engine": "windows_sapi"}
        except Exception as e:
            self._set_state(VoiceState.ERROR)
            return {"error": str(e), "spoken": False}

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
            except OSError as e:
                self._set_state(VoiceState.ERROR)
                return {"text": "", "success": False, "error": f"No microphone available: {e}"}

            self._set_state(VoiceState.PROCESSING)

            # Try Google Speech Recognition first
            try:
                text = recognizer.recognize_google(audio)
                self._set_state(VoiceState.IDLE)
                return {"text": text, "engine": "google", "success": True}
            except sr.UnknownValueError:
                pass
            except sr.RequestError:
                pass

            # Fallback: try with Sphinx (offline, if available)
            try:
                text = recognizer.recognize_sphinx(audio)
                self._set_state(VoiceState.IDLE)
                return {"text": text, "engine": "sphinx", "success": True}
            except Exception:
                pass

            self._set_state(VoiceState.IDLE)
            return {"text": "", "success": False, "error": "Could not understand audio - try speaking more clearly"}

        except ImportError as e:
            self._set_state(VoiceState.ERROR)
            return {"text": "", "success": False, "error": f"speech_recognition not installed: {e}"}
        except Exception as e:
            self._set_state(VoiceState.ERROR)
            return {"text": "", "success": False, "error": str(e)}


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
