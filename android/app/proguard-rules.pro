# ProGuard rules for ULTRON AI
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.ultron.ai.** { *; }
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
