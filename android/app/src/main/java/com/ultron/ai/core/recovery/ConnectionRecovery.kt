package com.ultron.ai.core.recovery

import com.ultron.ai.data.local.AppSettings
import com.ultron.ai.data.local.SettingsStore

/**
 * Module 15 — Connection recovery.
 *
 * Exponential backoff with jitter driven by the user's settings:
 * base delay from Settings, doubling per attempt, capped at 60s, plus a
 * ±20% random jitter so multiple devices never thundering-herd a server.
 */
class ConnectionRecovery(
    private val settingsProvider: () -> AppSettings = { AppSettings() }
) {

    private var attempt = 0

    val attempts: Int get() = attempt

    fun reset() {
        attempt = 0
    }

    /** True while the current attempt budget allows one more retry. */
    fun shouldContinue(): Boolean = attempt <= maxAttempts()

    /** Delay (ms) before the next retry; increments the attempt counter. */
    fun nextDelay(): Long {
        attempt++
        val base = settingsProvider().recoveryBaseDelayMs.toLong().coerceIn(250L, 60_000L)
        val exponent = Math.pow(2.0, (attempt - 1).coerceAtMost(12).toDouble())
        val exponential = (base * exponent).toLong().coerceAtMost(MAX_DELAY_MS)
        val jitter = (exponential * 0.2).toLong().coerceAtLeast(50L)
        return (exponential + (-jitter..jitter).random()).coerceAtLeast(250L)
    }

    private fun maxAttempts(): Int = settingsProvider().maxRetries.coerceIn(1, 50)

    companion object {
        private const val MAX_DELAY_MS = 60_000L
    }
}