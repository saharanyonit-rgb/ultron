# ULTRON AI — Android APK

JARVIS-style personal AI assistant with full phone control, packaged as an Android app.

## What It Does

- **Full Phone Control**: Calls, SMS, contacts, alarms, notifications, WiFi, Bluetooth, brightness, volume
- **Touch Automation**: Tap, swipe, long-press, text input, navigation keys
- **Screen Vision**: Screenshot + AI analysis to read what's on screen
- **Media Control**: Play, pause, skip, volume control
- **Location**: GPS access
- **Voice**: Text-to-speech and speech recognition
- **Background Service**: Runs automatically on boot

## Build the APK

### Option A: Android Studio
1. Open `android/` folder in Android Studio
2. Let Gradle sync
3. Click Run or Build → Build APK(s)

### Option B: Command Line
```bash
cd android/
gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

### Option C: Use Pre-built APK (when available)
Download from releases and install directly.

## Install & Setup

### First Time (on the Android device):
1. Install **Termux** from F-Droid (NOT Play Store)
   - https://f-droid.org/en/packages/com.termux/
2. Install **Termux:API** from F-Droid
   - https://f-droid.org/en/packages/com.termux.api/
3. Install **Termux:Boot** (optional, for auto-start)
   - https://f-droid.org/en/packages/com.termux.boot/
4. Open Termux and run:
   ```bash
   # Clone ULTRON
   git clone https://github.com/saharanyonit-rgb/ultron.git ~/ultron
   cd ~/ultron
   # Run setup
   chmod +x setup_android.sh
   ./setup_android.sh
   # Edit .env with your API key
   nano .env
   ```
5. Open the ULTRON AI app — it connects automatically

### Subsequent Launches:
Just open the ULTRON AI app. The server starts automatically.

## Project Structure

```
android/
├── app/
│   ├── build.gradle                    # App build config
│   ├── src/main/
│   │   ├── AndroidManifest.xml         # Permissions & components
│   │   ├── java/com/ultron/ai/
│   │   │   ├── MainActivity.java       # WebView + splash screen
│   │   │   ├── TermuxService.java      # Background Python server
│   │   │   ├── BootReceiver.java       # Auto-start on boot
│   │   │   └── UltronApp.java          # App + notification channel
│   │   ├── res/
│   │   │   ├── layout/activity_main.xml
│   │   │   └── values/styles.xml
│   │   └── assets/                     # Web assets
│   └── proguard-rules.pro
├── build.gradle                        # Project build config
├── settings.gradle
├── gradlew / gradlew.bat              # Gradle wrapper
├── BUILD_INSTRUCTIONS.md               # Build guide
└── README.md                           # This file
```

## Permissions Requested

| Permission | Purpose |
|-----------|---------|
| CALL_PHONE | Make calls |
| READ_CONTACTS | Phonebook access |
| SEND_SMS / READ_SMS | SMS control |
| ACCESS_FINE_LOCATION | GPS location |
| CAMERA | Screenshot / vision |
| BLUETOOTH / WIFI | Settings control |
| POST_NOTIFICATIONS | Send notifications |
| FOREGROUND_SERVICE | Background operation |
| RECORD_AUDIO | Voice input |
| RECEIVE_BOOT_COMPLETED | Auto-start on boot |

## Architecture

```
┌─────────────────────────┐
│  ULTRON AI APK          │
│  ┌───────────────────┐  │
│  │  WebView          │  │
│  │  (loads UI from   │  │
│  │   localhost:8080) │  │
│  └───────────────────┘  │
│         ↕               │
│  ┌───────────────────┐  │
│  │  TermuxService    │  │
│  │  (runs Python     │  │
│  │   via Termux)     │  │
│  └───────────────────┘  │
│         ↕               │
│  ┌───────────────────┐  │
│  │  ULTRON Python    │  │
│  │  (50+ tools for   │  │
│  │   full control)   │  │
│  └───────────────────┘  │
└─────────────────────────┘
```

## Requirements

- Android 7.0+ (API 24)
- Termux app (from F-Droid)
- Termux:API app
- Gemini API key (free at https://aistudio.google.com/app/apikey)

## License

Proprietary — all rights reserved.
