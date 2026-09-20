package com.ultron.ai.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ultron.ai.data.model.ServerConfig
import com.ultron.ai.data.model.ServerMode
import com.ultron.ai.ui.JarvisViewModel
import com.ultron.ai.ui.components.SettingsSection
import com.ultron.ai.ui.theme.JarvisCyan
import com.ultron.ai.ui.theme.JarvisSurfaceVariant
import kotlin.math.roundToInt

/**
 * Module 1 + 14 — Authentication and full app settings.
 * Backend address/mode, API key (stored encrypted), voice, connection
 * recovery parameters, background keep-alive and data management.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(vm: JarvisViewModel) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    val apiKeyConfigured by vm.apiKeyConfigured.collectAsStateWithLifecycle()

    // Local form state (values are pushed to the repo on "Save & connect").
    var mode by remember { mutableStateOf(settings.serverMode) }
    var address by remember { mutableStateOf(settings.serverAddress) }
    var port by remember { mutableStateOf(settings.serverPort.toString()) }
    var https by remember { mutableStateOf(settings.serverHttps) }
    var apiKeyInput by remember { mutableStateOf("") }
    var showKey by remember { mutableStateOf(false) }
    var ttsEnabled by remember { mutableStateOf(settings.ttsEnabled) }
    var ttsRate by remember { mutableStateOf(settings.ttsRate) }
    var ttsLanguage by remember { mutableStateOf(settings.ttsLanguage) }
    var listenTimeout by remember { mutableStateOf(settings.voiceListenTimeoutMs.toString()) }
    var maxRetries by remember { mutableStateOf(settings.maxRetries.toFloat()) }
    var baseDelay by remember { mutableStateOf(settings.recoveryBaseDelayMs.coerceAtLeast(500).toFloat()) }
    var testResult by remember { mutableStateOf<String?>(null) }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("SETTINGS", fontWeight = FontWeight.Bold, letterSpacing = 3.sp) },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                ),
                actions = {
                    TextButton(onClick = {
                        saveSettings(
                            vm, mode, address, port, https,
                            ttsEnabled, ttsRate, ttsLanguage, listenTimeout,
                            maxRetries, baseDelay
                        )
                    }) { Text("Save & connect", color = JarvisCyan) }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp)
        ) {
            SettingsSection("CONNECTION") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    connectionChip(ServerMode.LOOPBACK, mode) { mode = it }
                    connectionChip(ServerMode.REMOTE, mode) { mode = it }
                }
                OutlinedTextField(
                    value = address,
                    onValueChange = { address = it },
                    label = { Text("Server address") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = port,
                    onValueChange = { port = it.filter(Char::isDigit).take(5) },
                    label = { Text("Port") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "Use HTTPS",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f)
                    )
                    Switch(checked = https, onCheckedChange = { https = it })
                }
                OutlinedButton(onClick = {
                    val cfg = serverConfigFromForm(mode, address, port, https)
                    testResult = "Testing ${cfg.displayUrl()}…"
                    vm.testConnection(cfg) { testResult = it }
                }) {
                    Text("Test connection")
                }
                testResult?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            SettingsSection("AUTHENTICATION") {
                OutlinedTextField(
                    value = apiKeyInput,
                    onValueChange = { apiKeyInput = it },
                    label = { Text(if (apiKeyConfigured) "API key (saved)" else "API key") },
                    singleLine = true,
                    visualTransformation = if (showKey) VisualTransformation.None
                    else PasswordVisualTransformation(),
                    trailingIcon = {
                        IconButton(onClick = { showKey = !showKey }) {
                            Icon(
                                if (showKey) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                                contentDescription = "Toggle visibility"
                            )
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = {
                            if (apiKeyInput.isNotBlank()) {
                                vm.saveApiKey(apiKeyInput)
                                apiKeyInput = ""
                            }
                        },
                        enabled = apiKeyInput.isNotBlank()
                    ) { Text("Save key") }
                    if (apiKeyConfigured) {
                        TextButton(onClick = { vm.clearApiKey() }) { Text("Clear") }
                    }
                }
                Text(
                    "Stored encrypted via Android Keystore and sent as X-API-Key.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            SettingsSection("VOICE") {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "Text-to-speech",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f)
                    )
                    Switch(
                        checked = ttsEnabled,
                        onCheckedChange = {
                            ttsEnabled = it
                            vm.updateSettings { s -> s.copy(ttsEnabled = it) }
                        }
                    )
                }
                if (ttsEnabled) {
                    Text("Speech rate: ${"%.1f".format(ttsRate)}×", style = MaterialTheme.typography.bodySmall)
                    Slider(
                        value = ttsRate,
                        onValueChange = { ttsRate = it },
                        valueRange = 0.5f..2.0f,
                        onValueChangeFinished = {
                            vm.updateSettings { s -> s.copy(ttsRate = ttsRate) }
                        }
                    )
                }
                OutlinedTextField(
                    value = ttsLanguage,
                    onValueChange = { ttsLanguage = it },
                    label = { Text("TTS language (BCP-47)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = listenTimeout,
                    onValueChange = { listenTimeout = it.filter(Char::isDigit).take(6) },
                    label = { Text("Voice listen timeout (ms)") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }

            SettingsSection("CONNECTION RECOVERY") {
                Text("Max retries: ${maxRetries.roundToInt()}", style = MaterialTheme.typography.bodySmall)
                Slider(value = maxRetries, onValueChange = { maxRetries = it }, valueRange = 1f..30f)
                Text("Base delay: ${baseDelay.roundToInt()} ms", style = MaterialTheme.typography.bodySmall)
                Slider(
                    value = baseDelay,
                    onValueChange = { baseDelay = it },
                    valueRange = 500f..10_000f
                )
            }

            SettingsSection("BACKGROUND") {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "Keep connection alive",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f)
                    )
                    Switch(
                        checked = settings.keepAlive,
                        onCheckedChange = { keep ->
                            vm.updateSettings { s -> s.copy(keepAlive = keep) }
                        }
                    )
                }
                Text(
                    "Runs a foreground service so JARVIS stays connected in the background.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            SettingsSection("DATA") {
                OutlinedButton(
                    onClick = { vm.clearHistory() },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Clear activity history") }
            }

            SettingsSection("ABOUT") {
                Text(
                    "ULTRON AI 2.0 — native JARVIS client\nModular: connection, SSE, voice, tools, storage.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun connectionChip(option: ServerMode, selected: ServerMode, onSelect: (ServerMode) -> Unit) {
    FilterChip(
        selected = selected == option,
        onClick = { onSelect(option) },
        label = { Text(option.displayName) }
    )
}

private fun serverConfigFromForm(
    mode: ServerMode,
    address: String,
    port: String,
    https: Boolean
): ServerConfig = ServerConfig(
    mode = mode,
    address = address.trim().ifBlank { "127.0.0.1" },
    port = (port.toIntOrNull() ?: 8080).coerceIn(1, 65535),
    useHttps = https
)

private fun saveSettings(
    vm: JarvisViewModel,
    mode: ServerMode,
    address: String,
    port: String,
    https: Boolean,
    ttsEnabled: Boolean,
    ttsRate: Float,
    ttsLanguage: String,
    listenTimeout: String,
    maxRetries: Float,
    baseDelay: Float
) {
    vm.updateSettings { s ->
        s.copy(
            serverMode = mode,
            serverAddress = address.trim().ifBlank { "127.0.0.1" },
            serverPort = (port.toIntOrNull() ?: 8080).coerceIn(1, 65535),
            serverHttps = https,
            ttsEnabled = ttsEnabled,
            ttsRate = ttsRate,
            ttsLanguage = ttsLanguage,
            voiceListenTimeoutMs = (listenTimeout.toIntOrNull() ?: 5000).coerceIn(1000, 60_000),
            maxRetries = maxRetries.roundToInt().coerceIn(1, 50),
            recoveryBaseDelayMs = baseDelay.roundToInt().coerceIn(250, 60_000)
        )
    }
    vm.reconnect()
}