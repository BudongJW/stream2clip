package io.github.budongjw.stream2clip

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** The desktop app's colors (`src/stream2clip/brand.py`, `gui/theme.py`): dark ink, live pink, highlight yellow. */
object Brand {
    val Ink = Color(0xFF15131F)
    val Surface = Color(0xFF1D1A29)
    val Surface2 = Color(0xFF26223A)
    val Border = Color(0xFF332E48)
    val Muted = Color(0xFFA39DB3)
    val Paper = Color(0xFFF7F4FA)
    val Pink = Color(0xFFFF4F8B)
    val PinkLight = Color(0xFFFF7AA8)
    val Highlight = Color(0xFFFFD84D)
}

/** Always dark, like the desktop app and the brand's lockup (`logo_lockup.png` is the on-dark version). */
@Composable
fun Stream2clipTheme(content: @Composable () -> Unit) {
    val colors = darkColorScheme(
        primary = Brand.Pink,
        onPrimary = Brand.Ink,
        primaryContainer = Brand.Pink.copy(alpha = 0.16f),
        onPrimaryContainer = Brand.PinkLight,
        secondary = Brand.Highlight,
        onSecondary = Brand.Ink,
        background = Brand.Ink,
        onBackground = Brand.Paper,
        surface = Brand.Ink,
        onSurface = Brand.Paper,
        surfaceVariant = Brand.Surface2,
        onSurfaceVariant = Brand.Muted,
        surfaceContainer = Brand.Surface,
        surfaceContainerHigh = Brand.Surface2,
        surfaceContainerHighest = Brand.Surface2,
        outline = Brand.Border,
        outlineVariant = Brand.Border,
        error = Color(0xFFFF8A8A),
    )
    val base = Typography()
    val typography = base.copy(
        titleLarge = base.titleLarge.copy(fontWeight = FontWeight.ExtraBold),
        titleMedium = base.titleMedium.copy(fontWeight = FontWeight.Bold),
        titleSmall = base.titleSmall.copy(fontWeight = FontWeight.Bold, fontSize = 15.sp, lineHeight = 21.sp),
        labelSmall = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.6.sp),
    )
    MaterialTheme(colorScheme = colors, typography = typography, content = content)
}
