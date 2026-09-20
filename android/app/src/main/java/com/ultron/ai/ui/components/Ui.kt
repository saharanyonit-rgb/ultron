package com.ultron.ai.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ultron.ai.core.connection.ConnectionState
import com.ultron.ai.core.connection.title
import com.ultron.ai.data.model.EntryStatus
import com.ultron.ai.data.model.HistoryEntry
import com.ultron.ai.data.model.HistoryKind
import com.ultron.ai.ui.theme.JarvisAmber
import com.ultron.ai.ui.theme.JarvisCyan
import com.ultron.ai.ui.theme.JarvisGray
import com.ultron.ai.ui.theme.JarvisOrange
import com.ultron.ai.ui.theme.JarvisPurple
import com.ultron.ai.ui.theme.JarvisRed
import com.ultron.ai.ui.theme.JarvisTeal
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Card with the standard JARVIS surface treatment. */
@Composable
fun JarvisCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            content = content
        )
    }
}

/** Connection-state pill (module 2/5 UI). */
@Composable
fun StatusPill(state: ConnectionState, modifier: Modifier = Modifier) {
    val (color, label) = when (state) {
        is ConnectionState.Connected -> JarvisCyan to state.title()
        is ConnectionState.Connecting, is ConnectionState.Reconnecting -> JarvisAmber to state.title()
        is ConnectionState.Error -> JarvisRed to state.title()
        else -> JarvisGray to state.title()
    }
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(50),
        color = color.copy(alpha = 0.14f)
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
        ) {
            Box(Modifier.size(7.dp).background(color, CircleShape))
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                color = color,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

/** Label / value pair used across status cards. */
@Composable
fun KeyValueRow(label: String, value: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f)
        )
        Text(
            if (value.isBlank()) "—" else value,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.End,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

/** Uppercase section heading. */
@Composable
fun SectionHeader(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        letterSpacing = 2.sp,
        modifier = modifier
    )
}

/** Grouped settings/tools section. */
@Composable
fun SettingsSection(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionHeader(title)
        JarvisCard { content() }
    }
}

fun historyKindColor(kind: HistoryKind): Color = when (kind) {
    HistoryKind.COMMAND -> JarvisCyan
    HistoryKind.VOICE -> JarvisOrange
    HistoryKind.RESPONSE -> JarvisTeal
    HistoryKind.RESULT -> JarvisPurple
    HistoryKind.SYSTEM -> JarvisGray
}

private val timeFormat = SimpleDateFormat("MM/dd HH:mm", Locale.getDefault())
private fun formatTime(timestamp: Long): String = timeFormat.format(Date(timestamp))

/** One row in the activity / task history list. */
@Composable
fun HistoryRow(entry: HistoryEntry, modifier: Modifier = Modifier) {
    val color = historyKindColor(entry.kind)
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            Modifier
                .padding(top = 5.dp)
                .size(8.dp)
                .background(color, CircleShape)
        )
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    entry.kind.name,
                    style = MaterialTheme.typography.labelSmall,
                    color = color,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f)
                )
                if (entry.status == EntryStatus.FAILED) {
                    Text("FAILED", style = MaterialTheme.typography.labelSmall, color = JarvisRed)
                    Spacer(Modifier.size(6.dp))
                }
                Text(
                    formatTime(entry.timestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Text(
                entry.text,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis
            )
            if (entry.detail.isNotBlank()) {
                Text(
                    entry.detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}