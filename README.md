<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo/png/lockup_on-dark.png">
    <img alt="stream2clip" src="assets/brand/logo/png/lockup_on-light.png" height="72">
  </picture>
</p>

<p align="center">
  <b>Stream in. Clips out.</b><br>
  버튜버를 위한 방송 → 클립 편집 도구 · 캡쳐부터 움짤 녹화까지, 한 프로그램으로
</p>

<p align="center">
  <img alt="긴 방송 속 레전드만 쏙. — stream2clip 키 비주얼" src="assets/brand/02_concept-image_keyvisual_1920x1080.png">
</p>

---

**stream2clip**은 방송 화면과 다시보기(VOD)에서 장면을 캡쳐하고, 바로 편집하고, GIF·MP4·WebP 움짤로 녹화하는 도구입니다. 그린스크린을 지운 **투명 배경 녹화**도 됩니다. 데스크톱 앱(PySide6)으로도 쓸 수 있고, GUI 없이 **다른 오픈소스 영상 프로젝트에 그대로 이식**할 수 있도록 코어를 작은 파이썬 라이브러리로 분리했습니다.

> 현재 버전 v0.1은 캡쳐 · 편집 · 움짤 녹화 · VOD 구간 변환까지 구현되어 있습니다. 채팅 반응 기반 하이라이트 자동 검출, 9:16 세로 클립 레이아웃 같은 "방송 → 클립" 자동화는 [로드맵](#로드맵)에 있습니다.

## 주요 기능

| 기능 | 내용 |
|---|---|
| **영역 캡쳐** (F8) | 화면을 멈춘 상태에서 드래그로 영역 선택 → 보이는 그대로 캡쳐. 전체 화면(모든 모니터) 캡쳐, 이미지 파일 열기 |
| **캡쳐하고 바로 편집** | 선택 · 펜 · 형광펜 · 네모 · 화살표 · 글자 · 모자이크 · 투명 · 자르기 <br> 8색 팔레트 + 팔레트(임의 색) + 스포이드, 굵기, 되돌리기/다시 실행, 클립보드 복사, PNG/JPG/WebP/BMP 저장 |
| **번역 (한국어)** | 이미지 속 글자를 OCR → 번역해 덮어쓰기. OCR·번역기는 플러그인으로 연결 (기본 내장 서비스 없음) |
| **움짤 녹화** (F9) | F9 → 영역 드래그 → 바로 녹화 시작, 다시 F9 → 저장. **GIF**(어디서나 재생) · **MP4**(가벼운 용량) · **WebP**(선명한 화질) · **WebM**(투명 영상), CLI에서는 MOV(ProRes 4444)·APNG도 지원 |
| **투명 배경 녹화** | 고른 색(그린스크린 등)을 지워 GIF · WebP · WebM · MOV · APNG를 투명하게. 스포이드로 화면에서 색을 고르고 허용 범위 조절 |
| **VOD → 클립 변환** | 다시보기 파일에서 구간(시작/끝) · 크롭 · 크기 · fps를 지정해 GIF/WebP/MP4 클립으로 변환 (`stream2clip convert`) |
| **이식 가능한 코어** | ffmpeg 명령 빌더, ffmpeg `colorkey`와 같은 결과를 내는 numpy 크로마키, JSON 주석 포맷, 플러그인(캡처 백엔드·OCR·번역기) |

## 스크린샷

| 런처 | 편집기 |
|---|---|
| <img src="docs/images/launcher.png" alt="런처: 캡쳐 버튼, 움짤 녹화 설정, 투명 배경 녹화" width="420"> | <img src="docs/images/editor.png" alt="편집기: 선택·펜·형광펜·네모·화살표·글자·모자이크·투명·자르기 툴바" width="520"> |

<p align="center"><img src="docs/images/selector.png" alt="영역 선택 오버레이: 선택 영역만 밝게 표시하고 실제 픽셀 크기를 보여줌" width="720"><br><sub>영역 선택 오버레이 — 화면을 멈춘 채 드래그, 실제 픽셀 크기 표시, Enter 전체 화면 · Esc 취소</sub></p>

> 스크린샷의 캡쳐 대상 이미지는 [`assets/brand`](assets/brand)의 키 비주얼입니다.

## 설치

필요한 것: **Python 3.10+**, **ffmpeg** (PATH에 있거나 `STREAM2CLIP_FFMPEG` 환경 변수로 지정)

```bash
git clone https://github.com/BudongJW/stream2clip.git
```

```bash
cd stream2clip
```

```bash
pip install -e ".[gui]"
```

- 라이브러리/CLI만: `pip install -e ".[capture]"` (화면 캡쳐 없이 변환·편집만 쓰면 `pip install -e .`)
- 리눅스·맥에서 앱이 비활성일 때도 F8/F9를 쓰려면: `pip install -e ".[gui,hotkey]"` (Windows는 추가 설치 없이 전역 단축키 지원)
- OCR(번역 기능용 Tesseract): `pip install -e ".[ocr]"` + tesseract 바이너리

## 사용법

### 데스크톱 앱

```bash
stream2clip gui
```

| 단축키 | 동작 |
|---|---|
| `F8` | 영역 캡쳐 → 편집기 |
| `F9` | 녹화할 영역 선택 후 바로 녹화 시작 / 다시 누르면 정지·저장 |
| `V` `P` `H` `R` `A` `T` `M` `E` `C` | 선택 · 펜 · 형광펜 · 네모 · 화살표 · 글자 · 모자이크 · 투명 · 자르기 |
| `I` | 스포이드 |
| `[` `]` | 굵기 −/+ (글자 크기 = 굵기 × 3 + 12, 모자이크 블록 = 굵기 × 2) |
| `Ctrl+Z` / `Ctrl+Y` | 되돌리기 / 다시 실행 |
| `Ctrl+C` / `Ctrl+S` | 복사 / 저장 |
| `Ctrl+휠`, `Ctrl+0` | 확대·축소, 100% |

편집기 팁: **투명** 도구는 드래그하면 그 영역을 지우고, 클릭하면 클릭한 색을 이미지 전체에서 투명하게 만듭니다. **자르기**는 원본을 보존한 채 남길 영역만 지정합니다(다시 드래그하면 변경). 저장할 때 `.json`을 고르면 주석만 따로 저장됩니다.

### CLI

```bash
stream2clip capture --region 100,100,1280,720 -o shot.png
```

```bash
stream2clip record --region 0,0,640,360 --duration 5 -o clip.gif
```

```bash
stream2clip record --monitor 0 --transparent --key-color "#00FF00" -o avatar.webp
```

```bash
stream2clip convert vod.mp4 --start 1:02:03 --end 1:02:18 --crop 640,0,640,720 --width 480 -o highlight.webp
```

```bash
stream2clip convert greenscreen.mp4 --transparent --similarity 0.15 -o avatar.webm
```

```bash
stream2clip annotate shot.png --annotations edits.json -o out.png
```

`convert --print-command`는 실행 대신 ffmpeg 명령만 출력합니다. 다른 도구나 스크립트에 그대로 붙여 쓸 수 있습니다. 전체 옵션은 `stream2clip <명령> --help`.

## 라이브러리로 쓰기 / 다른 프로젝트에 이식

코어는 numpy + Pillow만 필요하고 GUI와 완전히 분리되어 있습니다. 자세한 이식 방법은 [docs/PORTING.md](docs/PORTING.md)에 있습니다.

```python
from stream2clip import ExportOptions, Region, build_export_command, export

# 1) ffmpeg 명령만 만들기 — 어떤 ffmpeg 기반 파이프라인에도 붙일 수 있음
opts = ExportOptions(format="webp", start=3723, end=3738, crop=Region(640, 0, 640, 720), width=480,
                     transparent=True, key_color="#00FF00")
print(build_export_command("vod.mp4", "clip.webp", opts))

# 2) 바로 실행
export("vod.mp4", "clip.webp", opts)
```

```python
from PIL import Image
from stream2clip.editor import Arrow, Document, Mosaic, Text
from stream2clip.geometry import Region

doc = Document(Image.open("frame.png"))
doc.add(Arrow((40, 300), (220, 180), color="#FF4F8B", width=6))
doc.add(Text((240, 150), "레전드 장면", size=32, background="#FFD84D", color="#15131F"))
doc.add(Mosaic(Region(20, 20, 200, 60)))
doc.save("frame_annotated.png")
doc.render_overlay().save("overlay.png")       # 주석만 있는 투명 PNG (영상 편집기·OBS 오버레이용)
doc.save_annotations("frame.annotation.json")  # stream2clip.annotation/v1
```

```python
from stream2clip.capture import ArrayBackend
from stream2clip.ffmpeg import ExportOptions
from stream2clip.geometry import Region
from stream2clip.record import Recorder

# 어떤 프레임 소스(게임 엔진, 아바타 렌더러, OBS 등)든 RGBA numpy 배열이면 녹화 가능
recorder = Recorder(Region(0, 0, 1080, 1920), fps=30, backend_factory=lambda: ArrayBackend(my_render_fn))
recorder.start(); ...; recording = recorder.stop()
recording.export("avatar.webm", ExportOptions(format="webm", transparent=True))
```

## 구조

```
src/stream2clip/
├── geometry.py, color.py, frames.py   기본 타입 (Region, 색, RGBA 프레임 규약)
├── ffmpeg.py     ffmpeg 명령/필터그래프 빌더 (프로세스 실행 없음, 순수 함수)
├── chroma.py     크로마키 — ffmpeg colorkey와 같은 수식 (미리보기 = 결과물)
├── export.py     ffmpeg 실행, ffprobe
├── capture/      캡처 백엔드 (mss, numpy 배열, 플러그인) + 커서 오버레이
├── editor/       주석 모델 · 렌더러 · 되돌리기 · JSON 직렬화
├── record/       실시간 영역 녹화 (무손실 FFV1 중간 파일 → 원하는 포맷으로 내보내기)
├── translate/    OCR + 번역 플러그인 인터페이스
├── plugins.py    entry point 기반 플러그인 레지스트리
├── cli.py        stream2clip 명령
└── gui/          PySide6 앱 (런처, 영역 선택, 편집기, 녹화 오버레이, 전역 단축키)
```

설계 원칙과 데이터 흐름은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 보세요.

## 브랜드

<p align="center"><img src="assets/brand/01_concept-logo-sheet@2x.png" alt="stream2clip 컨셉 로고 시트: 프라이머리 로크업, 심볼, 앱 아이콘, 컬러, 서체, 최소 크기" width="860"></p>

심볼은 **가로 16:9 스트림 프레임에서 세로 9:16 클립 카드를 꺼내는 순간**을 담았습니다. 왼쪽의 점은 REC, 즉 라이브의 흔적입니다.

| 컬러 | HEX | 용도 |
|---|---|---|
| 잉크 | `#15131F` | 배경, 진한 텍스트 |
| 페이퍼 | `#F7F4FA` | 밝은 배경, 어두운 배경 위 텍스트 |
| 라이브 핑크 | `#FF4F8B` | 포인트, REC, 클립 구간 |
| 하이라이트 | `#FFD84D` | 강조, 상태 표시 |

| 서체 | 용도 |
|---|---|
| Outfit | 워드마크 · 영문 헤드라인 |
| Noto Sans KR | 국문 헤드라인 · 본문 |
| JetBrains Mono | 타임코드 · 라벨 |

| 파일 | 설명 |
|---|---|
| [`assets/brand/logo/svg/`](assets/brand/logo/svg) | 벡터 원본: 컬러 심볼(밝은/어두운 배경), 단색(검정/흰색), 16px 이하용 단순화 버전, 앱 아이콘(다크/핑크) |
| [`assets/brand/logo/png/`](assets/brand/logo/png) | 투명 배경 1024px PNG, 가로형 로크업(`lockup_on-dark.png`, `lockup_on-light.png`) |
| [`assets/brand/logo/favicon/`](assets/brand/logo/favicon) | `favicon.ico`(16/32/48), 32·512px PNG, `apple-touch-icon_180.png` |
| [`assets/brand/02_concept-image_keyvisual_1920x1080.png`](assets/brand/02_concept-image_keyvisual_1920x1080.png) | 키 비주얼 (3840×2160 `@2x` 버전도 있음) |
| [`assets/brand/03_github-social-preview_1280x640.png`](assets/brand/03_github-social-preview_1280x640.png) | GitHub 소셜 프리뷰 — 저장소 Settings → General → Social preview에 업로드 |

<p align="center"><img src="assets/brand/03_github-social-preview_1280x640.png" alt="GitHub 소셜 프리뷰" width="640"></p>

데스크톱 앱도 같은 팔레트와 앱 아이콘(핑크)을 사용합니다. PNG 시안의 영문 워드마크는 Outfit 대신 Poppins로 렌더링되어 원본 디자인과 글자 모양이 약간 다릅니다 ([`assets/brand/README.txt`](assets/brand/README.txt) 참고). 심볼·앱 아이콘·파비콘은 순수 도형이라 원본과 같습니다.

## 로드맵

[외부 프로젝트 레퍼런스 조사](reports/버튜버%20영상%20작업%20프로젝트%20레퍼런스.md) 결과를 바탕으로 한 다음 단계입니다.

- [ ] VOD·채팅 수집: yt-dlp(구간 다운로드·`live_chat`·heatmap), chat-downloader, TwitchDownloader, CHZZK/SOOP
- [ ] 하이라이트 검출: 방송별 기준선 대비 채팅 급증 + 반응 어휘(草·ㅋㅋ·KEKW) + 오디오, 피크 −10~30초 보정, 슈퍼챗 신호
- [ ] 버튜버 인식 9:16 레이아웃: 애니메 얼굴 검출로 아바타 박스 제안 → "아바타 위 / 게임 아래" 템플릿
- [ ] 자막: faster-whisper/WhisperX + 카라오케 ASS, JP→KR 용어집
- [ ] 아바타 레이어: Spout2/NDI 알파 레이어 녹화, VMC/VTube Studio 파라미터 기록 후 재렌더
- [ ] 업로드 전 기획사 2차 창작 가이드라인 검사 (원본 URL 표기, 아카이브 공개 여부 등)
- [ ] OBS 리플레이 버퍼 연동 (obs-websocket `SaveReplayBuffer` → 바로 움짤 변환)

## 개발

```bash
pip install -e ".[dev]"
```

```bash
pytest
```

리눅스에서 실제 화면을 쓰는 end-to-end GUI 테스트(F8 캡쳐, F9 투명 녹화)까지 돌리려면 Xvfb를 사용합니다.

```bash
xvfb-run -a pytest
```

## 알려진 제약

- **Wayland**: 화면 캡쳐(mss)는 X11/XWayland에서 동작합니다. 순수 Wayland 세션은 아직 지원하지 않습니다.
- **macOS**: 시스템 설정에서 화면 기록 권한이 필요합니다. 아직 실기기에서 검증하지 않았습니다.
- **Windows**: 전역 단축키(RegisterHotKey)와 커서 위치는 Win32 API로 구현했지만 이 저장소의 테스트는 리눅스(Xvfb)에서만 돌렸습니다.
- **배율이 다른 다중 모니터**: 논리↔물리 좌표를 가상 화면 전체 비율로 환산하므로, 모니터마다 배율이 다르면 선택 영역이 조금 어긋날 수 있습니다.
- **GIF 투명도**는 1비트입니다. 부드러운 가장자리가 필요하면 WebP/WebM/MOV를 쓰세요.

## 라이선스

[Apache License 2.0](LICENSE). GUI는 PySide6(LGPLv3), 화면 캡쳐는 mss(MIT)를 사용하며, 영상 인코딩은 시스템에 설치된 ffmpeg 빌드의 라이선스(LGPL/GPL)를 따릅니다. 브랜드 에셋(`assets/brand`)은 이 프로젝트의 로고·컨셉 이미지입니다.
