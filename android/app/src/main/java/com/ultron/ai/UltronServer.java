package com.ultron.ai;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

import fi.iki.elonen.NanoHTTPD;

public class UltronServer extends NanoHTTPD {

    private static final String TAG = "UltronServer";
    private static final int PORT = 8080;
    private final Context context;
    private final PhoneController phone;
    private final Gson gson = new Gson();

    public UltronServer(Context context) {
        super(PORT);
        this.context = context;
        this.phone = new PhoneController(context);
    }

    public void startServer() throws IOException {
        start(NanoHTTPD.SOCKET_READ_TIMEOUT, false);
        Log.i(TAG, "ULTRON server running on http://127.0.0.1:" + PORT);
    }

    @Override
    public Response serve(IHTTPSession session) {
        String uri = session.getUri();
        Method method = session.getMethod();
        Map<String, String> params = session.getParms();

        // CORS headers
        String origin = session.getHeaders().get("origin");

        // API routes
        if (uri.startsWith("/api/")) {
            return handleApi(uri, method, session, params);
        }

        // Serve static files from assets
        return serveAsset(uri);
    }

    private Response handleApi(String uri, Method method, IHTTPSession session, Map<String, String> params) {
        JsonObject response = new JsonObject();

        try {
            switch (uri) {
                case "/api/status":
                    response.addProperty("status", "online");
                    response.addProperty("server", "ultron-android-native");
                    response.addProperty("version", "2.0.0-standalone");
                    break;

                case "/api/device":
                    response = phone.getDeviceInfo();
                    break;

                case "/api/battery":
                    response = phone.getBatteryInfo();
                    break;

                case "/api/screen":
                    response = phone.getScreenInfo();
                    break;

                case "/api/storage":
                    response = phone.getStorageInfo();
                    break;

                case "/api/memory":
                    response = phone.getMemoryInfo();
                    break;

                case "/api/contacts":
                    int cLimit = params.containsKey("limit") ? Integer.parseInt(params.get("limit")) : 50;
                    return jsonResponse(phone.getContacts(cLimit));

                case "/api/sms":
                    String box = params.get("box");
                    int sLimit = params.containsKey("limit") ? Integer.parseInt(params.get("limit")) : 20;
                    return jsonResponse(phone.getSmsList(box, sLimit));

                case "/api/call-log":
                    int clLimit = params.containsKey("limit") ? Integer.parseInt(params.get("limit")) : 20;
                    return jsonResponse(phone.getCallLog(clLimit));

                case "/api/volume":
                    response = phone.getVolumeInfo();
                    break;

                case "/api/wifi":
                    response = phone.getWifiInfo();
                    break;

                case "/api/location":
                    response = phone.getLastKnownLocation();
                    break;

                case "/api/apps":
                    return jsonResponse(phone.getInstalledApps());

                case "/api/clipboard":
                    String clip = phone.getClipboard();
                    response.addProperty("text", clip);
                    break;

                case "/api/android":
                    response.addProperty("status", "active");
                    response.addProperty("control_type", "standalone-java");
                    response.addProperty("termux", false);
                    break;

                default:
                    // POST actions
                    if (method == Method.POST) {
                        return handlePostAction(uri, session);
                    }
                    response.addProperty("error", "Unknown endpoint: " + uri);
                    break;
            }
        } catch (Exception e) {
            response.addProperty("error", e.getMessage());
        }

        return jsonResponse(response);
    }

    private Response handlePostAction(String uri, IHTTPSession session) {
        JsonObject body = parseBody(session);
        JsonObject response = new JsonObject();

        try {
            switch (uri) {
                case "/api/sms/send":
                    String number = body.has("number") ? body.get("number").getAsString() : "";
                    String msg = body.has("message") ? body.get("message").getAsString() : "";
                    response.addProperty("success", phone.sendSms(number, msg));
                    break;

                case "/api/call":
                    String callNum = body.has("number") ? body.get("number").getAsString() : "";
                    response.addProperty("success", phone.makeCall(callNum));
                    break;

                case "/api/notification":
                    String title = body.has("title") ? body.get("title").getAsString() : "ULTRON";
                    String text = body.has("message") ? body.get("message").getAsString() : "";
                    int notifId = body.has("id") ? body.get("id").getAsInt() : (int)(System.currentTimeMillis() % 10000);
                    phone.sendNotification(title, text, notifId);
                    response.addProperty("success", true);
                    break;

                case "/api/alarm":
                    int hour = body.has("hour") ? body.get("hour").getAsInt() : 8;
                    int minute = body.has("minute") ? body.get("minute").getAsInt() : 0;
                    String alarmMsg = body.has("message") ? body.get("message").getAsString() : "ULTRON Alarm";
                    response.addProperty("success", phone.setAlarm(hour, minute, alarmMsg));
                    break;

                case "/api/volume/set":
                    int vol = body.has("level") ? body.get("level").getAsInt() : 50;
                    phone.setVolume(vol);
                    response.addProperty("success", true);
                    break;

                case "/api/brightness":
                    int bright = body.has("level") ? body.get("level").getAsInt() : 128;
                    phone.setScreenBrightness(bright);
                    response.addProperty("success", true);
                    break;

                case "/api/vibrate":
                    int ms = body.has("duration") ? body.get("duration").getAsInt() : 500;
                    phone.vibrate(ms);
                    response.addProperty("success", true);
                    break;

                case "/api/wifi/toggle":
                    boolean enabled = body.has("enabled") && body.get("enabled").getAsBoolean();
                    response.addProperty("success", phone.setWifiEnabled(enabled));
                    break;

                case "/api/clipboard/set":
                    String clipText = body.has("text") ? body.get("text").getAsString() : "";
                    phone.setClipboard(clipText);
                    response.addProperty("success", true);
                    break;

                case "/api/open":
                    if (body.has("package")) {
                        phone.openApp(body.get("package").getAsString());
                    } else if (body.has("url")) {
                        phone.openUrl(body.get("url").getAsString());
                    }
                    response.addProperty("success", true);
                    break;

                case "/api/ai/chat":
                    String aiMsg = body.has("message") ? body.get("message").getAsString() : "";
                    String apiKey = body.has("api_key") ? body.get("api_key").getAsString() : "";
                    if (apiKey.isEmpty()) {
                        apiKey = getApiKey();
                    }
                    String aiResponse = phone.chatWithAI(aiMsg, apiKey);
                    response.addProperty("response", aiResponse);
                    break;

                default:
                    response.addProperty("error", "Unknown action: " + uri);
                    break;
            }
        } catch (Exception e) {
            response.addProperty("error", e.getMessage());
        }

        return jsonResponse(response);
    }

    private Response serveAsset(String uri) {
        if (uri.equals("/") || uri.isEmpty()) uri = "/index.html";

        String assetPath = "web" + uri;

        try {
            InputStream is = context.getAssets().open(assetPath);
            String mimeType = getMimeType(uri);
            return newChunkedResponse(Response.Status.OK, mimeType, is);
        } catch (IOException e) {
            // Try without web/ prefix
            try {
                InputStream is = context.getAssets().open(uri.substring(1));
                String mimeType = getMimeType(uri);
                return newChunkedResponse(Response.Status.OK, mimeType, is);
            } catch (IOException e2) {
                return newFixedLengthResponse(Response.Status.NOT_FOUND,
                    "text/plain", "404 Not Found: " + uri);
            }
        }
    }

    private String getMimeType(String uri) {
        if (uri.endsWith(".html") || uri.endsWith(".htm")) return "text/html";
        if (uri.endsWith(".css")) return "text/css";
        if (uri.endsWith(".js")) return "application/javascript";
        if (uri.endsWith(".json")) return "application/json";
        if (uri.endsWith(".png")) return "image/png";
        if (uri.endsWith(".jpg") || uri.endsWith(".jpeg")) return "image/jpeg";
        if (uri.endsWith(".svg")) return "image/svg+xml";
        if (uri.endsWith(".ico")) return "image/x-icon";
        if (uri.endsWith(".woff")) return "font/woff";
        if (uri.endsWith(".woff2")) return "font/woff2";
        return "text/plain";
    }

    private JsonObject parseBody(IHTTPSession session) {
        Map<String, String> bodyMap = new HashMap<>();
        try {
            session.parseBody(bodyMap);
            String jsonStr = bodyMap.get("postData");
            if (jsonStr != null) {
                return gson.fromJson(jsonStr, JsonObject.class);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error parsing body", e);
        }
        return new JsonObject();
    }

    private Response jsonResponse(JsonObject obj) {
        String json = gson.toJson(obj);
        NanoHTTPD.Response resp = newFixedLengthResponse(Response.Status.OK,
            "application/json", json);
        resp.addHeader("Access-Control-Allow-Origin", "*");
        return resp;
    }

    private Response jsonResponse(JsonArray arr) {
        String json = gson.toJson(arr);
        NanoHTTPD.Response resp = newFixedLengthResponse(Response.Status.OK,
            "application/json", json);
        resp.addHeader("Access-Control-Allow-Origin", "*");
        return resp;
    }

    private String getApiKey() {
        SharedPreferences prefs = context.getSharedPreferences("ultron", Context.MODE_PRIVATE);
        return prefs.getString("api_key", "");
    }
}
