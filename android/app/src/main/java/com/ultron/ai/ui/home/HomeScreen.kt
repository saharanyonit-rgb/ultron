package com.ultron.ai.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ultron.ai.core.connection.ConnectionState
import com.ultron.ai.core.connection.subtitle
import com.ultron.ai.core.voice.VoiceInput
import com.ultron.ai.data.model.HistoryEntry
import com.ultron.ai.ui.JarvisViewModel
import com.ultron.ai.ui.components.HistoryRow
import com.ultron.ai.ui.components.JarvisCard
import com.ultron.ai.ui.components.KeyValueRow
import com.ultron.ai.ui.components.SectionHeader
import com.ultron.ai.ui.components.StatusPill
import com.ultron.ai.ui.core.JarvisCoreView
import com.ultron.ai.ui.core.coreColor
import com.ultron.ai.ui.core.coreLabel
import com.ultron.ai.ui.theme.JarvisAmber
import com.ultron.ai.ui.theme.JarvisCyan

/**
 * Module 5 — Home screen. Connection telemetry, the JARVIS core orb
 * (module 6) and quick actions for command / voice / speech.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    vm: JarvisViewModel,
    onOpenCommand: () -> Unit
) {
    val connection by vm.connectionState.collectAsStateWithLifecycle()
    val core by vm.coreState.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    val latency by vm.latencyMs.collectAsStateWithLifecycle()
    val settings by vm.settings.collectAsStateWithLifecycle()
    val history by vm.history.collectAsStateWithLifecycle()
    val voiceState by vm.voiceState.collectAsStateWithLifecycle()
    val listening = voiceState == VoiceInput.VoiceState.LISTENING

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "JARVIS",
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 4.sp
                    )
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item { ConnectionCard(connection, status?.status, status?.version, latency, settings.serverConfig.displayUrl()) }

            item {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        JarvisCoreView(state = core)
                        Spacer(Modifier.height(10.dp))
                        Text(
                            coreLabel(core),
                            style = MaterialTheme.typography.titleMedium,
                            color = coreColor(core),
                            letterSpacing = 1.5.sp
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            connection.subtitle(),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center
                        )
                    }
                }
            }

            item {
                QuickActions(
                    listening = listening,
                    onOpenCommand = onOpenCommand,
                    onToggleVoice = { vm.toggleListening() },
                    onSpeak = { vm.speak("Hello, this is JARVIS. All systems online.") }
                )
            }

            item {
                RecentActivity(entries = history.take(4))
            }
        }
    }
}

@Composable
private fun ConnectionCard(
    connection: ConnectionState,
    rawStatus: String?,
    version: String?,
    latency: Long?,
    serverUrl: String
) {
    JarvisCard {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "JARVIS BACKEND",
                style = MaterialTheme.typography.titleSmall,
                letterSpacing = 2.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1f)
            )
            StatusPill(connection)
        }
        KeyValueRow("SERVER", serverUrl)
        KeyValueRow("STATUS", rawStatus?.uppercase() ?: "OFFLINE")
        KeyValueRow("VERSION", version ?: "—")
        KeyValueRow("LATENCY", latency?.let { "$it ms" } ?: "—")
    }
}

@Composable
private fun QuickActions(
    listening: Boolean,
    onOpenCommand: () -> Unit,
    onToggleVoice: () -> Unit,
    onSpeak: () -> Unit
) {
    JarvisCard {
        SectionHeader("QUICK ACTIONS")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ActionTile("Text", Icons.AutoMirrored.Filled.Send, JarvisCyan, onOpenCommand, Modifier.weight(1f))
            ActionTile(
                "Voice",
                Icons.Filled.Mic,
                if (listening) JarvisAmber else MaterialTheme.colorScheme.onSurfaceVariant,
                onToggleVoice,
                Modifier.weight(1f)
            )
            ActionTile("Speak", Icons.AutoMirrored.Filled.VolumeUp, MaterialTheme.colorScheme.onSurfaceVariant, onSpeak, Modifier.weight(1f))
        }
        if (listening) {
            Text(
                "Listening — speak now…",
                style = MaterialTheme.typography.bodySmall,
                color = JarvisAmber
            )
        }
    }
}

@Composable
private fun ActionTile(
    label: String,
    icon: ImageVector,
    accent: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    TextButton(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(14.dp)
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Surface(
                shape = CircleShape,
                color = accent.copy(alpha = 0.14f)
            ) {
                Box(
                    Modifier
                        .padding(10.dp)
                        .size(22.dp)
                ) {
                    Icon(icon, contentDescription = label, tint = accent)
                }
            }
            Text(label, style = MaterialTheme.typography.labelMedium, color = accent)
        }
    }
}

@Composable
private fun RecentActivity(entries: List<HistoryEntry>) {
    JarvisCard {
        SectionHeader("RECENT ACTIVITY")
        if (entries.isEmpty()) {
            Text(
                "No activity yet. Ask JARVIS something.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        } else {
            entries.forEach { entry ->
                HistoryRow(entry)
                if (entry != entries.last()) {
                    Spacer(Modifier.height(4.dp))
                }
            }
        }
    }
}