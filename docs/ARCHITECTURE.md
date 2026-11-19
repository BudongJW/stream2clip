# 아키텍처

## 설계 원칙

| 원칙 | 내용 |
|:---:|---|
| 코어와 앱 분리 | `gui/`를 삭제해도 나머지는 그대로 동작. GUI는 코어 위의 얇은 층 |
| 순수 함수 우선 | ffmpeg 명령, 필터그래프, 크로마키 수식, 주석 렌더링은 입력과 출력이 정해진 함수. 프로세스 실행(`export.py`, `record/`)은 그 위의 별도 층 |
| 비파괴 편집 | 원본 이미지는 유지하고 주석은 불변(frozen) 데이터클래스 목록과 자르기 영역으로 저장. 되돌리기는 상태 스냅샷 간 이동 |
| 미리보기와 결과물의 일치 | 편집기의 투명 도구와 녹화의 투명 배경은 동일한 크로마키 수식(ffmpeg `colorkey`) 사용 |
| 플러그인 확장 | 캡처 백엔드, OCR, 번역기는 `Protocol`과 entry point로 교체 |

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
                                 geometry, color, frames, plugins
```

## 데이터 흐름

### 영역 캡쳐, 편집

1. `ScreenSelector`가 가상 화면 전체를 mss로 먼저 캡쳐하고, 정지된 화면 위에서 드래그 입력을 수신(보이는 그대로 캡쳐)
2. Qt 논리 좌표의 선택 영역을 스크린샷과 가상 화면의 비율로 물리 픽셀 `Region`으로 변환(HiDPI 대응). 위치와 크기를 각각 반올림하며 `n.5`는 올림
3. 잘라낸 PIL 이미지로 `Document`를 생성하여 `EditorWindow`에 전달
4. 캔버스는 확정된 주석을 Pillow로 렌더링하여 캐시하고, 드래그 중인 도형만 QPainter로 미리 표시. 마우스를 놓으면 `Document.add()`로 새 상태를 히스토리에 추가

좌표 변환 관련 사항:

- 반올림 방식은 Qt가 소수 배율(125%, 150%)에서 창을 배치하는 방식과 동일. 선택 크기가 위치에 따라 달라지지 않음
- 창의 논리 영역을 선택하면 해당 창의 물리 픽셀과 정확히 일치(Windows 125% 실기기에서 `GetWindowRect`와 비교하여 확인)

### 움짤 녹화 (F9)

```
F9 ─► 영역 선택 ─► (200ms: 오버레이가 화면에서 사라질 시간) ─► Recorder.start()
                                                      │
       캡처 스레드: grab(region), 커서 합성, frame_filter, rawvideo RGBA
                                                      │ stdin
                                       ffmpeg -c:v ffv1 -pix_fmt bgra  (무손실 .mkv)
F9 ─► Recorder.stop() ─► Recording ─► export(GIF/WebP/MP4/WebM/MOV/APNG, 투명 배경 옵션)
```

| 항목 | 내용 |
|:---:|---|
| 타이밍 | 캡처 루프는 벽시계 기준. 캡처가 느리면 직전 프레임을 반복하여 재생 속도를 실제와 동일하게 유지 |
| 중간 파일 | FFV1, Matroska로 알파를 보존한 상태로 녹화하고 정지 후 원하는 포맷으로 변환. 녹화 중 GIF 팔레트 계산이 불필요하며 동일 녹화본을 여러 포맷으로 재내보내기 가능. VOD 변환과 동일한 `export()` 경로 사용 |
| 녹화 테두리 | 영역 바깥에 불투명한 얇은 창 4개로 표시. 반투명 창 1개로 덮는 방식은 컴포지터가 없는 X11에서 검게 칠해지고 일부 캡처 API에서 녹화 결과에 섞이는 문제가 있음 |
| 커서 | 화면 캡처 API는 대부분 커서를 제외하므로 직접 합성. Windows는 `GetCursorPos`, 그 외에는 GUI 스레드가 `QCursor.pos()`를 물리 좌표로 변환하여 공유. 화살표 크기는 `Recorder(cursor_scale=)`로 화면 배율(1.25, 1.5)에 맞춤 |
| 전역 단축키 | Windows는 `RegisterHotKey(NULL, ...)`로 등록하고 Qt 네이티브 이벤트 필터에서 스레드 메시지 `WM_HOTKEY` 수신. 런처가 숨겨진 상태에서 다른 프로그램이 앞에 있어도 F9로 정지(실기기에서 OS 수준 키 입력으로 확인) |

### 방송 클립 자동화 (`stream2clip auto`)

```
fetch (yt-dlp) ─► info.json, <id>.live_chat.json, <id>.ja.vtt, video.mp4
                     │              │                   │
                     ▼              ▼                   │
             heatmap/SourceInfo   chat.load_chat        │      audio.audio_levels(video)
                     └──────┬───────┘                   │                │
                            ▼                           │                │
              highlights.detect_highlights ◄────────────┼────────────────┘
               (robust z, 가중합, 이동평균, 봉우리, 채팅 지연 보정, 병합, 길이 제한)
                            │
                            ▼
              pipeline.make_clips ── 클립마다: slice_cues, write_ass(PlayRes = 출력 크기)
                            │                 ExportOptions(start, end, layout, subtitles)
                            │                 build_description + check_upload
                            ▼
            clip_XX.mp4, clip_XX.ass, clip_XX.txt, clips.json
```

| 구성 | 모듈 | 내용 |
|:---:|:---:|---|
| 아바타 박스 | `detect.py` | 프레임 12장에서 애니메 얼굴을 검출하고 여러 프레임의 동일 위치에 유지되는 얼굴을 아바타로 판정하여 방송 1개에 고정 박스 1개 결정. 프레임 단위 추적 미수행. 전처리(letterbox), 후처리(YOLO 출력 해석, NMS), 군집, 박스 계산은 numpy만 사용하는 순수 함수이며 onnxruntime은 `OnnxFaceDetector` 생성 시에만 import. 프레임 추출은 `export.grab_frames` 담당 |
| 자막 번역 | `translation.py` | `make_clips`가 클립 자막 생성 후 `translate_cues`로 번역기(플러그인)에 전달. 용어집은 번역 전후에 문자열을 치환하는 단순 방식이므로 번역기 종류와 무관. 번역 자막에는 단어 시각 없음 |
| 노래 구간, 웃음소리 | `audio.py` | `singing_sections`는 소리가 끊기지 않고(음량 변화가 작고) 음을 길게 유지하는 구간 검출. `laughter_levels`는 크고 초당 3.5~8회 끊어지는 소리에 점수를 주는 실험 신호이며, 평균에 포함하지 않고 점수에 가산만 수행(`BONUS_SIGNALS`). 사용 시 다른 하이라이트가 감소하지 않도록 하기 위함 |
| OBS | `obs.py` | obs-websocket 5 클라이언트. `SaveReplayBuffer` 후 `ReplayBufferSaved` 이벤트(없으면 `GetLastReplayBufferReplay`)로 파일 경로를 받아 `export`로 변환 |
| 라이브 모드 | `live.py` | `SurgeDetector`가 5초 구간마다 채팅 신호를 직전 15분의 구간과 비교(`highlights.robust_z` 사용). 구간은 확정된 이후에만 판정하며 도착 시각이 아닌 메시지에 기록된 시각 기준. 채팅 입력은 `read()`가 새 메시지를 반환하는 객체(`FileFollower`, `YtDlpLiveChat`), 발동 후 동작은 호출 가능한 객체 1개(`ReplayClipper`)이므로 교체 가능. PySide6, websocket, yt-dlp를 import하지 않음 |
| YouTube 업로드 | `upload.py` | 요청 본문을 만드는 순수 함수(`video_resource`)와 실제 전송(`upload_video`)을 분리. 공개 범위 기본값은 비공개 |
| CHZZK, SOOP | `sources.py`, `chat.py` | 채팅을 yt-dlp 대신 각 플랫폼의 다시보기 API에서 수신(`fetch_chzzk_chat`, `fetch_soop_chat`, 표준 라이브러리 `urllib`). 응답 해석은 순수 함수 `parse_chzzk`, `parse_soop`. 저장 형식은 작성자를 해시한 정규화 JSONL 1종. 네트워크 함수는 `get`을 교체할 수 있어 테스트가 실제 요청을 보내지 않음 |
| 채팅 정리 | `chat.py`, `highlights.py` | `load_chat`은 YouTube 다시보기에서 0초로 기록된 대기실 채팅을 보낸 시각(`timestampUsec` − 오프셋 = 방송 시작 시각)으로 판별하여 제외. `highlights`는 인사, 작별(`ROUTINE`)을 채팅 신호에서 제외. 둘 다 실제 아카이브에서 방송 시작과 종료 시점에 가짜 봉우리를 만들던 요인 |

필터 및 자막 처리:

| 항목 | 내용 |
|:---:|---|
| 필터 순서 | `crop, fps, [layout 그래프], scale, subtitles, extra, colorkey, 포맷별 처리`. 레이아웃은 `[pre], [lay]` 레이블을 사용하는 서브그래프이므로 GIF 팔레트 등 이후 단계와 그대로 연결 |
| 자막 시간 | `-ss`를 입력 옵션으로 사용하므로 필터 기준 시간은 0부터 시작. 자막은 `slice_cues`로 클립 기준 시간으로 이동(자막의 표시 시간을 테스트로 확인) |
| 자막 경로 | `filter_path()`가 ffmpeg의 2단계 이스케이프(옵션, 필터그래프) 처리. Windows `C:\` 경로와 `' [] , ; :`가 포함된 경로도 테스트 |
| 자막 크기 | 스타일 값은 짧은 변 1080px 기준이며 출력 크기에 비례하여 조정. 세로 화면에서는 쇼츠 하단 UI를 피하여 아래에서 약 20% 위에 배치 |

### 하이라이트 창 (`gui/highlights.py`)

`stream2clip auto`와 동일한 작업을 창에서 수행. 창은 설정 수집과 표시만 담당하며 계산은 전부 코어 함수가 수행

```
파일 선택 ─► pipeline.find_highlights (작업 스레드: 채팅 읽기, 음량, 검출)
                     │ HighlightResult
                     ▼
   TimelineWidget ── 구간 끌기 ──► Highlight.start / end 를 직접 수정
        │ 선택                              │
        ▼                                  ▼
 export.grab_frames(layout=)      pipeline.make_clips(체크한 구간, on_progress)
   레이아웃을 입힌 프레임 1장          진행률, QProgressBar
```

| 항목 | 내용 |
|:---:|---|
| 타임라인 | 막대는 표시 중인 시간 범위를 균등 분할하여 각 구간의 최고 점수를 표시(시간축과의 불일치 방지). 긴 방송에서는 클립 1개가 수 픽셀에 불과하므로 확대(휠, 더블클릭) 제공. 잡는 영역은 가장자리가 바깥쪽으로 넓어 좁은 구간도 가운데를 잡아 이동 가능 |
| 스레드 | 분석, 미리보기, 아바타 찾기, 내보내기는 `threading.Thread`에서 실행하고 결과는 Qt 시그널로 GUI 스레드에 전달. 미리보기는 요청 번호를 부여하여 늦게 끝난 이전 요청이 화면을 덮지 않도록 처리 |
| 미리보기 | 레이아웃만 적용한 정지 화면. 자막은 내보낸 클립에서 확인 |
| 번역, 노래, 웃음 | 창은 선택한 값을 코어에 전달: `find_highlights(laughter=...)`, `audio.singing_sections`, `highlights.mark_singing`, `translation.get_translator(이름 또는 file.py)`, `make_clips(subtitle_translator=...)` |
| 업로드 창 | `gui/upload.py`가 `upload.video_resource`로 본문을 만들고 작업 스레드에서 `upload.upload_video` 호출. 공개 범위는 저장하지 않아 매번 비공개에서 시작. 런처의 리플레이 버튼은 `obs.replay_to_clip` 호출 |
| 화면 언어 | `i18n.py`, `locales/*.json`. 코드의 문구는 한국어이며 `tr()`이 현재 언어의 번역을 조회(없으면 한국어 유지). 표 형태의 상수는 모듈을 가져올 때 번역되므로 앱은 창 모듈을 가져오기 전에 언어를 결정(`gui/app.py`의 `apply_saved_language`). 따라서 언어 변경은 다음 실행부터 적용 |
| 설정 저장 | `gui/settings.py`. 창마다 1개 구역을 가진 JSON 파일 1개. 읽을 때 값의 형식과 범위를 확인하여 사용할 수 없는 값은 건너뛰며, 파일이 손상되었거나 폴더에 쓸 수 없어도 앱은 기본값으로 동작. 비밀번호 미저장. 테스트는 `STREAM2CLIP_CONFIG_DIR`로 빈 폴더 사용 |
| 마스코트 | 상태 줄의 키리는 창의 상태(`set_mood`: wink, focus, laugh, cut, surprised)를, 목록의 얼굴은 `mood_for(highlight)`가 `stats["react_*"]`에서 가장 많은 반응을 선택하여 표시. 이미지는 `gui/qt.py`의 `mascot()`이 화면 배율에 맞춰 로드 |

### VOD 클립 (`stream2clip convert`)

- 절차: `ExportOptions(start, end, crop, fps, width/height, transparent, ...)`, `build_export_command()`, ffmpeg 1회 실행
- 필터 순서: `crop, fps, scale, (format=rgba, colorkey), 포맷별 처리(GIF 팔레트 / 픽셀 포맷)`
- yuv420 계열(MP4, WebM)은 짝수 크기로 조정

## Windows 실행 파일 (`packaging/`)

`packaging/build_windows.py`가 PyInstaller로 `stream2clip-gui.exe`(창)와 `stream2clip.exe`(콘솔)를 라이브러리를 공유하는 한 폴더에 생성하고 zip으로 묶음. `--installer` 지정 시 Inno Setup으로 설치 프로그램 추가 생성

| 항목 | 빌드된 프로그램의 동작 |
|:---:|---|
| ffmpeg | `ffmpeg.find_ffmpeg()`, `find_ffprobe()`는 환경 변수 다음으로 실행 파일과 같은 폴더를 우선 확인하고, 없으면 PATH 확인 |
| yt-dlp | `python -m yt_dlp`를 사용할 수 없으므로 `stream2clip.exe yt-dlp ...`로 실행(`cli.main`이 해당 인자를 yt-dlp에 그대로 전달) |
| 화면 언어 | 설치 프로그램이 선택한 언어를 프로그램과 같은 폴더의 `language.txt`에 기록하고 앱이 `i18n.installed_language()`로 조회 |
| 용량 | 사용하지 않는 Qt 모듈(WebEngine, QML, Multimedia 등)과 받아쓰기 관련 패키지 제외 |

`.github/workflows/package.yml`이 Windows 러너에서 빌드한 후 파이썬과 ffmpeg가 PATH에 없는 상태로 두 프로그램을 실행하여 확인하고, 설치 프로그램을 3개 언어로 자동 설치 및 제거

## 포맷별 처리

| 포맷 | 코덱 | 투명 | 비고 |
|:---:|---|---|---|
| GIF | gif, palettegen/paletteuse | 1비트 (`reserve_transparent`, `alpha_threshold=128`) | 불투명은 `stats_mode=diff`, `diff_mode=rectangle`로 용량 절감 |
| WebP | libwebp_anim | `yuva420p` | 애니메이션 WebP는 ffprobe가 읽지 못하므로 테스트는 Pillow로 확인 |
| MP4 | libx264 `yuv420p`, `+faststart` | 미지원 | 투명 요청 시 `ValueError` |
| WebM | libvpx-vp9 `yuva420p` | 지원 (`alpha_mode=1`) | 오디오 Opus |
| MOV | prores_ks 4444 `yuva444p10le` | 지원 | 영상 편집기 오버레이용 |
| APNG | apng `rgba` | 8비트 알파 | 무손실 |

## 스레드

| 스레드 | 역할 |
|:---:|---|
| GUI 스레드 | Qt 이벤트, 캔버스 렌더, 커서 좌표 갱신(33ms 타이머) |
| 하이라이트 창 작업 스레드 | 분석, 미리보기 프레임, 아바타 찾기, 클립 내보내기. 동시에 1개만 실행하며 미리보기만 별도 |
| 녹화 스레드 | 프레임 캡처, ffmpeg stdin 쓰기. mss 핸들은 스레드마다 별도 생성 |
| 인코딩 스레드 | 정지 후 내보내기. 결과는 Qt 시그널(`finished`, `failed`)로 GUI 스레드에 전달 |
| 라이브 모드 스레드 | 채팅 감시와 급증 판정, 리플레이 저장. 결과는 Qt 시그널로 런처에 전달 |

## 테스트

테스트 실행 방법과 파일별 범위: [TESTING.md](TESTING.md)
