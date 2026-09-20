package com.ultron.ai.core.permissions

import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat

/**
 * Module 12 — Android runtime permissions.
 *
 * Central registry for every runtime permission the app needs and a small
 * helper to drive the one-time grant dialog from the UI layer.
 */
class PermissionsManager(private val context: Context) {

    /** Permissions that need a runtime grant on modern Android. */
    fun runtimePermissions(): List<String> = buildList {
        add(android.Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(android.Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    fun isGranted(permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    fun alreadyResolved(): Boolean = runtimePermissions().isEmpty()

    /** All required permissions (declared in the manifest) mapped to a friendly label. */
    fun missing(): List<String> = runtimePermissions().filterNot { isGranted(it) }

    fun has(permission: String): Boolean =
        missing().none { it == permission }

    val allGranted: Boolean
        get() = runtimePermissions().all { isGranted(it) }

    /** Trigger the grant dialog; results flow back through onRequestPermissionsResult. */
    fun request(activity: Activity, requestCode: Int = REQUEST_CODE): Boolean {
        val needed = missing()
        if (needed.isEmpty()) return false
        activity.requestPermissions(needed.toTypedArray(), requestCode)
        return true
    }

    companion object {
        const val REQUEST_CODE = 7301
    }
}