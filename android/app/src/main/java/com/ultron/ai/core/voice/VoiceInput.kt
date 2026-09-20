package com.ultron.ai.core.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import java.util.Locale
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Module 8 — Voice input.
 *
 * Wraps the platform SpeechRecognizer. Use [start] after RECORD_AUDIO has been
 * granted; transcripts arrive on [results] and lifecycle changes on [state].
 */
class VoiceInput(private val context: Context) {

    enum class VoiceState { IDLE, LISTENING, PROCESSING, DONE, FAILED }

    private val _state = MutableStateFlow(VoiceState.IDLE)
    val state: StateFlow<VoiceState> = _state.asStateFlow()

    private val _results = MutableSharedFlow<String>(extraBufferCapacity = 8)
    val results: SharedFlow<String> = _results.asSharedFlow()

    private var recognizer: SpeechRecognizer? = null

    val isRecognizerAvailable: Boolean get() = SpeechRecognizer.isRecognitionAvailable(context)

    fun start(
        languageTag: String = Locale.getDefault().toLanguageTag(),
        timeoutMs: Int = 5000
    ) {
        if (!isRecognizerAvailable) {
            _state.value = VoiceState.FAILED
            _results.tryEmit(ERROR_UNAVAILABLE)
            return
        }
        stop()
        val sr = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = sr
        sr.setRecognitionListener(listener)

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        }
        _state.value = VoiceState.LISTENING
        sr.startListening(intent)
    }

    fun stop() {
        recognizer?.stopListening()
    }

    fun destroy() {
        recognizer?.destroy()
        recognizer = null
        _state.value = VoiceState.IDLE
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {}
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {
            _state.value = VoiceState.PROCESSING
        }
        override fun onError(error: Int) {
            Log.w(TAG, "SpeechRecognizer error: $error")
            _state.value = VoiceState.FAILED
            _results.tryEmit(errorMessage(error))
        }
        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val best = matches?.firstOrNull().orEmpty()
            _state.value = VoiceState.DONE
            if (best.isNotBlank()) _results.tryEmit(best)
        }
        override fun onPartialResults(partialResults: Bundle?) {}
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    private fun errorMessage(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected"
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Listening timed out"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognition service busy"
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission needed"
        SpeechRecognizer.ERROR_NETWORK -> "Recognition network error"
        SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE -> "Language pack unavailable"
        SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED -> "Language not supported"
        else -> "Voice recognition failed ($error)"
    }

    companion object {
        private const val TAG = "VoiceInput"
        private const val ERROR_UNAVAILABLE = "Voice recognition not available on this device"
    }
}