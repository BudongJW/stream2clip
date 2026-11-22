# Clip special effects with ffmpeg filters and libass (ASS): techniques, pitfalls, versions, licences (state: Nov 2026)

Test bed for claims tagged **[LT]** (local test, run during this research): ffmpeg `8.1-full_build-www.gyan.dev` on Windows 11, Intel Iris Xe (the only Vulkan device), libass `0.17.4-21-gfadc390` (reported by the `subtitles` filter at `-v verbose`), font provider DirectWrite. Input: 6 s 1920x1080 30 fps H.264 `testsrc2` clip plus a sine audio track, filtered to `-f null`. Timings are wall-clock per whole ffmpeg run (decode, filter, process start-up). Baseline decode with `-vf null` took **0.60 s**. Treat timings as relative and rough (run-to-run noise is about 0.2 s). [LT] has no URL. Everything else is cited.

Doc note: https://ffmpeg.org/ffmpeg-filters.html tracks git master (9.x era). A few options it shows may be newer than 8.1. Version notes below come from the Changelog.

---

## 1. Zoom / punch-in: zoompan vs scale+crop vs crop-with-t, smooth easing, keeping subtitles unzoomed

### Takeaway
`zoompan` handles video input when given `d=1`, `s=<WxH>` and `fps=<src fps>`. It has no `enable` and suffers from integer-rounding jitter: ticket #4298, open since 2015, still unfixed in 2025. The cheap CPU alternative is `scale=...:eval=frame` followed by a fixed-size `crop`. It steps in 2-px increments. For sub-pixel smooth zooms, use `perspective` (CPU, about 5x heavier) or `libplacebo` `crop_w/crop_h` expressions in `t` (GPU/Vulkan, full builds only). To keep captions unzoomed, put `subtitles` after the zoom/shake chain.

### Cited Findings
- **zoompan options.** `zoom, z` is the zoom expression: "Range is 1-10. Default is 1". `d` is "the duration expression in number of frames ... for single input image. Default is 90". `s` defaults to `'hd720'`. `fps` defaults to `'25'`. Variables: `in_w/iw, in_h/ih, out_w/ow, out_h/oh, in, on, in_time/it` ("NAN if the input timestamp is unknown"), `out_time/time/ot, x, y, px, py, zoom, pzoom, duration, pduration, a, sar, dar`. — [FFmpeg filters: zoompan](https://ffmpeg.org/ffmpeg-filters.html#zoompan)
- **zoompan official examples for video.** "Zoom in 2x into center of picture only for the first second of the input video": `zoompan=z='if(between(in_time,0,1),2,1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'`. "Without pausing": `z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:...`. — [FFmpeg filters: zoompan](https://ffmpeg.org/ffmpeg-filters.html#zoompan)
- **Easing works in zoompan [LT].** This eased punch-in (cubic ease-out from 1.0 to 1.3x over 0.4 s starting at t=1) ran fine in **0.90 s**: `zoompan=z='1+0.3*(1-pow(1-min(max((in_time-1)/0.4,0),1),3))':d=1:x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':s=1920x1080:fps=30`. Without `s`/`fps` the output would fall back to the hd720/25 defaults above.
- **zoompan has no timeline support [LT].** `ffmpeg -filters` lists `zoompan` with no `T` flag, so `enable=` is unavailable. The same holds for `crop`, `scale`, `setpts`, `tpad`, `reverse`, `loop`, `trim`, `concat` and `xfade` (xfade shows `.S`). Filters with `T` include `overlay`, `rotate`, `fade`, `eq`, `hue`, `gblur`, `boxblur`, `pixelize`, `rgbashift`, `noise`, `vignette`, `drawbox` and `drawtext`.
- **Jitter in zoompan.** Trac ticket #4298, "zoompan filter creates shaky image", was still open in April 2025, with no owner or resolution. A commenter linked a fork branch `subpixel_zoompan` (github.com/pYtoner/FFmpeg) as "Only actual patch at the moment." — [ffmpeg-trac, 5 Apr 2025](https://ffmpeg.org/pipermail/ffmpeg-trac/2025-April/073192.html); [trac #4298](https://trac.ffmpeg.org/ticket/4298)
- **The usual workaround is to upscale before zoompan**, e.g. `scale=iw*8:ih*8` placed before `zoompan`. Commenters warn about memory use at 4K and above. — [ffmpeg-user 2016 thread](https://lists.ffmpeg.org/pipermail/ffmpeg-user/2016-February/030613.html) (seen via search snippets); a 2020 patch series "avfilter/vf_zoompan: fix shaking when zooming" exists, merge status unverified — [ffmpeg-devel Feb 2020](https://ffmpeg.org/pipermail/ffmpeg-devel/2020-February/257073.html)
- **crop evaluation rules.** `w/out_w` and `h/out_h` are "evaluated during the filter configuration, when the 'w' or 'out_w' command is sent, or when the input frame size changes". `x` and `y` are "evaluated per-frame". Variables include `t` and `n`. Commands `w, h, x, y` are supported. — [FFmpeg filters: crop](https://ffmpeg.org/ffmpeg-filters.html#crop)
- **scale eval mode.** `eval` "Specify when to evaluate width and height expression", with values `init` and `frame`. — [FFmpeg filters: scale](https://ffmpeg.org/ffmpeg-filters.html#scale)
- **Punch-in with scale and a fixed crop [LT].** `scale=w='trunc(1920*(1+0.3*E)/2)*2':h=-2:eval=frame:flags=bicubic,crop=1920:1080`, where E is the eased 0..1 ramp in `t`, ran correctly in **0.88 s**. Because crop re-evaluates w/h when the input size changes, the output stays 1920x1080.
- **perspective for sub-pixel zoom.** It takes corner expressions `x0..y3`. Variables are only `W, H, in, on`: there is **no `t`**, so use `in/FPS`. Options are `interpolation=linear|cubic` and `sense=source|destination`. — [FFmpeg filters: perspective](https://ffmpeg.org/ffmpeg-filters.html#perspective). [LT] A centre zoom with `sense=source:eval=frame` and corners `P=W*(1-1/Z)/2`, `Q=H*(1-1/Z)/2` (Z = zoom as a function of `in/30`) worked, but took **3.47 s** (about 6x baseline).
- **libplacebo crop and placement.** It has `crop_x, crop_y, crop_w, crop_h` (input crop) and `pos_x, pos_y, pos_w, pos_h` (output placement) expressions. Constants include `in_t, t`, `idx`, `cw/ch` and `pw/ph`. Other options include `inputs` (multi-input compositing "similar to hstack, overlay"), `rotate` (0/90/180/270), `fillcolor`, `corner_rounding` and `extra_opts`. — [FFmpeg filters: libplacebo](https://ffmpeg.org/ffmpeg-filters.html#libplacebo)
- **libplacebo zoom on an Iris Xe [LT].** `-init_hw_device vulkan=vk -filter_hw_device vk ... -vf "libplacebo=w=1920:h=1080:format=yuv420p:crop_w='iw/(1+0.3*E)':crop_h='ih/(1+0.3*E)'"` ran in **2.93 s**, including Vulkan init and up/download. Adding an explicit `,hwdownload,format=yuv420p` failed on this iGPU with "No memory type found for flags 0x2".
- **Build availability.** libplacebo, Vulkan and OpenCL are in the gyan.dev **full** build only, not essentials. — [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/). libplacebo filter added in ffmpeg 5.0. — [FFmpeg Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog)

### Inferences
- **Recommended CPU punch-in:** first scale with a small fixed margin (e.g. 1.0–1.1x), then do the eased zoom with `scale=...:eval=frame` and a fixed `crop=OW:OH:x(t):y(t)`. This is fast, and the per-frame `crop` x/y also carries the shake (section 2). If 2-px stepping shows on slow zooms, switch that segment to `perspective` (CPU) or `libplacebo` (GPU, full build) for sub-pixel accuracy.
- **Graph order:** layout (crop/scale/stack/pip) → zoom/shake/flash/colour → `subtitles` → credit `overlay` → `format` → encoder. This keeps text sharp and unzoomed. Only put subtitles before zoom if the text should shake or zoom with the picture.
- **Easing helpers to generate from Python** (p = `clip((t-t0)/d,0,1)` or `min(max(...))`):
  - ease-out cubic: `1-pow(1-p,3)`
  - ease-in-out: `(1-cos(PI*p))/2`
  - overshoot "punch": `1+s*(p-1)*... ` or a damped spring `1-exp(-k*p)*cos(w*p)`
- Since none of the zoom filters support `enable`, gate the zoom amount inside the expression (factor 1 outside the window) rather than with `enable=`.

### Gaps
- No published benchmark compares zoompan, scale+crop, perspective and libplacebo. The timings above come from one iGPU laptop.
- Whether the `subpixel_zoompan` work or the 2020 patch was merged after April 2025 was not verified. Assume zoompan still jitters in 8.x/9.x.

---

## 2. Shake, flash, vignette, colour pop, chromatic aberration, glitch, blur and mosaic

### Takeaway
All of these are single-filter, timeline-gated operations that cost less than real-time on CPU:
- shake: per-frame `crop` x/y and/or `rotate`
- flash: `fade ... color=white` gated with `enable`, or `eq=brightness=f(t):eval=frame`
- colour pop: `hue=s=f(t)`
- aberration: `rgbashift`/`chromashift`
- glitch: `noise` plus `rgbashift` driven by `sendcmd`

Mosaic is `pixelize` (ffmpeg ≥5.1) or scale-down plus `flags=neighbor` (any version). Region censoring is split → crop → blur/pixelize → overlay with `enable`. The expensive ones: full-frame `boxblur` with a large radius, `vignette` and `perspective`.

### Cited Findings
- **Shake with crop.** The crop docs include a "trembling effect", `crop=in_w/2:in_h/2:(in_w-out_w)/2+((in_w-out_w)/2)*sin(n/10):(in_h-out_h)/2 +((in_h-out_h)/2)*sin(n/7)`, and an "erratic camera effect" using `sin(t*10)`/`sin(t*13)`. — [FFmpeg filters: crop](https://ffmpeg.org/ffmpeg-filters.html#crop)
- **[LT] Time-gated shake** (5 % oversize, then per-frame crop) took **0.60 s**: `scale=2016:1134,crop=1920:1080:x='48+40*sin(t*53)*between(t,2,2.5)':y='27+25*sin(t*71)*between(t,2,2.5)'`
- **rotate.** `angle` is "evaluated for each frame". `out_w/out_h` are "evaluated just once during configuration". `fillcolor` defaults to "black", and "none" skips the background. `bilinear` defaults to 1. Variables are `n, t, iw, ih, ow, oh`, and `rotw(a)/roth(a)` exist for size calculation. — [FFmpeg filters: rotate](https://ffmpeg.org/ffmpeg-filters.html#rotate). [LT] `rotate=a='0.03*sin(t*40)*between(t,2,2.5)':c=black` took **0.81 s**.
- **fade options.** `type in|out`, `start_time/st`, `duration/d`, `color`, and `alpha` ("If set to 1, fade only alpha channel, if one exists"). The filter supports the timeline. — [FFmpeg filters: fade](https://ffmpeg.org/ffmpeg-filters.html#fade). [LT] White flash that decays over 0.25 s: `fade=t=in:st=2:d=0.25:color=white:enable='gte(t,2)'` (**0.50 s**).
- **eq expressions.** `brightness` (range −1..1), `contrast`, `saturation` (0..3) and `gamma*` are expressions, with `eval` = `init|frame`. — [FFmpeg filters: eq](https://ffmpeg.org/ffmpeg-filters.html#eq). [LT] `eq=brightness='0.8*max(0,1-abs(t-2)/0.15)':eval=frame` (a triangular flash peaking at t=2) took **0.48 s**, so `t` is accepted.
- **[LT] Colour pop:** `hue=s='1+1.5*between(t,2,3)'` took **0.39 s**. Related filters: `huesaturation` (added 5.0), `colorize`, `colortemperature`, `colorcontrast` and `exposure` (4.4). — [FFmpeg Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog)
- **vignette.** `angle` defaults to `PI/5` and is clipped to [0, PI/2]. Other options: `x0`, `y0`, `mode=forward|backward` (the current docs also list `wavelet`), and `eval`. — [FFmpeg filters: vignette](https://ffmpeg.org/ffmpeg-filters.html#vignette). [LT] `vignette=a=PI/4` took **2.96 s**, about 5x baseline and one of the heaviest tested.
- **rgbashift / chromashift** (both added in 4.2). rgbashift has per-channel `rh, rv, gh, gv, bh, bv, ah, av` and `edge=smear|warp`, and all options work as commands. — [FFmpeg filters: rgbashift](https://ffmpeg.org/ffmpeg-filters.html#rgbashift); [Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog). [LT] `rgbashift=rh=8:bh=-8:enable='between(t,2,3)'` took **0.50 s**.
- **sendcmd syntax.** `START[-END] [FLAGS] TARGET COMMAND ARG`, with flags `enter`, `leave` and `expr` ("ARG is interpreted as expression"). The interval is [START, END). — [FFmpeg filters: sendcmd](https://ffmpeg.org/ffmpeg-filters.html#sendcmd_002c-asendcmd)
- **[LT] Glitch burst via sendcmd** (rc=0): `sendcmd=c='2.0-2.4 [enter] rgbashift@g rh 12, [enter] rgbashift@g bh -12, [leave] rgbashift@g rh 0, [leave] rgbashift@g bh 0',rgbashift@g`. The `[expr]` flag also works: `sendcmd=c='2.0-2.5 [expr] crop x 48+40*sin(TI*30)',crop=1920:1080` (TI = relative time in the interval) ran without error.
- **[LT] Noise:** `noise=alls=40:allf=t:enable='between(t,2,2.3)'` (temporal noise) took **0.55 s**.
- **displace** takes three video inputs (`VVV->V`: source plus x/y displacement maps), usable for wave/glitch warps. — [LT] `ffmpeg -filters`; [FFmpeg filters: displace](https://ffmpeg.org/ffmpeg-filters.html#displace)
- **chromaber_vulkan** (GPU chromatic aberration) was added in 4.3. — [Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog)
- **pixelize** was added in 5.1. Options: block `width/w` and `height/h` (default 16), `mode` = `avg|min|max`, `planes`. "This filter supports all options as commands." It supports the timeline. — [FFmpeg filters: pixelize](https://ffmpeg.org/ffmpeg-filters.html#pixelize); [Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog)
- **[LT] Region censoring**, all rc=0:

  | Method | Graph | Time |
  |---|---|---|
  | Pixelize | `[0:v]split[a][b];[b]crop=600:400:200:200,pixelize=w=24:h=24[p];[a][p]overlay=200:200:enable='between(t,1,4)'` | **0.51 s** |
  | Neighbor-scale mosaic | `...,scale=iw/24:-1,scale=600:400:flags=neighbor[p]...` | **0.58 s** |
  | Gaussian blur | `...,gblur=sigma=20[p]...` | **0.69 s** |
  | Full-frame boxblur | `boxblur=20:2` | **4.11 s** |
- **Blur filter threading [LT].** `gblur` supports the timeline and slice threading (`TS`). `boxblur` and `avgblur` support the timeline only (`T.`). GPU variants are `avgblur_vulkan`, `gblur_vulkan` and `boxblur_opencl`.

### Inferences
- **Moving-region censor:** feed the same x/y expression (or a `sendcmd` keyframe list) to both `crop` (x/y are per-frame) and `overlay` (x/y are per-frame). Keep crop w/h fixed.
- **Blur strategy:** prefer `gblur` on a cropped region over full-frame `boxblur`. For a blurred background layout, downscale first (e.g. to 1/4), blur, then upscale. The cost scales with the blurred area.
- **Deterministic shake:** use sums of sines with incommensurate frequencies, multiplied by an envelope (e.g. `exp(-k*(t-t0))*between(t,t0,t1)`). These are deterministic across runs and frame-rate independent when written in `t`.
- **Flash via fade:** without `enable`, a fade-in shows the fade colour before `st`, hence the `enable='gte(t,st)'` gate. That this is the reason was not verified in source; the gated command was tested. For a flash peaking mid-frame, the `eq` triangle is simpler.

### Gaps
- No authoritative performance data for `displace` or `geq`-based glitches. They were not timed here, and `geq` is known to be per-pixel expression evaluation.
- Whether `random()` in ffmpeg expressions is seeded deterministically across runs was not verified. Use sine sums or precomputed `sendcmd` lists instead.

---

## 3. Speed: slow motion, speed ramps, freeze frame, reverse, instant replay, and keeping karaoke timing right

### Takeaway
Do time changes as segments: `split`/`trim` + `setpts` (video) and `asplit`/`atrim` + `atempo` (audio), then `concat`. Use `fps=<src>` after any `setpts` that changes frame spacing. For freeze, use `tpad=stop_mode=clone` or `loop`. For reverse, use `trim` then `reverse`; it buffers the whole segment in RAM. Captions must be retimed to the output timeline. Alternatively, burn them before the time remap, in which case the text animation slows down too.

### Cited Findings
- **setpts examples:** `setpts=0.5*PTS` (fast), `setpts=2.0*PTS` (slow), `setpts=PTS-STARTPTS`, `setpts=N/(25*TB)`. Variables include `T`, `N`, `TB`, `STARTPTS`, `PREV_OUTT`, and `T_CHANGE` ("Time of the first frame after command was applied"). — [FFmpeg filters: setpts](https://ffmpeg.org/ffmpeg-filters.html#setpts_002c-asetpts)
- **setpts versions.** Command support in setpts/asetpts was added in 6.1. — [Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog). 8.1 also exposes a `strip_fps` option ("Unset framerate metadata"). — [LT] `ffmpeg -h filter=setpts`; [FFmpeg filters: setpts](https://ffmpeg.org/ffmpeg-filters.html#setpts_002c-asetpts)
- **atempo.** "Tempo must be in the [0.5, 100.0] range. ... tempo greater than 2 will skip some samples rather than blend them in", so chain several instances. — [FFmpeg filters: atempo](https://ffmpeg.org/ffmpeg-filters.html#atempo). [LT] `tempo` is a runtime command (`T` flag), and `asendcmd=c='2.0 atempo tempo 0.5; 3.0 atempo tempo 1.0',atempo=1.0` ran with rc=0.
- **rubberband** (pitch-preserving stretch) is in the gyan.dev builds, which are "licensed as GPLv3". Librubberband is GPL. — [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/); [LT] `--enable-librubberband` in the build configuration
- **[LT] Slow motion for 2–3 s at 0.5x with audio** (rc=0, **0.39 s**):
  ```
  [0:v]split=3[v1][v2][v3];[0:a]asplit=3[a1][a2][a3];
  [v1]trim=0:2,setpts=PTS-STARTPTS[va];[a1]atrim=0:2,asetpts=PTS-STARTPTS[aa];
  [v2]trim=2:3,setpts=2*(PTS-STARTPTS)[vb];[a2]atrim=2:3,asetpts=PTS-STARTPTS,atempo=0.5[ab];
  [v3]trim=3,setpts=PTS-STARTPTS[vc];[a3]atrim=3,asetpts=PTS-STARTPTS[ac];
  [va][aa][vb][ab][vc][ac]concat=n=3:v=1:a=1[v][a]
  ```
- **[LT] Continuous speed ramp with one piecewise setpts** (rc=0): `setpts='if(lt(T,2),T,if(lt(T,3),2+(T-2)*2,4+(T-3)))/TB',fps=30`. The output time map is t ↦ t for t<2, 2+2(t−2) for 2–3, and t+1 after. For a smooth ramp, write the integral of 1/speed(t) as the expression. `fps` duplicates frames (no interpolation).
- **minterpolate** exists for motion-interpolated slow motion. — [LT] `ffmpeg -filters`; [FFmpeg filters: minterpolate](https://ffmpeg.org/ffmpeg-filters.html#minterpolate)
- **tpad** (added 4.2). Options: `start`, `stop` (−1 = forever), `start_mode/stop_mode` = `add|clone` ("clone: frames are clones of last frame"), `start_duration/stop_duration`, `color`. — [FFmpeg filters: tpad](https://ffmpeg.org/ffmpeg-filters.html#tpad); [Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog). [LT] Freeze at t=2 for 1 s: `[0:v]split[x][y];[x]trim=0:2,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=1[f];[y]trim=2,setpts=PTS-STARTPTS[r];[f][r]concat=n=2:v=1:a=0` (rc=0).
- **loop.** Options `loop` (−1 = infinite), `size` (max frames), `start` (first frame), and `time` (start in seconds, used if `start=-1`). — [FFmpeg filters: loop](https://ffmpeg.org/ffmpeg-filters.html#loop). [LT] `loop=loop=30:size=1:start=60,setpts=N/30/TB` freezes frame 60 for 30 extra frames (rc=0). `freezeframes` (two inputs: `first`, `last`, `replace`) is an alternative. — [FFmpeg filters: freezeframes](https://ffmpeg.org/ffmpeg-filters.html#freezeframes)
- **reverse.** "Warning: This filter requires memory to buffer the entire clip, so trimming is suggested." Example: `trim=end=5,reverse`. — [FFmpeg filters: reverse](https://ffmpeg.org/ffmpeg-filters.html#reverse). [LT] A 2 s 1080p reverse worked in 0.46 s.
- **[LT] Instant replay** (normal 0–4 s, then a 2× rewind of 2–4 s, then a 0.5× replay of 2–4 s) via `split=3`/`trim`/`reverse`/`setpts`/`concat`. It produced "non monotonically increasing dts to muxer" warnings. Cause: the `reverse,setpts=0.5*PTS` branch yields 60 fps timestamps next to 30 fps branches. Fix: add `fps=30` after every `setpts` that rescales.
- **[LT] subtitles timing pitfall.** With input-side seeking (`-ss 1.1 -i src.mp4 -vf subtitles=fx.ass`), frame timestamps restart at 0, so captions render for the wrong time: none appeared at the 1.1 s mark. Adding `-copyts` (`-ss 1.1 -copyts -i ...`) restored correct caption timing.

### Inferences
- **Frame-accurate retiming for stream2clip.** Build one Python time-map function out(t) per clip (piecewise: normal, slow, freeze, rewind, replay). Use it to:
  1. emit the trim/setpts/atempo/concat graph;
  2. rewrite ASS event `Start`/`End` through out(t);
  3. scale `\k`/`\kf`/`\ko` durations and `\t(t1,t2,...)`, `\move(...,t1,t2)` and `\fad` times by the local slope inside slowed segments;
  4. for reversed or replayed segments, either drop karaoke lines or add a separate "REPLAY" caption.

  This keeps `subtitles` after the time remap, which is also where it should sit relative to zoom (section 1).
- **Audio choices.** For freeze frames, pad the audio with silence (e.g. `apad`/`aevalsrc=0` concat) or duck the music. For a reversed segment, `areverse` exists, but replay rewinds usually get a whoosh SFX instead.
- **Reverse memory estimate:** 1080p yuv420p ≈ 3.1 MB/frame, so 10 s at 30 fps ≈ 0.9 GB. Keep reverse/rewind segments to a few seconds, or pre-render them to an intermediate file.
- **Speed ramp audio** is awkward because `atempo` cannot follow a continuous expression (it can only receive `asendcmd` steps). Use stepped atempo segments, mute the ramp and add SFX, or use `rubberband` (GPL).

### Gaps
- minterpolate quality and speed on consumer CPUs were not measured.
- The exact behaviour of `concat` when segment timebases differ (vs `xfade`, which errors) was not tested separately.

---

## 4. Overlays: stickers, PNG/APNG/GIF/animated WebP, WebM VP9 alpha, ProRes 4444, Lottie, emoji

### Takeaway
`overlay` with `enable=` and per-frame x/y expressions covers timed and moving stickers. Fade a sticker with `fade=...:alpha=1` on an RGBA branch, and shift its start with `setpts=PTS-STARTPTS+T0/TB`. Input notes:
- APNG/GIF play once unless `-ignore_loop 0`.
- Animated WebP decodes only in ffmpeg ≥ 9.0 (Aug 2026).
- VP9 alpha WebM needs `-c:v libvpx-vp9` before `-i`.
- Lottie needs an external renderer: rlottie-python (LGPL-2.1 per metadata) or python-lottie (AGPL-3.0+).
- Colour emoji must be rasterised outside libass (e.g. Pillow `embedded_color=True`), because libass emits single-colour bitmaps only.

### Cited Findings
- **overlay options.** `x`, `y` (invalid values move the overlay off-screen). `eval` = `init|frame`, default "frame". `format`, default `yuv420` (also yuv422/444, 10-bit variants, `rgb`, `gbrp`, `auto`). `alpha` = `straight|premultiplied|auto`. Framesync options `eof_action`, `shortest`, `repeatlast`. Variables `main_w/W, main_h/H, overlay_w/w, overlay_h/h, n, t`. — [FFmpeg filters: overlay](https://ffmpeg.org/ffmpeg-filters.html#overlay)
- **[LT] Timed, fading, bouncing APNG sticker** (rc=0, 0.56 s):
  ```
  -ignore_loop 0 -i sticker.apng
  [1:v]format=rgba,fade=t=in:st=0:d=0.2:alpha=1,setpts=PTS-STARTPTS+2/TB[s];
  [0:v][s]overlay=x='860+200*(t-2)':y='H-300-abs(200*sin((t-2)*8))*exp(-(t-2)*3)':enable='between(t,2,4)':eof_action=pass
  ```
- **[LT] Demuxer options.** The APNG demuxer has `-ignore_loop` (default true), `-max_fps` and `-default_fps` (default 15). The GIF demuxer has `-ignore_loop` (default true, the "netscape extension"), `-min_delay` and `-default_delay`. Both play once by default. Use `-ignore_loop 0` (or `-stream_loop -1`) and bound the result with `enable`/`trim`/`shortest`.
- **Animated WebP needs 9.0.** FFmpeg 9.0 "Lei" (released 3–4 Aug 2026) added an "Animated WebP decoder" and "Animated WebP demuxer". — [FFmpeg Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog); [Phoronix](https://phoronix.com/news/FFmpeg-9.0-Released); [Linuxiac](https://linuxiac.com/ffmpeg-9-0-released-with-animated-webp-decoding-and-new-hardware-acceleration/)
  - 8.1.2 fails with "Could not find codec parameters ... (Video: webp, none): unspecified size". 9.0 opens it as `webp_anim, argb, 320x240, 10 fps` and decodes all frames. Ticket #4907 had been open since 2015. — [lilting.ch test 9.0 vs 8.1.2](https://lilting.ch/en/articles/ffmpeg-9-0-lei-tls-verify-default)
  - [LT] The local 8.1 lists only a still `webp` decoder and the `webp_pipe` demuxer.
  - gyan.dev's current release build is 9.1 (2026-11-20). — [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/)
- **VP9 alpha needs the libvpx decoder.** The native VP9 decoder ignores the alpha side-channel. Forcing `-c:v libvpx-vp9` before `-i` yields correct alpha for overlay or PNG extraction. Ticket #7719 is closed with that answer. Ticket #11165 (2024, still "new") reports that the `movie=` source filter cannot easily force the libvpx decoder. — [trac #7719](https://trac.ffmpeg.org/ticket/7719); [trac #11165](https://trac.ffmpeg.org/ticket/11165). Encoding alpha WebM needs `-pix_fmt yuva420p`. — [trac #8468](https://trac.ffmpeg.org/ticket/8468). [LT] The gyan 8.1 build includes the `libvpx-vp9` decoder.
- **Lottie renderers.** python-lottie (`lottie` on PyPI, Mattia Basaglia) is **AGPLv3+** and renders frames via cairosvg/Pillow. — [PyPI lottie](https://pypi.org/project/lottie/). rlottie-python is a ctypes wrapper that bundles Samsung rlottie in the wheel. It offers `render_pillow_frame()`, `save_frame()` and `save_animation()`, and its licence is listed as **LGPL-2.1** by a metadata aggregator (not confirmed against the repo LICENSE). — [PyPI rlottie-python](https://pypi.org/project/rlottie-python); [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Flaggykiller%2Frlottie-python)
- **libass cannot draw colour emoji.** Issue #381 "support color emoji" is still open. Maintainer astiob (2021): "The current architecture of ASS and of libass does not permit multicoloured glyphs ... Only if libass ever gets an RGBA-based API (#73), will this start looking plausible." TheOneric (9 Jan 2026) listed the blockers: RGBA output, run breaks around emoji (BiDi), 3D transforms and coloured blur, colour-space handling, and the interaction with `\c`, borders and fades. — [libass #381](https://github.com/libass/libass/issues/381)
- **[LT] Emoji in libass 0.17.4 (gyan 8.1, DirectWrite).** `😀🔥` in an ASS line rendered as **monochrome outline glyphs** in the line's colour, via system font fallback, not in colour. Third-party projects report the same, and on macOS empty boxes. — [clipsmith PR #28](https://github.com/AbdulSamad94/clipsmith/pull/28); [ffmpeg-skill issue #395](https://github.com/kajisho5/ffmpeg-skill/issues/395)
- **Pillow colour emoji.** Pillow draws colour glyphs only with `draw.text(..., embedded_color=True)` (PR #4955, merged Oct 2020). The CBDT bitmap build of Noto Color Emoji must be loaded at its strike size **109**, because "FreeType doesn't allow scaling of bitmap fonts". Render at 109 and resize. — [jdhao blog](https://jdhao.github.io/2022/04/03/add_color_emoji_to_image_in_python); [Pillow PR #4955](https://github.com/python-pillow/Pillow/pull/4955); [Pillow issue #1774](https://github.com/python-pillow/Pillow/issues/1774). The COLRv1 build of Noto Color Emoji is vector and "scales to any size". — [Qt blog: Emoji in Qt 6.9](https://qt.io/blog/emoji-in-qt-6.9)

### Inferences
- **Sticker pipeline for stream2clip:**
  1. Normalise every sticker source to an RGBA stream before the main graph. Use PNG directly; APNG/GIF with `-ignore_loop 0`; animated WebP on ≥9.0, or decode it with Pillow (which reads animated WebP) on 8.x; WebM with `-c:v libvpx-vp9`; Lottie via rlottie-python → RGBA frames.
  2. Then `format=rgba` → optional `scale`/`rotate` → `fade=alpha=1` → `setpts=PTS-STARTPTS+T0/TB` → `overlay=...:enable='between(t,T0,T1)':eof_action=pass`.
  3. Make overlay `x`/`y` bounce/slide expressions in `t` so they are deterministic.
- **Piping instead of files:** Python-rendered layers (emoji, Lottie, speed lines) can go to ffmpeg as `-f rawvideo -pix_fmt rgba -s WxH -r FPS -i pipe:` (or a temporary PNG sequence/`.mov` qtrle). This avoids temp files but needs a writer thread to avoid pipe deadlock.
- **A scale bounce on a sticker** needs `scale=w=...:h=...:eval=frame` on the sticker branch, plus centring overlay x/y on `w/2`, `h/2`. Alternatively, pre-render the bounce frames in Pillow, which is simpler and deterministic.
- **Licence fit with MIT:**
  - Bundling or importing AGPL python-lottie would impose AGPL terms on the distributed combination. Calling it only as an optional, separately installed external process is the low-risk route.
  - rlottie-python (LGPL) can be an optional dependency.
  - Pillow (HPND) and the Noto fonts (OFL) are permissive. The fonts' OFL licence comes from general knowledge and was not verified here.

### Gaps
- ProRes 4444 (`yuva444p10`) alpha decoding via the native ProRes decoder was not tested or sourced in this session.
- Whether Pillow (version in use) renders **COLRv1** Noto Color Emoji or Windows' Segoe UI Emoji (COLR) in colour was not verified. Test it, or use the CBDT build at size 109.
- The rlottie-python licence was taken from metadata, not the repository LICENSE file.

---

## 5. libass animated text: \t, \move, \fad/\fade, \blur/\be, \bord/\shad, \clip/\iclip, \p drawings, \org, karaoke; versions; PyonFX

### Takeaway
ASS supports these fully in libass 0.17.x:
- scale bounce: chained `\t(t1,t2,\fscx..\fscy..)`
- wobble: `\frz` chains around a fixed `\org`
- pop-in: `\fscx0\fscy0` + `\t` + `\fad`
- motion: `\move`, linear only and one per line
- vector shapes: `\p1` drawings (speed lines/集中線, bubbles)
- karaoke: `\k`/`\kf`/`\ko`, plus `\kt` since 0.17.0

Limits: only rectangular clips animate, `\org` cannot animate, and one `\pos`/`\move` per line. Per-character effects are generated by splitting text into one event per character or syllable.

### Cited Findings
- **\t animatable tags.** `\fs \fsp \c \1c-\4c \alpha \1a-\4a \fscx \fscy \frx \fry \frz \fr \fax \fay \bord \xbord \ybord \shad \xshad \yshad \clip \iclip \be \blur`. Syntax `\t([t1,t2,][accel,]modifiers)`, with times in ms relative to line start. accel=1 is linear, <1 starts fast, >1 starts slow (y = x^accel). — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **Official examples:** `{\an5\fscx0\fscy0\t(0,500,\fscx100\fscy100)}Boo!` (grow-in) and `{\an5\t(0,5000,0.5,\frz3600)}` (ease-out spin). — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **Clip limits.** "For \clip and \iclip, only the rectangle versions can be animated. The vector drawing versions cannot be animated." "Mixing \clip and \iclip in \t tags has undesireable results." Clip coordinates are integers. — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **\org.** "you can not animate the \org tag". There is at most one `\org` per line (only the first is used). Without `\org`, rotation is around the `\pos`/`\move` anchor. A far-away `\org` plus small rotations can fake curved or accelerated moves. — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **\move.** `\move(x1,y1,x2,y2[,t1,t2])`. "There can only be one positioning or movement tag in a line". No acceleration (hence the `\org` trick). — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **Fades.** `\fad(in,out)` is taken from the line's own duration. `\fade(a1,a2,a3,t1,t2,t3,t4)` is the 7-parameter alpha envelope. — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **\blur vs \be.** `\blur` is Gaussian and fractional: "setting strength too high can take a lot of CPU time". `\be` is "discouraged since it does not scale correctly with the frame size". Both blur only the border when `\bord` > 0. — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **Karaoke.** `\k` switches instantly. `\K`/`\kf` sweep left to right. `\ko` removes the outline until the syllable starts. Durations are in centiseconds. `\kt` sets the absolute start of the next syllable. — [Aegisub ASS tags](https://aegisub.org/docs/latest/ass_tags/)
- **libass releases:**

  | Version | Changes |
  |---|---|
  | 0.15.0 | "Fix stack overflow on deeply nested \t"; `\t(T,T,...)` at exactly T uses post-transition values; "Multiple fixes for karaoke override tags"; HarfBuzz required |
  | 0.16.0 | "Improve \iclip quality"; `ASS_FEATURE_WHOLE_TEXT_LAYOUT`; wyhash cache |
  | 0.17.0 | `LayoutRes{X,Y}` headers; `AlphaLevel` style override; "Support the \kt override tag"; `ASS_FEATURE_WRAP_UNICODE` (libunibreak); "Fix premature truncation of animated alphas" |
  | 0.17.2 | "Improve quality of animated rectangular clips"; SSSE3/aarch64 asm |
  | 0.17.3 | "Speed up parsing of events with very long override blocks" |
  | 0.17.4 | `ass_prune_events`; `ASS_OVERRIDE_BIT_BLUR` |
  | 0.17.5 | OOB read/write security fixes; "Fades are now applied to BorderStyle=4 boxes too"; `\fay` fix |

  — [libass releases](https://github.com/libass/libass/releases) (the page shows dates without years)
- **[LT] ffmpeg `subtitles` options (8.1):** `filename/f`, `original_size`, `fontsdir`, `alpha`, `charenc`, `stream_index/si`, `force_style`, `wrap_unicode` (default auto). There are no runtime commands.
- **[LT] Rendered correctly in libass 0.17.4** (PlayResX/Y 1920x1080), 1.80 s for 6 s with all lines:
  - Pop-in bounce: `{\pos(960,540)\fscx0\fscy0\t(0,120,\fscx130\fscy130)\t(120,220,\fscx90\fscy90)\t(220,300,\fscx100\fscy100)\fad(0,200)}POP!`
  - Wobble: `{\pos(960,300)\org(960,300)\t(0,100,\frz8)\t(100,200,\frz-8)\t(200,300,\frz5)\t(300,400,\frz0)\blur2\t(0,300,\blur0)}WOBBLE`
  - Eased move: `{\move(200,900,1700,900,0,600)\t(0,600,0.5,\fscx150)}MOVE`
  - Karaoke: `{\k30}KA{\kf40}RA{\ko30}O{\k40}KE`
  - Speed lines (集中線) as one drawing event, i.e. triangles from the centre to the frame edges: `{\an7\pos(0,0)\1c&HFFFFFF&\1a&H40&\p1}m 960 540 l 0 0 40 0 m 960 540 l 1920 0 1920 40 ...{\p0}`
- **PyonFX** ("easy way to create KFX (Karaoke Effects) and complex typesetting using the ASS format") is licensed **LGPL v3.0**. — [PyonFX GitHub](https://github.com/CoffeeStraw/PyonFX)

### Inferences
- **Generate ASS from Python directly** (stream2clip already writes karaoke ASS). Helpers needed:
  - bounce/wobble presets that emit `\t` chains, approximating easing curves with 3–6 linear or `accel` segments;
  - per-character split for staggered pop-in: one Dialogue per glyph with its own `\pos` and a start offset. Glyph x positions need font metrics: measure with Pillow `ImageFont.getbbox`/`getlength` for the same font file, or use `\an` plus centre-relative offsets and accept small kerning differences;
  - `\p` generators for speed lines (randomised wedge widths with a fixed seed), burst stars and speech bubbles.

  This avoids depending on LGPL PyonFX (importing it from MIT code is possible, but its own LGPL terms apply to it).
- **Animated speed lines:** rotate the drawing with `\t(\frz...)` around `\org(960,540)`, or emit 3–4 alternating Dialogue lines every ~66 ms for a flicker. A vector `\clip` cannot be animated, so use multiple lines.
- **Cost control:** `\blur` cost grows with radius and glyph area. Keep `\blur` ≤ 3 on large text, and animate blur only briefly.
- **Script resolution:** set `PlayResX/PlayResY` equal to the output size, plus `original_size` if rendering onto a differently scaled frame. That keeps `\pos`/`\move`/`\clip` pixel-exact and makes `LayoutRes` unnecessary.

### Gaps
- No evidence of a `\fsvp` tag in libass or the Aegisub reference. Variable-font axis support and per-release `\blur` performance changes were not found in the release notes visible in this session.
- The Aegisub karaoke templater's licence and template syntax were not researched in depth.

---

## 6. Transitions between clips: xfade, xfade_opencl/vulkan, acrossfade, GL transitions, whip pans

### Takeaway
`xfade` (ffmpeg ≥4.3) has about 58 built-in transitions plus a `custom` per-pixel expression. Both inputs must match in size, pixel format, frame rate **and timebase**; normalise with `scale`, `format`, `fps`, `settb` before it. `offset` is measured on the first input's timeline. Pair it with `acrossfade` for audio. `custom` expressions are slow. GPU variants (`xfade_opencl` 4.3, `xfade_vulkan` 6.1) exist. ffmpeg-gl-transition needs a patched custom ffmpeg build and its repository has no licence file, so it is not a practical dependency.

### Cited Findings
- **xfade requirements.** "Both inputs must be constant frame-rate and have the same resolution, pixel format, frame rate and timebase." Options:
  - `transition`: custom, fade, wipeleft/right/up/down, slideleft/right/up/down, circlecrop, rectcrop, distance, fadeblack, fadewhite, radial, smoothleft/right/up/down, circleopen/close, vertopen/close, horzopen/close, dissolve, pixelize, diagtl/tr/bl/br, hlslice, hrslice, vuslice, vdslice, hblur, fadegrays, wipetl/tr/bl/br, squeezeh/v, zoomin, fadefast, fadeslow, hlwind, hrwind, vuwind, vdwind, coverleft/right/up/down, revealleft/right/up/down
  - `duration`: 0–60 s, default 1
  - `offset`: "relative to first input stream in seconds"
  - `expr`: variables `X, Y, W, H, P, PLANE, A, B, a0..a3(x,y), b0..b3(x,y)`

  — [FFmpeg filters: xfade](https://ffmpeg.org/ffmpeg-filters.html#xfade)
- **[LT] Error messages for mismatched inputs:**
  - size: "First input link main parameters (size 1920x1080) do not match the corresponding second input link xfade parameters (size 1280x720)"
  - fps: shows up as a timebase error, "... main timebase (1/15360) do not match ... xfade timebase (1/25)"
  - an mp4 segment (tb 1/15360) against a lavfi source (tb 1/30) fails the same way; adding `settb=1/30` to both inputs fixed it.
- **[LT] Cost:** `xfade=transition=slideleft:duration=0.5:offset=3.5` took 1.08 s total. The `custom` transition `expr='if(gt(X,W*P),A,B)'` took **3.02 s** for only 0.5 s of transition, because per-pixel expression evaluation is slow.
- **Versions:** xfade and xfade_opencl were added in 4.3, xfade_vulkan in 6.1. — [Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog). xfade_opencl's `custom` transition takes the OpenCL `source` and `kernel` options. — [FFmpeg filters: xfade_opencl](https://ffmpeg.org/ffmpeg-filters.html#xfade_005fopencl)
- **acrossfade.** `duration/d`, `overlap/o` (default on), `curve1/curve2` (afade curve types), and `inputs/n` ("each input will be concatenated and crossfaded in sequence"). Example: `acrossfade=d=10:c1=exp:c2=exp`. — [FFmpeg filters: acrossfade](https://ffmpeg.org/ffmpeg-filters.html#acrossfade)
- **ffmpeg-gl-transition.** Repository metadata lists "License: None" (the Gitee mirror says "Not specified"). It must be compiled into ffmpeg by copying `vf_gltransition.c` and applying `ffmpeg.diff`, with `--enable-opengl` and GLEW (plus Xvfb headless on Linux). — [ecosyste.ms entry](https://awesome.ecosyste.ms/projects/github.com%2Ftransitive-bullshit%2Fffmpeg-gl-transition); [Gitee mirror](https://gitee.com/wgx0307/ffmpeg-gl-transition)
- **dblur** (directional blur) was added in 4.3. — [Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog); [FFmpeg filters: dblur](https://ffmpeg.org/ffmpeg-filters.html#dblur)

### Inferences
- **Normalisation recipe** before every xfade: `fps=F,scale=W:H,format=yuv420p,settb=1/F,setpts=PTS-STARTPTS`. For a chain of N clips, offset_k = sum of previous durations − k·d (accumulate in Python).
- **Whip pan:** apply an eased fast horizontal pan to the end of clip A (crop x(t), section 1) and the start of clip B, add `gblur`/`dblur` (horizontal) gated with `enable` for ~6–10 frames, and join with `xfade=slideleft` (or a hard cut) at the blur peak. Add a whoosh SFX via `amix`.
- **GL transitions without the custom build:** port a few GLSL transitions to `xfade=custom` expressions, which are slow but fine for 0.3–0.5 s, or to libplacebo `custom_shader_path`/OpenCL kernels on full builds. All of these keep the toolchain stock.

### Gaps
- No measurement of `xfade_vulkan`/`xfade_opencl` speed vs CPU `xfade` on consumer GPUs. Not tested here.
- Whether `libplacebo` custom shaders can implement two-input transitions (with `inputs=2` and `idx`) was not verified.

---

## 7. GPU / accelerated filters on Windows builds, and whether they help

### Takeaway
CUDA (`scale_cuda`, `overlay_cuda`, `pad_cuda` 8.0, `transpose_cuda` 9.0), D3D11/D3D12 scalers (8.0/8.1), Vulkan (`libplacebo`, `xfade_vulkan`, `overlay_vulkan`, `gblur_vulkan`, `chromaber_vulkan`, swscale-on-Vulkan in 8.1+) and OpenCL filters exist. In gyan.dev builds, Vulkan, OpenCL and libplacebo are **full-build only**. The `subtitles`/libass path and most effect filters are CPU-only, so a GPU graph needs upload/download hops. For 1080p short clips, CPU filters run several times faster than real-time; the GPU win is in the encoders (NVENC/QSV/AMF), which stream2clip already uses.

### Cited Findings
- **Versions:**

  | Version | Added |
  |---|---|
  | 3.4 | scale_cuda |
  | 4.3 | overlay_cuda; avgblur_vulkan, overlay_vulkan, scale_vulkan, chromaber_vulkan; xfade_opencl |
  | 5.0 | libplacebo |
  | 6.1 | xfade_vulkan |
  | 8.0 | pad_cuda, vf_scale_d3d11 |
  | 8.1 | vf_scale_d3d12; "swscale Vulkan support"; drawvg (libcairo) |
  | 9.0 | v360_vulkan, transpose_cuda, AMF FRC |
  | 9.1 | vf_fruc_vulkan (NVIDIA optical-flow interpolation), vf_vqe_amf |

  — [FFmpeg Changelog](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/Changelog)
- **overlay_cuda** "only accepts CUDA frames. The underlying input pixel formats have to match." — [FFmpeg filters: overlay_cuda](https://ffmpeg.org/ffmpeg-filters.html#overlay_005fcuda)
- **gyan.dev builds.** Essentials includes cairo, libass, libvpx, libwebp and librubberband. libplacebo, vulkan, opencl and frei0r are full-only. amf, cuda, cuvid, d3d11va, d3d12va, dxva2, libvpl, nvdec, nvenc and vaapi are in all builds. "All builds are 64-bit, static and licensed as GPLv3". Current release is 9.1 (2026-11-20). — [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/)
- **BtbN builds.** Variants: `gpl` ("Includes all dependencies, even those that require full GPL"), `lgpl` ("Lacking libraries that are GPL-only. Most prominently libx264 and libx265"), `nonfree` (adds fdk-aac), and `-shared` variants. win64 and winarm64 auto-builds cover master and release branches 4.4–9.0. — [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds)
- **[LT] Local 8.1 full build GPU filters:** `libplacebo`, `overlay_vulkan`, `blend_vulkan`, `avgblur_vulkan`, `gblur_vulkan`, `chromaber_vulkan`, `transpose_vulkan`, `scale_vulkan`, `xfade_vulkan`, `overlay_cuda`, `scale_cuda`, `overlay_opencl`, `boxblur_opencl`, `xfade_opencl`, `overlay_qsv`, `vpp_qsv`, `scale_d3d11` and `scale_d3d12`. frei0r and rubberband are enabled (`--enable-frei0r`, `--enable-librubberband`, under `--enable-gpl --enable-version3`).
- **[LT] Vulkan on Iris Xe.** The device was detected ("Intel(R) Iris(R) Xe Graphics (integrated)"). A libplacebo zoom ran in 2.93 s against 0.88 s for the CPU scale+crop. An explicit `hwdownload` failed with "No memory type found for flags 0x2".

### Inferences
- **For stream2clip,** keep the effect graph on CPU and keep GPU encoders. Add optional GPU paths only for heavy, isolated steps where profiling shows a bottleneck: big blurred backgrounds (`gblur_vulkan`/`boxblur_opencl`) and sub-pixel zoom (`libplacebo`). Driver and iGPU variance (as in the Iris Xe download failure) argues for automatic CPU fallback, which stream2clip already does for encoders.
- **Licensing:**
  - gyan.dev builds (essentials and full) and BtbN `gpl` builds are GPL. frei0r and rubberband are GPL components, and x264/x265 are GPL-only.
  - Calling ffmpeg via subprocess keeps stream2clip's MIT code separate.
  - Redistributing a GPL ffmpeg binary alongside the tool brings GPL source-offer obligations for that binary. Prefer letting users install ffmpeg, or ship a BtbN `lgpl` build, which loses libx264/x265 but keeps hardware encoders.
  - Avoid depending on `frei0r`/`rubberband` filters for core features.

### Gaps
- Whether the BtbN win64 `lgpl` build includes libass, libplacebo, Vulkan and OpenCL was not confirmed (the README points to `scripts.d`).
- No benchmark of CUDA overlay/scale vs CPU for 1080p30 short clips on NVIDIA consumer GPUs was found in this session.

---

## 8. Alternatives to ffmpeg-only: Pillow/numpy/skia, MoviePy, Remotion, Motion Canvas, Manim, Blender; licence fit for an MIT tool

### Takeaway
The practical, licence-clean pattern is a hybrid: keep the ffmpeg filtergraph for video ops and libass for text. Render effects that ffmpeg/libass cannot do well (colour emoji, Lottie, complex per-character motion, particle bursts) in Python with Pillow/numpy, or skia-python (BSD-3, Windows wheels), into RGBA frames that are piped into or overlaid onto the graph. ffmpeg ≥8.1 also has `drawvg` (cairo vector scripts with `t`) for in-graph vector graphics. MoviePy is MIT but slower than direct ffmpeg. Remotion is source-available with a company licence and unsuitable. Motion Canvas is MIT but browser/Node-based. Manim and Blender licences were not verified here.

### Cited Findings
- **skia-python** is licensed BSD-3-Clause. It ships Windows wheels ("Windows x86_64, arm64") for CPython 3.9–3.15, has release notes up to m144, and offers GPU acceleration on Linux via GLX/EGL. — [kyamagu/skia-python](https://github.com/kyamagu/skia-python)
- **MoviePy** is MIT. Its README says it is "slower than using ffmpeg directly due to heavier data import/export operations". Version 2.0 introduced breaking changes, and v1 is unmaintained. — [MoviePy GitHub](https://github.com/Zulko/moviepy); [PyPI moviepy](https://pypi.python.org/pypi/moviepy). A competing library's own (vendor) benchmark reports a complex composition at 175.31 s in MoviePy vs 38.07 s in MovieLite (unverified). — [MovieLite benchmarks](https://www.mintlify.com/francozanardi/movielite/resources/performance-benchmarks)
- **Remotion:** "Remotion is source-available software, but it is not open source software." The free licence covers individuals and organisations of up to 3 people; larger companies need a Company licence ($25/month per creator seat, or $0.01 per render with a $100/month minimum for automators). Licensees may not let others "avoid buying a license". — [Remotion License FAQ](https://www.remotion.dev/docs/license/faq)
- **Motion Canvas** is MIT. A proposed switch to GPLv3 (March 2024) was "postponed indefinitely" (4 April 2024). — [motion-canvas discussion #1015](https://github.com/orgs/motion-canvas/discussions/1015). A Remotion comparison page notes that Motion Canvas renders canvas content in the browser. — [Remotion: Motion Canvas comparison](https://www.remotion.dev/docs/compare/motion-canvas). Revideo, an MIT fork, advertises a headless render API (from its README via search, not verified in depth). — [Revideo README](https://cdn.jsdelivr.net/gh/midrender/revideo@main/README.md)
- **drawvg** (8.1, needs `--enable-cairo`) draws vector graphics from a VGS script with expressions in `t`, e.g. `translate (w/2) (h/2) rotate t rect -100 -100 200 200 setcolor red@0.5 fill`. It converts YUV input to an RGB format, so append `format=yuv420p`. — [FFmpeg filters: drawvg](https://ffmpeg.org/ffmpeg-filters.html#drawvg). gyan.dev says drawvg is in all builds. — [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/). [LT] `drawvg=s='translate (w/2) (h/2) rotate (t*2) rect -300 -10 600 20 setcolor white@0.6 fill',format=yuv420p` took 1.40 s.

### Inferences
- **Recommended architecture.** An "effect layer renderer" in Python (Pillow; skia-python optional for anti-aliased vector work, gradients and blur) produces short RGBA clips, one per effect instance, or a single full-length RGBA layer piped as rawvideo. The main ffmpeg graph overlays them with `enable` windows. This stays deterministic (seeded RNG, fixed fps) and scriptable, and it avoids JS runtimes and browsers.
- **Use in-graph filters for everything cheap:** zoom, shake, flash, colour, mosaic, speed, xfade and libass text. Render externally only for colour emoji, Lottie stickers and particle/sticker animations that ASS cannot express.
- **Remotion** cannot be redistributed as part of an MIT tool without imposing its licence terms on companies of 4+ people, so it is not suitable. Motion Canvas and Revideo are MIT but would add a Node and headless-browser dependency, which is heavy for a consumer Windows CLI.

### Gaps
- Manim Community's licence (believed MIT) and Blender's licence (believed GPL-2.0-or-later; usable only as an external process) were **not verified** with sources in this session.
- No head-to-head benchmark was found for Pillow vs skia-python per-frame RGBA rendering at 1080p, or for the throughput of rawvideo piping into ffmpeg on Windows.
