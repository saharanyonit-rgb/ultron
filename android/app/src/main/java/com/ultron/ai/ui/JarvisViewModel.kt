package com.ultron.ai.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ultron.ai.JarvisApp
import com.ultron.ai.data.local.AppSettings
import com.ultron.ai.data.model.ChatMessage
import com.ultron.ai.data.model.ChatRole
import com.ultron.ai.data.model.HistoryEntry
import com.ultron.ai.data.model.ServerConfig
import com.ultron.ai.data.model.ToolInfo
import com.ultron.ai.core.voice.VoiceInput
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Single shared screens-mVVM view-model. Wires the 15 modules to the UI:
 * connection (2/4/15), commands (7), voice (8/9), history (10), tools (11),
 * auth (1), settings (14).
 */
class JarvisViewModel(application: Application) : AndroidViewModel(application) {

    private val container = (application as JarvisApp).container

    // ── Connection (modules 2, 4, 15) ────────────────────────────────
    val connectionState = container.connectionManager.state
    val coreState = container.connectionManager.coreState
    val status = container.connectionManager.status
    val latencyMs = container.connectionManager.latencyMs
    val pendingPermission = container.connectionManager.pendingPermission

    // ── Settings / auth / history / tools (modules 14, 1, 10, 11) ────
    val settings: StateFlow<AppSettings> = container.settingsStore.settings
    val history: StateFlow<List<HistoryEntry>> = container.historyRepository.entries
    val apiKeyConfigured: StateFlow<Boolean> = container.authManager.apiKey
        .map { !it.isNullOrBlank() }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), false)

    private val _tools = MutableStateFlow<List<ToolInfo>>(emptyList())
    val tools: StateFlow<List<ToolInfo>> = _tools.asStateFlow()

    private val _toolsLoading = MutableStateFlow(false)
    val toolsLoading: StateFlow<Boolean> = _toolsLoading.asStateFlow()

    // ── Chat (modules 7, 8) ──────────────────────────────────────────
    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    // ── Voice / TTS (modules 8, 9) ───────────────────────────────────
    val voiceState: StateFlow<VoiceInput.VoiceState> = container.voiceInput.state
    val ttsState = container.textToSpeech.state

    init {
        viewModelScope.launch {
            container.voiceInput.results.collect { transcript ->
                if (transcript.isNotBlank()) sendMessage(transcript, fromVoice = true)
            }
        }
    }

    // ── Connection controls ──────────────────────────────────────────
    fun startConnection() = container.connectionManager.start()

    fun reconnect() = container.connectionManager.reconnect()

    fun allowPermission(id: String) = container.connectionManager.allowPermission(id)

    fun denyPermission(id: String) = container.connectionManager.denyPermission(id)

    fun testConnection(config: ServerConfig, onResult: (String) -> Unit) {
        viewModelScope.launch {
            val probe = container.jarvisApi.probeStatus(config)
            onResult(
                if (probe?.isOnline == true) {
                    "OK - ${probe.serverType ?: "JARVIS"} ${probe.version.orEmpty().trim()}"
                } else {
                    "Unreachable - check address and restart the backend"
                }
            )
        }
    }

    // ── Auth (module 1) ──────────────────────────────────────────────
    fun saveApiKey(key: String) = container.authManager.saveApiKey(key)

    fun clearApiKey() = container.authManager.clearApiKey()

    // ── Settings (module 14) ─────────────────────────────────────────
    fun updateSettings(transform: (AppSettings) -> AppSettings) {
        viewModelScope.launch { container.settingsStore.update(transform) }
    }

    // ── History (module 10) ──────────────────────────────────────────
    fun clearHistory() = container.historyRepository.clear()

    // ── Tools / capabilities (module 11) ─────────────────────────────
    fun loadTools() {
        if (_toolsLoading.value) return
        _toolsLoading.value = true
        viewModelScope.launch {
            _tools.value = container.jarvisApi.tools()
            _toolsLoading.value = false
        }
    }

    fun toggleTool(id: String, enabled: Boolean) {
        updateSettings { s ->
            s.copy(enabledTools = if (enabled) s.enabledTools + id else s.enabledTools - id)
        }
    }

    // ── Commands (module 7) ──────────────────────────────────────────
    fun sendMessage(text: String, fromVoice: Boolean = false) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return
        append(ChatRole.USER, trimmed)
        if (fromVoice) container.historyRepository.addVoice(trimmed)
        else container.historyRepository.addCommand(trimmed)

        _busy.value = true
        viewModelScope.launch {
            val reply = container.jarvisApi.sendMessage(trimmed)
            _busy.value = false
            val content = reply ?: "(no response from backend)"
            append(ChatRole.ASSISTANT, content)
            container.historyRepository.addResponse(content)
            speakIfEnabled(content, forceOnDevice = true)
        }
    }

    // ── Voice input (module 8) ───────────────────────────────────────
    fun startListening() {
        val s = settings.value
        container.voiceInput.start(s.ttsLanguage, s.voiceListenTimeoutMs)
    }

    fun stopListening() = container.voiceInput.stop()

    fun toggleListening() {
        if (voiceState.value == VoiceInput.VoiceState.LISTENING) stopListening()
        else startListening()
    }

    // ── TTS (module 9) ───────────────────────────────────────────────
    fun speak(text: String) {
        val s = settings.value
        if (s.ttsEnabled) {
            container.textToSpeech.updateSettings(s.ttsLanguage, s.ttsRate)
            container.textToSpeech.speak(text)
        } else {
            viewModelScope.launch { container.jarvisApi.speak(text) }
        }
    }

    fun stopSpeaking() = container.textToSpeech.stop()

    private fun speakIfEnabled(text: String, forceOnDevice: Boolean) {
        val s = settings.value
        if (!s.ttsEnabled) return
        val short = text.takeLast(400)
        container.textToSpeech.updateSettings(s.ttsLanguage, s.ttsRate)
        container.textToSpeech.speak(short)
    }

    // ── Tear-down ────────────────────────────────────────────────────
    override fun onCleared() {
        container.voiceInput.destroy()
        container.textToSpeech.shutdown()
        super.onCleared()
    }

    private fun append(role: ChatRole, content: String) {
        _messages.value = (_messages.value + ChatMessage(
            id = UUID.randomUUID().toString(),
            role = role,
            content = content
        )).takeLast(MAX_MESSAGES)
    }

    companion object {
        private const val MAX_MESSAGES = 200
    }
}