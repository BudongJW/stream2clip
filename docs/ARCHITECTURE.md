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
            │ launcher  selector  editor/canvas  recording(F9)  hotkeys  theme       │
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
2. Qt 논리 좌표의 선택 영역을 스크린샷/가상 화면 비율로 **물리 픽셀** `Region`으로 바꿉니다(HiDPI 대응).
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
- **커서**: 화면 캡처 API는 대부분 커서를 빼므로 직접 합성합니다. Windows는 `GetCursorPos`, 그 외에는 GUI 스레드가 `QCursor.pos()`를 물리 좌표로 바꿔 공유합니다.

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
- 녹화 스레드: 프레임 캡처 + ffmpeg stdin 쓰기 (mss 핸들은 스레드마다 따로 생성)
- 인코딩 스레드: 정지 후 내보내기. 결과는 Qt 시그널(`finished`/`failed`)로 GUI 스레드에 돌아옵니다.

## 테스트

| 파일 | 범위 |
|---|---|
| `tests/test_core.py` | Region/색/프레임, 크로마키, ffmpeg 빌더 |
| `tests/test_editor.py` | 도형별 렌더링, 직렬화 왕복, JSON 스키마, 되돌리기, 히트 테스트, 오버레이 |
| `tests/test_export_record.py` | 6개 포맷 내보내기, 구간·크롭, 투명 GIF/WebP/APNG 잔상 없음, WebM 알파, numpy↔ffmpeg 크로마키 일치, 실시간 녹화 |
| `tests/test_cli.py` | CLI 명령 |
| `tests/test_gui.py` | 편집기 도구를 실제 마우스 이벤트로 조작, HiDPI 좌표 환산, 녹화 테두리가 영역을 덮지 않음 |
| `tests/test_gui_flow.py` | (디스플레이 필요) F8 캡쳐 → 편집기, F9 영역 선택 → 녹화 → 투명 GIF 결과 검증 |
