# Live2D Ecosystem and 2D-VTuber External Projects (for stream2clip)

Scope: Live2D only (official SDK/Editor, open-source runtimes, open alternatives, AI-assisted rigging/animation, lip-sync/offline rendering, model licensing). General rendering apps and 3D/VRM are covered by other researchers.
Research date: 2026-11-18. GitHub star counts, licenses, and last-push dates come from the GitHub search API on 2026-11-18. GitHub reports "other" when it cannot detect a standard license; treat that as a custom license that must be read. "Stale" means no push for more than about 12 months.

---

## 1. Official Live2D: Editor, SDKs, Cubism 5 features, licensing, file formats

### Takeaway
Live2D Cubism 5.3 (Jan 2026) is the current stable Editor, and 5.4 has been in alpha since July 2026. The SDK ships for Web, Native, Unity, Java and Unreal (Unreal is still beta). The Framework layers are open on GitHub, but the Cubism Core runtime is proprietary. Individuals and businesses with annual sales under 10 million JPY need no SDK release license, except for "Expandable Applications" such as VTuber tracking software, which always need review and a special agreement. That exception matters most for a tool like stream2clip that loads users' own models.

### Cited Findings
**Editor versions and features**
- Cubism Editor 5.3.00 was released on 2026-01-20. Its headline features are "blend mode" (an expansion of the old blend method) and "offscreen drawing". Both make models more expressive but add drawing load — [Live2D update page](https://www.live2d.com/en/cubism/update/); [What's New in 5.3](https://docs.live2d.com/en/cubism-editor-manual/new-function5-3/); [5.3 model-creation notes](https://docs.live2d.com/en/cubism-editor-manual/cubism5-3-notes/)
- 5.3's feature list also includes "aliasing" and WebM video output. One source says more than 10 RGB color blends plus alpha blending can be set per object — [SDK support for 5.3 features](https://docs.live2d.com/en/cubism-sdk-manual/cubism-5-3-new-functions/); [5.3 compatibility and limitations](https://docs.live2d.com/en/cubism-sdk-manual/compatibility-with-cubism-5-3/). The WebM detail comes from a search-result summary, not a page I read in full.
- 5.3 features are supported in SDK beta3 environments, including Vulkan. In Unity, models that use any 5.3 feature are drawn by a different, heavier method — [SDK support for 5.3 features](https://docs.live2d.com/en/cubism-sdk-manual/cubism-5-3-new-functions/)
- The Cubism 5.4 alpha was announced on 2026-07-14. Alpha2 could be used until 2026-10-18 23:59 JST, and no beta or final date was given. The announcement lists no 5.4 features beyond pointing to Live2D's YouTube and X accounts. It also says 5.3 is the cutoff for features in the FREE version — [Cubism 5.4 alpha announcement](https://www.live2d.com/en/information/cubism-5_4-alpha/)
- 5.0 (Sept 2023) added "Motion Sync", an enhanced lip-sync that generates mouth movement from voice and can write it as timeline keyframes. It also extended Blend Shapes to rotation deformers, opacity, draw order, multiply/screen color, glue and more — [5.0 New Features](https://docs.live2d.com/en/cubism-editor-manual/new-function5-0/); [update 5.0.00](https://www.live2d.com/en/cubism/update/update_5_0_00/)
- 5.1 (July 2024) enhanced model templates. A Live2D page says new AI features can automatically generate deformers and swaying (physics-like) motions, but that page does not state the version — [5.1 New Features](https://docs.live2d.com/en/cubism-editor-manual/new-function5-1/); [live2d.com ?p=7392](https://www.live2d.com/en/?p=7392)
- 5.2 (Feb 2025) added the Parameter Controller with IK, which inserts keyframes automatically as you move the controller, plus "Paste inverted shapes" and "Restore deformer shapes" — [5.2 New Features](https://docs.live2d.com/en/cubism-editor-manual/new-function5-2/); [MoguraVR on 5.2.00 (JA)](https://www.moguravr.com/?p=263677)
- In the Cubism 5 SDK, Motion Sync is only "partially supported" (Unity only as of the Cubism 5 SDK beta). Enhanced Blend Shapes are supported from Cubism 5 — [SDK Support for New Features in Cubism 5](https://docs.live2d.com/en/cubism-sdk-manual/cubism-5-new-functions/)

**SDKs (official GitHub repos; all show "other" licenses on GitHub)**
- [Live2D/CubismWebFramework](https://github.com/Live2D/CubismWebFramework): 238 stars, last push 2026-04-02. [Live2D/CubismWebSamples](https://github.com/Live2D/CubismWebSamples): 398 stars, last push 2026-04-02 — GitHub search API
- [Live2D/CubismNativeFramework](https://github.com/Live2D/CubismNativeFramework): 267 stars, last push 2026-06-26. [CubismNativeSamples](https://github.com/Live2D/CubismNativeSamples): 242 stars. Both repo descriptions say Cocos2d-x support ends with "Cubism 5 SDK for Native R2" — GitHub search API
- [Live2D/CubismUnityComponents](https://github.com/Live2D/CubismUnityComponents): 264 stars, last push 2026-10-29 — GitHub search API
- [Live2D/CubismJavaFramework](https://github.com/Live2D/CubismJavaFramework): 16 stars. [CubismJavaSamples](https://github.com/Live2D/CubismJavaSamples): 31 stars. Both last pushed 2026-06-04 — GitHub search API
- [Live2D/CubismWebMotionSyncComponents](https://github.com/Live2D/CubismWebMotionSyncComponents): 11 stars, last push 2026-10-15. This is the MotionSync plugin for Cubism SDK for Web. It needs the separate "Live2D Cubism MotionSync Core", which is not in the repo. It supports Chrome/Edge/Firefox/Safari on Windows, macOS, Android and iOS — [repo README](https://github.com/Live2D/CubismWebMotionSyncComponents)
- Unreal: "Cubism 5 SDK for Unreal Engine R1 alpha1" was released in Sept 2024. Beta1 followed on 2025-05-29, adding render-to-render-target, re-import and motion consistency checks for UE 5.3–5.5. A full release had been planned "within 2025" — [Automaton (JA), alpha](https://automaton-media.com/articles/newsjp/20240905-309398/); [Automaton (JA), beta](https://automaton-media.com/articles/newsjp/live2d-ue-beta-20250529-341785/); [MoguraVR](https://www.moguravr.com/live2d-cubism-sdk-unreal-engine-beta-release/); [Live2D docs, Cubism SDK for Unreal Engine](https://docs.live2d.com/en/cubism-sdk-manual/cubism-sdk-for-unreal-engine/). One search summary mentioned an "R1 beta2" notice dated 2026-09-29 on the docs site, but I did not verify it directly.
- Cubism Core is distributed through Live2D's download pages under the Live2D Proprietary Software License, not on GitHub — [Cubism Core docs](https://docs.live2d.com/en/cubism-sdk-manual/cubism-core/)

**Licensing**
- The SDK is free to download and evaluate under the Live2D Proprietary Software License Agreement and the Live2D Open Software License Agreement. A "Publication (Release) License" is required only at release, and it must be completed at least one month before release — [Live2D SDK license page](https://www.live2d.com/en/sdk/license/)
- Individuals and small-scale enterprises are exempt from the release license and payment, "excluding Expandable Applications". Mid-size or larger enterprises may be exempt for temporary promotional use after review — [Live2D SDK license page](https://www.live2d.com/en/sdk/license/)
- Enterprise size is set by latest annual sales. Small-scale is under 10 million JPY, middle-scale is 10–100 million JPY, and large-scale is 100 million JPY or more. If another company substantially manages the business, the operating company's sales count — [Live2D Help ?p=5838](https://help.live2d.com/en/?p=5838); [Live2D Help ?p=2558](https://help.live2d.com/en/?p=2558)
- Required plans vary by product: games use plans D/B/F/E/G, native apps D/E/G, and web apps B/E/G. AI and chatbot content follows the web or native app flowcharts. Video and animation use plans B/E or C (Running Royalty for video content). "VTuber tracking software" is classed as an Expandable Application, which needs review and a special agreement before release. Gaming machines, events, embedded use and BtoBtoX require contacting Live2D — [Live2D SDK license page](https://www.live2d.com/en/sdk/license/)
- A separate VTuber license applies to VTuber streaming businesses whose annual revenue "exceeds JPY 20 million under certain conditions". Separately, the tracking-software (Expandable Application) terms say businesses must notify Live2D when annual sales exceed 20 million JPY — [Live2D SDK license page](https://www.live2d.com/en/sdk/license/); [Live2D Help ?p=2172](https://help.live2d.com/en/?p=2172)
- Plan pages: [running plan01](https://www.live2d.com/en/sdk/license/running_plan01/), [running plan02](https://www.live2d.com/en/sdk/license/running_plan02/), [purchase plan02](https://www.live2d.com/en/sdk/license/purchase_plan02/), [non-profit plan02](https://www.live2d.com/en/sdk/license/non-profit_plan02/)

**File formats**
- `.moc3` holds the actual model data for applications. `.model3.json` links the MOC3, textures and other files. `.physics3.json` holds physics (secondary motion). `.motion3.json` holds motion data from the Animation workspace. `.exp3.json` holds expressions, exported from motion3 files made for expressions. `.pose3.json` controls part switching, such as arm swaps — [Live2D docs: File Types and Extensions](https://docs.live2d.com/en/cubism-editor-manual/file-type-and-extension/); [Data for Embedded Use](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/); [Expression Settings and Export](https://docs.live2d.com/en/cubism-editor-manual/setting-and-exporting-facial-expressions/)
- `.cmo3` is the Editor's project format. psd2live (Section 4) claims to export `.cmo3` and `.moc3` for Cubism 3.0–5.3 — [psd2live README](https://github.com/tsunehimatoi/psd2live)

### Inferences
- If stream2clip renders a VTuber's own Live2D model, it embeds Cubism Core. When a company with 10M JPY or more in annual sales releases a web app that does this, it needs plan B/E/G. If stream2clip lets end users load arbitrary models, it may fall under "Expandable Application" like VTuber tracking software. That category is not exempt even for small entities, so confirm with Live2D before any public release.
- The `.motion3.json` format is plain JSON with parameter curves. stream2clip could generate motion3 files (for example a mouth-open curve from audio) offline, without the Editor. shinshin86's web UI (Section 4) shows this is practical.
- 5.3 blend modes and offscreen drawing raise the requirements for third-party renderers. Older community runtimes that predate 5.3 may draw such models wrong. Test real streamer models made with 5.3.

### Gaps
- I could not find the exact fee amounts for plans B/C/E/G; the pages require contacting Live2D.
- I could not confirm the formal definition of "Expandable Application" (whether "users load any model" alone qualifies) from the primary text, only the tracking-software example.
- I did not verify the full 5.4 feature list, which is published as videos and X posts. The 5.1 AI deformer and sway generation is not confirmed against a version.
- I did not confirm whether the Unreal SDK has reached a full release by Nov 2026.
- Which license covers which SDK component: the license page does not map them. Core is confirmed proprietary; the Framework being under the Live2D Open Software License is consistent with the [Framework LICENSE copy](https://cdn.jsdelivr.net/npm/phaser3-rex-plugins@1.80.20/plugins/gameobjects/live2d/framework/LICENSE.md) but was not read in full.

---

## 2. Open-source Live2D runtimes and wrappers (URL, stars, license, status)

### Takeaway
On the web, the original `pixi-live2d-display` has effectively stalled (Pixi v6/v7, last push Aug 2024). Active development has moved to forks, and `untitled-pixi-live2d-engine` (Pixi v8, Cubism 2–5, MIT, built-in `speak()` lip-sync, RenderTexture support) is the strongest candidate for stream2clip's web preview and render path. For Python, `live2d-py` is the maintained option. GDCubism (Godot) is semi-stale, and Unreal relies on the official beta SDK.

### Cited Findings
**PixiJS runtimes (web)**
- [guansss/pixi-live2d-display](https://github.com/guansss/pixi-live2d-display): 1,518 stars, MIT, last push 2024-08-20. Effectively stale; targets PixiJS v7 or earlier — GitHub search API; [lipsyncpatch README notes the base is a PixiJS v7 plugin](https://npmjs.com/package/pixi-live2d-display-lipsyncpatch)
- [pixi-live2d-display-lipsyncpatch (npm)](https://npmjs.com/package/pixi-live2d-display-lipsyncpatch), source at [RaSan147/pixi-live2d-display](https://github.com/RaSan147/pixi-live2d-display/blob/master/README.md). It adds `model.speak(audio, {volume, expression, crossOrigin, onFinish, onError})` and `model.stopSpeaking()`. Documentation and examples target Pixi v7 (^7.4.3), with no v8 support stated. Stars and license were not retrieved because the GitHub API blocked this repo.
- [Untitled-Story/untitled-pixi-live2d-engine](https://github.com/Untitled-Story/untitled-pixi-live2d-engine): 83 stars, MIT, created 2026-01-23, last push 2026-11-15 (active). It needs PixiJS 8.x and supports Cubism 2.1 (legacy) and Cubism 3/4/5. It is "a major refactor of pixi-live2d-display-mulmotion". `model.speak('url')` needs `@pixi/sound`, and it supports Filter and RenderTexture via a custom Render Pipe. The npm package is `untitled-pixi-live2d-engine`. The README does not mention Cubism 5.3 blend-mode support — [repo README](https://github.com/Untitled-Story/untitled-pixi-live2d-engine)
- [Untitled-Story/pixi-live2d-display-advanced](https://github.com/Untitled-Story/pixi-live2d-display-advanced): 24 stars, MIT, Pixi v7, last update 2026-08. Maintainers plan Pixi v8 support in v2.0.0 — GitHub search API; [npm](https://npmjs.com/package/pixi-live2d-display-advanced)
- `pixi-live2d-display-mulmotion` is another fork (multi-motion), and it is the upstream of the Untitled engine — [jsDelivr README](https://cdn.jsdelivr.net/npm/pixi-live2d-display-mulmotion@0.5.0-mm-6/README.md)
- [avgjs/pixi-live2d](https://github.com/avgjs/pixi-live2d): 680 stars, ARCHIVED — GitHub search API

**Web widgets (mascot or "kanban" style; low value for clips)**
- [stevenjoezhang/live2d-widget](https://github.com/stevenjoezhang/live2d-widget): 11,032 stars, GPL-3.0, active. [hacxy/l2d-widget](https://github.com/hacxy/l2d-widget): 653 stars, MIT, active ("one function call"). [xiazeyu/live2d-widget.js](https://github.com/xiazeyu/live2d-widget.js) (AGPL-3.0) and [EYHN/hexo-helper-live2d](https://github.com/EYHN/hexo-helper-live2d) are ARCHIVED — GitHub search API

**Python, Rust, Go, Java bindings**
- [EasyLive2D/live2d-py](https://github.com/EasyLive2D/live2d-py): 586 stars, MIT, last push 2026-10-28 (active). "Live2D Library for Python (C++ impl): model loading, lip-sync, basic face rigging, precise click test" — GitHub search API
- [qinyonghang/Live2D-Python (PyLive2D)](https://github.com/qinyonghang/Live2D-Python): 21 stars, Apache-2.0, last push 2026-06-08 — GitHub search API
- [Veykril/cubism-rs](https://github.com/Veykril/cubism-rs): 49 stars, Apache-2.0, last push 2020-01-16 (STALE) — GitHub search API
- [aethiopicuschan/cubism-go](https://github.com/aethiopicuschan/cubism-go): 31 stars, MIT, updated 2026-11 — GitHub search API
- [Eatgrapes/Live2D-JavaBinding](https://github.com/Eatgrapes/Live2D-JavaBinding): 16 stars, MIT — GitHub search API

**Game engines**
- Godot: [MizunagiKB/gd_cubism (GDCubism)](https://github.com/MizunagiKB/gd_cubism): 304 stars, custom license ("other"), last push 2025-04-01 (semi-stale, about 19 months). "Unofficial Live2D Player for Godot Engine". A community build template exists at [SnowOrb/gd_cubism-build-template](https://github.com/SnowOrb/gd_cubism-build-template) — GitHub search API
- Unreal: official SDK only, in beta (see Section 1). No significant open-source Unreal runtime turned up on GitHub; the search "live2d unreal" returned none.
- Unity: [Live2D/CubismUnityComponents](https://github.com/Live2D/CubismUnityComponents) (official, active). [Navi-Studio/Virtual-Human-for-Chatting](https://github.com/Navi-Studio/Virtual-Human-for-Chatting): 708 stars, Unity + Live2D chat character — GitHub search API

**Viewers and extractors**
- Live2DViewerEX is a closed-source viewer and wallpaper app with its own `.lpk` package format. [ihopenot/LpkUnpacker](https://github.com/ihopenot/LpkUnpacker) (300 stars) unpacks `.lpk` files — GitHub search API
- [Perfare/UnityLive2DExtractor](https://github.com/Perfare/UnityLive2DExtractor) (639 stars, MIT) extracts Cubism 3 models from Unity games. [Perfare/AzurLaneLive2DExtract](https://github.com/Perfare/AzurLaneLive2DExtract) is ARCHIVED/obsolete — GitHub search API
- VTube Studio (DenchiSoft) is the de facto commercial Live2D VTubing app. Its model-loading docs are at the [DenchiSoft/VTubeStudio wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Loading-your-own-Models), and its EULA at [denchisoft.com](https://denchisoft.com/wp-content/uploads/2024/04/denchisoft_eula_vts_2024_04_15.pdf).
- nizima LIVE is Live2D Inc.'s own tracking and streaming app — [nizima LIVE download](https://nizimalive.com/en/download/); [change history](https://docs.nizimalive.com/en/manual/history/)

**Tracking and puppeteering (Live2D-compatible, OSS)**
- [erodozer/open-vt](https://github.com/erodozer/open-vt): 328 stars, MIT, last push 2026-10-19, "Open-Source 2D Vtuber software" — GitHub search API
- [yeemachine/kalidoface-2d](https://github.com/yeemachine/kalidoface-2d): 381 stars, custom license, last push 2022-11 (STALE) — GitHub search API
- [vignetteapp/vignette](https://github.com/vignetteapp/vignette): 522 stars, last push 2023-07 (STALE) — GitHub search API
- [adrianiainlam/facial-landmarks-for-cubism](https://github.com/adrianiainlam/facial-landmarks-for-cubism): 75 stars, MIT. Maps OpenSeeFace landmarks to Cubism parameters — GitHub search API
- [mmmmmm44/VTuber-Python-Unity](https://github.com/mmmmmm44/VTuber-Python-Unity): 559 stars, MIT. Python face mocap driving Unity Live2D/3D — GitHub search API

### Inferences
- For stream2clip, the most practical stack is `untitled-pixi-live2d-engine` running in headless Chromium (Puppeteer or Playwright). Render to RenderTexture or canvas, then capture frames. It is the only actively maintained Pixi v8 runtime with lip-sync built in. Fallback: the `lipsyncpatch` fork pinned to Pixi v7.
- `live2d-py` suits a pure-Python pipeline (for example, rendering server-side with OpenGL and piping frames to FFmpeg), which avoids a browser. Verify that it can render offscreen or headless before relying on it.
- Every runtime above still loads Live2D's proprietary Cubism Core (`live2dcubismcore.js` or the native lib), so Section 1's licensing applies no matter which wrapper is used.

### Gaps
- I could not retrieve star, license or last-commit data for RaSan147/pixi-live2d-display (`lipsyncpatch`); the GitHub API was blocked for this repo.
- It is unverified whether any community runtime (Pixi or live2d-py) correctly renders Cubism 5.3 blend modes and offscreen drawing.
- I found no maintained OSS Unreal Live2D plugin. I did not check Korean sources (Naver blogs, Velog) or Japanese Qiita/Zenn articles on runtimes for lack of tool budget.

---

## 3. Open-source alternatives to Live2D (Inochi2D, Spine, PNGTuber tools)

### Takeaway
Inochi2D is still alive but slow-moving. The stable apps are stuck at 0.8.x (2024), and a 0.9 SDK rewrite with a new INP2 format is in progress. Its community fork nijilive/nijigenerate is more active. A wave of new MIT/Apache "Live2D-compatible or alternative" web puppet engines appeared in 2026 (ayagami, iki, livliv player), but they are very young. PNGTuber tools are the simplest fallback for creators without rigged models, and PNGTuber-Remix is the active open-source leader.

### Cited Findings
**Inochi2D and forks**
- [Inochi2D/inochi2d (SDK)](https://github.com/Inochi2D/inochi2d): 1,879 stars, BSD-2-Clause, last push 2026-11-10 (active) — GitHub search API
- [Inochi2D/inochi-creator](https://github.com/Inochi2D/inochi-creator): 1,268 stars, BSD-2-Clause, last push 2025-06-16. [Inochi2D/inochi-session](https://github.com/Inochi2D/inochi-session): 413 stars, BSD-2-Clause, last push 2025-11-08. [Inochi2D/inox2d (Rust)](https://github.com/Inochi2D/inox2d): 304 stars, last push 2026-09-23. Also [inochi-viewer](https://github.com/Inochi2D/inochi-viewer) and [example-models](https://github.com/Inochi2D/example-models) — GitHub search API
- The stable versions are still Creator 0.8.6 (2024-09-18) and Session 0.8.7 (2024-09-19). The 0.9 SDK is in development with deformation and node-graph rework, and puppets move to a new "INP2" format, with 0.8 data still readable — [issoh.co.jp explainer (JA, Oct 2026, secondary)](https://www.issoh.co.jp/md/tech/10294); [Flathub 0.8.x listing](https://flathub.org/pt/apps/com.inochi2d.inochi-creator)
- In Aug 2024 the developers ended free "community copies" and raised Inochi Creator's price to $30 to fund 0.9 — [itch.io devlog](https://kitsunebi-games.itch.io/inochi-creator/devlog/783583/announcing-pricing-change); [Inochi Session on itch](https://kitsunebi-games.itch.io/inochi-session)
- [nijigenerate/nijigenerate](https://github.com/nijigenerate/nijigenerate): 345 stars, BSD-2-Clause, last push 2026-11-17. It is an editor for the "nijilive" puppet format, derived from Inochi2D v0.8. The runtime is [nijigenerate/nijilive](https://github.com/nijigenerate/nijilive) (54 stars), and [nijimi](https://github.com/nijigenerate/nijimi) is a desktop mascot — GitHub search API

**New 2026 open puppet engines (young; verify before use)**
- [AyagamiDev/ayagami](https://github.com/AyagamiDev/ayagami): 395 stars, Apache-2.0, created 2026-07-11, "2D puppet model renderer compatible with Live2D" — GitHub search API
- [zeikar/iki](https://github.com/zeikar/iki): 47 stars, MIT, created 2026-06-04. "The open Live2D alternative that AI can build — a free, MIT-licensed 2D puppet engine for the web, with an open .iki format, an AI auto-rig..." — GitHub search API
- [livliv-dev/player](https://github.com/livliv-dev/player): 1,584 stars, Apache-2.0, created 2026-11-04 (two weeks old). "A lightweight 2.5D character player for the web, with lip sync and webcam face tracking." Its sibling [livliv-dev/stage](https://github.com/livliv-dev/stage) (69 stars) is an "AI VTuber Studio" — GitHub search API
- [MangoLion/stretchystudio](https://github.com/MangoLion/stretchystudio): 534 stars, MIT, last push 2026-04-28. "FOSS 2D animation tool for turning static illustrations into mesh-deformable characters" — GitHub search API
- [852wa/Anime2.5DRig](https://github.com/852wa/Anime2.5DRig): 420 stars, MIT, last push 2026-09-23. It builds VTuber-style avatars from layered PSDs and is listed by See-through as a downstream tool — GitHub search API; [See-through README](https://github.com/shitagaki-lab/see-through)
- [HRuiCcc/RuiC-2D](https://github.com/HRuiCcc/RuiC-2D): 270 stars, MIT, created 2026-11-06. A local 2D avatar editor that builds an avatar from a single image: layer binding, mesh deformation, mouth and blink, timeline, MediaPipe driving, OBS output — GitHub search API

**Spine-based VTubing**
- [EsotericSoftware/spine-runtimes](https://github.com/EsotericSoftware/spine-runtimes): 5,368 stars, custom Spine Runtimes license, active — GitHub search API
- "Spine VTuber Prototype" by SilverStraw is a community app, not an official Esoteric release, distributed on itch.io. v2.0.9 updated it to the Spine 4.2.61 WebGL runtime. It needs a webcam and specific animations (idle, breathe, face_roll_left and others), and v2.0.4 added hand tracking. Each user must own a Spine Editor license — [itch.io page](https://silverstraw.itch.io/spine-vtuber-prototype); [Esoteric forum thread](https://en.esotericsoftware.com/forum/d/16925-spine-pro-vtuber-working-prototype?page=7); [test model](https://silverstraw.itch.io/spine-vtube-test-model)

**PNGTuber tools**
- [MudkipWorld/PNGTuber-Remix](https://github.com/MudkipWorld/PNGTuber-Remix): 419 stars, custom license, last push 2026-11-10 (active) — GitHub search API
- [kaiakairos/PNGTuber-Plus](https://github.com/kaiakairos/PNGTuber-Plus): 192 stars, Unlicense, last push 2024-08-02 (STALE; Godot source) — GitHub search API
- [Gemmstone/PyNGtuber](https://github.com/Gemmstone/PyNGtuber): 139 stars, GPL-3.0, active (Python + HTML) — GitHub search API
- [rotejin/MotionPNGTuber](https://github.com/rotejin/MotionPNGTuber): 338 stars, MIT. "More than PNGTuber, less than Live2D": real-time mouth-flap using video loops for hair sway. [rotejin/MotionPNGTuber_Player](https://github.com/rotejin/MotionPNGTuber_Player): 113 stars, MIT, a browser lip-sync player with no Python. [rotejin/PuruPuruPNGTuber](https://github.com/rotejin/PuruPuruPNGTuber): 145 stars, adds bangs and back hair to expression-variant PNGs — GitHub search API
- Discord Reactive Images (fugi) exists; a compatibility shim is at [HollowedBlood/vesktop-fugi-rpc](https://github.com/HollowedBlood/vesktop-fugi-rpc) — GitHub search API

### Inferences
- For stream2clip, a "PNGTuber mode" (static PNG + mouth-open/closed swap + bounce driven by audio RMS) is the cheapest fallback avatar and has no licensing risk. MotionPNGTuber_Player's browser approach is a good reference.
- Inochi2D and nijilive are the only mature open formats with editors. Supporting `.inp` as a secondary avatar format avoids Live2D licensing entirely, but few VTubers actually use it.
- Treat the 2026 newcomers (ayagami, iki, livliv) as watch-list items. They are weeks to months old, and high star counts on very young repos are not proof of maturity.

### Gaps
- I did not verify current details for veadotube (veado.tube; proprietary, by olmewe) or Discord Reactive Images (fugi.tech): license, price, OSS status. They are not listed with facts for that reason.
- I could not confirm the Spine VTuber Prototype's price or whether it is still maintained in late 2026.
- I did not verify the Inochi2D 0.9 release timeline from a primary source (devlog or GitHub releases); the explainer is secondary.

---

## 4. AI-assisted Live2D: layer decomposition, auto-rigging, motion generation, LLM-driven characters

### Takeaway
The biggest 2026 development is See-through (SIGGRAPH 2026, Apache-2.0, about 5.8k stars). It splits a single anime illustration into up to 23 inpainted, depth-ordered layers and exports PSD. It has spawned a toolchain of PSD-to-rig tools (psd2live, which exports `.moc3`/`.cmo3` without Cubism Editor; StretchyStudio; Anime2.5DRig; image2live2d). The LLM-driven Live2D character space is dominated by AIRI (about 51.5k stars) and Open-LLM-VTuber (about 14.8k stars, v1 now in maintenance).

### Cited Findings
**Layer decomposition and segmentation**
- [shitagaki-lab/see-through](https://github.com/shitagaki-lab/see-through): 5,757 stars, Apache-2.0 (code), created 2026-03-31, last push 2026-11-14 — GitHub search API
- Paper: "See-through: Single-image Layer Decomposition for Anime Characters" by Jian Lin, Chengze Li, Haoyun Qin, Kwun Wang Chan, Yanghua Jin, Hanyuan Liu, Stephen Chun Wang Choy and Xueting Liu. ACM SIGGRAPH 2026 Conference Papers, [arXiv 2602.03749](https://arxiv.org/abs/2602.03749) — [repo README](https://github.com/shitagaki-lab/see-through)
- From one illustration it produces up to 23 "fully inpainted, semantically distinct layers with inferred drawing orders" (hair, face, eyes, clothing, accessories). It uses a fine-tuned Marigold for pseudo-depth and "LayerDiff 3D" (SDXL-based) for transparent layers. It writes a PSD with `--save_to_psd`. It needs about 12–16 GB VRAM at 1280 px in bf16, about 10 GB with group offload, and about 8 GB with NF4 or block-swap. Weight license not stated separately — [repo README](https://github.com/shitagaki-lab/see-through)
- The authors say it does not do rigging ("We don't think so — at least, not yet"). They call it a "useful starting point" for Live2D artists. A related CubismPartExtr repo prepares data for a Live2D parsing model — [repo README](https://github.com/shitagaki-lab/see-through)
- [jtydhr88/ComfyUI-See-through](https://github.com/jtydhr88/ComfyUI-See-through): 942 stars, no license detected, last push 2026-08-20. ComfyUI nodes with in-browser PSD export — GitHub search API; [See-through README](https://github.com/shitagaki-lab/see-through)
- [CartoonSegmentation/CartoonSegmentation](https://github.com/CartoonSegmentation/CartoonSegmentation): 204 stars, no license detected, last push 2025-04-29. Instance segmentation for anime characters — GitHub search API
- [mattyamonaca/layerdivider](https://github.com/mattyamonaca/layerdivider): 815 stars, MIT, last push 2023-08-30 (STALE). Divides an illustration into a layered structure — GitHub search API

**Auto-rigging, PSD to Live2D**
- [tsunehimatoi/psd2live](https://github.com/tsunehimatoi/psd2live): 1,124 stars, GPL-3.0 (app; format libraries and Rust runtime are MIT), created 2026-09-03, active. It turns layered PSDs into rigged models: adaptive meshes, head and body deformer chain, facial parameters, idle/blink/nod/head-shake motions, hair and cloth physics, FK/IK baked into native deformers. It exports `.moc3`/`.cmo3` (Cubism 3.0–5.3) "without Cubism Editor or the official SDK", and has an MCP server for coding agents. It states no affiliation with Live2D Inc. and says it ships no proprietary SDK components. Its own docs say agent tool access "does not mean complex modeling tasks are reliable" — [psd2live README](https://github.com/tsunehimatoi/psd2live)
- [Wzhang3912/image2live2d](https://github.com/Wzhang3912/image2live2d): 51 stars, Apache-2.0. Converts separated layers into a riggable puppet (nijilive `.inp` plus Live2D `.moc3`) — GitHub search API
- [rig-c/parts](https://github.com/rig-c/parts): 15 stars, MIT. Builds See-through layers into rig-ready PNGs plus a weighted-mesh rig spec — GitHub search API
- StretchyStudio, Anime2.5DRig and PNGAL are listed by See-through as downstream community tools for auto-rigging, VTuber avatars and sprite-sheet export — [See-through README](https://github.com/shitagaki-lab/see-through); repos in Section 3
- [shinshin86/live2d-add-motion-sample-web-ui](https://github.com/shinshin86/live2d-add-motion-sample-web-ui): 298 stars, MIT, created 2026-07. Adds new motions to a Live2D model "by editing JSON only, without Cubism Editor", through a browser UI, with docs written for AI coding agents — GitHub search API
- Official: a Live2D page says Editor "AI features" auto-generate deformers and swaying motions. The version (likely 5.1) is not confirmed; see Section 1 — [live2d.com ?p=7392](https://www.live2d.com/en/?p=7392)

**Single-image neural animation (non-Live2D alternative)**
- Talking Head Anime by pkhungurn: [THA demo](https://github.com/pkhungurn/talking-head-anime-demo) (2,028 stars), [THA2](https://github.com/pkhungurn/talking-head-anime-2-demo) (1,154), [THA3](https://github.com/pkhungurn/talking-head-anime-3-demo) (1,050), [THA4 demo](https://github.com/pkhungurn/talking-head-anime-4-demo) (360). All MIT; THA4 last push 2026-11 — GitHub search API
- [yuyuyzl/EasyVtuber](https://github.com/yuyuyzl/EasyVtuber): 3,077 stars, MIT, last push 2026-02. Built on THA3, "works like VTube Studio" — GitHub search API

**LLM-driven Live2D characters**
- [moeru-ai/airi](https://github.com/moeru-ai/airi): 51,530 stars, MIT, last push 2026-11-18 (very active). A self-hosted companion and "Neuro-sama"-style project that supports Live2D — GitHub search API
- [Open-LLM-VTuber/Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber): 14,757 stars, custom license on GitHub, last push 2026-05-15. Bundled Live2D sample models "are not covered by the MIT license of this project" and fall under Live2D's Free Material License. v2.0, a full rewrite, is in "early discussion and planning". Maintainers ask for no new v1 feature requests or PRs and will only fix v1 bugs — [repo README](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)
- [kimjammer/Neuro](https://github.com/kimjammer/Neuro): 2,125 stars, MIT, last push 2025-01-17 (STALE). Neuro-sama recreation — GitHub search API
- [elevenyellow/handcrafted-persona-engine](https://github.com/elevenyellow/handcrafted-persona-engine): 1,402 stars, no license detected, last push 2026-05-20. Live2D plus LLM, ASR, TTS and RVC for VTubing — GitHub search API
- [Project-N-E-K-O/N.E.K.O](https://github.com/Project-N-E-K-O/N.E.K.O): 3,261 stars, Apache-2.0. [morettt/my-neuro](https://github.com/morettt/my-neuro): 1,459 stars, MIT. [v3ucn/live2d-TTS-LLM-GPT-SoVITS-Vtuber](https://github.com/v3ucn/live2d-TTS-LLM-GPT-SoVITS-Vtuber): 283 stars. [wan-h/awesome-digital-human-live2d](https://github.com/wan-h/awesome-digital-human-live2d): 2,442 stars, MIT. [zeekk0/OpenAmika](https://github.com/zeekk0/OpenAmika): 674 stars — GitHub search API
- AITuberKit publishes a dedicated license page, a sign that it uses a non-plain-OSS license — [AITuberKit license docs](https://docs.aituberkit.com/en/guide/license)

### Inferences
- For stream2clip, the most reusable AI piece is See-through, used as an optional "no model available" path: VTuber key art → layered PSD → simple 2.5D rig (Anime2.5DRig or a PNGTuber-style rig) → short clip. psd2live is the most ambitious route to a real `.moc3`, but it is GPL-3.0 (copyleft affects distribution) and two months old. Third-party `.moc3` writers may also raise legal or EULA questions with Live2D. Its README disclaims affiliation but does not say how the format was implemented.
- AIRI and Open-LLM-VTuber are the best references for the "audio → Live2D lip-sync + expression" runtime path in the browser: their frontends solve model loading, `speak()`-style lip sync and expression triggering. Open-LLM-VTuber v1 is frozen, so treat its code as reference only.
- A clip tool will meet many repos that redistribute Live2D sample models under non-MIT terms. Keep sample models out of the stream2clip repo.

### Gaps
- I found no peer-reviewed paper (2025–2026) that generates Live2D parameter curves (motion3) from audio or text end-to-end. The arXiv search was not completed within the tool budget, so this remains open.
- The See-through weight license is not stated separately from the Apache-2.0 code license.
- I did not verify whether psd2live's `.moc3` writer is reverse-engineered or what Live2D's position on it is.
- I did not check Ikaros-521/AI-Vtuber (a formerly popular Chinese AI VTuber repo); GitHub search returned nothing, so it may be renamed, deleted or private.

---

## 5. Lip-sync and motion from recorded audio; exporting Live2D animation to video with alpha

### Takeaway
For offline clip rendering, the main options are: (a) amplitude/RMS → `ParamMouthOpenY`, which is built into the Pixi forks' `speak()` and live2d-py; (b) MFCC vowel classification (A/I/U/E/O) via uLipSync/wLipSync, or Live2D's official MotionSync plugin; (c) Rhubarb Lip Sync's offline phoneme-to-mouth-shape timeline. Cubism Editor's own video export uses straight alpha with known H.264 translucency problems, so the reliable route to alpha video is to render PNG frames from a runtime and encode them with FFmpeg to ProRes 4444 or VP9 WebM.

### Cited Findings
- [DanielSWolf/rhubarb-lip-sync](https://github.com/DanielSWolf/rhubarb-lip-sync): 2,781 stars, custom license, last push 2026-06-16. A command-line tool that "automatically creates 2D mouth animation from voice recordings" — GitHub search API
- [hecomi/uLipSync](https://github.com/hecomi/uLipSync): 1,717 stars, MIT, last push 2026-01-06. MFCC-based lip sync for Unity (Job System and Burst) — GitHub search API
- [mrxz/wLipSync](https://github.com/mrxz/wLipSync): 86 stars, MIT, last push 2026-08-06. "MFCC-based lip-sync library using WASM and WebAudio based on uLipSync" — GitHub search API
- Live2D MotionSync: Editor 5.0 generates mouth movement from voice and can bake it to timeline keyframes. The Web plugin needs the separately distributed MotionSync Core — [5.0 New Features](https://docs.live2d.com/en/cubism-editor-manual/new-function5-0/); [CubismWebMotionSyncComponents](https://github.com/Live2D/CubismWebMotionSyncComponents)
- [liyao1520/live2d-motionSync](https://github.com/liyao1520/live2d-motionSync): 101 stars, MIT, last push 2026-09-18. A community "live2d motionsync lib", also on npm as [live2d-motionsync](https://npmjs.com/package/live2d-motionsync) — GitHub search API
- Pixi runtimes: `lipsyncpatch` `model.speak(audio, {...})` (Pixi v7) — [npm](https://npmjs.com/package/pixi-live2d-display-lipsyncpatch). Untitled engine `model.speak(url)` with `@pixi/sound` (Pixi v8) — [repo](https://github.com/Untitled-Story/untitled-pixi-live2d-engine)
- live2d-py lists lip-sync among its features — [EasyLive2D/live2d-py](https://github.com/EasyLive2D/live2d-py)
- [adrianiainlam/mouse-tracker-for-cubism](https://github.com/adrianiainlam/mouse-tracker-for-cubism): 15 stars, MIT. Turns mouse position and microphone input into Cubism SDK parameters — GitHub search API
- Cubism Editor video export: "Cubism's video export is a straight output of an image with alpha due to its specifications". H.264 exports can show translucency wrongly in media players, and the transparent-background option is documented for GIF — [Live2D docs: Image and Video Export](https://docs.live2d.com/en/cubism-editor-manual/exporting-images). Users have reported jagged "saw-teeth" edges on transparent exports, and staff said the output matched spec (Cubism 4.x era) — [Live2D community thread](https://community.live2d.com/discussion/comment/3030)
- Cubism 5.3 adds WebM video output — [SDK support for 5.3 new features](https://docs.live2d.com/en/cubism-sdk-manual/cubism-5-3-new-functions/) (from a search summary; not verified directly)
- The standard FFmpeg/Remotion recipe for transparent video is a PNG sequence encoded as ProRes 4444 with `--pixel-format=yuva444p10le --codec=prores --prores-profile=4444` — [Remotion: transparent videos](https://www.remotion.dev/docs/transparent-videos)
- Open puppet players with built-in lip sync: [livliv-dev/player](https://github.com/livliv-dev/player) (Apache-2.0) and [rotejin/MotionPNGTuber_Player](https://github.com/rotejin/MotionPNGTuber_Player) (MIT) — GitHub search API

### Inferences
- Recommended offline pipeline for stream2clip:
  1. Separate the streamer's voice from game audio, if mixed, using a source-separation tool (covered elsewhere).
  2. Compute per-frame mouth parameters. RMS → `ParamMouthOpenY` is simple and robust. wLipSync/uLipSync-style MFCC vowel weights → `ParamA/I/U/E/O` or `ParamMouthForm` look better. Rhubarb gives discrete visemes for PNGTuber mode.
  3. Write the result as a `.motion3.json` curve, or drive parameters frame by frame in a deterministic headless renderer (Pixi v8 engine in Puppeteer, or live2d-py).
  4. Capture RGBA frames and encode to ProRes 4444 or VP9-alpha WebM for compositing over the clip.
- Do not use real-time `speak()` (Web Audio playback) for offline rendering, because it ties lip sync to wall-clock time. Precompute parameter tracks and step the model's update loop with a fixed delta-time per frame.
- Because Cubism's built-in export uses straight alpha, convert to premultiplied alpha, or composite carefully in FFmpeg, if Editor-exported clips are ever used.

### Gaps
- I did not verify whether the official Cubism SDK for Web samples include a WAV-file RMS lip-sync helper usable offline.
- I did not confirm whether Cubism 5.3's WebM export carries an alpha channel.
- I found no open-source tool dedicated to "Live2D model + audio file → transparent video" as a single CLI. stream2clip would likely build this itself, which is a gap in the ecosystem and possibly a differentiator.

---

## 6. Model marketplaces and free sample models: usage terms for demos and redistribution

### Takeaway
Live2D's official sample models are usable commercially only by individuals and small businesses (under 10M JPY in sales), under the Free Material License Agreement plus per-character terms. Live2D can object to sexual, violent or image-damaging uses. Marketplace (nizima, BOOTH) models are governed by each listing's own terms, which commonly prohibit redistribution. Large "Live2D model collection" GitHub repos have no license and often contain extracted game assets, so they are unsafe for a public repo or demos.

### Cited Findings
- Live2D sample models require agreeing to the Free Material License Agreement and each character's terms. "Live2D Original Character" materials may be used commercially and non-commercially by general users and small enterprises with annual sales under 10M JPY. Non-profits such as schools may use them non-commercially. Live2D may object to sexual, violent or grotesque use, or use that harms the character's image — [Live2D Help ?p=2546](https://help.live2d.com/en/?p=2546); [Free Material License Agreement](https://www.live2d.com/eula/live2d-free-material-license-agreement_en.html); [Terms of Use for Live2D Cubism Sample Data](https://www.live2d.com/en/learn/sample/model-terms/); [sample-model terms EULA page](https://www.live2d.com/eula/live2d-sample-model-terms_en.html)
- nizima LIVE sample models require both the Sample Model Terms of Use and the nizima LIVE Software License Agreement. For middle and large enterprises, use is limited to internal or supervision purposes. Some samples are restricted for streaming. The Japanese license agreement (ver. 1.6) bars modifying or redistributing sample materials unless explicitly permitted, and bars extracting them for use outside the software. Third-party characters (such as Sony's RAYNOS-chan) carry extra EULAs. The terms version found is dated 2026-06-03 — [nizima LIVE Sample Model Terms](https://docs.nizimalive.com/en/manual/samplemodel-terms/); [nizima LIVE Software License Agreement (JA)](https://live2d.com/eula/nizimalive-software-license-agreement_jp.html)
- Models sold on nizima are governed by the terms on each item's page — [nizima LIVE Sample Model Terms](https://docs.nizimalive.com/en/manual/samplemodel-terms/); [nizima selling guide](https://docs.nizima.com/en/?p=10033)
- BOOTH sells many premade VTuber Live2D models (for example [item 5353270](https://booth.pm/ja/items/5353270) and [item 7053100](https://booth.pm/en/items/7053100)), each with seller-defined terms.
- Open-LLM-VTuber warns that its bundled Live2D samples are not MIT and that medium or large enterprises "may be subject to additional licensing requirements" — [Open-LLM-VTuber README](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)
- [Eikanya/Live2d-model](https://github.com/Eikanya/Live2d-model) (3,533 stars), [imuncle/live2d](https://github.com/imuncle/live2d) (1,183 stars) and [xiazeyu/live2d-widget-models](https://github.com/xiazeyu/live2d-widget-models) (ARCHIVED) are model collections with no or GPL license detected — GitHub search API
- Inochi2D ships open example models at [Inochi2D/example-models](https://github.com/Inochi2D/example-models), with no license detected by GitHub — GitHub search API

### Inferences
- For stream2clip demos and tests: do not commit Live2D sample models to the repo. Download them at setup time from Live2D's site, after the user accepts the terms, or use the user's own model. A small company may show samples in demo videos, but redistribution inside an OSS repo is restricted.
- The safest bundled demo avatar is a self-made PNGTuber or 2.5D rig from original or CC0 art, or an Inochi2D or nijilive example model once its license is confirmed.
- Real VTuber clients will bring commissioned models. Their commission terms (artist and rigger) may restrict use outside streaming, such as in shorts or ads. Stream2clip's terms should leave that responsibility with the user.

### Gaps
- I did not read the full text of the Free Material License Agreement (redistribution clauses, Section 9.2 translation note).
- I found no general nizima marketplace buyer terms, only sample-model terms and the item-level rule. BOOTH platform rules on model licensing were not checked.
- Inochi2D example-models license is unknown; GitHub detected none.

---

## 7. What is most reusable for stream2clip

### Takeaway
Top picks: (1) `untitled-pixi-live2d-engine` (MIT, Pixi v8, Cubism 2–5, RenderTexture, lip-sync) in headless Chromium for deterministic RGBA frame rendering; (2) `live2d-py` (MIT) for a browser-free Python path; (3) wLipSync/uLipSync MFCC or a simple RMS mapping for audio → mouth parameters, with Rhubarb for PNGTuber visemes; (4) See-through (Apache-2.0) as an optional AI path from key art to layers; (5) the AIRI and Open-LLM-VTuber frontends as reference code. Every Live2D path requires respecting the Cubism Core proprietary license and the Expandable Application rule.

### Cited Findings
- untitled-pixi-live2d-engine: PixiJS 8.x, Cubism 2.1–5, `speak()`, Filter and RenderTexture support, MIT, active Nov 2026 — [repo](https://github.com/Untitled-Story/untitled-pixi-live2d-engine)
- live2d-py: MIT, C++ implementation, lip-sync, last push 2026-10-28 — [repo](https://github.com/EasyLive2D/live2d-py)
- wLipSync (MIT, WASM/WebAudio) and uLipSync (MIT, Unity) do MFCC lip sync — [wLipSync](https://github.com/mrxz/wLipSync); [uLipSync](https://github.com/hecomi/uLipSync)
- Rhubarb Lip Sync builds 2D mouth animation from recordings — [repo](https://github.com/DanielSWolf/rhubarb-lip-sync)
- See-through decomposes one image into up to 23 PSD layers, Apache-2.0, needs 8–16 GB VRAM — [repo](https://github.com/shitagaki-lab/see-through)
- Expandable Applications (VTuber tracking software) need review and a special agreement even for small entities — [Live2D SDK license](https://www.live2d.com/en/sdk/license/)
- ProRes 4444 alpha encoding recipe — [Remotion docs](https://www.remotion.dev/docs/transparent-videos)

### Inferences
- Priority tiers for stream2clip:
  - **Use now:** untitled-pixi-live2d-engine; live2d-py; wLipSync (port its MFCC logic offline in Node or Python) or an RMS mapper; Rhubarb; FFmpeg ProRes 4444/VP9-alpha.
  - **Reference only:** AIRI and Open-LLM-VTuber frontends; Live2D CubismWebSamples (official model-loading patterns); shinshin86's motion3 JSON editor (programmatic motion authoring); MotionPNGTuber_Player (PNGTuber mode).
  - **Optional AI features:** See-through, then Anime2.5DRig or StretchyStudio, for creators without Live2D models; Talking Head Anime 4 / EasyVtuber (MIT) as a neural single-image fallback.
  - **Watch list (young or uncertain):** psd2live (GPL-3.0, third-party `.moc3` writer), ayagami, iki, livliv player, nijilive and Inochi2D 0.9.
  - **Avoid or stale:** guansss/pixi-live2d-display (unmaintained base), avgjs/pixi-live2d (archived), kalidoface-2d, vignette, layerdivider, kimjammer/Neuro, model-collection repos with no license.
- Architecture hint: keep the "avatar renderer" behind an interface with modes such as `live2d` (Cubism Core via Pixi or live2d-py), `inochi`/`nijilive`, `pngtuber` and `image-2.5d`, all driven by the same precomputed parameter tracks (mouth open, vowels, blink, head angle). Licensing then stays isolated to the Live2D backend.

### Gaps
- Headless or offscreen rendering for both untitled-pixi-live2d-engine and live2d-py was not tested in this session; it is plausible but unverified.
- I did not survey Korean community sources (Naver Cafe, Velog), or Japanese Qiita/Zenn articles beyond one Inochi2D explainer, for lack of tool budget.
