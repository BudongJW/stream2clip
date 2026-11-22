# Automatic effect placement and effect templates/presets (survey for stream2clip, as of 2026-11-22)

Legend for evidence strength used throughout: **(V)** = primary page (README, help-center article, standard, paper abstract) read in this session; **(S)** = search-result snippet or secondary/vendor page only, not re-read at the source; **(P)** = taken from this repo's earlier research notes (which cite the source), not re-fetched today; **(Proposal)** = my own suggested rule or default value for stream2clip, not taken from any source. Copyleft / non-permissive code is flagged ⚠ (study the ideas, do not copy code into MIT stream2clip).

## 1. Open-source projects: how auto zoom, keyword emphasis, emoji, SFX and jump cuts are implemented

### Takeaway
No surveyed OSS clipper publishes a full signal→effect rulebook. Effects are either (a) fixed rules on a small number of anchors (hotclip: at most 3 SFX per clip, a "ding" at the emotional peak, a "whoosh" on hard-cut seams, a soft tick when the hook text appears; SharkyClips: a "subtle smart zoom" on peaks and facecam reactions, plus a "peak flash" opener), or (b) LLM choices (reelsaw's AI-picked key words, OpenShorts' Gemini-generated FFmpeg filters). I found no OSS project with documented keyword→emoji mapping. The projects with the most transferable rules are ⚠AGPL (hotclip, reelsaw, Clips Kitty), so stream2clip should take their parameters and ideas but not their code.

### Cited Findings
**Licences (check before reuse)**
- OpenShorts: core is MIT. The `cloud/` directory is source-available under the "OpenShorts Commercial License", and self-hosting never needs it (V) — [OpenShorts README](https://github.com/mutonby/openshorts)
- ⚠ SupoClip: the sources disagree. A search snippet of the README and this repo's earlier note say AGPL-3.0 (S/P) — [SupoClip README (HEAD snippet)](https://raw.githubusercontent.com/FujiwaraChoki/supoclip/HEAD/README.md). The current `main` README says "SupoClip Noncommercial Source License, version 1.1": noncommercial self-hosting is allowed, and company, agency or team use needs written permission (V) — [SupoClip README (main)](https://raw.githubusercontent.com/FujiwaraChoki/supoclip/main/README.md). Either way, no code reuse.
- ⚠ hotclip: "AGPL-3.0-only" (V) — [hotclip README](https://github.com/xixihhhh/hotclip)
- ⚠ reelsaw: AGPL-3.0. Hosted-billing `ee` dirs are under a separate licence (V) — [reelsaw README](https://github.com/osbytes/reelsaw)
- ⚠ Clips Kitty (clips-studio): app is "GNU AGPL-3.0-or-later". The SDK is MIT and the catalog file is CC0-1.0 (V) — [clips-studio README](https://github.com/ColinGPT9/clips-studio)
- SharkyClips: MIT (V) — [sharkyclips README](https://github.com/utkualsir/sharkyclips). NeonClipping: MIT (P) — [neonclipping](https://github.com/iamajmeena/neonclipping)
- Captacity: MIT (V, repo sidebar) — [unconv/captacity](https://github.com/unconv/captacity)
- auto-editor: the README states "Public Domain" (Unlicense for assets). Its bundled ae-ffmpeg is LGPLv3 (S) — [auto-editor](https://github.com/wyattblue/auto-editor), [PyPI](https://pypi.org/project/auto-editor)

**Auto zoom / punch-in**
- SharkyClips: "a subtle smart zoom on the peak moments and on your facecam when you react". It also has an optional "peak flash" opener and a slow-motion replay with a "REPLAY" badge. The README gives no zoom amount, duration, easing or frequency cap (V) — [sharkyclips README](https://github.com/utkualsir/sharkyclips)
- OpenShorts: the README has no speech-driven auto zoom. Its "AI video effects" are "Gemini-generated FFmpeg filters". Ken Burns zoom/pan is used only on generated B-roll images in AI Shorts. Layout (TRACK/GENERAL/SPLIT/SCREENCAST) is picked per scene by Gemini, with a face-tracking crop fallback (MediaPipe + YOLOv8) (V) — [OpenShorts README](https://github.com/mutonby/openshorts). Third-party docs list "Dynamic zooms" among editing tools (S) — [mintlify wiki](https://mintlify.wiki/mutonby/openshorts/guides/editing-clips)
- ⚠ Clips Kitty does not zoom at all. Framing is "crop-only: never stretched, never distorted". It cuts to the active speaker "instead of panning across", and sports framing "pans with the play and never zooms" (V) — [clips-studio README](https://github.com/ColinGPT9/clips-studio)
- ⚠ hotclip has no punch-in zoom. Smart framing follows a face smoothly only when it "really leaves the frame" (确实超出画幅才平滑跟随), and falls back to a center crop when there is no face (V) — [hotclip README](https://github.com/xixihhhh/hotclip)
- Tella's "add-zooms" Claude Code skill (GitHub `louisedesadeleer/add-zooms`) adds hard-cut punch-zooms (S) — [Tella skill page](https://www.tella.com/skills/add-zooms)
- I found no GitHub repo under the name "SharkyClips punch-in" beyond utkualsir/sharkyclips (S) — search, 2026-11-22.

**Keyword emphasis in captions**
- ⚠ reelsaw: "AI picks key words for each clip", shown in colour and a larger size, and editable. Readability limits: about two short lines, breaks at commas and sentence ends, minimum on-screen time **0.7 s + 0.3 s per word**, reading speed capped at **20 characters/s**. Word highlight uses ASS karaoke. Settings include "words on screen" (1 = one word at a time) and uppercase. In split/stack sections of 2.5 s or more, captions move to the seam between panes. Defaults are per project with per-clip overrides (V) — [reelsaw README](https://github.com/osbytes/reelsaw)
- ⚠ hotclip caption styles switch with one control (一档切换): keyword highlight, big pop-up text, bubble, and dynamic minimal. The bubble style is "自适应圆角气泡底、关键词渐变金字、弹性入场" (adaptive rounded bubble, gradient-gold keywords, elastic entrance). The big-text style lights up word by word (逐词点亮). Bubble captions are rendered in offscreen Chromium for effects libass can't do (V/P) — [hotclip README](https://github.com/xixihhhh/hotclip)
- Captacity (MIT) only highlights the current word: `highlight_current_word`, `word_highlight_color`, `line_count`, `font_size`, `stroke_width`, `shadow_strength`, `padding`. It has no semantic keyword emphasis (V) — [captacity](https://github.com/unconv/captacity)
- ⚠ Clips Kitty caption styling: "colour, size, position, words per line, casing, or off". A second speaker can get "another colour" (V) — [clips-studio README](https://github.com/ColinGPT9/clips-studio)
- NeonClipping ships 5 caption styles (GTA Neon, Impact, Clean, Hormozi, MrBeast) (P) — [neonclipping](https://github.com/iamajmeena/neonclipping)

**Emoji insertion**
- None of OpenShorts, SupoClip, Clips Kitty, SharkyClips, reelsaw or Captacity documents emoji insertion (V, READMEs above). Clips Kitty's site only describes "Word-synced captions in your style" (V) — [Clips Kitty site](https://colingpt9-clips-studio.static.hf.space/index.html)
- No OSS repo combining Whisper captions with keyword→emoji mapping was found. Building blocks exist: `BrianHung/emoji-keywords` ("emoji keywords from unicode") and the Remotion `template-tiktok` captions (S) — [emoji-keywords](https://awesome.ecosyste.ms/projects/github.com%2Fbrianhung%2Femoji-keywords), [remotion template-tiktok](https://github.com/remotion-dev/template-tiktok)

**Sound-effect placement**
- ⚠ hotclip: rule-based SFX, "每条最多 3 个宁缺毋滥" (at most 3 per clip; better none than bad). Placements: a whoosh on hard-cut seams of multi-segment or cold-open edits, a "叮" (ding) at the emotional high point, and a light sound when the hook text appears. Sounds are synthesized locally and replaced by dropping in a same-named wav (V) — [hotclip README](https://github.com/xixihhhh/hotclip)
- ⚠ reelsaw CLI: a sound of **≤ 8 s** plays as a one-shot at full level. Anything longer is treated as music: ducked under speech, faded and looped. Output loudness is −14 LUFS with a peak limiter (V) — [reelsaw README](https://github.com/osbytes/reelsaw)
- SharkyClips: "Sound effects are made on your PC". Music is suggested per clip, starts at its strongest part, ducks under the voice, and is mixed at −14 LUFS. Swears are bleeped in 11 languages, re-checked after render, and widened if still audible (V) — [sharkyclips README](https://github.com/utkualsir/sharkyclips)

**Openers / flash effects**
- ⚠ hotclip: the hook sentence is burned in large text over the top third for the first 2 s, and skipped if no hook was written. "Flash-forward" shows the hottest 0.3–1 s before the clip starts, then cuts back. It is auto-alternated with cold-open (高潮前置). Both "定位失败自动跳过": if localisation fails, the effect is skipped (V) — [hotclip README](https://github.com/xixihhhh/hotclip)

**Jump cuts / filler cuts**
- SharkyClips: silences and fillers are cut "with tiny crossfades but never inside a laugh". Edges snap to word boundaries, and the local LLM can extend them a few seconds for setup or payoff (V) — [sharkyclips README](https://github.com/utkualsir/sharkyclips)
- ⚠ reelsaw: fillers, repetitions and false starts become jump cuts located by forced alignment. Each seam is "listened" to and verified, and each fix is accept/reject in the transcript. Off by default (`DISFLUENCY_REMOVAL`) (V) — [reelsaw README](https://github.com/osbytes/reelsaw)
- auto-editor: `--edit audio` is the default method, with thresholds in % or dB (e.g. `audio:-19dB`; older default `threshold=4%`). `--margin` pads cuts and defaults to **0.2 s**. Silent parts can be sped up instead of cut (S) — [auto-editor](https://github.com/wyattblue/auto-editor), [PyPI](https://pypi.org/project/auto-editor)

**How effects are decided (LLM vs rules)**
- ⚠ hotclip: "LLM 只负责«挑哪段»并引用原文": the LLM only picks the segment and quotes text, and timestamps come from word alignment. SFX, cold-open and flash-forward are rule-decided. A highlight counts as real (爆点) only when loudness, danmaku and laughter rise in the same second (V/P) — [hotclip README](https://github.com/xixihhhh/hotclip)
- OpenShorts: the LLM decides layout and FFmpeg effects (V) — [OpenShorts README](https://github.com/mutonby/openshorts)

### Inferences
- stream2clip's current "one SFX chosen by dominant chat reaction, snapped to the sound onset" is already close to hotclip's rule-based "ding at emotional peak". The missing parts are hotclip's **budget** (≤3 SFX per clip), its **seam SFX** (whoosh on internal cuts, if stream2clip ever joins segments), and its **skip-on-uncertainty** rule.
- The safest OSS pattern for visual effects is "rules on a few strong anchors + skip if unsure", not "LLM decides everything". It matches stream2clip's no-built-in-LLM principle.
- reelsaw's caption readability numbers (0.7 s + 0.3 s/word, ≤20 cps) are the only quantified caption guardrail found in OSS. They were written for Latin script, so CJK limits need separate tuning (see Gaps).
- SharkyClips' "never inside a laugh" rule is directly reusable: stream2clip already detects laughter (chat 草/ｗ/ㅋㅋ plus audio).

### Gaps
- I did not verify ClipsAI, AI-Youtube-Shorts-Generator (SamurAIGPT) or the NeonClipping effect code in this session. They are not known to have zoom, emoji or SFX logic, but that is unconfirmed.
- I found no code paths for SharkyClips' smart zoom (file names, zoom factor, easing). Its MIT licence would allow reading `backend/` for parameters. Not done here.
- I found no documented OSS keyword→emoji dictionary used in a clipper, and no OSS "viral caption" generator with documented emoji logic.

## 2. Commercial tools: documented rules for when effects fire, user controls, and overuse complaints

### Takeaway
Commercial help centers document **controls**, not **rules**. Captions exposes zoom intensity 0/1/2 and three curves (Linear/Ease/Instant). OpusClip has on/off toggles (AI Emoji, Auto SFX, AI B-roll "Find spots") and says its Auto SFX "skips some to avoid clutter". Submagic's documented zoom is manual or bundled into "Magic B-rolls". Trigger descriptions ("vocal emphasis: louder volume, pitch changes, pauses"; "audio peaks"; "scene changes") come from vendor marketing blogs, mostly a competitor's (OpusClip). Few direct overuse complaints are indexed. The one research data point is that keyword highlighting is "too distracting" for everyday viewing.

### Cited Findings
**OpusClip**
- AI Emoji: "uses AI to automatically add relevant emojis to your subtitles". Turned on via AI Enhance → "AI Emoji". Manual: select a word → Add → Emoji. No density control or placement rule is documented (V) — [OpusClip help: AI Emojis/Keywords](https://help.opus.pro/docs/article/ai-emojis-keywords)
- I found no dedicated help article for the keyword highlighter. A third-party claim of "+65% watch time" is unverified (S) — [help.opus.pro llms.txt](https://help.opus.pro/llms.txt)
- Auto SFX "watches your video, detects key moments". It covers "transitions, impacts, UI moments, reactions and more" from a "curated library" (not generated), reads both on-screen action and speech (so it is language-independent), and adds sound only where it fits, skipping some to avoid clutter. Clips that need none get "No sound effects needed for this clip". Cost is 7 credits/min. It can be saved into a custom **recipe** to auto-apply. Users can move, re-volume, split or delete each sound. To rerun, delete all Auto SFX sounds (V) — [OpusClip help: Auto SFX](https://help.opus.pro/docs/article/auto-sfx.md)
- AI B-roll: "Find spots" "reads your transcript and suggests where B-roll fits" (about 30 s). Users can deselect spots. Fill type is AI image, AI video or stock. Rerunning replaces auto B-roll and keeps manual B-roll. No density or spacing rule is documented (V) — [OpusClip help: AI B-roll](https://help.opus.pro/docs/article/ai-broll.md)
- OpusClip separates "Brand Kit", "Brand Template" and "Recipes", and exposes brand templates via API (`get-brand-templates`). The schema page did not render (V for titles only) — [help.opus.pro llms.txt](https://help.opus.pro/llms.txt)
- OpusClip's own blog claims its zoom "analyzes your speech patterns and automatically adds zooms at moments of emphasis" (punchlines, statistics, emotional peaks), with adjustable "zoom intensity and frequency" (S, vendor) — [OpusClip blog: best auto-zoom tools](https://www.opus.pro/blog/best-auto-zoom-in-tools)

**Captions (Captions/Mirage)**
- AI Zoom applies zooms to "the most engaging parts". Intensity is **0 / 1 / 2**, the animation curve is **Linear / Ease / Instant**, and there are Edit / Delete / Delete All controls. No frequency control is documented (V) — [Captions docs: Zoom](https://captions.ai/help/docs/visual/zoom.md)
- Per-word effects (iOS): Supersize, Emphasize (emphasis colour), Emojis (standard or animated), Underline, Effects (background), **Sounds (per-word SFX)**, Color, Font, Timing. The doc describes manual application only (V) — [Captions docs: Word effects](https://captions.ai/help/docs/captions/word-effects.md)

**Submagic**
- The help center documents manual zoom only: B-roll tab → magnifier-plus icon. Named effects include "Zoom Fast", "Crash Zoom Out 2", "Fast Snap" and "Steady Hold". A zoom on a B-roll or transition applies only to that segment (V) — [Submagic care: add zooms](https://care.submagic.co/en/article/how-to-add-zooms-to-your-video-au3qiw/)
- "Magic B-rolls" reads the transcript and auto-adds B-rolls **plus zoom effects and transitions**. Sound effects are added per subtitle line via a speaker icon, and audio is "automatically generated from B-rolls" (S, feature pages) — [Submagic B-rolls](https://submagic.co/features/b-rolls), [Submagic auto zooms](https://submagic.co/features/auto-zooms), [Submagic SFX](https://www.submagic.co/features/add-sound-effects-to-video)
- Per OpusClip's blog, Submagic detects vocal emphasis from "louder volume, pitch changes, pauses" and adds "subtle" punch-ins (S, competitor's claim) — [OpusClip blog](https://www.opus.pro/blog/best-auto-zoom-in-tools)

**Other tools (all from one vendor blog, S)**
- CapCut "Beat Zoom" detects tempo and intensity in the audio and zooms on drops, kicks and snares. "Auto Zoom" analyzes speech. Descript "Fancy Captions" zoom on specific words or phrases and can apply a zoom to every instance of a word. Kapwing "Smart Zoom" uses "scene changes and audio peaks". VEED zooms "at regular intervals or synced to audio peaks" with speed (slow/medium/fast) and intensity (subtle/moderate/dramatic). Zubtitle zooms on emphasis or pauses, or when a keyword appears in captions — [OpusClip blog](https://www.opus.pro/blog/best-auto-zoom-in-tools)
- The same blog's qualitative rules: "use zoom as your primary motion effect, then add one or two complementary elements". For long-form, zoom "sparingly at key moments rather than continuously". TikTok expects "fast-paced, energetic zooms" and LinkedIn/Facebook "professional, understated". It gives no numeric cadence (S) — [OpusClip blog](https://www.opus.pro/blog/best-auto-zoom-in-tools)
- StreamLadder: AI captions add "highlights and emojis", which are editable. Styles cover size, colour, highlights, emojis and rotation, per word or per group. Zooms and SFX are premium, and watermarked on free (S) — [StreamLadder captions](https://streamladder.com/features/captions), [StreamLadder zoom](https://streamladder.com/features/zoom-in)

**Complaints about overuse**
- A G2 reviewer of OpusClip: "Sometimes I feel like it does a little bit too much" (S) — [G2 OpusClip reviews](https://g2.com/products/opusclip/reviews?page=2)
- Unite.ai found every Submagic clip had animated captions and emojis, which suggests fixed density (S) — [Unite.ai Submagic review](https://www.unite.ai/submagic-review)
- OpusClip's blog says some tools' zooms are "robotic, predictable" and "scream AI-generated". This is vendor opinion (S) — [OpusClip blog](https://www.opus.pro/blog/best-auto-zoom-in-tools)
- Reviews mostly complain that "the AI lacks nuance" and needs manual fixes (S) — [eesel OpusClip reviews](https://www.eesel.ai/blog/opusclip-reviews)

### Inferences
- The common commercial control model is **toggle per effect family + discrete intensity (3 levels) + easing curve + accept/reject per instance + rerun replaces auto items and keeps manual ones**. stream2clip can copy this UX without copying any code. Keeping manual edits on rerun (OpusClip B-roll) is especially worth adopting.
- OpusClip's "No sound effects needed for this clip" shows that a **null result is a valid output**. stream2clip should allow zero effects when the signals are weak.
- Trigger signals in commercial marketing (loudness peaks, pitch change, pauses, keywords, scene changes, beats) are all things stream2clip already has or can compute cheaply. Its unique extra signal is **chat reaction type**, which no commercial tool documents using for effect choice.

### Gaps
- Descript Underlord, Vizard, CapCut "AI auto edit" and Captions "AI Edit" help pages were not fetched. Their trigger rules remain unverified.
- I found no official zoom scale percentages, durations, or "every N seconds" cadence from any vendor. Common creator advice such as "pattern interrupt every 2–3 s" has no reliable source in this session.
- Reddit threads specifically about "too many zooms/emojis" were not indexed by the search tool.

## 3. Research: automatic editing effects, emphasis detection, laughter/excitement timing, viewer preference

### Takeaway
Academic work covers **effect recommendation** (AutoTransition for transitions, Soundify for SFX, B-Script for B-roll timing) and **prominence/emphasis detection** from prosody, but not the combined "where to zoom/emoji" problem in short-form clips. Viewer studies of keyword highlighting and emoji captions show modest comprehension and load benefits for some groups (DHH, neurodivergent). They also show keyword highlights judged "too distracting" for everyday captions. That supports sparse, opt-in emphasis.

### Cited Findings
- **AutoTransition** (ECCV 2022) frames transition choice as multimodal retrieval from shots plus audio, using a multimodal transformer. In a user study it scored comparably to professional editors and reportedly cut editing time by about 300×. The dataset and code are released (S, abstract-level) — [arXiv 2207.13479](https://arxiv.org/abs/2207.13479). Follow-up **V-Trans4Style** (Jan 2025) adds production-style conditioning and the AutoTransition++ 6k-video style-labelled subset (S) — [arXiv 2501.07983](https://arxiv.org/abs/2501.07983)
- **Soundify** (UIST 2023, CMU + Runway) retrieves studio SFX from existing libraries instead of generating audio. It splits video into scenes, classifies effects and ambients, and predicts the top-5 sound labels per scene. Design principles: "surface, synchronize, spatial, stack" (pan/volume follows video changes). Evaluated with 889 raters: better matching, lower workload, faster completion (S) — [arXiv 2112.09726](https://arxiv.org/abs/2112.09726), [UIST paper PDF](https://chuanenlin.github.io/papers/soundify-uist2023.pdf)
- **B-Script** (CHI 2019, Adobe + Harvard): a transcript-based B-roll editor with a recommender trained on expert annotations for both content and **placement**. Within-subject study, N=110: the transcript UI was faster and easier, and videos made with recommendations were rated more engaging (S) — [arXiv 1902.11216](https://arxiv.org/abs/1902.11216)
- A survey of what editors want from AI video tools (2021) exists (S, bibliography only seen) — [arXiv 2109.07809](https://arxiv.org/pdf/2109.07809)
- **Emphasis/prominence detection**: pitch accent is the most common acoustic marker of emphasis (S) — [Jurafsky group, Stanford](https://web.stanford.edu/~jurafsky/p1034.pdf). In spontaneous speech, F0 curve shape and magnitude plus duration and energy beat lexical/syntactic features (S) — [Mishra et al., Interspeech 2012](https://www.isca-archive.org/interspeech_2012/mishra12_interspeech.html). Adding head-movement video features cut the prominence-detection EER by about 80% relative in noisy speech (S) — [Heckmann 2018](https://eld.bl.uk/catalog/100054536461_0x000001). Crowdsourced prominence is defined as a 0–1 scalar averaged from non-expert binary labels (S) — [arXiv 2310.08464](https://arxiv.org/html/2310.08464v2)
- **Google Expressive Captions** (Android Live Caption) shows intensity with **capitalisation** (e.g. "HAPPY BIRTHDAY!" vs "Happy birthday!"), labels vocal bursts (sighing, grunting, gasping), and adds a "Lengthen words" option. It runs on-device in real time and is an opt-in "Add styles to captions" setting (S) — [Google blog](https://blog.google/products/android/google-android-expressive-captions), [Live Caption help](https://support.google.com/accessibility/android/answer/9350862?hl=en)
- **Viewer studies**: "Useful but Distracting" (language learners, N=49 online) preferred time-synced keyword highlights for learning but found them too distracting to replace standard captions in everyday viewing (S) — [arXiv 2307.05870](https://arxiv.org/abs/2307.05870). "Adaptive Captioning with Emotional Cues" (ACII 2025, arXiv Mar 2026): four prototypes with facial-expression, gesture, keyword-highlight and emoji cues, 24 participants (pilot + main). "Certain prototypes" reduced self-reported cognitive load and improved comprehension versus plain captions. Users asked for customisation, including differing comfort with emoji (V, abstract) — [arXiv 2603.15977](https://arxiv.org/abs/2603.15977). A DHH lecture-video study found highlighting easier to follow with lower task load (S; exact paper not confirmed, link may be one of two NSF records) — [NSF PAR record](https://par.nsf.gov/servlets/purl/10170034)
- Industry claims that word-by-word highlighting raises watch time 18–23% cite no study (S, treat as unverified) — [DEV Community post](https://dev.to/clamper_ai/how-ai-caption-styles-affect-watch-time-and-engagement-409i)

### Inferences
- For emphasis without an LLM, stream2clip can rank words by **prosodic prominence**: per-word RMS loudness z-score, F0 peak z-score and lengthened duration relative to the speaker's running baseline. faster-whisper word timings already give the word boundaries. This is the literature-backed version of the vendor claim of "louder volume, pitch changes, pauses".
- Expressive Captions provides a defensible, accessibility-grounded style rule: **ALL-CAPS (or supersize) when loudness is well above the speaker baseline**, and **bracketed vocal-burst labels** ([laughs], [gasps]). stream2clip already detects laughter and onsets.
- Soundify's "synchronize" principle and B-Script's placement recommender both treat **timing as a first-class output separate from choosing the content**. stream2clip's existing onset snapping is that same design.
- Research supports keeping emphasis sparse and configurable (distraction, clutter, individual comfort with emoji). An effect **density** slider and a full **off** switch should exist.

### Gaps
- I found no paper that evaluates auto zoom or punch-in on viewer retention or preference, and no controlled study of emoji density in short-form captions.
- No paper on "reaction-aware" editing that uses live-chat reaction type to pick effects was found in this session. Livestream highlight detection from chat exists (covered in earlier notes) but stops at selection.
- Beat-synced effect research (music-video editing) was not searched in depth. CapCut "Beat Zoom" is the only beat-sync evidence here (vendor blog).
- Laughter-detection papers specifically about effect timing were not searched. The OSS evidence is hotclip's same-second loudness+danmaku+laughter rule and SharkyClips' sherpa-onnx laughter/shout detection (P).

## 4. VTuber specifics: avatar expression/motion and chat reactions as effect triggers

### Takeaway
The live-streaming toolchain already has a mature **trigger → action with cooldown and auto-reset** model. VTube Studio's Twitch Hotkey Triggers fire expressions, item scenes, VFX presets and model moves from bits, subs, redeems, chat commands and more. Streamer.bot can trigger VTS hotkeys from any event. No clip editor I found reads VTS expression or parameter logs to place post-production effects. That gap is stream2clip's to fill, using the same cooldown and reset semantics.

### Cited Findings
- VTube Studio Twitch Hotkey Triggers: hotkeys can fire from gift subs (within a configured range, e.g. 5 → "Visual Effects Preset"), bits (e.g. "over 100 bits"), channel-point redeems, power-ups, chat commands (space-separated list, restrictable to self/VIPs/subs/mods), subs, follows, raids, shoutouts and ad-break starts. One hotkey can have several triggers. Repeated triggers act like repeated manual presses, so an expression hotkey toggles (V) — [VTS wiki: Twitch Hotkey Triggers](https://github.com/DenchiSoft/VTubeStudio/wiki/Twitch-Hotkey-Triggers)
- Same page: a **cooldown** blocks Twitch re-triggering while active. "Reset after cooldown" auto-reverts: toggle expression (.exp3) turns off, Move Model returns to position, Item Scene items unload, Effect Preset reloads the previous VFX, and model changes revert. A manual action during cooldown cancels the pending reset. There is also a "Twitch Emote Dropper" feature toggle (V) — [VTS wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Twitch-Hotkey-Triggers)
- Streamer.bot's VTube Studio integration has a "Hotkey Triggered" trigger (fires on manual or API hotkey use) and "Trigger Hotkey" / "Trigger Hotkey by Name" sub-actions, so any chat or Twitch event can drive avatar reactions (S) — [Streamer.bot: Trigger Hotkey](https://docs.streamer.bot/api/sub-actions/integrations/vtube-studio/trigger-hotkey), [Trigger Hotkey by Name](https://docs.streamer.bot/api/sub-actions/integrations/vtube-studio/trigger-hotkey-by-name)
- ⚠ hotclip uses **facial-expression peaks** (YuNet + FER+, both MIT models per its README) as a highlight signal alongside loudness, cut density and motion (V/P) — [hotclip README](https://github.com/xixihhhh/hotclip)
- SharkyClips zooms "on your facecam when you react", which is a reaction-triggered zoom for a human facecam (V) — [sharkyclips README](https://github.com/utkualsir/sharkyclips)
- This repo's earlier notes found no clipper that recognises VTuber avatars, and Clips Kitty's webcam+game mode explicitly excludes VTubers ("People on camera only, no VTubers") (P) — [clips-studio](https://github.com/ColinGPT9/clips-studio)
- Audio-visual fusion (head movement) improves prominence detection in noise (S) — [Heckmann 2018](https://eld.bl.uk/catalog/100054536461_0x000001). By analogy, avatar head-motion parameters from VTS could be used the same way (Inference, not tested).

### Inferences
- **Expression hotkey = explicit intent signal.** When the streamer fires a "surprised" or "laugh" expression hotkey within about ±1 s of the chat-corrected peak, stream2clip can (a) raise confidence in the category, (b) override the chat-dominant category when they disagree, and (c) use the hotkey timestamp as the anchor, since it is the streamer's own timing (Proposal).
- **VTS parameter spikes as emphasis anchors**: high velocity of `FaceAngleX/Y/Z`, sudden `MouthOpen` maxima, or eye-open jumps can serve as the "visual prominence" channel next to audio prominence (Proposal; parameter names per VTS API, not re-verified today).
- **Chat-triggered stream overlays are the live analogue of post-production effects.** If the stream already showed a VTS item drop or VFX preset at that moment (logged by the session recorder), the clip should **not** add a second competing overlay effect. Treat logged live effects as "occupied" time (Proposal).
- Borrow VTS's **cooldown** and **reset_after** semantics directly into the preset format (see §5): every effect has a cooldown and an explicit end state.
- Superchat/bits/gift events map naturally to "hype" effects (caption CAPS, ding/cash SFX, short confetti). Viewer names or amounts should not be burned into clips by default (privacy; Proposal).

### Gaps
- I did not verify any tool that consumes VTS parameter logs offline for editing. None was found.
- The exact current VTube Studio API parameter list and expression-state events were not re-fetched this session.

## 5. Templates/presets: how editors package reusable effect bundles, and a preset format for stream2clip

### Takeaway
Across editors, a reusable effect bundle is **(1) a set of exposed parameters with ranges/defaults, (2) timing expressed relative to an anchor (clip start/end, segment start, protected intro/outro), (3) referenced assets by ID or path, (4) per-project defaults with per-item overrides**. Specific mechanisms: Premiere MOGRT Responsive Design–Time protects intro/outro regions. Fusion macros publish chosen controls via `InstanceInput`. CapCut drafts store microsecond timing with segment-relative keyframes and effects by `resource_id`. AviUtl scripts declare trackbars as `--track0:name,min,max,default,step`. reelsaw and hotclip save "layer templates" and "recipes" with timing relative to the clip. stream2clip's preset should add **event anchors** (peak, onset, word, laugh, expression hotkey) and **guardrail fields** (cooldown, max per clip, exclusivity, accessibility).

### Cited Findings
**Premiere / After Effects MOGRT**
- Responsive Design–Time lets a template protect intros, outros and "any arbitrary region" so animation timing holds when the clip is stretched or trimmed (S) — [Adobe help: Responsive Design](https://helpx.adobe.com/sea/after-effects/using/responsive-design.html)
- Forum reports say only intro/outro protected regions carry over to Premiere (middle regions work only in AE). A sound effect inside a protected region can stop a MOGRT from extending. Bugs were reported 2020–2025 (S, user reports) — [Adobe community 24530](https://community.adobe.com/questions-529/motion-graphic-template-responsive-design-time-protected-region-bug-in-premiere-pro-24530), [Adobe community: audio in protected regions](https://community.adobe.com/t5/premiere-pro-discussions/adding-audio-in-mogrt-mess-with-a-protected-regions/td-p/14971635)

**DaVinci Resolve Fusion macros**
- Title templates are "compositions saved from Fusion as macros with published controls" shown in the Edit/Cut page Inspector (S, manual excerpt) — [Resolve 18.6 manual excerpt](https://www.steakunderwater.com/VFXPedia/__man/Resolve18-6/DaVinciResolve18_Manual_files/part2582.htm)
- In the `.setting` file, published controls are `InstanceInput` entries with `SourceOp`, `Source`, `Name` and `Page`. Inspector order follows the InstanceInput order. Setting `Page` in the InstanceInput keeps files smaller (S) — [Zenn article (JA)](https://zenn.dev/2ndillness/articles/4a4eb4d10e60c4), [Blackmagic forum examples](https://forum.blackmagicdesign.com/viewtopic.php?p=973864)

**CapCut / 剪映 drafts and templates**
- `draft_content.json` is the timeline. All times are **microseconds**. Segments carry `target_timerange` and a `material_id`. Peripheral materials go in ordered `extra_material_refs`. Stickers, filters, animations and effects are identified by a `resource_id` resolved against CapCut's effect cache. Keyframes live in `common_keyframes` with a `time_offset` **relative to segment start** and Bezier curves. Scale must be keyed on both X and Y. In/out animation durations must not exceed the segment. Transitions attach to the outgoing segment. Positions are normalised to [-1, 1] with Y up (V) — [capcut-cli draft-schema overview](https://cdn.jsdelivr.net/npm/capcut-cli-david@1.14.1/docs/draft-schema/00-overview.md)
- pyJianYingDraft: newer 剪映 versions encrypt `draft_content.json`, so template features only support 剪映 ≤ 5.9. Imported template tracks cannot directly receive clips, transitions or effects. Licence is unclear (a Gitee mirror says "Not specified") (S) — [pyJianYingDraft GitHub](https://github.com/GuanYixuan/pyJianYingDraft), [PyPI](https://pypi.org/project/pyjianyingdraft/)

**AviUtl / YMM4 (JP)**
- AviUtl `.anm` animation-effect scripts declare trackbars as `--track0:名前,最小値,最大値,初期値,刻み` and read them as `obj.track0`. Files go in the `script` folder (S) — [scrapbox example](https://scrapbox.io/nanikani-shugo/%E4%BD%95%E5%87%A6%E3%81%8B%E3%82%89%E3%81%A8%E3%82%82%E3%81%AA%E3%81%8F%E7%99%BB%E5%A0%B4%E3%82%92%E3%82%B9%E3%83%9E%E3%83%96%E3%83%A9%E3%81%AE%E3%83%AD%E3%82%B4%3F%E3%81%A3%E3%81%BD%E3%81%8F%E3%81%99%E3%82%8B). Distributed scripts must be Shift_JIS with CRLF (S) — [AviUtl scrapbox: script not recognised](https://scrapbox.io/aviutl/%E3%82%B9%E3%82%AF%E3%83%AA%E3%83%97%E3%83%88%E3%81%8C%E8%AA%8D%E8%AD%98%E3%81%95%E3%82%8C%E3%81%AA%E3%81%84). AviUtl2 uses `.anm2` scripts labelled as アニメーション効果 (S) — [BOOTH TA-Delay-type listing](https://booth.pm/en/items/8713264)
- YMM4 ships 15 built-in animation effects (e.g. 反復移動, 砕け散る), added per item from the right-hand エフェクト panel → アニメーション (S) — [coconala explainer](https://coconala.com/blogs/5189435/545252)
- A third-party "テキストテンプレートプラグイン" saves text decoration as one-click templates (published 2025-12-17; v3.0.2 dated 2026-02-22). I could not confirm a built-in YMM4 item/effect template feature (S) — [BOOTH: YMM4 text template plugin](https://booth.pm/ja/items/7768497)

**Clipper-level presets (OSS and SaaS)**
- ⚠ reelsaw "layer templates" save a look (logo, follow card, watermark, music bed, intro/outro) **with timing relative to the clip**, applied to selected clips or as the project default. Fade settings are style fields (`fadeIn`, `fadeOut`, `bumperTransition`) (V) — [reelsaw README](https://github.com/osbytes/reelsaw)
- ⚠ hotclip: a brand-style template stores accent colour, caption size/position and logo watermark, applied to every clip. Three output plans are one-click switchable (默认出片/带货全家桶/极简省时). "栏目配方" (v0.35.0) saves "品牌、音乐、字幕、分屏和选段规则" (brand, music, captions, split layout and selection rules) (V) — [hotclip README](https://github.com/xixihhhh/hotclip)
- SharkyClips: export presets per platform (size, fps, bitrate, length limit, caption safe zones) and a brand kit (logo, @handle, intro/outro cards, caption style). Easy vs Pro modes (V) — [sharkyclips README](https://github.com/utkualsir/sharkyclips)
- OpusClip: Brand Kit vs Brand Template vs Recipes. A recipe can carry Auto SFX so it applies automatically (V) — [OpusClip Auto SFX](https://help.opus.pro/docs/article/auto-sfx.md), [llms.txt](https://help.opus.pro/llms.txt)
- VTube Studio's trigger config (trigger ranges, cooldown, reset-after-cooldown) is effectively a preset format for live effects (V) — [VTS wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Twitch-Hotkey-Triggers)

### Inferences
**Design principles for a stream2clip effect preset (Proposal)**
- **Exposed parameters with ranges**, like AviUtl `--track0` and Fusion `InstanceInput`: each effect declares `params: {name: {min, max, default, step}}` so the GUI can render sliders. Users only see what the preset author published.
- **Anchors instead of absolute times**: like CapCut's segment-relative `time_offset` and MOGRT's protected regions, every effect is placed relative to an event: `clip_start`, `clip_end`, `peak`, `onset` (nearest sound onset to peak), `word` (a selected caption word), `laugh_start`, `laugh_end`, `vts_expression` (hotkey on), `vts_param_spike`, `cut_seam`. Add `offset_ms` and `duration_ms`, or `until: word_end | utterance_end`.
- **Protected intro/outro** (MOGRT): an effect's own in/out animation lengths are fixed, and only the hold stretches. Clamp so in + out ≤ duration (the CapCut rule).
- **Assets by relative path + hash + licence** (CapCut uses cache `resource_id`, hotclip uses replace-by-filename): `assets: [{id, path, sha256, license, source_url}]`, so presets can be shared without bundling questionable files.
- **Conditions** on stream2clip's existing signals: dominant chat category and its share, chat burst z-score, superchat present, laughter detected, avatar box present, VTS expression name, speaker label.
- **Guardrail fields** borrowed from VTS and hotclip: `cooldown_ms`, `max_per_clip`, `exclusive_group` (only one "hero" effect at the peak), `priority`, `skip_if_unsure`, `reset_after`, `reduced_motion_fallback`, `flash_safe: true`.
- **Project default + per-clip override** (reelsaw), and **rerun keeps manual edits** (OpusClip B-roll).
- Store the preset in **UTF-8 YAML/JSON** (not Shift_JIS as AviUtl requires). Include `schema_version` and `min_app_version`, since CapCut/剪映 template breakage came from undocumented format changes and encryption.

**Example preset (Proposal; all numbers are suggested defaults, not sourced)**
```yaml
schema_version: 1
id: s2c.default.reaction-pop
name: "Reaction pop (default)"
author: stream2clip
license: CC0-1.0
budget: {max_visual_effects: 3, max_sfx: 3, min_gap_ms: 2000}   # hotclip caps SFX at 3/clip
accessibility: {flash_safe: true, reduced_motion: false}
effects:
  - id: peak_punch_in
    type: zoom
    when: {chat.burst_z: ">=2.0"}
    anchor: onset            # nearest sound onset to the chat-delay-corrected peak, search ±500 ms
    offset_ms: -40
    in: {ms: 120, curve: instant_or_ease}   # Captions offers Linear/Ease/Instant
    hold: {until: utterance_end, max_ms: 2500}
    out: {ms: 400, curve: ease_out}
    params: {scale: {min: 1.0, max: 1.3, default: 1.12, step: 0.02}}
    intensity_from: chat.burst_z            # mapped to 3 discrete levels like Captions 0/1/2
    center: avatar_box_or_frame_center
    exclusive_group: hero
    cooldown_ms: 4000
    skip_if_unsure: true                    # hotclip: localisation fails → skip
    reduced_motion_fallback: caption_supersize
  - id: reaction_emoji
    type: sticker_emoji
    when: {chat.dominant_share: ">=0.4"}
    map: {laugh: "😂", surprise: "‼️", cute: "💕", hype: "🔥", superchat: "✨"}
    anchor: peak
    duration_ms: 1200
    max_per_clip: 2
    avoid: [captions_safe_zone, avatar_face_box]
  - id: emphasis_word
    type: caption_emphasis
    select: {by: prosodic_prominence, window_ms: [-2000, 1500], max_per_line: 1}
    style: {supersize: 1.25, color: accent, caps_if_loudness_db_over_baseline: 9}
  - id: reaction_sfx
    type: sfx
    map: {laugh: pop.wav, surprise: boom.wav, cute: sparkle.wav, default: ding.wav}
    anchor: onset
    gain_db: -6
    max_per_clip: 1
```

**Consolidated rule set stream2clip could adopt (Proposal, derived from the findings above)**
1. **Budget**: ≤3 SFX per clip (hotclip), ≤1 "hero" visual effect at the peak plus ≤2 secondary ones, and a minimum gap of about 2 s between visual effects. Zero effects is allowed when signals are weak (OpusClip's "No sound effects needed").
2. **Anchor priority**: VTS expression hotkey near the peak, then sound onset nearest the corrected peak (existing logic), then the prominent word nearest the peak, then the raw peak. If no anchor exists within ±500 ms, skip the visual effect (hotclip skip-on-failure).
3. **Category → effect family**: laugh → small bounce or ease punch-in, 😂/草 emoji, pop SFX, and never cut inside laughter (SharkyClips). Surprise → instant punch-in, "!?" caption supersize, boom, no shake by default. Cute → slow push-in, sparkle overlay, 💕. Hype/superchat → CAPS caption (Expressive-Captions style), ding.
4. **Intensity** = discrete level (0/1/2, like Captions) from chat burst z-score × dominant-category share. Discrete levels avoid jittery per-clip scale values.
5. **Emphasis words**: at most 1 per caption line, chosen by prosodic prominence (loudness, F0 and duration z-scores) within the peak window. Keep reelsaw's readability floor (≥0.7 s + 0.3 s/word; ≤20 cps for Latin script).
6. **Placement guard**: emoji and stickers must not overlap the caption safe zone or the avatar face box. Zoom must keep the avatar face box fully in frame.
7. **No double-up with live effects**: if the session recorder logged a VTS item drop or VFX preset in that window, do not add an overlay effect.
8. **Flash/shake defaults off** (see §6). A "peak flash" or flash-forward opener (SharkyClips, hotclip) should be a **content flash-forward (cut)**, not a white luminance flash.
9. **Learning loop**: log which auto effects users delete or keep per preset, using the same local record stream2clip already keeps for highlights, and use it to tune defaults. reelsaw and hotclip do this for clip selection (P).

### Gaps
- I could not find a Korean product called "Captus/캡터스" with templates. The search returned only CapCut, Canva and Filmora caption templates. The name may be misspelled or the product too niche to be indexed.
- The OpusClip Brand Template API schema page did not render, so its field list is unknown.
- The detailed CapCut draft-schema files (01–05) and how CapCut "templates" (as opposed to drafts) bind replaceable slots were not read.
- I could not confirm whether YMM4 has a built-in item/effect template feature (only a third-party text template plugin was found). The official YMM4 manual was not reached.
- Submagic caption-template structure was not documented in pages reached.

## 6. Guardrails: frequency caps, gaps, avoiding faces/captions, photosensitivity, motion sickness

### Takeaway
The hard numeric limits come from accessibility standards. WCAG 2.3.1 sets **no more than 3 flashes in any 1 s** unless below the general and red flash thresholds. ITU-R BT.1702-3 (2023) adds: a **20 cd/m² luminance step** (darker image < 160 cd/m²), **25% of screen area**, any transition to or from **saturated red**, flashes ≥ **334 ms apart (60 Hz)** always acceptable, **rapid cuts count as flashes** if they make areas flash, and a **>5 s flashing sequence** may be risky even if compliant. Motion sickness has no numeric video standard. Guidance is to avoid or offer an off switch for camera shake and rapid zoom (Xbox XAG 117, WCAG 2.3.3 intent). Effect frequency caps in tools are qualitative or small fixed caps (hotclip ≤3 SFX).

### Cited Findings
**Photosensitive epilepsy**
- WCAG 2.3.1: content must not contain "anything that flashes more than three times in any one second period" unless below thresholds. A general flash is "a pair of opposing changes in relative luminance of 10% or more of the maximum relative luminance", with the darker image below 0.80. A red flash is any opposing pair involving saturated red: R/(R+G+B) ≥ 0.8 and a CIE 1976 UCS chromaticity difference > 0.2. Area threshold is 0.006 sr, or 25% of a 10° field, given as **341 × 256 px at 1024 × 768**. Analyse video **at full screen** and loops while looping. Harding FPA and Trace Center PEAT are listed as tools (V) — [W3C Understanding SC 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)
- ITU-R BT.1702-3 (11/2023, in force), Guideline 1: a harmful flash is an opposing pair of luminance changes. When the darker image is **below 160 cd/m²**, a difference of **20 cd/m² or more** counts, for both SDR and HDR. When the darker image is ≥160 cd/m² (HDR only), a Michelson contrast above **1/17** counts. A transition to or from saturated red is harmful regardless of luminance. "Isolated single, double, or triple flashes are acceptable", but a sequence is not permitted when the concurrent flashing area exceeds **25%** of the screen **and** there are **more than three flashes (six luminance changes) in any one second**. Flashes whose leading edges are ≥360 ms apart (50 Hz) or ≥334 ms apart (60 Hz) are acceptable regardless of brightness or area. "Rapidly changing image sequences (for example, fast cuts) are provocative if they result in areas of the screen that flash". A sequence over **five seconds** "might constitute a risk even when it complies". Guideline 2 covers regular patterns (stripes, polka dots), which are worse when they oscillate, flash or reverse. Note 3: SDR peak white is assumed to be 200 cd/m² and HLG 1000 cd/m². Note 5: automatic analysers are beneficial (V) — [ITU-R BT.1702-3 PDF](https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1702-3-202311-I!!PDF-E.pdf)
- Ofcom's legacy ITC "Guidance Note for Licensees on Flashing Images and Regular Patterns in Television" (revised July 2001) uses the same 20 cd/m² rule. The UK ASA references its Annex 1 (S; PDF returned 403) — [Ofcom gn_flash.pdf](https://www.ofcom.org.uk/__data/assets/pdf_file/0021/16248/gn_flash.pdf), [ASA: flashing images in advertising](https://www.asa.org.uk/news/flashing-images-in-advertising.html)

**Motion sickness / vestibular**
- WCAG 2.3.3 Animation from Interactions (AAA) aims to prevent harm or distraction from motion. Its sufficient technique is honouring `prefers-reduced-motion` (S) — [W3C Understanding SC 2.3.3](https://w3.org/WAI/WCAG21/Understanding/animation-from-interactions)
- Rapid zoom transitions from video editing software and "shaky cam" can cause dizziness, nausea and vertigo in people with vestibular disorders (S) — [U. Michigan: Accommodating Vertigo and Vestibular Disorders](https://teamdynamix.umich.edu/TDClient/30/Portal/KB/Article/14019/Accommodating-Vertigo-and-Vestibular-Disorders)
- Xbox Accessibility Guideline 117 says to avoid camera shake, camera bobbing and motion blur, or provide an option to turn them off (S; games guidance applied to video by analogy) — [XAG 117](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/117)

**Placement, overlap and frequency in tools**
- Caption safe-zone handling: reelsaw has a platform safe-zone overlay and moves captions to the split seam (V) — [reelsaw](https://github.com/osbytes/reelsaw). SharkyClips keeps subtitles out of each app's UI buttons (V) — [sharkyclips](https://github.com/utkualsir/sharkyclips). hotclip offers a caption safe-zone preview with platform UI masks (V) — [hotclip](https://github.com/xixihhhh/hotclip)
- OpenShorts places captions "on the seam where they cover nobody" when two speakers are stacked (S) — [OpenShorts](https://github.com/mutonby/openshorts)
- Frequency caps found: hotclip ≤3 SFX per clip (V) — [hotclip](https://github.com/xixihhhh/hotclip). OpusClip Auto SFX skips some moments to avoid clutter (V) — [OpusClip Auto SFX](https://help.opus.pro/docs/article/auto-sfx.md). VTS cooldowns (V) — [VTS wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Twitch-Hotkey-Triggers). Vendor advice: one primary motion effect plus one or two complementary ones (S) — [OpusClip blog](https://www.opus.pro/blog/best-auto-zoom-in-tools)

### Inferences
- **Render-time flash guard (Proposal)**: compute per-frame mean luminance, converting 8-bit Rec.709 to approximate cd/m² with ITU's assumption of a 200 cd/m² SDR peak. Track opposing transitions ≥20 cd/m² over >25% of the frame, plus saturated-red transitions (R/(R+G+B) ≥ 0.8). Fail the render, or drop the offending effect, if more than 3 flashes occur in any 1 s window or the leading edges of flashes are closer than 334 ms. A 20 cd/m² step at a 200 cd/m² peak is only about 10% of peak white, consistent with WCAG's 10% rule. So a full-screen white "impact flash" will almost always count as a flash, and stacking more than three in a second (e.g. a beat-synced strobe) is non-compliant. This also covers **fast cut montages** (ITU: fast cuts count).
- **Isolated flashes are allowed** (ITU: single, double or triple), so a single peak flash is permissible. The default should still be a cut-based flash-forward rather than a white frame, and flashes should never repeat within 334 ms.
- **Shake off by default.** Provide a "reduced motion" preset that replaces zoom and shake with static caption supersize or emphasis colour. This mirrors `prefers-reduced-motion` and XAG 117's "option to turn off".
- **Zoom comfort (Proposal, unsourced numbers)**: cap scale at about 1.3×, avoid more than one zoom change per 3–4 s, and avoid zoom oscillation (in-out-in within 1 s). Rapid zoom is named as a vestibular trigger, but no numeric threshold was found.
- The cumulative rule (ITU: >5 s of flashing may be risky) argues against long "hype" strobe sequences on superchat bursts.

### Gaps
- No numeric standard for zoom speed, shake amplitude or frequency for pre-recorded video was found. The proposed numbers are heuristics.
- Ofcom's current guidance text could not be fetched (HTTP 403). The Harding FPA and PEAT thresholds were not separately verified beyond the WCAG listing.
- Whether short-form platforms (YouTube Shorts, TikTok) apply their own photosensitivity checks to uploads was not researched.
