# VTuber Rendering: Real-time Output, Offline Re-rendering, and AI Avatar Animation (reference for stream2clip)

Scope: software that takes a VTuber avatar (2D/3D) plus motion/tracking/audio data and renders it to video, live or offline, plus single-image avatar generation. Model-format details (Live2D internals, VRM spec) are covered by other researchers.

Methodology note: GitHub stars / last-push dates were pulled on 2026-11-18 from the ungh.cc GitHub mirror API (e.g. [ungh.cc/repos/pixiv/three-vrm](https://ungh.cc/repos/pixiv/three-vrm)), and license types were read from each repo's LICENSE file on raw.githubusercontent.com. The direct GitHub API was blocked in this session, so the "archived" flag could not be checked. "Stale" below means no push for more than 18 months. Star counts are approximate.

## 1. Real-time VTuber apps and their rendering/output paths (transparency, open-source status)

### Takeaway
On Windows, the standard way to get the avatar out with alpha is **Spout2**: VTube Studio, Warudo, VSeeFace, VNyan, Animaze, PrprLive and EasyVtuber all send it. **NDI** is the cross-platform alternative with alpha (VTube Studio documents it on Windows and macOS). Virtual webcams generally lose alpha. Among the apps you named, only VMagicMirror (MIT), Inochi Session (BSD-2) and the older Kalidoface 3D (MIT, stale) are open source. VTube Studio, VSeeFace, Warudo, VNyan, Animaze, nizima LIVE, PrprLive, 3tene and Webcam Motion Capture are closed source, which matters if stream2clip wants to re-render. For stream2clip, the easiest wins are capturing a clean alpha layer during the stream (Spout2/NDI into OBS) and using the apps' built-in motion recorders (VTS, Warudo).

### Cited Findings
**VTube Studio (Live2D; Windows/macOS/iOS/Android; proprietary app; its API repo is MIT)**
- The official VTS wiki lists these OBS output paths: **Spout2** (Windows only), which "supports transparency (no green-screen needed)" with "almost no CPU usage" (set OBS Composite mode to Premultiplied Alpha and use a transparent black VTS background); **NDI** (Windows and macOS), with transparency and "very good" quality, but "CPU utilization of VTS may increase" and it "may not be very performant" on macOS, and multiple VTS instances show up as separate sources; a **Virtual Webcam**, transparent only with "Transparent in OBS" enabled and limited to one stream; and **Game Capture** with "Transparent in capture" (Windows). The wiki says "You should never use green-screen." — [VTS wiki: Recording/Streaming with OBS](https://github.com/DenchiSoft/VTubeStudio/wiki/Recording-Streaming-with-OBS)
- VTS includes **"Record Live2D Animation"** (camera settings, all platforms including mobile). It records parameter values over time and saves `<name>.motion3.json`, which can be replayed in VTS or imported into Cubism Animator. "VTube Studio animations are always exported as 60-FPS-based curves," and physics parameters set by an animation are ignored on VTS playback. — [VTS wiki: Record Animations](https://github.com/DenchiSoft/VTubeStudio/wiki/Record-Animations)
- VTS API development repo: [DenchiSoft/VTubeStudio](https://github.com/DenchiSoft/VTubeStudio), MIT, about 1,333 stars, pushed 2026-11-09 (active).

**VSeeFace (VRM/VSFAvatar; Windows; freeware, closed source)**
- Has a "Transparent Background" toggle in General Settings and works as a Spout2 source — [PRISM guide: Spout2 in VTuber software](https://guide.prismlive.com/desktop/guides/sources/spout2-capture-source/setting-spout2-in-vtuber-software)
- Listed as a VMC Protocol **Performer** (sender) — [VMC Protocol spec](https://protocol.vmc.info/english.html). It can also act as a VMC receiver: "General Settings > OSC/VMC receiver (disables tracking)" — [VRMPlaybackClient README](https://github.com/kevinjycui/VRMPlaybackClient)
- The SDK for exporting the VSFAvatar format is at [emilianavt/VSeeFaceSDK](https://github.com/emilianavt/VSeeFaceSDK) (about 199 stars, no LICENSE file at the repo root, pushed 2026-07). Its tracking backend, [OpenSeeFace](https://github.com/emilianavt/OpenSeeFace), is BSD-2-Clause (about 2,116 stars, pushed 2026-09) and does "robust realtime face and facial landmark tracking on CPU with Unity integration."

**Warudo (3D/VRM; Windows; free on Steam, closed source)**
- Spout2 output is turned on through a "Spout Output" setting — [PRISM guide](https://guide.prismlive.com/desktop/guides/sources/spout2-capture-source/setting-spout2-in-vtuber-software)
- **Motion Recorder**: "allows you to record the character's animation and output an animation file" in **FBX** (skeleton + blendshapes; "FBX exporting is experimental"), **BVH** (skeleton only) or **WANIM** (skeleton + blendshapes + triggered expressions; "If you only need to playback the animation in Warudo, this is the recommended format"). You pick a target frame rate, and a separate Motion Player handles playback. — [Warudo docs: Motion Recorder](https://docs.warudo.app/docs/assets/motion-recorder)
- Receives VMC protocol — [Warudo docs: VMC](https://docs.warudo.app/docs/mocap/vmc)

**VNyan (3D/VRM; Windows; free, closed source)**
- Listed with VTS, Warudo and VSeeFace among apps that send transparent Spout2 output — [VDO.Ninja: how to stream transparent video](https://docs.vdo.ninja/guides/how-to-stream-transparent-video)
- Also has a built-in **Spout2 receiver prop** for showing an OBS or other Spout feed inside the 3D scene, and supports NDI the same way — [VTuberLabs: VNyan Adding OBS in Worlds](https://lunazera.pages.gay/VTuberLabs/VNyan/How-To's/Adding-OBS-In-Worlds)

**VMagicMirror (VRM; Windows; open source)**
- [malaybaku/VMagicMirror](https://github.com/malaybaku/VMagicMirror): MIT, about 549 stars, pushed 2026-11-18 (very active). "VRM Software for Windows to move avatar with minimal devices."

**Virtual Motion Capture / VMC (VRM; Windows; open source, with a paid build)**
- [sh-akira/VirtualMotionCapture](https://github.com/sh-akira/VirtualMotionCapture): MIT, about 829 stars, pushed 2026-10. This is where the VMC Protocol came from. vmc2bvh requires "the paid version of VirtualMotionCapture" — [vmc2bvh README](https://github.com/infosia/vmc2bvh)

**Animaze (2D/3D; Windows; proprietary, freemium)**
- The official manual has an "Alpha Transparency w/ OBS Spout2 Plugin (recommended)" page — [Animaze manual: Spout](https://www.animaze.us/manual/streaming-transparency/spout) — and a VMC protocol guide — [Animaze VMC guide](https://www.animaze.us/manual/vmc-guide)

**nizima LIVE (Live2D; by Live2D Inc.; proprietary)**
- Provides a free OBS plug-in that outputs the model with a transparent background ("Background settings" > "Transparent background"). The plug-in installer is on the download page. — [nizima LIVE docs: Link with streaming software](https://docs.nizimalive.com/en/tutorials/how-to-link-with-obs/)

**PrprLive (Live2D; Windows; proprietary)**
- Per a forum post, its own OBS plug-ins are built on Spout, and you should remove the bundled plug-ins before using the generic Spout2 OBS plug-in because they interfere — [itch.io post](https://itch.io/post/11519995) (community source, not official)

**Inochi Session (Inochi2D; Windows/macOS/Linux; open source)**
- [Inochi2D/inochi-session](https://github.com/Inochi2D/inochi-session): BSD-2-Clause, about 412 stars, pushed 2025-11. The README says it is "currently under heavy development and isn't ready for production just yet." — [README](https://github.com/Inochi2D/inochi-session)
- Available for Windows, macOS and Linux. On Linux it uses a transparent framebuffer, so OBS XComposite window capture keeps transparency. — [itch.io page](https://kitsunebi-games.itch.io/inochi-session)
- Companion rigging app: [Inochi2D/inochi-creator](https://github.com/Inochi2D/inochi-creator), BSD-2, about 1,267 stars, pushed 2025-06.

**Kalidoface (web)**
- The open-source version is [yeemachine/kalidoface-3d](https://github.com/yeemachine/kalidoface-3d): MIT, about 550 stars, **last push 2022-11 (stale)**. "Face and Body Tracking for VRM 3D models on the web."

**EasyVtuber (AI-rendered "VTuber" from one image; Windows/NVIDIA; open source)**
- [yuyuyzl/EasyVtuber](https://github.com/yuyuyzl/EasyVtuber): MIT, about 3,077 stars, pushed 2026-02. Built on THA3 and has added **THA4** support. Outputs: **Spout2 with a native alpha channel** (the recommended path, tested on OBS 31.0.0, with Premultiplied Alpha composite), or the OBS Virtual Camera without alpha. The older RGBA virtual camera trick (StreamFX shader with `--alpha_split`) is marked outdated because the plugin went paid. Other features: waifu2x / Real-ESRGAN / Anime4K upscaling, RIFE frame interpolation (which causes edge jitter in the Spout2 alpha), TensorRT-RTX acceleration, and direct iFacialMocap UDP input at up to 60 fps. — [EasyVtuber README](https://github.com/yuyuyzl/EasyVtuber)

**Transport plumbing**
- Spout2: "A video frame sharing system for Microsoft Windows," [leadedge/Spout2](https://github.com/leadedge/Spout2), BSD-2, about 1,015 stars, active (2026-10). OBS receiver plug-in: [Off-World-Live/obs-spout2-plugin](https://github.com/Off-World-Live/obs-spout2-plugin/releases), as referenced by [EasyVtuber README](https://github.com/yuyuyzl/EasyVtuber)
- NDI in OBS: [DistroAV/DistroAV](https://github.com/DistroAV/DistroAV) ("formerly OBS-NDI"), GPL, about 4,627 stars, active (2026-11)
- Unity send-side plug-ins: [keijiro/KlakSpout](https://github.com/keijiro/KlakSpout) (public domain/Unlicense, about 829 stars) and [keijiro/KlakNDI](https://github.com/keijiro/KlakNDI) (about 923 stars; the NDI SDK license applies, see `libndi_licenses.txt`)
- Caveat: the OBS virtual camera outputs the composed scene, not an alpha overlay — [veado.tube docs](https://veado.tube/help/mini/obs) (about veadotube, but the same OBS behavior)

### Inferences
- Windows Spout2 with alpha is effectively universal across VTuber apps. stream2clip can ask streamers to add an extra OBS source or a separate recording of just the avatar layer (Spout2/NDI to OBS, e.g. a "source record" or a second recording track). That gives a transparent avatar plate that can be re-composited into 9:16 without re-rendering. It is the cheapest form of "re-rendering."
- Because the major apps are closed source, true re-rendering from a different camera angle or aspect ratio means capturing **data** (motion3.json, WANIM/BVH/FBX, VMC packets) and rendering it again in an engine stream2clip controls (Q2 and Q6).
- VMagicMirror and VirtualMotionCapture are the only actively maintained open-source 3D VTuber apps found. Inochi Session is open but still pre-production.

### Gaps
- No official source found for the output options of **3tene** or **Webcam Motion Capture** (Spout2, virtual camera, alpha). Searches returned nothing relevant.
- Not confirmed: whether Warudo or VNyan also offer NDI output natively, and VSeeFace's and VNyan's exact license or EULA terms (described as freeware from background knowledge, not verified here).
- No pricing or licensing pages were verified for VTS, Warudo Pro, Animaze or nizima LIVE.
- Not verified whether Inochi Session currently ships Spout2/Syphon output on Windows/macOS.

## 2. Offline/batch rendering from recorded tracking data or audio

### Takeaway
No turnkey open-source tool takes "recorded VTuber tracking file in, transparent vertical MP4 out." The pieces exist, though. **Recorders** include VTS motion3.json, Warudo FBX/BVH/WANIM, VMC packet dumps (MotionReplay, VRMPlaybackClient) and vmc2bvh. **Renderers** include three-vrm or a Live2D web runtime driven by a deterministic clock in headless Chromium (Puppeteer) piped to ffmpeg, Blender (VRM add-on plus VMC4B), Unity (UniVRM plus EVMC4U), and the Live2D Cubism Editor's own video export (transparent MOV).

### Cited Findings
**Live2D**
- Cubism Editor can export video (File > Export Image/Video > Video). **MOV with a transparent background is lossless**, so quality is high but files are large. H.264 may not show translucent parts correctly. The free version caps output at about 0.94 MP (1280x720). — [Live2D manual: Image and Video Export](https://docs.live2d.com/en/cubism-editor-manual/exporting-images) (summarized via search)
- `motion3.json` is motion data, not video. No built-in tool renders motion3.json to video; you load the .moc3 and motion into a runtime and capture frames. — [Live2D manual: Data for Embedded Use](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/); [Live2D community thread](https://community.live2d.com/discussion/529/how-to-export-video-in-cubism-3-x)
- Official SDK samples: [Live2D/CubismWebSamples](https://github.com/Live2D/CubismWebSamples) (about 398 stars, pushed 2026-04) and [Live2D/CubismNativeSamples](https://github.com/Live2D/CubismNativeSamples) (about 241 stars). Both use the **proprietary Live2D license** (the LICENSE starts with "Definitions / Live2D Cubism Components"), not OSI open source. CubismNativeSamples announces end of Cocos2d-x support with Cubism 5. Cubism Editor/SDK 5.4 alpha was announced and updated July 14, 2026 — [Live2D community](https://community.live2d.com/discussion/comment/3527)
- VTS motion3.json recordings re-import into Cubism Animator (set Animator to 60 fps first) — [VTS wiki: Record Animations](https://github.com/DenchiSoft/VTubeStudio/wiki/Record-Animations)

**VRM / 3D**
- Headless web path: generic Puppeteer-to-ffmpeg frame renderers exist, such as [andreybo/html5-animation-video-renderer](https://github.com/andreybo/html5-animation-video-renderer), which captures WebGL/canvas frame by frame and pipes them to ffmpeg. The npm package [@headless-three/renderer](https://www.pkgstats.com/pkg:@headless-three/renderer) offers a headless wgpu renderer for three.js in Node and shows VRMA seeking (AnimationMixer, then `vrm.update(0)`, then render), which is the seek-then-capture pattern offline rendering needs. A write-up describes the same Puppeteer, H5 frame, FFmpeg architecture for 3D avatars — [besthub.dev article](https://www.besthub.dev/articles/turning-3d-avatars-into-video-puppeteer-h5-frames-ffmpeg-workflow-03f5d716d050). (Search summaries; these packages were not inspected in depth.)
- [pixiv/three-vrm](https://github.com/pixiv/three-vrm): MIT, about 2,295 stars, pushed 2026-10. Since v3 it is compatible with three.js **WebGPURenderer** via `MToonNodeMaterial` — [three-vrm README](https://github.com/pixiv/three-vrm)
- [vrm-c/bvh2vrma](https://github.com/vrm-c/bvh2vrma): VRM Consortium BVH-to-VRMA converter, MIT, about 87 stars, pushed 2024-07 (quiet)
- [vrm-c/UniVRM](https://github.com/vrm-c/UniVRM): Unity VRM implementation, MIT, about 3,424 stars, active
- [saturday06/VRM-Addon-for-Blender](https://github.com/saturday06/VRM-Addon-for-Blender): "VRM Importer, Exporter and Utilities for Blender 2.93 to 5.3," about 1,742 stars, pushed 2026-11-16. No LICENSE file was found at the root by my check.
- VMC receivers for engine-based offline rendering: **EVMC4U** (Unity), **VMC4UE** (Unreal), **VMC4B** (Blender), **VRM4U**, and a Godot XR VMC tracker (Godot 4.3) — [VMC Protocol spec](https://protocol.vmc.info/english.html). A Unity forum thread combines EVMC4U and EasyMotionRecorder to capture live VMC — [Unity discussions](https://discussions.unity.com/t/evmc4u-and-easymotionrecorder-complete-hack-for-vmc-protocol-live-capture-in-a-window/858473)
- Warudo's Motion Recorder exports FBX/BVH, which can be imported into Blender or Unity for offline rendering — [Warudo docs](https://docs.warudo.app/docs/assets/motion-recorder)

**Recorders for VMC streams (see Q6)**
- [infosia/vmc2bvh](https://github.com/infosia/vmc2bvh): listens on VMC port 39539 and writes BVH (60 fps default, `--in-place` option), Windows/C++. About 41 stars, **last push 2021 (stale)**.

### Inferences
- For stream2clip, the most controllable offline renderer is a **web page (three-vrm, or a Live2D web runtime from Q4) in headless Chromium with a fixed timestep**, writing frames to ffmpeg. It runs on Linux servers, supports any resolution (1080x1920), and can output alpha (PNG sequence, then ProRes 4444 / VP9 or AV1 with alpha). Blender (VRM add-on plus a BVH/FBX import) is the higher-quality but heavier alternative.
- For Live2D, Cubism Editor's transparent MOV export is high quality but manual and GUI-bound, with the free tier capped at 720p. It does not suit batch processing.

### Gaps
- Unity Recorder (alpha/ProRes output) was not researched this session.
- I did not find a maintained open-source project that renders VRM plus VMC recordings to video headlessly. The headless-three and Puppeteer findings come from search snippets and package pages, not code review.
- Not confirmed: the exact Live2D Cubism SDK commercial "release license" thresholds (relevant if stream2clip ships the Cubism Core in a product).

## 3. AI talking-head / avatar animation from a single (anime) image

### Takeaway
For **anime**-specific single-image animation, the only purpose-built line is pixiv/Khungurn's **Talking Head Anime (THA) 1-4** and its real-time wrapper **EasyVtuber**. THA2/3 models are CC BY 4.0 (commercial-friendly). THA4 models are **CC BY-NC 4.0** and need about 30 GPU-hours of per-character distillation. The general portrait animators (LivePortrait, PersonaLive, EchoMimic, Hallo, InfiniteTalk, LiveAvatar, Ditto) are photoreal-first. They often work on anime faces but are not designed for them, and several carry non-commercial dependencies (InsightFace, X-Pose) or NC licenses (Sonic, THA4). The 2025-2026 trend is real-time, infinite-length streaming diffusion (PersonaLive, Live Avatar, SoulX-FlashHead).

### Cited Findings
**Anime-specific**
| Project | URL | Stars / last push | License | GPU / speed | Notes |
|---|---|---|---|---|---|
| THA1 | [talking-head-anime-demo](https://github.com/pkhungurn/talking-head-anime-demo) | ~2,028 / 2022-06 (stale) | MIT code | — | Original 2019 project |
| THA2 | [talking-head-anime-2-demo](https://github.com/pkhungurn/talking-head-anime-2-demo) | ~1,154 / 2022-06 (stale) | MIT code; model **CC BY 4.0** | Titan RTX tested; "RTX 2080, RTX 3080 or better" | iFacialMocap puppeteer + manual poser ([README](https://github.com/pkhungurn/talking-head-anime-2-demo)) |
| THA3 | [talking-head-anime-3-demo](https://github.com/pkhungurn/talking-head-anime-3-demo) | ~1,050 / 2023-08 | MIT code; model **CC BY 4.0** | Titan RTX; RTX 2080/3080+ | Adds body; `ifacialmocap_puppeteer`; 4 variants (standard/separable x float/half) ([README](https://github.com/pkhungurn/talking-head-anime-3-demo)) |
| THA4 | [talking-head-anime-4-demo](https://github.com/pkhungurn/talking-head-anime-4-demo) | ~359 / 2024-03 | MIT code (© pixiv); models **CC BY-NC 4.0** | Full model "too slow" for real time; per-character **student model (<2 MB)** distillation took "about 30 hours" on an RTX A6000; "anything after the GeForce RTX 2080 should be fine" | Input: 512x512 RGBA with zero-alpha background; student can be converted to TF.js for the web ([README](https://github.com/pkhungurn/talking-head-anime-4-demo)); WACV 2025 paper ([mlanthology](https://mlanthology.org/wacv/2025/khungurn2025wacv-talking)); 45 control parameters ([project page](https://pkhungurn.github.io/talking-head-anime-4)) |
| EasyVtuber | [yuyuyzl/EasyVtuber](https://github.com/yuyuyzl/EasyVtuber) | ~3,077 / 2026-02 | MIT (THA model licenses still apply) | NVIDIA + TensorRT-RTX; VRAM/RAM cache | Real-time THA3/THA4 + Spout2 alpha + upscaling + RIFE ([README](https://github.com/yuyuyzl/EasyVtuber)) |

**General portrait animation (video- or audio-driven)**
| Project | URL | Stars / last push | License | GPU / speed | Notes |
|---|---|---|---|---|---|
| LivePortrait (Kuaishou/Kling) | [KlingAIResearch/LivePortrait](https://github.com/KlingAIResearch/LivePortrait) (moved from KwaiVGI) | ~19,522 / 2026-06 | MIT code and weights; **InsightFace detection models are non-commercial research only**, so swap them for commercial use ([WarpTuber card](https://huggingface.co/AIWarper/WarpTuber); secondhand) | About 15 ms/frame total on RTX 4090 ([HF card](https://huggingface.co/KwaiVGI/LivePortrait/raw/main/README.md)); Apple Silicon "maybe 20x slower" | Video-driven (expression transfer); Animals model (2024-08, updated 2025-01) needs X-Pose and is NVIDIA/Linux/Windows only ([README](https://github.com/KlingAIResearch/LivePortrait)) |
| FasterLivePortrait | [warmshao/FasterLivePortrait](https://github.com/warmshao/FasterLivePortrait) | ~1,211 / 2025-06 | MIT | ONNX/TensorRT real time | Real-time LivePortrait |
| WarpTuber | [HF: AIWarper/WarpTuber](https://huggingface.co/AIWarper/WarpTuber) | — | MIT code + InsightFace NC caveat | — | LivePortrait-based webcam VTuber with animal mode; warns "highly stylized anime or cartoon characters may not work well" |
| PersonaLive | [GVCLab/PersonaLive](https://github.com/GVCLab/PersonaLive) | ~4,156 / 2026-08 | Apache-2.0 (LICENSE file) | Real-time WebUI; offline streaming mode for long videos "on 12GB VRAM"; TensorRT; RTX 50 notes | CVPR 2026, "Expressive Portrait Image Animation for Live Streaming"; "real-time and streamable… infinite-length" ([README](https://github.com/GVCLab/PersonaLive)) |
| Live Avatar (Alibaba Quark) | [Alibaba-Quark/LiveAvatar](https://github.com/Alibaba-Quark/LiveAvatar) | ~2,526 / 2026-08 | Apache-2.0 (base Wan2.2 also Apache-2.0) | 14B; 45+ FPS on multiple H800s; single 80 GB GPU; FP8 runs on 48 GB | Audio-driven, streaming, infinite length; ECCV 2026 spotlight ([README](https://github.com/Alibaba-Quark/LiveAvatar)) |
| SoulX-FlashHead | [arXiv 2602.07449](https://arxiv.org/abs/2602.07449) | — (Feb 2026) | Code release not confirmed | 1.3B; Lite variant "96 FPS on a single NVIDIA RTX 4090" | Real-time streaming audio-driven heads; no anime mention |
| InfiniteTalk (Meituan MeiGen) | [MeiGen-AI/InfiniteTalk](https://github.com/MeiGen-AI/InfiniteTalk) | ~8,421 / 2026-05 | Apache-2.0 | Low-VRAM mode; Wan2GP integration | Unlimited-length image-to-video / video-to-video dubbing; LongCat-Video-Avatar-1.5 released 2026-05-21 ([README](https://github.com/MeiGen-AI/InfiniteTalk)) |
| EchoMimic v1/v2/v3 (Ant Group) | [v1](https://github.com/antgroup/echomimic), [v2](https://github.com/antgroup/echomimic_v2), [v3](https://github.com/antgroup/echomimic_v3) | ~4,336 / ~4,678 / ~1,125; active | Apache-2.0 | v3: 1.3B params, "12G VRAM" via Gradio; tested A100/4090D/V100 | v2: semi-body; v3: unified multi-modal (AAAI 2026) ([v3 README](https://github.com/antgroup/echomimic_v3)) |
| Ditto (Ant Group) | [antgroup/ditto-talkinghead](https://github.com/antgroup/ditto-talkinghead) | ~937 / 2025-11 | Apache-2.0 (bundles insightface_det.onnx, so check the InsightFace caveat) | Real-time; tested on A100 | ACM MM 2025, motion-space diffusion ([README](https://github.com/antgroup/ditto-talkinghead)) |
| Hallo / Hallo2 / Hallo3 (Fudan) | [hallo](https://github.com/fudan-generative-vision/hallo), [hallo2](https://github.com/fudan-generative-vision/hallo2), [hallo3](https://github.com/fudan-generative-vision/hallo3) | ~8,675 / ~3,760 / ~1,423; last push 2024-09 / 2025-02 / 2025-03 (quiet) | MIT | Heavy diffusion, offline | Hallo2: long-duration and high-res (ICLR 2025); Hallo3: video-diffusion-based (CVPR 2025) |
| Sonic (Tencent) | [jixiaozhong/Sonic](https://github.com/jixiaozhong/Sonic) | ~3,276 / 2026-01 | **CC BY-NC-SA 4.0 (non-commercial)** | — | Global audio perception for portrait animation |
| HunyuanVideo-Avatar | [Tencent-Hunyuan/HunyuanVideo-Avatar](https://github.com/Tencent-Hunyuan/HunyuanVideo-Avatar) | ~2,221 / 2025-12 | **Tencent Hunyuan Community License** (custom, restrictive) | Large | Audio-driven multi-character |
| JoyVASA (JD) | [jdh-algo/JoyVASA](https://github.com/jdh-algo/JoyVASA) | ~888 / 2026-04 | MIT | — | "Diffusion-based Portrait and Animal Animation" (LivePortrait-style renderer) |
| AniPortrait | [Zejun-Yang/AniPortrait](https://github.com/Zejun-Yang/AniPortrait) | ~5,015 / 2024-07 (stale) | Apache-2.0 | — | Photoreal, audio-driven |
| SadTalker | [OpenTalker/SadTalker](https://github.com/OpenTalker/SadTalker) | ~14,211 / 2024-06 (stale) | Tencent-authored license text (LICENSE begins "Tencent is pleased to support the open source community…"); check terms | — | CVPR 2023, 3DMM coefficients; photoreal-oriented |

**Lip-sync only (re-dub an existing avatar video)**
- [TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk): MIT code ("no limitation for both academic and commercial usage"), but third-party models (whisper, ft-mse-vae, dwpose, S3FD) keep their own licenses. "30fps+ on an NVIDIA Tesla V100"; tested minimum is an RTX 3050 Ti laptop with 4 GB (8 s of video in about 5 min, fp16). About 6,975 stars, pushed 2025-09 — [README](https://github.com/TMElyralab/MuseTalk)
- [bytedance/LatentSync](https://github.com/bytedance/LatentSync): Apache-2.0, about 6,288 stars, 2025-06. "Taming Stable Diffusion for Lip Sync."
- [Rudrabha/Wav2Lip](https://github.com/Rudrabha/Wav2Lip): about 13,282 stars, 2025-06. No LICENSE file at the repo root (check README terms before commercial use).

**Image to 3D character / to Live2D (avatar generation)**
- [zjp-shadow/CharacterGen](https://github.com/zjp-shadow/CharacterGen) (SIGGRAPH'24; Apache-2.0; about 850 stars; 2025-04): 3D character from a single image via multi-view generation
- [hyz317/StdGEN](https://github.com/hyz317/StdGEN) (CVPR 2025; Apache-2.0; about 409 stars; 2026-04): semantic-decomposed 3D character (body/clothes/hair) from a single image, anime-oriented
- [aigc3d/LHM](https://github.com/aigc3d/LHM) (ICCV 2025; Apache-2.0; about 2,698 stars; 2026-03): animatable human from one image "in seconds" (realistic humans)
- [aigc3d/AniGS](https://github.com/aigc3d/AniGS) (CVPR 2025; no LICENSE file found; about 456 stars): animatable Gaussian avatar from one image
- **CartoonAlive** ([arXiv 2507.17327](https://arxiv.org/abs/2507.17327), July 2025): generates a Live2D model from a single portrait by mapping facial landmarks to Live2D parameters, with hair transferred via segmentation. Claims about half a minute per model. Portrait (head) only. Code status not verified.
- **Bunraku** ([alphaXiv 2607.27348](https://www.alphaxiv.org/abs/2607.27348), July 2026): splits one illustration into ordered RGBA layers with layered diffusion, builds meshes and predicts keypose deformations (auto-rigging). Reports a per-vertex direction cosine of about 0.74-0.77 and releases a benchmark. *Seen only through search snippets; verify before citing.*
- [Human3DAIGC/Textoon](https://github.com/Human3DAIGC/Textoon): "Generating Vivid 2D Cartoon Characters from Text Descriptions" (Live2D-style output). About 238 stars, 2025-07, no LICENSE file found.
- A December 2025 blog argued fully automatic image-to-Live2D rigging "doesn't reliably exist yet" — [waifuai blog](https://waifuai.blogspot.com/2025/12/from-image-to-live2d-what-ai-can-and.html) (opinion, predates Bunraku)

### Inferences
- If stream2clip ever needs to **re-animate a VTuber from a still** (for example, a clip whose avatar layer was occluded), THA3 or EasyVtuber (CC BY 4.0 models, anime-native, real time on a mid-range GPU) is the anime-native option. However, a VTuber stream has no face video of the streamer to drive it, so the driving signal has to come from recorded tracking or parameters, or from audio. Audio-driven models (PersonaLive, EchoMimic v3, InfiniteTalk, MuseTalk) are therefore the relevant class, but they target photoreal faces, and anime quality must be tested.
- License triage for commercial use: safer are THA2/THA3 models, PersonaLive, EchoMimic, InfiniteTalk, LiveAvatar, Hallo, LatentSync and MuseTalk code. Caution: LivePortrait and Ditto (InsightFace models), and LivePortrait Animals (X-Pose). Non-commercial: THA4 models, Sonic. Custom: HunyuanVideo-Avatar, SadTalker.
- Generative avatar re-animation will look different from the streamer's real rig. For a clip tool, faithful re-rendering of the actual model (Q2/Q6) beats AI re-animation; AI is a fallback or creative feature.

### Gaps
- No anime-specific quality benchmark comparing LivePortrait, PersonaLive and EchoMimic on anime illustrations was found.
- Not verified: the LivePortrait GitHub README's own wording on InsightFace or X-Pose licensing (the HF card lists only MIT). The NC caveat is secondhand via WarpTuber.
- Code or weight release for SoulX-FlashHead, CartoonAlive and Bunraku is not confirmed.
- The exact GitHub "archived" flags could not be read (API blocked); staleness is inferred from push dates.
- No newer anime-specific model (2025-2026) beyond THA4/EasyVtuber was found. Possibly none exists, or search coverage was insufficient.

## 4. Web-based renderers and libraries

### Takeaway
The web stack is the most reusable rendering layer for stream2clip. For VRM: **three-vrm** (MIT, active, WebGPU-capable, with VRMA animation support in the same monorepo). For Live2D: **pixi-live2d-display**, whose upstream is stale on PixiJS v6/v7, so use a maintained PixiJS v8 / Cubism 5 fork; the Cubism Core it loads is proprietary-licensed. For tracking-to-rig math: **MediaPipe + Kalidokit**. Babylon.js VRM support is stale.

### Cited Findings
- [pixiv/three-vrm](https://github.com/pixiv/three-vrm): "Use VRM on Three.js," MIT, about 2,295 stars, pushed 2026-10-22. WebGPURenderer compatibility since v3 — [README](https://github.com/pixiv/three-vrm). VRMA (VRM animation) playback in three.js is demonstrated in headless use by [@headless-three/renderer](https://www.pkgstats.com/pkg:@headless-three/renderer). The `@pixiv/three-vrm-animation` package is believed to live in the same monorepo, but this was not re-verified this session (see Gaps).
- [pixiv/ChatVRM](https://github.com/pixiv/ChatVRM): MIT, about 848 stars, last push 2025-05. A browser VRM conversational avatar demo, useful as a reference three-vrm app with lip-sync.
- [guansss/pixi-live2d-display](https://github.com/guansss/pixi-live2d-display): MIT, about 1,518 stars, **last push 2024-08 (stale)**. Targets PixiJS v6 per its docs.
  - Forks: [RaSan147/pixi-live2d-display](https://github.com/RaSan147/pixi-live2d-display) ("with lip-sync from audio," MIT, about 195 stars, 2025-06); [@naari3/pixi-live2d-display](https://cdn.jsdelivr.net/npm/@naari3/pixi-live2d-display@1.2.5/README.md) (PixiJS 8.x + Cubism Core 5); [untitled-pixi-live2d-engine](https://www.pkgstats.com/pkg:untitled-pixi-live2d-engine) (PixiJS v8, Cubism 2-5); [pixi-live2d-display-advanced](https://npmjs.com/package/pixi-live2d-display-advanced) (PixiJS v7, v8 planned). The Cubism 5 core (`live2dcubismcore.min.js`) must be taken from the Cubism SDK.
- [yeemachine/kalidokit](https://github.com/yeemachine/kalidokit): "Blendshape and kinematics calculator for Mediapipe/Tensorflow.js Face, Eyes, Pose, and Finger tracking models," MIT, about 5,731 stars, pushed 2025-08.
- [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe): Apache-2.0, about 37,732 stars, active. THA4 redistributes the MediaPipe Face Landmarker model — [THA4 README](https://github.com/pkhungurn/talking-head-anime-4-demo)
- [virtual-cast/babylon-vrm-loader](https://github.com/virtual-cast/babylon-vrm-loader): MIT, about 137 stars, **last push 2024-03 (stale)**
- [Open-LLM-VTuber/Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber): MIT, about 14,755 stars, 2026-05. A working Live2D web front end with LLM, voice and lip-sync, and a large-scale example of browser Live2D rendering.
- [Live2D/CubismWebSamples](https://github.com/Live2D/CubismWebSamples): the official Web SDK sample (proprietary Live2D license), pushed 2026-04.

### Inferences
- A single headless-browser "renderer service" (Chromium + WebGL/WebGPU) can cover VRM (three-vrm) and Live2D (pixi-live2d-display v8 fork or the Cubism Web SDK) with one capture pipeline. This is likely the best architectural fit for stream2clip's re-render feature.
- Licensing: three-vrm, Kalidokit and MediaPipe are permissive. Live2D's Cubism Core is not open source, so check redistribution terms before bundling.

### Gaps
- Not verified whether the @naari3 or untitled-pixi-live2d-engine forks are actively maintained (no commit history fetched).
- Not re-verified: the `@pixiv/three-vrm-animation` package name and its location in the three-vrm monorepo (the README grep this session showed only WebGPU and basic examples).
- No Babylon.js VRM loader newer than virtual-cast's was found.

## 5. Protocols (VMC, VTube Studio API, iFacialMocap/ARKit, Spout/NDI) and what they enable

### Takeaway
**VMC Protocol** (OSC over UDP, MIT-licensed spec) is the key interchange for 3D. It carries every humanoid bone, blendshapes, root and camera per frame, so a timestamped dump of VMC packets is a complete, engine-independent recording that can be replayed into any receiver (VSeeFace, Warudo, Unity, Blender, a web renderer) for re-rendering. For Live2D, the equivalent is the stream of Live2D parameter values: VTS records them as motion3.json, and the VTS API exposes them programmatically. Spout2 and NDI carry pixels with alpha, not data.

### Cited Findings
- VMC Protocol: "a simple implementation using Open Sound Control and VRM." OSC over UDP, typically ports 39539/39540; Windows/Mac/Linux/iOS. Roles: Marionette (receiver/renderer), Performer (sender), Assistant. Messages: `/VMC/Ext/Bone/Pos` (all HumanBodyBones including eyes and fingers), `/VMC/Ext/Blend/Val` + `/VMC/Ext/Blend/Apply` (expressions, lip-sync), `/VMC/Ext/Root/Pos`, `/VMC/Ext/Cam` (position, rotation, FOV), plus lights, input, trackers and others. MIT licence. Performers include Virtual Motion Capture, Waidayo, VSeeFace, MocapForAll and TDPT. Marionettes include EVMC4U (Unity), VMC4UE (Unreal), VMC4B (Blender), VRM4U and a Godot VMC tracker. The spec page does not mention recording. — [VMC Protocol spec (EN)](https://protocol.vmc.info/english.html)
- Other VMC implementations: Python [vmcp on PyPI](https://pypi.org/project/vmcp); Rust [vmc crate](https://docs.rs/crate/vmc/latest/source/src/lib.rs); Warudo VMC receiver ([docs](https://docs.warudo.app/docs/mocap/vmc)); Animaze VMC ([guide](https://www.animaze.us/manual/vmc-guide))
- VTube Studio API: official dev repo [DenchiSoft/VTubeStudio](https://github.com/DenchiSoft/VTubeStudio) (MIT, active 2026-11). VTS-native recording of Live2D parameters to 60-fps motion3.json — [VTS wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Record-Animations)
- iFacialMocap (iOS ARKit face tracking app) drives THA2/THA3 (`ifacialmocap_puppeteer`) — [THA3 README](https://github.com/pkhungurn/talking-head-anime-3-demo). EasyVtuber connects to iFacialMocap over UDP directly (skipping the PC app) for up to 60 fps tracking — [EasyVtuber README](https://github.com/yuyuyzl/EasyVtuber)
- Spout2 is Windows-only GPU texture sharing ([leadedge/Spout2](https://github.com/leadedge/Spout2), BSD-2). NDI is networked video with alpha, Windows/macOS ([VTS wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Recording-Streaming-with-OBS)), and reaches OBS via [DistroAV](https://github.com/DistroAV/DistroAV).

### Inferences
- For stream2clip's re-render feature, the most valuable thing to capture during a live stream is a **timestamped parameter stream**: VMC packets for VRM apps, and Live2D parameter values via the VTS API or VTS's own motion3.json recorder for Live2D. Store it alongside the stream's VOD timestamps. This is small (KB/s), lossless and engine-agnostic.
- Spout2/NDI only help if the streamer records the alpha avatar layer at stream time. They cannot re-frame the camera afterwards.
- ARKit 52-blendshape data (iFacialMocap and similar) is a common denominator between Live2D and VRM face tracking. Recording raw tracking, rather than rig parameters, allows re-targeting to any rig later, but needs the rig's mapping logic.

### Gaps
- The VTS API message list (parameter read, inject and subscription endpoints, WebSocket port) was not re-fetched this session. From background knowledge it is a WebSocket JSON API with parameter list and injection requests, but that should be verified in the repo README before relying on it.
- The ARKit blendshape spec and iFacialMocap protocol details were not fetched.
- No standard file format for "recorded VMC sessions" was found. Each tool uses its own (JSON dump, BVH, Unity anim, WANIM).

## 6. Projects that record avatar parameters during a stream and replay/re-render them later

### Takeaway
Re-rendering for clips is supported only piecemeal. VTS and Warudo have first-party recorders. For VMC there are small hobby tools (MotionReplay, VRMPlaybackClient, vmc2bvh), all Windows/Unity-based and stale. No project was found that does the full stream2clip use case ("record during stream, then re-render a clip at a new aspect ratio or camera angle with alpha"). That is an open gap stream2clip could fill with a VMC/VTS-API recorder plus a headless web renderer.

### Cited Findings
- **VTube Studio Record Live2D Animation**: records parameters to motion3.json at 60 fps, with per-parameter toggles and smoothing; replays in VTS or imports into Cubism Animator/Physics Editor — [VTS wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Record-Animations)
- **Warudo Motion Recorder / Motion Player**: WANIM (skeleton + blendshapes + expressions) for in-Warudo replay, which can then be re-shot with Warudo's cameras; FBX/BVH for external tools — [Warudo docs](https://docs.warudo.app/docs/assets/motion-recorder)
- **[emilianavt/MotionReplay](https://github.com/emilianavt/MotionReplay)** (by the VSeeFace author): receives VMC on localhost:39539 and saves to a **JSON packet dump**, then plays it back to 127.0.0.1:39539 with busy-wait timing for accuracy. Unity build, about 14 stars, last push 2022-09 (stale). — [README](https://github.com/emilianavt/MotionReplay)
- **[kevinjycui/VRMPlaybackClient](https://github.com/kevinjycui/VRMPlaybackClient)**: "Capture and playback of VRM motion data in VMC protocol," with optional audio recording (audio captures limited to 59m59s). Can forward playback to a third-party VMC player such as VSeeFace. Windows-only, built on UniVRM, uOSC and EVMC4U. About 8 stars, last push 2024-01. — [README](https://github.com/kevinjycui/VRMPlaybackClient)
- **[infosia/vmc2bvh](https://github.com/infosia/vmc2bvh)**: VMC to BVH recorder (60 fps default), needs paid VirtualMotionCapture. Stale since 2021. — [README](https://github.com/infosia/vmc2bvh)
- **EVMC4U + EasyMotionRecorder**: community recipe for capturing live VMC in Unity — [Unity discussions](https://discussions.unity.com/t/evmc4u-and-easymotionrecorder-complete-hack-for-vmc-protocol-live-capture-in-a-window/858473)
- A Reddit r/vtubertech thread describes syncing OBS events to a video using Warudo blueprints and the Spout plug-in (community workflow) — [mirror link](https://lr.eu.psf.lt/r/vtubertech/comments/1kmxf4t/synchronizing_obs_events_to_a_video)

### Inferences
**Most reusable for stream2clip, in priority order:**
1. **Alpha avatar layer at stream time** (Spout2/NDI into a separate OBS recording; VTS, Warudo, VSeeFace, VNyan, Animaze, nizima LIVE and EasyVtuber all support it). This gives instant transparent cut-outs for vertical re-composition with no rendering engine. Lowest effort, works with any closed-source app.
2. **Parameter recording sidecar**: a small cross-platform VMC/OSC listener (Python `vmcp`, or port the MotionReplay JSON-dump idea) for VRM apps, and a VTS API client (or VTS's motion3.json recorder) for Live2D, timestamp-aligned to the VOD.
3. **Headless web re-renderer**: three-vrm (+ VRMA/VMC replay) and a pixi-live2d-display v8 fork or the Cubism Web SDK, in Puppeteer with a deterministic clock, then ffmpeg (PNG / ProRes 4444 / VP9-alpha, 1080x1920). This enables new aspect ratios, zoom or camera angles (3D), and transparent backgrounds. Requires the streamer's model file (.vrm or .moc3 + textures) and permission.
4. **AI fallback**: EasyVtuber/THA3 (anime, CC BY 4.0 models) or audio-driven portrait models (PersonaLive, EchoMimic v3, MuseTalk lip-sync) only where model files or parameter data are missing. Weigh licenses and anime quality.
- Reference projects worth bookmarking as code to study: three-vrm, pixi-live2d-display (+ v8 forks), Kalidokit, MotionReplay (VMC dump format), VRMPlaybackClient (VMC + audio capture), VMagicMirror and VirtualMotionCapture (open-source VRM apps), EasyVtuber (Spout2 alpha output from Python), Open-LLM-VTuber and ChatVRM (web avatar apps with lip-sync).

### Gaps
- No existing open-source "VTuber stream to re-rendered clip" project was found. The specific "different camera angle / aspect ratio from recorded parameters" workflow appears unaddressed in public projects (absence of evidence, limited search budget).
- Not investigated: whether Warudo's WANIM format is documented, or whether VTS can record continuously for multi-hour streams. The VTS wiki does not state duration limits.
- Legal/consent aspects of re-rendering a streamer's model (model ToS on BOOTH, creator licenses) were not researched and are likely important.
