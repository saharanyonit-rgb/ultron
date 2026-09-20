package com.ultron.ai.ui.tools

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ultron.ai.data.model.ToolInfo
import com.ultron.ai.ui.JarvisViewModel
import com.ultron.ai.ui.components.JarvisCard
import com.ultron.ai.ui.components.SectionHeader
import com.ultron.ai.ui.theme.JarvisAmber
import com.ultron.ai.ui.theme.JarvisCyan
import com.ultron.ai.ui.theme.JarvisGray
import com.ultron.ai.ui.theme.JarvisOrange
import com.ultron.ai.ui.theme.JarvisRed

/**
 * Module 11 — Tools / capabilities. Lists everything the backend exposes
 * (GET /api/tools) with risk badges and local availability toggles.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ToolsScreen(vm: JarvisViewModel) {
    val tools by vm.tools.collectAsStateWithLifecycle()
    val loading by vm.toolsLoading.collectAsStateWithLifecycle()
    val settings by vm.settings.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) { vm.loadTools() }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("TOOLS", fontWeight = FontWeight.Bold, letterSpacing = 3.sp) },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                ),
                actions = {
                    IconButton(onClick = { vm.loadTools() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh tools")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                SectionHeader("BACKEND CAPABILITIES")
                Spacer(Modifier.weight(1f))
                Text(
                    "${tools.size} tools",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            when {
                loading && tools.isEmpty() -> {
                    Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                tools.isEmpty() -> {
                    Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                        Text(
                            "The backend did not report any tools yet.\nTry again after it finishes loading.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier.weight(1f).fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(tools, key = { it.id }) { tool ->
                            val localEnabled = if (settings.enabledTools.isEmpty()) {
                                tool.enabled
                            } else {
                                tool.id in settings.enabledTools
                            }
                            ToolCard(
                                tool = tool,
                                localEnabled = localEnabled,
                                onToggle = { enabled -> vm.toggleTool(tool.id, enabled) }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ToolCard(
    tool: ToolInfo,
    localEnabled: Boolean,
    onToggle: (Boolean) -> Unit
) {
    JarvisCard {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        tool.name,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = if (localEnabled) MaterialTheme.colorScheme.onSurface
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                        textDecoration = if (localEnabled) TextDecoration.None else TextDecoration.LineThrough
                    )
                    if (tool.risk.isNotBlank()) RiskBadge(tool.risk)
                }
                if (tool.category.isNotBlank()) {
                    Text(
                        tool.category.uppercase(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Switch(checked = localEnabled, onCheckedChange = onToggle)
        }
        if (tool.description.isNotBlank()) {
            Text(
                tool.description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
private fun RiskBadge(risk: String) {
    val color = when (risk.lowercase()) {
        "read", "low" -> JarvisCyan
        "medium" -> JarvisAmber
        "high" -> JarvisOrange
        "critical" -> JarvisRed
        else -> JarvisGray
    }
    Surface(shape = RoundedCornerShape(6.dp), color = color.copy(alpha = 0.14f)) {
        Text(
            risk.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = color,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}