package io.github.budongjw.stream2clip

import android.content.Context
import android.graphics.Typeface
import androidx.annotation.StringRes

/**
 * Looks for the words on the video. The fonts are five Korean fonts of the desktop app's caption font
 * catalog (`src/stream2clip/fonts.py`), shipped in `assets/fonts` with their licences (SIL Open Font License).
 */
data class OverlayFont(val key: String, val asset: String?, @StringRes val label: Int) {
    fun typeface(context: Context): Typeface =
        asset?.let { Typeface.createFromAsset(context.assets, it) } ?: Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
}

/** A fill and the outline around it, as the desktop's caption looks pair them. */
data class OverlayColor(val key: String, val fill: Int, val edge: Int, @StringRes val label: Int)

data class OverlayPlace(val key: String, @StringRes val label: Int)

object TextLooks {
    val fonts = listOf(
        OverlayFont("black-han-sans", "fonts/BlackHanSans-Regular.ttf", R.string.font_black_han),
        OverlayFont("do-hyeon", "fonts/DoHyeon-Regular.ttf", R.string.font_do_hyeon),
        OverlayFont("jua", "fonts/Jua-Regular.ttf", R.string.font_jua),
        OverlayFont("gothic-a1-black", "fonts/GothicA1-Black.ttf", R.string.font_gothic_black),
        OverlayFont("pretendard-black", "fonts/Pretendard-Black.otf", R.string.font_pretendard),
        OverlayFont("system", null, R.string.font_system),
    )
    val colors = listOf(
        OverlayColor("white", 0xFFFFFFFF.toInt(), 0xFF000000.toInt(), R.string.color_white),
        OverlayColor("yellow", 0xFFFFD84D.toInt(), 0xFF000000.toInt(), R.string.color_yellow),
        OverlayColor("pink", 0xFFFF7AA8.toInt(), 0xFFFFFFFF.toInt(), R.string.color_pink),
    )
    val places = listOf(
        OverlayPlace("top", R.string.place_top),
        OverlayPlace("middle", R.string.place_middle),
        OverlayPlace("bottom", R.string.place_bottom),
    )

    fun font(key: String): OverlayFont = fonts.firstOrNull { it.key == key } ?: fonts.first()
    fun color(key: String): OverlayColor = colors.firstOrNull { it.key == key } ?: colors.first()
    fun place(key: String): OverlayPlace = places.firstOrNull { it.key == key } ?: places.first()
}
