package io.github.budongjw.stream2clip

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.util.UnstableApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

/** Where one clip's export stands: waiting its turn, making (percent), saved (uri) or failed (error). */
data class ExportState(val percent: Int = 0, val uri: Uri? = null, val error: String? = null, val waiting: Boolean = false) {
    val running: Boolean get() = uri == null && error == null
}

/** What the user wrote over the suggestion: the YouTube title and the words on the video. */
data class ClipText(val title: String, val caption: String)

/** YouTube's longest title, in characters (as `upload.TITLE_LIMIT` on the desktop). */
const val TITLE_LIMIT = 100

@UnstableApi
class MainViewModel(app: Application) : AndroidViewModel(app) {
    var url by mutableStateOf("")
    var form by mutableStateOf("shorts")
    var busy by mutableStateOf(false)
        private set
    var stage by mutableStateOf("")
        private set
    var fraction by mutableStateOf(-1.0)
        private set
    var analysis by mutableStateOf<Analysis?>(null)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    val exports = mutableStateMapOf<Int, ExportState>()
    val edits = mutableStateMapOf<Int, ClipText>()

    /** One export at a time: the phone's encoder and the stream's bandwidth are shared, so several at once only slow each other. */
    private val encoder = Mutex()

    /** A shared text may carry words around the address: keep the first http(s) address. */
    fun takeShared(text: String) {
        Regex("""https?://\S+""").find(text)?.let { url = it.value.trimEnd('.', ',', ')') }
    }

    fun text(clip: Clip): ClipText = edits[clip.rank] ?: ClipText(clip.title, clip.caption)

    /** Keep what the user wrote; YouTube takes at most 100 characters in a title. */
    fun edit(clip: Clip, title: String, caption: String) {
        edits[clip.rank] = ClipText(title.replace('\n', ' ').take(TITLE_LIMIT), caption)
    }

    fun analyse() {
        val address = url.trim()
        if (address.isEmpty() || busy) return
        busy = true
        error = null
        analysis = null
        exports.clear()
        edits.clear()
        stage = "info"
        fraction = -1.0
        viewModelScope.launch {
            try {
                val work = File(getApplication<Application>().filesDir, "work").apply { mkdirs() }
                analysis = withContext(Dispatchers.IO) {
                    Core.analyse(getApplication(), address, work, form, Core.phoneLanguage()) { name, part ->
                        viewModelScope.launch(Dispatchers.Main) {
                            stage = name
                            fraction = part
                        }
                    }
                }
            } catch (e: Exception) {
                error = readable(e)
            } finally {
                busy = false
            }
        }
    }

    fun export(clip: Clip) {
        val found = analysis ?: return
        val stream = found.stream ?: return
        if (exports[clip.rank]?.running == true) return
        val caption = text(clip).caption
        exports[clip.rank] = ExportState(waiting = encoder.isLocked)
        viewModelScope.launch {
            exports[clip.rank] = try {
                encoder.withLock {
                    exports[clip.rank] = ExportState()
                    val uri = ShortsExporter(getApplication()).export(stream, found.source, clip, caption, found.form) { percent ->
                        exports[clip.rank] = ExportState(percent)
                    }
                    ExportState(100, uri)
                }
            } catch (e: Exception) {
                ExportState(error = readable(e))
            }
        }
    }

    private fun readable(e: Exception): String {
        val text = e.message ?: e.javaClass.simpleName
        // A Python error comes with its traceback: the last line says what went wrong.
        return text.lineSequence().map { it.trim() }.filter { it.isNotEmpty() }.lastOrNull() ?: text
    }
}
