package io.github.budongjw.stream2clip

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.Locale

/** The stream a highlight list came from. */
data class Source(
    val url: String,
    val title: String,
    val channel: String,
    val duration: Double?,
    val streamDate: String?,
    val category: String,
    val game: String,
    val platform: String,
)

/** An address the phone can read the picture and sound from, with the headers the site wants. */
data class Stream(val url: String, val height: Int, val headers: Map<String, String>)

/** One highlight, as the core found and named it. Times are seconds into the stream. */
data class Clip(
    val rank: Int,
    val start: Double,
    val end: Double,
    val peak: Double,
    val score: Double,
    val reasons: List<String>,
    val title: String,
    /** The words drawn on the video: the whole line, without the title's `[name]` tag. */
    val caption: String,
    val hashtags: List<String>,
    val description: String,
    val link: String,
) {
    val length: Double get() = end - start
}

data class Analysis(
    val source: Source,
    val stream: Stream?,
    val form: String,
    val messages: Int,
    val clips: List<Clip>,
    val note: String,
)

/** Receives the core's progress: a stage name (info, chat, detect) and a fraction, or -1 when it is not known. */
fun interface ProgressSink {
    fun update(stage: String, fraction: Double)
}

/** Calls the stream2clip core (`s2c_android.py`) in the app's Python. Slow: call it off the main thread. */
object Core {
    /** Starts Python once; the app calls it in the background at launch, and every use waits for it. */
    @Synchronized
    fun start(context: Context) {
        if (!Python.isStarted()) Python.start(AndroidPlatform(context.applicationContext))
    }

    fun analyse(context: Context, url: String, workDir: File, form: String, language: String, progress: ProgressSink): Analysis {
        start(context)
        val module = Python.getInstance().getModule("s2c_android")
        val text = module.callAttr("analyse", url, workDir.absolutePath, form, language, progress).toString()
        return parseAnalysis(text)
    }

    fun phoneLanguage(): String = when (Locale.getDefault().language) {
        "ja" -> "ja"
        "en" -> "en"
        else -> "ko"
    }
}

private fun JSONObject.optText(name: String): String = if (isNull(name)) "" else optString(name, "")

private fun JSONArray.texts(): List<String> = List(length()) { getString(it) }

fun parseAnalysis(text: String): Analysis {
    val root = JSONObject(text)
    val src = root.getJSONObject("source")
    val source = Source(
        url = src.optText("url"),
        title = src.optText("title"),
        channel = src.optText("channel"),
        duration = if (src.isNull("duration")) null else src.optDouble("duration"),
        streamDate = src.optText("stream_date").ifEmpty { null },
        category = src.optText("category"),
        game = src.optText("game"),
        platform = src.optText("platform"),
    )
    val stream = root.optJSONObject("stream")?.let { s ->
        val headers = s.optJSONObject("headers")
        Stream(
            url = s.getString("url"),
            height = s.optInt("height"),
            headers = headers?.keys()?.asSequence()?.associateWith { headers.getString(it) } ?: emptyMap(),
        )
    }
    val list = root.getJSONArray("clips")
    val clips = List(list.length()) { index ->
        val c = list.getJSONObject(index)
        Clip(
            rank = c.getInt("rank"),
            start = c.getDouble("start"),
            end = c.getDouble("end"),
            peak = c.getDouble("peak"),
            score = c.getDouble("score"),
            reasons = c.getJSONArray("reasons").texts(),
            title = c.optText("title"),
            caption = c.optText("caption").ifEmpty { c.optText("title") },
            hashtags = c.getJSONArray("hashtags").texts(),
            description = c.optText("description"),
            link = c.optText("link"),
        )
    }
    return Analysis(source, stream, root.optText("form").ifEmpty { "shorts" }, root.optInt("messages"), clips, root.optText("note"))
}

/** `1:02:03` or `2:03`, as the desktop app writes stream times. */
fun clock(seconds: Double): String {
    val total = seconds.coerceAtLeast(0.0).toLong()
    val h = total / 3600
    val m = total % 3600 / 60
    val s = total % 60
    return if (h > 0) String.format(Locale.ROOT, "%d:%02d:%02d", h, m, s) else String.format(Locale.ROOT, "%d:%02d", m, s)
}
