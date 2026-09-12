package com.ultron.ai;

import android.Manifest;
import android.app.AlarmManager;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.location.Location;
import android.location.LocationManager;
import android.media.AudioManager;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.CallLog;
import android.provider.ContactsContract;
import android.provider.Settings;
import android.telephony.SmsManager;
import android.telephony.TelephonyManager;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class PhoneController {

    private final Context context;
    private final Gson gson = new Gson();

    public PhoneController(Context context) {
        this.context = context;
    }

    // ── Battery ──────────────────────────────────────────────

    public JsonObject getBatteryInfo() {
        JsonObject info = new JsonObject();
        BatteryManager bm = (BatteryManager) context.getSystemService(Context.BATTERY_SERVICE);
        if (bm != null) {
            int level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            info.addProperty("level", level);
            info.addProperty("charging", bm.isCharging());
            int status = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS);
            String statusStr;
            switch (status) {
                case BatteryManager.BATTERY_STATUS_CHARGING: statusStr = "charging"; break;
                case BatteryManager.BATTERY_STATUS_DISCHARGING: statusStr = "discharging"; break;
                case BatteryManager.BATTERY_STATUS_FULL: statusStr = "full"; break;
                default: statusStr = "unknown"; break;
            }
            info.addProperty("status", statusStr);
        }
        return info;
    }

    // ── Device Info ──────────────────────────────────────────

    public JsonObject getDeviceInfo() {
        JsonObject info = new JsonObject();
        info.addProperty("model", Build.MODEL);
        info.addProperty("manufacturer", Build.MANUFACTURER);
        info.addProperty("device", Build.DEVICE);
        info.addProperty("android_version", Build.VERSION.RELEASE);
        info.addProperty("sdk_version", Build.VERSION.SDK_INT);
        info.addProperty("product", Build.PRODUCT);
        info.addProperty("board", Build.BOARD);
        info.addProperty("hardware", Build.HARDWARE);
        info.addProperty("fingerprint", Build.FINGERPRINT);
        return info;
    }

    public JsonObject getScreenInfo() {
        JsonObject info = new JsonObject();
        WindowManager wm = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        if (wm != null) {
            DisplayMetrics dm = new DisplayMetrics();
            wm.getDefaultDisplay().getMetrics(dm);
            info.addProperty("width", dm.widthPixels);
            info.addProperty("height", dm.heightPixels);
            info.addProperty("density", dm.density);
            info.addProperty("densityDpi", dm.densityDpi);
        }
        return info;
    }

    public JsonObject getStorageInfo() {
        JsonObject info = new JsonObject();
        android.os.StatFs stat = new android.os.StatFs("/data");
        long total = stat.getTotalBytes();
        long free = stat.getAvailableBytes();
        long used = total - free;
        info.addProperty("total_gb", Math.round(total / 1e9));
        info.addProperty("used_gb", Math.round(used / 1e9));
        info.addProperty("free_gb", Math.round(free / 1e9));
        info.addProperty("usage_percent", Math.round(used * 100.0 / total));
        return info;
    }

    public JsonObject getMemoryInfo() {
        JsonObject info = new JsonObject();
        Runtime rt = Runtime.getRuntime();
        long maxMem = rt.maxMemory();
        long totalMem = rt.totalMemory();
        long freeMem = rt.freeMemory();
        info.addProperty("max_mb", maxMem / (1024 * 1024));
        info.addProperty("total_mb", totalMem / (1024 * 1024));
        info.addProperty("free_mb", freeMem / (1024 * 1024));
        info.addProperty("used_mb", (totalMem - freeMem) / (1024 * 1024));
        return info;
    }

    // ── SMS ──────────────────────────────────────────────────

    public boolean sendSms(String number, String message) {
        try {
            SmsManager sms = SmsManager.getDefault();
            sms.sendTextMessage(number, null, message, null, null);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public JsonArray getSmsList(String box, int limit) {
        JsonArray list = new JsonArray();
        String uri = "content://sms/" + (box != null ? box : "inbox");
        try {
            Cursor cursor = context.getContentResolver().query(
                Uri.parse(uri), null, null, null, "date DESC");
            if (cursor != null) {
                int count = 0;
                while (cursor.moveToNext() && count < limit) {
                    JsonObject sms = new JsonObject();
                    sms.addProperty("id", cursor.getLong(cursor.getColumnIndexOrThrow("_id")));
                    sms.addProperty("address", cursor.getString(cursor.getColumnIndexOrThrow("address")));
                    sms.addProperty("body", cursor.getString(cursor.getColumnIndexOrThrow("body")));
                    sms.addProperty("date", cursor.getLong(cursor.getColumnIndexOrThrow("date")));
                    sms.addProperty("read", cursor.getInt(cursor.getColumnIndexOrThrow("read")));
                    list.add(sms);
                    count++;
                }
                cursor.close();
            }
        } catch (Exception e) {
            // Permission denied
        }
        return list;
    }

    // ── Calls ────────────────────────────────────────────────

    public boolean makeCall(String number) {
        try {
            Intent intent = new Intent(Intent.ACTION_CALL);
            intent.setData(Uri.parse("tel:" + number));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public JsonArray getCallLog(int limit) {
        JsonArray list = new JsonArray();
        try {
            Cursor cursor = context.getContentResolver().query(
                CallLog.Calls.CONTENT_URI,
                null, null, null,
                CallLog.Calls.DATE + " DESC");
            if (cursor != null) {
                int count = 0;
                while (cursor.moveToNext() && count < limit) {
                    JsonObject call = new JsonObject();
                    call.addProperty("number", cursor.getString(cursor.getColumnIndexOrThrow(CallLog.Calls.NUMBER)));
                    call.addProperty("name", cursor.getString(cursor.getColumnIndexOrThrow(CallLog.Calls.CACHED_NAME)));
                    call.addProperty("type", cursor.getInt(cursor.getColumnIndexOrThrow(CallLog.Calls.TYPE)));
                    call.addProperty("date", cursor.getLong(cursor.getColumnIndexOrThrow(CallLog.Calls.DATE)));
                    call.addProperty("duration", cursor.getInt(cursor.getColumnIndexOrThrow(CallLog.Calls.DURATION)));
                    list.add(call);
                    count++;
                }
                cursor.close();
            }
        } catch (Exception e) {
            // Permission denied
        }
        return list;
    }

    // ── Contacts ─────────────────────────────────────────────

    public JsonArray getContacts(int limit) {
        JsonArray list = new JsonArray();
        try {
            Cursor cursor = context.getContentResolver().query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                new String[]{
                    ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                },
                null, null,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC");
            if (cursor != null) {
                int count = 0;
                java.util.Set<String> seen = new java.util.HashSet<>();
                while (cursor.moveToNext() && count < limit) {
                    String id = cursor.getString(0);
                    String name = cursor.getString(1);
                    String number = cursor.getString(2);
                    if (id != null && !seen.contains(id)) {
                        seen.add(id);
                        JsonObject contact = new JsonObject();
                        contact.addProperty("id", id);
                        contact.addProperty("name", name);
                        contact.addProperty("number", number);
                        list.add(contact);
                        count++;
                    }
                }
                cursor.close();
            }
        } catch (Exception e) {
            // Permission denied
        }
        return list;
    }

    public boolean addContact(String name, String number) {
        try {
            ArrayList<ContentValues> data = new ArrayList<>();

            ContentValues nameRow = new ContentValues();
            nameRow.put(ContactsContract.Data.MIMETYPE,
                ContactsContract.CommonDataKinds.StructuredName.CONTENT_ITEM_TYPE);
            nameRow.put(ContactsContract.CommonDataKinds.StructuredName.DISPLAY_NAME, name);
            data.add(nameRow);

            ContentValues phoneRow = new ContentValues();
            phoneRow.put(ContactsContract.Data.MIMETYPE,
                ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE);
            phoneRow.put(ContactsContract.CommonDataKinds.Phone.NUMBER, number);
            phoneRow.put(ContactsContract.CommonDataKinds.Phone.TYPE,
                ContactsContract.CommonDataKinds.Phone.TYPE_MOBILE);
            data.add(phoneRow);

            Intent intent = new Intent(Intent.ACTION_INSERT_OR_EDIT);
            intent.setType(ContactsContract.Contacts.CONTENT_ITEM_TYPE);
            intent.putExtra(ContactsContract.Intents.Insert.NAME, name);
            intent.putExtra(ContactsContract.Intents.Insert.PHONE, number);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // ── Notifications ────────────────────────────────────────

    public void sendNotification(String title, String message, int id) {
        android.app.Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new android.app.Notification.Builder(context, UltronApp.CHANNEL_ID);
        } else {
            builder = new android.app.Notification.Builder(context);
        }
        builder.setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(message)
            .setAutoCancel(true);

        NotificationManager nm = (NotificationManager)
            context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(id, builder.build());
        }
    }

    // ── Alarm ────────────────────────────────────────────────

    public boolean setAlarm(int hour, int minute, String message) {
        try {
            Intent intent = new Intent("android.intent.action.SET_ALARM");
            intent.putExtra("android.intent.extra.alarm.HOUR", hour);
            intent.putExtra("android.intent.extra.alarm.MINUTES", minute);
            intent.putExtra("android.intent.extra.alarm.MESSAGE",
                message != null ? message : "ULTRON Alarm");
            intent.putExtra("android.intent.extra.alarm.SKIP_UI", true);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // ── Media / Volume ───────────────────────────────────────

    public JsonObject getVolumeInfo() {
        JsonObject info = new JsonObject();
        AudioManager am = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (am != null) {
            int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
            int current = am.getStreamVolume(AudioManager.STREAM_MUSIC);
            info.addProperty("music_current", current);
            info.addProperty("music_max", max);
            info.addProperty("music_percent", max > 0 ? Math.round(current * 100.0 / max) : 0);
            info.addProperty("ringer_mode", am.getRingerMode());
            info.addProperty("is_silent", am.getRingerMode() == AudioManager.RINGER_MODE_SILENT);
        }
        return info;
    }

    public void setVolume(int level) {
        AudioManager am = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (am != null) {
            int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
            int vol = Math.max(0, Math.min(level, max));
            am.setStreamVolume(AudioManager.STREAM_MUSIC, vol, 0);
        }
    }

    public void vibrate(int ms) {
        Vibrator v = (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
        if (v != null && v.hasVibrator()) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                v.vibrate(ms);
            }
        }
    }

    // ── Screen ───────────────────────────────────────────────

    public void setScreenBrightness(int level) {
        try {
            int brightness = Math.max(0, Math.min(level, 255));
            Settings.System.putInt(context.getContentResolver(),
                Settings.System.SCREEN_BRIGHTNESS, brightness);
        } catch (Exception e) {
            // Permission denied
        }
    }

    // ── Connectivity ─────────────────────────────────────────

    public JsonObject getWifiInfo() {
        JsonObject info = new JsonObject();
        WifiManager wm = (WifiManager) context.getApplicationContext()
            .getSystemService(Context.WIFI_SERVICE);
        if (wm != null) {
            info.addProperty("enabled", wm.isWifiEnabled());
            if (wm.getConnectionInfo() != null) {
                info.addProperty("ssid", wm.getConnectionInfo().getSSID());
                info.addProperty("rssi", wm.getConnectionInfo().getRssi());
                info.addProperty("link_speed", wm.getConnectionInfo().getLinkSpeed());
            }
        }
        return info;
    }

    public boolean setWifiEnabled(boolean enabled) {
        WifiManager wm = (WifiManager) context.getApplicationContext()
            .getSystemService(Context.WIFI_SERVICE);
        if (wm != null) {
            wm.setWifiEnabled(enabled);
            return true;
        }
        return false;
    }

    // ── Clipboard ────────────────────────────────────────────

    public String getClipboard() {
        android.content.ClipboardManager cm = (android.content.ClipboardManager)
            context.getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null && cm.hasPrimaryClip()) {
            android.content.ClipData clip = cm.getPrimaryClip();
            if (clip != null && clip.getItemCount() > 0) {
                CharSequence text = clip.getItemAt(0).getText();
                return text != null ? text.toString() : "";
            }
        }
        return "";
    }

    public void setClipboard(String text) {
        android.content.ClipboardManager cm = (android.content.ClipboardManager)
            context.getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null) {
            android.content.ClipData clip = android.content.ClipData.newPlainText("ULTRON", text);
            cm.setPrimaryClip(clip);
        }
    }

    // ── Installed Apps ───────────────────────────────────────

    public JsonArray getInstalledApps() {
        JsonArray list = new JsonArray();
        android.content.pm.PackageManager pm = context.getPackageManager();
        List<android.content.pm.ApplicationInfo> apps = pm.getInstalledApplications(0);
        for (android.content.pm.ApplicationInfo app : apps) {
            JsonObject obj = new JsonObject();
            obj.addProperty("package", app.packageName);
            obj.addProperty("name", pm.getApplicationLabel(app).toString());
            obj.addProperty("system", (app.flags & android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0);
            list.add(obj);
        }
        return list;
    }

    // ── Location ─────────────────────────────────────────────

    public JsonObject getLastKnownLocation() {
        JsonObject loc = new JsonObject();
        LocationManager lm = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
        if (lm != null) {
            try {
                Location last = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER);
                if (last == null) last = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
                if (last != null) {
                    loc.addProperty("latitude", last.getLatitude());
                    loc.addProperty("longitude", last.getLongitude());
                    loc.addProperty("accuracy", last.getAccuracy());
                    loc.addProperty("time", last.getTime());
                    loc.addProperty("provider", last.getProvider());
                } else {
                    loc.addProperty("error", "No location available");
                }
            } catch (SecurityException e) {
                loc.addProperty("error", "Location permission denied");
            }
        }
        return loc;
    }

    // ── AI Chat (OpenRouter) ─────────────────────────────────

    public String chatWithAI(String message, String apiKey) {
        try {
            URL url = new URL("https://openrouter.ai/api/v1/chat/completions");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Authorization", "Bearer " + apiKey);
            conn.setDoOutput(true);
            conn.setConnectTimeout(30000);
            conn.setReadTimeout(60000);

            JsonObject body = new JsonObject();
            body.addProperty("model", "google/gemma-3-27b-it:free");
            body.addProperty("max_tokens", 2048);

            JsonArray messages = new JsonArray();
            JsonObject sysMsg = new JsonObject();
            sysMsg.addProperty("role", "system");
            sysMsg.addProperty("content", "You are ULTRON, a helpful AI assistant with control over an Android phone. Be concise and helpful.");
            messages.add(sysMsg);

            JsonObject userMsg = new JsonObject();
            userMsg.addProperty("role", "user");
            userMsg.addProperty("content", message);
            messages.add(userMsg);

            body.add("messages", messages);

            OutputStream os = conn.getOutputStream();
            os.write(body.toString().getBytes("UTF-8"));
            os.flush();
            os.close();

            int responseCode = conn.getResponseCode();
            BufferedReader reader;
            if (responseCode >= 200 && responseCode < 300) {
                reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
            } else {
                reader = new BufferedReader(new InputStreamReader(conn.getErrorStream()));
            }

            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            reader.close();
            conn.disconnect();

            JsonObject resp = gson.fromJson(response.toString(), JsonObject.class);
            if (resp.has("choices") && resp.getAsJsonArray("choices").size() > 0) {
                JsonObject choice = resp.getAsJsonArray("choices").get(0).getAsJsonObject();
                if (choice.has("message")) {
                    return choice.getAsJsonObject("message").get("content").getAsString();
                }
            }
            if (resp.has("error")) {
                return "API Error: " + resp.getAsJsonObject("error").get("message").getAsString();
            }
            return "No response from AI";

        } catch (Exception e) {
            return "Error: " + e.getMessage();
        }
    }

    // ── System ───────────────────────────────────────────────

    public void openApp(String packageName) {
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(packageName);
        if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        }
    }

    public void openUrl(String url) {
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    public void openSettings() {
        Intent intent = new Intent(Settings.ACTION_SETTINGS);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }
}
