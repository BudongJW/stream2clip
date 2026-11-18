# 변경 내역

## 다음 릴리즈 (작업 중)

### 앱
- **하이라이트 창에서 번역 · 노래 구간 · 웃음소리**를 고릅니다. 번역기는 설치한 플러그인 목록에서 고르거나 `.py` 파일을 직접 고릅니다.
- **업로드 창**: 내보낸 클립과 설명란이 채워진 채로 열립니다. 기본 비공개, 보낼 내용 미리 보기, 공개로 올릴 때는 한 번 더 묻습니다.
- **OBS 리플레이 저장 버튼** (런처): 리플레이 버퍼를 저장해 마지막 N초를 녹화 설정 형식으로 만듭니다.
- **설정 기억**: 녹화 형식 · 저장 폴더 · 하이라이트 창의 선택 · OBS 주소가 `settings.json`에 남습니다. 비밀번호는 저장하지 않습니다.

### 번역기 연결
- `--translator file.py[:함수]` / `module:함수`, 환경 변수 `STREAM2CLIP_TRANSLATOR`: 플러그인 패키지를 만들지 않고 파이썬 파일 하나로 번역기를 연결합니다.
- `examples/translators/openai_compatible.py`: OpenAI 호환 주소(기본은 로컬 Ollama)를 쓰는 예제. 표준 라이브러리만 쓰며 Windows 실행 파일 묶음에도 들어갑니다.
- 로컬 Ollama(qwen2.5:7b)로 실제 방송 자막을 번역해 두 줄 자막 클립까지 확인했습니다. 작은 모델은 다른 언어가 섞일 수 있습니다.

## v0.3.0 — 2026-11-19

### 새 기능
- **하이라이트 창** (앱): 영상 · 채팅을 고르고 하이라이트를 찾은 뒤, 타임라인에서 구간을 끌어 조정하고 레이아웃 미리보기를 보며 내보냅니다. 긴 방송은 휠 · 더블클릭으로 확대합니다.
- **아바타 위치 자동 찾기**: `--layout stack --avatar auto`, `stream2clip avatar`. 애니메 얼굴 검출로 방송 하나에 고정 박스 하나를 정합니다.
- **CHZZK · SOOP 다시보기 채팅 수집**: `stream2clip fetch <주소>`. 닉네임 없이 정규화해 저장합니다.
- **자막 번역 + 이름 용어집**: `--translate ko --glossary names.csv --bilingual`, `stream2clip glossary`. 번역 서비스는 플러그인으로 연결합니다.
- **노래 구간 검출**: `stream2clip singing`, `--mark-singing`, `--skip-singing`. 웃음소리 신호 `--laughter`는 실험 기능입니다.
- **OBS 리플레이 버퍼 → 클립**: `stream2clip replay -o moment.gif --last 15`.
- **YouTube 업로드**: `stream2clip upload` (기본 비공개, `--dry-run`, `--shorts`).
- **Windows 실행 파일**: `python packaging/build_windows.py`로 GUI와 명령줄 프로그램을 한 폴더 · zip으로.
- **새 앱 아이콘과 마스코트 키리**: 창 · 실행 파일 아이콘, 하이라이트 창의 상태 표시.

### 실제 환경에서 확인하며 고친 것
- Windows 125% 배율에서 선택 영역이 1px 짧게 나오던 문제, 녹화 커서 크기.
- YouTube 대기실 채팅이 0초에 몰리던 문제, 반응 어휘 부족(11% → 40%), 종료 인사가 하이라이트로 뽑히던 문제.
- `--transcribe`가 faster-whisper 1.2.1 + PyAV 19에서 실패하던 문제.
- 출력을 파이프로 연결한 영어 Windows에서 한글을 인쇄하다 죽던 문제.
- ぶいすぽっ! 가이드라인 프로필을 공식 원문(2026-09-17 개정)에 맞춤.

### 아직 실제 서비스로 확인하지 못한 것
- OBS 연동(실제 OBS), YouTube 업로드(실제 계정), 자막 번역(실제 번역기), Holodex 이름 초안(API 키).
- Windows 실행 파일은 서명이 없습니다. SmartScreen 경고가 뜰 수 있고 Smart App Control이 켜진 PC에서는 차단될 수 있습니다. ffmpeg는 들어 있지 않습니다.
- 배율이 다른 모니터 2대, Windows 10, macOS, Wayland.

## v0.2.0

방송 → 클립 자동화: 채팅 · 음량 · 많이 다시 본 구간으로 하이라이트 검출, 9:16 레이아웃, 카라오케 자막, 기획사 가이드라인 설명란 · 점검.

## v0.1.0

영역 캡쳐, 편집기, 움짤 녹화(GIF · MP4 · WebP · WebM · MOV · APNG), 투명 배경 녹화, VOD 구간 변환.
