package com.ultron.ai.ui.core

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.ultron.ai.data.model.CoreState
import com.ultron.ai.ui.theme.JarvisAmber
import com.ultron.ai.ui.theme.JarvisCyan
import com.ultron.ai.ui.theme.JarvisGray
import com.ultron.ai.ui.theme.JarvisOrange
import com.ultron.ai.ui.theme.JarvisRed
import com.ultron.ai.ui.theme.JarvisTeal
import com.ultron.ai.ui.theme.JarvisYellow
import kotlin.math.min

/** Module 6 — visual mapping of JARVIS core state → color and label. */

fun coreColor(state: CoreState): Color = when (state) {
    CoreState.IDLE -> JarvisGray
    CoreState.CONNECTING -> JarvisAmber
    CoreState.CONNECTED -> JarvisCyan
    CoreState.THINKING -> JarvisTeal
    CoreState.LISTENING -> JarvisOrange
    CoreState.SPEAKING -> JarvisYellow
    CoreState.ERROR -> JarvisRed
    CoreState.PERMISSION_REQUIRED -> JarvisAmber
}

fun coreLabel(state: CoreState): String = when (state) {
    CoreState.IDLE -> "JARVIS CORE — STANDBY"
    CoreState.CONNECTING -> "ESTABLISHING LINK"
    CoreState.CONNECTED -> "SYSTEMS ONLINE"
    CoreState.THINKING -> "PROCESSING REQUEST"
    CoreState.LISTENING -> "LISTENING"
    CoreState.SPEAKING -> "RESPONDING"
    CoreState.ERROR -> "FAULT DETECTED"
    CoreState.PERMISSION_REQUIRED -> "PERMISSION REQUIRED"
}

fun CoreState.isAnimated(): Boolean =
    this in setOf(CoreState.CONNECTING, CoreState.THINKING, CoreState.LISTENING, CoreState.SPEAKING, CoreState.PERMISSION_REQUIRED)

/**
 * Module 6 — the animated JARVIS core orb.
 *
 * A canvas glyph whose color, glow and sweep animation track [CoreState].
 */
@Composable
fun JarvisCoreView(
    state: CoreState,
    modifier: Modifier = Modifier,
    diameter: Dp = 220.dp
) {
    val color = coreColor(state)
    val infinite = rememberInfiniteTransition(label = "jarvisCore")

    val pulse by infinite.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "corePulse"
    )

    val spin by infinite.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 9000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "coreSpin"
    )

    Canvas(modifier = modifier.size(diameter)) {
        val r = min(size.width, size.height)
        val center = Offset(size.width / 2f, size.height / 2f)
        val brightness = if (state.isAnimated()) pulse else 0.55f

        // Outer radial glow
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    color.copy(alpha = 0.30f * brightness),
                    color.copy(alpha = 0f)
                ),
                center = center,
                radius = r * 0.58f
            ),
            radius = r * 0.58f,
            center = center
        )

        // Fixed outer ring
        drawCircle(
            color = color.copy(alpha = 0.35f * brightness),
            radius = r * 0.40f,
            center = center,
            style = Stroke(width = r * 0.012f)
        )

        // Rotating sweep arc while the core is active
        if (state.isAnimated()) {
            drawArc(
                color = color.copy(alpha = 0.9f * pulse),
                startAngle = spin,
                sweepAngle = 95f,
                useCenter = false,
                topLeft = Offset(center.x - r * 0.40f, center.y - r * 0.40f),
                size = Size(r * 0.80f, r * 0.80f),
                style = Stroke(width = r * 0.022f, cap = StrokeCap.Round)
            )
        }

        // Core disc
        drawCircle(
            color = color.copy(alpha = 0.85f + 0.15f * brightness),
            radius = r * 0.22f,
            center = center
        )

        // Inner glow / specular highlight
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    Color.White.copy(alpha = 0.55f * brightness),
                    Color.White.copy(alpha = 0f)
                )
            ),
            radius = r * 0.11f,
            center = Offset(center.x - r * 0.05f, center.y - r * 0.05f)
        )
        drawCircle(
            color = Color.White.copy(alpha = 0.9f * brightness),
            radius = r * 0.03f,
            center = Offset(center.x - r * 0.06f, center.y - r * 0.06f)
        )
    }
}