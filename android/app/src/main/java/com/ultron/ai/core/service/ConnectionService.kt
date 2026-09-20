package com.ultron.ai.core.service

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.ultron.ai.JarvisApp
import com.ultron.ai.R
import com.ultron.ai.core.connection.ConnectionState
import com.ultron.ai.core.connection.subtitle
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Module 15 (companion) — keeps the JARVIS connection alive while the app is
 * backgrounded. Started from Settings ("Keep alive") via startForegroundService;
 * reflects live connection state in a non-dismissable notification.
 */
class ConnectionService : Service() {

    private val app get() = application as JarvisApp
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        app.container.connectionManager.start()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification(getString(R.string.notif_connecting)))
        scope.launch {
            app.container.connectionManager.state.collectLatest { state ->
                updateNotification(state)
            }
        }
        return START_STICKY
    }

    private fun updateNotification(state: ConnectionState) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as android.app.NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification(state.subtitle().orEmpty()))
    }

    private fun buildNotification(text: String): Notification =
        NotificationCompat.Builder(this, JarvisApp.CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_jarvis)
            .setContentTitle(getString(R.string.notif_title))
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()

    override fun onDestroy() {
        scope.cancel()
        app.container.connectionManager.stop()
        super.onDestroy()
    }

    companion object {
        private const val NOTIFICATION_ID = 9001
    }
}