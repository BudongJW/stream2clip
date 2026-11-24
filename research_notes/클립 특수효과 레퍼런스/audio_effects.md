# Audio effects for VTuber clips beyond BGM and one-shot SFX: catalogue, local implementation, licences, automatic timing (as of 2026-11-22)

Scope: voice and clip-audio treatments (echo, pitch, replay, filters, stutter, bleep and more), more synthesized one-shots, beat sync, and loudness and Content ID safety for stream2clip (MIT, Python + numpy + ffmpeg, Windows installer). The site-licence survey in `reports/무료 BGM 효과음 레퍼런스.md` is not repeated.

Local measurements in this note ("local test") were run on 2026-11-22 with ffmpeg 8.1 full_build (gyan.dev, `--enable-gpl --enable-librubberband ...`) on Windows 11 using synthetic pink-noise signals, not real stream audio. They show that the commands run and how long they take. They do not show how the effects sound.

## 1. Which voice and clip effects do editors use, and which are standard or rare?

### Takeaway
The best-documented treatments are the censor bleep (ピー音/삐 처리, a 1 kHz sine), comedic sound replacements for hidden words, the Korean "repeat the line three times" replay, canned laughter and reaction tracks (especially in Korean variety), crickets for awkward silence, and short SFX timed to telops and tsukkomi. Echo on a punchline, pitch-up or slow-down, rewind, record scratch, telephone or muffle filters and 鬼畜-style stutter are common in practice, but none of the editing guides I found names them as standard for kirinuki. Stutter editing belongs to the 音MAD genre, not to ordinary kirinuki.

### Cited Findings
- **Bleep basics (Japan).** The most-used 自主規制音 is a 1 kHz sine. It probably comes from the broadcast mixer test tone, and it is sometimes pitch-shifted slightly so it sounds less harsh. Variety shows use it mainly for taboo words and celebrity names. Words that truly cannot be aired are almost always cut rather than beeped. — [ja.wikipedia 自主規制音](https://ja.wikipedia.org/wiki/自主規制音)
- **Bleep alternatives (Japan).** Other sounds replace hidden words: gunshots (ズキューン), explosions (ドカーン), bells or gongs (チン, カーン), destruction sounds for sexual slang, and electronic chirps (ピヨピヨ, ぼよよよよ) to hide quiz answers. Muting is used when less disruption is wanted. With multitrack audio, only the dialogue is muted and the BGM stays. Recent productions also cover the speaker's mouth with a graphic so the word can't be lip-read. — [ja.wikipedia 自主規制音](https://ja.wikipedia.org/wiki/自主規制音)
- **Bleeps as a gag.** Shows beep innocent words, cover only part of a word, or give a hint after a commercial break to build curiosity. — [ja.wikipedia 自主規制音](https://ja.wikipedia.org/wiki/自主規制音)
- **Synth phrases for hiding words.** Sound-effect sites distribute ピコピコ synth phrases and finely vibrato'd synth tones made for 伏せる演出 in Japanese variety. (Search-result summary of OtoLogic's 規制音 page; page not opened.) — [OtoLogic 規制音](https://otologic.jp/free/se/censor-bleep01.html)
- **Streamer clip guide.** A 2026 Japanese guide says SE are short sounds matched to telop display, scene changes and tsukkomi. It recommends L/J cuts, starting a cut 1–2 s before the line, not over-trimming pauses, and keeping reaction shots. It notes that over 50% of viewers watch muted. It does not mention echo, pitch, speed effects or ピー音. — [We Streamer 編集部, 2026-03-26, updated 2026-05-18](https://bloomeria.jp/blog/video-editing-complete-guide-streamers)
- **Common YouTube SFX (US list).** Uppbeat (Jamie Chambers, 2026-10-03) lists 14: whoosh, meme "fail" alert, cha-ching, bell ding, bubble pop, censor beep (to censor or to exaggerate a joke), playful detective sting, audience cheering and clapping, typing, quick swoosh, awkward-silence crickets, camera shutter, ocean waves, and heartbeat tension before reveals. Vine boom, record scratch, airhorn, laugh track, rewind, boing, drum roll, rimshot and riser are not on it. — [Uppbeat blog](https://uppbeat.io/blog/sound-effects/sound-effects-youtubers-use)
- **Korean variety audio.** Korean variety uses varied canned laughs, including high-pitched female "우~~" tracks, and a long "Ooooooo" after a goofy or scandalous line. Its "Say Whaaat?" repeat effect replays a shocking line three times from different camera angles. — [KoreanClass101 blog, 2009-07-07](https://www.koreanclass101.com/blog/?p=412) (old, informal source)
- **Korean editing posts (search-result summaries only; pages not opened).** Korean posts say editors add 방청객 웃음소리 at the right moments, insert SFX as the last editing step, and use crickets to stress an embarrassed silence. Korean variety captions were first borrowed from Japanese variety. — [Artlist KO blog](https://artlist.io/blog/ko/free-youtube-sfx/), [Korea Herald](https://www.koreaherald.com/article/10410946)
- **Reverse echo.** Reverse the sound, add reverb or delay, then reverse again so the tail swells in before the sound. It is described as a flashy treatment for SFX. (Search-result summary of a DTM blog.) — [yuuki-dimension.com](https://yuuki-dimension.com/arrange-se-revers/)
- **音MAD and 鬼畜.** 人力VOCALOID retunes character voices with pitch and formant correction. Bilibili calls the genre 鬼畜. Works built from existing media are described as "basically illegal", and Niconico has removed works when rights holders asked. The article does not explain how stutter or loop edits are made. — [ja.wikipedia 音MAD](https://ja.wikipedia.org/wiki/音MAD)
- **Agency rule.** にじさんじ guidelines forbid adding audio that intentionally misleads (Article 5, paragraph 2). — `reports/무료 BGM 효과음 레퍼런스.md` §2, citing [anycolor.co.jp/guidelines](https://www.anycolor.co.jp/guidelines) (2025-05-23 revision)

### Inferences
- **Proposed tiers for a default palette:**
  - Tier 1, low risk and well documented: bleep or mute over specified words; "repeat ×2–3" replay of the punchline; crickets or silence-drop before a reaction; laugh or cheer bed under the chat peak; punchline echo.
  - Tier 2: pitch-up or slow-down replay, rewind (reverse plus pitch sweep) before a replay, record-scratch stop, telephone or muffle filter for quoted or "inner voice" lines.
  - Tier 3, opt-in only: 鬼畜 stutter.
- **Tier 3 risk.** Stutter edits recombine the talent's words. That can collide with the にじさんじ misleading-audio clause and similar agency rules. Limit it to repeating whole words, never re-ordering them.
- **Replay vs echo.** The Korean triple replay and the Japanese "もう一回" replay are the same pattern. stream2clip already has the peak time, so a replay effect needs nothing new: cut [peak − d, peak], append it 1–2 times, optionally pitched or slowed, with a rewind SFX between copies.

### Gaps
- I found no editor survey or guide that measures how often kirinuki or 예능 editors use echo, pitch, telephone EQ, rimshot, drum roll, boing or risers. Standard vs rare above is judgment backed by the sources, not a measurement.
- The Korean sources are thin: one old blog plus search snippets. No Korean broadcast post-production manual was found.

## 2. ffmpeg implementations: filters, quality, speed, and LGPL vs GPL builds

### Takeaway
Every treatment except formant-preserving pitch can be built from native ffmpeg filters, and none of the native audio filters needs a GPL build. Echo is `aecho`. Reverb is `afir` with an IR you generate yourself. Chipmunk or slow-mo is `asetrate`+`aresample`(+`atempo`). Telephone or muffle is `highpass`/`lowpass`/`bandpass`. The other treatments use `acrusher`, `vibrato`/`tremolo`, `afreqshift`, `areverse`, `aloop`, and `volume` with `enable`/`eval=frame`. Only the `rubberband` filter needs a GPL build (librubberband is on ffmpeg's GPL list), and the gyan.dev essentials build that stream2clip already downloads includes it.

### Cited Findings
- **aecho.** Options: `in_gain` 0.6, `out_gain` 0.3, `delays` in ms separated by `|` (default 1000, max 90000), `decays` (default 0.5).
  - Doc examples: `aecho=0.8:0.88:60:0.4` doubles the instruments, `aecho=0.8:0.88:6:0.4` sounds metallic or robotic, `aecho=0.8:0.9:1000|1800:0.3|0.25` gives a mountain echo.
  - No timeline (`enable`) support.
  - [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html); local `ffmpeg -h filter=aecho`
- **No native reverb.** ffmpeg 8.1 full has no reverb filter. `ffmpeg -filters` matches only `aecho` and `ladspa` for "reverb|verb|echo". — local test
- **afir (convolution reverb).** Convolves with an IR of up to 60 s (`maxir` default 30 s).
  - Options: `dry`/`wet`, `irnorm`, `irgain`, `minp`/`maxp` (default 8192; trade latency against CPU), and up to 32 IRs switchable at runtime with `ir`.
  - Doc example: `ffmpeg -i input.wav -i middle_tunnel_1way_mono.wav -lavfi afir output.wav`.
  - [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **afir local test.**
  - A 2 s exponentially decaying noise IR made by ffmpeg itself (`anoisesrc=...,volume='exp(-4*t)':eval=frame`) processed 60 s of 48 kHz mono in 0.17 s.
  - With a delta IR, a click at sample 48000 came out at sample 48000, so afir adds no offset when rendering offline.
  - `afir=dry=8:wet=3:irnorm=1` dropped the peak from about −12 to −27 dBFS, so it needs makeup gain.
  - — local test
- **asetrate.** Changes the sample rate without touching the data, so speed and pitch change together. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **atempo.** Range 0.5–100. Above 2 it skips samples, so chain instances (e.g. `atempo=sqrt(3),atempo=sqrt(3)`). Runtime command `tempo`. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **Pitch and speed local tests** (4 s source):
  - `asetrate=48000*1.5,aresample=48000,atempo=1/1.5` (chipmunk, duration kept) gave 3.98 s.
  - `asetrate=48000*1.5,aresample=48000` (chipmunk plus speed-up) gave 2.67 s.
  - `asetrate=48000*0.7,aresample=48000` (slow, deep "slow-mo" voice) gave 5.71 s.
  - On 60 s of audio: asetrate chain 0.25 s, `rubberband=pitch=1.5` 1.65 s, `rubberband=pitch=1.5:formant=preserved:pitchq=quality` 2.97 s.
  - — local test
- **rubberband options.**
  - `tempo` and `pitch` (0.01–100, runtime-changeable).
  - `transients` crisp/mixed/smooth, `detector` compound/percussive/soft, `phase` laminar/independent, `window` standard/short/long.
  - `formant` shifted (default) or preserved, `pitchq` quality/speed/consistency, `channels` apart/together.
  - — local `ffmpeg -h filter=rubberband` (8.1)
- **rubberband licensing.**
  - ffmpeg `configure` lists `librubberband` in `EXTERNAL_LIBRARY_GPL_LIST` (with avisynth, frei0r, libx264, libx265, libxvid and others), and `rubberband_filter_deps="librubberband"`. — [FFmpeg configure (master)](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/configure)
  - The Rubber Band library repo reports GPL-2.0 (816★, last push 2025-03-03). — [breakfastquay/rubberband](https://github.com/breakfastquay/rubberband)
- **GPL-only filters are all video.** Every filter with `_filter_deps` containing `gpl` is a video filter (blackframe, boxblur, delogo, eq, hqdn3d, mpdecimate, stereo3d, pp7 and others). No native audio filter is GPL-gated. ladspa, lv2, bs2b, sofalizer and flite depend on external libraries. — [FFmpeg configure (master)](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/configure)
- **gyan.dev builds.**
  - "All builds are 64-bit, static and licensed as GPLv3."
  - Essentials includes librubberband. The full build adds libsoxr and ladspa.
  - Current release is 9.1 (2026-11-20). The previous release is 9.0.2.
  - — [gyan.dev FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/)
- **stream2clip's ffmpeg.** It downloads ffmpeg 9.0.2 essentials from gyan.dev with a pinned SHA-256, and calls ffmpeg only as an external process. — `README.md` line 978, `CHANGELOG.md` line 249, `docs/PORTING.md` line 285 (local repo)
- **acrusher.** `bits` default 8, `mix` 0.5, `mode` lin/log (log sounds more natural and does not gate low signals), `aa`, `samples` 1–250 (sample-rate reduction), optional LFO. Timeline and runtime commands supported. — local `ffmpeg -h filter=acrusher`; [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **vibrato / tremolo.** `f` 0.1–20000 Hz (default 5) and `d` 0–1 (default 0.5). Both support timeline `enable`. — local `ffmpeg -h filter=vibrato` / `tremolo`
- **afreqshift / aphaseshift.** `afreqshift` has `shift` (Hz), `level` and `order` 1–16. It is a non-harmonic frequency shift for "robot" or "alien" voices. Both support timeline and commands. — local `ffmpeg -h`; [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **areverse.** Buffers the whole clip in memory, so trim first: `atrim=end=5,areverse`. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **aloop.** `loop` (−1 = infinite), `size` (samples), `start`, `time`. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **Stutter local test.** `atrim=start=1:end=1.15,asetpts=PTS-STARTPTS,aloop=loop=5:size=7200,afade=t=out:st=0.8:d=0.1` gave 6 × 150 ms repeats (0.90 s). — local test
- **Filters (bandpass, highpass, lowpass).**
  - `highpass` and `lowpass` are 2-pole Butterworth (default width 0.707q).
  - `bandpass` defaults to 3000 Hz with an optional `csg` (constant skirt gain).
  - All three support runtime commands.
  - — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **Telephone chain (local test).** `highpass=f=300,lowpass=f=3400` (twice), then `acompressor=threshold=0.1:ratio=4`, then `acrusher=bits=8:mix=0.3:mode=log` ran without errors. — local test
- **Other built-in colour.** `chorus` (doc example `chorus=0.7:0.9:55:0.4:0.25:2`), `flanger`, `apulsator` (LFO autopan, bpm sync), `asoftclip` (tanh/atan/... with oversampling), `compand` (doc 2:1 and hard-limiter point examples), `crystalizer`, `aexciter`. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **volume.** `eval` once (default) or frame, so an expression like `volume='...t...'` is re-evaluated per frame. Timeline via `enable`. Local test: `volume=0:enable='between(t,1.2,1.8)'` mutes a span. — local `ffmpeg -h filter=volume`; local test
- **asendcmd.** Changes filter options at set times. Doc example: `asendcmd=0.0 afftdn sn start,asendcmd=0.4 afftdn sn stop,afftdn=...`. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **alimiter.** `level` (auto-normalize) is on by default. The doc recommends upsampling 2× or 4× with aresample first. There is a `latency` option. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)

### Inferences
- **No new licence obligation.** stream2clip already ships a GPLv3 ffmpeg as an external process, so the `rubberband` filter adds no obligation. If the project ever moves to an LGPL ffmpeg build, every effect here except `rubberband` still works. Add a capability check (`ffmpeg -filters | rubberband`) and fall back to `asetrate`+`atempo`.
- **Comedy pitch doesn't need rubberband.** Chipmunk is the comedic sound, and `asetrate` deliberately shifts the formants. Rubberband with `formant=preserved` only matters for "same voice, higher note" effects, and it is 7–12× slower (still about 20–35× faster than real time).
- **Reverb without IR licences.** Generate the IR procedurally: exponentially decaying filtered noise made with ffmpeg or numpy, or a room IR from pyroomacoustics (MIT). Store a few presets (small room 0.4 s, hall 1.5 s, cave 3 s) as code, not files.
- **Punchline echo chain.** `asplit` → `[wet] atrim=last ~0.6 s of punchline, aecho=0.8:0.6:220|440|660:0.5|0.35|0.2` (or `afir`) → `adelay=<punchline end>` → `amix normalize=0` over the original. The tail rings into the reaction instead of overlapping the next line.
- **Rewind.** Reverse the 1–2 s before the replay start (`areverse`) and run it through an `asetrate` speed-up (×2–3) and `atempo` so the sweep is short. Optionally add a numpy-synthesized "tape" noise burst.
- **Record-scratch stop.** Use `asetrate` with a falling rate, approximated by 2–3 concatenated segments at decreasing rates, then a short `afade=out`. Alternatively, `aeval` or numpy resampling of the last 300 ms along a curve gives a smooth "power-down" (tape stop).
- **Telephone or radio voice.**
  - Band-limit to roughly 300–3400 Hz (doubling the 2-pole stages makes a steeper skirt) and add light `acompressor` and `acrusher` grit.
  - Radio voice: add `bandpass` around 1.5–2 kHz plus a little noise.
  - Muffle ("next room", "underwater"): `lowpass=f=400–800` twice, with optional `aecho` for a room feel.
  - The 300–3400 Hz figure is the conventional telephone voice band; it was not verified against a primary ITU source in this session.

### Gaps
- I did not verify which Windows LGPL builds (e.g., BtbN `lgpl` variants) exist or what they include.
- No listening test was done. Quality judgments of atempo vs rubberband come from the docs and timing only.
- No licence check of public IR libraries (e.g., OpenAIR) was done. The procedural approach avoids the question.

## 3. Python libraries and licences usable in an MIT project shipped as a Windows installer

### Takeaway
librosa, audiomentations, pydub, python-soundfile, pyroomacoustics, pyloudnorm, faster-whisper, WhisperX, stable-ts, silero-vad, demucs, beat_this (code and weights) and the TD-PSOLA script are all permissive and safe to bundle. Pedalboard, Rubber Band, aubio, Parselmouth, psola (maxrmorrison) and matchering are GPL. Essentia, gpuRIR and whisper-timestamped are AGPL. madmom's code is BSD, but its models are CC BY-NC-SA 4.0. BeatNet and the LDNOOBW word list are CC BY 4.0 and need attribution.

### Cited Findings
GitHub repository licence (SPDX), stars and last push, queried with `gh api repos/...` on 2026-11-22:

| Package | Licence | Notes | Source |
|---|---|---|---|
| spotify/pedalboard | **GPL-3.0** | 6.5k★, pushed 2026-11-09 | [repo](https://github.com/spotify/pedalboard) |
| bmcfee/pyrubberband | ISC (wrapper) | needs the Rubber Band tool, **GPL-2.0** ([repo](https://github.com/breakfastquay/rubberband)) | [repo](https://github.com/bmcfee/pyrubberband) |
| librosa | ISC | 9.1k★, pushed 2026-11-21 | [repo](https://github.com/librosa/librosa) |
| audiomentations | MIT | | [repo](https://github.com/iver56/audiomentations) |
| pydub | MIT | needs ffmpeg | [repo](https://github.com/jiaaro/pydub) |
| aubio | **GPL-3.0** | | [repo](https://github.com/aubio/aubio) |
| madmom | code BSD-2-style; **data and model files CC BY-NC-SA 4.0**; commercial use of pickled processors requires contacting Gerhard Widmer | | [LICENSE](https://raw.githubusercontent.com/CPJKU/madmom/main/LICENSE) |
| essentia | **AGPL-3.0** | | [repo](https://github.com/MTG/essentia) |
| BeatNet | **CC-BY-4.0** (attribution) | | [repo](https://github.com/mjhydri/BeatNet) |
| beat_this | MIT, code and released weights | | [repo](https://github.com/CPJKU/beat_this) |
| all-in-one (allin1) | MIT code; weights licence not stated | | [repo](https://github.com/mir-aidj/all-in-one) |
| python-soundfile | BSD-3-Clause | | [repo](https://github.com/bastibe/python-soundfile) |
| libsndfile | LGPL-2.1 | | [repo](https://github.com/libsndfile/libsndfile) |
| faster-whisper | MIT | | [repo](https://github.com/SYSTRAN/faster-whisper) |
| whisperX | BSD-2-Clause | | [repo](https://github.com/m-bain/whisperX) |
| whisper-timestamped | **AGPL-3.0** | | [repo](https://github.com/linto-ai/whisper-timestamped) |
| stable-ts | MIT | | [repo](https://github.com/jianfch/stable-ts) |
| silero-vad | MIT | | [repo](https://github.com/snakers4/silero-vad) |
| pyroomacoustics | MIT | room impulse response simulation | [repo](https://github.com/LCAV/pyroomacoustics) |
| gpuRIR | **AGPL-3.0** | | [repo](https://github.com/DavidDiazGuerra/gpuRIR) |
| pyworld (WORLD wrapper) | MIT | WORLD C++ repo shows NOASSERTION | [wrapper](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder), [WORLD](https://github.com/mmorise/World) |
| Parselmouth (Praat) | **GPL-3.0** | | [repo](https://github.com/YannickJadoul/Parselmouth) |
| maxrmorrison/psola | **GPL-3.0** | | [repo](https://github.com/maxrmorrison/psola) |
| sannawag/TD-PSOLA | MIT | 2019 script | [repo](https://github.com/sannawag/TD-PSOLA) |
| matchering | **GPL-3.0** | | [repo](https://github.com/sergree/matchering) |
| pyloudnorm | MIT | | [repo](https://github.com/csteinmetz1/pyloudnorm) |
| demucs (adefossez fork, active) | MIT | facebookresearch original archived | [repo](https://github.com/adefossez/demucs) |
| pyfluidsynth | LGPL-2.1 | | [repo](https://github.com/nwhitehead/pyfluidsynth) |
| rnnoise | BSD-3-Clause | | [repo](https://github.com/xiph/rnnoise) |

- **beat_this details.** Dependencies: PyTorch ≥2.0, tqdm, einops, soxr, rotary-embedding-torch. madmom is needed only for optional DBN postprocessing. Models are about 78 MB (final) or 8.1 MB (small). The CLI falls back to CPU (`--gpu=-1` forces it). — [beat_this README](https://github.com/CPJKU/beat_this)
- **allin1 details.** Requires madmom from GitHub and NATTEN; on Windows, NATTEN must be built from source. It uses demucs and was trained on the Harmonix Set. — [all-in-one README](https://github.com/mir-aidj/all-in-one)
- **BeatNet details.** Offline mode uses madmom's DBN; online and realtime modes use BeatNet's own particle filtering. — [BeatNet README](https://github.com/mjhydri/BeatNet)

### Inferences
- **Safe set for the installer:** numpy plus scipy.signal (filters, `resample_poly`, `fftconvolve`) for synthesis and offline DSP; librosa for onset or beat analysis and `effects.time_stretch`/`pitch_shift`; pyroomacoustics or procedural numpy for IRs; pyloudnorm for checks. Everything else goes through ffmpeg. That covers every effect in this note without any GPL Python dependency.
- **Avoid in-process:** Pedalboard (GPL-3.0) would put an MIT-distributed installer under GPL-3.0 terms if bundled. Parselmouth and the maxrmorrison psola package are in the same position. Any Rubber Band use should stay inside the external ffmpeg process.
- **madmom.** Bundling its NC models in a freely distributed installer breaks the "non-commercial" condition as soon as a user monetizes clips. It would also pull in an unmaintained PyPI release that requires Python <3.10 and numpy <1.20 (per the beat_this README). So beat_this without `--dbn` is the clean deep-learning option, and allin1 inherits the madmom problem.

### Gaps
- I did not verify the SoX licence (libsox vs the sox binary) or the scipy licence this session. scipy is widely known as BSD-3.
- The WORLD vocoder licence text shows NOASSERTION on GitHub and was not read.
- The licence of the allin1 pretrained weights is not stated, and the Harmonix Set licence was not checked.
- I did not check the licences of the WhisperX alignment models for ja and ko (wav2vec2 checkpoints on Hugging Face).

## 4. Automating the censor bleep: word timestamps, word lists, boundaries, mute or duck

### Takeaway
Whisper-family word timestamps can place a bleep, but they are approximate. WhisperX-style forced alignment is measurably tighter. Pad each span, then snap it to energy minima, and offer three styles: the classic 1 kHz sine, mute, and duck (plus comedic replacement SFX). Permissive word lists exist for ja (LDNOOBW CC BY 4.0, MosasoM MIT) and ko (LDNOOBW, doublems MIT), but a streamer-specified list (names, spoilers, NG words) is the main use case.

### Cited Findings
- **Word-segmentation accuracy (200 ms collar).**

  | Method | AMI precision / recall | Switchboard precision / recall |
  |---|---|---|
  | Whisper (timestamps from attention DTW) | 78.9 / 52.1 | 85.4 / 62.8 |
  | WhisperX (wav2vec2 forced alignment) | 84.1 / 60.3 | 93.2 / 65.4 |

  The paper calls Whisper's timestamps "prone to inaccuracies". Multilingual use needs a VAD and a phoneme alignment model for each language, and no non-English segmentation was evaluated. — [WhisperX paper, arXiv 2303.00747](https://arxiv.org/html/2303.00747v2)
- **stable-ts.** Its README notes that Whisper sometimes predicts a word's start well before it is spoken, or its end long after, and stable-ts corrects this with silence suppression. (Search-result summary of the README.) stable-ts is MIT. — [stable-ts README](https://raw.githubusercontent.com/jianfch/stable-ts/main/README.md)
- **Word lists.**
  - LDNOOBW (CC-BY-4.0) has `ja` (180 lines) and `ko` (72 lines) files plus `en` and 25 other languages. — [LDNOOBW repo](https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words), counted via GitHub API
  - MosasoM/inappropriate-words-ja is MIT (215★, last push 2021). — [repo](https://github.com/MosasoM/inappropriate-words-ja)
  - doublems/korean-bad-words is MIT (62★, last push 2019). — [repo](https://github.com/doublems/korean-bad-words)
  - dsojevic/profanity-list is MIT. — [repo](https://github.com/dsojevic/profanity-list)
- **Styles from broadcast practice.** Beep with a 1 kHz sine, mute when less disruption is wanted, mute only the dialogue track with multitrack audio, cover the mouth to prevent lip-reading, or use comedic SFX in variety. — [ja.wikipedia 自主規制音](https://ja.wikipedia.org/wiki/自主規制音)
- **Bleep as a gag.** Censor beeps are also used to exaggerate a joke. — [Uppbeat blog](https://uppbeat.io/blog/sound-effects/sound-effects-youtubers-use)
- **ffmpeg bleep chain (local test).** `[0]volume=0:enable='between(t,1.2,1.8)'[v];[1:sine=f=1000]volume=0.3,volume=0:enable='not(between(t,1.2,1.8))'[b];[v][b]amix=inputs=2:normalize=0:duration=first` runs and keeps the duration. — local test

### Inferences
- **Pipeline.**
  1. faster-whisper `word_timestamps=True` (already in the stack).
  2. Normalize text: NFKC, kana or hiragana folding for ja, jamo-insensitive match for ko.
  3. Match against the streamer list, optionally plus the built-in list. Japanese Whisper "words" are often sub-word tokens, so match on the joined character stream and map back to the union of the token spans.
  4. Pad each span by about 60–120 ms. At a 200 ms collar, Whisper misses or misplaces a substantial share of boundaries.
  5. Snap each edge outward to the nearest 10 ms RMS minimum within ±150 ms, reusing the onset and silence detector stream2clip already has.
  6. Apply 5 ms gain ramps to avoid clicks.
- **Optional refinement.** Re-align only the flagged words with a WhisperX wav2vec2 model when one is available for the language, after checking the model licence.
- **Styles to offer:**
  - `beep`: 1 kHz sine, or a slightly detuned 950–1050 Hz variant per the "pitch slightly altered" practice, replacing the voice.
  - `mute`: voice to 0, BGM stays.
  - `duck`: voice −20 to −30 dB.
  - `sfx`: replace with a synthesized "pyoing" or "chin".
  - `reverse`: play the word backwards (my suggestion; I found no source for it).
- **Visual pair.** The mouth-cover practice translates to an optional subtitle mask (●●) or a sticker over the avatar mouth, coordinated with the video-effects work.
- **Defaults.** Bleep only words on the streamer's list by default. Built-in profanity lists produce false positives in ja and ko (short words embedded in longer words), and a missed bleep is less harmful to a kirinuki channel than a bleep over a talent's normal speech.

### Gaps
- I found no published accuracy figures for faster-whisper word timestamps in Japanese or Korean.
- I did not assess the quality or coverage of the ja and ko word lists, beyond line counts.
- LDNOOBW's CC BY 4.0 means bundling the list requires attribution in the app's licence notices.

## 5. Beat-synced editing: aligning cuts, effects and zooms to BGM beats, and the "drop at the peak"

### Takeaway
librosa's `beat_track` (ISC, dynamic programming per Ellis 2007) is enough for steady-tempo BGM and has no licence issues. beat_this (MIT code and weights) adds downbeats and much better robustness on CPU. allin1 (MIT code) also gives chorus and verse segments, but on Windows it needs NATTEN built from source plus madmom. madmom models are non-commercial, Essentia is AGPL, aubio is GPL, and BeatNet is CC BY with a madmom dependency. 音ハメ (syncing cuts and motion to beats) is an established Japanese editing term.

### Cited Findings
- **librosa.** `beat_track` runs in three stages: onset strength, tempo estimate from onset autocorrelation, and peak picking consistent with that tempo (Ellis 2007, "Beat tracking by dynamic programming", JNMR 36(1)). The PLP method may be preferred when tempo varies. — [librosa 0.11.0 docs](https://librosa.org/doc/0.11.0/generated/librosa.beat.beat_track.html), [Ellis 2007 PDF](https://hajim.rochester.edu/ece/sites/zduan/teaching/ece472/reading/Ellis_2007.pdf) (search-result summary of the docs; the docs page itself returned 404 for the `latest` and `main` paths)
- **beat_this.** Outputs `beats` and `downbeats` (and a `.beats` TSV). Paper: "Beat This! Accurate Beat Tracking Without DBN Postprocessing" (ISMIR 2024). No numeric scores appear in the README. — [beat_this README](https://github.com/CPJKU/beat_this)
- **allin1.** Outputs tempo, beats, downbeats and labelled segments (intro, outro, break, bridge, inst, solo, verse, chorus, start, end). It runs on CPU if no CUDA is present, but the only speed benchmark is on an RTX 4090. — [all-in-one README](https://github.com/mir-aidj/all-in-one)
- **BeatNet.** Outputs an array of beats with a downbeat flag. Offline mode uses the madmom DBN. — [BeatNet README](https://github.com/mjhydri/BeatNet)
- **音ハメ.** Syncs cuts and motion to BGM beats, close to the meaning of MAD. Rhythmic songs with clear drums and bass are easiest, and short SFX or voice work as accents. (Vendor blog.) — [Filmora JP 音ハメ](https://filmora.wondershare.jp/get-creative/edit-video-to-beat.html)

### Inferences
- **What to snap to the beat.** stream2clip owns the BGM placement and the existing `--bgm-start` option, so beat sync can be one-directional: choose the BGM start offset so a strong beat (or downbeat) lands on the highlight peak. Snap zoom punches, sticker pops and SFX within ±80 ms of the nearest beat. Don't move content cuts, because speech timing wins.
- **"BGM drop at the peak".** Two cheap variants with no source separation:
  1. A silence-drop: duck the BGM to −∞ for 0.3–0.8 s before the punchline, then return it at full level on the downbeat at the peak.
  2. A swap from a calm loop to a high-energy loop at the peak, crossfaded on a downbeat with `acrossfade`.
  
  Where the drop or chorus sits in a user track can come from allin1 segments (if installed) or from a simple RMS or onset-energy jump detector in librosa.
- **Recommended stack.** Default to librosa `beat_track` plus `onset_strength` (no new dependency beyond librosa). Offer beat_this as an optional extra for downbeats, without `--dbn`, to avoid madmom.

### Gaps
- I found no kirinuki or 예능 source that documents the "BGM drop at the peak" pattern explicitly. It is a widely seen pattern, but it is not sourced here.
- I found no CPU benchmark for beat_this or allin1 on Windows.

## 6. Synthesizing more one-shot effects in numpy: DSP recipes and recipe-source licences

### Takeaway
The sfxr model is the most reusable recipe set: oscillator plus ADSR plus frequency slide, vibrato, arpeggio, duty sweep, repeat, phaser and filters. The original sfxr is MIT, jsfxr is Unlicense, and ZzFX is MIT, so porting the algorithm into numpy is clean. Farnell's Designing Sound provides physically motivated recipes, including a boing built from bar mode ratios. Its companion patches carry no licence notice, so reimplement the concepts rather than copying the patches. Synth Secrets gives the snare model (≈180/330 Hz shell modes plus filtered noise), which extends to rimshot and drum roll.

### Cited Findings
- **sfxr.** DrPetter: "I've put it under the MIT free software license" and "free to use it for anything you please". — [drpetter.se sfxr](https://www.drpetter.se/project_sfxr.html)
- **jsfxr (Unlicense).**
  - Parameters: `wave_type`; envelope `p_env_attack`/`sustain`/`punch`/`decay`; `p_base_freq`, `p_freq_limit`, `p_freq_ramp` (slide), `p_freq_dramp` (delta slide); `p_vib_strength`/`speed`; `p_arp_mod`/`speed`; `p_duty`/`p_duty_ramp`; `p_repeat_speed`; `p_pha_offset`/`ramp`; `p_lpf_freq`/`ramp`/`resonance`; `p_hpf_freq`/`ramp`.
  - Preset generators: pickupCoin, laserShoot, explosion, powerUp, hitHurt, jump, blipSelect, synth, tone, click, random.
  - — [chr15m/jsfxr](https://github.com/chr15m/jsfxr) (also [grumdrig/jsfxr](https://github.com/grumdrig/jsfxr), Unlicense)
- **Other generators.** ZzFX and ZzFXM are MIT. — [ZzFX](https://github.com/KilledByAPixel/ZzFX)
- **bfxr.** GitHub detects no licence and the repo root has no LICENSE file, so treat it as all rights reserved. — [increpare/bfxr](https://github.com/increpare/bfxr)
- **ChipTone.** I found no source or licence; it appears to be a closed web tool. (Not verified.)
- **Farnell "Boing" (Practical 10).**
  - Noise excitation through `lop~ 4000` and `hip~ 90`.
  - Clamped-bar mode ratios 1, 6.267, 17.55, 34.39 (cited to Olsen), weighted 0.5/0.25/0.125/0.0625.
  - Free-bar ratios 1, 2.7565, 5.40392, 8.93295, 13.3443, 18.6379 (Benson) via resonant `vcf~` filters.
  - Pitch control 20–800 Hz (default 426), vibrato `osc~ 5`, decays of 1500 ms and 7000 ms.
  - No licence or copyright notice appears on the page.
  - — [MIT Press companion, Practical 10](https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/8375/designing_sound.zip/practical10.html)
- **More Farnell practicals.** Practical 7 is "Bouncing Ball". The SuperCollider port groups Telephone bell, Bouncing ball, Rolling can, Creaking door and Boing under "Idiophonics". — [Practical 7](https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/8375/designing_sound.zip/practical07.html), [Wikibooks: Designing Sound in SuperCollider](https://en.wikibooks.org/wiki/Designing_Sound_in_SuperCollider/Print_version) (search-result summary)
- **Snare model (Synth Secrets).**
  - Shell modes at about 180 Hz and 330 Hz, each with its own VCA and decay (the TR-909 uses two oscillators plus waveshapers).
  - Noise goes through a low-pass filter, then splits into a high-pass branch with its own contour and an unfiltered branch.
  - No pitch envelope is needed; the author calls the 909's pitch contour unnecessary.
  - The article gives no rimshot recipe.
  - — [Gordon Reid, Sound On Sound, April 2002](https://www.soundonsound.com/techniques/practical-snare-drum-synthesis)
- **YouTube-common one-shots.** Camera shutter, heartbeat tension, crickets, cheering and clapping, and cha-ching. — [Uppbeat blog](https://uppbeat.io/blog/sound-effects/sound-effects-youtubers-use)

### Inferences
These are untested design starting points, not verified recipes:
- **Rimshot or "ba-dum-tss".** Two snare hits (Synth Secrets model, shell modes about 180/330 Hz, 80–120 ms decay, noise HP about 2 kHz), 150 ms apart, then a cymbal. For the cymbal: about 6 detuned square waves at non-harmonic ratios plus noise, high-pass about 7 kHz, 600–900 ms exponential decay. A rimshot "click" adds a 1–2 ms broadband impulse and a short modal ping around 400–800 Hz.
- **Drum roll.** Snare hits retriggered at 12–20 Hz with ±15% random amplitude and ±5 ms jitter, a 1.5–3 s crescendo, and a final accented hit plus cymbal. Place it so the final hit lands on the reveal or peak.
- **Boing.** Port Farnell's modal model: a sum of decaying sines at clamped-bar ratios on a base of about 200–430 Hz, with a slow 5 Hz vibrato whose depth decays, plus a downward pitch glide (sfxr `p_freq_ramp` < 0). Simpler: an FM tone with the modulation index decaying from about 5 to 0 over 400 ms.
- **Slide whistle.** A near-sine (sfxr wave 2) with an exponential pitch glide (e.g., 600 → 1800 Hz up or the reverse), vibrato about 5–6 Hz, and a little band-passed breath noise.
- **Riser.** White or pink noise through a band-pass whose centre sweeps from about 300 Hz to 8 kHz over 1–4 s, plus a rising sine or saw with an exponential glide, a crescendo, and a hard stop or reverse cymbal at the peak. A short reverse-reverb pre-swell (reverse, `afir` with a procedural IR, reverse) of the punchline is the voice-based riser.
- **Record scratch.** Resample a short noise-plus-harmonic grain, or the clip audio, along a velocity curve of ±(0–3)× over about 250 ms (two back-and-forth strokes), then band-pass about 300 Hz–4 kHz. The tape-stop or power-down variant uses a pitch ramp to 0 over 300–600 ms.
- **Camera shutter.** Two filtered noise bursts (5–15 ms, band-pass about 2–6 kHz) 40–80 ms apart, the second quieter, with an optional low "thunk" at about 120 Hz.
- **Heartbeat.** "Lub-dub" from two sine thumps (about 50–60 Hz, 80–120 ms, a quick pitch drop of about 20%) about 0.25–0.3 s apart, repeated at 60–90 bpm. Accelerate before the reveal.
- **Licence hygiene.** Reimplement the algorithms from the parameter descriptions; algorithms aren't copyrightable, though the code is. Credit sfxr (MIT) in NOTICE if the code structure follows it. Don't copy Farnell's Pd patches verbatim (no licence notice) or Wikibooks code verbatim (Wikibooks text is typically CC BY-SA; not verified).

### Gaps
- I found no authoritative public-domain recipe for a record scratch, riser or slide whistle.
- I did not verify ChipTone's licence or the licence of Farnell's companion patches.

## 7. Loudness and clipping safety when stacking effects, and Content ID risks of free effect packs

### Takeaway
YouTube's own Content ID rules make sound effects, soundbeds and production loops ineligible as reference files, and route royalty-free libraries to manual review. So effects synthesized in code carry essentially no matching risk. The residual risk comes from popular sampled SFX that also appear inside songs registered by third parties. For loudness, sum all layers with `amix normalize=0`, then apply one oversampled `alimiter`, then the existing two-pass `loudnorm`.

### Cited Findings
- **Content ID eligibility.**
  - Under "Distinct reference content", "Sound effects, soundbeds, or production loops" are ineligible.
  - "So-called 'royalty free' production music libraries" must be "routed to manual review before claiming".
  - "Content that is sold or licensed at scale for incorporation into other works must be routed for review."
  - Non-exclusive licences, Creative Commons and similar open licences, and public-domain recordings are ineligible.
  - — [YouTube Help: Content eligible for Content ID](https://support.google.com/youtube/answer/2605065?hl=en)
- **How false matches happen (search-result summaries).** A Freesound forum thread says matches occur when an artist uses a raw sample in a song registered in Content ID; modifying or stretching the sound makes a match less likely. A library blog lists sound effects among non-music sounds that commonly trigger false claims, and recommends disputing with the specific rule cited. A Content ID claim is not a copyright strike. — [Freesound forum](https://freesound.org/forum/legal-help-and-attribution-questions/41930), [TunePocket](https://www.tunepocket.com/false-copyright-claims-youtube/), [YouTube Help: copyright claims](https://support.google.com/youtube/answer/6013276)
- **alimiter.** The doc recommends 2× or 4× upsampling before the limiter, `level` auto-normalizes by default, and there is a `latency` option. — [FFmpeg filters doc](https://ffmpeg.org/ffmpeg-filters.html)
- **Limiter local test.** `volume=12dB,aresample=192000,alimiter=limit=0.89:level=0,aresample=48000` held the sample peak at −1.2 dBFS on a hot signal. Inter-sample (true) peak was not measured. — local test
- **Existing stream2clip practice.** `amix normalize=0`, `alimiter level=0` at −1 dBFS, and two-pass `loudnorm` at −14 LUFS with a −1.5 dBTP ceiling. — `reports/무료 BGM 효과음 레퍼런스.md` §4 and §6

### Inferences
- **Stacking order.**
  1. Voice effects (echo, reverb, pitch) are applied on the voice stem, with gain matched so the integrated loudness of the processed span is within about ±1 LU of the dry span. A short-term LUFS measurement of the span with pyloudnorm or ffmpeg `ebur128` is enough.
  2. SFX and BGM are mixed with `normalize=0`.
  3. A single limiter at the end (oversampled), then loudnorm.
  
  Never put a limiter per effect. Several limiters pump.
- **Gain budgets.** Reverb wet paths (−15 dB in the afir test) and stacked echoes (which add up to 1+Σdecays) need explicit budgets. Cap echo `out_gain` so that `in_gain·out_gain·(1+Σdecays) ≤ 1`, or follow with `volume` correction. Bleep tones should sit at about −6 to −10 dB relative to speech peaks; a full-scale 1 kHz sine sounds much louder than speech.
- **Overlap rule.** Keep the existing 3 s SFX gap. Count voice treatments such as echo tails and rewinds as "effects" for the gap rule, so a punchline echo, a riser and a pop don't pile up in the same second.
- **Content ID.** Code-synthesized SFX are original, not sampled, and SFX are ineligible as references anyway, so the risk is lowest of any option. Imported packs (e.g., meme SFX such as vine boom or bruh) are best kept user-supplied with provenance recorded in `sounds.json`, as the project already does. Treat clips longer than 1 minute with imported sounds as higher risk, because valid claims on Shorts over 1 minute block them worldwide (per the existing report).

### Gaps
- YouTube publishes no figures on how often SFX-triggered claims occur.
- I measured no true-peak or inter-sample overshoot after the oversampled limiter. Verify with `ebur128=peak=true` on real clips.
