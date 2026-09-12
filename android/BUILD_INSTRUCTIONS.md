# ULTRON AI — Android APK Build

## Prerequisites
- Android Studio (or Android SDK command line tools)
- JDK 17+
- Gradle 8.2+

## Quick Build
```bash
cd android/
./gradlew assembleDebug
```

APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Release Build
```bash
# First, sign the APK
./gradlew assembleRelease
```

## Install on Device
```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

## How It Works
1. The APK opens a WebView that loads `http://127.0.0.1:8080`
2. A background service starts the ULTRON Python server via Termux
3. The WebView connects to the local server
4. Full phone control tools are available through the web UI

## Requirements on Device
- **Termux** must be installed (from F-Droid, not Play Store)
- **Termux:API** must be installed
- First time: run `setup_android.sh` inside Termux to install Python + ULTRON

## Architecture
```
com.ultron.ai
├── MainActivity.java        ← WebView shell + splash screen
├── TermuxService.java       ← Background service running Python
├── BootReceiver.java        ← Auto-start on boot
├── UltronApp.java           ← Application + notification channel
└── UltronBridge.java        ← JavaScript ↔ Android bridge
```
