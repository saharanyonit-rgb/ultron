package com.ultron.ai.core.connection

import android.util.Log
import com.ultron.ai.core.recovery.ConnectionRecovery
import com.ultron.ai.data.local.HistoryRepository
import com.ultron.ai.data.local.SettingsStore
import com.ultron.ai.data.model.CoreState
import com.ultron.ai.data.model.JarvisEvent
import com.ultron.ai.data.model.JarvisStatus
import com.ultron.ai.data.model.PendingPermissionRequest
import com.ultron.ai.data.model.stringOrNull
import com.ultron.ai.data.remote.JarvisApi
import com.ultron.ai.data.remote.SseClient
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.cancellation.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Module 2 — JARVIS backend connection.
 *
 * Owns the connect → health-check → (drop) → replay loop. The realtime stream
 * (SSE) plus a periodic status probe both feed a single "connection lost"
 * signal; on loss the [ConnectionRecovery] backoff kicks in, the loop re-snapshots
 * the current server settings and reconnects. Exposes the public connection
 * state and the derived JARVIS core state for the UI.
 */
class ConnectionManager(
    private val scope: CoroutineScope,
    private val api: JarvisApi,
    private val sse: SseClient,
    private val settingsStore: SettingsStore,
    private val recovery: ConnectionRecovery,
    private val history: HistoryRepository
) {

    private val _state = MutableStateFlow<ConnectionState>(ConnectionState.Idle)
    val state: StateFlow<ConnectionState> = _state

    private val _coreState = MutableStateFlow(CoreState.IDLE)
    val coreState: StateFlow<CoreState> = _coreState

    private val _status = MutableStateFlow<JarvisStatus?>(null)
    val status: StateFlow<JarvisStatus?> = _status

    private val _latencyMs = MutableStateFlow<Long?>(null)
    val latencyMs: StateFlow<Long?> = _latencyMs

    private val _pendingPermission = MutableStateFlow<PendingPermissionRequest?>(null)
    val pendingPermission: StateFlow<PendingPermissionRequest?> = _pendingPermission.asStateFlow()

    private var worker: Job? = null
    private var sseCollector: Job? = null
    private var healthJob: Job? = null

    private val active = AtomicBoolean(false)

    /**
     * Opens the connection loop. Safe to call more than once; a running loop is
     * left untouched.
     */
    fun start() {
        if (!active.compareAndSet(false, true)) return
        worker = scope.launch { runLoop() }
    }

    fun stop() {
        active.set(false)
        worker?.cancel()
        worker = null
        stopPeripherals()
        _state.value = ConnectionState.Idle
        _coreState.value = CoreState.IDLE
        _status.value = null
        _latencyMs.value = null
        _pendingPermission.value = null
    }

    /** Tear down and reconnect immediately (used by Settings and the UI). */
    fun reconnect() {
        worker?.cancel()
        worker = null
        stopPeripherals()
        if (!active.get()) active.set(true)
        worker = scope.launch { runLoop() }
    }

    fun allowPermission(permissionId: String) {
        scope.launch {
            api.allowPermission(permissionId)
            _pendingPermission.value = null
            _coreState.value = CoreState.CONNECTED
        }
    }

    fun denyPermission(permissionId: String) {
        scope.launch {
            api.denyPermission(permissionId)
            _pendingPermission.value = null
            _coreState.value = CoreState.CONNECTED
        }
    }

    private suspend fun runLoop() {
        recovery.reset()
        Log.i(TAG, "Connection loop started")
        while (active.get()) {
            if (!active.get()) break
            val config = settingsStore.settings.value.serverConfig
            _coreState.value = CoreState.CONNECTING
            recovery.reset()
            val alive = Channel<Unit>(Channel.CONFLATED)

            try {
                val probe = probeStatus()
                if (!probe.status.isOnline) {
                    _state.value = ConnectionState.Disconnected(
                        probe.note ?: "Backend reported status '${probe.status.status}'"
                    )
                } else {
                    _status.value = probe.status
                    _latencyMs.value = probe.latencyMs
                    _state.value = ConnectionState.Connected(config.displayUrl(), probe.status)
                    _coreState.value = CoreState.CONNECTED

                    history.addSystem("Connected to JARVIS at ${config.displayUrl()}")

                    startSse(alive)
                    startHealth(alive)

                    // Block until the connection is lost (SSE close or a failed probe).
                    alive.receive()
                    Log.w(TAG, "Connection lost, scheduling recovery")
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.w(TAG, "Connection loop error: ${e.message}", e)
            } finally {
                stopPeripherals()
            }

            if (!active.get()) break

            // ── Recovery ──────────────────────────────────────────────
            if (!recovery.shouldContinue()) {
                _state.value = ConnectionState.Disconnected("Max retries reached")
                _coreState.value = CoreState.ERROR
                break
            }
            val delayMs = recovery.nextDelay()
            _state.value = ConnectionState.Reconnecting(recovery.attempts, delayMs, reason())
            _coreState.value = CoreState.CONNECTING
            Log.i(TAG, "Reconnecting in ${delayMs}ms (attempt ${recovery.attempts})")
            delay(delayMs)
        }
    }

    private fun reason(): String? = when (_state.value) {
        is ConnectionState.Connected -> "Stream interrupted"
        is ConnectionState.Error -> (_state.value as ConnectionState.Error).message
        is ConnectionState.Disconnected -> (_state.value as ConnectionState.Disconnected).reason
        else -> "Connection lost"
    }

    private suspend fun probeStatus(): ProbeResult {
        val started = System.nanoTime()
        val status = api.status()
        val latencyMs = (System.nanoTime() - started) / 1_000_000
        if (status == null || !status.isOnline) {
            return ProbeResult(JarvisStatus("offline", null, null, null), latencyMs, "No status reply")
        }
        return ProbeResult(status, latencyMs, null)
    }

    private data class ProbeResult(val status: JarvisStatus, val latencyMs: Long, val note: String?)

    private fun startSse(alive: Channel<Unit>) {
        sse.onClosed = {
            alive.trySend(Unit)
            Log.w(TAG, "SSE stream closed")
        }
        sse.onError = { alive.trySend(Unit) }
        sse.start()
        sseCollector = scope.launch {
            sse.events.collect { event -> handleEvent(event) }
        }
    }

    private fun handleEvent(event: JarvisEvent) {
        if (event.type == "permission_required") {
            val req = PendingPermissionRequest.fromJson(event.data)
            if (req != null) {
                _pendingPermission.value = req
                _coreState.value = CoreState.PERMISSION_REQUIRED
            }
        } else if (event.type == "permission_decided") {
            _pendingPermission.value = null
            _coreState.value = CoreState.CONNECTED
        }

        event.coreTransition()?.let { transition ->
            // ERROR is transient while the stream stays up (a task failed, not the link).
            if (transition != CoreState.ERROR || _coreState.value != CoreState.CONNECTED) {
                _coreState.value = transition
            }
            if (transition == CoreState.ERROR) {
                history.addResult(
                    event.data?.stringOrNull("error").orEmpty(),
                    "Task failed",
                    com.ultron.ai.data.model.EntryStatus.FAILED
                )
            }
        }
    }

    private fun startHealth(alive: Channel<Unit>) {
        healthJob = scope.launch {
            while (isActive) {
                delay(HEALTH_INTERVAL_MS)
                val ok = runCatching { api.status()?.isOnline == true }.getOrDefault(false)
                if (!ok) {
                    alive.trySend(Unit)
                    break
                }
            }
        }
    }

    private fun stopPeripherals() {
        sseCollector?.cancel()
        sseCollector = null
        healthJob?.cancel()
        healthJob = null
        sse.stop()
        sse.onClosed = null
        sse.onError = null
    }

    companion object {
        private const val TAG = "ConnectionManager"
        private const val HEALTH_INTERVAL_MS = 10_000L
    }
}