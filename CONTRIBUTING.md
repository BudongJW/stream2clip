# 기여 안내

버그 제보, 문서 수정, 기능 제안 접수. 절차와 기준은 아래와 같음

## 개발 환경

```bash
git clone https://github.com/BudongJW/stream2clip
cd stream2clip
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS, Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

- 요구 사항: Python 3.10 이상, ffmpeg(ffprobe 포함)
- 기능별 추가 패키지: README의 [설치](README.md#설치)

## 제출 전 확인

```bash
ruff check .
pytest -q
```

| &numsp;&numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp;&numsp; | 기준 |
|:---:|---|
| 테스트 실행 | Windows에서 `pytest`를 옵션 없이 실행하면 창을 표시하고 F8, F9를 실제로 입력. 화면 없이 실행하려면 `QT_QPA_PLATFORM=offscreen` 지정 |
| 신규 기능 | 테스트 포함. 외부 서비스(OBS, YouTube, 번역 서비스 등)는 테스트에서 가짜 구현으로 대체하고, 실제 서비스 검증 여부를 PR에 기재 |
| 문서 | 사용법 변경 시 README(기능 표, 로드맵, 테스트 수 배지), `CHANGELOG.md`, 필요 시 `docs/`를 함께 수정 |

테스트 구성과 파일별 범위: [docs/TESTING.md](docs/TESTING.md)

## 설계 원칙

상세 설명: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PORTING.md](docs/PORTING.md)

| &numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;원&NoBreak;칙&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| 코어와 앱 분리 | `gui/` 밖의 코드는 numpy와 Pillow에만 의존하며 PySide6를 import하지 않음 |
| 명령 생성과 실행 분리 | `ffmpeg.py`는 명령 생성만 담당. 실행은 `export.py`와 `record/`가 담당 |
| 프레임과 좌표 | 프레임은 `(h, w, 4)` uint8 RGBA, 좌표는 물리 픽셀 `Region(x, y, w, h)` |
| 주석 JSON | 스키마 버전 보유. 형식 변경 시 스키마와 버전을 함께 갱신 |
| 플러그인 확장 | 번역 서비스 등 외부 서비스는 본체에 포함하지 않고 `plugins.py`의 entry point 또는 `--translator 파일.py`로 연결 |
| 가이드라인 프로필 | 점검 목록이며 법적 판단이 아님. 공식 원문(주소와 개정일)을 확인하지 않은 규칙은 추가 금지 |
| 제3자 화면 | 타인의 방송 화면, 게임 화면은 저장소에 포함 금지. 문서 이미지와 테스트 자료는 `assets/brand`의 그림 또는 합성 데이터로 제작. 채팅 자료는 닉네임 제거 후 포함 |

## 화면 문구 추가

1. 앱 화면에 표시되는 문구는 한국어로 작성하고 `tr("...")`로 감쌈(`from ..i18n import tr`)
2. 값이 들어가는 문장은 f-string 대신 `tr("클립 {0}개").format(n)` 형식으로 문장 전체를 1개 문구로 유지
3. 동일 문구를 `src/stream2clip/locales/ja.json`, `en.json`에 추가. 누락 시 `tests/test_i18n.py`가 실패
4. 번역 수정 PR 접수

## 브랜치와 커밋

- `main`에 직접 푸시 금지. `feature/<주제>` 브랜치에서 작업 후 PR 제출
- 커밋 메시지는 영어, 제목은 명령형(예: `Add CHZZK replay chat fetcher`). 본문에는 변경 내용과 사유 기재
- 커밋 작성자는 작업자 본인의 계정으로 지정(`git config user.name`, `git config user.email`). 도구 명의의 작성자, 도구를 가리키는 `Co-Authored-By` 서명, 세션 주소 꼬리표 사용 금지. PR 검사(`packaging/check_commits.py`)에서 확인
- PR 설명은 바뀐 것, 확인한 것, 확인하지 못한 것으로 구분하여 기재

## 버그 제보 기재 사항

- 운영체제와 화면 배율(예: Windows 11, 125%), 모니터 수
- `stream2clip --version`, `ffmpeg -version` 첫 줄
- 실행한 명령과 출력 전체. 방송 주소가 필요한 경우 공개 다시보기만 기재

## 보안 문제

공개 이슈로 등록하지 않고 [SECURITY.md](SECURITY.md)의 절차로 제보

## 라이선스

제출된 기여는 이 저장소의 [Apache-2.0](LICENSE) 라이선스로 배포

## 문서, 홈페이지 작성 기준

적용 대상: README, `CHANGELOG.md`, `docs/`, 홈페이지와 사용 설명서(`site/`), 앱 화면 문구

| &numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp; | 기준 |
|:---:|---|
| 어체 | 개조식(명사형 종결). 사실과 절차만 기재하며 구어체 문장, 수식어, 예정 사항 표기("다음 버전")는 사용하지 않음 |
| 기호 | 가운뎃점, 화살표, 줄표, 말줄임표, 꺾쇠 등 장식 기호와 이모지 사용 금지. 쉼표와 "및"으로 표기 |
| 구성 | 표와 번호 목록으로 정리. 대문자 라벨, 번호 장식, 카드 그리드, 블러, 애니메이션 사용 금지 |
| 언어판 | 홈페이지는 한국어, 영어(`site/en/`), 일본어(`site/ja/`) 3종. 1개 언어판 수정 시 나머지도 동일 구성으로 수정 |
| 표 | 항목 열은 첫 열 가운데 정렬(`:---:`)로 작성. 수정 후 `python packaging/format_docs.py` 실행 시 제목 칸에 줄바꿈 방지 처리 적용 |
| 확인 | `python packaging/build_site.py --pdf`로 조립하여 확인 |
| 자동 검사 | 홈페이지는 `tests/test_site.py`, 앱 문구는 `tests/test_i18n.py`, 저장소 문서는 `tests/test_docs.py` |
