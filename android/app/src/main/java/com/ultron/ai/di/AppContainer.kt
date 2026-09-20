package com.ultron.ai.di

import android.content.Context
import com.ultron.ai.core.auth.AuthManager
import com.ultron.ai.core.connection.ConnectionManager
import com.ultron.ai.core.permissions.PermissionsManager
import com.ultron.ai.core.recovery.ConnectionRecovery
import com.ultron.ai.core.voice.TextToSpeechManager
import com.ultron.ai.core.voice.VoiceInput
import com.ultron.ai.data.local.HistoryRepository
import com.ultron.ai.data.local.SecureStorage
import com.ultron.ai.data.local.SettingsStore
import com.ultron.ai.data.remote.JarvisApi
import com.ultron.ai.data.remote.JarvisHttpClient
import com.ultron.ai.data.remote.SseClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

/**
 * Hand-rolled service locator (no DI framework needed for a project this size).
 * Every singleton is created lazily and torn down together at process death.
 */
class AppContainer(context: Context) {

    private val appContext = context.applicationContext
    private val connectionScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val secureStorage: SecureStorage by lazy { SecureStorage(appContext) }
    val settingsStore: SettingsStore by lazy { SettingsStore(appContext) }
    val historyRepository: HistoryRepository by lazy { HistoryRepository(appContext) }
    val authManager: AuthManager by lazy { AuthManager(secureStorage) }
    val permissionsManager: PermissionsManager by lazy { PermissionsManager(appContext) }

    val httpClient: JarvisHttpClient by lazy {
        JarvisHttpClient(
            configProvider = { settingsStore.settings.value.serverConfig },
            authProvider = { authManager.authInfo }
        )
    }
    val jarvisApi: JarvisApi by lazy { JarvisApi(httpClient) }
    val sseClient: SseClient by lazy { SseClient(httpClient) }
    val recovery: ConnectionRecovery by lazy { ConnectionRecovery({ settingsStore.settings.value }) }

    val connectionManager: ConnectionManager by lazy {
        ConnectionManager(
            scope = connectionScope,
            api = jarvisApi,
            sse = sseClient,
            settingsStore = settingsStore,
            recovery = recovery,
            history = historyRepository
        )
    }

    val voiceInput: VoiceInput by lazy { VoiceInput(appContext) }
    val textToSpeech: TextToSpeechManager by lazy { TextToSpeechManager(appContext) }
}