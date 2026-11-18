# 기여 안내

stream2clip에 관심 가져 주셔서 고맙습니다. 버그 제보, 문서 수정, 기능 제안 모두 환영합니다.

## 개발 환경

```bash
git clone https://github.com/BudongJW/stream2clip
cd stream2clip
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS · Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.10 이상과 ffmpeg(ffprobe 포함)가 필요합니다. 기능별 추가 패키지는 README의 [설치](README.md#-설치)에 있습니다.

## 확인하고 보내기

```bash
ruff check .
pytest -q
```

- Windows에서 `pytest`를 그냥 실행하면 창을 띄우고 F8/F9를 실제로 누릅니다. 조용히 돌리려면 `QT_QPA_PLATFORM=offscreen`을 지정하세요.
- 새 기능에는 테스트를 함께 넣어 주세요. 외부 서비스(OBS, YouTube, 번역 서비스 등)는 테스트에서 가짜로 대신하고, 실제 서비스로 확인했는지 여부를 PR에 적어 주세요.
- 사용법이 바뀌면 README(기능 표 · 로드맵 · 테스트 수 배지)와 `CHANGELOG.md`, 필요하면 `docs/`도 함께 고칩니다.

## 지키는 원칙

자세한 설명은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)와 [docs/PORTING.md](docs/PORTING.md)에 있습니다.

- **코어와 앱 분리**: `gui/` 밖의 코드는 numpy와 Pillow에만 의존하고 PySide6를 가져오지 않습니다.
- **`ffmpeg.py`는 명령을 만들기만** 합니다. 실행은 `export.py`와 `record/`가 합니다.
- **프레임은 `(h, w, 4)` uint8 RGBA**, 좌표는 물리 픽셀 `Region(x, y, w, h)`입니다.
- **주석 JSON은 스키마 버전**을 가집니다. 형식을 바꾸면 스키마와 버전을 함께 올립니다.
- **확장은 플러그인으로**: 번역 서비스 같은 외부 서비스는 본체에 넣지 않고 `plugins.py`의 entry point나 `--translator 파일.py`로 연결합니다.
- **기획사 가이드라인 프로필은 체크리스트**이며 법적 판단이 아닙니다. 공식 원문(주소와 개정일)을 확인하지 않은 규칙은 추가하지 않습니다.
- **다른 사람의 방송 화면 · 게임 화면을 저장소에 넣지 않습니다.** 문서 이미지와 테스트 자료는 `assets/brand`의 그림이나 합성 데이터로 만듭니다. 채팅 자료는 닉네임을 지워서 넣습니다.

## 브랜치와 커밋

- `main`에 직접 푸시하지 않습니다. `feature/<주제>` 브랜치에서 작업하고 PR로 보냅니다.
- 커밋 메시지는 영어, 제목은 명령형으로 씁니다(예: `Add CHZZK replay chat fetcher`). 본문에는 무엇을 왜 바꿨는지 적습니다.
- PR 설명에는 바뀐 것, 확인한 것, 확인하지 못한 것을 나눠 적어 주세요.

## 버그 제보에 넣으면 좋은 것

- 운영체제와 화면 배율(예: Windows 11, 125%), 모니터 수
- `stream2clip --version`, `ffmpeg -version` 첫 줄
- 실행한 명령과 출력 전체. 방송 주소가 필요하면 공개 다시보기만 적어 주세요.

## 보안 문제

공개 이슈로 올리지 말고 [SECURITY.md](SECURITY.md)의 방법으로 알려 주세요.

## 라이선스

보내 주신 기여는 이 저장소의 [Apache-2.0](LICENSE) 라이선스로 배포됩니다.
