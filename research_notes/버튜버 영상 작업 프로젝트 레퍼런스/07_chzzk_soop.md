# CHZZK·SOOP 연동 외부 오픈소스와 공식 API (추가 조사)

> 조사 기준일: 2026-11-20. 01~06 노트(2026-11-18)를 보완하는 추가 조사다. `02_kirinuki.md`나 `06_others.md`에 이미 있는 저장소는 **(기존)** 으로 표시하고, 여기서는 새로 찾은 것을 중심으로 적었다.
> 메타데이터 수집 방법: GitHub search API(`gh api search/repositories`)에 19개 쿼리를 던졌다("chzzk soop", "치지직 숲", "topic:chzzk topic:soop", "chzzk highlight", "soop vod", "숲 채팅" 등). star 수, 라이선스(GitHub가 감지한 SPDX), 마지막 push 날짜는 2026-11-20에 조회했다. 기능 설명은 README 원문(raw.githubusercontent.com)을 직접 읽은 것이고, 읽지 못한 저장소는 "(설명문 기준)"이라고 표시했다. 라이선스 "없음"은 GitHub가 라이선스를 감지하지 못했다는 뜻이다. 이 경우 코드는 재사용할 수 없고 아이디어만 참고할 수 있다. "NOASSERTION"은 LICENSE 파일은 있지만 GitHub가 종류를 판별하지 못한 경우이며, 원문은 확인하지 않았다.
> 표기는 `★star / 라이선스 / 마지막 push (상태)`다. 상태 범례는 06 노트와 같다. **활발**은 최근 3개월 안(2026-08-20 이후)에 push가 있는 경우, **둔화**는 3~12개월, **정체**는 12개월을 넘은 경우다.

## 1. 하이라이트·클립 도구 (stream2clip과 직접 겹치는 영역)

### Takeaway
CHZZK와 SOOP 채팅을 모두 받아 하이라이트를 찾고 세로형 클립까지 렌더링하는 오픈소스는 stream2clip 말고는 찾지 못했다. 구조가 가장 가까운 것은 mw5114-tech/soop-autoclip이다. 다만 v0.1이고 SOOP에서 영상이나 채팅을 가져오는 기능이 아직 없다. CHZZK 쪽은 "후보 구간만 보여 주는" 브라우저 확장, 데스크톱 앱, 웹 서비스가 대부분이다. SOOP 쪽은 노래 구간 검출과 AI 타임라인에 몰려 있다. 거의 모두 ★0~1이고 2025~2026년에 만들어진 개인 프로젝트다.

### Cited Findings
**CHZZK**
- **Firedrago95/stream-engine (치즈픽)**: Java 25/Spring Boot와 Airflow로 만든 서비스다. CHZZK 라이브 채팅을 수백 채널에서 웹소켓으로 수집한다. 방송이 끝나면 Z-Score와 포아송 LLR 스캔으로 채팅이 폭발한 구간과 키워드를 찾는다. 분석이 끝난 원본 채팅은 파기하고 통계만 남긴다. ★0 / 없음 / 2026-10-28 (활발) — [GitHub](https://github.com/Firedrago95/stream-engine)
- **vov-y/chzzk-highlight-graph**: CHZZK 다시보기 재생바에 채팅 반응 그래프를 그리는 Chrome 확장이다. 추천 구간은 기본 최대 20개다. 영상마다 지표별 가중치를 바꿀 수 있고(0이면 그 지표 제외), 반응 키워드도 추가할 수 있다. 채팅과 분석 결과는 브라우저에 캐시한다. ★0 / 없음 / 2026-11-18 (활발) — [GitHub](https://github.com/vov-y/chzzk-highlight-graph)
- **eeengng/chzzk-highlight-ext**: Chrome 확장(Manifest V3)이다. `api.chzzk.naver.com` 페이지네이션 API로 다시보기 채팅을 모두 받는다. 10초 슬라이딩 윈도우로 밀도를 계산하고, 최소 간격 조건을 걸어 피크 N개(기본 20, 1~50)를 고른다. 피크 앞 25초와 뒤 25초를 붙여 60초 구간을 만든다. v1.3에서는 방송 시작·종료 무렵의 채팅 몰림을 빼도록 분석 구간을 지정하는 필터를 추가했다. ★1 / 없음 / 2026-04-24 (둔화) — [GitHub](https://github.com/eeengng/chzzk-highlight-ext)
- **zxc88kr/chzzk-archiver**: macOS용 셸 스크립트와 Python 3(외부 의존성 없음)으로 되어 있고, yt-dlp와 ffmpeg를 쓴다. 다시보기 링크 하나로 1080p60 영상, 채팅 전체본과 필터본, **채팅이 몰린 구간에 마커를 찍은 Premiere 마커 XML**, Obsidian 타임스탬프 노트를 만든다. `live.sh`는 채널을 감시해 녹화하고, 나중에 다시보기가 올라오면 녹화본을 다시보기로 바꾼다. ★0 / MIT / 2026-10-01 (활발) — [GitHub](https://github.com/zxc88kr/chzzk-archiver)
- **ThankyouJerry/chzzk-clip-moment-catcher**: CHZZK VOD 채팅 CSV에서 편집용 후보 구간을 찾는 PyQt6 로컬 앱이다. 영상은 내려받지 않는다(설명문과 검색 결과 기준). 같은 작성자의 ClipRadar와 ClipCatcher는 (기존) 항목이다. ★0 / MIT / 2026-11-01 (활발) — [GitHub](https://github.com/ThankyouJerry/chzzk-clip-moment-catcher)
- **pachylover/hiphant-client**: CHZZK 다시보기에서 채팅이 많은 구간의 타임스탬프를 보여 주는 웹 서비스다. 공개된 것은 Next.js 프론트엔드뿐이고 분석 백엔드는 공개되지 않았다. 데모는 hiphant.pachylover.com에 있다. ★1 / 없음 / 2026-10-21 (활발) — [GitHub](https://github.com/pachylover/hiphant-client)
- (기존) ThankyouJerry/ClipRadar, yechankun/streamer-assist, Runpad1197/chzzk_edit_point_Timer — `02_kirinuki.md` §5 참고

**SOOP**
- **mw5114-tech/soop-autoclip**: "한국어 방송 하이라이트 탐지·클립 자동 편집용 오픈소스 실험 엔진"(Python 3.10+)이다.
  - 입력은 한국어 자막 JSON과 선택 사항인 채팅 CSV(`at,text`) 또는 JSON이다.
  - 채팅량 급증과 웃음·반전 표현을 상대 평가해 후보를 찾고, 겹치는 후보를 제거한다.
  - 선택 기능으로 로컬 Ollama(qwen2.5:3b 등)가 대화 맥락을 다시 평가하고 제목을 만든다. faster-whisper 전사도 선택 기능이다.
  - FFmpeg로 MP4를 자르고, 출처 BJ·원본 URL·사용 권한을 확인하는 "게시 승인 대기" 데이터를 만든다.
  - README는 SOOP 라이브·VOD 수집, 로그인, 자동 게시가 **미구현**이라고 밝힌다.
  - CHZZK 지원과 세로형 레이아웃은 언급이 없다.
  - ★0 / MIT / 2026-11-14 (활발) — [GitHub](https://github.com/mw5114-tech/soop-autoclip)
- **SBKIM9704/SOOP_VOD_AUTO_TIMESTAMP (soopts)**: SOOP 다시보기에서 노래 구간을 찾고 곡을 식별하는 CLI다.
  - 일일 배치(`daily`)는 팬 댓글 타임라인의 🎤 마커를 정규식으로 파싱하고 노래책 카탈로그와 대조한다. 미디어는 내려받지 않는다.
  - 수동 CLI(`songs`/`clips`)는 **채팅 스티커 반응**(로그인이 필요 없는 공개 API)과 inaSpeechSegmenter 음악 구간이 겹치는 곳을 찾아 BGM과 실제 노래를 구분한다. 그다음 Groq Whisper로 가사를 전사해 곡을 식별한다.
  - 산출물은 타임스탬프와 SOOP 다시보기 딥링크다. 노래모음 영상을 YouTube에 올리는 별도 옵션도 있다.
  - ★0 / MIT / 2026-11-19 (활발) — [GitHub](https://github.com/SBKIM9704/SOOP_VOD_AUTO_TIMESTAMP)
- **32m1nd0t/soop-ai-timeline**: SOOP 다시보기로 상세 타임라인을 만들고 검수하는 Windows 앱이다.
  - 스트리머를 등록하면 신규 다시보기를 주기적으로 확인한다.
  - 선택한 VOD는 **오디오 전용 HLS만** 10분 단위 메모리 청크로 받아 faster-whisper로 전사한다. 오디오 전용 재생목록이 사라진 오래된 VOD는 최저 화질 스트림에서 오디오를 뽑는다.
  - Gemini에는 타임스탬프 자막만 보낸다. 45분 단위로 주제 경계를 판정하고, 직접 인용은 로컬 자막과 다시 대조한다.
  - 라이브는 약 15초 단위로 실시간 자막을 만든다. 5시간 단위로 나뉜 다중 파트 VOD는 전체 방송 시각을 파트별 시각으로 변환한다.
  - 검수 결과를 스트리머별로 학습해 다음 분석에 반영한다.
  - ★0 / 없음 / 2026-10-15 (활발) — [GitHub](https://github.com/32m1nd0t/soop-ai-timeline)
- (기존) ouor/cliper(CHZZK·SOOP 노래 구간), Moontaehyeon01/SOOP_VOD_SHORTS_MAKED(SOOP VOD → 쇼츠) — `02_kirinuki.md` 참고

**여러 플랫폼**
- **HLGX/KWS**: Twitch, Kick, SOOP, YouTube, CHZZK의 VOD 채팅을 키워드로 검색하고, 그 시점으로 바로 이동하는 Chrome 확장이다. ★0 / 없음 / 2026-11-17 (활발) — [GitHub](https://github.com/HLGX/KWS)
- **yanghwi99/CHZZK-SOOP-Chat-Heatmap**: 이름은 정확히 이 분야지만 설명문이 없고, 저장소 페이지가 403을 반환해 내용을 확인하지 못했다. ★0 / 없음 / 2025-12-08 (둔화) — [GitHub](https://github.com/yanghwi99/CHZZK-SOOP-Chat-Heatmap)
- **gong-beak/soop-highlight**: README가 제목 한 줄뿐이다. ★0 / 없음 / 2026-03-24 (둔화) — [GitHub](https://github.com/gong-beak/soop-highlight)

### Inferences
- stream2clip의 차별점(두 플랫폼 지원, 하이라이트에서 9:16 렌더링까지)은 여전히 유효하다. 다만 같은 문제를 푸는 개인 프로젝트가 2026년 하반기에 빠르게 늘고 있어서, 이 우위가 오래 간다고 보기는 어렵다.
- 검출 알고리즘 비교 대상:
  - stream2clip은 방송별 중앙값과 MAD를 쓰는 robust z-점수를 가중합한다(`docs/DETECTION.md`).
  - 치즈픽의 포아송 LLR 스캔은 "구간 길이를 고정하지 않고 기준선보다 유의하게 높은 구간"을 찾는 방식이다. 평가셋으로 두 방식을 비교해 볼 가치가 있다.
  - eeengng 확장의 "방송 시작·종료 구간 제외 필터"는 stream2clip의 인사말 필터, `--warmup`과 목적이 같다.
- 노래 구간 신호: soopts는 "스티커 반응 ∩ 음악 구간"으로 BGM과 실제 노래를 구분한다. stream2clip은 SOOP OGQ 스티커를 `sticker` 종류로 파싱하지만(`src/stream2clip/chat.py`) 노래 구간 검출에 쓰지는 않는다. soopts가 말하는 "스티커(작은 이모티콘)"가 OGQ 스티커와 같은 것인지는 확인하지 않았다.
- 사용자 조절 UI: chzzk-highlight-graph처럼 영상마다 가중치와 반응 키워드를 바꾸는 패널은 stream2clip 하이라이트 창에 넣을 만한 기능이다.
- 편집 프로그램 연동: stream2clip의 마커 내보내기는 DaVinci Resolve용 EDL 형식이다(`src/stream2clip/handoff.py`). chzzk-archiver처럼 Premiere에서 바로 마커로 가져오는 XML을 추가할 수 있다.
- 저대역 전사: soop-ai-timeline의 "오디오 전용 HLS만 청크로 받아 전사하는" 방식은 긴 다시보기의 자막과 신호를 만들 때 영상 전체 다운로드를 피하는 방법이다.

### Gaps
- 위 도구들을 실제로 돌려 보지 않았다. 검출 품질은 README 서술만으로 판단할 수 없다.
- yanghwi99/CHZZK-SOOP-Chat-Heatmap의 내용은 확인하지 못했다.
- hiphant의 분석 알고리즘은 백엔드가 공개되지 않아 알 수 없다.

## 2. 여러 플랫폼을 묶는 채팅·후원 라이브러리, SOOP 채팅 라이브러리

### Takeaway
CHZZK와 SOOP을 한 인터페이스로 묶은 라이브러리는 Java(stream4j)와 TypeScript(Poly_chat)뿐이고 Python에는 없다. SOOP 채팅만 다루는 라이브러리는 Java, TS/Node, C#, Go, Unity로 여럿 있지만, 활발히 관리되는 Python 라이브러리는 찾지 못했다. 그러니 Python 프로젝트인 stream2clip은 지금처럼 자체 어댑터를 유지하는 것이 맞다. CHZZK·SOOP 라이브 채팅 직접 수신은 v0.8에서 구현됐다.

### Cited Findings
**여러 플랫폼 통합**
- **bbobbogi/stream4j**: CHZZK, CiMe, SOOP, YouTube, Toonation의 채팅과 후원을 하나의 Java/Kotlin API로 다룬다. URL을 넣으면 플랫폼을 자동으로 감지하고, 메시지를 공통 형식으로 넘기며, 끊기면 자동 재연결한다. SOOP은 채팅, 후원, 방송 종료 감지를 지원하고 인증은 선택이다. R2turnTrue/chzzk4j(★46 / MIT / 2026-10-23)에서 출발했다. ★0 / MIT / 2026-11-18 (활발) — [GitHub](https://github.com/bbobbogi/stream4j)
- **Thedum2/Poly_chat**: YouTube, CHZZK, SOOP 채팅을 어댑터 패턴으로 묶은 TypeScript 라이브러리다(npm `polychat-bridge`). 플랫폼마다 개발자센터에서 OAuth 클라이언트를 만들어야 한다고 안내한다. 즉 공식 API를 쓰므로 §3의 "본인 채널" 제약을 그대로 받는다. ★3 / MIT / 2026-09-29 (활발) — [GitHub](https://github.com/Thedum2/Poly_chat)
- **Hanbyori/Web_StreamingChatCombine**: SOOP과 CHZZK의 여러 채널 채팅을 합산한다(Python, README 한 줄). ★1 / MIT / 2025-05-01 (둔화) — [GitHub](https://github.com/Hanbyori/Web_StreamingChatCombine)
- **h66rogi/hogi-chat**: SOOP 라이브 채팅 파이프라인이다. 실시간 수집과 전사, AI 후보 생성, 사람 승인, 방송 전송까지 한다(설명문 기준). ⚠ ★0 / AGPL-3.0 / 2026-11-02 (활발) — [GitHub](https://github.com/h66rogi/hogi-chat)

**SOOP 채팅 단일 플랫폼 라이브러리**
- getCurrentThread/soopapi (Java): ★9 / MIT / 2026-09-24 (활발) — [GitHub](https://github.com/getCurrentThread/soopapi)
- zzik2/soop4j (Java 11+): 라이브 정보, 방송국 정보, 채팅 WebSocket. Maven Central `kr.zzik2:soop4j`(검색 결과 기준). ★5 / MIT / 2026-09-12 (활발) — [GitHub](https://github.com/zzik2/soop4j)
- joyfuI/soop-chat (TypeScript, npm `soop-chat`): 읽기 전용이고 채팅 전송은 지원하지 않는다. 같은 작성자의 soop-chat-collector와 soop-chat-webtool도 있다. ★0 / MIT / 2026-11-07 (활발) — [GitHub](https://github.com/joyfuI/soop-chat)
- obabo0801/SOOP-Chat (Node.js): ★2 / MIT / 2026-11-14 (활발) — [GitHub](https://github.com/obabo0801/SOOP-Chat)
- w0lfv/SoopChatNet (C#): ★4 / MIT / 2026-04-25 (둔화) — [GitHub](https://github.com/w0lfv/SoopChatNet)
- halfdogs/soopchat (Go): README가 "학습용이며 언제든 깨지거나 바뀔 수 있다"고 밝힌다. ★5 / MIT / 2026-04-19 (둔화) — [GitHub](https://github.com/halfdogs/soopchat)
- IVAEU/SoopChat (Unity): ★3 / 없음 / 2025-06-10 (둔화) — [GitHub](https://github.com/IVAEU/SoopChat)
- Python: wakscord/afreeca("AfreecaTV API Wrapper", PyPI `afreeca`)가 검색에 나왔다. 하지만 GitHub search API가 이 저장소를 찾지 못해(HTTP 422) 관리 상태를 확인하지 못했다 — [GitHub](https://github.com/wakscord/afreeca)

**CHZZK 채팅 보관·분석 (참고)**
- PCBiS/chzzk-chat-archive: kimcore/chzzk로 방송별 채팅을 JSONL로 저장한다(`*_live.jsonl`, `*_off.jsonl`). 참여자 분석 웹 화면과 **AI 도구용 읽기 전용 MCP 엔드포인트**(`/mcp`)를 제공한다. ★1 / MIT / 2026-11-19 (활발) — [GitHub](https://github.com/PCBiS/chzzk-chat-archive)
- hypn4/chzzk-python(Python SDK, 비공식 채팅 클라이언트): ★0 / MIT / 2026-02-08 (둔화) — [GitHub](https://github.com/hypn4/chzzk-python). (기존) gunyu1019/chzzkpy, kimcore/chzzk — `06_others.md` §1 참고

### Inferences
- stream4j와 Poly_chat의 공통 메시지 형식(채팅, 후원, 구독 이벤트)은 stream2clip `ChatMessage`의 `kind`/`amount`/`currency` 설계와 비교해 볼 만하다. 특히 CiMe와 Toonation처럼 stream2clip이 아직 다루지 않는 플랫폼을 붙일 때 참고가 된다.
- SOOP 채팅 프로토콜은 비공식이라 언제든 깨질 수 있다. 여러 언어의 구현체가 따로 관리되고 있으므로, 깨졌을 때 이들의 최근 커밋을 보면 프로토콜 변경을 빨리 파악할 수 있다.

## 3. CHZZK·SOOP 공식 Open API

### Takeaway
두 플랫폼 모두 **공식 Open API가 있다**. 06 노트의 "공식 API가 확인되지 않았다"는 서술은 틀렸고, 2026-11-20에 고쳤다. 그런데 공식 API로 채팅을 받으려면 OAuth로 동의한 **본인 채널**이어야 한다. CHZZK는 토큰 주인의 이벤트만, SOOP은 본인 방송만 연결할 수 있다. 다시보기(VOD) 채팅을 내려 주는 공식 API는 두 문서 어디에서도 찾지 못했다. 따라서 남의 방송과 다시보기를 다루는 키리누키 편집은 공식 API로 할 수 없다. 공식 API는 스트리머 본인이 자기 방송에 쓰는 경우에만 대안이 된다.

### Cited Findings
**CHZZK Developers**
- 공식 문서는 GitBook에 있다(`developers.chzzk.naver.com`에서 연결). 목차는 Authorization, 참고사항, Session, User, Channel, Category, Live, Chat, Drops, Restriction이다. 다시보기나 클립 항목은 없다 — [CHZZK Developers](https://chzzk.gitbook.io/chzzk), [문서 목차 llms.txt](https://chzzk.gitbook.io/chzzk/llms.txt)
- 소개 페이지에 따르면 라이브 조회, 방송 설정 조회와 변경, 채팅 발송, 채팅 공지 등록 등을 제공한다 — [About CHZZK Developers](https://chzzk.gitbook.io/chzzk)
- Session API — [Session](https://chzzk.gitbook.io/chzzk/chzzk-api/session)
  - 세션 생성은 두 종류다. 클라이언트 인증 세션(`GET /open/v1/sessions/auth/client`)은 최대 10개 연결을 유지할 수 있다. 유저 Access Token 세션은 유저별 최대 3개이고, "세션 생성에 사용된 Access Token과 동일한 유저 이벤트만 구독할 수 있다".
  - 채팅 이벤트 구독은 `POST /open/v1/sessions/events/subscribe/chat`이고 관련 Scope는 "채팅 메시지 조회"다. 설명은 "요청한 세션에 사용자의 채팅 이벤트를 구독합니다"이며, 세션당 최대 30개 이벤트를 구독할 수 있다.
  - 이벤트 종류는 CHAT, DONATION, SUBSCRIPTION이다. 후원 이벤트에는 `donationType`(CHAT/VIDEO), `payAmount`(원), `donationText`, `emojis`가 담긴다.
  - 소켓 연결은 Socket.IO-client 1.0.0 이상 2.0.3 이하만 지원한다.

**SOOP Developers**
- 공식 개발자 사이트가 있다. 사이트는 SPA라서 아래 내용은 사이트 JS 번들 안의 문서 문자열에서 읽었다 — [SOOP Developers](https://developers.sooplive.co.kr/)
- 문서 구성은 세 부분이다.
  - API: 시작하기, 인증 및 토큰, 방송 송출, 방송 시청, 전자비서, VOD, 멤버십
  - Chat SDK: 개요, 시작하기, OAuth, 채팅 연결, 채팅 관리, 채팅 메세지 전송·조회, 후원 메세지 조회
  - Extensions
- Chat SDK 문서 문구는 다음과 같다. "브라우저 환경에서 사용할 수 있는 방송 채팅창 관리 메서드를 제공", "현재 채팅 SDK는 JavaScript를 활용한 웹 브라우저 환경에서 개발을 지원", "현재 SDK로 개발된 프로그램은 본인 방송에만 접속하여 사용이 가능". 채팅 연결 항목에는 "현재는 본인 방송에만 접속할 수 있습니다. 향후 streamerId or broadNo를 매개변수로 받아서 다른 방송에도 접속할 수 있도록 할 예정"이라고 적혀 있다.
- API 범위(scope) 설명에 다음 항목이 있다.
  - `broad_review_list`: 특정 유저의 전체 공개 다시보기 VOD 목록
  - `validate_live_status`: 생방송 상태와 상세 정보
  - `user_stationinfo`: 방송국 이름, 프로필, 최근 방송일, 애청자 수 등
  - `validate_vod_owner`
  - `broad_access_chatinfo`: 채팅 메시지 조회와 보내기, 채팅 관리, 후원 메시지 조회
- 일부 scope는 별도 심사를 거친다. 이메일, 구현 기능, 연관 스트리머, 개인정보처리방침 등을 내면 SOOP Developers 운영팀이 승인한다. 애플리케이션을 만들면 API KEY(Client ID/Secret)가 발급된다. VOD 항목에는 oEmbed(`oembed/oembedinfo`)가 있다. 예시의 API 호스트는 `openapi.sooplive.com`이다.

### Inferences
- stream2clip은 지금 비공식 엔드포인트를 쓴다.
  - CHZZK: `api.chzzk.naver.com/service`, `polling/v2/channels/{channel}/live-status`
  - SOOP: `api.m.sooplive.co.kr/station/video/a/view`, `live.sooplive.co.kr/afreeca/player_live_api.php`
  - 남의 방송과 다시보기를 다루는 한, 이 방식은 당분간 유지할 수밖에 없다. 대신 플랫폼별 어댑터로 격리해 두는 것이 중요하다.
- 스트리머 본인이 자기 방송에 라이브 모드를 쓰는 경우에는 공식 API를 선택 백엔드로 둘 수 있다.
  - CHZZK Session API는 Socket.IO 2.x 프로토콜을 요구한다. Python에서는 python-socketio 4.x 계열이 이 프로토콜과 호환되는 것으로 알고 있으나 확인하지 않았다.
  - SOOP Chat SDK는 브라우저 JS 전용이라 PySide6 앱에서 바로 쓰기 어렵다. 쓰려면 내장 웹뷰나 브라우저 소스 같은 우회가 필요하다.
- 공식 API의 후원 이벤트(`payAmount`)와 SOOP 후원 메시지 조회는 후원 급증을 하이라이트 신호로 쓸 때 공식 경로가 된다.

### Gaps
- 앱 등록과 OAuth 동의가 필요해서 공식 API를 실제로 호출해 보지 않았다.
- SOOP 문서는 SPA 번들의 문자열에서 읽었으므로, 렌더된 페이지와 표현이 다를 수 있다.
- CHZZK 클라이언트 인증 세션으로 임의 채널의 채팅을 구독할 수 있는지는 확인하지 않았다. 문서 문구("사용자의 채팅 이벤트", Scope "채팅 메시지 조회")를 근거로 불가능하다고 해석했다.
- 두 플랫폼의 Open API 이용약관(데이터 보관, 2차 이용, 상업적 이용 제한)은 읽지 않았다.

## 4. 녹화·다운로드 (CHZZK와 SOOP을 함께 지원)

### Takeaway
녹화기와 다운로더는 이미 많다. 그래서 stream2clip이 직접 녹화기를 만들 이유는 약하다. 구간 다운로드는 yt-dlp에, 녹화는 기존 도구에 맡기는 현재 방향이 맞다.

### Cited Findings
- **LEEJUNSEO04/CHZZK-SOOP-Recorder**: Windows용 CHZZK·SOOP 자동 녹화기다.
  - 방송 감지, 다중 스트리머 감시, 웹 대시보드, 파일 병합, YouTube 업로드, 썸네일 생성(OpenAI 이미지 API)을 지원한다.
  - Python, FFmpeg, MySQL/MariaDB, Chrome이 필요하다.
  - README는 SOOP 녹화가 로그인·세션·페이지 구조 변경에 영향을 받아 CHZZK보다 불안정할 수 있다고 경고한다.
  - ★0 / NOASSERTION / 2026-09-24 (활발) — [GitHub](https://github.com/LEEJUNSEO04/CHZZK-SOOP-Recorder)
- **olivedapp/olived**: Go로 만든 자동 녹화기다. Bilibili, Douyin, Flextv, Kick, LiveMe, Mixch, CHZZK, SOOP 등을 지원한다(설명문 기준). ★87 / 없음 / 2026-10-12 (활발) — [GitHub](https://github.com/olivedapp/olived)
- **ihmily/DouyinLiveRecorder**: Python 다중 플랫폼 녹화기다. 설명문에 sooplive, flextv, popkontv, twitcasting, winktv 등이 나온다. CHZZK 지원 여부는 설명문에 없어 확인하지 못했다. ★11,266 / MIT / 2026-04-01 (둔화) — [GitHub](https://github.com/ihmily/DouyinLiveRecorder)
- **eruminyu/Rookery**: CHZZK, TwitCasting, X Spaces, YouTube 라이브를 감시해 자동 녹화한다. VOD 다운로드, 채팅 아카이브와 통계, Discord 알림을 하나의 웹 UI로 관리한다(설명문 기준). SOOP은 지원하지 않는다. ★3 / MIT / 2026-11-01 (활발) — [GitHub](https://github.com/eruminyu/Rookery)
- **ghfhffh12345/chzzk-load**: Rust로 만든 도구다. CHZZK 자동 녹화, 실시간 채팅 아카이브, rclone 클라우드 동기화를 한다(설명문 기준). ★0 / Apache-2.0 / 2026-11-17 (활발) — [GitHub](https://github.com/ghfhffh12345/chzzk-load)
- 소규모 다운로더(모두 ★0~2, 설명문 기준):
  - kaskobi2023-boop/StreamNest: C#, MIT, 2026-10-20. CHZZK·YouTube·SOOP
  - OrcusExtreme/ORCUS-Downloader: Python, MIT, 2026-10-08
  - Min790/S.D.Chan: 없음, 2026-03-26. SOOP·CHZZK VOD와 클립
  - Redater2254/yudown: 없음, 2026-06-01. SOOP·CHZZK
  - NB-XX/SOOP_VOD_DL: 없음, 2026-08-15
  - agjvrkgj/yopoq: MIT, 2026-03-04. SOOP VOD 다운로드 봇
  - LuneFleurs/Chzzk-Downloader: Rust, MIT, 2026-09-30
- (기존) horsaen/afreeca-downloader, honey720/chzzk-vod-downloader-v2, Choonholic/ChzzkDownloader, HO-Silverplate/SOOP-VOD-downloader — `02_kirinuki.md` §1 Q2 참고

### Inferences
- chzzk-archiver와 Rookery는 "라이브를 녹화해 두었다가, 다시보기가 올라오면 다시보기를 정본으로 바꾸는" 운영 방식을 쓴다. stream2clip 라이브 모드(OBS 리플레이 저장)의 결과물을 나중에 다시보기와 맞춰 볼 때 참고할 수 있다.

## 5. 범위 밖이지만 검색에 나온 것 (간단 목록)
- 멀티뷰: jebibot/mullive(★9 / NOASSERTION / 2026-11-19) — [GitHub](https://github.com/jebibot/mullive). minsuho/moabom(★1 / NOASSERTION / 2026-10-25) — [GitHub](https://github.com/minsuho/moabom)
- 후원 연동(주로 마인크래프트): Colla-Bot/mc-donation(★6 / NOASSERTION / 2026-05-12) — [GitHub](https://github.com/Colla-Bot/mc-donation). taromati/done-connector(★18 / MIT / 2026-01-28) — [GitHub](https://github.com/taromati/done-connector). RTUStudio/DonationAPI(★4 / ⚠ GPL-3.0 / 2026-04-12) — [GitHub](https://github.com/RTUStudio/DonationAPI)
- 알림·모니터링: laikal/HIKI-Notifier, noblesi/soop-chzzk-live-notifier, intrandom5/chzzk-soop-live-board, bngts/bngts. VOD 정리: (기존) HWcoms/StreamVODTracker, bchsol/soop-keeper. 데이터 파이프라인: Jaeho-99/InternetBroadcastDataHub, Recklehs/chzzk-chat-pipeline.

## 6. 종합 (stream2clip 관점)

### Takeaway
"CHZZK·SOOP 채팅 수신 → 하이라이트 검출 → 세로형 클립 렌더링"을 한 도구로 이어 주는 오픈소스는 여전히 stream2clip뿐이다. 주변 도구는 세 갈래로 나뉜다. 후보 구간만 보여 주는 도구, 노래와 타임라인 같은 특화 도구, 녹화·다운로드 도구다. 공식 Open API는 두 플랫폼 모두 있지만, 본인 채널에만 쓸 수 있어 키리누키 용도와 맞지 않는다.

### Inferences
- 가져올 만한 아이디어(코드 재사용 여부는 각 항목의 라이선스를 따른다):
  1. 포아송 LLR 스캔으로 길이가 정해지지 않은 급증 구간 찾기(치즈픽, 라이선스 없음이라 아이디어만)
  2. 스티커 반응과 음악 구간을 겹쳐 노래 구간 찾기(soopts, MIT)
  3. 영상별 가중치와 반응 키워드를 사용자가 조절하는 패널(chzzk-highlight-graph, 라이선스 없음이라 아이디어만)
  4. Premiere 마커 XML 내보내기(chzzk-archiver, MIT)
  5. 오디오 전용 HLS 청크 전사(soop-ai-timeline, 라이선스 없음이라 아이디어만)
  6. 게시 전 "출처·원본 URL·사용 권한" 확인 데이터(soop-autoclip, MIT). stream2clip의 출처 표기(`--credit`)와 기획사 가이드라인 점검을 넓히는 방향과 같다.
- 라이선스: 이번에 찾은 저장소는 대부분 MIT이거나 라이선스가 없다. 라이선스 없음, NOASSERTION, AGPL-3.0(hogi-chat), GPL-3.0(DonationAPI) 저장소에서는 코드를 가져오지 않는다.
- 기존 노트와 보고서의 "CHZZK/SOOP 지원이 비어 있는 영역"이라는 판단은 유지된다. 다만 2026-11 기준으로 비슷한 개인 프로젝트가 계속 늘고 있으므로 정기적으로 다시 검색할 필요가 있다.
