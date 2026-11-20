# 방송 기록기

방송 중에만 얻을 수 있는 신호를 세션 파일에 기록하고, 방송 후 하이라이트 검출과 9:16 클립 제작에 사용하는 기능. 영상은 녹화하지 않음(영상 녹화는 OBS 담당)

## 구성

| &numsp;&numsp;&numsp;&numsp;&numsp;&numsp;구&NoBreak;성&numsp;&numsp;&numsp;&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| `stream2clip.session` | 세션 파일 쓰기(`SessionWriter`), 읽기(`load_session`), 시각 기준, 장면 구간, OBS 배치 좌표 변환, 아바타 박스 계산. numpy만 사용 |
| `stream2clip.recorder` | 채팅, OBS, VTube Studio를 읽는 부분(`ChatPart`, `ObsPart`, `VtsPart`)과 폴링 루프(`SessionRecorder`), 조립 함수(`build_recorder`) |
| `stream2clip.vts` | VTube Studio 공개 API 클라이언트(인증 토큰 발급과 보관, 요청, 이벤트 구독) |
| `gui/session.py` | 앱의 **방송 기록기** 창. 시작 화면의 클립 영역에서 열기. 단독 실행 명령 `stream2clip-recorder` |
| 명령 | `stream2clip session record`, `stream2clip session show` |
| 스키마 | [`session.v1.schema.json`](../src/stream2clip/schemas/session.v1.schema.json) |

## 기록 신호

| &numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;신&NoBreak;호&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp; | 출처 | 클립 제작에서의 용도 |
|:---:|---|---|
| 채팅 | 라이브 모드와 동일한 수신부(Twitch, CHZZK, SOOP 직접 수신, YouTube는 yt-dlp, 파일) | 하이라이트 검출. 방송 후 채팅 다시보기를 받을 필요 없음 |
| 채팅 급증 | 라이브 모드의 급증 판정(`SurgeDetector`) | `session show`의 시점 목록 |
| 표시 | 창의 **지금 표시** 버튼, F11(사용 설정 시), 명령줄의 Enter, VTube Studio 단축키(`--vts-hotkey`), 채팅의 `!clip` 등 | 하이라이트 검출에서 항상 클립으로 포함 |
| OBS 장면 | obs-websocket `CurrentProgramSceneChanged` | `--skip-scene`으로 대기 화면, 엔딩 등 제외 |
| 송출, 녹화, 리플레이 버퍼 | `StreamStateChanged`, `RecordStateChanged`, `ReplayBufferStateChanged` | 영상의 0초 시점 결정 |
| 저장된 리플레이 | `ReplayBufferSaved` | 표시할 때 리플레이 저장(`--replay-on-marker`) 결과 기록 |
| 캔버스 크기 | `GetVideoSettings`의 기본 해상도와 출력 해상도 | 아바타 좌표를 영상 픽셀로 변환 |
| VTube Studio 소스 배치 | `GetSceneItemTransform`(장면 전환 시와 15초마다 확인, 변경 시에만 기록) | 아바타 좌표를 영상 픽셀로 변환. 숨김 상태이거나 장면에 없으면 빈 값 기록 |
| 아바타 외곽선 | VTube Studio `ModelOutlineEvent`(초당 15회 수신, 기본 0.5초마다 기록) | `--avatar session`의 아바타 박스 |
| 아바타 파라미터 | VTube Studio `Live2DParameterListRequest`(기본 0.2초마다) | `--avatar-motion`(실험): 구간별 움직임을 보조 신호로 하이라이트 점수에 반영. 기본값은 표준 얼굴, 머리 파라미터 13종 |
| 연결 상태 | 각 부분의 연결, 대기, 재연결 | `session show`의 연결 문제 개수 |

## 세션 파일

JSON Lines. 첫 줄은 헤더, 이후 한 줄에 사건 1개. 시각은 UNIX 초(벽시계)

```json
{"schema":"stream2clip.session/v1","started":1763600000.0,"app":"stream2clip 0.14.0","sources":{"obs":"ws://127.0.0.1:4455"}}
{"t":1763600012.4,"type":"output","output":"stream","active":true}
{"t":1763600400.1,"type":"chat","text":"ㅋㅋㅋㅋ","author":"3f2a9c01d4e5","kind":"text"}
{"t":1763600401.0,"type":"marker","by":"hotkey"}
{"t":1763600401.2,"type":"avatar_outline","hull":[[-0.4,0.9],[0.5,0.9],[0.5,-1.2],[-0.4,-1.2]],"window":[1920,1080]}
```

| &numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| 사건 종류 | `chat`, `marker`, `surge`, `scene`, `output`, `replay_saved`, `obs_video`, `avatar_source`, `avatar_outline`, `avatar_params`, `avatar_model`, `status` |
| 호환 | 읽는 쪽은 모르는 사건 종류를 건너뜀. 새 종류 추가는 버전 변경 없이 가능 |
| 중단 | 줄마다 즉시 기록. 프로그램이 중간에 종료되어 마지막 줄이 잘린 경우 해당 줄만 제외하고 읽음 |
| 개인정보 | 채팅 작성자는 해시(SHA-1 앞 12자리)로만 기록, 닉네임 미기록. 파일은 로컬에만 저장 |
| 값 정리 | NaN, 무한대 값은 JSON이 아니므로 해당 항목 제외 |
| 크기 | 외곽선 0.5초, 파라미터 0.2초 간격 기준으로 1시간에 외곽선 7,200줄, 파라미터 18,000줄 |

## 영상의 0초

세션 시각을 영상 시각으로 변환하는 기준(`--session-origin`)

| &numsp;&numsp;기&NoBreak;준&numsp;&numsp; | 0초 | 대상 영상 |
|:---:|---|---|
| `stream` | OBS 송출 시작 | 플랫폼 다시보기 |
| `record` | OBS 녹화 시작 | 로컬 녹화 파일 |
| `session` | 기록 시작 | 그 외 |
| `auto` | 송출, 녹화, 기록 시작 중 처음 있는 것 | 기본값 |

- 플랫폼 다시보기가 송출 시작보다 늦게 시작하면 그 차이를 `--session-offset`(초)으로 지정
- 채팅 시각은 플랫폼 서버 시각, OBS 사건 시각은 PC 시계 기준. PC 시계가 크게 어긋나면 채팅이 그만큼 이동
- 단축키 표시는 누른 순간이 장면 시점. 하이라이트 검출이 채팅 표시에서 빼는 채팅 지연(`--delay`, 기본 8초)만큼 미리 더하여 누른 순간에 장면이 놓임

## 아바타 박스 계산

`--avatar session`이 VTube Studio 외곽선으로 stack, pip 레이아웃의 아바타 영역을 정하는 절차

1. 외곽선 좌표(VTube Studio 창 기준, x는 왼쪽 -1에서 오른쪽 1, y는 아래 -1에서 위 1)를 소스 픽셀로 변환
2. 기록된 OBS 배치(`sceneItemTransform`)로 캔버스 좌표로 변환. libobs와 같은 순서로 자르기, 배율 또는 경계 상자(stretch, scale inner, scale outer, 너비 맞춤, 높이 맞춤, 축소만), 정렬 기준점 적용
3. 캔버스 기본 해상도와 영상 해상도의 비율로 영상 픽셀로 변환. 소스가 보이는 범위와 영상 범위 밖은 제외
4. 하이라이트 구간 안의 외곽선만 사용(없으면 전체). 외곽선별 경계 상자의 좌상단은 5번째 백분위, 우하단은 95번째 백분위를 취해 순간적인 점프 제외
5. 레이아웃 비율을 유지하고 모델 위쪽에 맞춘 상자 생성. 모델이 상자보다 길면 머리와 상반신이 들어감. 크기는 짝수 픽셀

| &numsp;&numsp;&numsp;&numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp;&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| 지원하지 않는 배치 | 회전, 좌우 반전된 소스. 그룹이나 중첩 장면 안의 소스(프로그램 장면에 직접 있는 소스만 확인) |
| 수동 지정 | `--vts-region x,y,w,h`: 영상에서 VTube Studio 화면 전체가 차지하는 영역. OBS 배치 기록이 없거나 지원하지 않는 배치일 때 사용 |
| 전제 | OBS 소스가 VTube Studio 화면 전체를 표시(게임 캡처, Spout2, 창 캡처의 클라이언트 영역) |

## 사용법

```bash
stream2clip session record --chat "https://chzzk.naver.com/live/CHANNEL_ID" --vts --vts-source "VTube Studio" -o session.jsonl
```

```bash
stream2clip session show session.jsonl
```

```bash
stream2clip auto vod.mp4 -o clips --session session.jsonl --skip-scene 대기 --layout stack --avatar session
```

| &numsp;&numsp;&numsp;&numsp;&numsp;&numsp;옵&NoBreak;션&numsp;&numsp;&numsp;&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| `--chat` | 본인 채널 주소, `chzzk-api`(CHZZK 공식 Open API), 수집기가 추가하는 채팅 파일. 생략 시 채팅 없이 기록 |
| `--no-obs` | OBS에 연결하지 않음. 기본은 `127.0.0.1:4455`, 비밀번호는 `--password` 또는 `OBS_WEBSOCKET_PASSWORD` |
| `--vts`, `--vts-url` | VTube Studio 외곽선과 파라미터 기록. VTube Studio 설정에서 API 시작 필요. 첫 연결 시 VTube Studio의 플러그인 허용 창에서 허용 |
| `--vts-source` | OBS에서 VTube Studio를 표시하는 소스 이름. 지정 시 소스 배치 기록 |
| `--parameters` | `default`(표준 13종), `all`, `none` |
| `--vts-hotkey` | 이름이 일치하는 VTube Studio 단축키를 표시로 기록(대소문자 무시, 반복 지정 가능) |
| `--replay-on-marker` | 표시할 때 OBS 리플레이 버퍼도 저장 |
| `--viewer-votes` | 시청자 투표 기준 인원. 0이면 사용 안 함(기본값) |
| `--widget` | OBS 위젯 제공. 포트 기본값 8790 |
| `--session` | `highlights`, `auto`, `clips`에서 세션 파일 사용. `--chat`이 없으면 세션의 채팅과 표시로 검출. 주소로 실행한 `auto`는 채팅 다시보기를 받지 않음 |
| `--skip-scene` | 이름에 지정 문자열이 포함된 OBS 장면에 절반 이상 걸친 하이라이트 제외 후 순위 재계산 |
| `--avatar session` | 세션의 VTube Studio 외곽선으로 아바타 박스 지정 |
| `--avatar-motion` | 실험 기능. 세션의 아바타 파라미터 변화량을 하이라이트 점수의 보조 신호로 사용. 근거에 **아바타 움직임 큼 (실험)** 표시 |

| &numsp;&numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| 앱 | 시작 화면 클립 영역의 **방송 기록기**. 채팅 주소, OBS 사용, VTube Studio 사용, VTS 소스 이름, 표시할 때 리플레이 저장, F11 선택 후 **기록 시작**. 채팅, OBS, VTube Studio의 연결 상태와 채팅, 급증, 표시, 아바타 외곽선 개수 표시. 종료 후 **하이라이트 찾기**로 하이라이트 창의 채팅 칸에 세션 파일 입력 |
| 저장 위치 | 저장 폴더의 `sessions/session-날짜-시각.jsonl`. YouTube 채팅을 yt-dlp로 받는 경우 같은 폴더의 `-chat` 폴더 사용 |
| F11 | 사용 설정 시 다른 프로그램 사용 중에도 F11로 표시. 사용 중에는 다른 프로그램이 F11을 받지 못하므로 기본값은 사용 안 함 |
| 연결 실패 | 각 부분이 독립적으로 재연결(채팅 30초, OBS와 VTube Studio 10초 간격). 한 부분의 실패가 다른 부분의 기록을 멈추지 않음 |
| 하이라이트 창 | 채팅 칸에 세션 파일 지정 시 채팅과 표시를 읽음(`load_chat`의 `session` 형식, 0초는 `auto` 기준) |

## 시청자 투표

- `--viewer-votes N`(앱은 **시청자 투표**, 3명): 서로 다른 시청자 N명이 30초 안에 표시 명령(`!clip` 등)을 입력하면 표시 1개 기록(`by: viewers`)
- 스트리머와 모더레이터의 입력은 투표가 아닌 일반 표시로 처리. 같은 시청자의 반복 입력은 1표
- 표시 시각은 창 안의 첫 투표 시각. 시청자 입력은 채팅이므로 단축키 표시와 달리 채팅 지연 보정을 하지 않음
- 표시 후 60초 동안은 추가 투표 표시 없음

## OBS 위젯

- `--widget`(앱은 **OBS 위젯**): 기록 중 이 PC에서만 접속 가능한 주소(`http://127.0.0.1:8790/widget`)로 방송 화면용 페이지 제공
- OBS에 브라우저 소스로 추가(너비 400, 높이 120). 배경 투명
- 표시 내용: 시청자 투표 진행(현재 인원 / 필요 인원), 표시가 남으면 3초간 강조. 시청자 투표를 쓰지 않으면 표시 강조만 수행
- 페이지는 1초마다 `/state`(JSON: 투표 수, 필요 인원, 표시 수, 마지막 표시 시각)를 조회. 외부로 나가는 통신 없음
- 기록 종료 시 함께 종료. 포트가 사용 중이면 기록을 시작하지 않고 안내

## CHZZK 공식 Open API

본인 채널의 채팅과 후원을 공식 경로로 수신. 다른 채널은 수신 불가(공식 API의 제약)

```bash
stream2clip chzzk login --client-id CLIENT_ID --client-secret CLIENT_SECRET --redirect http://localhost:8765/callback
```

```bash
stream2clip session record --chat chzzk-api --vts
```

| &numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| 사전 준비 | CHZZK 개발자 센터에서 애플리케이션 등록, 채팅 메시지 조회와 후원 조회 권한 선택, 로그인 리디렉션 URL을 `--redirect`와 같은 로컬 주소로 등록 |
| 로그인 | `chzzk login`이 브라우저로 동의 화면을 열고 로컬 주소에서 인증 코드를 받아 토큰 발급. 브라우저를 열 수 없으면 `--no-browser`로 주소만 출력 |
| 토큰 | 앱 설정 폴더의 `chzzk-token.json`(사용자 본인만 읽기 가능). Access Token 1일, Refresh Token 30일. 만료 시 자동 갱신. `chzzk logout`으로 삭제 |
| 앱 정보 | Client Secret은 파일에 저장하지 않음. 기록 시 환경 변수 `CHZZK_CLIENT_ID`, `CHZZK_CLIENT_SECRET` 필요(앱의 방송 기록기도 동일) |
| 수신 | 세션 생성 후 Socket.IO(Engine.IO 3) 연결, 연결 완료 메시지의 세션 키로 채팅과 후원 구독. 후원 금액은 원 단위 |
| 권한 회수 | 사용자가 동의를 철회하면 해당 사실을 안내하고 재연결 대기 상태로 전환 |
| SOOP | 공식 Chat SDK는 브라우저 JavaScript 전용이고 본인 방송에만 접속 가능하여 미지원. SOOP은 기존 직접 수신 사용 |

## 확인하지 못한 것

- 실제 OBS, VTube Studio, CHZZK, SOOP 방송과의 연결. 모든 연결은 가짜 서버로 테스트
- 실제 방송의 외곽선으로 계산한 아바타 박스의 품질
- 장시간 방송에서 VTube Studio 파라미터 조회 간격 0.2초의 부하
- 플랫폼 다시보기와 OBS 송출 시작 사이의 실제 시각 차이
- CHZZK 공식 Open API의 실제 로그인과 Socket.IO 서버 연결(애플리케이션 미등록)
- 아바타 움직임 신호의 검출 성능. 합성 데이터로만 확인하였으며 실제 방송으로 `evaluate` 미실시
