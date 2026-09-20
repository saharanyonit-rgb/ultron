package com.ultron.ai.core.auth

import com.ultron.ai.data.local.SecureStorage
import com.ultron.ai.data.model.AuthInfo
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Module 1 — API key / authentication.
 *
 * API keys and bearer tokens are never stored in plaintext: they live in
 * [SecureStorage] (Android Keystore AES-GCM) and are injected into outgoing
 * requests by the HTTP client as `X-API-Key` / `Authorization: Bearer`.
 */
class AuthManager(private val secureStorage: SecureStorage) {

    private val _apiKey = MutableStateFlow<String?>(read(KEY_API))
    val apiKey: StateFlow<String?> = _apiKey.asStateFlow()

    private val _token = MutableStateFlow<String?>(read(KEY_TOKEN))
    val token: StateFlow<String?> = _token.asStateFlow()

    val authInfo: AuthInfo
        get() = AuthInfo(apiKey = _apiKey.value, token = _token.value)

    val hasApiKey: Boolean
        get() = !_apiKey.value.isNullOrBlank()

    fun saveApiKey(key: String) {
        val trimmed = key.trim()
        if (trimmed.isEmpty()) clearApiKey()
        else {
            secureStorage.put(KEY_API, trimmed)
            _apiKey.value = trimmed
        }
    }

    fun clearApiKey() {
        secureStorage.remove(KEY_API)
        _apiKey.value = null
    }

    fun saveToken(token: String) {
        val trimmed = token.trim()
        if (trimmed.isEmpty()) {
            secureStorage.remove(KEY_TOKEN)
            _token.value = null
        } else {
            secureStorage.put(KEY_TOKEN, trimmed)
            _token.value = trimmed
        }
    }

    private fun read(key: String): String? = secureStorage.get(key)

    companion object {
        private const val KEY_API = SecureStorage.KEY_API_KEY
        private const val KEY_TOKEN = SecureStorage.KEY_AUTH_TOKEN
    }
}