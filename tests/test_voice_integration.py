"""Tests for JARVIS voice integration (voice tools + web endpoints).

Covers:
  - VoiceEngine state machine and interrupts
  - /api/voice state, speak, listen, interrupt HTTP endpoints
  - SSE voice_state broadcasting wiring
"""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import speech_recognition as _sr

from ultron.tools.voice import (
    GetVoiceState,
    Listen,
    Speak,
    VoiceEngine,
    VoiceState,
    get_voice_engine,
)
from ultron.web import EventBroadcaster, JarvisAPI

_UnknownValueError = _sr.UnknownValueError


def _fresh_engine():
    """Return a standalone VoiceEngine with no global state."""
    return VoiceEngine()


@pytest.fixture(autouse=True)
def _reset_global_engine():
    """Reset the module-level voice engine singleton before each test."""
    import ultron.tools.voice as voice_mod
    old = voice_mod._voice_engine
    voice_mod._voice_engine = None
    yield
    voice_mod._voice_engine = old


# ═══════════════════════════════════════════════════════════════════
# VoiceEngine state machine
# ═══════════════════════════════════════════════════════════════════

class TestVoiceEngineStateMachine:
    def test_starts_idle(self):
        engine = _fresh_engine()
        assert engine.state == VoiceState.IDLE

    def test_state_callback_fires_on_change(self):
        engine = _fresh_engine()
        seen = []
        engine.set_state_callback(lambda s: seen.append(s))
        engine._set_state(VoiceState.LISTENING)
        engine._set_state(VoiceState.SPEAKING)
        engine._set_state(VoiceState.IDLE)
        assert seen == [VoiceState.LISTENING, VoiceState.SPEAKING, VoiceState.IDLE]

    def test_subclass_enum_values(self):
        assert VoiceState.LISTENING.value == "listening"
        assert VoiceState.SPEAKING.value == "speaking"
        assert VoiceState.ERROR.value == "error"
        assert VoiceState.IDLE.value == "idle"

    def test_interrupt_returns_to_idle(self):
        engine = _fresh_engine()
        seen = []
        engine.set_state_callback(lambda s: seen.append(s))
        engine._set_state(VoiceState.SPEAKING)
        assert engine.state == VoiceState.SPEAKING
        engine.interrupt()
        assert engine.state == VoiceState.IDLE
        assert VoiceState.IDLE in seen


# ═══════════════════════════════════════════════════════════════════
# VoiceEngine.listen with mocked speech_recognition
# ═══════════════════════════════════════════════════════════════════

class TestVoiceEngineListen:
    def test_listen_success(self):
        engine = _fresh_engine()
        fake_audio = object()

        class FakeRecognizer:
            def adjust_for_ambient_noise(self, source, duration=0.3):
                pass

            def listen(self, source, timeout=10, phrase_time_limit=10):
                return fake_audio

            def recognize_google(self, audio):
                assert audio is fake_audio
                return "hello jarvis"

        fake_mic_ctx = MagicMock()

        with patch("speech_recognition.Recognizer", return_value=FakeRecognizer()) as mock_rec, \
             patch("speech_recognition.Microphone") as mock_mic:
            mock_mic.return_value.__enter__.return_value = fake_mic_ctx
            result = engine.listen(timeout=5)

        assert result["success"] is True
        assert result["text"] == "hello jarvis"
        assert result["engine"] == "google"

    def test_listen_missing_microphone(self):
        engine = _fresh_engine()

        with patch("speech_recognition.Recognizer", return_value=MagicMock(listen=MagicMock(side_effect=OSError("no mic")))):
            result = engine.listen(timeout=5)

        assert result["success"] is False
        assert "microphone" in result.get("error", "").lower()
        assert engine.state == VoiceState.ERROR

    def test_listen_falls_back_to_processing_state(self):
        engine = _fresh_engine()
        states = []
        engine.set_state_callback(lambda s: states.append(s))

        class FakeRecognizer:
            def adjust_for_ambient_noise(self, source, duration=0.3):
                pass

            def listen(self, source, timeout=10, phrase_time_limit=10):
                return "audio"

            def recognize_google(self, audio):
                raise _UnknownValueError()

            def recognize_sphinx(self, audio):
                raise Exception("no sphinx")

        with patch("speech_recognition.Recognizer", return_value=FakeRecognizer()) as mock_rec, \
             patch("speech_recognition.Microphone") as mock_mic:
            mock_mic.return_value.__enter__.return_value = MagicMock()
            result = engine.listen(timeout=5)

        assert result["success"] is False
        assert engine.state == VoiceState.IDLE
        assert VoiceState.LISTENING in states
        assert VoiceState.PROCESSING in states


# ═══════════════════════════════════════════════════════════════════
# VoiceEngine.speak with mocked audio playback
# ═══════════════════════════════════════════════════════════════════

class TestVoiceEngineSpeak:
    def test_speak_uses_google_tts_when_key_present(self):
        engine = _fresh_engine()
        with patch.object(engine, "_speak_google_tts", return_value={"spoken": True, "engine": "google_tts"}) as mock_google, \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = engine.speak("hello")
        mock_google.assert_called_once_with("hello", "test-key")
        assert result["spoken"] is True

    def test_speak_marks_error_on_failure(self):
        engine = _fresh_engine()

        with patch.object(engine, "_speak_google_tts", return_value={"spoken": False, "error": "fail"}) as mock_google, \
             patch.object(engine, "_speak_elevenlabs", return_value={"spoken": False, "error": "fail"}) as mock_el, \
             patch.object(engine, "_init_tts", return_value=False) as mock_init, \
             patch.object(engine, "_speak_sapi", return_value={"spoken": True, "engine": "sapi"}) as mock_sapi:
            result = engine.speak("hello")

        mock_sapi.assert_called_once()
        assert result["spoken"] is True

    def test_interrupt_stops_playback(self):
        engine = _fresh_engine()
        engine._interrupt_event.set()
        assert engine._play_audio("dummy.wav") is False


# ═══════════════════════════════════════════════════════════════════
# Voice tools
# ═══════════════════════════════════════════════════════════════════

class TestVoiceTools:
    def test_speak_tool_runs_engine(self):
        with patch("ultron.tools.voice.get_voice_engine") as mock_getter:
            engine = MagicMock()
            engine.speak.return_value = {"spoken": True}
            mock_getter.return_value = engine
            result = Speak().run(text="hello")
        assert result["spoken"] is True

    def test_listen_tool_runs_engine(self):
        with patch("ultron.tools.voice.get_voice_engine") as mock_getter:
            engine = MagicMock()
            engine.listen.return_value = {"success": True, "text": "hi"}
            mock_getter.return_value = engine
            result = Listen().run(timeout=3)
        assert result["success"] is True

    def test_get_voice_state_tool(self):
        with patch("ultron.tools.voice.get_voice_engine") as mock_getter:
            engine = MagicMock()
            engine.state.value = "idle"
            mock_getter.return_value = engine
            result = GetVoiceState().run()
        assert result["state"] == "idle"

    def test_global_engine_is_singleton(self):
        with patch("ultron.tools.voice._voice_engine", None):
            assert get_voice_engine() is get_voice_engine()


# ═══════════════════════════════════════════════════════════════════
# HTTP endpoints
# ═══════════════════════════════════════════════════════════════════

def _start_server(port: int = 0) -> JarvisAPI:
    server = JarvisAPI(host="127.0.0.1", port=port)
    server._start_time = time.time()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    return server


def _get_port(server: JarvisAPI) -> int:
    return server.server_address[1]


class TestVoiceHTTPEndpoints:
    def test_get_voice_state_endpoint(self):
        import httpx
        with patch("ultron.tools.voice.get_voice_engine") as mock_getter:
            engine = MagicMock()
            engine.state.value = "idle"
            mock_getter.return_value = engine

            server = _start_server()
            try:
                r = httpx.get(f"http://127.0.0.1:{_get_port(server)}/api/voice")
                assert r.status_code == 200
                data = r.json()
                assert data["state"] == "idle"
                assert data["available"] is True
            finally:
                server.shutdown()

    def test_speak_endpoint(self):
        import httpx
        with patch("ultron.tools.voice.get_voice_engine") as mock_getter:
            engine = MagicMock()
            engine.speak.return_value = {"spoken": True, "text": "hello", "engine": "test"}
            mock_getter.return_value = engine

            server = _start_server()
            try:
                r = httpx.post(
                    f"http://127.0.0.1:{_get_port(server)}/api/voice/speak",
                    json={"text": "hello"},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["spoken"] is True
                engine.speak.assert_called_once_with("hello")
            finally:
                server.shutdown()

    def test_speak_endpoint_requires_text(self):
        import httpx
        server = _start_server()
        try:
            r = httpx.post(f"http://127.0.0.1:{_get_port(server)}/api/voice/speak", json={})
            assert r.status_code == 400
        finally:
            server.shutdown()

    def test_listen_endpoint(self):
        import httpx
        with patch("ultron.tools.voice.get_voice_engine") as mock_getter:
            engine = MagicMock()
            engine.listen.return_value = {"success": True, "text": "hello jarvis"}
            mock_getter.return_value = engine

            server = _start_server()
            try:
                r = httpx.post(
                    f"http://127.0.0.1:{_get_port(server)}/api/voice/listen",
                    json={"timeout": 5},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["success"] is True
                assert data["text"] == "hello jarvis"
                engine.listen.assert_called_once_with(timeout=5)
            finally:
                server.shutdown()

    def test_interrupt_endpoint(self):
        import httpx
        with patch("ultron.tools.voice.get_voice_engine") as mock_getter:
            engine = MagicMock()
            engine.state.value = "idle"
            mock_getter.return_value = engine

            server = _start_server()
            try:
                r = httpx.post(f"http://127.0.0.1:{_get_port(server)}/api/voice/interrupt", json={})
                assert r.status_code == 200
                data = r.json()
                assert data["interrupted"] is True
                engine.interrupt.assert_called_once()
            finally:
                server.shutdown()


# ═══════════════════════════════════════════════════════════════════
# SSE voice_state broadcasting
# ═══════════════════════════════════════════════════════════════════

class TestVoiceSSEBroadcast:
    def test_voice_state_endpoint_wires_broadcast(self):
        """Getting voice state should wire the engine state callback to SSE."""
        from ultron.tools.voice import get_voice_engine

        server = JarvisAPI(port=0)
        server._start_time = time.time()
        q = server.subscribe_events()
        try:
            server._wire_voice_broadcast()
            engine = get_voice_engine()
            engine._set_state(VoiceState.LISTENING)
            msg = q.get(timeout=2)
            assert "voice_state" in msg
            assert '"state": "listening"' in msg
        finally:
            engine = get_voice_engine()
            engine.set_state_callback(None)
            server.server_close()

    def test_broadcast_does_not_double_wire(self):
        """Calling _wire_voice_broadcast twice must not reset the callback."""
        from ultron.tools.voice import get_voice_engine

        server = JarvisAPI(port=0)
        q = server.subscribe_events()
        try:
            server._wire_voice_broadcast()
            callback = get_voice_engine()._on_state_change
            server._wire_voice_broadcast()
            assert get_voice_engine()._on_state_change is callback
        finally:
            get_voice_engine().set_state_callback(None)
            server.server_close()