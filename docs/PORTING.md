# 다른 오픈소스 영상 프로젝트에 이식하기

stream2clip은 단일 앱보다 필요한 부분만 가져다 쓰는 부품 묶음을 목표로 함. 각 층은 아래 방향으로만 의존하므로 필요한 부분만 선택하여 사용 가능

| 가져갈 것 | 필요한 모듈 | 외부 의존성 |
|---|---|---|
| ffmpeg 명령, 필터그래프 | `ffmpeg`, `chroma`, `geometry`, `color` | numpy, Pillow. 명령 생성 자체는 표준 라이브러리 수준 |
| 크로마키(투명 배경) 프레임 처리 | `chroma`, `frames` | numpy, Pillow |
| 주석(펜, 네모, 화살표, 글자, 모자이크, 투명, 자르기) | `editor` | numpy, Pillow |
| 실시간 녹화 | `record`, `capture` | ffmpeg 바이너리 추가. 화면 녹화는 mss 추가 |
| 편집기 위젯, 앱 | `gui` | PySide6 추가 |

공통 규약:

| 규약 | 내용 |
|:---:|---|
| 프레임 | `numpy.ndarray`, shape `(높이, 너비, 4)`, `uint8`, RGBA 순서. RGB와 흑백은 `stream2clip.frames.ensure_rgba()`로 변환 |
| 좌표 | 왼쪽 위가 원점인 정수 픽셀. 영역은 `Region(x, y, width, height)`, 문자열 표기는 `"x,y,w,h"` 또는 `"WxH+X+Y"` |

## 1. ffmpeg 기반 파이프라인에 붙이기

autoclip, FunClip, AI-Youtube-Shorts-Generator, biliup 등 ffmpeg를 호출하는 프로젝트는 하이라이트 구간마다 명령만 생성하여 사용. 이 모듈은 프로세스를 실행하지 않는 순수 함수

```python
from stream2clip.ffmpeg import ExportOptions, build_export_command, build_video_filter
from stream2clip.geometry import Region

for start, end in highlights:  # 다른 프로젝트가 찾은 구간
    opts = ExportOptions(format="gif", start=start, end=end, fps=15, width=480, crop=Region(640, 0, 640, 720))
    cmd = build_export_command("vod.mp4", f"clip_{start:.0f}.gif", opts)
    subprocess.run(cmd, check=True)

# 필터그래프 문자열만 필요하면 ([0:v] 입력 -> [v] 출력)
graph = build_video_filter(ExportOptions(format="webp", transparent=True, key_color="#00FF00"))
```

- `format`: `gif`, `webp`, `mp4`, `webm`, `mov`, `apng`. 투명 배경(`transparent=True`)은 MP4를 제외한 전체 포맷 지원. MP4로 요청하면 `ValueError`
- GIF는 `palettegen`, `paletteuse` 2단계를 1개 그래프로 처리. 투명 GIF는 `reserve_transparent`, `alpha_threshold` 사용. 움직이는 물체가 지나간 자리에 잔상이 남지 않음을 테스트로 확인
- 파이썬 외의 프로젝트는 CLI로 명령만 출력하여 사용: `stream2clip convert vod.mp4 -o clip.webp --start 1:00 --end 1:10 --transparent --print-command`

## 2. 프레임 단위로 크로마키 적용하기 (MoviePy, OpenCV, PyAV)

`chroma.colorkey_alpha()`는 ffmpeg `colorkey` 필터와 동일 수식(테스트 기준 오차 ±1 이내)이므로 미리보기와 최종 인코딩 결과가 일치

```python
from stream2clip.chroma import apply_colorkey, colorkey_alpha, colorkey_filter

rgba = apply_colorkey(frame_rgb, "#00FF00", similarity=0.12, blend=0.05)  # (h, w, 4)
mask = colorkey_alpha(frame_rgb, "#00FF00", 0.12, 0.05) / 255.0           # (h, w) 0..1
colorkey_filter("#00FF00", 0.12, 0.05)                                   # 'colorkey=0x00FF00:0.12:0.05'
```

| 대상 | 적용 방법 |
|:---:|---|
| MoviePy | 마스크 클립에 `colorkey_alpha(...) / 255` 사용. 색 처리는 v2 `clip.image_transform(fn)`(v1은 `clip.fl_image(fn)`)에 전달 |
| OpenCV | 프레임이 BGR이므로 `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` 후 전달 |
| PyAV | `frame.to_ndarray(format="rgba")`를 그대로 전달 |

## 3. 주석을 다른 도구와 주고받기

주석은 원본을 변경하지 않는 JSON(`stream2clip.annotation/v1`). 스키마: [`src/stream2clip/schemas/annotation.v1.schema.json`](../src/stream2clip/schemas/annotation.v1.schema.json)

```json
{
  "schema": "stream2clip.annotation/v1",
  "canvas": {"width": 1920, "height": 1080},
  "crop": [640, 0, 640, 720],
  "items": [
    {"type": "arrow", "start": [700, 600], "end": [900, 400], "color": "#FF4F8B", "width": 6},
    {"type": "text", "position": [720, 80], "text": "레전드 장면", "color": "#15131F", "size": 36, "background": "#FFD84D"},
    {"type": "mosaic", "rect": [1000, 900, 300, 80], "block": 12},
    {"type": "colorkey", "color": "#00FF00", "similarity": 0.1, "blend": 0}
  ]
}
```

- 렌더링: `stream2clip.editor.render(base_image, state_from_dict(data))` 또는 CLI `stream2clip annotate frame.png --annotations a.json -o out.png`
- 오버레이 PNG: `Document.render_overlay()` 또는 `annotate --overlay`가 주석만 있는 투명 PNG 생성. Kdenlive, Shotcut 트랙이나 OBS 이미지 소스에서 원본 위에 배치. 영역 투명화와 색상 키는 오버레이로 표현할 수 없어 제외
- 도형 종류: `pen`, `highlighter`, `rect`, `arrow`, `text`, `mosaic`, `transparent`, `colorkey`. 항목은 순서대로 적용하며 자르기(`crop`)는 마지막에 적용

## 4. 내 프레임 소스를 녹화하기 (게임 엔진, 아바타 렌더러, OBS 등)

`Recorder`는 RGBA 배열을 제공하는 모든 소스를 녹화. 실시간 간격을 유지하며(느린 프레임은 반복), 무손실 FFV1 중간 파일에 알파를 보존한 후 원하는 포맷으로 여러 번 내보내기 가능

```python
from stream2clip.capture import ArrayBackend
from stream2clip.ffmpeg import ExportOptions
from stream2clip.geometry import Region
from stream2clip.record import Recorder

def render_avatar(t: float):  # 경과 시간(초) -> (h, w, 4) uint8 RGBA
    ...

rec = Recorder(Region(0, 0, 1080, 1920), fps=30, backend_factory=lambda: ArrayBackend(render_avatar), max_duration=10)
rec.start(); rec.wait()
recording = rec.stop()
recording.export("avatar.webm", ExportOptions(format="webm", transparent=True, key_color=None))  # 프레임 자체의 알파를 그대로 유지
recording.export("avatar.gif", ExportOptions(format="gif", fps=15, width=540))
recording.discard()
```

`frame_filter=`로 프레임별 처리(워터마크, 얼굴 모자이크, 실시간 크로마키) 추가 가능

## 5. 플러그인: 캡처 백엔드, OCR, 번역기

포크 없이 기능을 추가하는 방법

| 방법 | 용도 |
|:---:|---|
| (a) 실행 중 등록 | 호스트 앱에 넣는 경우. 가장 간단 |
| (b) entry point | 별도 패키지로 배포하는 경우 |
| (c) 파일 1개 | 자막 번역기만 연결하는 경우. 패키지와 등록 불필요 |

**(a) 실행 중 등록**

```python
from stream2clip.plugins import register_capture_backend, register_text_detector, register_translator
from stream2clip.translate import CallableTranslator
from stream2clip.translate.tesseract import TesseractDetector

register_text_detector("tesseract", lambda: TesseractDetector(lang="jpn+eng"))
register_translator("my-llm", lambda: CallableTranslator(lambda texts, target, source: my_llm_translate(texts, target)))
register_capture_backend("obs", lambda: MyObsBackend())
```

**(b) entry point**

```toml
[project.entry-points."stream2clip.capture_backends"]
obs = "my_pkg.obs:ObsBackend"

[project.entry-points."stream2clip.text_detectors"]
paddle = "my_pkg.ocr:make_detector"

[project.entry-points."stream2clip.translators"]
deepl = "my_pkg.deepl:make_translator"

[project.entry-points."stream2clip.face_detectors"]
mine = "my_pkg.faces:make_detector"
```

**(c) 번역기를 파일 1개로 연결**: 함수가 있는 파일 지정

```python
# my_translator.py
def translate(texts, target, source=None):
    """texts와 같은 길이, 같은 순서의 번역을 돌려준다."""
    return [my_service(text, target) for text in texts]
```

```bash
stream2clip clips video.mp4 --highlights h.json --subtitles ja.vtt --translate ko --translator my_translator.py
```

- `file.py:이름` 또는 `package.module:이름`으로 다른 이름 지정 가능
- 지정 대상: 함수, `translate` 메서드가 있는 클래스, 해당 클래스의 객체(`translation.load_translator`)
- `STREAM2CLIP_TRANSLATOR` 환경 변수로 기본 번역기 지정
- 앱의 하이라이트 창에서도 동일 파일 선택 가능
- 줄 수가 다른 응답은 자막 시각이 어긋나므로 오류로 처리
- 예제: [`examples/translators/openai_compatible.py`](../examples/translators/openai_compatible.py)

인터페이스는 전부 `typing.Protocol`(상속 불필요)

```python
class CaptureBackend(Protocol):
    name: str
    def virtual_screen(self) -> Region: ...           # 물리 픽셀
    def monitors(self) -> list[Region]: ...
    def grab(self, region: Region | None = None) -> np.ndarray: ...  # (h, w, 4) RGBA
    def close(self) -> None: ...

class TextDetector(Protocol):
    def detect(self, image: PIL.Image.Image) -> list[TextBlock]: ...  # TextBlock(region, text)

class Translator(Protocol):
    def translate(self, texts: Sequence[str], target: str, source: str | None = None) -> list[str]: ...
```

자막 번역(`--translate`)도 동일한 번역기 사용. 텍스트 목록을 받아 같은 개수의 번역을 반환하는 구조

```python
from stream2clip.plugins import register_translator
from stream2clip.subtitles import load_subtitles
from stream2clip.translate import CallableTranslator
from stream2clip.translation import Glossary, translate_cues

translator = CallableTranslator(lambda texts, target, source: my_translate(texts, target))
register_translator("mine", lambda: translator)                     # 이후 CLI의 --translate ko 가 이 번역기를 사용

cues = translate_cues(load_subtitles("clip.vtt"), translator, target="ko", source="ja",
                      glossary=Glossary({"兎田ぺこら": "우사다 페코라"}), bilingual=True)
```

편집기의 번역 버튼:

- 등록된 첫 번째 OCR과 번역기 쌍 사용
- 번역 결과는 일반 주석(`rect` 배경과 `text`)으로 추가되므로 수정, 되돌리기, JSON 저장 가능
- stream2clip 자체는 외부 번역 서비스를 호출하지 않음

## 6. PySide6 / PyQt 앱에 편집기 넣기

```python
from stream2clip.editor import Document
from stream2clip.gui.app import create_app        # 테마, 아이콘을 적용한 QApplication
from stream2clip.gui.editor import EditorWindow    # 또는 gui.canvas.EditorCanvas 위젯만

app = create_app()
win = EditorWindow(Document(pil_image))
win.show()
app.exec()
```

| 위젯 | 용도 |
|:---:|---|
| `EditorCanvas(document, ToolState())` | 툴바 없이 캔버스만 사용. 변경 시 `changed` 시그널 발생 |
| `gui.highlights.TimelineWidget` | 하이라이트 타임라인만 사용. `set_result(result)`로 `HighlightResult`를 전달하면 막대와 구간을 표시. 사용자가 구간을 끌면 `result.highlights`의 `start`, `end`가 변경되고 `changed(index)` 발생 |
| `HighlightsWindow()` | 하이라이트 창 전체 |

## 7. 하이라이트, 레이아웃, 자막만 가져가기 (v0.2)

다운로드와 편집 기능이 이미 있는 프로젝트(autoclip, FunClip, biliup 등)는 구간 검출 또는 세로 레이아웃만 분리하여 사용 가능

```python
from stream2clip.chat import load_chat
from stream2clip.highlights import HighlightConfig, detect_highlights

msgs = load_chat("VIDEO_ID.live_chat.json")          # 또는 CSV: time,author,text[,amount] / CHZZK, SOOP 다시보기 채팅
result = detect_highlights(msgs, duration=3 * 3600, config=HighlightConfig(top=5, chat_delay=10))
for h in result.highlights:
    print(h.rank, h.start, h.end, h.reasons)        # 다른 파이프라인의 컷 리스트로 사용
```

```python
from stream2clip.ffmpeg import build_video_filter, ExportOptions
from stream2clip.geometry import Region
from stream2clip.layouts import VerticalLayout

layout = VerticalLayout("stack", avatar=Region(1280, 0, 640, 720))
print(layout.graph("[0:v]", "[v]"))  # 9:16 필터그래프 조각만
print(build_video_filter(ExportOptions(format="mp4", layout=layout, subtitles="clip.ass")))
```

```python
from stream2clip.subtitles import load_subtitles, slice_cues, write_ass

cues = slice_cues(load_subtitles("VIDEO_ID.ja.vtt"), 3723, 3778)   # 클립 기준 시간으로
write_ass(cues, "clip.ass", play_res=(1080, 1920))                  # 카라오케 \k 태그
```

아바타 박스만 필요한 경우 `detect` 사용. 검출기는 `detect(image) -> list[Face]` 메서드만 있으면 되므로 다른 얼굴 검출 모델로 교체 가능

```python
from stream2clip.detect import OnnxFaceDetector, suggest_avatar_for_video
from stream2clip.layouts import VerticalLayout

found = suggest_avatar_for_video("vod.mp4", OnnxFaceDetector())      # 프레임 12장, CPU로 몇 초
if found:                                                             # 못 찾으면 None
    layout = VerticalLayout("stack", avatar=found.region)             # found.hits / found.frames = 얼굴이 나온 프레임 수
```

```python
from stream2clip.plugins import register_face_detector

register_face_detector("mine", lambda: MyDetector())                 # --avatar auto 가 이 검출기를 사용
```

LLM 기반 하이라이트 판정을 사용하는 프로젝트는 `HighlightResult.signals`(신호별 z-점수 배열)와 각 구간의 `reasons`를 프롬프트 자료로 전달 가능

## 8. 라이선스 메모

| 대상 | 라이선스 및 조건 |
|:---:|---|
| stream2clip | Apache-2.0. 코어(`gui` 제외)는 numpy(BSD), Pillow(MIT-CMU)만 사용 |
| GUI | PySide6는 LGPLv3. 동적 링크(pip 설치)로 사용하면 호스트 프로젝트 라이선스에 제약 없음 |
| ffmpeg | 바이너리를 외부 프로세스로 호출만 수행. 배포 시 사용하는 ffmpeg 빌드(LGPL 또는 GPL, libx264는 GPL)의 조건 적용 |
| 아바타 검출 | onnxruntime(MIT)으로 deepghs/anime_face_detection 모델(MIT)의 ONNX 파일만 실행. 모델 파일은 저장소에 포함하지 않으며 최초 사용 시 다운로드 |
| 선택 의존성 | yt-dlp(Unlicense), faster-whisper(MIT, 모델 가중치는 각 모델 라이선스), libass(ISC, ffmpeg에 포함) |
| 미사용 코드 | 레퍼런스 조사에서 AGPL로 확인된 클리퍼(supoclip, Clips Kitty, hotclip)와 ultralytics YOLO의 코드는 가져오지 않음 |
