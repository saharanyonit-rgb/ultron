package com.ultron.ai.core.connection

import com.ultron.ai.data.model.JarvisStatus

/**
 * Module 2 (state half) — the app's connection lifecycle for the JARVIS
 * backend. Drives the home screen status pill and the core orb.
 */
sealed interface ConnectionState {
    /** Nothing done yet (app start / after stop). */
    data object Idle : ConnectionState

    /** Attempting the initial HTTP handshake. */
    data class Connecting(val attempt: Int) : ConnectionState

    /** Backend reachable; realtime stream open. */
    data class Connected(
        val serverUrl: String,
        val status: JarvisStatus? = null
    ) : ConnectionState

    /** Connection dropped; scheduled to retry after [delayMs]. */
    data class Reconnecting(
        val attempt: Int,
        val delayMs: Long,
        val reason: String? = null
    ) : ConnectionState

    /** Gave up (or backend reported offline). */
    data class Disconnected(val reason: String? = null) : ConnectionState

    /** Hard failure that aborted the current session. */
    data class Error(val message: String) : ConnectionState
}

fun ConnectionState.title(): String = when (this) {
    is ConnectionState.Idle -> "OFFLINE"
    is ConnectionState.Connecting -> "CONNECTING…"
    is ConnectionState.Connected -> "ONLINE"
    is ConnectionState.Reconnecting -> "RECONNECTING…"
    is ConnectionState.Disconnected -> "OFFLINE"
    is ConnectionState.Error -> "ERROR"
}

fun ConnectionState.subtitle(): String = when (this) {
    is ConnectionState.Idle -> "Waiting to connect"
    is ConnectionState.Connecting -> "Handshake attempt $attempt"
    is ConnectionState.Connected -> serverUrl
    is ConnectionState.Reconnecting -> reason?.let { "$it — retry $attempt" } ?: "Retry $attempt"
    is ConnectionState.Disconnected -> reason ?: "Backend unreachable"
    is ConnectionState.Error -> message
}

fun ConnectionState.isConnected(): Boolean = this is ConnectionState.Connected

fun ConnectionState.isActive(): Boolean = this !is ConnectionState.Idle