package io.github.budongjw.stream2clip

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Color as AndroidColor
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.SportsEsports
import androidx.compose.material.icons.filled.StayCurrentLandscape
import androidx.compose.material.icons.filled.StayCurrentPortrait
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.media3.common.util.UnstableApi

@UnstableApi
class MainActivity : ComponentActivity() {
    private val model: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(SystemBarStyle.dark(AndroidColor.TRANSPARENT), SystemBarStyle.dark(AndroidColor.TRANSPARENT))
        handle(intent)
        setContent { Stream2clipTheme { MainScreen(model) } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND) intent.getStringExtra(Intent.EXTRA_TEXT)?.let(model::takeShared)
    }
}

private val CardShape = RoundedCornerShape(18.dp)

/** A card on the ink background: the desktop app's `Card` (surface, 1 px border, round corners). */
@Composable
private fun BrandCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(
        modifier
            .fillMaxWidth()
            .clip(CardShape)
            .background(Brand.Surface)
            .border(1.dp, Brand.Border, CardShape)
            .padding(16.dp),
    ) { content() }
}

@UnstableApi
@Composable
fun MainScreen(model: MainViewModel) {
    val context = LocalContext.current
    Scaffold(containerColor = Brand.Ink, topBar = { TopBar() }) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).imePadding(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item { InputCard(model, context) }
            model.error?.let { message -> item { ErrorNote(message) } }
            val found = model.analysis
            when {
                found != null -> {
                    item { SourceCard(found) }
                    if (found.clips.isEmpty()) item { Mascot(R.drawable.kiri_focus, stringResource(R.string.no_highlights)) }
                    val best = found.clips.maxOfOrNull { it.score } ?: 1.0
                    items(found.clips, key = { it.rank }) { clip -> ClipCard(model, found, clip, best, context) }
                }
                !model.busy && model.error == null -> item { Mascot(R.drawable.kiri_wink, stringResource(R.string.empty_hint)) }
            }
        }
    }
}

/** The brand lockup at the top left, as on the desktop app's start window. */
@Composable
private fun TopBar() {
    Row(
        modifier = Modifier.fillMaxWidth().background(Brand.Ink).statusBarsPadding().padding(horizontal = 18.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Image(painterResource(R.drawable.logo_lockup), contentDescription = stringResource(R.string.app_name), modifier = Modifier.height(26.dp))
        Spacer(Modifier.width(10.dp))
        Text(
            stringResource(R.string.badge_beta),
            style = MaterialTheme.typography.labelSmall,
            color = Brand.Pink,
            modifier = Modifier.border(1.dp, Brand.Pink, RoundedCornerShape(6.dp)).padding(horizontal = 6.dp, vertical = 2.dp),
        )
    }
}

@UnstableApi
@Composable
private fun InputCard(model: MainViewModel, context: Context) {
    BrandCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.address_title), style = MaterialTheme.typography.labelSmall, color = Brand.Muted)
            OutlinedTextField(
                value = model.url,
                onValueChange = { model.url = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("chzzk.naver.com/video/...", color = Brand.Muted.copy(alpha = 0.6f)) },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                leadingIcon = { Icon(Icons.Filled.Link, contentDescription = null, tint = Brand.Muted) },
                trailingIcon = {
                    IconButton(onClick = {
                        val clip = (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).primaryClip
                        clip?.getItemAt(0)?.text?.toString()?.let(model::takeShared)
                    }) { Icon(Icons.Filled.ContentPaste, contentDescription = stringResource(R.string.paste), tint = Brand.PinkLight) }
                },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = Brand.Surface2,
                    unfocusedContainerColor = Brand.Surface2,
                    focusedBorderColor = Brand.Pink,
                    unfocusedBorderColor = Brand.Border,
                    cursorColor = Brand.Pink,
                ),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                FormTile(Modifier.weight(1f), model.form == "shorts", Icons.Filled.StayCurrentPortrait, R.string.form_shorts, R.string.form_shorts_hint) { model.form = "shorts" }
                FormTile(Modifier.weight(1f), model.form == "clip", Icons.Filled.StayCurrentLandscape, R.string.form_clip, R.string.form_clip_hint) { model.form = "clip" }
            }
            Button(
                onClick = model::analyse,
                enabled = !model.busy && model.url.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Brand.Pink, contentColor = Brand.Ink, disabledContainerColor = Brand.Surface2, disabledContentColor = Brand.Muted),
            ) {
                Icon(Icons.Filled.AutoAwesome, contentDescription = null, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.find), fontWeight = FontWeight.Bold)
            }
            if (model.busy) Steps(model.stage, model.fraction)
        }
    }
}

/** One of the two forms: a tile with its shape, name and lengths; the chosen one in pink. */
@Composable
private fun FormTile(modifier: Modifier, selected: Boolean, icon: ImageVector, @StringRes name: Int, @StringRes hint: Int, onClick: () -> Unit) {
    val shape = RoundedCornerShape(14.dp)
    Row(
        modifier = modifier
            .clip(shape)
            .background(if (selected) Brand.Pink.copy(alpha = 0.14f) else Brand.Surface2)
            .border(BorderStroke(if (selected) 1.5.dp else 1.dp, if (selected) Brand.Pink else Brand.Border), shape)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, tint = if (selected) Brand.Pink else Brand.Muted, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(8.dp))
        Column {
            Text(stringResource(name), style = MaterialTheme.typography.titleSmall, color = if (selected) Brand.Paper else Brand.Muted)
            Text(stringResource(hint), style = MaterialTheme.typography.bodySmall, color = Brand.Muted)
        }
    }
}

/** Where the search is: information, chat, detection; done ones ticked, the current one turning. */
@Composable
private fun Steps(stage: String, fraction: Double) {
    val order = listOf("info" to R.string.step_info, "chat" to R.string.step_chat, "detect" to R.string.step_detect)
    val current = order.indexOfFirst { it.first == stage }.coerceAtLeast(0)
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            order.forEachIndexed { index, (_, label) ->
                val color = if (index <= current) Brand.Paper else Brand.Muted
                Row(verticalAlignment = Alignment.CenterVertically) {
                    when {
                        index < current -> Icon(Icons.Filled.Check, contentDescription = null, tint = Brand.Pink, modifier = Modifier.size(16.dp))
                        index == current -> CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp, color = Brand.Pink)
                        else -> Box(Modifier.size(8.dp).clip(CircleShape).background(Brand.Border))
                    }
                    Spacer(Modifier.width(6.dp))
                    Text(stringResource(label), style = MaterialTheme.typography.bodySmall, color = color, fontWeight = if (index == current) FontWeight.Bold else FontWeight.Normal)
                }
            }
        }
        if (fraction in 0.0..1.0) {
            LinearProgressIndicator(progress = { fraction.toFloat() }, modifier = Modifier.fillMaxWidth().clip(CircleShape), color = Brand.Pink, trackColor = Brand.Surface2)
        } else {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth().clip(CircleShape), color = Brand.Pink, trackColor = Brand.Surface2)
        }
    }
}

@Composable
private fun Mascot(@DrawableRes image: Int, text: String) {
    Column(modifier = Modifier.fillMaxWidth().padding(top = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Image(painterResource(image), contentDescription = null, modifier = Modifier.size(132.dp))
        Spacer(Modifier.height(10.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = Brand.Muted, textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 24.dp))
    }
}

@Composable
private fun ErrorNote(message: String) {
    Text(
        stringResource(R.string.failed, message),
        color = MaterialTheme.colorScheme.error,
        style = MaterialTheme.typography.bodyMedium,
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Brand.Surface).border(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.5f), RoundedCornerShape(12.dp)).padding(12.dp),
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SourceCard(found: Analysis) {
    BrandCard {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.source_title), style = MaterialTheme.typography.labelSmall, color = Brand.Muted)
            Text(found.source.title.ifBlank { found.source.url }, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (found.source.channel.isNotBlank()) Chip(Icons.Filled.Person, found.source.channel)
                if (found.source.game.isNotBlank()) Chip(Icons.Filled.SportsEsports, found.source.game)
                Chip(Icons.AutoMirrored.Filled.Chat, pluralStringResource(R.plurals.messages_count, found.messages, found.messages))
                Chip(Icons.Filled.AutoAwesome, pluralStringResource(R.plurals.clips_count, found.clips.size, found.clips.size), accent = true)
            }
            if (found.stream == null) Text(stringResource(R.string.no_stream), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun Chip(icon: ImageVector?, text: String, accent: Boolean = false) {
    Row(
        modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(if (accent) Brand.Pink.copy(alpha = 0.16f) else Brand.Surface2).padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, tint = if (accent) Brand.Pink else Brand.Muted, modifier = Modifier.size(14.dp))
            Spacer(Modifier.width(4.dp))
        }
        Text(text, style = MaterialTheme.typography.bodySmall, color = if (accent) Brand.PinkLight else Brand.Paper, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@UnstableApi
@Composable
private fun ClipCard(model: MainViewModel, found: Analysis, clip: Clip, best: Double, context: Context) {
    BrandCard {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(Brand.Pink), contentAlignment = Alignment.Center) {
                    Text("${clip.rank}", color = Brand.Ink, fontWeight = FontWeight.ExtraBold)
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("${clock(clip.start)} ~ ${clock(clip.end)}", fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                    // How strong this moment is against the best one of the stream.
                    Box(Modifier.padding(top = 6.dp).fillMaxWidth().height(4.dp).clip(CircleShape).background(Brand.Surface2)) {
                        Box(
                            Modifier.fillMaxWidth((clip.score / best).toFloat().coerceIn(0.08f, 1f)).height(4.dp).clip(CircleShape)
                                .background(Brush.horizontalGradient(listOf(Brand.Pink, Brand.Highlight))),
                        )
                    }
                }
                Spacer(Modifier.width(10.dp))
                Chip(null, stringResource(R.string.length_seconds, clip.length.toInt()))
            }
            val text = model.text(clip)
            var editing by rememberSaveable(clip.rank) { mutableStateOf(false) }
            if (editing) {
                TextEditor(text, onDone = { edited -> model.edit(clip, edited); editing = false }, onCancel = { editing = false })
            } else {
                Row(verticalAlignment = Alignment.Top) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(text.title, style = MaterialTheme.typography.titleSmall)
                        if (text.caption.isNotBlank()) {
                            // The words on the video, in their own font and colour.
                            Text(text.caption, fontFamily = overlayFamily(text.font), color = Color(TextLooks.color(text.color).fill),
                                 style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                    }
                    IconButton(onClick = { editing = true }, modifier = Modifier.size(36.dp)) {
                        Icon(Icons.Filled.Edit, contentDescription = stringResource(R.string.edit_text), tint = Brand.Muted, modifier = Modifier.size(18.dp))
                    }
                }
            }
            if (clip.reasons.isNotEmpty()) Text(clip.reasons.joinToString(", "), style = MaterialTheme.typography.bodySmall, color = Brand.Muted)
            if (clip.hashtags.isNotEmpty()) Text(clip.hashtags.joinToString(" "), style = MaterialTheme.typography.bodySmall, color = Brand.Highlight)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SmallAction(Icons.Filled.ContentCopy, R.string.copy_text) { copy(context, text.title + "\n\n" + clip.description) }
                // The link comes from the replay's information: only an https page is handed to the browser.
                if (clip.link.startsWith("https://")) SmallAction(Icons.AutoMirrored.Filled.OpenInNew, R.string.open_source) { open(context, clip.link.toUri()) }
            }
            ExportArea(model, found, clip, context)
        }
    }
}

/** The Compose family of one of the video text's fonts (the platform's bold for the system one). */
@Composable
private fun overlayFamily(key: String): FontFamily? {
    val context = LocalContext.current
    val asset = TextLooks.font(key).asset ?: return null
    return remember(asset) { FontFamily(Font(asset, context.assets)) }
}

/**
 * Rewrite the YouTube title (100 characters at most) and the words on the video (they shrink to fit three lines),
 * and pick how those words look: one of the app's fonts, a fill and outline, a place on the frame.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TextEditor(text: ClipText, onDone: (ClipText) -> Unit, onCancel: () -> Unit) {
    var title by rememberSaveable { mutableStateOf(text.title) }
    var caption by rememberSaveable { mutableStateOf(text.caption) }
    var font by rememberSaveable { mutableStateOf(text.font) }
    var color by rememberSaveable { mutableStateOf(text.color) }
    var place by rememberSaveable { mutableStateOf(text.place) }
    val colors = OutlinedTextFieldDefaults.colors(
        focusedContainerColor = Brand.Surface2,
        unfocusedContainerColor = Brand.Surface2,
        focusedBorderColor = Brand.Pink,
        unfocusedBorderColor = Brand.Border,
        cursorColor = Brand.Pink,
        focusedLabelColor = Brand.PinkLight,
    )
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(
            value = title,
            onValueChange = { title = it.replace('\n', ' ').take(TITLE_LIMIT) },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(R.string.title_label)) },
            supportingText = { Text("${title.length}/${TITLE_LIMIT}", color = Brand.Muted) },
            shape = RoundedCornerShape(12.dp),
            colors = colors,
        )
        OutlinedTextField(
            value = caption,
            onValueChange = { caption = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(R.string.caption_label)) },
            supportingText = { Text(stringResource(R.string.caption_hint), color = Brand.Muted) },
            minLines = 2,
            maxLines = 4,
            shape = RoundedCornerShape(12.dp),
            colors = colors,
            textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = overlayFamily(font), color = Color(TextLooks.color(color).fill)),
        )
        ChoiceRow(R.string.look_font, TextLooks.fonts.map { it.key to it.label }, font) { font = it }
        ChoiceRow(R.string.look_color, TextLooks.colors.map { it.key to it.label }, color) { color = it }
        ChoiceRow(R.string.look_place, TextLooks.places.map { it.key to it.label }, place) { place = it }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            Spacer(Modifier.weight(1f))
            OutlinedButton(onClick = onCancel, shape = RoundedCornerShape(10.dp), border = BorderStroke(1.dp, Brand.Border)) {
                Text(stringResource(R.string.cancel), color = Brand.Paper)
            }
            Button(
                onClick = { onDone(ClipText(title.trim(), caption.trim(), font, color, place)) },
                enabled = title.isNotBlank(),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Brand.Pink, contentColor = Brand.Ink),
            ) { Text(stringResource(R.string.save_text), fontWeight = FontWeight.Bold) }
        }
    }
}

/** One of the video text's choices as a row of chips, the chosen one in pink. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChoiceRow(@StringRes title: Int, options: List<Pair<String, Int>>, chosen: String, onPick: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(stringResource(title), style = MaterialTheme.typography.labelSmall, color = Brand.Muted)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            options.forEach { (key, label) ->
                FilterChip(
                    selected = key == chosen,
                    onClick = { onPick(key) },
                    label = { Text(stringResource(label)) },
                    colors = FilterChipDefaults.filterChipColors(
                        containerColor = Brand.Surface2,
                        labelColor = Brand.Paper,
                        selectedContainerColor = Brand.Pink.copy(alpha = 0.22f),
                        selectedLabelColor = Brand.PinkLight,
                    ),
                )
            }
        }
    }
}

@Composable
private fun SmallAction(icon: ImageVector, @StringRes label: Int, onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, Brand.Border),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
        colors = ButtonDefaults.outlinedButtonColors(contentColor = Brand.Paper),
    ) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(16.dp), tint = Brand.Muted)
        Spacer(Modifier.width(6.dp))
        Text(stringResource(label), style = MaterialTheme.typography.bodySmall)
    }
}

/** Make the clip, follow it, then open or share it; a failure leaves the button to try again. */
@UnstableApi
@Composable
private fun ExportArea(model: MainViewModel, found: Analysis, clip: Clip, context: Context) {
    val state = model.exports[clip.rank]
    when {
        state?.uri != null -> Row(verticalAlignment = Alignment.CenterVertically) {
            Image(painterResource(R.drawable.kiri_cut), contentDescription = null, modifier = Modifier.size(40.dp))
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.saved), style = MaterialTheme.typography.bodySmall, color = Brand.Muted, modifier = Modifier.weight(1f))
            IconButton(onClick = { open(context, state.uri, "video/mp4") }) { Icon(Icons.Filled.PlayArrow, contentDescription = stringResource(R.string.open_video), tint = Brand.Pink) }
            IconButton(onClick = { share(context, state.uri) }) { Icon(Icons.Filled.Share, contentDescription = stringResource(R.string.share), tint = Brand.Paper) }
        }
        state != null && state.running -> Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                if (state.waiting) stringResource(R.string.waiting) else stringResource(R.string.making, state.percent),
                style = MaterialTheme.typography.bodySmall,
                color = Brand.PinkLight,
            )
            LinearProgressIndicator(progress = { state.percent / 100f }, modifier = Modifier.fillMaxWidth().clip(CircleShape), color = Brand.Pink, trackColor = Brand.Surface2)
        }
        else -> {
            Button(
                onClick = { model.export(clip) },
                enabled = found.stream != null,
                modifier = Modifier.fillMaxWidth().height(46.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Brand.Pink.copy(alpha = 0.16f), contentColor = Brand.PinkLight, disabledContainerColor = Brand.Surface2, disabledContentColor = Brand.Muted),
            ) {
                Icon(Icons.Filled.Movie, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(stringResource(if (found.form == "shorts") R.string.make_short else R.string.make_clip), fontWeight = FontWeight.Bold)
            }
            state?.error?.let { Text(stringResource(R.string.failed, it), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        }
    }
}

private fun copy(context: Context, text: String) {
    val board = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    board.setPrimaryClip(ClipData.newPlainText("stream2clip", text))
    Toast.makeText(context, R.string.copied, Toast.LENGTH_SHORT).show()
}

private fun open(context: Context, uri: Uri, type: String? = null) {
    val intent = Intent(Intent.ACTION_VIEW).apply {
        if (type != null) {
            setDataAndType(uri, type)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION) // the saved video: the chosen player may read it, nothing else is granted
        } else {
            data = uri
        }
    }
    context.startActivity(Intent.createChooser(intent, null))
}

private fun share(context: Context, uri: Uri) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "video/mp4"
        putExtra(Intent.EXTRA_STREAM, uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, context.getString(R.string.share)))
}
