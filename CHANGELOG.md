# 변경 내역

## v0.9.0: 2026-11-19

### 클립 제작
- 하이라이트 창에 **아바타 영상** 입력 추가: 아바타만 녹화한 영상을 stack, pip 레이아웃의 아바타로 사용. 이전에는 명령줄에서만 지정 가능
- 투명 배경 아바타 영상의 자동 인식: `--avatar-key`의 기본값을 `auto`로 변경. 영상에 투명 정보가 있으면(ProRes 4444 MOV, 알파 WebM) 그대로 사용하고 없으면 `#00FF00` 제거
- 알파 WebM은 libvpx 디코더로 읽도록 지정(ffmpeg 기본 VP9 디코더는 투명 정보를 버림)
- 자막 속 반응 표현 신호(`--speech 자막 파일`, 실험): 채팅이 없는 방송에서 스트리머의 발화 중 반응 표현을 신호로 사용. 일본어 방송 5개 기준 무작위 대비 1.07배로 효과가 뚜렷하지 않아 기본값에는 포함하지 않음
- 코어: `export.has_alpha`, `ffmpeg.avatar_decoder_args`, `highlights.speech_levels`, `detect_highlights(speech=...)`

### 업로드
- 예약 게시: `upload --publish-at "2026-12-24 18:00"`, 업로드 창의 **예약 게시**. 비공개로 업로드한 후 지정한 시각에 YouTube가 공개로 전환. 공개 범위가 비공개인 경우에만 허용하며 과거 시각은 거부
- 코어: `upload.video_resource(publish_at=...)`, `scheduled_time`

### 확인 내용
- CHZZK, SOOP 채팅과 실제 OBS Studio 33.0.1로 클립 저장 확인(각 35초 클립 1개, 10개 항목 통과)
- 투명 배경 WebM, ProRes 4444 MOV 아바타 영상의 인식과 합성을 합성 영상으로 확인
- 미검증: 예약 게시의 실제 업로드(계정 필요), 실제 아바타 녹화본
- Windows 11 실기기에서 v0.8.0 실행 파일을 직접 실행: 클립 제작(pip 레이아웃, 아바타 영상, 문장 경계 맞춤, 자막 스타일), 스트리머 표시 구간, VRM 검사, CHZZK 및 SOOP 및 Twitch 라이브 채팅 수신 등 13개 항목 통과
- 설치 프로그램을 자동 옵션 없이 화면 단계별로 진행하여 설치, 실행, 제거 확인(15개 항목 통과). 이전에는 러너에서의 자동 설치만 확인

## v0.8.0: 2026-11-19

### 라이브 모드
- CHZZK, SOOP 라이브 채팅 직접 수신: 채널 주소(`chzzk.naver.com/live/채널 ID`, `play.sooplive.co.kr/스트리머 ID`)만으로 채팅 서버에 로그인 없이(읽기 전용) 접속. 명령줄과 런처 공통
- CHZZK는 채팅과 후원, SOOP은 채팅과 별풍선, 애드벌룬, 영상풍선을 수신. 스트리머 본인의 메시지는 역할을 구분하여 표시 명령(`!clip` 등)에 사용
- 성인 인증, 비밀번호 방송은 미지원(로그인 필요)
- 코어: `live.ChzzkLiveChat`, `SoopLiveChat`, `chzzk_channel`, `soop_channel`, `reads_chat_itself`, `chat.chzzk_live_message`, `soop_live_message`

### 화면 언어
- 하이라이트 근거(채팅 급증, 반응, 후원, 음량, 스트리머 표시 등), 가이드라인 점검, VRM 검사, Shorts 경고, 기획사 프로필의 주의 사항을 일본어와 영어로 제공. 이전에는 일본어, 영어 화면에서도 한국어로 표시됨
- 클립 설명란의 표제와 AI 사용 문구도 화면 언어에 맞춰 작성
- 번역 목록 검사 범위를 창의 문구에서 패키지 전체로 확대
- 코어: `i18n.mark`, `shown`, `highlights.chat_reason`, `reactions_reason`, `marker_reason`

### 확인 내용
- CHZZK, SOOP: 실제 방송 중인 채널에서 수신 확인(기본 설정, OBS 미사용, 각 5분. CHZZK 메시지 1,021개에서 1회 발동, SOOP 메시지 1,543개에서 발동 없음)
- 채팅 서버의 응답 구조는 실제 응답으로 확인. SOOP의 별풍선, 애드벌룬, 영상풍선 패킷은 실제 방송에서 관찰한 구조에 맞춤
- 미검증: CHZZK, SOOP 채팅과 OBS를 함께 사용한 저장(저장 경로는 Twitch 채팅으로 확인한 것과 동일), SOOP의 구독 및 팔로우 알림(수신하지 않음), 일본어 및 영어 문구의 원어민 검수


### 자막
- 폰트의 언어별 자동 선택: 자막의 문자 구성에 맞는 후보 중 설치된 첫 폰트 사용(일본어는 Noto Sans JP, Yu Gothic, Meiryo 순, 한국어는 Noto Sans KR, Malgun Gothic 순). 이전에는 Noto Sans KR 고정이어서 일본어 한자가 한국어 자형으로 표시됨. `--font`로 직접 지정 가능
- 원문 병기 자막은 원문 줄과 번역 줄에 각 언어의 폰트 적용
- 줄바꿈 개선: 표시 폭 기준(전각 1, 영문자 약 0.55)으로 최대 3줄까지 균등 분할. 일본어는 문절 경계에서 분할. 이전에는 글자 수 기준 2줄 고정이어서 일본어가 단어 중간에서 나뉘고 긴 자막은 화면 밖으로 넘침
- 3줄로도 넘치는 자막은 해당 자막만 축소 표시
- 스타일 프리셋 4종(`default`, `box`, `pink`, `small`)과 위치 3종(`bottom`, `middle`, `top`): `--subtitle-style`, `--subtitle-position`, `--font-size`, 하이라이트 창의 **스타일** 줄
- 코어: `subtitles.subtitle_style`, `SUBTITLE_STYLES`, `pick_font`, `script_of`, `installed_fonts`, `SubtitleStyle(font="auto", max_lines=3, box=False)`

### 권리 검사
- VRM 아바타 권리 검사: `stream2clip check --vrm model.vrm [--monetized] [--corporation]`. 파일에 기록된 사용 조건(아바타 사용 범위, 영리 사용, 크레딧 표기, 개변과 재배포)을 표시하고 계획한 사용과 대조. VRM 1.0과 0.x 지원
- 코어: `vrm.read_vrm_meta`, `check_vrm`

### 확인 내용
- 자막: 스타일 4종과 위치 3종, 113자 일본어 자막, 원문 병기 자막을 키 비주얼 영상에 렌더링하여 확인
- VRM: 메타 항목 이름을 공식 스키마(1.0, 0.x) 원문과 대조. 실제 VRM 모델 파일은 미검증
- 라이브 모드: 실제 Twitch 채팅과 실제 OBS Studio 33.0.1로 클립 저장 확인(급증 2회에 35초 클립 2개). 스트리머의 `!clip` 표시로 급증 없이 클립 1개 저장 확인

### 변경 사항
- 라이브 모드 출력: 표시 명령으로 저장한 경우 `surge 0.0` 대신 `marker`로 표기

## v0.6.0: 2026-11-19

### 클립 제작
- 문장 경계 맞춤: 클립의 시작 또는 끝이 자막 줄의 중간에 걸리면 해당 줄의 경계로 이동. `--subtitles` 지정 시 기본 적용, 이동 한도는 `--snap SECONDS`(기본 3초, 0은 사용 안 함). 앱은 하이라이트 창의 **문장 경계 맞춤**
- 스트리머 표시 구간: 스트리머 또는 모더레이터가 채팅에 입력한 `!clip`, `!클립`, `!切り抜き`, `!ts`, `!mark`의 시점을 점수와 무관하게 클립으로 포함하고 앞 순위에 배치. `--marker`, `--marker-anyone`, `--no-markers`
- 채팅 메시지에 작성자 역할(스트리머, 모더레이터) 추가. YouTube, Twitch, CHZZK 채팅과 chat-downloader JSON에서 판독하며 CSV, JSONL은 `role` 열 사용
- pip 레이아웃: 게임 화면을 전체에 채우고 구석에 아바타 삽입. `--layout pip`, `--corner`, `--inset`
- 별도 아바타 영상 합성: 아바타만 녹화한 그린스크린 또는 알파 영상을 `stack`, `pip`의 아바타로 사용. `--avatar-video`, `--avatar-key`, `--avatar-offset`
- 코어: `highlights.snap_to_cues`, `marker_times`, `ChatMessage.role`, `VerticalLayout(kind="pip", avatar_source=...)`, `ffmpeg.avatar_input_args`

### 라이브 모드
- Twitch 채널 주소 지원: 채팅 서버에 익명(읽기 전용)으로 접속하여 전송 즉시 수신. 명령줄(`live https://www.twitch.tv/CHANNEL`)과 런처 공통
- 스트리머 또는 모더레이터의 표시 명령 입력 시 준비 시간, 임계값과 무관하게 즉시 저장
- 코어: `live.TwitchLiveChat`, `parse_twitch_irc`, `twitch_channel`, `open_chat`

### 확인 내용
- 문장 경계 맞춤: 실제 방송 1개(85분, YouTube 자동 자막)의 하이라이트 10개에서 줄 중간에 걸린 가장자리가 12곳에서 1곳으로 감소
- 역할 판독: 실제 YouTube 채팅 7개 방송, 실제 CHZZK 다시보기 1개에서 스트리머와 모더레이터 메시지 판독
- pip 레이아웃: 실제 방송 녹화본에서 `--avatar auto`로 클립 제작(1080×1920, 24.6초 클립에 18초 소요)
- Twitch 채팅: 실제 방송 중인 채널에서 4분간 수신하여 급증 판정까지 확인(OBS 미사용)
- 미검증: 실제 방송에서 사용된 표시 명령, 실제 아바타 그린스크린 녹화본(합성 영상으로만 확인), Twitch 채팅과 OBS를 함께 사용한 저장

### 문서
- README의 あおぎり高校 가이드라인 기준을 프로필과 동일하게 2026-02 개정으로 수정
- README를 개조식으로 재작성. 줄글 설명을 표와 목록으로 정리하고 개요, 버전별 주요 변경, 명령 목록 추가
- 세부 내용을 별도 문서로 분리: 검출 방식 및 평가(`docs/DETECTION.md`), 실환경 검증 현황(`docs/VERIFICATION.md`), 테스트(`docs/TESTING.md`)
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/ARCHITECTURE.md`, `docs/PORTING.md`를 동일 어체로 정리
- README 배지 문구의 가운뎃점과 화살표 제거, 기술 스펙 표의 빈칸 표기 정리
- 이슈 및 PR 양식, 브랜드 폴더의 안내 파일을 동일 기준으로 정리
- 영역 선택 스크린샷을 현재 문구의 화면으로 교체
- 표의 항목 열이 GitHub 화면에서 2글자 폭으로 줄바꿈되는 문제 수정. 제목 칸을 가장 긴 항목 폭에 맞추는 `packaging/format_docs.py` 추가
- 저장소 문서 검사 추가(`tests/test_docs.py`): 링크와 책갈피, 장식 기호, 구어체 종결, 버전 및 테스트 수 표기

## v0.5.1: 2026-11-19

### 설치 프로그램
- Windows 설치 프로그램(`stream2clip-<버전>-windows-x64-setup.exe`) 추가. 첫 화면에서 언어(한국어, 일본어, 영어)를 선택하면 설치 화면과 앱이 해당 언어로 표시. 관리자 권한 불필요, 시작 메뉴 바로 가기와 제거 항목 생성. zip 배포는 유지
- 앱은 설치 시 선택한 언어를 프로그램과 같은 폴더의 `language.txt`에서 조회. 결정 순서: 앱에서 선택한 언어, `STREAM2CLIP_LANG`, 설치 시 선택한 언어, 시스템 언어. `stream2clip language`로 현재 값 확인
- CI의 Windows 러너에서 설치 프로그램을 3개 언어로 자동 설치하여 설치된 프로그램의 시작 언어와 제거 동작 확인

### 앱
- 라이브 모드: 구간당 최소 메시지 수를 5에서 8로 상향. 기본 설정으로 실제 방송(분당 약 10개의 느린 채팅)을 30분 관찰한 결과 메시지 5~7개 구간에서 6회 발동(시간당 12회), 8로 설정 시 2회. 채팅이 많은 방송 7개의 결과는 변동 없음
- 하이라이트 창에서 CHZZK 다시보기 주소(4시간 39분)로 전체 절차 확인: 검출 3초, 클립 2개 내보내기 5분 31초(1080p 구간 2개, 29MB)
- 화면 문구에서 가운뎃점, 화살표, 줄표, 말줄임표, 꺾쇠 제거(한국어, 일본어, 영어 71개 문구, 하이라이트 근거, 가이드라인 점검 문구)
- 런처와 하이라이트 창의 구역 이름을 대문자 영문 라벨(CAPTURE, RECORD, CLIPS, SOURCE, HIGHLIGHTS)에서 일반 제목으로 변경. NEW 표시 제거
- 런처 제목 문구를 사실 위주로 변경(화면 캡쳐, 녹화, 방송 클립 제작)

### 문서
- README와 문서에서 장식 기호와 이모지 제거

### 홈페이지
- 언어 선택을 국기가 표시되는 드롭다운으로 변경. Windows에는 국기 이모지가 없어 국기 전용 글꼴을 함께 로드
- 다운로드 버튼을 설치 프로그램으로 연결하고 zip은 별도 링크로 제공. 설치 절차와 설명서를 설치 프로그램 기준으로 수정
- 일본어판 추가([https://budongjw.github.io/stream2clip/ja/](https://budongjw.github.io/stream2clip/ja/)). 화면 그림과 설명서 PDF도 일본어판 별도 제공
- 홈페이지와 사용 설명서의 영어판 추가([https://budongjw.github.io/stream2clip/en/](https://budongjw.github.io/stream2clip/en/)). 화면 그림은 영어 화면으로 촬영, 설명서 PDF도 영어판 별도 제공
- 표의 제목 행과 제목 열을 가운데 정렬, 모든 칸을 세로 가운데 정렬로 변경
- 첫 화면의 배포일 표시 제거

## v0.5.0: 2026-11-19

### 라이브 모드
- `stream2clip live <YouTube 라이브 주소 | 채팅 파일>`: 방송 중 채팅 급증 시 OBS 리플레이 버퍼를 저장하고 해당 장면(약 35초)을 클립으로 저장. `--no-obs`는 알림만 수행, `--simulate`는 종료된 방송의 채팅으로 발동 시점 표시
- 급증 판정은 다시보기 검출과 동일한 점수(채팅 수, 참여자, 반응 어휘, 후원의 robust z)를 직전 15분과 비교. 기본값은 종료된 방송 7개의 발동 횟수(시간당 약 6회) 기준으로 선정
- 리플레이 버퍼가 클립보다 짧은 경우(OBS 기본 20초) 저장 시 안내
- 실제 OBS Studio 33.0.1과 실제 YouTube 라이브 채팅(분당 약 25개)으로 확인: 버퍼가 꺼진 경우 즉시 안내, 급증 2회에 35초 클립 2개를 55초 리플레이에서 잘라 저장. 이 확인에서는 수 분 내 발동하도록 임계값을 1로 하향
- yt-dlp가 라이브 중에 기록한 채팅 파일을 읽지 못하던 문제 수정(영상 시각 없이 보낸 시각만 있는 줄을 전부 제외하던 문제). 첫 메시지부터의 경과 시간으로 처리
- 코어: `live.SurgeDetector`, `simulate`, `FileFollower`, `YtDlpLiveChat`, `ReplayClipper`, `chat.live_messages`, `obs.replay_to_clip(trim_end=...)`

### 앱
- 런처의 라이브 모드: YouTube 라이브 주소와 민감도를 선택하여 시작하면 채팅 급증 시 OBS 리플레이 버퍼를 저장하여 해당 장면을 저장 폴더에 클립으로 저장. OBS에 연결할 수 없거나 리플레이 버퍼가 동작하지 않으면 대기 전에 안내
- 실제 OBS Studio 33.0.1과 실제 YouTube 라이브 채팅으로 런처의 시작, 클립 저장, 중지 확인(수 분 내 발동하도록 임계값을 하향한 설정)
- 하이라이트 창의 방송 주소 입력: 영상 칸에 방송 주소를 입력하면 채팅 다시보기와 방송 정보를 수신하여 하이라이트를 검출하고, 내보낼 때 체크한 구간의 영상만 다운로드. 수신 자료는 저장 폴더의 `sources/<플랫폼>_<영상 ID>/`에 방송별로 보관하여 재사용
- 주소 입력 시 음량, 웃음소리, 노래 구간 선택 사용 불가(영상 파일 필요). 미리보기는 구간 수신 후부터 표시
- 실제 YouTube 아카이브(1시간 24분, 채팅 43,967개) 주소 1개로 확인: 검출 3분 12초(대부분 채팅 다시보기 수신 시간), 클립 2개 내보내기 4분 36초(1080p 구간 64초, 94초, 88MB 다운로드)
- 코어: `sources.fetch_replay`(정보와 채팅만 수신), `sources.source_folder_name`. `auto <주소>`도 동일 함수 사용

### 홈페이지
- [https://budongjw.github.io/stream2clip/](https://budongjw.github.io/stream2clip/) 개설: Windows 실행 파일 다운로드와 사용 설명서 제공. 다운로드 버튼은 최신 릴리즈를 가리키며 버전과 크기 표시(GitHub API를 사용할 수 없으면 릴리즈 페이지로 연결)
- 설명서는 웹 페이지와 PDF 2종. PDF는 배포 시 동일 페이지를 Chrome으로 인쇄하여 생성
- 홈 화면과 사용 설명서를 개조식으로 재작성. 내용은 표와 번호 목록으로 정리하고 대문자 라벨, 번호 장식, 카드 그리드, 블러 헤더, 깜빡임 등 장식 제거. 설명서의 "다음 버전" 표시 제거(표시했던 기능은 이 버전에 포함)
- 브랜드 컨셉(잉크, 페이퍼, 라이브 핑크, 하이라이트, Outfit, Noto Sans KR, JetBrains Mono, 채팅 타임라인과 9:16 클립 카드, 키리) 적용. 그림은 저장소에 중복 보관하지 않고 `packaging/build_site.py`가 `assets/brand`, `docs/images`에서 복사

## v0.4.0: 2026-11-19

### 앱
- 하이라이트 창에서 번역, 노래 구간, 웃음소리 선택. 번역기는 설치한 플러그인 목록에서 선택하거나 `.py` 파일을 직접 지정
- 업로드 창: 내보낸 클립과 설명란이 입력된 상태로 열림. 기본 비공개, 전송 내용 사전 확인, 공개로 게시하는 경우 재확인
- 런처의 OBS 리플레이 저장 버튼: 리플레이 버퍼를 저장하여 마지막 N초를 녹화 설정 형식으로 변환
- 설정 저장: 녹화 형식, 저장 폴더, 하이라이트 창의 선택, OBS 주소를 `settings.json`에 보관. 비밀번호 미저장

### 실제 OBS 검증 및 수정
- 실제 OBS Studio 33.0.1에서 인증, 리플레이 시작, 저장, 변환을 명령줄과 앱 버튼으로 확인
- 리플레이 버퍼가 설정에서 꺼진 경우(신규 설치한 OBS의 기본값) `604` 코드만 표시하던 것을 설정 위치를 안내하도록 변경
- `--start-buffer`가 OBS의 "ok" 응답만으로 시작된 것으로 표시하던 문제 수정. 장면에 소스가 없으면 OBS는 "소스 없음" 확인 창을 표시하고 시작하지 않으므로 실제 시작 여부를 확인

### 화면 언어
- 앱 화면을 한국어, 일본어, 영어로 제공. 런처에서 선택(다음 실행부터 적용)하거나 시스템 언어, `STREAM2CLIP_LANG` 적용
- 번역 목록은 `stream2clip/locales/*.json`. 코드의 문구와 불일치하면 테스트가 실패
- 하이라이트 근거, 가이드라인 점검, 명령줄 출력은 한국어만 제공. 번역은 원어민 검수 미실시

### 평가, 단축키
- `stream2clip evaluate`: 여러 방송에서 채팅만으로 검출한 하이라이트를 시청자 댓글의 타임스탬프와 비교(precision, recall, 무작위 대비 배수, `--sweep`으로 설정값 비교). `fetch --comments N`으로 댓글 함께 수신
- 런처의 F10(선택 사항): 다른 프로그램 사용 중에도 F10으로 OBS 리플레이 저장
- Python 3.10에서 테스트 전체 통과 후 인터프리터 종료 단계에서 비정상 종료하던 문제를 테스트 실행 단계에서 우회

### 주소만으로 클립 제작
- `stream2clip auto <주소>`, `clips <주소>`: 채팅 다시보기를 수신하여 하이라이트를 검출하고 해당 구간의 영상만 다운로드. 수신한 구간은 재실행 시 재사용
- CHZZK 구간 다운로드가 ffmpeg 7.1 이후 버전에서 실패하던 문제 수정(HLS 확장자 검사가 `.m4s` 조각을 거부). 실제 4시간 39분 다시보기에서 약 3분에 클립 2개 제작 확인
- 구간 수신 시 HLS 형식을 우선 선택. 실제 YouTube 아카이브에서 64초 구간이 DASH 형식으로는 6분 이상 미완료, HLS로는 13초. `auto <YouTube 주소> --top 2`는 채팅 수신 완료 상태에서 1분 45초에 클립 2개 제작
- 코어: `pipeline.make_clips(section=...)`, `sources.download_highlight_sections`

### 번역기 연결
- `--translator file.py[:함수]`, `module:함수`, 환경 변수 `STREAM2CLIP_TRANSLATOR`: 플러그인 패키지 없이 파이썬 파일 1개로 번역기 연결
- `examples/translators/openai_compatible.py`: OpenAI 호환 주소(기본값은 로컬 Ollama)를 사용하는 예제. 표준 라이브러리만 사용하며 Windows 실행 파일 묶음에도 포함
- 로컬 Ollama(qwen2.5:7b)로 실제 방송 자막을 번역하여 원문 병기 자막 클립까지 확인. 소형 모델은 다른 언어가 혼입될 수 있음

### 저장소
- 린트(ruff) 추가, CI에서 확인. Linux 테스트를 Python 3.10, 3.12, 3.14에서 실행(이전에는 3.12만 실행)
- GitHub Actions를 Node 24 기반 버전으로 갱신
- `CONTRIBUTING.md`, `SECURITY.md`, 이슈 및 PR 양식 추가

## v0.3.0: 2026-11-19

### 신규 기능
- 하이라이트 창(앱): 영상과 채팅을 선택하여 하이라이트를 검출하고, 타임라인에서 구간을 끌어 조정한 후 레이아웃 미리보기를 확인하며 내보내기. 긴 방송은 휠, 더블클릭으로 확대
- 아바타 위치 자동 검출: `--layout stack --avatar auto`, `stream2clip avatar`. 애니메 얼굴 검출로 방송 1개에 고정 박스 1개 결정
- CHZZK, SOOP 다시보기 채팅 수집: `stream2clip fetch <주소>`. 닉네임 없이 정규화하여 저장
- 자막 번역 및 이름 용어집: `--translate ko --glossary names.csv --bilingual`, `stream2clip glossary`. 번역 서비스는 플러그인으로 연결
- 노래 구간 검출: `stream2clip singing`, `--mark-singing`, `--skip-singing`. 웃음소리 신호 `--laughter`는 실험 기능
- OBS 리플레이 버퍼 클립 변환: `stream2clip replay -o moment.gif --last 15`
- YouTube 업로드: `stream2clip upload`(기본 비공개, `--dry-run`, `--shorts`)
- Windows 실행 파일: `python packaging/build_windows.py`로 GUI와 명령줄 프로그램을 한 폴더 및 zip으로 구성
- 신규 앱 아이콘과 마스코트 키리: 창, 실행 파일 아이콘, 하이라이트 창의 상태 표시

### 실환경 검증 및 수정
- Windows 125% 배율에서 선택 영역이 1px 짧게 나오던 문제, 녹화 커서 크기
- YouTube 대기실 채팅이 0초에 집중되던 문제, 반응 어휘 부족(11%에서 40%로 개선), 종료 인사가 하이라이트로 선정되던 문제
- `--transcribe`가 faster-whisper 1.2.1, PyAV 19 조합에서 실패하던 문제
- 출력을 파이프로 연결한 영어 Windows에서 한글 출력 중 비정상 종료하던 문제
- ぶいすぽっ! 가이드라인 프로필을 공식 원문(2026-09-17 개정)에 맞게 수정

### 미검증 사항
- OBS 연동(실제 OBS), YouTube 업로드(실제 계정), 자막 번역(실제 번역기), Holodex 이름 초안(API 키)
- Windows 실행 파일은 코드 서명 미적용. SmartScreen 경고가 표시될 수 있으며 Smart App Control 사용 환경에서는 차단될 수 있음. ffmpeg 미포함
- 배율이 다른 모니터 2대, Windows 10, macOS, Wayland

## v0.2.0

방송 클립 자동화: 채팅, 음량, 많이 다시 본 구간으로 하이라이트 검출, 9:16 레이아웃, 카라오케 자막, 기획사 가이드라인 설명란, 점검

## v0.1.0

영역 캡쳐, 편집기, 움짤 녹화(GIF, MP4, WebP, WebM, MOV, APNG), 투명 배경 녹화, VOD 구간 변환
