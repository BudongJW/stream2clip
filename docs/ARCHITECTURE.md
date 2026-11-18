# 아키텍처

## 설계 원칙

1. **코어와 앱 분리.** `gui/`를 지워도 나머지는 그대로 동작합니다. GUI는 코어의 얇은 껍데기입니다.
2. **순수 함수 우선.** ffmpeg 명령, 필터그래프, 크로마키 수식, 주석 렌더링은 입력→출력이 정해진 함수입니다. 프로세스 실행(`export.py`, `record/`)은 그 위의 별도 층에 있습니다.
3. **비파괴 편집.** 원본 이미지는 그대로 두고, 주석은 불변(frozen) 데이터클래스 목록 + 자르기 영역으로 저장합니다. 되돌리기는 상태 스냅샷을 오가기만 합니다.
4. **미리보기 = 결과물.** 편집기의 투명 도구와 녹화의 투명 배경은 같은 크로마키 수식(ffmpeg `colorkey`)을 씁니다.
5. **확장은 플러그인으로.** 캡처 백엔드, OCR, 번역기는 `Protocol` + entry point로 바꿔 끼웁니다.

## 층 구조

```
            ┌──────────────────────────── gui/ (PySide6) ───────────────────────────┐
            │ launcher  selector  editor/canvas  recording(F9)  hotkeys  highlights  │
            └───────┬──────────┬───────────┬──────────────┬─────────────────────────┘
                    │          │           │              │
   cli.py ──────────┤          │           │              │
                    ▼          ▼           ▼              ▼
              capture/      editor/      record/  ───►  export.py ──► ffmpeg 프로세스
              (mss, array,  (model,       (Recorder,      (run, probe)
               plugins,      render,       Recording)        ▲
               cursor)       history,         │              │
                             document)        └── ffmpeg.py ─┘  (명령/필터그래프 빌더)
                    │          │                     │
                    └──────────┴───── chroma.py ─────┘
                                 geometry · color · frames · plugins
```

## 데이터 흐름

### 영역 캡쳐 → 편집

1. `ScreenSelector`가 가상 화면 전체를 mss로 **먼저 캡쳐**해 멈춘 화면 위에서 드래그를 받습니다(보이는 그대로 캡쳐).
2. Qt 논리 좌표의 선택 영역을 스크린샷/가상 화면 비율로 **물리 픽셀** `Region`으로 바꿉니다(HiDPI 대응). 위치와 크기를 따로, `n.5`는 올림으로 반올림합니다. Qt가 소수 배율(125% · 150%)에서 창을 놓는 방식과 같아서 선택 크기가 위치에 따라 달라지지 않고, 창의 논리 영역을 고르면 그 창의 물리 픽셀과 정확히 맞습니다(Windows 125% 실기기에서 `GetWindowRect`와 비교해 확인).
3. 잘라낸 PIL 이미지로 `Document`를 만들고 `EditorWindow`에 넘깁니다.
4. 캔버스는 확정된 주석을 Pillow로 렌더링해 캐시하고, 드래그 중인 도형만 QPainter로 미리 그립니다. 마우스를 놓으면 `Document.add()`로 새 상태가 히스토리에 쌓입니다.

### 움짤 녹화 (F9)

```
F9 ─► 영역 선택 ─► (200ms: 오버레이가 화면에서 사라질 시간) ─► Recorder.start()
                                                      │
       캡처 스레드: grab(region) → 커서 합성 → frame_filter → rawvideo RGBA
                                                      │ stdin
                                       ffmpeg -c:v ffv1 -pix_fmt bgra  (무손실 .mkv)
F9 ─► Recorder.stop() ─► Recording ─► export(GIF/WebP/MP4/WebM/MOV/APNG, 투명 배경 옵션)
```

- **타이밍**: 캡처 루프는 벽시계 기준입니다. 캡처가 느리면 직전 프레임을 반복해 재생 속도가 실제와 같게 유지됩니다.
- **중간 파일**: FFV1/Matroska로 알파를 보존한 채 녹화하고, 정지 후 원하는 포맷으로 변환합니다. 녹화 중에는 GIF 팔레트를 계산할 필요가 없고, 같은 녹화본을 여러 포맷으로 다시 내보낼 수 있습니다. VOD 변환과 같은 `export()` 경로를 씁니다.
- **녹화 테두리**: 영역 **바깥**에 불투명한 얇은 창 4개로 그립니다. 반투명 창 하나로 덮으면 컴포지터가 없는 X11에서는 검게 칠해지고, 일부 캡처 API에서는 녹화 결과에 섞이기 때문입니다.
- **커서**: 화면 캡처 API는 대부분 커서를 빼므로 직접 합성합니다. Windows는 `GetCursorPos`, 그 외에는 GUI 스레드가 `QCursor.pos()`를 물리 좌표로 바꿔 공유합니다. 화살표 크기는 `Recorder(cursor_scale=)`로 화면 배율(1.25, 1.5 …)에 맞춥니다.
- **전역 단축키**: Windows는 `RegisterHotKey(NULL, …)`로 등록하고 Qt 네이티브 이벤트 필터에서 스레드 메시지 `WM_HOTKEY`를 받습니다. 런처가 숨겨져 있고 다른 프로그램이 앞에 있어도 F9로 정지됩니다(실기기에서 OS 수준 키 입력으로 확인).

### 방송 → 클립 자동화 (`stream2clip auto`)

```
fetch (yt-dlp) ─► info.json · <id>.live_chat.json · <id>.ja.vtt · video.mp4
                     │              │                   │
                     ▼              ▼                   │
             heatmap/SourceInfo   chat.load_chat        │      audio.audio_levels(video)
                     └──────┬───────┘                   │                │
                            ▼                           │                │
              highlights.detect_highlights ◄────────────┼────────────────┘
               (robust z · 가중합 · 이동평균 · 봉우리 · 채팅 지연 보정 · 병합 · 길이 제한)
                            │
                            ▼
              pipeline.make_clips ── 클립마다: slice_cues → write_ass(PlayRes = 출력 크기)
                            │                 ExportOptions(start, end, layout, subtitles)
                            │                 build_description + check_upload
                            ▼
            clip_XX.mp4 · clip_XX.ass · clip_XX.txt · clips.json
```

- **아바타 박스**(`--avatar auto`, `detect.py`): 프레임 12장을 뽑아 애니메 얼굴을 검출하고, 여러 프레임에서 같은 자리에 남는 얼굴을 아바타로 봐서 방송 하나에 고정 박스 하나를 정합니다. 프레임 단위 추적은 하지 않습니다. 전처리(letterbox) · 후처리(YOLO 출력 해석, NMS) · 군집 · 박스 계산은 numpy만 쓰는 순수 함수이고, onnxruntime은 `OnnxFaceDetector`를 만들 때만 import합니다. 프레임 추출은 `export.grab_frames`가 맡습니다.
- **채팅 정리**: `chat.load_chat`은 YouTube 다시보기에서 0초로 기록된 대기실 채팅을 보낸 시각(`timestampUsec` − 오프셋 = 방송 시작 시각)으로 가려 버립니다. `highlights`는 인사 · 작별(`ROUTINE`)을 채팅 신호에서 뺍니다. 둘 다 실제 아카이브에서 방송 시작 · 끝에 가짜 봉우리를 만들던 것입니다.
- **필터 순서**: `crop → fps → [layout 그래프] → scale → subtitles → extra → colorkey → 포맷별 처리`. 레이아웃은 `[pre] → [lay]` 레이블을 쓰는 서브그래프라 GIF 팔레트 등 뒤 단계와 그대로 이어집니다.
- **자막 시간**: `-ss`를 입력 옵션으로 쓰므로 필터가 보는 시간은 0부터 시작합니다. 그래서 자막은 `slice_cues`로 클립 기준 시간으로 옮겨서 씁니다(테스트로 자막이 정해진 시간에만 보이는지 확인).
- **자막 경로**: `filter_path()`가 ffmpeg의 두 단계 이스케이프(옵션 · 필터그래프)를 처리합니다. Windows `C:\` 경로와 `' [ ] , ; :`가 들어간 경로도 테스트합니다.
- **자막 크기**: 스타일 값은 짧은 변 1080px 기준이며 출력 크기에 비례해 조정됩니다. 세로 화면에서는 쇼츠 하단 UI를 피해 아래에서 약 20% 위에 둡니다.

### 하이라이트 창 (`gui/highlights.py`)

`stream2clip auto`와 같은 일을 창에서 합니다. 창은 설정을 모으고 그리기만 하며, 계산은 전부 코어 함수가 합니다.

```
파일 선택 ─► pipeline.find_highlights (작업 스레드: 채팅 읽기 → 음량 → 검출)
                     │ HighlightResult
                     ▼
   TimelineWidget ── 구간 끌기 ──► Highlight.start / end 를 직접 수정
        │ 선택                              │
        ▼                                  ▼
 export.grab_frames(layout=…)      pipeline.make_clips(체크한 구간, on_progress)
   레이아웃을 입힌 프레임 1장          진행률 → QProgressBar
```

- **타임라인**: 막대는 보이는 시간 범위를 균등하게 나눠 그 구간의 최고 점수를 그립니다(시간축과 어긋나지 않게). 긴 방송에서는 클립 하나가 몇 픽셀밖에 안 되므로 확대(휠 · 더블클릭)가 있고, 잡는 영역은 가장자리가 바깥쪽으로 넓어 좁은 구간도 가운데를 잡아 옮길 수 있습니다.
- **스레드**: 분석 · 미리보기 · 아바타 찾기 · 내보내기는 `threading.Thread`에서 돌고 결과는 Qt 시그널로 GUI 스레드에 돌아옵니다. 미리보기는 요청 번호를 붙여, 늦게 끝난 이전 요청이 화면을 덮지 않게 합니다.
- **미리보기**는 레이아웃만 입힌 정지 화면입니다. 자막은 내보낸 클립에서 확인합니다.

### VOD → 클립 (`stream2clip convert`)

`ExportOptions(start, end, crop, fps, width/height, transparent, ...)` → `build_export_command()` → ffmpeg 한 번. 필터 순서는 `crop → fps → scale → (format=rgba, colorkey) → 포맷별 처리(GIF 팔레트 / 픽셀 포맷)`입니다. yuv420 계열(MP4/WebM)은 짝수 크기로 맞춥니다.

## 포맷별 처리

| 포맷 | 코덱 | 투명 | 비고 |
|---|---|---|---|
| GIF | gif + palettegen/paletteuse | 1비트 (`reserve_transparent`, `alpha_threshold=128`) | 불투명은 `stats_mode=diff` + `diff_mode=rectangle`로 용량 절약 |
| WebP | libwebp_anim | `yuva420p` | 애니메이션 WebP는 ffprobe가 읽지 못해 테스트는 Pillow로 확인 |
| MP4 | libx264 `yuv420p`, `+faststart` | 없음 | 투명 요청 시 `ValueError` |
| WebM | libvpx-vp9 `yuva420p` | 있음 (`alpha_mode=1`) | 오디오 Opus |
| MOV | prores_ks 4444 `yuva444p10le` | 있음 | 영상 편집기 오버레이용 |
| APNG | apng `rgba` | 8비트 알파 | |

## 스레드

- GUI 스레드: Qt 이벤트, 캔버스 렌더, 커서 좌표 갱신(33ms 타이머)
- 하이라이트 창 작업 스레드: 분석, 미리보기 프레임, 아바타 찾기, 클립 내보내기(한 번에 하나, 미리보기만 따로)
- 녹화 스레드: 프레임 캡처 + ffmpeg stdin 쓰기 (mss 핸들은 스레드마다 따로 생성)
- 인코딩 스레드: 정지 후 내보내기. 결과는 Qt 시그널(`finished`/`failed`)로 GUI 스레드에 돌아옵니다.

## 테스트

| 파일 | 범위 |
|---|---|
| `tests/test_core.py` | Region/색/프레임, 크로마키, ffmpeg 빌더 |
| `tests/test_editor.py` | 도형별 렌더링, 직렬화 왕복, JSON 스키마, 되돌리기, 히트 테스트, 오버레이 |
| `tests/test_export_record.py` | 6개 포맷 내보내기, 구간·크롭, 투명 GIF/WebP/APNG 잔상 없음, WebM 알파, numpy↔ffmpeg 크로마키 일치, 실시간 녹화 |
| `tests/test_chat_sources.py` | 채팅 형식 4종, 실제 YouTube 다시보기 발췌본(익명화), 대기실 채팅 제거, 금액, yt-dlp 명령 · 쿠키, info · heatmap, 음량 곡선 |
| `tests/test_highlights.py` | 반응 분류(실제 채팅 어휘 포함), 인사 · 작별 제외, 심어 둔 장면 검출 · 지연 보정 · 병합 · 길이 제한, 음량/heatmap 단독, JSON · 타임라인 |
| `tests/test_clips.py` | 레이아웃 4종, 필터 경로 이스케이프, SRT/VTT/ASS, 자막 시간, 가이드라인 점검, 클립 파이프라인 |
| `tests/test_detect.py` | letterbox · YOLO 출력 해석 · NMS, 같은 자리에 남는 얼굴 고르기, 박스 모양, 모델 체크섬, `avatar` 명령과 `--avatar auto` |
| `tests/test_cli.py` | CLI 명령 (`auto` · `check` 포함) |
| `tests/test_gui.py` | 편집기 도구를 실제 마우스 이벤트로 조작, HiDPI 좌표 환산(소수 배율에서 선택 크기 일정), 클립보드 복사, 녹화 테두리가 영역을 덮지 않음 |
| `tests/test_gui_highlights.py` | 하이라이트 창: 타임라인 막대 · 구간 끌기 · 확대, 분석 → 미리보기 → 내보내기, 아바타 자동 찾기, 실패 표시 |
| `tests/test_gui_flow.py` | (디스플레이 필요) F8 캡쳐 → 편집기, F9 영역 선택 → 녹화 → 투명 GIF 결과 검증. Windows: OS 수준 F8/F9 입력으로 전역 단축키, `GetWindowRect`로 선택 영역 · 테두리 · REC 바의 물리 좌표, `SetCursorPos`로 커서 합성 위치 |
