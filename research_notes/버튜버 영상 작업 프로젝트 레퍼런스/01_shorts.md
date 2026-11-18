# Shorts production from long-form videos and livestreams: external projects and tools (VTuber focus)

Scope: the shorts production side of the pipeline (vertical 16:9 to 9:16 reframing, face/speaker tracking incl. anime faces, animated/karaoke captions, layout templates, AI highlight-to-shorts pipelines, auto-upload). Kirinuki-specific highlight extraction is covered by a separate researcher.

Data note: GitHub star counts, license, last push date and archived flags below came from the GitHub REST search API on **2026-11-18** (the date of this research). "Last push" = `pushed_at`. Stars move fast in this category; treat as approximate.

---

## 1. Notable open-source projects for long-video to shorts generation

### Takeaway
The open-source field is large and has grown a lot during 2025–2026. Dozens of "open-source OpusClip alternative" repos now exist. Most share one recipe: yt-dlp, then Whisper-family ASR with word timestamps, then LLM highlight scoring, then MediaPipe/YOLO face-tracked 9:16 crop, then ASS/libass karaoke captions burned in with ffmpeg, then an optional uploader. The most mature and actively maintained are zhouxiaoka/autoclip, Anil-matcha/AI-Youtube-Shorts-Generator, FujiwaraChoki/supoclip, modelscope/FunClip, NaufalRizqullah/opensource-clipping, ColinGPT9/clips-studio ("Clips Kitty") and xixihhhh/hotclip. Early, well-known projects are now stale: ClipsAI (2024), ShortGPT (Feb 2025), Reelsfy (2023), and stable-ts, which is archived.

### Cited Findings

**End-to-end long→short pipelines (actively maintained unless noted)**

| Project | Stars | Stack / License | Last push | Key features | Status |
|---|---|---|---|---|---|
| [zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip) | 10,731 | Python (FastAPI, React, Tauri desktop), MIT | 2026-11-18 | Long video (podcast/interview/course) to shorts. Subtitles come from author subs, local Whisper/SenseVoice, or cloud ASR. Generates covers and post copy. Two vertical layouts: "interview" and "full-screen podcast". Framing follows the speaker. Can post directly to Bilibili or via Upload-Post. Has CLI/MCP. README in JA/KO | Active |
| [Anil-matcha/AI-Youtube-Shorts-Generator](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator) | 6,214 | Python, MIT | 2026-11-12 | "Open-source alternative to Opus Clip, Vidyo.ai, Klap, SubMagic". `--mode api` uses the paid MuAPI. `--mode local` uses yt-dlp + faster-whisper + ffmpeg/OpenCV face tracking with motion smoothing. LLM (OpenAI/Gemini) virality scoring returns score, hook and reason. Auto-chunks videos over 30 min. Dedupes overlapping clips. JSON output; usable as a Python lib | Active (README heavily promotes the MuAPI paid API) |
| [FujiwaraChoki/supoclip](https://github.com/FujiwaraChoki/supoclip) | 3,476 | Python + web, AGPL-3.0 | 2026-11-18 | Inputs: YouTube, Twitch VOD/clip, Kick VOD/clip, upload (no live streams). An LLM (Gemini/GPT/Claude/Ollama) picks 3–7 clips with virality scores. Face-centered 9:16 crop. Word-synced subtitles via **AssemblyAI** with animated templates. Hook titles, B-roll, built-in editor. Direct publish/schedule to YouTube/TikTok/Instagram. Performance feedback loop. MCP server, REST API, hosted SaaS | Active |
| [modelscope/FunClip](https://github.com/modelscope/FunClip) | 6,574 | Python (Gradio), MIT | 2026-11-01 | Alibaba FunASR Paraformer ASR with token timestamps and hotword customization (SeACo-Paraformer). Supports SenseVoice and Fun-ASR-Nano (Mandarin, English, Japanese…). Text- or speaker-based clipping, LLM-assisted clipping, SRT output. v2.2.0/2.2.1 released Aug–Sep 2026 | Active |
| [xixihhhh/hotclip](https://github.com/xixihhhh/hotclip) | 484 | Electron + React + TS, AGPL-3.0 | 2026-10-26 | Livestream VOD slicing. **Danmaku (chat) density feeds highlight scoring**: reads Bilibili 录播姬 .xml and Douyin .jsonl, weights SC/gift/like, caps single-user spam, adds a burst bonus. Fuses up to nine signals (loudness, shots, motion, expressions, laughter…). Local ASR via sherpa-onnx (SenseVoice/Paraformer/FireRedASR2). Subtitles via libass, plus offscreen-Chromium CSS "bubble" subtitles. VAD-safe jump cuts. 24/7 recording watcher. MCP | Active, Chinese-focused |
| [NaufalRizqullah/opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping) | 321 | Python, MIT | 2026-11-18 | faster-whisper large-v3. Face tracking with MediaPipe BlazeFace or YOLOv8, with smooth pan, deadzone and anti-jitter. **Word-by-word karaoke `.ASS` subtitles**. Pyannote split-screen and active-speaker camera switch. Pexels B-roll, BGM ducking. **Auto YouTube upload with scheduling**; Facebook Reels via Graph API. Runs on Kaggle/Colab | Active |
| [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio) ("Clips Kitty") | 318 | Python, AGPL-3.0 | 2026-11-18 | Inputs: YouTube/Twitch/Kick. faster-whisper (large-v3-turbo) with word timestamps; local Gemma LLM. 9:16 crop via **YOLOv8 + TalkNet active-speaker detection**. **Gaming/Reaction mode puts the webcam in one half and the game in the other**. Uses **Twitch chat replay (unique chatters)** and **YouTube most-replayed heatmap** as signals. "Vertical Live" mode handles streams already in 9:16 (YouTube vertical live, Twitch Dual Format). Publishes to YouTube/TikTok/Instagram. Lists Japanese & Korean among supported languages. **States gaming mode is "People on camera only, no VTubers"** | Active |
| [artbyjazi/autoclip](https://github.com/artbyjazi/autoclip) | 388 | Python + web UI, MIT | 2026-08-01 | Local-first: Whisper + Ollama, or BYO key (Anthropic/OpenAI/Gemini). Speaker-tracked reframe (MediaPipe; optional WhisperX diarization). Four caption styles burned with **libass**. Three aspect ratios, review UI, `autoclip doctor`. Warns that default ffmpeg on macOS/Windows lacks libass | Pre-1.0 |
| [jipraks/yt-short-clipper](https://github.com/jipraks/yt-short-clipper) | 1,092 | Tauri v2 + React + Python sidecar (yt-dlp, FFmpeg, MediaPipe), MIT | 2026-09-20 | Windows-only. LLM highlight detection from **YouTube's own subtitle track**, so it needs no Whisper. Three reframe modes: MediaPipe face tracking, centered with black bars, or blurred fill. Word-by-word captions, hook overlays. Uploads via Repliz | Beta |
| [mutonby/shortcast](https://github.com/mutonby/shortcast) | 402 | Swift (macOS native), Apache-2.0 | 2026-06-04 | Drop a long video to get captioned, reframed vertical shorts | Active-ish |
| [faris-sait/openshorts](https://github.com/faris-sait/openshorts) | 394 | JavaScript, MIT | 2026-04-17 | Long YouTube/upload to 9:16 viral clips | Created 2026-04 |
| [ClipsAI/clipsai](https://github.com/ClipsAI/clipsai) | 575 | Python lib, MIT | **2024-01-17** | `ClipFinder` (transcript-based segmentation using WhisperX) + `resize()` speaker-focused reframing using **Pyannote diarization**. Designed for "audio-centric, narrative-based videos" (podcasts, interviews) | **Stale (~3 yrs)**; good reference design |
| [RayVentura/ShortGPT](https://github.com/RayVentura/ShortGPT) | 8,177 | Python, MIT | **2025-02-10** | Mainly a text-to-short content framework, not long-to-short. "Editing Markup Language", captions, EdgeTTS voiceover in 30+ languages incl. JA/KO, translation/dubbing engine | **Stale (~21 months)** |
| [eddieoz/reels-clips-automator](https://github.com/eddieoz/reels-clips-automator) (Reelsfy) | 235 | Python, MIT | **2023-09-23** | GPT + face tracking to Instagram Reels | **Abandoned** |

**Adjacent / component-level open-source tools**
- [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo): GitHub reports 144,304 stars, Python, MIT, pushed 2026-11-18. It generates shorts from a topic or keyword (text-to-video, not long-to-short). Useful only as a reference for its subtitle and upload pieces.
- [FujiwaraChoki/MoneyPrinterV2](https://github.com/FujiwaraChoki/MoneyPrinterV2): 32,475 stars, AGPL-3.0, pushed 2026-09-15. "Automate the process of making money online" (shorts automation).
- [linyqh/NarratoAI](https://github.com/linyqh/NarratoAI): 11,866 stars, MIT. Does LLM commentary-style editing.
- [mli/autocut](https://github.com/mli/autocut): 7,845 stars, Apache-2.0, last push 2024-10-05. "Edit video with a text editor" (Whisper transcript, then select lines, then cut).
- [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor): 5,973 stars, Nim, Unlicense, pushed 2026-11-18. Cuts automatically on silence or motion.
- [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo): 19,301 stars, Apache-2.0. Offers "Netflix-level subtitle cutting, translation, alignment, dubbing".
- [jianchang512/pyvideotrans](https://github.com/jianchang512/pyvideotrans): 19,771 stars, GPL-3.0. Handles video translation plus subtitles and dubbing.
- [m1guelpf/auto-subtitle](https://github.com/m1guelpf/auto-subtitle): 2,302 stars, MIT, last push 2024-07-12 (stale). Burns Whisper subtitles in with ffmpeg.
- [KazKozDev/auto-vertical-reframe](https://github.com/KazKozDev/auto-vertical-reframe): 25 stars, MIT. A CLI that reframes to 9:16 using YOLO tracking.
- [shubhdotai/AutoFrame](https://github.com/shubhdotai/AutoFrame): 3 stars, MIT. Converts 16:9 to vertical and follows the active speaker.
- [Istalry/ClipReframe](https://github.com/Istalry/ClipReframe): 0 stars, MIT, pushed 2026-11-10. Turns a 16:9 gameplay + webcam clip into 1080×1920. Tiny, but it covers the same use case as a VTuber "avatar + game" layout.
- [LuisSotelo/vod-to-viral](https://github.com/LuisSotelo/vod-to-viral): 12 stars. Turns Twitch VODs into clips using audio-based highlight detection.
- [mismai-li/n8n-youtube-to-shorts-workflow](https://github.com/mismai-li/n8n-youtube-to-shorts-workflow): 138 stars, MIT. An n8n workflow that converts long YouTube videos into scheduled Shorts.
- Many more small "OpusClip alternative" repos (2026), mostly with few stars: [fralapo/clippyme](https://github.com/fralapo/clippyme) (68★), [osbytes/reelsaw](https://github.com/osbytes/reelsaw) (18★, AGPL), [Shaarav4795/ClippedAI](https://github.com/Shaarav4795/ClippedAI) (245★), [SamurAIGPT/ai-clipping-generator](https://github.com/SamurAIGPT/ai-clipping-generator) (122★, Next.js SaaS), [Magerko/ReelsMaker-Pro](https://github.com/Magerko/ReelsMaker-Pro) (72★), [GrepCut/OpenClipper](https://github.com/GrepCut/OpenClipper) (21★), [kleZ799/clipmint](https://github.com/kleZ799/clipmint) (51★, explicitly handles stream VODs). There is also a curated list, [cipher-vault-hq/awesome-free-opusclip-alternatives](https://github.com/cipher-vault-hq/awesome-free-opusclip-alternatives).
- OpenShorts: [mutonby/openshorts-plugin](https://github.com/mutonby/openshorts-plugin) (71★) is a Claude plugin for the hosted OpenShorts service. The original `mutonby/openshorts` repository did not resolve through the GitHub API on 2026-11-18, while mirrors exist ([gastonmorsetto/openshorts](https://github.com/gastonmorsetto/openshorts), "Mirror of mutonby/openshorts"). The upstream may have gone private or been renamed.
- A Japanese review of a GitHub "AI-Shorts-Creator" tool reported that its person-tracking vertical crop was jerky ("カクカク") and low quality. Tracking quality varies widely between implementations — [WEEL](https://weel.co.jp/media/ai-shorts-creator) (via search summary).

**Reframing primitive: Google AutoFlip (MediaPipe)**
- The AutoFlip example still exists in [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/examples/desktop/autoflip/README.md) (37,733★, Apache-2.0). It is built with Bazel, and its README states "AutoFlip currently only works with OpenCV 3". Its old docs page (`docs/solutions/autoflip.md`) now returns 404. In practice it is legacy, and modern projects use MediaPipe's face detector directly (e.g. opensource-clipping, yt-short-clipper, artbyjazi/autoclip) — see the READMEs linked above.

### Inferences
- Nearly every OSS project targets **real human faces** (MediaPipe BlazeFace, YOLOv8-face, TalkNet). No mainstream OSS clipper documents anime/avatar face tracking, and Clips Kitty explicitly excludes VTubers from its webcam+game mode. This is a clear gap that stream2clip can fill.
- Two VTuber-relevant ideas appear in OSS: chat- and audience-signal highlight scoring (hotclip danmaku weighting; Clips Kitty's Twitch chat unique chatters and YouTube most-replayed heatmap) and the **webcam + game split layout** (Clips Kitty, ClipReframe, StreamLadder/Eklipse in SaaS). A VTuber "avatar + game" layout is the same problem with an anime face detector or a fixed region in place of the webcam detector.
- License matters for reuse. supoclip, Clips Kitty, hotclip and ultralytics YOLO are AGPL-3.0. Anil-matcha's generator, zhouxiaoka/autoclip, artbyjazi/autoclip, opensource-clipping, FunClip and pycaps are MIT. If stream2clip wants a permissive license, it should study the AGPL projects but copy code only from the MIT/Apache ones.

### Gaps
- I did not verify each repo's code quality or actual output quality; the descriptions come from READMEs.
- I could not confirm why `mutonby/openshorts` is unreachable (private, renamed or deleted).
- The MoneyPrinterTurbo star count (144k) is what the API returned, but it seems unusually high. Verify it on GitHub before quoting.

---

## 2. Commercial SaaS tools and which are popular with streamers/VTubers

### Takeaway
Two families exist. Generalist "long video to viral clips" tools (OpusClip, Vizard, Klap, Submagic, Munch, 2short.ai, CapCut) are tuned for talking-head and podcast content. Stream-specific tools (StreamLadder, Eklipse) are built around Twitch/Kick/YouTube VODs with facecam + gameplay stacked layouts, chat or audience spikes, and auto-posting. The only VTuber-specific SaaS found, **VTubeClip**, offered avatar + game two-panel vertical clips without subtitles, and its site returned HTTP 410 Gone on 2026-11-18.

### Cited Findings
- **OpusClip** ([opus.pro](https://www.opus.pro/)):
  - Features: ClipAnything clips any genre, including gaming, and can find a moment described in natural language. ReframeAnything uses AI object tracking with a manual tracking override. Also offers AI relayout, auto captions (claims 97–99% accuracy), brand templates, one-click publishing to social platforms, and an API.
  - Scale and pricing: claims "20M+ creators and businesses". The free plan gives 60 credits/month, and a 7-day Pro trial is offered — [opus.pro](https://www.opus.pro/).
  - Languages, conflict: the homepage fetched on 2026-11-18 listed about 20 European/other languages and did not include JA/KO. A changelog item says 5 new languages, including Japanese and Korean, were added for processing and captions — [OpusClip changelog](https://opusclip.canny.io/changelog) (via search summary). The homepage list may be out of date.
- **StreamLadder** ([streamladder.com](https://streamladder.com/)):
  - Clipping and editing: ClipGPT finds highlights in a full VOD (Creator plan). The Clip Editor converts horizontal stream clips to vertical. Other tools include AI Reframing, Captions, Montage Maker, and Emote Maker (Twitch/7TV/BTTV).
  - Publishing: Content Publisher posts to TikTok, YouTube Shorts, Reels, Facebook Reels and X, with scheduling and auto-chosen posting times. Imports come from Twitch, YouTube and Kick. The Pro plan adds 4K60 export.
  - Scale and pricing: claims "1 million streamers have made 12 million clips". The free plan adds a watermark — [streamladder.com](https://streamladder.com/).
  - Layouts: third-party reviews describe side-by-side and picture-in-picture layout templates and smart detection of facecam vs gameplay areas — [vidpros review 2026](https://vidpros.com/streamladder-review-2026/). The free template count is disputed by competitor Eklipse ("only 4 templates") — [Eklipse blog](https://blog.eklipse.gg/tools/eklipse-vs-streamladder.html).
- **Eklipse** ([eklipse.gg/features](https://eklipse.gg/features)):
  - Highlight detection: game-aware, using clutches, multi-kills, reactions, chat spikes and audience spikes, with "3,000+ games" supported. It also detects moments in Just Chatting, podcasts and reactions.
  - Editing and posting: gameplay + facecam stacked 9:16 layout, styled auto-captions, and posting/scheduling to TikTok/Shorts/Reels up to a week ahead. Sources are Twitch, Kick, YouTube and Facebook. The site has a Japanese UI. The features page does not mention VTubers.
  - A free browser tool converts a single Twitch clip into a YouTube Short — [Eklipse tool](https://eklipse.gg/features/twitch-clip-to-youtube-short/).
- **VTubeClip** (vtubeclip.com):
  - Described as an "automatic clip maker for Vtubers". It picks highlights from loud moments, laughter and scares, and outputs a vertical two-panel avatar + game screen. "Editing + framing only — no subtitles". English only, SaaS, $3–16/month. It was added to AlternativeTo on 2026-07-15 — [AlternativeTo](https://alternativeto.net/software/vtubeclip/about/).
  - Fetching https://vtubeclip.com/en/ on 2026-11-18 returned **HTTP 410 Gone**, so the service may have shut down.
- **Vizard**: its Japanese subtitle page claims over 97% accuracy and translation into 28 languages, with SRT/TXT export — [vizard.ai](https://vizard.ai/tools/auto-subtitle-generator-online/japanese-subtitles). Reviewers call it more editor- and timeline-oriented — [Klap blog (competitor)](https://klap.app/blog/vizard-ai-alternatives); [lilachbullock.com](https://www.lilachbullock.com/klap-alternatives/).
- **Submagic**: caption-first. It claims 123 languages and has a dedicated Japanese subtitle generator — [submagic.co](https://www.submagic.co/auto-subtitle-generator/japanese). A third party says 50+ — [reap.video](https://reap.video/blog/reap-vs-submagic-opusclip-descript-language-support), which conflicts with the vendor claim.
- **Klap**: marketed on speed and talking-head content, with an entry plan cited at $29/month — [vizologi Klap review 2026](https://vizologi.com/fewer-clips-better-cuts-our-2026-klap-review/); [dupple](https://www.dupple.com/tools/klap-ai).
- **Munch**: distinguished by marketing analytics (trend and performance signals in clipping) — [ClipSpeed comparison](https://www.clipspeed.ai/compare/best-munch-alternatives-2026.html).
- **2short.ai**: described as tracking your face throughout videos to generate YouTube Shorts — [Eklipse vs 2short](https://blog.eklipse.gg/tools/eklipse-vs-2short-ai.html). Coverage is thin.
- **Category view** (a vendor blog, so biased): caption-first tools (Submagic, Captions) reframe talking heads fine but are "weak on complex layouts". Generalist tools (Opus, Klap, Vizard) are "more variable on gaming". Stream-specific tools (StreamLadder, Eklipse) are "built around gaming layouts, with facecam handling as a priority". CapCut auto-reframe works for single-speaker footage — [autoclip.dev comparison](https://autoclip.dev/blog/9-16-reframing-tools-compared-2026).
- **YouTube "Edit into Short"** (built in, free) added layout options including Single, Square and Split Screen variants — [Lindsey Gamble](https://www.lindseygamble.com/blog/youtube-adds-new-layout-options-for-its-edit-into-short-tool) (via search summary).
- **Twitch** launched a native clip editor for vertical TikTok/Reels exports in May 2023 — [TechCrunch](https://techcrunch.com/2023/05/11/twitch-clip-editor-edit-vertical-video-tiktok-reels) (title from search results; not fetched).
- **VTuber freelance clipper practice**: one VTuber clip editor's service page asks clients for a **green-screen video of the VTuber** plus assets for Shorts/TikToks — [necroch.carrd.co](https://necroch.carrd.co/) (via search summary).

### Inferences
- For VTubers, the stream-specific tools (StreamLadder, Eklipse) are closest in workflow: VOD import, stacked layouts, chat signals and auto-posting. But they are tuned to real facecams and game events. VTubeClip, the one VTuber-specific SaaS, appears to have shut down, which suggests both an unmet niche and possibly a small market.
- The freelancer "green-screen avatar video" practice suggests stream2clip should support an optional **separate avatar source**, such as an OBS source recording or a vertical-canvas recording, in addition to cropping the composited stream.

### Gaps
- **Gling**: I found no reliable 2026 feature info. It is known as an editor that removes silences and bad takes for YouTubers, but that is unverified here.
- I found no first-hand Reddit (r/VirtualYoutubers, r/vtubers) threads in the search results, so there is no community evidence on which SaaS VTubers actually prefer.
- I did not verify current pricing for most SaaS tools; third-party figures may be outdated.

---

## 3. Common libraries and components

### Takeaway
The de facto 2026 stack is:
- **ASR**: faster-whisper or WhisperX for word timestamps. stable-ts is now archived.
- **Captions**: ASS subtitles rendered by libass/ffmpeg (pysubs2 to author them) for karaoke `\k` captions. For richer animation, CSS/HTML renderers (pycaps, hotclip's offscreen Chromium) or React-based Remotion.
- **Reframing**: MediaPipe face detector or YOLOv8, optionally with TalkNet or Pyannote for the active speaker.
- **Upload**: the YouTube Data API `videos.insert`. Its 2026 quota model differs from the widely cited "1,600 units / private-only for unverified apps".

### Cited Findings
**Speech-to-text with word timestamps**
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper): 26,844★, MIT, active (pushed 2026-11-12). CTranslate2 Whisper with `word_timestamps=True` and a `BatchedInferencePipeline`; VAD is on by default for batched mode.
- [m-bain/whisperX](https://github.com/m-bain/whisperX): 25,444★, BSD-2, active. Word-level timestamps via wav2vec2 forced alignment, plus diarization. Default alignment models include `ja`: `jonatasgrosman/wav2vec2-large-xlsr-53-japanese` and `ko`: `kresnik/wav2vec2-large-xlsr-korean` — [whisperx/alignment.py](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py).
- [jianfch/stable-ts](https://github.com/jianfch/stable-ts): 2,282★, MIT, **ARCHIVED**. Its README says "Development on this repository is indefinitely paused."
- [linto-ai/whisper-timestamped](https://github.com/linto-ai/whisper-timestamped): 2,862★, **AGPL-3.0**. Word-level timestamps with confidence scores.
- [openai/whisper](https://github.com/openai/whisper) (112,992★, MIT) and [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) (55,283★, MIT). Remotion's TikTok template uses whisper.cpp — [remotion-dev/template-tiktok](https://github.com/remotion-dev/template-tiktok).
- [pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio) (10,810★, MIT): diarization. Gated HF models need a token, as noted in the ClipsAI and opensource-clipping READMEs.

**Caption rendering**
- [libass/libass](https://github.com/libass/libass) (1,195★, ISC): the ASS renderer used by ffmpeg's `subtitles`/`ass` filters. artbyjazi/autoclip warns that Homebrew's plain `ffmpeg` and Windows "Essentials" builds lack libass; use `ffmpeg-full` or the full Gyan build — [artbyjazi/autoclip](https://github.com/artbyjazi/autoclip).
- [tkarabela/pysubs2](https://github.com/tkarabela/pysubs2) (448★, MIT, active): a Python library for authoring and editing ASS/SRT.
- Karaoke `.ASS` word highlighting (Hormozi style), with `--words-per-sub` grouping — [NaufalRizqullah/opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping). Small reference repos: [sebetancurch/auto-caption](https://github.com/sebetancurch/auto-caption) (14★, Whisper word timestamps to animated ASS to ffmpeg burn-in) and [DorXmoon/karaoke-subs](https://github.com/DorXmoon/karaoke-subs).
- [francozanardi/pycaps](https://github.com/francozanardi/pycaps) (233★, MIT, alpha, pushed 2026-09-30): CSS-styled animated subtitles (e.g. a `.word-being-narrated` selector), templates, word tagging by regex/AI, animations and effects, Whisper/faster-whisper transcription. CLI plus library. Its sibling [francozanardi/tscaps](https://github.com/francozanardi/tscaps) (123★, AGPL-3.0) is a browser editor.
- [remotion-dev/remotion](https://github.com/remotion-dev/remotion) (73,991★, TypeScript, active): React-based programmatic video. GitHub reports its license as **NOASSERTION** (not OSI-standard), so check the terms before commercial use. [template-tiktok](https://github.com/remotion-dev/template-tiktok) generates TikTok-style captions with whisper.cpp.
- [Zulko/moviepy](https://github.com/Zulko/moviepy) (15,164★, MIT, pushed 2026-08-26) and [motion-canvas/motion-canvas](https://github.com/motion-canvas/motion-canvas) (20,018★, MIT) are alternatives. FunClip moved its subtitle rendering to Pillow so it no longer needs ImageMagick — [FunClip](https://github.com/modelscope/FunClip).
- hotclip uses an **offscreen Chromium** to render CSS bubble subtitles frame by frame for effects "libass can't do" — [xixihhhh/hotclip](https://github.com/xixihhhh/hotclip).
- [unconv/captacity](https://github.com/unconv/captacity) (141★, MIT) adds Shorts captions but is stale (last push 2024-06-07).

**Vertical reframing / speaker tracking**
- MediaPipe BlazeFace (short-range) with smoothing and deadzone, or YOLOv8 face (`--face-detector yolo`, sizes 8n/8s/8m/9c) — [opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping).
- YOLOv8 pose + [TaoRuijie/TalkNet-ASD](https://github.com/TaoRuijie/TalkNet-ASD) (521★, MIT, last push 2023) for audio-visual active-speaker detection — [Clips Kitty](https://github.com/ColinGPT9/clips-studio).
- Pyannote diarization–driven crops — [ClipsAI](https://github.com/ClipsAI/clipsai).
- [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics) (63,554★) is **AGPL-3.0**, which affects any product that bundles YOLO.
- [facebookresearch/sam2](https://github.com/facebookresearch/sam2) (20,183★, Apache-2.0) for segmentation and tracking.
- Google AutoFlip is legacy (Bazel, OpenCV 3 only) — [AutoFlip README](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/examples/desktop/autoflip/README.md).
- **Capture-side vertical**: [Aitum/obs-vertical-canvas](https://github.com/Aitum/obs-vertical-canvas) (339★, GPL-2.0, pushed 2026-11-17) adds a second vertical canvas to OBS. Clips Kitty's "Vertical Live" mode consumes streams that were already 9:16 (YouTube vertical live, Twitch Dual Format, Streamlabs Dual Output) — [Clips Kitty](https://github.com/ColinGPT9/clips-studio).

**Ingest**
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) (208,782★, Unlicense) for downloads.
- [lay295/TwitchDownloader](https://github.com/lay295/TwitchDownloader) (4,079★, MIT) downloads Twitch VODs and clips and can download and render chat, which is useful for chat overlays.

**Auto-upload**
- **YouTube Data API `videos.insert`**, official page as of 2026-11-18: "A call to this method has a quota cost of **1 unit in the Video Uploads quota bucket**", listed as **100 calls per day**. It also says "Videos uploaded from unverified API projects are **not** restricted to private viewing mode." Max file size is 256GB — [Google developers: videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert).
  - This **contradicts** the older, widely repeated rule: 1,600 units per upload (about 6 uploads/day on a 10,000-unit quota), and uploads from unverified projects created after 2020-07-28 locked to private. Vendor blogs still cite that rule — [Ayrshare](https://www.ayrshare.com/solutions/how-to-bypass-the-youtube-10k-unit-limit-fixing-the-403-quota-exceeded-error/); [Ayrshare audit](https://www.ayrshare.com/solutions/google-api-error-403-unverified-app-how-to-fix-the-audit-pipeline/); [activepieces](https://www.activepieces.com/blog/youtube-api-quota-exceeded-how-to-fix-and-avoid-it).
  - One secondary source says Google moved to granular quota buckets on 2026-06-01 (via search summary, not verified).
- CLI uploaders:
  - [porjo/youtubeuploader](https://github.com/porjo/youtubeuploader): 895★, Go, Apache-2.0, active (pushed 2026-08-07).
  - [tokland/youtube-upload](https://github.com/tokland/youtube-upload): 2,188★, stale (last push 2024-04-25).
  - [linouk23/youtube_uploader_selenium](https://github.com/linouk23/youtube_uploader_selenium): 668★, stale (2023).
  - [wkaisertexas/tiktok-uploader](https://github.com/wkaisertexas/tiktok-uploader): 787★, MIT, pushed 2026-02-12.
- Built-in uploaders inside OSS clippers:
  - opensource-clipping uploads to YouTube with scheduling and to Facebook Reels via the Meta Graph API — [link](https://github.com/NaufalRizqullah/opensource-clipping).
  - supoclip and Clips Kitty connect YouTube/TikTok/Instagram accounts — [supoclip](https://github.com/FujiwaraChoki/supoclip), [Clips Kitty](https://github.com/ColinGPT9/clips-studio).
  - zhouxiaoka/autoclip and others use the **Upload-Post** aggregator for multi-platform posting — [zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip); [upload-post.com YouTube API guide](https://www.upload-post.com/youtube-api/).

### Inferences
- For a Python-centric stream2clip, a reasonable default would be faster-whisper or WhisperX, then pysubs2-authored ASS with `\k`/`\kf` karaoke tags, burned in by libass/ffmpeg. That path is fast and has no browser dependency. Add a pycaps- or Remotion-style HTML renderer only if bubble or emoji-pop styles are needed.
- Because the YouTube upload quota rules changed in 2026, stream2clip should read the current values from the official page or Cloud Console, not hard-code the "6 uploads/day" folklore.

### Gaps
- I did not verify the TikTok Content Posting API or Instagram Graph API Reels requirements (audit needs, private-only posting for unaudited apps) in this session.
- I could not pin down the exact date of the YouTube quota-bucket change; only a secondary source mentions 2026-06-01.

---

## 4. VTuber- and anime-specific shorts tools; anime face detection

### Takeaway
No mature open-source VTuber shorts tool exists. VTuber-specific repos are tiny (0–20★), early-stage or stale, and the one SaaS (VTubeClip) appears defunct. Anime face detection is a solved component with several options: the classic OpenCV cascade (lbpcascade_animeface), hysts/anime-face-detector (with 28 landmarks), YOLOv8/YOLOv5 anime-face weights, and deepghs ONNX models. These can stand in for MediaPipe in a reframing pipeline.

### Cited Findings
**Anime face detection models**
- [nagadomi/lbpcascade_animeface](https://github.com/nagadomi/lbpcascade_animeface): 1,984★, no license file per the API, last push **2018-11-23**. An OpenCV LBP cascade for anime/manga faces. Old, but trivial to run.
- [hysts/anime-face-detector](https://github.com/hysts/anime-face-detector): 547★, MIT, pushed 2026-07-05.
  - Uses Faster R-CNN and YOLOv3 detectors plus an HRNetV2 **28-point landmark** model. Since v0.1.0 it runs in plain PyTorch without an OpenMMLab dependency.
  - "Detects near-frontal anime faces". Needs Python ≥3.12; install with `pip install anime-face-detector`.
- [Fuyucch1/yolov8_animeface](https://github.com/Fuyucch1/yolov8_animeface): 75★, **AGPL-3.0**, last push 2024-09-27.
  - A yolov8x6 model trained on 10,000 manually annotated Safebooru images at 1280px.
  - Reports P 0.957, R 0.924, mAP50 0.955, mAP50-95 0.534.
- [deepghs/anime_face_detection](https://huggingface.co/deepghs/anime_face_detection) (Hugging Face): MIT, ONNX, versions v0–v1.4, "n" (≈3M params) and "s" (≈11M) sizes, F1 ≈0.93–0.97. It is part of the [deepghs/imgutils](https://github.com/deepghs/imgutils) ecosystem (430★, MIT, last push 2025-10-11), described as "anime-style image data processing library".
- Others:
  - [zymk9/yolov5_anime](https://github.com/zymk9/yolov5_anime): 117★, GPL-3.0, 2023.
  - [qhgz2013/anime-face-detector](https://github.com/qhgz2013/anime-face-detector): 253★, Faster-RCNN/TF, 2022.
  - [cheese-roll/light-anime-face-detector](https://github.com/cheese-roll/light-anime-face-detector): 72★, LFFD.
  - [luxdelux7/ComfyUI-Forbidden-Vision](https://github.com/luxdelux7/ComfyUI-Forbidden-Vision): 104★, AGPL-3.0, custom-trained face detection "across anime, realism, extreme poses".

**VTuber-specific clip/shorts projects (all small)**
- [Charlotte970304/VTuber-Shorts-Agent](https://github.com/Charlotte970304/VTuber-Shorts-Agent): 0★, pushed 2026-10-14, **no license yet**. A modular Python pipeline for "newcomer-friendly Shorts moments from Japanese VTuber livestreams".
  - Stages: faster-whisper Japanese transcription (`language=ja`, optional word timestamps), then audio analysis (volume, low-volume spans, periodic pitch), then event discovery, then a 3-round LLM selection with JSON schemas, then human review, then Shorts output, then a performance feedback step. Currently v0.1/v0.2: rendering is not yet implemented.
- [billietomato/ytclip](https://github.com/billietomato/ytclip): 3★, MIT, pushed 2026-09-08. "AI Agent Skills to help produce VTuber clips and translated subtitles".
- [airdrop-alpha/vclip](https://github.com/airdrop-alpha/vclip): 0★, MIT. "AI-powered VTuber automatic clip/highlight editor".
- [zhkzly/vtuber-clipper](https://github.com/zhkzly/vtuber-clipper): 0★. A Chinese livestream pipeline: SenseVoice ASR, LLM highlight selection, ffmpeg cut with burned subtitles.
- [MelanLee-shadow/bilibili-vtuber-clip](https://github.com/MelanLee-shadow/bilibili-vtuber-clip): 2★, Apache-2.0. Unattended Bilibili VTuber stream clipping.
- [anAtheist987/AutoSlicer-v2](https://github.com/anAtheist987/AutoSlicer-v2): 3★, MIT. **Singer-specific singing detection** for livestream VODs (log-mel CRNN). Relevant for 歌枠 (karaoke stream) song clipping.
- [mipacd/auto-clip](https://github.com/mipacd/auto-clip) ("HoloAutoClip"): 6★, last push 2025-04-01. A machine-generated VTuber clip site.
- Older resources:
  - [idolactivities/vtuber-things](https://github.com/idolactivities/vtuber-things): 14★, 2022, subtitle/clip tools.
  - [haganenoneko/VTuberClippingResources](https://github.com/haganenoneko/VTuberClippingResources): 2★, 2022.
  - JP kirinuki automation: [yutoe183/youtube-clip-automation](https://github.com/yutoe183/youtube-clip-automation) (8★, 2025-01) and [keimaruO/Cliptogen](https://github.com/keimaruO/Cliptogen) (2★, 2023, subtitled clips from a URL plus a time range).
- [Danmanbg/autoclip_editor](https://github.com/Danmanbg/autoclip_editor): 0★, MIT. Stream recordings to captioned vertical clips plus bleeped VODs (ffmpeg + Whisper).
- SaaS: **VTubeClip** (avatar + game two-panel; site 410 Gone) — see section 2.
- The leading general OSS clipper with a webcam/game layout explicitly excludes VTubers: its Gaming/Reaction mode is "People on camera only, no VTubers" — [Clips Kitty](https://github.com/ColinGPT9/clips-studio).

### Inferences
- VTuber streams usually have a **stable compositing layout** (Live2D/3D avatar in a fixed corner or side, game or chat elsewhere). A robust approach for stream2clip:
  1. Detect the avatar's face region with an anime face detector (deepghs ONNX MIT or hysts MIT; avoid AGPL YOLO weights if licensing matters) on sampled frames.
  2. Derive a stable **avatar crop box** per stream or per scene, rather than tracking frame by frame.
  3. Compose layout templates: avatar top + game bottom; avatar full-frame for 雑談 (chatting) streams; avatar PiP over the game.
  
  Per-frame tracking is mainly needed for 3D/full-body or "zatsudan" (talk) layouts where the model moves.
- hysts's landmark output (eyes and mouth points) could feed simple "is the avatar talking / reacting" heuristics, but audio-based VAD or diarization is likely more reliable, since Live2D mouth motion is itself driven by audio. This is speculative and needs testing.
- The singing-detection idea (AutoSlicer-v2) and laughter/emotion tags (SenseVoice, see section 5) map well onto VTuber content types (歌枠, reactions, horror-game screams).

### Gaps
- I found no benchmark comparing anime face detectors on **Live2D VTuber stream frames** specifically (small avatar in a corner, compression artifacts, overlays). Testing on real stream frames is needed.
- No source confirmed whether StreamLadder's or Eklipse's facecam auto-detection works on VTuber avatars.

---

## 5. Japanese and Korean language support

### Takeaway
For JP/KR ASR with word timing:
- Whisper large-v3 via faster-whisper or WhisperX is the baseline. WhisperX ships Japanese and Korean wav2vec2 alignment models.
- kotoba-whisper is a Japanese-specialised, ~6x faster distilled Whisper.
- SenseVoice covers Mandarin, Cantonese, English, Japanese and Korean and adds emotion and audio-event tags.

Several 2026 OSS clippers ship JA/KO READMEs or support (zhouxiaoka/autoclip, Clips Kitty). Among SaaS tools, Submagic, Vizard and (per changelog) OpusClip claim Japanese/Korean. Vrew (Korean company VoyagerX) is the go-to transcript-based editor in JP/KR blog comparisons.

### Cited Findings
**Japanese ASR**
- [kotoba-tech/kotoba-whisper-v2.0](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0):
  - A distilled Whisper large-v3 (full encoder, 2-layer decoder), trained on ReazonSpeech (~7.2M clips). About **6.3x faster** than large-v3.
  - CER on CommonVoice8 / JSUT / ReazonSpeech-test: 9.2 / 8.4 / 11.6, vs large-v3 at 8.5 / 7.1 / 14.9. It is better in-domain and slightly worse out-of-domain.
  - Apache-2.0. Segment-level timestamps. v2.1 adds a stable-ts/punctuation pipeline. faster-whisper and ggml weights are linked from the page.
- [reazon-research/ReazonSpeech](https://github.com/reazon-research/ReazonSpeech): 407★, Apache-2.0, pushed 2026-06-10. "Massive open Japanese speech corpus" and models.

**Multilingual ASR with JA/KO**
- [QwenAudio/SenseVoice](https://github.com/QwenAudio/SenseVoice): 9,778★, MIT, pushed 2026-09-30. "Mandarin, Cantonese, English, Japanese, and Korean ASR, language ID, emotion recognition, and audio event detection."
- [QwenLM/Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR): 3,919★, Apache-2.0. Multilingual ASR.
- FunClip's Fun-ASR-Nano covers Mandarin, English and Japanese — [FunClip](https://github.com/modelscope/FunClip).
- WhisperX alignment models for `ja` and `ko` — [whisperx/alignment.py](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py).

**Line breaking**
- [google/budoux](https://github.com/google/budoux) (1,811★, Apache-2.0, active): "the machine learning powered line break organizer tool", standalone and about 15 KB, with no dependency on third-party word segmenters. Useful for splitting Japanese caption lines, which have no spaces.

**OSS clippers with JA/KO support**
- [zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip) ships README-JA and README-KO and Whisper/SenseVoice transcription.
- [Clips Kitty](https://github.com/ColinGPT9/clips-studio) lists Japanese and Korean among supported languages and has JA/KO READMEs.
- [ShortGPT](https://github.com/RayVentura/ShortGPT) supports JA/KO voiceover via EdgeTTS (it is stale).
- [VideoLingo](https://github.com/Huanshere/VideoLingo) and [pyvideotrans](https://github.com/jianchang512/pyvideotrans) handle subtitle translation, e.g. JP to KR/EN.
- [Charlotte970304/VTuber-Shorts-Agent](https://github.com/Charlotte970304/VTuber-Shorts-Agent) defaults to `language=ja`.

**SaaS**
- Submagic has a Japanese subtitle generator page and claims 123 languages — [submagic.co](https://www.submagic.co/auto-subtitle-generator/japanese).
- Vizard has a Japanese subtitle page claiming over 97% accuracy — [vizard.ai](https://vizard.ai/tools/auto-subtitle-generator-online/japanese-subtitles).
- OpusClip's changelog says Japanese and Korean were added — [opusclip.canny.io](https://opusclip.canny.io/changelog). This conflicts with the homepage list, which omits them — [opus.pro](https://www.opus.pro/).
- **Vrew**:
  - Japanese comparison articles describe it as designed around Japanese, with transcript-based cutting and high Japanese recognition accuracy — [atsoho.com](https://atsoho.com/blog/clip-video-editor-ai-subtitle-tool-comparison) (via search summary).
  - The **Vrew mobile apps (iOS/Android) ended service on 2026-07-01 KST**; desktop continues — [Vrew notice](https://vrew-help.notion.site/Vrew-Mobile-Service-Ending-Notice-2c4c552a746e8004ad93ef13416d1fa6).
- Japanese "best tools" comparisons commonly list Vrew, CapCut, Opus Clip, Submagic, Filmora and Vizard — [atsoho.com](https://atsoho.com/blog/clip-video-editor-ai-subtitle-tool-comparison); [Vizard JA](https://vizard.ai/ja/tools/short-form-video-editor); [Filmora JP](https://filmora.wondershare.jp/video-editing-tools/ai-short-video-generators.html).

**Japanese and Korean community articles**
- Zenn articles show Whisper-based subtitle pipelines:
  - faster-whisper to SRT — [zenn.dev/mossan_hoshi](https://zenn.dev/mossan_hoshi/articles/20241011_faster_whisper_srt).
  - yt-dlp + ffmpeg-python + openai-whisper transcription of YouTube audio — [zenn.dev/s0g0m1hara](https://zenn.dev/s0g0m1hara/articles/dd10cdcd09931b) (library list verified).
  - A search summary also mentioned a Zenn article on removing fillers and re-segmenting subtitles to a character limit. I could not pin down which URL; [zenn.dev/roswell](https://zenn.dev/roswell/articles/b921641c9350a5) is a candidate, but its content was not verifiable because the page renders client-side.
- A Japanese-language article on braindetox.kr covers OpenShorts and 2026 long-to-9:16 automation — [braindetox.kr/ja](https://braindetox.kr/ja/posts/openshorts_video_to_shorts_automation_2026.html) (not fetched).
- Korean OSS in this space is small and mostly text-to-short rather than long-to-short:
  - [choigpt-ai/retention-shorts](https://github.com/choigpt-ai/retention-shorts): 6★, MIT. Picks segments by YouTube **audience retention**, then cold open, 9:16, subtitles, and a Reels safe-zone check.
  - [biblcontentofficial-art/Shorts-Agent-bibl](https://github.com/biblcontentofficial-art/Shorts-Agent-bibl): 1★, MIT. Long-to-vertical shorts with speech-based cuts and subtitles.

### Inferences
- Japanese word-level karaoke captions need extra care. Whisper's "words" in Japanese are sub-word or character tokens, and there are no spaces. A JP caption step should:
  1. Get char- or token-level timings (WhisperX `ja` alignment or faster-whisper `word_timestamps`).
  2. Re-chunk them into readable phrases (BudouX or a morphological analyzer).
  3. Emit ASS `\k` per phrase or chunk, using a CJK font (e.g. Noto Sans JP/KR) available to libass.
  
  This is a design inference, not a sourced benchmark.
- VTuber streams contain game audio, BGM and screaming. SenseVoice's audio-event and emotion tags (laughter, applause etc.) could double as highlight signals.

### Gaps
- No head-to-head benchmark of JP **livestream** ASR (noisy game audio, fast casual speech, slang, VTuber names) across Whisper large-v3, kotoba-whisper, SenseVoice and Qwen3-ASR was found.
- I could not confirm Vrew's official current language list or JP accuracy; Klap's JA/KO support was not found.
- No Korean-specific evaluation of OSS clippers was found.

---

## 6. Most relevant / reusable for stream2clip

### Takeaway
Use the MIT-licensed, actively maintained pipelines as architectural references: zhouxiaoka/autoclip, Anil-matcha/AI-Youtube-Shorts-Generator (local mode), NaufalRizqullah/opensource-clipping (karaoke ASS, YouTube upload) and artbyjazi/autoclip (libass and doctor UX). Study the AGPL projects for VTuber-adjacent ideas without copying their code: hotclip for chat-density highlight scoring, Clips Kitty for webcam/game split, chat replay and vertical-live handling. Swap the human face detector for an anime face detector (deepghs ONNX / hysts, MIT) to build the missing "avatar + game" layout.

### Cited Findings
- MIT, active, end-to-end with local mode:
  - [zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip): 10.7k★, desktop + CLI/MCP, JA/KO docs.
  - [Anil-matcha/AI-Youtube-Shorts-Generator](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator): faster-whisper + OpenCV face tracking + LLM scoring, usable as a Python lib.
  - [NaufalRizqullah/opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping): karaoke ASS, YOLO/MediaPipe tracking, YouTube scheduled upload.
  - [artbyjazi/autoclip](https://github.com/artbyjazi/autoclip): libass captions, local Ollama.
- Stream- and chat-signal ideas (AGPL, reference only):
  - [xixihhhh/hotclip](https://github.com/xixihhhh/hotclip): danmaku weighting, anti-spam, burst bonus, multi-signal fusion, 24/7 recording watcher.
  - [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio): Twitch chat unique chatters, YouTube most-replayed heatmap, webcam + game split, Vertical Live mode.
- Library-quality reference for reframing: [ClipsAI/clipsai](https://github.com/ClipsAI/clipsai). It is stale but has a clean `ClipFinder`/`resize` API design.
- Captions: [pysubs2](https://github.com/tkarabela/pysubs2) + [libass](https://github.com/libass/libass) via ffmpeg; [pycaps](https://github.com/francozanardi/pycaps) (MIT) for CSS-animated styles; [Remotion](https://github.com/remotion-dev/remotion) if a TS/React render stack is acceptable (non-standard license).
- Anime faces:
  - [deepghs/anime_face_detection](https://huggingface.co/deepghs/anime_face_detection): MIT ONNX, light.
  - [hysts/anime-face-detector](https://github.com/hysts/anime-face-detector): MIT, with landmarks.
  - [Fuyucch1/yolov8_animeface](https://github.com/Fuyucch1/yolov8_animeface): AGPL, high-accuracy yolov8x6.
- VTuber-specific reference for JP stream to shorts selection: [Charlotte970304/VTuber-Shorts-Agent](https://github.com/Charlotte970304/VTuber-Shorts-Agent) (early, unlicensed, so read but don't copy).
- Capture side: [Aitum/obs-vertical-canvas](https://github.com/Aitum/obs-vertical-canvas) for streamers who can record a native vertical canvas. Clips Kitty's Vertical Live mode shows how to consume such streams.
- Upload: the official YouTube Data API `videos.insert` (2026: 1 unit in the Video Uploads bucket, 100/day, unverified projects no longer private-only per the official page) — [Google](https://developers.google.com/youtube/v3/docs/videos/insert). Also [porjo/youtubeuploader](https://github.com/porjo/youtubeuploader) (Apache-2.0, active) as a reference CLI.

### Inferences
- **Proposed stream2clip shorts stack.** This is an inference based on the findings above:
  - Ingest: yt-dlp, plus live-chat replay and TwitchDownloader chat.
  - ASR: faster-whisper large-v3 or kotoba-whisper for JA (WhisperX alignment for ja/ko), with SenseVoice as an optional emotion/laughter tagger.
  - Highlight scoring: transcript LLM plus chat density plus audio energy (kirinuki researcher's domain).
  - Layout engine: templates for avatar + game stacked, full avatar, and PiP, with avatar box auto-proposed by an anime face detector and user-adjustable.
  - Captions: ASS karaoke via pysubs2 + libass, with BudouX phrase chunking for JA.
  - Upload: YouTube Data API.
- **Differentiators vs existing tools:** anime/avatar-aware layouts (no OSS or SaaS currently does this reliably; VTubeClip appears defunct) and JP-first captions. Optional ingestion of a separate avatar or green-screen recording or an OBS vertical canvas would give higher-quality avatar crops.

### Gaps
- I did not test any repo's output on actual VTuber footage, so all suitability judgments are from documentation.
- Licensing of model weights (e.g. YOLO-based anime face weights, Pyannote gated models) needs per-model review before bundling.
