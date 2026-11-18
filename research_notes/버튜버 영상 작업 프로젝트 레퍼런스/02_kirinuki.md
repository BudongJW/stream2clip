# Kirinuki (切り抜き) — Highlight Detection and Clip Extraction from VTuber Livestreams

Notes on method. Star counts, primary language, license and last-push dates for GitHub repos come from the GitHub search API, queried on 2026-11-18. Feature descriptions come from each repo's README unless another source is given. "No license" means the repo declares none, so the code cannot legally be reused; only the ideas can. Searching GitHub for "切り抜き" mostly returns image-cutout and matting tools (for example AviUtl2/YMM4 SAM3 plugins), not stream clipping. A naive keyword search is therefore misleading, and several entries below were found through other phrasings.

---

## 1. Open-source highlight detection from livestreams (chat density, keyword/emote spikes, superchat, audio/laughter, LLM)

### Takeaway
There is no dominant open-source "kirinuki engine". The field is made of many small repos (0–60 stars, apart from one 318-star AGPL app) that all converge on the same recipe: bin the chat into 10–30 s windows, compare each bin with the stream's own baseline, add a reaction lexicon (草/w/lol/KEKW/ㅋㅋ), optionally fuse an audio-loudness or laughter signal, then pad and merge the windows into cut ranges. Newer 2025–2026 projects add an LLM pass over a Whisper transcript. The best references for algorithm design are ClipRadar (CHZZK, documented scoring), VoxClutch (documented weights), HoloAutoClip (VTuber-specific, open CSV data) and Clips Kitty (multimodal plus LLM).

### Cited Findings

**Chat-density / keyword-spike detectors (VTuber-specific)**
- **mipacd/auto-clip (HoloAutoClip / VTAutoClip)**: 6★, JavaScript, no license, last push 2025-04-01. Its site lists VTuber clips generated automatically from chat logs: chat messages matching terms such as "lol" and "kusa" are grouped into 30-second windows, and each clip starts 30 s before the largest grouping "to provide context". The site updates weekly and the raw data is in a `csv` folder. Live sites: https://mipacd.github.io/auto-clip/holo.html and https://mipacd.github.io/auto-clip/vt.html. — [GitHub](https://github.com/mipacd/auto-clip)
- **yutoe183/youtube-clip-automation** ("YouTube切り抜き動画の自動生成ツール"): 8★, Python, license NOASSERTION, last push 2025-01-18. It pulls chat and comments from a channel's live archives over a date range and filters them with three regexes ("strict", "loose" and "count"). It then clusters the matches into candidate times, downloads with yt-dlp and cuts and concatenates with moviepy. Exact start and end times are still chosen by hand. — [GitHub](https://github.com/yutoe183/youtube-clip-automation)
- **MTJOBHUNTING/AutoKirinukiVideo** ("切り抜き動画の自動化に特化した、自動動画編集ソフト"): 1★, Python, last push 2023-05-28. Small and stale. — [GitHub](https://github.com/MTJOBHUNTING/AutoKirinukiVideo)
- **pyristix/Livestream-Highlighter**: 3★, JavaScript, last push 2023-07-13. A Chrome extension that analyzes trends in YouTube live chat. Stale. — [GitHub](https://github.com/pyristix/Livestream-Highlighter)
- **prashanthrebala/stream-sense**: 0★, Python, last push 2024-05-07. Uses YouTube live chat replay to find highlights. — [GitHub](https://github.com/prashanthrebala/stream-sense)

**Chat-density detectors (Twitch / CHZZK / generic)**
- **ThankyouJerry/ClipRadar** (Korean, CHZZK): 1★, Python (standard library only), MIT, last push 2026-08-20. Its scoring is fully documented:
  - Chat is binned into 30 s windows and each window is compared with that VOD's own normal level.
  - A message such as ㅋㅋㅋㅋ counts as one reaction however many times the expression repeats inside it.
  - Candidates less than 90 s apart are merged into one scene of at most 3 minutes.
  - The recommended cut adds 30 s before and 60 s after the core window.
  - Score = 70% chat surge + 30% "reaction chat" surge (laughter, surprise and hype expressions).
  - Candidates are typed as funny, hype, surprise or chat-surge.
  - With several VODs, each VOD is normalized on its own so that long or busy streams do not dominate.
  - Modes are sampled ("quick" and "precise") or full chat crawl, and results export as JSON, CSV or HTML editor sheets.

  — [GitHub](https://github.com/ThankyouJerry/ClipRadar)
- **Rohi56u/VoXCluTcH (VoxClutch)**: 0★, MIT, last push 2026-11-02. It reads Twitch IRC anonymously (`justinfan`, no OAuth) and scores 15 s windows as chat velocity 45% + normalized chatter entropy 35% + reaction-cue density 20%. Audio is analyzed with FFmpeg as 8 kHz mono RMS dBFS, comparing each window peak with a 40 s ambient baseline. The final fusion is 70% chat + 30% audio. Only aggregates are kept in SQLite. — [GitHub](https://github.com/Rohi56u/VoXCluTcH)
- **xurei/twitch-highlights-logger**: 34★, JavaScript (Electron), GPL-3.0, last push 2025-05-13. It loads the full chat log of a Twitch VOD and counts messages matching a filter in a sliding window. A window that passes a threshold becomes a highlight, and clicking it jumps the video to that point. — [GitHub](https://github.com/xurei/twitch-highlights-logger)
- **VadlapatiKarthik/autoclipper**: 45★, Python, no license, last push 2025-05-07. It detects highlights from YouTube channels and Twitch/Kick live streams using audience-retention data, chat spikes and timestamped comments, then clips with FFmpeg, subtitles the result and uploads to YouTube. Stack: FastAPI, Celery, Redis, a React dashboard, Cloud Run and an OpenAI key. — [GitHub](https://github.com/VadlapatiKarthik/autoclipper)
- **cairthenn/TwitchChatVideo**: 45★, C#, GPL-3.0, last push 2022-12-08. Renders Twitch VOD chat as a replay video "for highlight editors". Stale. — [GitHub](https://github.com/cairthenn/TwitchChatVideo)
- **A wave of near-identical 0★ repos from 2026** shows the chat-velocity pattern is now commoditized:
  - [Vladshmalii/twitch-auto-clip-bot](https://github.com/Vladshmalii/twitch-auto-clip-bot) (2026-11-10)
  - [shubtriple7/StreamSniper](https://github.com/shubtriple7/StreamSniper) (MIT, 2026-11-17; chat velocity, 30 s auto-clips, Faster-Whisper)
  - [windycityassassin/reactorlab](https://github.com/windycityassassin/reactorlab) (streamlink, ffmpeg, 9:16)
  - [Deeptanil/HyperClip-AI](https://github.com/Deeptanil/HyperClip-AI)
  - [plagrizr/VODrizr](https://github.com/plagrizr/VODrizr) (chat spikes, emote storms, raids and subs, audio energy, speech cues)

  — GitHub search, 2026-11-18

**Audio / laughter / singing detection**
- **jrgillick/laughter-detection**: 298★, Python, MIT, last push 2024-07-25. The standard open laughter detector. — [GitHub](https://github.com/jrgillick/laughter-detection)
- **omine-me/LaughterSegmentation**: 66★, Python, MIT, last push 2024-09-01. Implements "Robust Laughter Segmentation with Automatic Diverse Data Synthesis" (Interspeech 2024) and describes itself as the latest laughter detection and segmentation model. — [GitHub](https://github.com/omine-me/LaughterSegmentation)
- **nirvagold/stream-clipper**: 5★, Rust/Tauri/Svelte, MIT, last push 2025-12-31. Detects highlights from RMS volume spikes and WebRTC VAD. Its chat analysis (a "Pro" tier feature) parses TwitchDownloader JSON, yt-dlp YouTube chat JSON and `[HH:MM:SS] user: message` text, with custom keywords such as "POG" and "CLIP IT". — [GitHub](https://github.com/nirvagold/stream-clipper)
- **kiy0ni/auto-video-editor**: 11★, Python, MIT, last push 2026-10-26. A single audio pass scores every second for loudness relative to context, sudden spikes, speech rate, exclamations and "hype phrases", plus laughter detection. faster-whisper supplies word-level timestamps so cuts snap to sentence boundaries, and every cut gets a 20 ms fade. — [GitHub](https://github.com/kiy0ni/auto-video-editor)
- **anAtheist987/AutoSlicer-v2** (歌回 / karaoke-stream slicer, Bilibili): 3★, Python, MIT, last push 2026-06-12. A 2.1M-parameter log-mel CRNN detects segments where the streamer herself is singing and cuts each song losslessly with ffmpeg, with a 5 s margin. The README claims a 3-hour VOD is processed in under a minute. — [GitHub](https://github.com/anAtheist987/AutoSlicer-v2)
- **ouor/cliper**: Rust, MIT, last push 2026-11-11. A Windows app that finds song segments in CHZZK and SOOP karaoke-stream replays and exports one video per song. — [GitHub](https://github.com/ouor/cliper)

**ML / multimodal (older)**
- **artkulak/twitch-stream-highlights-detection**: 59★, Python, Unlicense, last push 2021-05-26 (stale). Every 10-second chunk gets three features: audio tagging (PANNs `audioset_tagging_cnn`), chat sentiment from transformers, and a motion score. A logistic-regression metamodel predicts whether the chunk is a highlight. — [GitHub](https://github.com/artkulak/twitch-stream-highlights-detection)
- **dscig/twitch-highlight-detection (MINT)**: 19★, PyTorch, last push 2021-06-21. Code for "Finding Epic Moments in Live Content through Learning from Collective Decisions" (EPJ Data Science). It learns emote embeddings with gensim and ships pretrained top-1000 Twitch emote vectors. The model reaches 0.8261 accuracy at detecting popular clips, and the authors say combining chat and video features is critical. Clip and video IDs are released; the full data is available on request. — [GitHub](https://github.com/dscig/twitch-highlight-detection)

**LLM / transcript-based pipelines**
- **ColinGPT9/clips-studio ("Clips Kitty")**: 318★, Python, AGPL-3.0, last push 2026-11-18, actively maintained.
  - faster-whisper produces word-level timestamps.
  - Audio, visual and reaction signals are computed in 1-second bins. Reaction signals include Twitch chat replay measured by *unique chatters* and YouTube's most-replayed heatmap.
  - A local LLM (Ollama; Gemma by default, or OpenRouter) scores the transcript "plus a timeline of those events", which lets it recognize moments where "the words are mild but the room exploded". Moments are scored 0–100.
  - It also exports 16:9 highlight reels with chapter timestamps.

  This overlaps with the short-form researcher's scope, but the detection design is relevant here. — [GitHub](https://github.com/ColinGPT9/clips-studio)
- **billietomato/ytclip** (烤肉 / translated VTuber clips): 3★, TypeScript/Bun, MIT, last push 2026-09-08. A set of Claude Code "Agent Skills":
  1. fetch the transcript, optionally only a time range;
  2. `clip_candidates.ts` builds chunks, and the LLM scores each chunk 0–5 and tags it KEEP/TRIM/CUT in a "content map";
  3. a human edits;
  4. mlx-whisper generates SRT from the edited audio;
  5. LLM translation and proofreading to zh-TW/zh-CN.

  — [GitHub](https://github.com/billietomato/ytclip)
- **MelanLee-shadow/bilibili-vtuber-clip**: 2★, Python, Apache-2.0, last push 2026-11-18. An unattended, "fail-closed" pipeline from a recording plus danmaku XML to a published Bilibili clip.
  - `discover` picks candidates by score under a daily quota.
  - Any spot where the channel's own account posts "标记" (mark) in danmaku is always cut.
  - Later stages: boundaries, dedup, subtitles, speaker identification, title and cover, burn-in, review, upload via biliup.
  - The authors say the repo is meant to be configured by an AI agent through AGENTS.md.

  — [GitHub](https://github.com/MelanLee-shadow/bilibili-vtuber-clip)
- **ChunHao-dev/stream-clip-editor** (Whisper + LLM, 0★, 2026-05-18) and **lxgicstudios/lxgic-clipper** (12★, Shell, MIT, 2026-02-16, an "AI highlight detection + social posting agent") — [GitHub](https://github.com/ChunHao-dev/stream-clip-editor), [GitHub](https://github.com/lxgicstudios/lxgic-clipper)

**Clipper workflow kits (not detection)**
- **haganenoneko/VTuberClippingResources**: 2★, MIT, last push 2022-11-15. The "minimal full spectrum" for clipping: download with yt-dlp, subtitle in Aegisub (`.ass` examples), PSD thumbnail templates with VTuber icons, and burn subtitles with ffmpeg. — [GitHub](https://github.com/haganenoneko/VTuberClippingResources)
- **idolactivities/vtuber-things**: 14★, Lua, MIT, last push 2022-06-07. "Tools to help create subtitles and clips". README not retrievable. — [GitHub](https://github.com/idolactivities/vtuber-things)
- **keimaruO/kirinuki_dl** (1★, MIT, 2024-04-08) is a yt-dlp downloader tuned for 切り抜き creators. **keimaruO/Cliptogen** (2★, MIT, 2023-05-27, marked 未完成 / unfinished) makes a subtitled clip from just a URL and a time range. — [GitHub](https://github.com/keimaruO/kirinuki_dl), [GitHub](https://github.com/keimaruO/Cliptogen)
- **YoutubeClipPlaylist/YoutubeClipPlaylist**: 20★, GPL-3.0, **ARCHIVED** (last push 2025-12-28). A Chrome extension that plays "start~end" clip playlists directly on YouTube, Google Drive and TwitCasting. — [GitHub](https://github.com/YoutubeClipPlaylist/YoutubeClipPlaylist)

### Inferences
- HoloAutoClip's 30 s lead-in and ClipRadar's 30 s pre-roll and 60 s post-roll both indicate that chat reacts *after* the event. stream2clip should apply a configurable negative offset (about −10 to −30 s) to chat peaks before cutting.
- Raw message count is easy to game and is biased by audience size. The better-designed repos normalize per stream (ClipRadar), add diversity measures such as unique chatters or chatter entropy (Clips Kitty, VoxClutch), and collapse repeated characters (ClipRadar's ㅋㅋㅋ rule). These are cheap wins worth copying.
- Signal fusion currently uses hand-set weights (70/30, 45/35/20). stream2clip could start with similar weights and later learn them from weak labels; see the Holodex and Mr. HiSum findings in Q3 and Q6.
- Two complementary, reusable signals appear only in VTuber and Bilibili projects: singing-segment detection for 歌枠 (karaoke streams; AutoSlicer, cliper) and "owner marks" (the 标记 danmaku in bilibili-vtuber-clip). The second is analogous to YouTube timestamp comments and Holodex tags.
- Licensing: Clips Kitty is AGPL-3.0, and xurei and chzzk-vod-downloader-v2 are GPL-3.0. These are copyleft and should not be vendored into a permissively licensed stream2clip. ClipRadar, VoxClutch, auto-video-editor, AutoSlicer and ytclip are MIT, and bilibili-vtuber-clip is Apache-2.0, so they are safe to study and adapt. autoclipper and HoloAutoClip have no license, so only their ideas can be used.

### Gaps
- I found no open-source project that uses **superchat or membership spikes** as an explicit highlight signal. chat-downloader exposes paid-message types (see Q2), so the data is available, but this is an unexploited idea rather than an existing implementation.
- I could not find any open-source "kusa/www density" project from Qiita or Zenn with public code. The 2020 Highlight-Ranking service (Q7) was announced on Qiita, but I could not confirm that its code is public.
- Accuracy claims in the README-only projects (all of the above except MINT) are unvalidated.

---

## 2. Tools for downloading streams and chat archives

### Takeaway
The core ingestion stack is mature and maintained: yt-dlp (VODs, time sections, live-from-start, live chat, and the "most replayed" heatmap), ytarchive and hoshinova (YouTube live archiving), streamlink (live piping), chat-downloader (YouTube and Twitch chat, including paid messages) and TwitchDownloader (Twitch VOD, clip and chat JSON, plus chat render). pytchat is archived, and the Python Twitch-Chat-Downloader (tcd) is stale. Korean platforms (CHZZK, SOOP) are served only by small community downloaders.

### Cited Findings
- **yt-dlp/yt-dlp**: 208,783★, Python, Unlicense, last push 2026-11-17. — [GitHub](https://github.com/yt-dlp/yt-dlp)
  - `--download-sections` downloads only a time range or matching chapters, e.g. `--download-sections "*10:15-inf"`.
  - `--live-from-start` (marked experimental for YouTube) and `--wait-for-video` for scheduled streams.
  - YouTube live chat is exposed as a subtitle track named `live_chat`, selectable through `--sub-langs`.
- **The yt-dlp info dict has a `heatmap` field**: a list of `{start_time, end_time, value}` entries, where `value` is a normalized float between 0 and 1. This is YouTube's "Most replayed" curve. — [yt-dlp extractor/common.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/common.py)
- **Kethsar/ytarchive**: 1,701★, Go, MIT, last push 2025-12-19. It archives a YouTube livestream from its start, waits for scheduled streams, and accepts cookies for members-only streams when the user is a member. The README warns that `--potoken` is **REQUIRED**; without it the user "will almost certainly encounter issues". — [GitHub](https://github.com/Kethsar/ytarchive)
- **HoloArchivists/hoshinova**: 154★, Rust, MIT, last push 2024-04-19 (somewhat stale). It monitors multiple YouTube channels through RSS, filters by regex and runs ytarchive automatically, with Discord webhook notifications and a web UI. — [GitHub](https://github.com/HoloArchivists/hoshinova)
- **streamlink/streamlink**: 11,952★, Python, BSD-2-Clause, last push 2026-11-14. A CLI that pipes live streams to a player or file. — [GitHub](https://github.com/streamlink/streamlink)
- **xenova/chat-downloader**: 1,200★, Python, MIT, last push 2025-11-05 (about a year without a push, so watch for breakage). — [GitHub](https://github.com/xenova/chat-downloader)
  - Retrieves chat with no authentication from YouTube (livestreams, past broadcasts, premieres), Twitch (livestreams, past broadcasts, clips) and Zoom (past broadcasts); Facebook is "in development".
  - Supports `--start_time` and `--end_time`, and filtering by `--message_types` or `--message_groups`.
- **lay295/TwitchDownloader**: 4,079★, C#, MIT, last push 2026-11-15. — [GitHub](https://github.com/lay295/TwitchDownloader)
  - Downloads VODs and clips, and downloads chat as JSON (all original information), HTML or text.
  - Renders chat with BTTV, FFZ and 7TV emotes.
  - Ships a cross-platform CLI (`videodownload`, chat download and render) intended for scripting.
- **PetterKraabol/Twitch-Chat-Downloader (tcd)**: 651★, Python, MIT, last push 2022-12-26 (stale). — [GitHub](https://github.com/PetterKraabol/Twitch-Chat-Downloader)
- **taizan-hokuto/pytchat**: 370★, Python, MIT, **ARCHIVED** (last push 2021-07-24). Do not depend on it. — [GitHub](https://github.com/taizan-hokuto/pytchat)
- **Other YouTube chat tools**:
  - [hase-ryo/youtube_livechat_replay_crawler](https://github.com/hase-ryo/youtube_livechat_replay_crawler): 69★, MIT, 2024-07-12.
  - [abhinavxd/youtube-live-chat-downloader](https://github.com/abhinavxd/youtube-live-chat-downloader): Go, 33★, MIT, 2026-07-31.
  - [zaacksb/tubechat](https://github.com/zaacksb/tubechat): TypeScript, 11★, MIT, 2026-10-04; real-time chat plus VOD replay download.
  - [koshkokoshka/yt-chat-to-video](https://github.com/koshkokoshka/yt-chat-to-video): renders `.live_chat.json` to mp4, 2026-09-10.

  — GitHub search
- **Korean platforms (CHZZK / SOOP)**:
  - [honey720/chzzk-vod-downloader-v2](https://github.com/honey720/chzzk-vod-downloader-v2): 73★, Python, GPL-3.0, last push 2026-11-18. Downloads CHZZK replays and clips, and can download only chosen sections (up to 20 per video, one file per section).
  - [Choonholic/ChzzkDownloader](https://github.com/Choonholic/ChzzkDownloader): 35★, 2026-11-03. Windows suite for live, VOD, replay and clips.
  - [horsaen/afreeca-downloader](https://github.com/horsaen/afreeca-downloader): Go, 45★, no license, 2026-09-05. Downloads from AfreecaTV/SOOP and other sites.
  - [321098123/chzzk-VOD-chat-downloader](https://github.com/321098123/chzzk-VOD-chat-downloader): 4★, 2025-02-11. Downloads CHZZK replay chat logs.
  - [HO-Silverplate/SOOP-VOD-downloader](https://github.com/HO-Silverplate/SOOP-VOD-downloader): 4★, 2026-04-09.
  - [ThankyouJerry/ClipCatcher](https://github.com/ThankyouJerry/ClipCatcher): MIT, 2026-11-14. CHZZK and YouTube downloader paired with ClipRadar.

  — GitHub search

### Inferences
- A two-pass design keeps bandwidth low. Pass 1 fetches chat, metadata and the heatmap only. Pass 2 cuts candidate ranges with `yt-dlp --download-sections` instead of downloading 6–10 h VODs in full.
- For live archiving of VTuber streams, which matters because many archives are privated or trimmed afterwards, ytarchive plus hoshinova is the community standard. The PO-token requirement and hoshinova's 2024 last commit are maintenance risks.
- No single library covers YouTube, Twitch and CHZZK chat. stream2clip should define an internal normalized chat schema (timestamp_offset, author_hash, text, emotes, paid_amount, membership flag) with per-platform adapters: chat-downloader, the TwitchDownloader JSON format and a CHZZK replay-chat adapter.

### Gaps
- I did not verify chat-downloader's current breakage status against YouTube changes in late 2026. The last push was 2025-11.
- I did not verify that yt-dlp's CHZZK and SOOP extractors exist or work.

---

## 3. VTuber-specific data sources (Holodex, timestamp communities, datasets)

### Takeaway
Holodex is the most valuable VTuber-specific source. Its v2 API exposes clips linked to source streams (`include=clips,sources,refers`), timestamp comments (`?c=1`), a comment search and song data. Together these give stream2clip free weak labels for "which streams and moments human clippers chose". For chat statistics, the VTuber 1B dataset (over a billion chats and superchats) exists but stops in 2022.

### Cited Findings
- **Holodex API v2** (base `https://holodex.net/api/v2`). Every request needs an `X-APIKEY` header. — [Holodex API docs](https://docs.holodex.net/)
  - `GET /videos` filters by `type=stream|clip`, org, topic, `mentioned_channel_id` and date range, with a maximum of 50 per page.
  - `GET /channels/{id}/clips` lists clips of a VTuber.
  - The `include` parameter can add `clips`, `sources`, `refers`, `simulcasts`, `mentions` and `songs`. `sources` and `refers` are the links that tie a clip to the videos it clips.
  - `GET /videos/{id}?c=1` returns timestamp comments (`comment_key`, `video_id`, `message`).
  - `POST /search/commentSearch` finds videos whose comments contain a string.
  - No numeric rate limit is documented. "Excessive" use can lead to throttling or suspension, and using multiple keys to evade limits is prohibited.
- **Holodex ecosystem repos**:
  - [HolodexNet/Holodex](https://github.com/HolodexNet/Holodex) (frontend): 674★, Vue, MIT, last push 2026-11-11.
  - [HolodexNet/Holodex-Plus](https://github.com/HolodexNet/Holodex-Plus) (extension): 28★, 2026-03-29.
  - [HolodexNet/Musicdex](https://github.com/HolodexNet/Musicdex): 112★, Apache-2.0, 2025-04-29.
  - API wrappers: [holodex.js](https://github.com/HolodexNet/holodex.js) (24★, last push 2022, stale); [ombe1229/holodex](https://github.com/ombe1229/holodex) for Python (18★, 2023); [anden3/holodex-rs](https://github.com/anden3/holodex-rs) for Rust (7★, 2026-07-20).

  — GitHub search
- **VTuber 1B (sigvt/vtuber-livechat-dataset)**:
  - Content: over a billion live chats, superchats and moderation events (bans and deletions) from VTuber streams, collected by Yasuaki Uechi.
  - Distribution: on Kaggle as a full edition of about 47 GB (with over 4M Super Chat events) and an "Elements" edition of about 2 MB with statistics. A "Complete" tier is available to approved organizations.
  - Privacy: author names were removed and channel IDs hashed.
  - Licenses: MIT for the code, ODC-PDDL for the data. The repo's last push was in 2022.

  — [GitHub](https://github.com/sigvt/vtuber-livechat-dataset); [awesome.ecosyste.ms entry](https://awesome.ecosyste.ms/projects/github.com%2Fsigvt%2Fvtuber-livechat-dataset)
- **Related academic uses of VTuber chat**: "Who Reaps All the Superchats? A Large-Scale Analysis of Income Inequality in Virtual YouTuber Livestreaming" (arXiv 2503.00825). — [arXiv](https://arxiv.org/pdf/2503.00825)
- **f2sk/hololive-jp-audience-overlap**: analyzes chat-audience overlap across 35 Hololive JP talents using YouTube live chat `authorExternalChannelId` (2026-05-30). — [GitHub](https://github.com/f2sk/hololive-jp-audience-overlap)
- **Fan clip indexes**:
  - [pjvegam/holoclips](https://github.com/pjvegam/holoclips): CLI that finds the most-viewed Hololive clips and builds MPV playlists, 2026-11-07.
  - [mnyu123/DokHub](https://github.com/mnyu123/DokHub): Korean "키리누키 채널 모아보기" (kirinuki channel aggregator), 2026-10-20.
  - [ghostclog/stellive_calander](https://github.com/ghostclog/stellive_calander): Stellive replay and kirinuki calendar, 2024.

  — GitHub search
- **HoloAutoClip** publishes its chat-group data as CSV, which is a small ready-made VTuber dataset. — [GitHub](https://github.com/mipacd/auto-clip)

### Inferences
- The Holodex `clips` and `sources` relations, combined with each clip's YouTube description, can bootstrap a training and evaluation set: given a source stream, which segments did human kirinuki channels cut? Clip descriptions usually carry the source URL, often with a `t=` timestamp, and Hololive's guideline requires the source URL at the top of the description (Q4). This inference has not been tested; recovering exact offsets may require audio fingerprint alignment between clip and source.
- Holodex timestamp comments (`c=1`) are the "timestamp community" signal. They are a strong human prior for chaptering and highlight candidates.
- The YouTube `heatmap` from yt-dlp (Q2) is a third weak label and is available per archive.

### Gaps
- I did not verify Holodex's terms for bulk or commercial use of clip and comment data beyond the docs' rate-limit language.
- `pykeio/oshichats-v2` on Hugging Face appeared in search results as a possible VTuber chat dataset, but I did not open or verify it. — [HF](https://huggingface.co/datasets/pykeio/oshichats-v2/blob/main/README.md)
- I found no public dataset of VTuber clips with exact source-stream offsets.

---

## 4. Japanese kirinuki ecosystem (guidelines, workflows, automation write-ups)

### Takeaway
The major Japanese agencies explicitly permit clips, but they increasingly require **registration** and **source attribution**. Hololive allows clippers to monetize. ANYCOLOR (Nijisanji) moved to mandatory pre-registration in May 2025. VSPO appears to use a permission-number (許諾番号) system, but I could not retrieve its official text. Workflows are mostly manual editors (Premiere, DaVinci Resolve, PowerDirector, CapCut) with heavy telop (on-screen captions); automation write-ups are rare.

### Cited Findings
- **Hololive (COVER Corp) clip guideline** (切り抜き動画に関するガイドライン, on the 二次創作 terms page; page shows "2026年8月31日改訂"). — [hololive production terms](https://hololivepro.com/terms/)
  - Monetization through platform partner programs is permitted (収益化機能をご利用頂いて差し支えありません) if the clip follows the guideline, the platform's terms and any third-party rights.
  - The source video's URL and title must appear at the **start of the description**.
  - Clippers are asked to register their channel through a form. Registered channels are contacted before a takedown, and COVER may file a takedown if a removal request is not honored within 7 days.
  - Members-only, ticketed and other paid content is prohibited unless specifically permitted.
  - Registering clips in Content ID or similar systems as one's own work is prohibited.
  - Clips should not be posted before the original stream has ended and its archive is public.
- **Hololive history**: the clip guideline was introduced in June 2022, and clips fall under both the clip guideline and the general derivative-works guideline. — [Dengeki Online](https://dengekionline.com/articles/136894/); [KAI-YOU](https://kai-you.net/article/83928)
- **ANYCOLOR / Nijisanji, Guidelines for Secondary Creation, Article 5** (enacted 2019-06-17; latest revision 2025-05-23). — [ANYCOLOR guidelines (EN)](https://www.anycolor.co.jp/guidelines/en/); [GameBusiness.jp, 2025-05-24](https://www.gamebusiness.jp/article/2025/05/24/24313.html)
  - Clippers must register in advance through the "Registration Form for Social Media Accounts Uploading Video Clips".
  - The source stream or archive URL must be placed somewhere easy to find, such as the description box.
  - Trimming or additions that cause misunderstanding, spread false information or damage reputation are prohibited, as are offensive or misrepresentative thumbnails.
  - Clips of streams containing third-party copyrighted material, such as gaming or singing streams, may be restricted.
  - Deletion requests must be complied with immediately, and no reasons will be given.
  - Monetization beyond the stated scope needs prior approval.
  - Registration does not itself grant permission.
- **Nijisanji, earlier revision**: the October 2024 revision banned thumbnails or text far removed from what the liver actually said, and individual livers (for example Joe Rikiichi) publish their own extra clip rules. — [KAI-YOU](https://kai-you.net/article/92488); [Dengeki Online](https://dengekionline.com/article/202505/42795)
- **VSPO (ぶいすぽっ!)**:
  - Clip uploads show "ぶいすぽっ!許諾番号" followed by a number in their descriptions (example: 08385), which suggests a permission-number system. — [yutura.net example](https://yutura.net/channel/82292/video/3QkaMbBETMI/)
  - One article says VSPO's derivative-works guideline requires prior review and permission for work beyond the standard conditions. — [Mogura VR](https://www.moguravr.com/?p=183447)
- **Revenue sharing**: one tax-advice article claims "official clip" (公式切り抜き) arrangements commonly split revenue 50/50 with the original creator or agency, and that YouTube's reused-content monetization policy has tightened. This is a secondary, non-authoritative source. — [Money Forward](https://biz.moneyforward.com/tax_return/basic/81382/)
- **Editing tools named in Japanese how-to guides**:
  - DaVinci Resolve (free) — [bloomeria](https://bloomeria.jp/blog/clip-video-editing-beginner-guide)
  - Premiere Pro and PowerDirector — [VideoConverterFactory](https://www.videoconverterfactory.com/jp/tips/create-a-video-clip.html)
  - CapCut and iMovie on mobile
  - Telop and thumbnails are described as the main way to differentiate a clip channel. — [pamxy](https://pamxy.co.jp/marke-driven/sns-marketing/youtube/youtube-clippings/amp/)
  - CapCut is also cited as the go-to tool for clips, captions and templates in 2026 VTuber AI guides. — [aipicks.jp](https://aipicks.jp/mag/vtuber-ai-guide-2026)
- **Academic Japanese work** (IEICE FIT2023, paper F-014): treats detection of exciting moments (盛り上がり) as the first technical problem in automating YouTube kirinuki. It describes the existing "highlight-ranking" tool as counting 「草」 and 「w」 in chat every 10 seconds, and notes that this fails on videos with chat disabled or little such chat. Taken from a search snippet; the PDF itself returned HTTP 405. — [IEICE FIT2023 F-014](https://www.ieice.org/publications/conference-FIT-DVDs/FIT2023/data/html/program/pdf/F-014.pdf)
- **Practitioner caution** (2026 Japanese AI guide): AI tends to infer "hype" from volume or speech density, but what makes a stream funny often lies elsewhere. The guide recommends giving the AI explicit clip "templates" (型) and keeping the final judgment with a human. — [aipicks.jp](https://aipicks.jp/mag/vtuber-ai-use-cases-2026)

### Inferences
- stream2clip should include a per-agency **compliance profile**. Examples:
  - automatically put the source URL and title at the top of the description;
  - block members-only, ticketed or paid sources;
  - hold uploads until the archive is public;
  - check that the channel is registered;
  - never register output in Content ID;
  - log permission numbers where an agency uses them (VSPO).
- Chat-free fallbacks such as audio, laughter and LLM-on-transcript are required, because some streams have chat disabled; the FIT2023 paper names this as the weakness of 草-count methods.

### Gaps
- I could not retrieve VSPO's official 二次創作 / 切り抜き guideline text or the 許諾番号 application process.
- I found no Qiita or Zenn article with public code for 草-density detection. The search engine returned none for site-restricted queries, so this is a gap, not proof of absence.
- I could not confirm whether any Japanese agency runs a formal clip revenue-share program.
- The claim that YouTube's clip feature was discontinued in April 2026 comes from a single blog ([vip-jikkyo](https://vip-jikkyo.net/?p=28993)) and is **unverified**.

---

## 5. Korean context (키리누키 / clip channels, agency guidelines, CHZZK/SOOP tooling)

### Takeaway
The Korean kirinuki ecosystem has an active long tail of small 2025–2026 tools aimed at CHZZK and SOOP: downloaders, replay-chat downloaders, a manual edit-point timer, a chat-based highlight radar (ClipRadar) and singing-segment extractors. I could not find official secondary-creation or clip guidelines from Stellive or Isegye Idol (Waktaverse) through web search.

### Cited Findings
- **Korean-language kirinuki tools on GitHub**:
  - [ThankyouJerry/ClipRadar](https://github.com/ThankyouJerry/ClipRadar): chat-signal highlight candidates for CHZZK VODs (details in Q1).
  - [Runpad1197/chzzk_edit_point_Timer](https://github.com/Runpad1197/chzzk_edit_point_Timer): "a program for capturing (manual) edit points, for people doing kirinuki on CHZZK", 2026-05-09.
  - [yechankun/streamer-assist](https://github.com/yechankun/streamer-assist): MIT, 2026-11-17. Records live or replay chat on CHZZK, YouTube and Twitch, marks moments with a hotkey, merges replay chat per video and offers optional AI chat analysis.
  - [Choonholic/ChzzkDownloader](https://github.com/Choonholic/ChzzkDownloader), [honey720/chzzk-vod-downloader-v2](https://github.com/honey720/chzzk-vod-downloader-v2), [horsaen/afreeca-downloader](https://github.com/horsaen/afreeca-downloader) and [ouor/cliper](https://github.com/ouor/cliper): see Q1 and Q2.
  - [mnyu123/DokHub](https://github.com/mnyu123/DokHub): kirinuki channel aggregator.
  - [chibi-chichi/Takodachi-Hololive-crawler](https://github.com/chibi-chichi/Takodachi-Hololive-crawler): Hololive live and kirinuki crawler, 2021, stale.
  - [Moontaehyeon01/SOOP_VOD_SHORTS_MAKED](https://github.com/Moontaehyeon01/SOOP_VOD_SHORTS_MAKED): SOOP VOD to shorts, 2026-08-12.
  - [HWcoms/StreamVODTracker](https://github.com/HWcoms/StreamVODTracker): organizes CHZZK and SOOP VODs, MIT, 2026-11-15.

  — GitHub search, 2026-11-18
- **CHZZK platform context**: CHZZK created a "Challenger" streamer tier with production support of up to ₩30M per year (October 2026). This is not clip-specific. — [Money Today](https://www.mt.co.kr/article/2026100111233698466)
- **Isegye Idol**: a six-member virtual group from Woowakgood's Waktaverse, debuted 2021-12-17. Search found only commentary on Waktaverse derivative-work controversies, not the guideline text. — [Typecast](https://typecast.ai/kr/learn/?p=282); [zod.kr](https://zod.kr/news_game/5617359/comment/5617810?page=49)

### Inferences
- In Korean chat, ㅋㅋ/ㅋㅋㅋ (laughter), ㄷㄷ (shock), ㅠㅠ, "와", "미쳤다" and similar act as the reaction lexicon, much as 草/w does in Japanese. ClipRadar's "one reaction per message" dedup is a good model. The specific lexicon list here is my inference; only ㅋㅋㅋㅋ is cited in ClipRadar's README.
- Because Korean VTubers stream mainly on CHZZK and SOOP rather than YouTube, stream2clip needs CHZZK replay-chat ingestion. That currently means a small community repo ([chzzk-VOD-chat-downloader](https://github.com/321098123/chzzk-VOD-chat-downloader), 4★) or ClipRadar's own crawler, which is a maintenance risk.

### Gaps
- I could not find official clip or secondary-creation guidelines for **Stellive** or **Isegye Idol / Waktaverse**. The next step is to check their official sites, cafes (Naver Cafe) and X accounts directly.
- I found no velog or tistory write-ups on kirinuki automation.
- I did not verify CHZZK's or SOOP's native clip features or their editor revenue programs.

---

## 6. Academic and industry work on livestream highlight detection

### Takeaway
The core academic lineage is: chat-reaction prediction on Twitch esports (Fu et al., EMNLP 2017); implicit crowdsourcing from chat plus viewer interactions (LIGHTOR, 2019); emote-embedding multimodal models (MINT, EPJ Data Science); and "Most replayed" as a large-scale highlight label (Mr. HiSum, NeurIPS 2023). All of them confirm that chat plus video beats either alone. None targets VTubers specifically.

### Cited Findings
- **Fu et al., "Video Highlight Prediction Using Audience Chat Reactions" (EMNLP 2017)**: a new dataset of League of Legends championship broadcasts from NALCS (English) and LMS (Taiwanese) Twitch channels, 218 videos, predicting highlights from chat reactions. — [ACL Anthology D17-1102](https://aclanthology.org/D17-1102/); [arXiv 1707.08559](https://arxiv.org/pdf/1707.08559v1.pdf)
- **LIGHTOR, "Towards Extracting Highlights From Recorded Live Videos: An Implicit Crowdsourcing Approach"** (Jiang, Qu, Wang, Wang, Zheng; arXiv 1910.12201, 2019):
  - A Highlight Initializer uses time-stamped chat to predict approximate highlight positions.
  - A Highlight Extractor refines those positions from how users interact with them (seeking and playback).
  - It was evaluated on two Twitch games with MTurk workers and reached high precision with little training data.

  — [arXiv](https://arxiv.org/abs/1910.12201)
- **MINT ("Finding Epic Moments in Live Content through Learning from Collective Decisions", EPJ Data Science)**: emote-embedding sentiment plus video content reaches 0.8261 accuracy at detecting popular clips. A user study found the algorithmic suggestions comparable to human expert edits. Twitch clips (5–60 s) were used as labels. — [GitHub](https://github.com/dscig/twitch-highlight-detection); [BMC blog](https://blogs.biomedcentral.com/on-physicalsciences/2021/09/02/epic-moments-live-streaming/)
- **Mr. HiSum (NeurIPS 2023 Datasets & Benchmarks)**: 31,892 videos from YouTube-8M, labeled with YouTube's "Most replayed" statistics aggregated over at least 50,000 viewers per video, under CC BY 4.0. Code and data are at github.com/MRHiSum/MR.HiSum. Later work notes that YouTube-8M covers only videos uploaded before 2014. — [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2023/hash/7f880e3a325b06e3601af1384a653038-Abstract.html); [paper PDF](https://papers.neurips.cc/paper_files/paper/2023/file/7f880e3a325b06e3601af1384a653038-Paper-Datasets_and_Benchmarks.pdf)
- **"Can we predict the Most Replayed data of video streaming platforms?"** (arXiv 2309.06102): a follow-up on predicting the most-replayed curve. — [ar5iv](https://ar5iv.labs.arxiv.org/html/2309.06102)
- **IEICE FIT2023 F-014** (Japanese): addresses automatic YouTube kirinuki and the limits of 草/w chat counting; see Q4. — [IEICE](https://www.ieice.org/publications/conference-FIT-DVDs/FIT2023/data/html/program/pdf/F-014.pdf)
- **Laughter segmentation (Interspeech 2024)**: "Robust Laughter Segmentation with Automatic Diverse Data Synthesis", with code available. — [GitHub](https://github.com/omine-me/LaughterSegmentation)
- **COHETS** (Hugging Face): lists 65 streaming videos and 163 streamer-discourse segments citing a 2022 Knowledge-Based Systems paper, but the card appears to be boilerplate and has no data files. Treat it as unreliable. — [HF](https://huggingface.co/datasets/samjaylin/COHETS)

### Inferences
- Mr. HiSum shows that YouTube's heatmap is a recognized proxy label. stream2clip can obtain it per VOD through yt-dlp (Q2) and use it to evaluate or calibrate its chat and audio scoring on VTuber archives, which typically gather enough views for a heatmap.
- LIGHTOR's two-stage idea (a coarse position from chat, then refinement) maps onto stream2clip as coarse chat or heatmap peaks refined by transcript sentence boundaries, VAD or laughter, then by LLM context judgment.

### Gaps
- I found no peer-reviewed paper specifically on VTuber or kirinuki highlight detection beyond the FIT2023 abstract.
- I did not survey general video-highlight benchmarks (e.g. QVHighlights, TVSum) or newer 2025–2026 multimodal-LLM highlight papers in depth.

---

## 7. Commercial kirinuki-assist tools

### Takeaway
Western commercial tools (Eklipse, Medal, Powder, plus Opus-style clippers) target gamers and run either as cloud processing after the stream (Eklipse) or as local capture and analysis (Medal, Powder). Japanese-market tools are smaller and chat-centric: the Highlight Analyzer Chrome extension (laughter-density and comment-pace graphs) and the 2020 Highlight-Ranking web service. All comparisons I found are vendor-written.

### Cited Findings
- **Eklipse**: cloud AI that processes the stream VOD after the broadcast (Twitch, Kick, YouTube) into vertical clips. **Medal** is a local recorder that captures at source quality. **Powder** is a Windows app that analyzes recordings locally and is described as free for gamers. These descriptions come from vendor comparison pages. — [Eklipse vs Medal](https://eklipse.gg/compare/eklipse-vs-medal-tv); [Medal vs Eklipse](https://medal.tv/compare/medal-vs-eklipse); [Eklipse: Powder alternatives](https://eklipse.gg/compare/powder-alternatives/)
- **Eklipse pricing**: Premium is listed at $24.99/month by a third-party guide; not verified on the vendor site. — [twoaveragegamers](https://www.twoaveragegamers.com/best-ai-tools-for-gaming-content-creators-in-2026/)
- **Highlight Analyzer** (Chrome extension "Highlight Analyzer: Youtube & Twitch切り抜き動画作成支援ツール"). — [Chrome Web Store](https://chromewebstore.google.com/detail/highlight-analyzeryoutube/pcicbonbpknjgpmofodbaiiljfhdbpok); [chromeboard listing](https://chromeboard.com/extension/highlight-analyzeryoutube-pcicbonbpknjgpmofodbaiiljfhdbpok)
  - Graphs laughter density and comment pace on YouTube and Twitch archives.
  - Offers a per-channel ranking of the funniest moments and generates a timestamped table of contents from comments.
  - A PRO tier uses AI to suggest clip scenes.
  - Laughter analysis supports EN, JA, KO, ZH and ID.
  - The site is highlight-analyzer.com; the extension has about 1–2K users.
- **VOD Highlight Analyzer** (Greasy Fork userscript): a clickable chat-density chart for YouTube, Twitch and Kick VODs. — [Greasy Fork](https://greasyfork.org/scripts/581599-vod-highlight-analyzer/code)
- **Highlight-Ranking** (highlight-ranking.com, January 2020): enter a YouTube Live URL and it ranks the 10 most exciting moments from chat, cutting about one minute around each. It was announced on Qiita. — [INTERNET Watch](https://internet.watch.impress.co.jp/docs/yajiuma/1228457.html)
- **KIRARI** (Product Hunt): takes a URL, analyzes chat spikes and dialogue, detects highlights and scores each clip for viral potential. — [Product Hunt](https://www.producthunt.com/p/kirari/kirari)
- **Japanese 2026 comparison** of game-streaming clip AI tools: the advice is to choose by detection method — speech recognition for talk streams, volume or cheer peaks for FPS and horror, and chat analysis for VTubers, whose humor comes from chat reactions. — [atsoho](https://atsoho.com/blog/game-streaming-clip-ai-tool-compare)

### Inferences
- The commercial gap stream2clip could fill is VTuber-native, multilingual (JA/KO/EN) chat and laughter analysis, combined with agency-guideline compliance and Holodex awareness. None of the commercial tools surveyed advertises these together.

### Gaps
- I found no independent accuracy benchmarks for any commercial clipper.
- I did not verify current pricing for Highlight Analyzer PRO or KIRARI.
- I did not research Japanese enterprise 切り抜き AI services (agency-operated "official clip" production) in depth.

---

## 8. What is most reusable for stream2clip (synthesis)

### Takeaway
Reuse mature libraries for ingestion, and copy algorithm ideas, not code, for detection: per-stream baseline-normalized chat surge in 15–30 s bins, reaction-lexicon and unique-chatter weighting, a negative chat-lag offset, fusion with audio, laughter and heatmap, merge-and-pad rules, then an LLM pass over the transcript plus an event timeline. Use the Holodex clips/sources data and YouTube heatmaps as weak labels for evaluation.

### Cited Findings
- **Ingestion libraries**:
  - yt-dlp: time-section download, live chat, heatmap — [GitHub](https://github.com/yt-dlp/yt-dlp)
  - chat-downloader: YouTube and Twitch chat, message types — [GitHub](https://github.com/xenova/chat-downloader)
  - TwitchDownloader CLI: Twitch chat JSON — [GitHub](https://github.com/lay295/TwitchDownloader)
  - ytarchive and hoshinova: live archiving — [ytarchive](https://github.com/Kethsar/ytarchive), [hoshinova](https://github.com/HoloArchivists/hoshinova)
  - chzzk-vod-downloader-v2: CHZZK section download, GPL-3.0, so call it as an external tool — [GitHub](https://github.com/honey720/chzzk-vod-downloader-v2)
- **Scoring recipes with explicit parameters**:
  - ClipRadar: 30 s bins, per-VOD baseline, 70/30 chat/reaction weights, merge within 90 s up to 3 min, −30 s/+60 s padding — [GitHub](https://github.com/ThankyouJerry/ClipRadar)
  - VoxClutch: 15 s windows; velocity 45%, entropy 35%, cues 20%; audio RMS against a 40 s baseline; 70/30 chat/audio fusion — [GitHub](https://github.com/Rohi56u/VoXCluTcH)
  - HoloAutoClip: 30 s groupings of lol/kusa, clip starts 30 s before the peak — [GitHub](https://github.com/mipacd/auto-clip)
- **LLM-stage designs**:
  - Clips Kitty: the LLM sees the transcript plus the event timeline, uses unique chatters and the heatmap, scores 0–100 — [GitHub](https://github.com/ColinGPT9/clips-studio)
  - ytclip: chunks scored 0–5 with KEEP/TRIM/CUT, a human editor in the loop — [GitHub](https://github.com/billietomato/ytclip)
  - bilibili-vtuber-clip: daily quota, owner "mark" messages force a cut, fail-closed stages — [GitHub](https://github.com/MelanLee-shadow/bilibili-vtuber-clip)
- **Specialized detectors**:
  - Laughter: [jrgillick/laughter-detection](https://github.com/jrgillick/laughter-detection), [omine-me/LaughterSegmentation](https://github.com/omine-me/LaughterSegmentation)
  - Singing segments for 歌枠: [AutoSlicer-v2](https://github.com/anAtheist987/AutoSlicer-v2)
  - Pretrained Twitch emote embeddings: [MINT](https://github.com/dscig/twitch-highlight-detection)
- **Weak labels and evaluation**:
  - Holodex `include=clips,sources` and timestamp comments `c=1` — [Holodex docs](https://docs.holodex.net/)
  - YouTube heatmap through yt-dlp — [common.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/common.py)
  - Mr. HiSum methodology — [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2023/hash/7f880e3a325b06e3601af1384a653038-Abstract.html)
  - VTuber 1B chat statistics — [GitHub](https://github.com/sigvt/vtuber-livechat-dataset)

### Inferences
Suggested stream2clip pipeline, assembled from the references above (my synthesis, not an existing project):
1. **Discover** streams through the Holodex API or the CHZZK channel list.
2. **Fetch cheap signals**: chat replay through chat-downloader, TwitchDownloader or a CHZZK adapter; heatmap and metadata through yt-dlp; Holodex timestamp comments.
3. **Score coarsely** in 10–30 s bins:
   - z-score of chat rate against the per-stream baseline;
   - unique-chatter ratio;
   - a reaction lexicon for JA, KO and EN (草/w/ｗ/8888, ㅋㅋ/ㄷㄷ, lol/KEKW/LMAO), counted once per message;
   - superchat and membership bursts;
   - Holodex timestamp-comment hits;
   - heatmap value.

   Shift chat by −5 to −30 s to compensate for lag.
4. **Download only candidate windows** with `--download-sections`, plus padding.
5. **Refine** with audio RMS, VAD, laughter and singing detectors and a faster-whisper transcript. Snap boundaries to sentence edges and merge candidates within about 90 s.
6. **Judge with an LLM**: transcript plus event timeline, then title, summary and telop suggestions.
7. **Run the compliance gate** for the agency profile (source URL at the top, registration, no members-only content, wait for the archive).
8. **Hand off to editing**, which the short-form researcher covers.

### Gaps
- No existing open-source project combines VTuber-specific chat lexicons, superchat signals, Holodex weak labels and agency compliance. That is the opportunity, but it also means none of these combined choices has been validated.
