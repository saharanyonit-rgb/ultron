package com.ultron.ai.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// JARVIS palette
val JarvisCyan = Color(0xFF00E5FF)
val JarvisAmber = Color(0xFFFFB300)
val JarvisPurple = Color(0xFF7C4DFF)
val JarvisOrange = Color(0xFFFF7043)
val JarvisRed = Color(0xFFFF5252)
val JarvisYellow = Color(0xFFFFD54F)
val JarvisTeal = Color(0xFF4FC3F7)
val JarvisGray = Color(0xFF5B6B73)
val JarvisBackground = Color(0xFF05090A)
val JarvisSurface = Color(0xFF0B1215)
val JarvisSurfaceVariant = Color(0xFF101A1F)

private val DarkColors = darkColorScheme(
    primary = JarvisCyan,
    onPrimary = Color(0xFF002022),
    secondary = JarvisAmber,
    onSecondary = Color.Black,
    tertiary = JarvisPurple,
    background = JarvisBackground,
    onBackground = Color(0xFFE6F0F3),
    surface = JarvisSurface,
    onSurface = Color(0xFFE6F0F3),
    surfaceVariant = JarvisSurfaceVariant,
    onSurfaceVariant = Color(0xFF9FB6BE),
    outline = Color(0xFF2A3A42),
    error = JarvisRed,
    onError = Color.Black
)

@Composable
fun JarvisTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography = Typography(),
        content = content
    )
}