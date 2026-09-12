package com.ultron.ai;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.File;
import java.io.InputStreamReader;

/**
 * Background service that runs the ULTRON Python server via Termux.
 * Uses shell commands to start the Python process.
 */
public class TermuxService extends Service {

    private static final String TAG = "UltronService";
    private Process pythonProcess;
    private static final String ULTRON_DIR = "/data/data/com.ultron.ai/files/ultron";

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "ULTRON service created");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(1, createNotification());
        startUltronServer();
        return START_STICKY;
    }

    private void startUltronServer() {
        new Thread(() -> {
            try {
                // Check if Termux is available
                File termuxDir = new File("/data/data/com.termux");
                if (!termuxDir.exists()) {
                    Log.w(TAG, "Termux not installed. ULTRON requires Termux for full control.");
                    Log.w(TAG, "Install Termux from F-Droid: https://f-droid.org/en/packages/com.termux/");
                    return;
                }

                // Build command to run via Termux
                String[] cmd = {
                    "/data/data/com.termux/files/usr/bin/bash",
                    "-c",
                    "cd " + ULTRON_DIR + " && " +
                    "source .venv/bin/activate 2>/dev/null; " +
                    "python -m ultron --headless --lan --port 8080"
                };

                ProcessBuilder pb = new ProcessBuilder(cmd);
                pb.redirectErrorStream(true);
                pb.environment().put("PREFIX", "/data/data/com.termux/files/usr");
                pb.environment().put("HOME", "/data/data/com.termux/files/home");

                pythonProcess = pb.start();

                // Read output
                BufferedReader reader = new BufferedReader(
                    new InputStreamReader(pythonProcess.getInputStream())
                );
                String line;
                while ((line = reader.readLine()) != null) {
                    Log.d(TAG, "ULTRON: " + line);
                }

            } catch (Exception e) {
                Log.e(TAG, "Failed to start ULTRON: " + e.getMessage());
            }
        }).start();
    }

    private Notification createNotification() {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent,
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );

        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new Notification.Builder(this, UltronApp.CHANNEL_ID);
        } else {
            builder = new Notification.Builder(this);
        }

        return builder
            .setContentTitle("ULTRON AI Running")
            .setContentText("Tap to open dashboard")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build();
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (pythonProcess != null) {
            pythonProcess.destroy();
        }
        Log.i(TAG, "ULTRON service destroyed");
    }
}
