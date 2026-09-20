package com.ultron.ai.ui

import android.content.Intent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.ultron.ai.core.service.ConnectionService
import com.ultron.ai.ui.command.CommandScreen
import com.ultron.ai.ui.components.PermissionDialog
import com.ultron.ai.ui.history.HistoryScreen
import com.ultron.ai.ui.home.HomeScreen
import com.ultron.ai.ui.settings.SettingsScreen
import com.ultron.ai.ui.tools.ToolsScreen

/** Bottom-bar destinations. */
enum class Dest(val route: String, val label: String, val icon: ImageVector) {
    HOME("home", "HOME", Icons.Filled.Home),
    COMMAND("command", "COMMAND", Icons.AutoMirrored.Filled.Send),
    HISTORY("history", "HISTORY", Icons.Filled.History),
    TOOLS("tools", "TOOLS", Icons.Filled.Build),
    SETTINGS("settings", "SETTINGS", Icons.Filled.Settings)
}

/**
 * App shell — top-level Scaffold with bottom navigation. Also owns the
 * keep-alive foreground service lifecycle (modules 5 + 15).
 */
@Composable
fun AppRoot(vm: JarvisViewModel = viewModel()) {
    val navController = rememberNavController()
    val context = LocalContext.current
    val settings by vm.settings.collectAsStateWithLifecycle()
    val pendingPermission by vm.pendingPermission.collectAsStateWithLifecycle()

    pendingPermission?.let { req ->
        PermissionDialog(
            request = req,
            onAllow = { vm.allowPermission(req.permissionId) },
            onDeny = { vm.denyPermission(req.permissionId) }
        )
    }

    // Keep-alive toggle drives the foreground connection service.
    LaunchedEffect(settings.keepAlive) {
        val intent = Intent(context, ConnectionService::class.java)
        if (settings.keepAlive) {
            ContextCompat.startForegroundService(context, intent)
        } else {
            context.stopService(intent)
        }
    }

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                Dest.entries.forEach { dest ->
                    NavigationBarItem(
                        selected = currentRoute == dest.route,
                        onClick = {
                            navController.navigate(dest.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(dest.icon, contentDescription = dest.label) },
                        label = { Text(dest.label, style = MaterialTheme.typography.labelSmall) }
                    )
                }
            }
        }
    ) { paddingValues ->
        NavHost(
            navController = navController,
            startDestination = Dest.HOME.route,
            modifier = Modifier.padding(paddingValues)
        ) {
            composable(Dest.HOME.route) {
                HomeScreen(
                    vm = vm,
                    onOpenCommand = {
                        navController.navigate(Dest.COMMAND.route) { launchSingleTop = true }
                    }
                )
            }
            composable(Dest.COMMAND.route) { CommandScreen(vm) }
            composable(Dest.HISTORY.route) { HistoryScreen(vm) }
            composable(Dest.TOOLS.route) { ToolsScreen(vm) }
            composable(Dest.SETTINGS.route) { SettingsScreen(vm) }
        }
    }
}