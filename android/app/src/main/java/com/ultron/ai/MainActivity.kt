package com.ultron.ai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import com.ultron.ai.ui.AppRoot
import com.ultron.ai.ui.theme.JarvisTheme

class MainActivity : ComponentActivity() {

    private val container get() = (application as JarvisApp).container

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        // Granted state is re-read from PermissionsManager whenever needed.
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        requestRuntimePermissions()
        container.connectionManager.start()

        setContent {
            JarvisTheme {
                AppRoot()
            }
        }
    }

    private fun requestRuntimePermissions() {
        val pm = container.permissionsManager
        if (pm.missing().isNotEmpty()) {
            permissionLauncher.launch(pm.missing().toTypedArray())
        }
    }
}