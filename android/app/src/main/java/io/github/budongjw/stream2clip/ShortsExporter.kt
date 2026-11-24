package io.github.budongjw.stream2clip

import android.content.ContentValues
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.net.Uri
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import androidx.core.graphics.createBitmap
import androidx.core.graphics.withTranslation
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.effect.BitmapOverlay
import androidx.media3.effect.FrameDropEffect
import androidx.media3.effect.OverlayEffect
import androidx.media3.effect.Presentation
import androidx.media3.effect.StaticOverlaySettings
import androidx.media3.effect.TextureOverlay
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.transformer.Composition
import androidx.media3.transformer.DefaultDecoderFactory
import androidx.media3.transformer.DefaultEncoderFactory
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.Effects
import androidx.media3.transformer.ExoPlayerAssetLoader
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.ProgressHolder
import androidx.media3.transformer.Transformer
import androidx.media3.transformer.VideoEncoderSettings
import com.google.common.collect.ImmutableList
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Cuts one highlight straight from the replay's stream (only that part is downloaded) with Media3 on the
 * phone's own encoder: `shorts` is 1080x1920 with the blurred background, `clip` keeps the stream's frame.
 * The suggested title sits at the top and the original channel in a corner, as the desktop app's
 * `--credit` does. The result goes to Movies/stream2clip.
 */
@UnstableApi
class ShortsExporter(private val context: Context) {
    companion object {
        const val FPS = 30f
        /** YouTube's recommended bitrate for 1080p at 30 fps; the phone's encoder chose about 17 Mbps without it. */
        const val VIDEO_BITRATE = 8_000_000
        /** Lines of text at the top of the clip before the words get smaller, then cut. */
        const val MAX_LINES = 3
    }

    /** `text.caption` is drawn in its font, colour and place: the clip's suggested words, or what the user wrote. */
    suspend fun export(stream: Stream, source: Source, clip: Clip, text: ClipText, form: String, onProgress: (Int) -> Unit): Uri {
        val vertical = form == "shorts"
        val out = File(context.cacheDir, "clip_${clip.rank.toString().padStart(2, '0')}.mp4")
        withContext(Dispatchers.Main) { run(stream, source, clip, text, vertical, out, onProgress) }
        return withContext(Dispatchers.IO) { saveToMovies(out, source, clip) }
    }

    private suspend fun run(stream: Stream, source: Source, clip: Clip, text: ClipText, vertical: Boolean, out: File, onProgress: (Int) -> Unit) =
        suspendCancellableCoroutine { done ->
            val http = DefaultHttpDataSource.Factory()
                .setAllowCrossProtocolRedirects(true)
                .setDefaultRequestProperties(stream.headers.filterKeys { !it.equals("User-Agent", ignoreCase = true) })
            stream.headers.entries.firstOrNull { it.key.equals("User-Agent", ignoreCase = true) }?.let { http.setUserAgent(it.value) }
            val item = MediaItem.Builder()
                .setUri(stream.url)
                .setClippingConfiguration(
                    MediaItem.ClippingConfiguration.Builder()
                        .setStartPositionMs((clip.start * 1000).toLong())
                        .setEndPositionMs((clip.end * 1000).toLong())
                        .build(),
                )
                .build()
            val frame = if (vertical) Pair(1080, 1920) else Pair(1920, 1080)
            val overlay = OverlayEffect(ImmutableList.of<TextureOverlay>(textOverlay(text, source.channel, frame.first, frame.second)))
            // 30 fps, as the desktop app's clips (`default_clip_options`): a 60 fps stream is halved before any other work.
            val fps = FrameDropEffect.createDefaultFrameDropEffect(FPS)
            val video = if (vertical) listOf(fps, BlurFitEffect(frame.first, frame.second), overlay) else listOf(fps, Presentation.createForWidthAndHeight(frame.first, frame.second, Presentation.LAYOUT_SCALE_TO_FIT), overlay)
            val edited = EditedMediaItem.Builder(item).setEffects(Effects(emptyList(), video)).build()
            // The stream's own headers (CHZZK, SOOP) on every request; only video items are cut, so no image loader.
            val loader = ExoPlayerAssetLoader.Factory(
                context,
                DefaultDecoderFactory.Builder(context).build(),
                androidx.media3.common.util.Clock.DEFAULT,
                DefaultMediaSourceFactory(context).setDataSourceFactory(http),
            )
            val handler = Handler(Looper.getMainLooper())
            lateinit var transformer: Transformer
            val poll = object : Runnable {
                val holder = ProgressHolder()
                override fun run() {
                    if (transformer.getProgress(holder) == Transformer.PROGRESS_STATE_AVAILABLE) onProgress(holder.progress)
                    handler.postDelayed(this, 500)
                }
            }
            val encoders = DefaultEncoderFactory.Builder(context)
                .setRequestedVideoEncoderSettings(VideoEncoderSettings.Builder().setBitrate(VIDEO_BITRATE).build())
                .setEnableFallback(true)
                .build()
            transformer = Transformer.Builder(context)
                .setVideoMimeType(MimeTypes.VIDEO_H264)
                .setAudioMimeType(MimeTypes.AUDIO_AAC)
                .setEncoderFactory(encoders)
                .setAssetLoaderFactory(loader)
                .addListener(object : Transformer.Listener {
                    override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                        handler.removeCallbacks(poll)
                        done.resume(Unit)
                    }

                    override fun onError(composition: Composition, exportResult: ExportResult, exportException: ExportException) {
                        handler.removeCallbacks(poll)
                        done.resumeWithException(exportException)
                    }
                })
                .build()
            transformer.start(edited, out.absolutePath)
            handler.post(poll)
            done.invokeOnCancellation {
                handler.removeCallbacks(poll)
                handler.post { transformer.cancel() }
            }
        }

    /**
     * The clip's words at the top, white on a dark outline: as large as fits in [MAX_LINES] lines, down to 70% of the
     * full size before anything is cut. `원본: 채널` goes in the lower left.
     */
    private fun textOverlay(look: ClipText, channel: String, width: Int, height: Int): BitmapOverlay {
        val bitmap = createBitmap(width, height)
        val canvas = Canvas(bitmap)
        val margin = width * 0.06f
        val box = (width - 2 * margin).toInt()
        val text = look.caption.trim()
        val font = TextLooks.font(look.font)
        val colors = TextLooks.color(look.color)
        val face = font.typeface(context)
        // Korean clip channels' Shorts title lines are about 5% of the frame's height (4.5 to 6.5%); 8% of the
        // width draws Hangul at about 4.7% with its outline. Horizontal clips keep a smaller line.
        val full = width * (if (height > width) 0.08f else 0.04f)
        fun paints(size: Float): Pair<TextPaint, TextPaint> {
            val fill = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
                color = colors.fill
                textSize = size
                typeface = face
            }
            val stroke = TextPaint(fill).apply {
                color = colors.edge
                style = Paint.Style.STROKE
                strokeWidth = size * 0.16f
                strokeJoin = Paint.Join.ROUND
            }
            return fill to stroke
        }
        fun layout(paint: TextPaint, cut: Boolean) = StaticLayout.Builder.obtain(text, 0, text.length, paint, box)
            .setAlignment(Layout.Alignment.ALIGN_CENTER)
            .apply { if (cut) setMaxLines(MAX_LINES).setEllipsize(android.text.TextUtils.TruncateAt.END) }
            .build()
        if (text.isNotEmpty()) {
            var size = full
            while (size > full * 0.7f && layout(paints(size).first, cut = false).lineCount > MAX_LINES) size *= 0.92f
            val (fill, stroke) = paints(size)
            val block = layout(fill, cut = true).height
            val portrait = height > width
            // Top: the band over the picture; middle: across it; bottom: above the corner credit (and the Shorts buttons).
            val top = when (look.place) {
                "middle" -> (height - block) / 2f
                "bottom" -> height * (if (portrait) 0.80f else 0.92f) - block
                else -> height * (if (portrait) 0.09f else 0.05f)
            }
            canvas.withTranslation(margin, top) {
                layout(stroke, cut = true).draw(this)
                layout(fill, cut = true).draw(this)
            }
        }
        if (channel.isNotBlank()) {
            // Outlined like the title: the blurred background behind it can be as bright as the picture.
            val text = context.getString(R.string.credit_line, channel)
            val creditSize = width * 0.03f
            val outline = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.BLACK
                textSize = creditSize
                style = Paint.Style.STROKE
                strokeWidth = creditSize * 0.18f
                strokeJoin = Paint.Join.ROUND
            }
            val credit = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.WHITE
                textSize = creditSize
                typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            }
            outline.typeface = credit.typeface
            canvas.drawText(text, margin, height - margin, outline)
            canvas.drawText(text, margin, height - margin, credit)
        }
        return BitmapOverlay.createStaticBitmapOverlay(bitmap, StaticOverlaySettings.Builder().build())
    }

    private fun saveToMovies(file: File, source: Source, clip: Clip): Uri {
        val resolver = context.contentResolver
        val name = "stream2clip_${source.channel.filter { it.isLetterOrDigit() }.take(20)}_${clip.rank.toString().padStart(2, '0')}_${System.currentTimeMillis() / 1000}.mp4"
        val values = ContentValues().apply {
            put(MediaStore.Video.Media.DISPLAY_NAME, name)
            put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
            put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/stream2clip")
            put(MediaStore.Video.Media.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values) ?: error("MediaStore refused the new video")
        resolver.openOutputStream(uri).use { output -> file.inputStream().use { it.copyTo(output!!) } }
        values.clear()
        values.put(MediaStore.Video.Media.IS_PENDING, 0)
        resolver.update(uri, values, null, null)
        file.delete()
        return uri
    }
}
