# 기타 VTuber 관련 외부 프로젝트 (데이터/API, AI VTuber, 음성, 번역·자막, OBS, 팬 툴, 저작권, 엔드투엔드 유사 프로젝트)

> 조사 기준일: 2026-11-18. 범위 밖(다른 조사자 담당): 쇼츠 제작, 키리누키/하이라이트 추출 알고리즘, 아바타 렌더링, Live2D, 3D/VRM.
> 메타데이터 수집 방법: GitHub REST API가 이 세션에서 막혀 있어 star 수, 마지막 push 날짜, 설명은 GitHub 미러 API `ungh.cc`(`https://ungh.cc/repos/{owner}/{repo}`)로, 라이선스는 각 저장소의 `LICENSE` 파일 본문(raw.githubusercontent.com)을 직접 읽어 판별했다(2026-11-18 조회). "archived" 플래그는 직접 확인하지 못했으므로, 아래 상태 표시는 마지막 push 날짜와 README의 공지 문구를 근거로 한다. 표기는 `★star / 라이선스 / 마지막 push`.
> 상태 범례: **활발**(최근 3개월 내 push), **둔화**(3~12개월), **정체**(12개월 넘음), **중단**(README에 유지보수 중단 공지).
> 2026-11-20 정정: §1의 "CHZZK/SOOP 공식 API가 확인되지 않았다"는 서술은 틀렸다. 두 플랫폼 모두 공식 Open API가 있다. 다만 채팅 수신은 OAuth로 동의한 본인 채널에만 쓸 수 있다. §1의 Takeaway, 한국 항목, Inferences, Gaps와 §8 Inferences를 고쳤다. CHZZK·SOOP 추가 조사(공식 API 세부, 외부 오픈소스)는 `07_chzzk_soop.md`에 있다.

## 1. VTuber 데이터/메타데이터 플랫폼과 API (Holodex, 스케줄 트래커, vtbs.moe, 시청 통계, 한국 CHZZK/SOOP)

### Takeaway
stream2clip이 바로 쓸 수 있는 공개 API는 사실상 Holodex v2 하나다. 라이브/아카이브/클립 목록, 곡 정보, 타임스탬프 댓글까지 제공한다. 다만 API 키가 필요하고, 파생 콘텐츠에 유료 과금을 금지하는 약관이 있다. 한국(CHZZK/SOOP)에는 VTuber 전용 통계 사이트가 확인되지 않았다. 두 플랫폼 모두 공식 Open API가 있지만, 채팅은 OAuth로 동의한 본인 채널에서만 받을 수 있고 다시보기 채팅 API는 문서에 없다. 그래서 남의 방송과 다시보기를 다루는 클립 작업은 비공식 라이브러리, 비공식 엔드포인트, streamlink 플러그인에 기대야 한다.

### Cited Findings
**Holodex (홀로덱스)**
- Holodex 프런트엔드는 오픈소스다. HolodexNet/Holodex ★674 / MIT / 2026-11-11 (활발) — [GitHub](https://github.com/HolodexNet/Holodex)
- API 베이스 URL은 `https://holodex.net/api/v2`이고 모든 요청에 `X-APIKEY` 헤더가 필요하다. 키는 계정 설정에서 발급한다. 레이트리밋 수치는 공개돼 있지 않고 "과도한 사용은 제한·정지할 수 있다"고만 적혀 있다 — [Holodex API Docs](https://docs.holodex.net/)
- 주요 엔드포인트는 `/live`(라이브·예정, 기본 48시간 창), `/users/live`(고정 채널 목록용 경량 조회), `/videos`(채널·상태·type·topic·org·언어·기간 필터), `/channels/{id}/clips|videos|collabs`, `POST /search/videoSearch`, `POST /search/commentSearch`다. 클립은 `type=clip`인 영상이고, 영상 객체에 `clips` 배열이 있다 — [Holodex API Docs](https://docs.holodex.net/)
- 단일 영상 요청에 `c=1`을 붙이면 타임스탬프 댓글이 반환된다. `songs` include로 곡 목록(`songs`, `songcount`)도 받을 수 있다 — [Holodex API Docs](https://docs.holodex.net/)
- 약관 요지: 철회 가능한 제한적 라이선스, 용도별 키 1개, API나 파생 콘텐츠에 프리미엄 과금 금지, 공개 시 Holodex 출처 표기 — [Holodex API Docs](https://docs.holodex.net/)
- 클라이언트 라이브러리: 공식 holodex.js ★24 / MIT / 2022-04-18 (정체) — [GitHub](https://github.com/HolodexNet/holodex.js). 서드파티 npm `@stu43005/holodex-api` — [npm](https://npmjs.com/package/@stu43005/holodex-api). Rust 크레이트 `holodex`(v2 래퍼) — [docs.rs](https://docs.rs/crate/holodex/latest/source/src/client.rs)

**스케줄·통계 트래커**
- vtbs.moe(빌리빌리 VTuber 통계): dd-center/vtbs.moe ★641 / MIT / 2026-11-11 (활발) — [GitHub](https://github.com/dd-center/vtbs.moe)
- HoloStats 후신 vtstats/web("VTubers Statistics and Data Visualization"): ★144 / 라이선스 미확인 / 2024-07-02 (정체). PoiScript/HoloStats가 이 저장소로 리다이렉트된다 — [GitHub](https://github.com/vtstats/web)
- 브이스포 스케줄 "すぽじゅーる": vspo-lab/vspo-portal ★23 / MIT / 2026-11-08 (활발, WIP) — [GitHub](https://github.com/vspo-lab/vspo-portal)
- Playboard: VTuber 슈퍼챗 랭킹을 국가·기간별로 공개한다 — [Playboard 주간 VTuber 슈퍼챗 랭킹](https://playboard.co/en/youtube-ranking/most-superchatted-v-tuber-channels-in-worldwide-weekly). 2025년 연간 1위는 Nekomoto Patra로 보도됐다 — [4Gamers](https://www.4gamers.com.tw/news/detail/75792/playboard-youtube-ranking-most-superchatted-v-tuber-channels-in-worldwide-2025)
- Playboard 슈퍼챗 집계는 2020-01-10에 시작됐다. r/HoloStatistics의 한 분석은 Playboard가 잘못 집계하는 사례를 들어 수치를 "proper data"로 보기 어렵다고 지적한다 — [r/HoloStatistics 2023 연말 분석 (redlib 미러로 확인)](https://www.reddit.com/r/HoloStatistics/comments/18jts9h/2023_year_end_superchat_leaders)
- StreamsCharts는 유료 데이터 API를 운영한다. 채널 단위 지표와 실시간 방송 현황을 5분 주기로 갱신하고, 현재 추적 중인 플랫폼 9개와 서비스 종료 플랫폼 4개의 과거 데이터를 다룬다 — [StreamsCharts API](https://streamscharts.com/api). 채널 목록에는 VTuber 필터가 있다 — [StreamsCharts channels?vtuber](https://streamscharts.com/channels?vtuber=all)

**한국 (CHZZK / SOOP)**
- StreamsCharts는 2024년 6월부터 SOOP 통계를 제공한다 — [European Gaming 보도자료](https://europeangaming.eu/portal/press-releases/2024/06/21/161720/soop-statistics-are-now-available-on-streams-charts/). SOOP 개요 페이지 — [StreamsCharts SOOP](https://streamscharts.com/overview?platform=afreecatv)
- Stream Hatchet의 SOOP 첫 주 리뷰(2024)에서 VTuber 아이네가 최다 시청 스트리머 10위에 올랐다 — [Stream Hatchet](https://streamhatchet.com/blog/soop-first-week-in-live-streaming-review/)
- CHZZK 비공식 라이브러리: kimcore/chzzk(JS) ★211 / MIT / 2024-08-13 (정체) — [GitHub](https://github.com/kimcore/chzzk). gunyu1019/chzzkpy(Python) ★47 / MIT / 2026-11-12 (활발) — [GitHub](https://github.com/gunyu1019/chzzkpy)
- streamlink 본가에 `chzzk.py`와 `soop.py` 플러그인이 있다. `afreeca.py`는 더 이상 없다(SOOP로 이름 변경). `twitcasting.py`와 `nicolive.py`도 있다. chzzk 플러그인 메타데이터는 `$type live, vod`다 — [streamlink plugins 디렉터리](https://github.com/streamlink/streamlink/tree/master/src/streamlink/plugins)
- (2026-11-20 추가) CHZZK 공식 Open API(CHZZK Developers):
  - 문서 목차는 Authorization, Session, User, Channel, Category, Live, Chat, Drops, Restriction이다. 다시보기와 클립 항목은 없다.
  - 채팅 이벤트 구독(`POST /open/v1/sessions/events/subscribe/chat`, Scope "채팅 메시지 조회")은 "사용자의 채팅 이벤트"를 구독한다.
  - 유저 세션은 "세션 생성에 사용된 Access Token과 동일한 유저 이벤트만 구독"할 수 있다.
  - 소켓은 Socket.IO-client 1.0.0~2.0.3만 지원한다.
  - 출처 — [CHZZK Developers](https://chzzk.gitbook.io/chzzk), [Session](https://chzzk.gitbook.io/chzzk/chzzk-api/session)
- (2026-11-20 추가) SOOP 공식 Open API와 Chat SDK(SOOP Developers):
  - API 범위에는 다시보기 목록(`broad_review_list`), 생방송 상태(`validate_live_status`), 방송국 정보, 채팅 조회·전송·후원 메시지 조회(`broad_access_chatinfo`) 등이 있다.
  - Chat SDK는 브라우저 JavaScript 전용이다. 문서는 "현재 SDK로 개발된 프로그램은 본인 방송에만 접속하여 사용이 가능"하다고 밝힌다.
  - 일부 scope는 별도 심사를 거친다.
  - 출처 — [SOOP Developers](https://developers.sooplive.co.kr/) (SPA라서 사이트 JS 번들의 문서 문자열로 확인)

### Inferences
- stream2clip의 "소스 발견" 단계(어떤 방송을 언제 클립할지)는 Holodex `/live`·`/videos`·`/channels/{id}/clips`로 구현할 수 있다. `c=1` 타임스탬프 댓글은 하이라이트 후보의 약한 라벨(weak label)로 쓸 수 있다. 다만 상업 서비스로 만들면 "파생 콘텐츠 프리미엄 과금 금지" 조항과 충돌할 수 있으니 약관 검토가 필요하다.
- 한국 VTuber를 지원하려면 chzzkpy + streamlink(chzzk/soop 플러그인) 조합이 가장 현실적이다. 메타데이터 DB는 자체 구축해야 한다. 공식 Open API는 본인 채널 전용이라 키리누키 편집자의 주 용도(남의 방송, 다시보기)에는 쓸 수 없다. 스트리머가 자기 방송에 라이브 모드를 쓸 때만 선택 백엔드로 검토할 만하다.
- 통계 사이트(Playboard, StreamsCharts)는 채널 우선순위 결정용 참고 자료다. 파이프라인 입력으로는 부적합하다(유료이거나 정확도 논란이 있음).

### Gaps
- Holodex API의 실제 레이트리밋 수치는 문서에 없다.
- TwitchTracker와 SullyGnome의 API 제공 여부와 조건은 이번 검색에서 1차 출처로 확인하지 못했다.
- CHZZK/SOOP VTuber 전용 통계 사이트(예: 커뮤니티 운영 랭킹)는 검색으로 찾지 못했다.
- CHZZK·SOOP 공식 Open API는 문서만 읽었고 실제로 호출해 보지 않았다(앱 등록과 OAuth 동의 필요). 이용약관도 읽지 않았다.
- 공식 hololive/にじさんじ 스케줄 사이트의 API 존재 여부는 확인하지 않았다.

## 2. AI VTuber (LLM + TTS + 아바타 파이프라인)

### Takeaway
2026년 기준 가장 큰 생태계는 moeru-ai/AIRI(★5만 이상, MIT, 매일 커밋)와 Open-LLM-VTuber(★1.4만, MIT, 2026-05 이후 둔화)다. 중국(Luna AI 계열)과 일본(AITuberKit, ChatdollKit) 생태계도 활발하다. stream2clip에 직접 쓸 부분은 적고, ASR/TTS/LLM 모듈 구성 방식을 참고하는 정도다.

### Cited Findings
- **moeru-ai/airi**: 셀프호스팅 AI 컴패니언/VTuber. ★51,518 / MIT / 2026-11-18 (활발) — [GitHub](https://github.com/moeru-ai/airi)
- **Open-LLM-VTuber**: 음성 핸즈프리 대화, 음성 끼어들기(interruption), Live2D, 로컬 크로스플랫폼. ★14,751 / MIT / 2026-05-15 (둔화) — [GitHub](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)
- **Ikaros-521/AI-Vtuber (Luna AI, 중국어권)**: ChatGPT, Claude, LangChain, ChatGLM, Qwen, Kimi, Ollama 등 다수 LLM 백엔드를 지원한다. ★4,631 / GPL-3.0 / 2026-11-08 (활발) — [GitHub](https://github.com/Ikaros-521/AI-Vtuber)
- **AkagawaTsurunaki/ZerolanLiveRobot**: LLM, ASR, TTS, OCR, CV를 결합한 라이브 방송·마인크래프트용 AI VTuber. ★830 / MIT / 2026-04-14 (둔화) — [GitHub](https://github.com/AkagawaTsurunaki/ZerolanLiveRobot)
- **kimjammer/Neuro**: Neuro-sama를 7일 만에 재현한 프로젝트. ★2,124 / MIT / 2025-01-17 (정체) — [GitHub](https://github.com/kimjammer/Neuro)
- **VedalAI/neuro-sdk**: Neuro-sama 운영자 측의 공식 SDK/API로, Neuro가 게임을 플레이하게 하는 연동용이다. ★908 / MIT / 2026-11-11 (활발) — [GitHub](https://github.com/VedalAI/neuro-sdk)
- **elevenyellow/handcrafted-persona-engine** (구 fagenorn): Live2D, LLM, ASR, TTS, RVC를 묶은 아바타 엔진. ★1,399 / 라이선스 미확인 / 2026-05-20 (둔화) — [GitHub](https://github.com/elevenyellow/handcrafted-persona-engine)
- **ardha27/AI-Waifu-Vtuber**: YouTube/Twitch 방송용 AI VTuber. ★1,127 / 라이선스 파일 미확인 / 2026-05-31 — [GitHub](https://github.com/ardha27/AI-Waifu-Vtuber)
- **SugarcaneDefender/z-waif**: 완전 로컬 AI 와이프. ★613 / MIT / 2026-06-19 — [GitHub](https://github.com/SugarcaneDefender/z-waif)
- **Koischizo/AI-Vtuber**: ★491 / MIT / 2023-03-18 (정체) — [GitHub](https://github.com/Koischizo/AI-Vtuber)
- **zixiiu/Digital_Life_Server**: 중국어권 "살아있는 음성 비서". ★2,537 / MIT / 2023-12-01 (정체) — [GitHub](https://github.com/zixiiu/Digital_Life_Server)
- **tegnike/aituber-kit (일본 AITuber)**: ★1,149 / 2026-11-17 (활발). v2.0.0부터 커스텀 라이선스로 바뀌어 비상업 이용은 무료, 상업 이용은 별도 라이선스가 필요하다 — [GitHub LICENSE](https://github.com/tegnike/aituber-kit/blob/main/LICENSE)
- **uezo/ChatdollKit (일본)**: 3D 모델을 챗봇으로 만드는 툴킷. ★1,285 / Apache-2.0 / 2026-10-31 (활발) — [GitHub](https://github.com/uezo/ChatdollKit)

### Inferences
- stream2clip에 바로 가져올 만한 건 이들 프로젝트의 ASR→LLM→TTS 오케스트레이션 패턴이다. 특히 AIRI와 Open-LLM-VTuber는 다양한 ASR/TTS 백엔드를 어댑터 패턴으로 추상화한다. 이를 참고하면 stream2clip에서 Whisper 계열과 TTS 내레이션을 플러그형으로 설계할 수 있다.
- AI VTuber의 방송 자체도 클립 대상이다(Neuro-sama 클립 채널이 대표적이다). 다만 이 경우에도 원본 권리자 가이드라인이 적용된다.
- aituber-kit은 상업 이용 시 라이선스가 필요하므로 코드 재사용은 피하는 편이 안전하다.

### Gaps
- 각 프로젝트의 정확한 사용자 수나 실제 방송 운영 사례는 확인하지 않았다.
- handcrafted-persona-engine, ardha27/AI-Waifu-Vtuber의 라이선스 파일은 확인하지 못했다.
- 한국어권 AI VTuber 오픈소스 프로젝트는 별도로 검색하지 않았다.

## 3. 음성: 보이스 체인저와 TTS (클립 내레이션 용도, 라이선스, 일본어·한국어 지원)

### Takeaway
내레이션 TTS 후보 중 일본어·한국어를 함께 지원하고 라이선스가 관대한 것은 GPT-SoVITS(MIT, JA/KO 교차언어)와 CosyVoice(Apache-2.0)다. 일본어 전용으로는 VOICEVOX(크레딧 표기 필수), AivisSpeech(LGPL), Irodori-TTS(코드 MIT)가 강하다. Fish-Speech와 IndexTTS는 커스텀 상업 제한 라이선스라 주의가 필요하다. 가장 중요한 원칙은 VTuber 본인 목소리를 학습한 음성 클론을 클립에 쓰지 않는 것이다. 이는 기획사 가이드라인 위반 소지가 크다(섹션 7 참조).

### Cited Findings
**보이스 체인저 / 음성 변환**
- **RVC WebUI** (RVC-Project/Retrieval-based-Voice-Conversion-WebUI): 10분 이하 음성 데이터로 VC 모델 학습. ★39,313 / MIT / 2026-08-04 — [GitHub](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI)
- **so-vits-svc**: ★28,032 / AGPL-3.0 / 마지막 push 2023-11-11 (정체). README에 "데이터셋 권리 문제는 사용자 책임"이라는 경고와, 기타 목적 사용 시 사전 연락 요구가 있다 — [GitHub](https://github.com/svc-develop-team/so-vits-svc)
- **w-okada/voice-changer**: 실시간 보이스 체인저(일본 개발자). ★21,404 / MIT / 2026-11-17 (활발) — [GitHub](https://github.com/w-okada/voice-changer)
- **Plachtaa/seed-vc**: 제로샷 음성 변환과 노래 음성 변환, 실시간 지원. ★3,906 / GPL-3.0 / 2025-04-20 (정체 직전) — [GitHub](https://github.com/Plachtaa/seed-vc)

**TTS**
- **GPT-SoVITS**: 1분 음성으로 퓨샷 클론이 가능하다. 학습 언어와 다른 언어로 추론하는 교차언어를 지원하며 영어, 일본어, 한국어, 광둥어, 중국어를 다룬다. ★65,270 / MIT / 2026-11-11 (활발) — [GitHub README](https://github.com/RVC-Boss/GPT-SoVITS)
- **Style-Bert-VITS2**: 스타일 제어가 가능한 Bert-VITS2 파생 모델. 2024-02-03 ver 2.0(JP-Extra) 공개. ★1,412 / AGPL-3.0(일부 모듈 LGPL v3 언급) / 2025-12-07 — [GitHub](https://github.com/litagin02/Style-Bert-VITS2)
- **AivisSpeech** (일본어 TTS 앱 ★487, 엔진 ★185): 둘 다 LGPL / 2026-07~10 (활발) — [GitHub](https://github.com/Aivis-Project/AivisSpeech), [Engine](https://github.com/Aivis-Project/AivisSpeech-Engine)
- **VOICEVOX** (에디터 ★3,295 / 엔진 ★1,778 / 코어 ★1,151, 모두 2026-11 활발): 에디터와 엔진은 "LGPL v3 + 소스 공개가 필요 없는 별도 라이선스"의 듀얼 라이선스이고, 코어는 MIT다 — [voicevox](https://github.com/VOICEVOX/voicevox), [voicevox_engine](https://github.com/VOICEVOX/voicevox_engine), [voicevox_core](https://github.com/VOICEVOX/voicevox_core)
- VOICEVOX 이용 시 VOICEVOX를 사용했음을 알 수 있는 크레딧 표기가 필요하다 — [VOICEVOX 이용규약](https://voicevox.hiroshiba.jp/term/)
- **Fish-Speech** ★33,768 / 2026-11-14 (활발): "Fish Audio Community License"로, 연구·비상업 이용은 무료이고 상업 이용은 연매출 기준선 미만 사업자에게만 제한적으로 허용된다 — [GitHub LICENSE](https://github.com/fishaudio/fish-speech/blob/main/LICENSE)
- **CosyVoice**: 다국어 음성 생성 모델로, 저장소가 FunAudioLLM에서 QwenAudio/CosyVoice로 리다이렉트된다. ★24,434 / Apache-2.0 / 2026-05-25 (둔화) — [GitHub](https://github.com/QwenAudio/CosyVoice)
- **IndexTTS** (bilibili): ★25,169 / 2026-09-29. "bilibili Model Use License"가 적용된다. 월간 활성 사용자 1억 명 초과 시 별도 조건이 붙고, 다른 AI 모델 개선에 사용할 수 없다 — [GitHub LICENSE](https://github.com/index-tts/index-tts/blob/main/LICENSE)
- **Irodori-TTS** (Aratako): 일본어 전용 Flow Matching TTS. 이모지로 스타일을 제어한다. 코드 ★1,536 / MIT / 2026-11-04 (활발) — [GitHub](https://github.com/Aratako/Irodori-TTS). 모델은 HF에 v2, v3, v4-Small 등으로 배포된다 — [HF v4-Small](https://huggingface.co/Aratako/Irodori-TTS-v4-Small), [HF 500M-v3](https://huggingface.co/Aratako/Irodori-TTS-500M-v3)
- **F5-TTS**: ★15,616 / MIT(코드) / 2026-11-03 — [GitHub](https://github.com/SWivid/F5-TTS)
- **MeloTTS** (MyShell): 다국어(영·스·프·중·일 등). ★7,722 / MIT / 2024-12-24 (정체) — [GitHub](https://github.com/myshell-ai/MeloTTS)
- **Kokoro-82M**: ★10,211 / Apache-2.0 / 2025-08-06 — [GitHub](https://github.com/hexgrad/kokoro)
- **ChatTTS**: ★40,020 / AGPL-3.0 / 2026-04-10 — [GitHub](https://github.com/2noise/ChatTTS)
- COEIROINK 공식 사이트(coeiroink.com)는 응답한다(HTTP 200). GitHub 오픈소스 저장소는 확인하지 못했다 — [COEIROINK](https://coeiroink.com/)

### Inferences
- 클립 내레이션(해설, 번역 더빙)용 기본 후보는 다음과 같다. 일본어는 VOICEVOX 엔진(HTTP API, 크레딧 자동 삽입 필요) 또는 AivisSpeech Engine(VOICEVOX 호환 계열 앱으로 보이나 미검증)이고, 다국어와 한국어는 GPT-SoVITS 또는 CosyVoice다. 셋 다 로컬 HTTP 서버 형태로 붙이기 쉽다.
- AGPL 프로젝트(Style-Bert-VITS2, so-vits-svc, ChatTTS)를 서버 기능으로 내장하면 소스 공개 의무가 생길 수 있다. 별도 프로세스나 외부 서비스로 분리하는 편이 안전하다.
- RVC나 so-vits-svc로 VTuber 본인 목소리를 흉내 내는 기능은 넣지 않아야 한다. 저작권과 퍼블리시티권 문제가 있고, hololive 음악 가이드라인도 탤런트 음성으로 음성을 생성하는 것을 거부한다(섹션 7).

### Gaps
- Irodori-TTS v4-Large의 라이선스가 Gemma 약관이라는 정보는 2차 블로그 요약에서만 확인됐다. HF 모델 카드에서 직접 확인이 필요하다.
- COEIROINK와 AivisSpeech의 캐릭터별 음성 이용약관(상업 이용, 크레딧)은 확인하지 않았다.
- MeloTTS의 한국어 지원은 README 전문으로 확인하지 못했다(설명 문구가 잘림).

## 4. 번역·자막 커뮤니티와 도구 (라이브 번역, 클립용 자동 번역 자막, Whisper 기반 JP→EN/KR, 고유명사 용어집)

### Takeaway
라이브 번역 커뮤니티 도구는 LiveTL과 HyperChat(AGPL, 활발)이 표준이다. 클립 자막 파이프라인으로는 VideoLingo(Apache-2.0, 용어집 기능 내장)가 stream2clip에 가장 가깝다. 기반 ASR은 faster-whisper나 whisperX(단어 단위 타임스탬프)가 사실상 표준이다. 일본어 특화로는 kotoba-whisper와 ReazonSpeech가 있다.

### Cited Findings
- **LiveTL**: "스트림 번역 필터" 브라우저 확장. HyperChat과 YtcFilter를 함께 만든다. ★620 / AGPL-3.0 / 2026-11-17 (활발). Firefox 호환 때문에 MV2와 MV3를 병행 유지한다 — [GitHub](https://github.com/LiveTL/LiveTL), [livetl.app](https://livetl.app/)
- **HyperChat**: CPU/RAM을 최적화한 YouTube 채팅 대체 확장. ★329 / AGPL-3.0 / 2026-08-09 — [GitHub](https://github.com/LiveTL/HyperChat)
- **stream-translator** (fortypercnt): Whisper 기반 라이브 스트림 실시간 번역. ★268 / MIT / 2023-03-19 (정체) — [GitHub](https://github.com/fortypercnt/stream-translator)
- **stream-translator-gpt** (포크): VAD 기반 오디오 슬라이싱과 GPT/Gemini 번역을 붙였다. ★218 / MIT / 2026-11-02 (활발) — [GitHub](https://github.com/ionic-bond/stream-translator-gpt)
- **VideoLingo**: "Netflix 수준" 자막 분할, 번역, 정렬, 더빙까지 원클릭으로 처리한다. "Custom + AI-generated terminology"로 용어 일관성을 유지하며 일본어를 지원한다. ★19,300 / Apache-2.0 / 2026-11-13 (활발) — [GitHub](https://github.com/Huanshere/VideoLingo)
- **pyvideotrans**: 영상 번역과 더빙·자막 삽입. ★19,769 / GPL-3.0 / 2026-11-17 (활발) — [GitHub](https://github.com/jianchang512/pyvideotrans)
- **VideoCaptioner (卡卡字幕助手)**: LLM 기반으로 자막 생성, 문장 분할, 교정, 번역을 한다. ★16,566 / GPL-3.0 / 2026-09-12 — [GitHub](https://github.com/WEIFENG2333/VideoCaptioner)
- **N46Whisper**: 노기자카46 자막 제작자용 Colab 노트북(faster-whisper 기반). 자막 그룹 스타일이 들어간 ASS를 출력해 Aegisub로 바로 편집할 수 있고, 2024-04에 Gemini 번역 옵션이 추가됐다. ★1,705 / MIT. README에 "더 이상 유지보수하지 않음" 공지가 있다 (중단) — [GitHub](https://github.com/Ayanaminn/N46Whisper)
- **SakuraLLM**: 라이트노벨·갈게임 특화 일→중 번역 LLM. ★4,850 / GPL-3.0(코드) / 2026-07-23 — [GitHub](https://github.com/SakuraLLM/SakuraLLM)
- **ASR 기반**: openai/whisper ★113,086 / MIT — [GitHub](https://github.com/openai/whisper). faster-whisper ★26,842 / MIT / 2026-11-12 — [GitHub](https://github.com/SYSTRAN/faster-whisper). whisperX(단어 단위 타임스탬프와 화자 분리) ★25,435 / BSD / 2026-11-12 — [GitHub](https://github.com/m-bain/whisperX). stable-ts(강제 정렬) ★2,282 / MIT / 2026-05-30 — [GitHub](https://github.com/jianfch/stable-ts). whisper.cpp ★55,282 / MIT / 2026-11-18 — [GitHub](https://github.com/ggml-org/whisper.cpp)
- **일본어 특화 ASR**: kotoba-whisper ★105 / 라이선스 파일 미확인 / 2024-10-23 — [GitHub](https://github.com/kotoba-tech/kotoba-whisper). ReazonSpeech(대규모 일본어 음성 코퍼스와 모델) ★406 / Apache-2.0 / 2026-06-10 — [GitHub](https://github.com/reazon-research/ReazonSpeech)
- **OBS LocalVocal**: OBS 안에서 로컬 음성 인식과 동시 번역(whisper.cpp, DeepL 옵션)을 한다. GPU나 네트워크가 필요 없다. ★1,675 / GPL-2.0 / 2026-11-05. locaal-ai에서 royshil/obs-localvocal로 리다이렉트된다 — [GitHub](https://github.com/royshil/obs-localvocal)
- 한 CSDN 글은 VTuber 클립용 Whisper 일본어 인식, 화자 분리(선택), 자동 타이밍, SRT/ASS 생성 구성을 소개한다. 업로드 단계는 다루지 않는다 — [CSDN](https://bbs.csdn.net/weixin_29041195/article/details/100250085)

### Inferences
- stream2clip 자막 단계 권장 구성: whisperX 또는 faster-whisper(+kotoba-whisper 가중치)로 단어 단위 타임스탬프를 얻는다 → LLM 번역 시 VTuber 이름, 팬 네임, 밈 용어집을 프롬프트에 주입한다(VideoLingo의 custom terms 방식 참고) → ASS 스타일 템플릿을 적용한다(N46Whisper 방식).
- VTuber 고유명사 용어집의 시드 데이터는 Holodex 채널 메타데이터(영문명과 일본어명)에서 자동 생성할 수 있다.
- LiveTL과 HyperChat은 AGPL이므로 코드 직접 재사용보다는 UX 참고용이 적절하다.

### Gaps
- 요청에 있던 "TLsync"는 검색과 GitHub에서 동명 프로젝트를 확인하지 못했다.
- Holodex의 번역 기능(TLdex)의 현재 상태와 API는 확인하지 않았다.
- 한국어(JP→KR) 특화 VTuber 번역 도구나 커뮤니티 용어집은 찾지 못했다.

## 5. OBS 생태계와 방송 인터랙션 도구 (플러그인, 리플레이 버퍼, 채팅 오버레이, Streamer.bot, VTube Studio 플러그인)

### Takeaway
OBS 쪽에서 stream2clip이 재사용할 핵심은 obs-websocket의 `SaveReplayBuffer`/`ReplayBufferSaved`/`SplitRecordFile` API다. 이를 쓰면 방송 중 "지금 클립" 트리거를 구현할 수 있다. VTuber 방송 인터랙션 도구(T.I.T.S., Karasubonk, Streamer.bot)는 클립 대상 이벤트(아이템 던지기, 리딤)의 발생 신호로 쓸 수 있다.

### Cited Findings
- **OBS Studio** ★79,787 / GPL-2.0 / 2026-11-18 — [GitHub](https://github.com/obsproject/obs-studio)
- **obs-websocket** ★4,393 / GPL-2.0 / 2026-10-08. 프로토콜에 `SaveReplayBuffer`, `GetLastReplayBufferReplay` 요청, `ReplayBufferSaved` 이벤트, `StartRecord`, `SplitRecordFile`이 정의돼 있다 — [protocol.md](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md)
- **obs-spout2-plugin** (VTuber 아바타 앱과 OBS 간 텍스처 공유): ★1,123 / GPL-2.0 / 2026-10-29 — [GitHub](https://github.com/Off-World-Live/obs-spout2-plugin)
- **Move Transition** ★945 / GPL-2.0 / 2026-11-14 — [GitHub](https://github.com/exeldro/obs-move-transition)
- **Advanced Scene Switcher** (OBS 자동화 도구) ★1,611 / GPL-2.0 / 2026-11-11 — [GitHub](https://github.com/WarmUpTill/SceneSwitcher)
- **Source Record** ★688 / GPL-2.0 / 2026-11-13 — [GitHub](https://github.com/exeldro/obs-source-record). **Replay Source** ★178 / GPL-2.0 / 2026-11-02 — [GitHub](https://github.com/exeldro/obs-replay-source). **Shaderfilter** ★823 / GPL-2.0 — [GitHub](https://github.com/exeldro/obs-shaderfilter)
- **StreamFX**: Vhonowslend/StreamFX-Public으로 이전. ★4,190 / GPL-2.0 / 2024-12-13 (정체) — [GitHub](https://github.com/Vhonowslend/StreamFX-Public)
- **VTube Studio API**: DenchiSoft/VTubeStudio(API 개발 페이지) ★1,333 / MIT / 2026-11-09 — [GitHub](https://github.com/DenchiSoft/VTubeStudio). Python 클라이언트 pyvts ★133 / MIT / 2025-07-23 — [GitHub](https://github.com/Genteki/pyvts)
- **T.I.T.S. (Twitch Integrated Throwing System)**: 시청자가 모델에 아이템을 던지게 하는 앱. VTube Studio 유무와 상관없이 동작하며 itch.io로 배포된다 — [itch.io](https://remasuri3.itch.io/tits?s=09). Streamer.bot에 T.I.T.S. 서브액션(트리거 활성화, ID나 이름으로 아이템 던지기)이 있고 문서상 WIP다 — [Streamer.bot Docs](https://docs.streamer.bot/api/sub-actions/integrations/tits). Mix It Up도 T.I.T.S. 연동을 제공한다 — [Mix It Up Docs](https://dev.site.mixitupapp.com/docs/integrations/tits)
- **Karasubonk**: VTube Studio용 "bonk" 아이템 던지기 도구. ★28 / MIT / 2026-04-02 — [GitHub](https://github.com/typeou/karasubonk), [itch.io](https://typeou.itch.io/karasubonk/comments)
- **Streamer.bot**: Twitch, YouTube, Kick, OBS 이벤트를 듣고 액션을 실행하는 무료 Windows 앱(포터블) — [streamer.bot](https://streamer.bot/)
- **Firebot** (Twitch 올인원 봇): ★484 / GPL-3.0(README 기준) / 2026-11-09 — [GitHub](https://github.com/crowbartools/Firebot)
- **Kruiz Control**: 채널 포인트, 채팅, OBS를 의사코드로 자동화한다. ★239 / CC 계열 라이선스 / 2026-07-12 — [GitHub](https://github.com/Kruiser8/Kruiz-Control)
- **채팅 오버레이**: jChat(Twitch) ★182 / GPL-3.0 / 2024-03-10 (정체) — [GitHub](https://github.com/giambaJ/jChat). ChatIS v3 ★65 / 2024-10-31 (WIP, 정체) — [GitHub](https://github.com/IS2511/ChatIS). blivechat(빌리빌리 댓글을 YouTube 스타일 OBS 오버레이로) ★2,762 / MIT / 2026-08-19 — [GitHub](https://github.com/xfgryujk/blivechat)

### Inferences
- stream2clip "라이브 모드" 설계안: obs-websocket에 연결해 채팅 급증이나 Streamer.bot 이벤트(T.I.T.S. 던지기, 리딤, 슈퍼챗)가 발생하면 `SaveReplayBuffer`를 호출하고, `ReplayBufferSaved` 이벤트로 파일 경로를 받아 후처리 큐에 넣는다. 이렇게 하면 VOD를 다운로드하지 않고도 크리에이터 본인용 클립 툴을 만들 수 있다.
- Streamer.bot은 무료지만 소스가 공개된 저장소를 찾지 못했다. 의존성으로 삼기보다는 WebSocket/HTTP 트리거 수신만 지원하는 것이 바람직하다.
- OBS 플러그인은 대부분 GPL-2.0이므로 stream2clip 본체와는 프로세스 경계(obs-websocket)로 분리하는 것이 라이선스상 깔끔하다.

### Gaps
- Streamer.bot 라이선스(소스 비공개 여부)를 공식 문서로 확인하지 못했다. "무료, Patreon 후원"만 확인했다.
- StreamElements 등 상용 오버레이 서비스의 API 조건은 조사하지 않았다.
- Source Record와 Replay Source의 세부 기능은 README 본문으로 확인하지 않았다(설명 필드가 비어 있음).

## 6. 팬/커뮤니티 툴링 (곡 DB, 노래방송 세트리스트, 타임스탬프 봇, 클립 집계, 아카이빙)

### Takeaway
VTuber 커뮤니티에는 크라우드소싱 타임스탬프(디스코드 tagger 채널, Holodex 타임스탬프 댓글), 곡 DB(Musicdex), 채팅 기반 자동 클립 사이트(HoloAutoClip)가 이미 있다. 또 HoloArchivists 계열 아카이빙 도구(ytarchive, chat-downloader)가 사실상의 인프라 역할을 한다. 이 중 채팅 로그 수집과 타임스탬프 데이터가 stream2clip에 가장 유용하다.

### Cited Findings
- **Musicdex** (Holodex 팀): "Spotify for VTubers". ★112 / Apache-2.0 / 2025-04-29 (둔화) — [GitHub](https://github.com/HolodexNet/Musicdex)
- **HoloAutoClip / VTAutoClip** (mipacd/auto-clip): 채팅 로그를 30초 단위로 묶어 "lol", "kusa"(草) 등의 급증을 분석해 자동 클립 목록을 만든다. 최대 그룹 30초 전부터 시작하도록 클립을 잡고, 주 1회 갱신하며, 원시 데이터를 CSV로 공개한다. ★6 / 라이선스 미확인 / 2025-04-01 — [GitHub](https://github.com/mipacd/auto-clip), [사이트](https://mipacd.github.io/auto-clip/holo.html)
- **KoroTagger**: 다른 봇 프로젝트 README에서 `!stream {link}`와 `!tags {link}`로 설정하는 디스코드 태깅 봇으로 언급된다 — [tdyskinesia/Kari](https://github.com/tdyskinesia/Kari). r/Hololive에서는 디스코드 tagger 채널이 커뮤니티 타임스탬프의 집결지로 언급된다 — [r/Hololive (redlib 미러로 확인)](https://www.reddit.com/r/Hololive/comments/127ftc6/)
- **Tsnip**: YouTube 라이브에서 시청자가 `!ts`로 순간을 표시하면 방송 후 타임스탬프를 댓글이나 디스코드로 게시하는 봇. ★10 / MIT / 2026-11-02 — [GitHub](https://github.com/jaypatel208/tsnip)
- **Go-Simp**: VTuber 신규 영상, 팬아트, 라이브 알림 디스코드 봇. ★70 / GPL-3.0 / 2023-01-26 (정체) — [GitHub](https://github.com/JustHumanz/Go-Simp)
- **SponsorBlock**: 크라우드소싱 영상 구간 DB(브라우저 확장). ★14,103 / GPL-3.0 / 2026-11-07 — [GitHub](https://github.com/ajayyy/SponsorBlock)
- **아카이빙 인프라**: ytarchive(YouTube 라이브 다운로더, VTuber 아카이버 사이에서 널리 쓰임) ★1,701 / MIT / 2025-12-19 — [GitHub](https://github.com/Kethsar/ytarchive). hoshinova(ytarchive 매니저, HoloArchivists) ★154 / MIT / 2024-04-19 (정체) — [GitHub](https://github.com/HoloArchivists/hoshinova). chat-downloader(라이브·아카이브·클립 채팅 수집, 인증 불필요) ★1,199 / MIT / 2025-11-05 — [GitHub](https://github.com/xenova/chat-downloader). TwitchDownloader(VOD와 클립 다운로드, 채팅 다운로드·렌더) ★4,074 / MIT / 2026-11-15 — [GitHub](https://github.com/lay295/TwitchDownloader). yt-dlp ★208,737 / Unlicense / 2026-11-17 — [GitHub](https://github.com/yt-dlp/yt-dlp). streamlink ★11,947 / BSD / 2026-11-14 — [GitHub](https://github.com/streamlink/streamlink)
- **빌리빌리 탄막**: DanmakuFactory(XML 탄막을 ASS로 변환) ★879 / MIT / 2026-07-27 — [GitHub](https://github.com/hihkm/DanmakuFactory)

### Inferences
- HoloAutoClip의 "30초 버킷 + 웃음 키워드(kusa, lol, w, 草) + 피크 30초 전 시작" 휴리스틱은 stream2clip MVP의 하이라이트 베이스라인으로 바로 복제할 수 있다. 정교한 알고리즘은 키리누키 담당 조사 참조.
- 수집 계층은 yt-dlp(VOD) + chat-downloader(YouTube 채팅) + TwitchDownloader CLI(Twitch 채팅) + streamlink(chzzk/soop) 조합이 가장 넓은 커버리지를 준다.
- 노래방송(歌枠)은 곡 저작권 때문에 클립하기에 위험도가 높다. Holodex/Musicdex의 곡 구간 데이터는 반대로 "제외 구간"을 정하는 데 활용할 수 있다.

### Gaps
- KoroTagger의 공식 저장소, 운영 상태, 데이터 공개 여부를 확인하지 못했다.
- 노래방송 세트리스트 전용 DB(일본 팬 운영 사이트 등)는 별도로 조사하지 못했다.
- 팬 위키(hololive fandom, 일본 wikiwiki 등)의 데이터 이용 조건은 확인하지 않았다.

## 7. 저작권·권리 툴링 (업로드 전 음악 탐지, 오디오 핑거프린팅, BGM 분리, 기획사 2차 창작 가이드라인)

### Takeaway
기술적으로는 inaSpeechSegmenter로 음악 구간을 탐지하고, Chromaprint/Olaf/ShazamIO로 곡을 식별하고, python-audio-separator로 BGM을 분리하는 3단 구성이 가능하다. 다만 AcoustID 웹서비스는 비상업 전용이고 ShazamIO는 리버스 엔지니어링된 비공식 API다. 정책 측면에서는 hololive(2026-08-31 개정)와 にじさんじ(2025-05-23 개정)가 모두 클립 채널 등록을 요구한다. 원본 URL 표기도 필수다. hololive는 Content ID 등록을 금지하고, 원본 아카이브가 공개되기 전 게시도 금지한다.

### Cited Findings
**음악 탐지 / 핑거프린팅 / 분리**
- **Chromaprint** (AcoustID용 핑거프린트 C 라이브러리): ★1,424 / MIT / 2026-10-15 — [GitHub](https://github.com/acoustid/chromaprint). AcoustID 웹서비스는 "비상업 이용만 무료"이고 상업 이용은 별도 문의가 필요하다 — [AcoustID Web Service](https://acoustid.org/webservice)
- **Olaf** (경량 오디오 핑거프린팅): ★424 / AGPL-3.0 / 2026-10-16 — [GitHub](https://github.com/JorenSix/Olaf). **Panako** ★270 / 라이선스 미확인 / 2026-09-17 — [GitHub](https://github.com/JorenSix/Panako)
- **dejavu** (Python 핑거프린팅): ★6,789 / MIT / 2024-04-22 (정체) — [GitHub](https://github.com/worldveil/dejavu). **audfprint** ★619 / MIT / 2019-09-24 (정체) — [GitHub](https://github.com/dpwe/audfprint)
- **ShazamIO**: 리버스 엔지니어링한 Shazam API의 비동기 Python 라이브러리. ★1,017 / MIT / 2026-11-16 — [GitHub](https://github.com/shazamio/ShazamIO). **SongRec**(Linux용 오픈소스 Shazam 클라이언트, Rust) ★2,057 / GPL-3.0 / 2026-11-17 — [GitHub](https://github.com/marin-m/SongRec)
- **inaSpeechSegmenter**: CNN 기반으로 음성, 음악, 잡음, 화자 성별을 구간 탐지한다. ★919 / MIT / 2026-03-12 — [GitHub](https://github.com/ina-foss/inaSpeechSegmenter). **PANNs** (audioset_tagging_cnn) ★1,799 / 2024-07-25 — [GitHub](https://github.com/qiuqiangkong/audioset_tagging_cnn)
- **Demucs**: ★10,415 / MIT. README에 "더 이상 유지보수하지 않음"이 명시돼 있고 adefossez/demucs 포크로 안내한다 (중단) — [GitHub](https://github.com/facebookresearch/demucs). **python-audio-separator**(CLI·패키지 형태 스템 분리) ★1,496 / MIT / 2026-10-29 — [GitHub](https://github.com/nomadkaraoke/python-audio-separator). **Ultimate Vocal Remover GUI** ★27,223 / 2026-10-06 — [GitHub](https://github.com/Anjok07/ultimatevocalremovergui)

**기획사 가이드라인**
- **hololive production (커버)**, 2026-08-31 개정:
  - 가이드라인을 지키고 플랫폼 약관이나 제3자 권리를 침해하지 않는 조건으로 클립의 광고 수익화(YPP 등)를 허용한다.
  - 클립을 Content ID 등 자동 식별 시스템에 등록하는 것은 금지한다.
  - 설명란 맨 위에 원본 URL과 제목을 적어야 한다.
  - 원본 아카이브가 공개되기 전에는 클립을 게시할 수 없다.
  - 멤버십 한정 영상과 유료 영상은 금지다.
  - monday.com 폼으로 채널 등록을 권장한다. 등록 채널은 삭제 요청 전에 연락을 받고, 7일 안에 삭제하지 않으면 회사가 삭제 신청을 할 수 있다.
  - 음악 가이드라인은 탤런트 음성을 추출해 음성을 생성하는 것을 거부한다.
  — [hololive 2차 창작 가이드라인](https://hololivepro.com/terms/)
- **にじさんじ (ANYCOLOR)**, 2025-05-23 개정:
  - 클립을 제작·게시하기 전에 등록 폼에 채널을 등록해야 한다(5조 1항).
  - 원본 URL을 표기해야 한다.
  - 공격적이거나 실제 내용과 동떨어진 썸네일을 금지한다.
  - 오해를 부르는 편집을 금지한다.
  - 멤버십 콘텐츠에는 적용되지 않는다(무단 사용 시 법적 조치).
  - 6조 범위를 넘는 수익화는 사전 승인이 필요하다.
  - AI나 대량 자동 생성에 관한 조항은 없다.
  — [ANYCOLOR Guidelines (EN)](https://www.anycolor.co.jp/guidelines/en/), [GameBusiness.jp 보도](https://www.gamebusiness.jp/article/2025/05/24/24313.html)
- **ぶいすぽっ!**: 사전 등록에 더해 허락제를 채택한 더 엄격한 사례로 보도됐다 — [電撃オンライン](https://dengekionline.com/article/202505/42795) (검색 요약 기준)
- **あおぎり高校 (viviON)**: 2026-02 개정으로 생성형 AI 2차 창작물은 "#AIイラスト" 같은 해시태그나 AI 사용 명시를 붙이면 허용된다. 공식으로 오인될 수 있는 작품과 무편집 재업로드는 금지다 — [インサイド](https://www.inside-games.jp/article/2026/02/17/177489.html)

### Inferences
- stream2clip 업로드 단계에 "가이드라인 컴플라이언스 체크"를 기본 기능으로 넣어야 한다. 구체적으로는 원본 URL과 제목을 설명란 맨 위에 자동 삽입하고, 원본 아카이브 공개 여부를 확인(Holodex `status`나 YouTube API)한 뒤에야 업로드를 허용하고, 멤버십·유료 방송은 차단하고, 소속사별 등록 여부를 확인하는 체크리스트를 둔다.
- 음악 구간 처리 권장 순서: inaSpeechSegmenter로 음악 구간 탐지 → 노래·BGM 구간은 클립 후보에서 제외하거나 경고 → (선택) python-audio-separator로 배경 BGM 감쇠. 상업 서비스라면 AcoustID와 ShazamIO 의존은 피해야 한다.
- AI 생성 요소(TTS 내레이션, AI 요약 썸네일)를 쓰면 AI 사용 명시를 기본값으로 넣는 것이 앞으로의 가이드라인 추세(viviON 사례)와 맞다.

### Gaps
- 한국 VTuber 기획사(스텔라이브 등)의 클립·2차 창작 가이드라인은 검색으로 찾지 못했다. 공식 사이트에서 직접 확인이 필요하다.
- ぶいすぽっ!, 774inc 등 다른 기획사 가이드라인 원문은 직접 확인하지 않았다.
- YouTube Content ID에서 실제로 VTuber 클립이 클레임되는 빈도에 대한 데이터는 찾지 못했다.
- Panako와 UVR GUI의 라이선스 파일은 확인하지 못했다.

## 8. stream2clip과 매우 가까운 엔드투엔드 프로젝트 (VOD 다운로드 → 하이라이트 → 편집 → 자막 → 업로드)

### Takeaway
엔드투엔드에 가장 가까운 오픈소스는 중국 빌리빌리 생태계에 있다. timerring/bilive(Apache-2.0)는 녹화부터 탄막 렌더링, 자막, 탄막 밀도 기반 자동 슬라이스, 멀티모달 LLM 제목 생성, 자동 업로드까지 처리한다. biliup(MIT)은 24시간 녹화, 편집기, LLM 하이라이트 추천(사람 확인 후 슬라이스), 업로드에 Agent skill까지 갖췄다. 일본어와 한국어 권역에서는 이 정도로 통합된 오픈소스를 찾지 못했다.

### Cited Findings
- **timerring/bilive**: "7×24 무인 녹화, 탄막 렌더링, 자막 인식, 자동 슬라이스, 자동 업로드, 저사양 머신 호환". 탄막 밀도로 하이라이트를 자르고, 영상 이해 LLM으로 제목과 커버를 생성한다. 지원 모델은 OpenAI Whisper, GLM-4V-Plus, Gemini, Qwen 등이다. 탄막 XML→ASS 변환은 DanmakuConvert로 분리해 공개했다. README에 학습·교류용이며 상대 허락을 받고 녹화하라는 경고가 있다. ★3,324 / Apache-2.0 / 2026-04-24 (둔화) — [GitHub](https://github.com/timerring/bilive)
- **biliup**:
  - 다수 스트리머를 24시간 녹화하고 XML 탄막을 동기 저장한다.
  - 편집기에서 멀티트랙 편집, 자막, 모자이크, 탄막 오버레이를 지원한다.
  - LLM이 하이라이트를 추천하고 사람이 확인한 뒤 슬라이스한다.
  - CLI와 Agent skill(`npx skills add biliup/biliup`)을 제공한다.
  - 19개 플랫폼을 지원한다(YouTube, Twitch, TwitCasting, niconico, AfreecaTV 포함). 매칭되지 않는 URL은 yt-dlp나 Streamlink 범용 어댑터로 처리한다.
  - ★5,636 / MIT / 2026-11-09 (활발)
  — [GitHub](https://github.com/biliup/biliup)
- **녹화기**: BililiveRecorder(录播姬) ★4,901 / GPL-3.0 / 2026-10-12 — [GitHub](https://github.com/BililiveRecorder/BililiveRecorder). bililive-go ★5,843 / GPL-3.0 / 2026-11-09 — [GitHub](https://github.com/bililive-go/bililive-go)
- **FunClip** (ModelScope): FunASR 기반 전사, 자막 생성, LLM 보조 클리핑(로컬 Gradio UI). ★6,571 / MIT / 2026-11-01 — [GitHub](https://github.com/modelscope/FunClip)
- **AutoCut**: 텍스트 에디터에서 자막을 지우는 방식으로 영상을 편집한다. ★7,845 / Apache-2.0 / 2024-10-05 (정체) — [GitHub](https://github.com/mli/autocut)
- **HoloAutoClip**: 채팅 분석 자동 클립 "사이트"(편집·업로드는 없음) — [GitHub](https://github.com/mipacd/auto-clip)
- **한국 CHZZK 녹화**:
  - d2n0s4ur/chzzk-downloader: Python + ffmpeg로 라이브 m3u8, 썸네일, 채팅 CSV를 저장한다. ★4 / MIT / 2024-05-08 (정체) — [GitHub](https://github.com/d2n0s4ur/chzzk-downloader)
  - billy0402/chzzk-obs-recorder: CHZZK 방송 시작·종료에 맞춰 OBS 녹화를 켜고 끈다. ★1 / 2024-04-17 — [GitHub](https://github.com/billy0402/chzzk-obs-recorder)
  - kpg-anon/streamloop: CHZZK 지원은 "계획" 단계다 — [GitHub](https://github.com/kpg-anon/streamloop)
- 일본어 검색("VTuber 切り抜き 自動化 GitHub 文字起こし 字幕 アップロード")에서는 클립, 전사, 업로드를 하나로 자동화한 저장소를 찾지 못했다. 부분 사례(CSDN의 Whisper 자막 글, 유료 note 글, HoloAutoClip)만 확인됐다 — [CSDN](https://bbs.csdn.net/weixin_29041195/article/details/100250085), [aipicks.jp VTuber 영상 편집](https://aipicks.jp/industries/vtuber/video-edit)

### Inferences
- bilive와 biliup은 stream2clip의 아키텍처 레퍼런스로 가장 가치가 높다. 특히 녹화와 처리를 파이프라인으로 겹쳐 돌리는 구조, 탄막(채팅) 밀도 기반 슬라이스, LLM 제목 생성, 사람 확인 단계(human-in-the-loop)가 참고할 만하다. biliup은 MIT라 코드 재사용도 가능하다(bilive는 Apache-2.0).
- 두 프로젝트 모두 업로드 대상이 빌리빌리 중심이다. YouTube Shorts, TikTok 업로드와 hololive·にじさんじ 가이드라인 준수 로직을 붙이는 것이 stream2clip의 차별점이 될 수 있다.
- 한국어권(CHZZK/SOOP)은 녹화 스크립트 수준의 소규모 프로젝트뿐이라, "CHZZK/SOOP + 한국어 자막 + 쇼츠" 엔드투엔드는 사실상 비어 있는 영역이다. 2026-11-20 추가 조사에서도 이 판단은 그대로다. 녹화기, 후보 구간 표시 도구, 노래 구간 도구는 늘었지만 렌더링까지 잇는 도구는 없었다(`07_chzzk_soop.md` 참고).

### Gaps
- 상용 서비스(OpusClip, Eklipse, Vizard 등)는 쇼츠·하이라이트 담당 조사자 범위로 보고 조사하지 않았다.
- biliup의 LLM 하이라이트 추천에 쓰는 프롬프트와 신호(탄막만인지 ASR도 쓰는지)는 README 수준에서만 확인했다.
- 일본 Zenn/Qiita의 개인 "切り抜き自動化" 프로젝트는 검색에 나오지 않았다. 키워드를 바꿔 추가 조사할 여지가 있다.

## 9. stream2clip에 가장 재사용 가치가 높은 항목 요약

### Takeaway
재사용 가치가 높은 상위 10개는 다음과 같다. ① Holodex API ② yt-dlp, streamlink(chzzk/soop 플러그인), chat-downloader, TwitchDownloader ③ biliup·bilive 아키텍처 ④ HoloAutoClip 채팅 휴리스틱 ⑤ faster-whisper/whisperX + kotoba-whisper ⑥ VideoLingo의 용어집 번역 방식 ⑦ obs-websocket 리플레이 버퍼 API ⑧ inaSpeechSegmenter 음악 구간 탐지 ⑨ VOICEVOX/GPT-SoVITS 내레이션 ⑩ hololive·にじさんじ 가이드라인 기반 업로드 체크리스트.

### Cited Findings
- 메타데이터, 클립 목록, 타임스탬프 댓글, 곡 정보: Holodex v2 API — [Holodex API Docs](https://docs.holodex.net/)
- 수집: yt-dlp(Unlicense) — [GitHub](https://github.com/yt-dlp/yt-dlp). streamlink(BSD, chzzk·soop 플러그인 포함) — [GitHub](https://github.com/streamlink/streamlink/tree/master/src/streamlink/plugins). chat-downloader(MIT) — [GitHub](https://github.com/xenova/chat-downloader). TwitchDownloader(MIT) — [GitHub](https://github.com/lay295/TwitchDownloader)
- 파이프라인 레퍼런스: biliup(MIT) — [GitHub](https://github.com/biliup/biliup). bilive(Apache-2.0) — [GitHub](https://github.com/timerring/bilive)
- 하이라이트 베이스라인: HoloAutoClip의 30초 버킷 웃음 키워드 휴리스틱 — [GitHub](https://github.com/mipacd/auto-clip)
- 자막과 번역: whisperX(BSD) — [GitHub](https://github.com/m-bain/whisperX). faster-whisper(MIT) — [GitHub](https://github.com/SYSTRAN/faster-whisper). VideoLingo(Apache-2.0, 커스텀 용어집) — [GitHub](https://github.com/Huanshere/VideoLingo)
- 라이브 트리거: obs-websocket `SaveReplayBuffer`/`ReplayBufferSaved` — [protocol.md](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md)
- 권리 필터: inaSpeechSegmenter(MIT) — [GitHub](https://github.com/ina-foss/inaSpeechSegmenter). hololive 가이드라인 — [hololivepro.com/terms](https://hololivepro.com/terms/). ANYCOLOR 가이드라인 — [anycolor.co.jp](https://www.anycolor.co.jp/guidelines/en/)
- 내레이션: VOICEVOX(크레딧 필수) — [이용규약](https://voicevox.hiroshiba.jp/term/). GPT-SoVITS(MIT, JA/KO) — [GitHub](https://github.com/RVC-Boss/GPT-SoVITS)

### Inferences
- 라이선스 관점에서는 MIT, Apache-2.0, BSD, Unlicense 컴포넌트(yt-dlp, streamlink, chat-downloader, faster-whisper, whisperX, VideoLingo, biliup, inaSpeechSegmenter, GPT-SoVITS, VOICEVOX core)로 본체를 구성하는 것이 좋다. GPL/AGPL 도구(OBS 플러그인, LiveTL, Style-Bert-VITS2, pyvideotrans, VideoCaptioner, Olaf)는 외부 프로세스나 선택 플러그인으로 분리하는 것이 안전하다.
- 제품 차별화 포인트는 세 가지다. (a) 한국 플랫폼(CHZZK/SOOP) 지원, (b) 기획사 가이드라인 자동 준수, (c) JP→KR 용어집 기반 자막. 이 셋은 기존 오픈소스에서 비어 있는 영역이다.

### Gaps
- 각 컴포넌트를 조합했을 때의 실제 품질(일본어 VTuber 발화에 대한 WER 등)은 이번 조사 범위에서 측정하지 않았다.
- GitHub "archived" 플래그는 API 차단으로 직접 확인하지 못했다. 상태 판단은 마지막 push 날짜와 README 공지에 근거한다.
