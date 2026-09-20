package com.ultron.ai.core.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.Locale
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Module 9 — Text-to-speech.
 *
 * On-device TTS built on android.speech.tts. Reads the configured rate and
 * language from Settings; anything the assistant answers can be spoken aloud.
 */
class TextToSpeechManager(private val context: Context) {

    enum class TtsState { INITIALIZING, READY, UNAVAILABLE }

    private val _state = MutableStateFlow(TtsState.INITIALIZING)
    val state: StateFlow<TtsState> = _state.asStateFlow()

    private var tts: TextToSpeech? = null
    private var configuredLocale: Locale = Locale.getDefault()
    private var configuredRate: Float = 1.0f

    init {
        tts = TextToSpeech(context.applicationContext) { status ->
            val engine = tts
            if (status == TextToSpeech.SUCCESS && engine != null) {
                engine.language = configuredLocale
                engine.setSpeechRate(configuredRate)
                engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        _state.value = TtsState.READY
                    }
                    override fun onDone(utteranceId: String?) = Unit
                    override fun onError(utteranceId: String?) = Unit
                })
                _state.value = TtsState.READY
            } else {
                _state.value = TtsState.UNAVAILABLE
                Log.w(TAG, "TextToSpeech engine failed to initialize")
            }
        }
    }

    fun speak(text: String) {
        if (text.isBlank()) return
        val engine = tts ?: return
        val id = UUID.randomUUID().toString()
        val queue = if (isSpeaking()) TextToSpeech.QUEUE_ADD else TextToSpeech.QUEUE_FLUSH
        engine.speak(text, queue, null, id)
        _state.value = TtsState.READY
    }

    fun isSpeaking(): Boolean = tts?.isSpeaking == true

    fun stop() {
        tts?.stop()
    }

    fun updateSettings(languageTag: String, rate: Float) {
        configuredLocale = localeFrom(languageTag)
        configuredRate = rate
        val engine = tts ?: return
        engine.language = configuredLocale
        engine.setSpeechRate(rate)
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
    }

    private fun localeFrom(tag: String): Locale =
        runCatching { Locale.forLanguageTag(tag) }.getOrDefault(Locale.getDefault())

    companion object {
        private const val TAG = "TextToSpeech"
    }
}