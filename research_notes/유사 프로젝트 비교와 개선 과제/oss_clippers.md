# 오픈소스 자동 클리핑·쇼츠 생성 프로젝트 비교 (2026-11-22 기준)

조사 방법: GitHub REST API(`gh api`)로 저장소 검색(topic `shorts-generator`, `video-clipping`, `highlight-detection`, `opusclip-alternative`, "直播 切片 自动", "vtuber clip", "切り抜き 自動", "chzzk clip" 등 15개 이상 쿼리)과 저장소 메타데이터·최신 릴리스·댓글 많은 이슈를 2026-11-22에 직접 조회했다. 기능 설명은 각 저장소 README 원문에서 가져왔다(README는 개발자 자기 서술이라 실제 동작은 검증하지 않음). ★·날짜는 모두 2026-11-22 조회값이다. 이전 조사(`reports/버튜버 영상 작업 프로젝트 레퍼런스.md` §1·§6, `reports/키리누키 영상 레퍼런스 검토.md` §7, `research_notes/버튜버 영상 작업 프로젝트 레퍼런스/01_shorts.md`, 기준일 2026-11-18)에 이미 있는 내용은 바뀐 점만 적었다.

## 1. 2025~2026년에 가장 활발하거나 인기 있는 오픈소스 클리퍼는 무엇이고, 2026년 신규는 무엇인가

### Takeaway
규모로는 zhouxiaoka/autoclip(13.1k★), mutonby/openshorts(9.7k★, 이전 조사 때 접속이 안 되던 저장소로 지금은 MIT로 공개됨), AI-Youtube-Shorts-Generator(6.4k★), FunClip(6.6k★), auto-editor(6.0k★), biliup(5.7k★), supoclip(4.0k★)이 상위권이다. 2026년 하반기에는 **스트리머용 로컬 클리퍼**가 쏟아졌다(NeonClipping, AutoShorts(JayWebtech), SharkyClips, StreamClipper, ClipMint, reelsaw 등). 대부분 생긴 지 몇 주에서 몇 달밖에 안 됐고, ★ 수가 비정상적으로 빨리 늘어난 곳도 있다. VTuber 아바타를 인식하는 클리퍼는 이번에도 찾지 못했다.

### Cited Findings
**주요 저장소 현황 (GitHub API, 2026-11-22)**

| 저장소 | ★ | 마지막 push | 최신 릴리스 | 생성 | 라이선스 | 성격 |
|---|---|---|---|---|---|---|
| [zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip) | 13,064 (fork 2,093) | 2026-11-22 | v1.5.8 (2026-11-02) | 2025-07 | MIT | 데스크톱/Docker 웹/CLI/MCP, 중국 플랫폼+TikTok/Shorts |
| [mutonby/openshorts](https://github.com/mutonby/openshorts) | 9,664 (fork 2,032) | 2026-11-22 | 없음 | 2025-12-19 | MIT (`cloud/`만 상용 라이선스) | Docker 셀프호스트+유료 클라우드 |
| [modelscope/FunClip](https://github.com/modelscope/FunClip) | 6,620 | 2026-11-01 | v2.2.1 (2026-09-01) | 2023-05 | MIT | FunASR 기반 텍스트/화자 클리핑 |
| [Anil-matcha/AI-Youtube-Shorts-Generator](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator) | 6,448 | 2026-11-21 | 없음 | 2024-06 | MIT | 기본 모드는 유료 MuAPI, `--mode local` 별도 |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | 6,047 | 2026-11-22 | 31.9.0 (2026-11-13) | 2020-04 | Unlicense | 무음 컷 "first pass"(현재 Nim 구현) |
| [biliup/biliup](https://github.com/biliup/biliup) | 5,653 | 2026-11-09 | v1.3.5 (2026-11-06) | 2018-01 | MIT | 24×7 녹화+탄막+편집대(Rust), open issue 288 |
| [FujiwaraChoki/supoclip](https://github.com/FujiwaraChoki/supoclip) | 4,020 | 2026-11-22 | 없음 | 2025-07 | ⚠ SupoClip Noncommercial Source License v1.1 | Docker+MCP+SaaS, open issue 135 |
| [timerring/bilive](https://github.com/timerring/bilive) | 3,328 | 2026-04-24 | v0.3.1 (2025-04-27) | 2024-07 | Apache-2.0 | 둔화 |
| [Geniusay/ChopperBot](https://github.com/Geniusay/ChopperBot) | 2,862 | 2025-08-04 | 없음 | 2023-04 | Apache-2.0 | ☠ 정체 (Java, 플러그인 핫스왑) |
| [iamajmeena/neonclipping](https://github.com/iamajmeena/neonclipping) | 1,864 | 2026-11-21 | v1.1.0 (2026-11-21) | **2026-11-19** | MIT | **신규**. 스트림용 오디오 우선 로컬 클리퍼 |
| [JayWebtech/autoshorts](https://github.com/JayWebtech/autoshorts) | 1,596 | 2026-11-20 | v0.1.7 (2026-11-19) | 2026-06-22 | ⚠ 라이선스 없음 | **신규**. Tauri 2+Rust+SQLite 데스크톱 |
| [jipraks/yt-short-clipper](https://github.com/jipraks/yt-short-clipper) | 1,105 | 2026-09-20 | v2.0.7-beta | 2026-01 | MIT | (기존 조사에 있음) |
| [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio) (Clips Kitty) | 585 (11-18엔 318) | 2026-11-22 | v2.1.0 (2026-10-21) | 2026-06 | ⚠ AGPL-3.0 (SDK만 MIT) | 스트림·게임·스포츠, 플러그인 SDK |
| [RafaelGodoyEbert/ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter) | 518 | 2026-09-10 | 없음 | 2024-09 | ⚠ GPL-3.0 | 포르투갈어권. 웹 UI, 로컬 GGUF |
| [NaufalRizqullah/opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping) | 505 (11-18엔 321) | 2026-11-22 | 없음 | 2026-04 | MIT | B-roll, Facebook Reels 업로드 |
| [xixihhhh/hotclip](https://github.com/xixihhhh/hotclip) | 503 | 2026-11-20 | v0.35.2 (2026-11-20) | 2026-07 | ⚠ AGPL-3.0 | 중국 라이브 切片(直播切片), 탄막·SC 가중 |
| [mutonby/shortcast](https://github.com/mutonby/shortcast) | 402 | 2026-06-04 | v1.0.0 | 2026-05 | Apache-2.0 | macOS 네이티브(Swift) |
| [line/lighthouse](https://github.com/line/lighthouse) | 275 | 2026-11-01 | v1.2 (2025-11-20) | 2024-07 | Apache-2.0 | 연구용 moment retrieval / highlight detection 라이브러리 |
| [divyaprakash0426/autoshorts](https://github.com/divyaprakash0426/autoshorts) | 210 | 2026-11-05 | — | 2026-01 | Apache-2.0 | 게임 플레이 영상용. GPU 가속 |
| [openclaw-easy/ViralMint](https://github.com/openclaw-easy/ViralMint) | 212 | 2026-11-19 | v1.4.0 | 2026-05 | ⚠ AGPL-3.0 | 트렌드 탐색+클리핑+스크립트 영상 |
| [zenstory-ai/video-recap-skills](https://github.com/zenstory-ai/video-recap-skills) | 649 | 2026-11-22 | v0.8.0 | 2026-05 | MIT | 해설 영상 Agent 스킬, 剪映/CapCut 초안 export |
| [Shaitrish/37studio](https://github.com/Shaitrish/37studio) | 168 | 2026-11-14 | v0.15.0 | 2026-10 | MIT | Claude Code 편집 에이전트, 9개 플랫폼 게시 |
| [nmbrthirteen/podcli](https://github.com/nmbrthirteen/podcli) | 94 | 2026-11-19 | v2.9.0 | 2026-02 | ⚠ AGPL-3.0 | 팟캐스트, MCP 도구 32개 |
| [JeremySNR/cutawan](https://github.com/JeremySNR/cutawan) | 91 | 2026-10-13 | v0.14.0 | 2026-07 | MIT | 데스크톱 설치본(exe/dmg/AppImage) |
| [CipherNoct/douyin-living](https://github.com/CipherNoct/douyin-living) | 67 | 2026-11-13 | 없음 | 2026-06 | MIT | 抖音 라이브 녹화+다중 신호 융합+평가 도구 |
| [kleZ799/clipmint](https://github.com/kleZ799/clipmint) | 65 | 2026-11-21 | v1.31.6 | 2026-08 | MIT | 게임 스트림·팟캐스트, 게시 후 성과 학습 |
| [alokbaraii/streamclipper](https://github.com/alokbaraii/streamclipper) | 38 | 2026-11-18 | 없음 | **2026-11-17** | ⚠ AGPL-3.0 | 라이브 클리핑(약 35초 지연) |
| [arcticloud/ai-stream-clipper](https://github.com/arcticloud/ai-stream-clipper) | 31 | 2026-11-19 | 없음 | 2026-11-17 | MIT | Claude Code 스킬(유료 "full version" 언급) |
| [osbytes/reelsaw](https://github.com/osbytes/reelsaw) | 26 | 2026-11-22 | v0.47.1 (2026-11-21) | 2026-10 | ⚠ AGPL-3.0 | TypeScript, 큐 5단계, pairwise LLM 랭킹 |
| [utkualsir/sharkyclips](https://github.com/utkualsir/sharkyclips) | 25 | 2026-11-21 | v1.2.64 (2026-11-21) | 2026-10 | MIT | 스트리머용. 게임 HUD OCR, 욕설 bleep, 3개 플랫폼 게시 |
| [ClipsAI/clipsai](https://github.com/ClipsAI/clipsai) | 618 | 2024-01-17 | 없음 | 2023-12 | MIT | ☠ 정체. 이슈 #17 "Is this project abandoned?"(2026-03-26, 미답) |

- 2026년 신규 스트리머용 클리퍼는 이 밖에도 더 있다. [AlexanderPatsukov/NekoClipper](https://github.com/AlexanderPatsukov/NekoClipper)(AGPL, 2026-11-16 생성, 0★), [lxgicstudios/lxgic-clipper](https://github.com/lxgicstudios/lxgic-clipper)(MIT, 13★), [jekku0966/HighlightMiner](https://github.com/jekku0966/HighlightMiner)(MIT, 0★, 오디오+Whisper+선택적 채팅 신호), [Edualnog/medusa-clip](https://github.com/Edualnog/medusa-clip)(AGPL, 25★, 게임 플레이), [V413havai/GTAClipper](https://github.com/V413havai/GTAClipper)(AGPL). 출처는 모두 GitHub 검색 결과(2026-11-22).
- 브라우저만으로 도는 클리퍼: [imgly/videoclipper](https://github.com/imgly/videoclipper)(46★, 라이선스 없음, 2026-02-10 이후 push 없음, HN Show HN "Vibe-coded AI video clipper that runs in the browser" 4점) — [HN Algolia](https://hn.algolia.com/api/v1/search?query=clips%20shorts%20open%20source&tags=story&numericFilters=created_at_i%3E1767225600)
- 텍스트→영상 생성기는 ★가 압도적이지만 롱폼→숏폼 클리퍼가 아니다: [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) 145,020★(MIT, v1.3.10 2026-11-07), [linyqh/NarratoAI](https://github.com/linyqh/NarratoAI) 11,903★, [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) 19,348★(Apache-2.0, v3.2.0 2026-11-13). AI 편집기 [palmier-io/palmier-pro](https://github.com/palmier-io/palmier-pro)는 14,800★(⚠ GPL-3.0, 2026-04 생성)이다. HN Show HN은 191점/41댓글(2026-07-23)이었다 — [HN Algolia](https://hn.algolia.com/api/v1/search?query=clips%20shorts%20open%20source&tags=story&numericFilters=created_at_i%3E1767225600)
- 중국 라이브 切片(直播切片) 생태계: [AsaChiri/DDRecorder](https://github.com/AsaChiri/DDRecorder)(Apache, 457★, 마지막 릴리스 2022-07)는 정체. 신규로는 [MelanLee-shadow/bilibili-vtuber-clip](https://github.com/MelanLee-shadow/bilibili-vtuber-clip)(Apache-2.0, 3★, "Unattended, fail-closed VTuber stream clipping pipeline for Bilibili", 2026-11-21 push), [ngrict/Auto-Song-Cutter](https://github.com/ngrict/Auto-Song-Cutter)(inaSpeechSegmenter 기반 歌回 자동 컷, 라이선스 없음), [Yuiffy/danmaku-to-summary-ts](https://github.com/Yuiffy/danmaku-to-summary-ts)(B站 라이브 자동 요약·切片, 라이선스 없음)가 있다.
- 일본어·한국어권 키리누키 자동화는 여전히 소규모다. [morip1119-lab/auto-youtube-kirinuki](https://github.com/morip1119-lab/auto-youtube-kirinuki)(0★, WebUI+CLI, 라이선스 없음), [ThankyouJerry/ClipRadar](https://github.com/ThankyouJerry/ClipRadar)(MIT, 1★, CHZZK VOD 채팅 신호), [Choonholic/ChzzkDownloader](https://github.com/Choonholic/ChzzkDownloader)(35★, 라이선스 없음, CHZZK 라이브·VOD·클립 다운로드)가 있다.
- Clips Kitty는 플러그인 생태계가 생기기 시작했다. 서드파티 [ColinGPT9/Grand-Theft-Auto-6-Clips-Kitty-Plugin](https://github.com/ColinGPT9/Grand-Theft-Auto-6-Clips-Kitty-Plugin)(MIT, 45★)은 GTA 하이라이트 검출기다.
- ComfyUI 노드형 클리퍼: [Anil-matcha/ai-clipping-comfyui](https://github.com/Anil-matcha/ai-clipping-comfyui)(MIT, 48★, 2026-07)

**★ 수의 신뢰도**
- NeonClipping은 2026-11-19에 생성돼 3일 만에 1,864★가 됐다. 같은 기간 이슈 대부분이 "STUCK AT FINDING MOMENT IN AUDIO 12%"(#16), "failed to fetch"(#32), "Problem: youtube-bot-check"(#37) 같은 실행 실패 보고다 — [neonclipping issues](https://github.com/iamajmeena/neonclipping/issues)
- autoclip 이슈 #59 "这么多Star是咋刷出来的。数不清的错误。"(★를 어떻게 이렇게 많이 모았나, 오류투성이)에 다른 사용자가 동조했다. 메인테이너는 Docker 경로 버그(#88)가 v1.2.1에서 고쳐졌다고 답했다 — [autoclip #59](https://github.com/zhouxiaoka/autoclip/issues/59)
- 이전 조사(2026-11-18)의 ★ 수와 비교하면 autoclip은 약 10.7k→13,064, Clips Kitty는 318→585, opensource-clipping은 321→505, supoclip은 약 3.5k→4,020이다. 나흘 동안의 증가폭으로는 너무 크다. 이전 수치가 더 오래된 스냅샷이었을 가능성도 있다 — [이전 보고서 §1](../../reports/버튜버%20영상%20작업%20프로젝트%20레퍼런스.md)

### Inferences
- 2026년 신작 README는 같은 문구("Free, open-source Opus Clip alternative", "Paste a link")와 비교표, 대량의 기능 목록을 공유하고, 상당수가 AI로 작성된 문서로 보인다(HN 비판은 §3 참고). ★와 README 분량은 품질을 가늠하는 지표가 못 된다. 릴리스 빈도(SharkyClips v1.2.64, ClipMint v1.31.6, reelsaw v0.47.1)와 테스트 유무(§3)가 더 나은 신호다.
- 스트리머(Twitch/Kick/YouTube Live) 시장은 이제 "facecam 위 + 게임 아래" 레이아웃, 채팅 급증, 라이브 클리핑, 3개 플랫폼 게시가 기본 패키지다. stream2clip이 내세우던 "채팅 + 오디오 + 레이아웃" 조합 자체는 더 이상 차별점이 아니다. 남는 차별점은 VTuber 아바타 인식, JP/KR 반응 어휘, CHZZK/SOOP, 기획사 가이드라인, 시청자 댓글 타임스탬프 평가다.
- 이전 보고서의 "슈퍼챗·멤버십 신호를 하이라이트로 쓰는 OSS가 없다"는 문장은 고쳐야 한다. hotclip이 SC/舰长/礼物/点赞을 상호작용 등급별로 가중하고(§2), douyin-living도 선물·좋아요·입장 이벤트를 수집한다.

### Gaps
- GitHub stargazers 타임스탬프 API(`application/vnd.github.star+json`)가 이번 환경에서 404를 반환해, ★ 증가 곡선으로 조작 여부를 검증하지 못했다.
- HN Show HN "AutoShorts – Local, GPU-accelerated AI video pipeline"(72점/31댓글)이 divyaprakash0426/autoshorts인지는 본문 링크로 확인하지 못했다. 게임 플레이용이라는 설명이 일치해 그럴 가능성이 높다는 정도다.
- Reddit(r/selfhosted, r/NewTubers 등) 스레드는 검색에 걸리지 않았다.

## 2. 이 프로젝트들은 어떤 기능을 제공하고, stream2clip에 없는 것은 무엇인가

### Takeaway
2026년 클리퍼의 공통 기본값은 "OpenAI 호환 엔드포인트(로컬 Ollama 포함)를 쓰는 LLM 판정 + 바이럴 점수 분해 + 단어 단위 애니메이션 자막 + 얼굴/화자 추적 리프레이밍 + 영속 작업 큐 + MCP/REST + 다중 플랫폼 게시"다. stream2clip과 비교해 가장 큰 차이는 네 가지다. (1) 선택적 로컬 LLM·비전 판정이 없다. (2) **사용자 평가와 게시 후 성과를 랭킹에 되먹이는 학습 루프**(NeonClipping, SharkyClips, hotclip, reelsaw, ClipMint, Clips Kitty)가 없다. (3) 대본 기반 편집과 군말 컷이 없다. (4) TikTok/Instagram 게시, MCP 서버, 플러그인 SDK가 없다.

### Cited Findings
**LLM·멀티모달 하이라이트 선택과 점수**
- OpenShorts: Gemini 3.1 Flash-Lite가 전사본과 장면 경계를 보고 15~60초 구간 3~15개를 고르고 각각 virality score를 매긴다. `LLM_BASE_URL`을 Ollama/LM Studio/vLLM로 바꾸면 Google 키 없이 돈다. `LLM_SCORE_BATCH`는 로컬 3, Gemini 8이다 — [openshorts README](https://github.com/mutonby/openshorts)
- reelsaw: map→pool→rank 구조다. 긴 쉼표에서 20% 겹치게 청크를 나눠 "lost in the middle"을 피하고, 청크별로 후보를 병렬 수집해 dedupe한다. rubric(hook/value/flow/shareability)은 k회 샘플의 중앙값으로 매긴다. 상위 10개는 PRP-Sliding-K pairwise 비교(기본 3회, 위치를 바꿔 judge 편향 상쇄)로 정렬한다. 개수를 고정하지 않고 런 상대 기준으로 약한 후보를 버리는데, "pointwise scores do not transfer between judge models"이기 때문이다 — [reelsaw README](https://github.com/osbytes/reelsaw)
- Clips Kitty: 발화, 오디오 흥분도, 시각 활동, 화면 속 반응, hook/payoff 강도를 융합해 0~100점을 매기고, 품질선을 넘은 클립은 상한 없이 모두 남긴다. "make it 5 seconds longer" 같은 AI 편집 채팅이 있다. Creator Profiles는 채널별 반복 주제, 시리즈, 협업자, running joke 지식베이스를 만든다(실제로 반복돼야 인정하고, 점수 기여는 가산·상한·끄기 가능) — [clips-studio README](https://github.com/ColinGPT9/clips-studio)
- hotclip: 음량, 탄막, 웃음이 같은 초에 함께 올라야 진짜 爆点으로 본다("只有音量高可能是BGM,只有弹幕高可能是刷屏"). 표정 피크는 YuNet+FER+(MIT 모델), 장면 경계는 TransNetV2로 잡는다. 선택적으로 Ollama `qwen3.5:4b`가 3×3 격자 프레임을 보고 시각 개그를 찾고, 상위 후보를 비전 모델로 재검토해 "画面与标题货不对板"이면 경고한다. 로컬 소형 모델로 1차 거르고 클라우드는 입선 구간만 정독하는 2단 퍼널이다. 참고 爆款 영상을 넣으면 리듬 프로필에 맞춰 고른다(`--reference`) — [hotclip README](https://github.com/xixihhhh/hotclip)
- NeonClipping Fast mode: 오디오만 받는다(85분에 79 MB). YouTube 자체 단어 타이밍 자막을 전사본으로 쓰고, 2분 로컬 기준선 대비 음량 점프, 2~4 kHz 대역 에너지(고함), 조용함→큰 소리 전환으로 점수를 매긴다. Ollama가 후보별 점수·제목·hook을 쓰고, 선택 구간만 내려받아 오디오 매칭으로 정확히 자른다. Deep mode는 Farneback 광류 모션과 컷 밀도를 더하고 후보를 4배 뽑아 앞뒤 15초 맥락을 준다. 실측은 85분 YouTube 스트림 97초, 3시간 Twitch VOD 136초(RTX 2060) — [neonclipping README](https://github.com/iamajmeena/neonclipping)
- ClipMint: 영상 유형(stream/vlog/podcast/tutorial/sports)을 시작·중간·끝 발화와 제목·설명으로 판별하고 유형별로 다른 랭킹 규칙을 적용한다. 점수를 Hook/Moment/Look/Energy/Pace로 나누고 순위 이유를 보여 준다. 쿼터가 소진되면 Gemini→Groq→OpenRouter→Ollama→OpenAI→Claude 순서로 넘어간다. `qwen2.5vl:7b`·`gemma3` 같은 비전 모델이 프레임을 확인한다. "webcam at the top, vertical for Shorts, 5 clips" 같은 자연어로 레이아웃을 지정한다 — [clipmint README](https://github.com/kleZ799/clipmint)
- SupoClip: 클립마다 hook/engagement/value/shareability 점수, 처음 몇 초에 박는 AI hook 제목, 트림·분할·병합 편집기 — [supoclip README](https://github.com/FujiwaraChoki/supoclip)
- AI-Youtube-Shorts-Generator: hooks, emotional peaks, opinion bombs, revelation, conflict, quotable lines로 순위를 매기고 클립마다 Score+Hook+Reason을 단다. `xargs`로 URL 목록을 일괄 처리한다 — [README](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator)
- autoclip(zhouxiaoka): 플랫폼별로 기준을 넘는 클립을 최대 10개 생성하고 나머지는 후보로 남긴다. 클립마다 표지, 제목, 소개, 话题, ZIP 게시 패키지를 만든다. 브랜드 아웃트로는 기본으로 켜져 있다. 클라우드 ASR(百炼 `qwen-audio-3.1-asr-flash`, 약 0.1위안/시간)을 쓸 수 있다 — [autoclip README](https://github.com/zhouxiaoka/autoclip)
- douyin-living: 탄막 텍스트 특징(`dmRepeatRate`, `dmQuestionRate`, `dmExclamationRate`, `dmEmojiRate`)과 키워드 범주 강도(high-energy/funny/controversy/interactive/emotional/shopping)를 쓴다. `utr_auto_calibrate`는 그 방송의 UTR 분포 하위 분위수로 도배 방지 임계값을 자동으로 잡는다. 2단계 recall/rerank는 선택 사항이다 — [douyin-living README](https://github.com/CipherNoct/douyin-living)

**학습·피드백 루프 (stream2clip에 없음)**
- NeonClipping: 결과마다 별 5개 평가를 받아 `data/feedback.jsonl`에 로컬 저장한다. 서로 다른 순간 8개 이상이 평가되면 로컬 랭킹 가중치가 조정된다("a small preference ranker, not the foundation model") — [neonclipping README](https://github.com/iamajmeena/neonclipping)
- SharkyClips: thumbs up/down으로 제목 스타일을 학습하고, glossary로 이름 철자를 지키며, 각 플랫폼 조회수를 되받는다 — [sharkyclips README](https://github.com/utkualsir/sharkyclips)
- hotclip: 채택·거부한 후보를 로컬 선호 프로필에 넣는다. 플랫폼에서 내보낸 CSV/JSON 조회·상호작용 데이터를 `pnpm cli feedback`에 주면 고성과·저성과 콘텐츠의 주제, hook, 길이 공통점을 찾아 다음 선택에 반영한다 — [hotclip README](https://github.com/xixihhhh/hotclip)
- reelsaw: 수락, 거부, 컷, 수정, 편집 기록을 decision log에 남긴다. 거부된 컷은 filler 검출기의 "keep" 예시가 되고, `reelsaw decisions export`로 eval 케이스가 된다. Settings → Learning에서 끄거나 지울 수 있다 — [reelsaw README](https://github.com/osbytes/reelsaw)
- ClipMint: 게시한 각 클립의 성과를 읽어 채널에서 통하는 것을 알려 주고, 근거가 충분하면 랭킹을 조정한다 — [clipmint README](https://github.com/kleZ799/clipmint)
- Clips Kitty: YouTube Analytics API의 **organic audience retention**(`dimensions=elapsedVideoTimeRatio`, `metrics=audienceWatchRatio,relativeRetentionPerformance`, `audienceType==ORGANIC`)을 `audience_curve()`의 선택적 인증 소스로 넣었다. 공개 Most Replayed/채팅 리플레이 경로 위에 얹는 방식이다(이슈 #85, PR #88 병합) — [clips-studio #85](https://github.com/ColinGPT9/clips-studio/issues/85)
- OpenShorts(게시 클립 조회수 표시)와 podcli("YouTube analytics to see which clips landed")에도 게시 후 분석 기능이 있다 — [openshorts](https://github.com/mutonby/openshorts), [podcli](https://github.com/nmbrthirteen/podcli)

**리프레이밍·레이아웃**
- OpenShorts: 장면마다 TRACK(MediaPipe+YOLOv8 얼굴 추적), GENERAL(블러 배경), SPLIT(두 화자를 쌓고 자막을 이음매에 배치), SCREENCAST(화면 위 발표자) 중 하나를 쓰고, Gemini가 영상별로 고른다 — [openshorts](https://github.com/mutonby/openshorts)
- Clips Kitty: YOLOv8 pose와 TalkNet active-speaker(얼굴+오디오)로 화자를 따라가되 패닝 없이 컷으로 바꾼다. 멀티캠 podcast mode, 이미 세로로 송출된 라이브를 그대로 쓰는 Vertical Live(Twitch Dual Format, Streamlabs Dual Output), 스포츠 공 추적(E-BARD YOLOv8n, CC BY 4.0)이 있다 — [clips-studio](https://github.com/ColinGPT9/clips-studio)
- NeonClipping: 네이티브 레이아웃 11종(카메라 위/아래, 블러, 전체 크롭, 게임만, 네 귀퉁이 오버레이, 원형 facecam, 좌우 배치), facecam 위치 프리셋, 박스 직접 그리기, 플랫폼 safe zone 미리보기 — [neonclipping](https://github.com/iamajmeena/neonclipping)
- reelsaw: UltraFace(1.2 MB ONNX, CPU 약 7 ms/프레임)로 4 fps 샘플링해 장면 컷과 얼굴 유무 변화 지점에서 구간마다 레이아웃을 고른다 — [reelsaw](https://github.com/osbytes/reelsaw)
- opensource-clipping: pyannote로 3인 이상 split-screen, 동시 발화 때만 블러 pillarbox로 바꾸는 카메라 스위치 — [opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping)
- AutoShorts(JayWebtech)는 center-crop뿐이다 — [autoshorts](https://github.com/JayWebtech/autoshorts)

**자막·편집 스타일**
- NeonClipping: 자막 스타일 5종(GTA Neon, Impact, Clean, Hormozi, MrBeast)과 52개 언어. SRT/ASS/WebVTT를 가져와 단어 타이밍을 조정하고 분할·병합할 수 있다. 오프닝 헤딩(기본 8초)과 "Improve opening heading"이 있다 — [neonclipping](https://github.com/iamajmeena/neonclipping)
- reelsaw: AI가 클립별 핵심 단어를 골라 색과 크기로 강조한다. 가독성 제한(약 두 줄, 최소 0.7초, 단어당 0.3초)이 있다. vocabulary hints(`TRANSCRIPT_BIAS`)는 채널명, 제목, 설명, 태그, 챕터의 고유명사를 ASR prompt로 넘긴다. filler/false start 컷은 forced alignment로 위치를 잡고 이음매를 다시 들어 검증한다 — [reelsaw](https://github.com/osbytes/reelsaw)
- ViralCutter: Hormozi 스타일 단어별 하이라이트와 이모지 — [ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter). ClipMint: 강조 구간 punch-in, 이모지, stock B-roll — [clipmint](https://github.com/kleZ799/clipmint). StreamClipper: 애니메이션 자막 15종, punch-in zoom, filler 제거 — [streamclipper](https://github.com/alokbaraii/streamclipper)
- SharkyClips: 대본 편집(단어를 지우면 컷되고, 첫·끝 단어를 끌어 트림), 웃음 안에서는 자르지 않는 무음·filler 컷(짧은 crossfade), 피크와 facecam 반응에 맞춘 smart zoom, "peak flash" 오프너, 아랍어 RTL 자막 — [sharkyclips](https://github.com/utkualsir/sharkyclips)
- OpenShorts·reelsaw: 원본·출력 모니터와 전체 전사본을 나란히 두고, 단어를 클릭해 컷하는 에디터 — [openshorts](https://github.com/mutonby/openshorts), [reelsaw](https://github.com/osbytes/reelsaw)

**B-roll·더빙·생성 미디어**
- B-roll: SupoClip(Pexels stock 오버레이와 전환 효과), opensource-clipping(Pexels, crossfade, Ken Burns, multi-hook intro), ClipMint, cutawan — [supoclip](https://github.com/FujiwaraChoki/supoclip), [opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping), [cutawan](https://github.com/JeremySNR/cutawan)
- 더빙: OpenShorts는 ElevenLabs 30개 이상 언어, 음성 클로닝(사용자 키)과 Gemini가 생성하는 FFmpeg 필터 효과를 제공한다. Clips Kitty는 로컬 TTS 더빙(언어별 음성 시청), 자막 번역 검토를 제공한다 — [openshorts](https://github.com/mutonby/openshorts), [clips-studio](https://github.com/ColinGPT9/clips-studio)
- OpenShorts에는 YouTube Studio 기능(제목 10개+다듬기 채팅, 얼굴 합성 썸네일, 챕터 타임스탬프 설명란)과 AI 배우 UGC 광고 생성(fal.ai)도 있다 — [openshorts](https://github.com/mutonby/openshorts)

**게시·자동화**
- SharkyClips는 YouTube Data+Analytics API, TikTok Content Posting API, Instagram Graph API를 직접 연동한다. 토큰은 DPAPI/Keychain으로 암호화하고, TikTok 필수 게시 화면(공개 범위, 상호작용, 콘텐츠 고지)을 내장했다. 플랫폼별 캡션 제한, 예약 시각, 재시도를 지원한다 — [sharkyclips](https://github.com/utkualsir/sharkyclips)
- 게시 대행 SaaS를 쓰는 곳: OpenShorts(Upload-Post, TikTok, Instagram, YouTube, Facebook, LinkedIn, Threads, Bluesky, "Schedule a week"), autoclip(Upload-Post, 이전 조사), AutoShorts(PostOnce, 예약 배치는 하루 1클립) — [openshorts](https://github.com/mutonby/openshorts), [autoshorts](https://github.com/JayWebtech/autoshorts)
- 직접 연동하는 곳: SupoClip(YouTube/TikTok/Instagram 게시와 예약), StreamClipper(YouTube Shorts와 Instagram Reels, `streamclipper publish`로 일주일 예약), opensource-clipping(Facebook Reels, Meta Graph API) — [supoclip](https://github.com/FujiwaraChoki/supoclip), [streamclipper](https://github.com/alokbaraii/streamclipper), [opensource-clipping](https://github.com/NaufalRizqullah/opensource-clipping)
- MCP 서버: OpenShorts(`/mcp`), autoclip(MCP `get_version` 등), hotclip(`clip_video`/`detect_highlights`), SupoClip(`mcp/`), reelsaw, podcli(도구 32개), Clips Kitty — 각 README. reelsaw는 Standard Webhooks 서명 웹훅(`project.created`/`project.done`)과 로그인 없는 공유 링크(Buffer, Metricool, Zapier용)를, OpenShorts는 n8n 예제를 제공한다 — [reelsaw](https://github.com/osbytes/reelsaw), [openshorts](https://github.com/mutonby/openshorts)

**큐·배치·인프라**
- 영속 작업 큐: SharkyClips(다중 레인 큐 + psutil/NVML 리소스 거버너), reelsaw(ingest→transcribe→refine×3→pick→render 5개 큐, 렌더 중 재시작해도 이어서 진행), OpenShorts(`MAX_CONCURRENT_JOBS` 세마포어), hotclip(녹화 감시와 웹훅이 공유하는 영속 큐, 재시작 시 소재·전사·후보·수동 컷 복구) — 각 README
- 하드웨어 인코딩: NVENC/AMF/QSV 자동 감지와 CPU 폴백(Clips Kitty, SharkyClips + VideoToolbox), OpenShorts NVENC, podcli VideoToolbox/NVENC — 각 README
- 배포 형태: Docker(OpenShorts는 RAM 8 GB 이상, CPU에서 8분 영상당 5~8분, SupoClip, reelsaw, autoclip 웹), 설치본(hotclip exe/zip/dmg/AppImage, cutawan, AutoShorts msi/dmg/deb), 로컬 웹 UI(SharkyClips는 FastAPI가 127.0.0.1에서 React UI를 서빙), Google Colab(StreamClipper), 휴대폰 리모컨(NeonClipping) — 각 README
- 멀티 머신: biliup Fleet. 노드가 `biliup node join` 티켓으로 붙고, 아웃바운드 연결만으로 암호화 relay를 쓴다 — [biliup](https://github.com/biliup/biliup)

**라이브·무인 녹화**
- NeonClipping Creators 패널: Twitch 이름이나 Twitch/YouTube 채널을 등록하면 1분마다 확인해 라이브가 시작되면 Streamlink로 녹화하고 채팅 급증 지점을 자른다. 무인 녹화는 3시간 상한, 남은 디스크 8 GB 미만이면 중단, 마지막 클립 후 원본 삭제다. 채팅 hype meter는 최근 약 30초 채팅을 그 방송의 평소 속도와 비교한다(피크=평소의 4배). YouTube 자동 클리핑은 "not run end to end"라고 적혀 있다 — [neonclipping](https://github.com/iamajmeena/neonclipping)
- StreamClipper: 순간 발생 약 35초 뒤 클립이 준비된다. 실제 Twitch에서만 시험했고 YouTube Live와 Kick은 미시험이다 — [streamclipper](https://github.com/alokbaraii/streamclipper)
- biliup: 미리보기 페이지에서 마커를 찍거나 "직전 30초/1분/2분 자르기"를 할 수 있다. 녹화 후에는 로컬 영상과 탄막 XML을 모자이크·탄막 조정과 함께 합성해 내보낸다 — [biliup](https://github.com/biliup/biliup)
- hotclip: 录播姬/OBS 폴더를 7×24 감시하고, 녹화가 끝나면 자동으로 자른다. 录播姬 `.xml`과 抖音 `.jsonl` 탄막을 자동으로 찾는다 — [hotclip](https://github.com/xixihhhh/hotclip)

**게임·도메인 특화, 플러그인**
- SharkyClips: RapidOCR로 Delta Force·League of Legends HUD를 읽어 킬·멀티킬·오브젝트를 잡는다("A pentakill is never cut in half"). sherpa-onnx로 웃음·고함을 검출한다. 욕설은 11개 언어로 bleep/mute하고, 렌더 후 다시 들어 여전히 들리면 더 넓게 bleep해 재렌더하고, 그래도 안 되면 게시를 보류한다 — [sharkyclips](https://github.com/utkualsir/sharkyclips)
- Clips Kitty plugin SDK(MIT): find/understand/rate/edit 단계를 둔다. finder는 1개, understand와 rate는 각 3개까지다. 예제 플러그인은 `scene-cut-highlights`와 `keyword-rater` — [clips-studio](https://github.com/ColinGPT9/clips-studio)
- ChopperBot: "Everything Plugin", 핫스왑, 플랫폼 인기 방송 감시(정체) — [ChopperBot](https://github.com/Geniusay/ChopperBot)

**편집기 연동·내보내기**
- 剪映/CapCut 초안 내보내기: hotclip, zenstory video-recap-skills(`timeline.json` 중심, 표준 라이브러리+ffmpeg만 사용), StreamClipper("Open a clip in CapCut") — [hotclip](https://github.com/xixihhhh/hotclip), [zenstory](https://github.com/zenstory-ai/video-recap-skills), [streamclipper](https://github.com/alokbaraii/streamclipper)
- auto-editor: NLE 타임라인 export(README에 `--export kdenlive` 명시). 온라인 앱과 데스크톱 앱은 별도 독점 에셋을 쓴다 — [auto-editor](https://github.com/WyattBlue/auto-editor)
- SRT/VTT 입출력(reelsaw), 자막 파일 입력 `--subtitles`(hotclip, 최대 5 MB/20,000 cue) — 각 README

**컴플라이언스성 기능**
- hotclip: 플랫폼별 AIGC 표기 문구와 조작 위치 안내("AIGC 标注助手")를 제공하고, 한 방송에서 5개를 넘게 뽑으면 생산량 제한을 권고한다("2026 算法偏好质量不偏好数量"). 반면 "反指纹多版"(중복 검출을 피하는 다중 버전)도 있다 — [hotclip](https://github.com/xixihhhh/hotclip)
- StreamClipper Legal: "Only clip streams you have permission to clip, such as a streamer's official clipping program" — [streamclipper](https://github.com/alokbaraii/streamclipper)

### Inferences
**stream2clip에 없는 기능 (관련도 높은 순, 내 판단)**
1. **평가·성과 학습 루프**: 클립별 평가(별점이나 👍/👎), 채택·거부 로그, YouTube Analytics organic retention과 게시 성과 CSV를 받아 신호 가중치를 재학습한다. stream2clip은 이미 "시청자 댓글 타임스탬프 평가"가 있으므로 같은 평가 하네스 위에 가중치 튜닝(douyin-living `tune_weights.py`식 고정 특징 재가중)을 얹기 쉽다.
2. **선택적 로컬 LLM 판정**: OpenAI 호환 `base_url` 하나로 Ollama/LM Studio를 지원하는 것이 사실상 표준이다. "내장 LLM 없음" 원칙을 지키려면 플러그인 경계 밖의 선택 기능으로 두고, reelsaw식 pairwise 랭킹이나 hotclip식 2단 퍼널(신호로 1차 → LLM은 입선 구간만)을 쓸 수 있다. 개수를 고정하지 않는 상대 게이트도 참고할 만하다.
3. **대본 기반 편집과 군말(filler) 컷**: 현재 기능은 무음 트림뿐이다. 웃음 안에서는 자르지 않는 규칙(SharkyClips)과 forced alignment 검증(reelsaw)은 웃음 검출이 이미 있는 stream2clip에 잘 맞는다.
4. **AI 핵심어 강조 자막과 스타일 프리셋**(Hormozi/MrBeast류, 이모지, punch-in zoom, peak flash 오프너): 카라오케 ASS는 있지만 "핵심 단어 색·크기 강조"와 가독성 제한 규칙은 명시돼 있지 않다.
5. **TikTok/Instagram 직접 게시**(TikTok 필수 게시 화면 포함)와 **게시 후 조회수 회수**: SharkyClips(MIT)가 직접 API 연동의 레퍼런스다.
6. **MCP 서버·웹훅·영속 큐**: 상위 프로젝트 대부분이 MCP를 노출한다. 라이브러리+CLI가 이미 있으므로 MCP 래퍼의 비용은 낮을 것이다.
7. **무인 채널 감시 녹화**(채널을 등록하면 라이브 시작 시 녹화·클립, 디스크 가드·시간 상한)와 **채팅 hype meter** UI: stream2clip의 라이브 모드는 OBS replay buffer 중심이어서, 남의 방송을 지켜보는 키리누키 채널 용도는 비어 있다.
8. **플러그인 SDK의 역할 분리**(find/understand/rate/edit): stream2clip은 번역 플러그인만 있다. 게임 HUD OCR이나 노래 방송 검출을 플러그인으로 열면 Clips Kitty처럼 외부 기여를 받을 수 있다.
9. **욕설 bleep + 렌더 후 재청취 검증**: 기획사 가이드라인 검사와 같은 "게시 전 차단" 계열이다. 일본어·한국어 욕설 목록이 필요하다.
10. **CapCut/剪映 초안 export**: 키리누키 편집자가 실제로 쓰는 NLE로 바로 넘기는 경로다. 지금은 EDL/마커만 있다.
11. **비전 LLM 프레임 재검토**(3×3 격자)와 **참고 영상 스타일 프로필**: 선택 기능 후보다.
12. **하드웨어 인코더 자동 감지**(NVENC/AMF/QSV + CPU 폴백): 이미 있는지 stream2clip 코드에서 확인해야 한다.
13. **자연어 레이아웃·편집 지시**(ClipMint, Clips Kitty): LLM이 필요하므로 위 2번에 종속된다.

**stream2clip이 여전히 앞서는 부분**: VTuber 아바타 박스(애니메 얼굴) 인식, JP/KR 반응 어휘와 CHZZK/SOOP 입력, 기획사 가이드라인과 재사용 콘텐츠 검사, BGM·SFX 라이선스 추적, 시청자 댓글 타임스탬프를 약한 라벨로 쓰는 평가, 아바타 별도 녹화 합성. 조사한 클리퍼는 모두 facecam(실사 얼굴, OpenCV/YOLO/UltraFace/TalkNet)을 전제로 한다.

**들이지 말아야 할 기능**: hotclip의 "反指纹多版"은 플랫폼의 재사용·중복 콘텐츠 판정을 피하려는 기능이다. stream2clip의 재사용 콘텐츠 검사와 기획사 가이드라인 방향에 정면으로 어긋난다. 음성 클로닝 더빙(OpenShorts의 ElevenLabs)은 이전 보고서가 지적한 hololive 음악 가이드라인의 탤런트 음성 생성 거부와 충돌한다.

### Gaps
- stream2clip에 하드웨어 인코딩 자동 선택, AI 핵심어 강조가 이미 있는지는 이 조사 범위(외부 프로젝트) 밖이라 확인하지 않았다.
- 각 프로젝트의 리프레이밍이나 자막 품질을 실제로 돌려 비교하지 않았다. README 주장만 있다.
- TikTok Content Posting API의 감사(audit) 요건, 미감사 앱의 비공개 게시 제한은 SharkyClips README에 "required post screen"만 있고 세부는 확인하지 못했다.

## 3. 검출 품질은 어떻게 평가하며, 사용자는 무엇을 불평하는가

### Takeaway
정량 평가 도구를 공개한 곳은 소수다. douyin-living(사람 라벨 기반 Precision/Recall/F1@K + 가중치 튜닝 + 라벨링 리포트), hotclip(골든셋 CER/WER, 단어 경계 오차, 爆点 recall@3/@5), reelsaw(decision log에서 만든 eval 케이스, `pnpm eval:cuts`)가 그렇다. 나머지는 "실제 스트림에서 시험"이나 테스트 스위트 수준이다. 이슈는 하이라이트 품질보다 **설치와 실행 실패**(Whisper 감지, 다운로드 403/봇 체크, 작업 큐 정지, GPU 미감지), **외부 API 변경**, **LLM 비용**이 압도적으로 많다.

### Cited Findings
**평가 방식**
- douyin-living: `scripts/evaluate.py`가 `time_table.json`과 사람 라벨 JSON으로 Precision@K/Recall@K/F1@K를 계산하고 여러 방송을 집계한다(`--fail-on-target`). `tune_weights.py`는 오디오·텍스트·비전을 다시 돌리지 않고 고정 특징 위에서 가중치를 random search로 맞추고 YAML로 출력한다. `label_report.py`는 후보 검토 페이지와 라벨 템플릿을 만들고, `profile_report.py`는 같은 라벨셋으로 모든 프로필을 다시 채점한다. 2단계 랭킹은 기본으로 꺼 두고 "固定标注集做 A/B"에 쓴다. `--report-html`은 점수 곡선, 후보 카드, 썸네일, 탄막 상위 단어, 복사 가능한 ffmpeg 명령이 담긴 dry-run 보고서를 만든다 — [douyin-living README](https://github.com/CipherNoct/douyin-living)
- hotclip: "质量黄金集" `pnpm quality:eval [fixture.json]`이 CER/WER, 단어 경계 중앙값·P95 오차, 爆点 recall@3/@5를 로컬에서 낸다. 모델이나 임계값을 바꾸기 전에 같은 샘플로 돌리는 용도다. 타임라인에 탄막·음량 곡선을 그리고 후보마다 "为什么选这段"와 4개 분항 점수를 보여 주며, 약한 클립에는 "不建议发布"를 표시한다 — [hotclip README](https://github.com/xixihhhh/hotclip)
- reelsaw: `reelsaw decisions export`로 사용자 결정을 JSONL eval 케이스로 만든다. `reelsaw cuts --fixture`는 표시된 군말 구간을 오프라인 회귀 케이스(`pnpm eval:cuts`)로 내보낸다. 성능 실측(Apple Silicon, `qwen2.5:14b`, 20분 팟캐스트): 전사 4.9분, refine 10분, moment 4분, 렌더 47초, 합계 20분 — [reelsaw README](https://github.com/osbytes/reelsaw)
- SharkyClips: Windows/Ubuntu/macOS에서 pytest 600개 이상, Playwright로 9개 화면 크기×3개 언어×양 테마 레이아웃 검사, 라이브 미리보기와 렌더 결과의 픽셀 일치 검사. 하이라이트 정확도 지표는 공개하지 않았다 — [sharkyclips README](https://github.com/utkualsir/sharkyclips)
- NeonClipping: 실제 서버를 대상으로 한 end-to-end 스위트(모든 레이아웃·자막 스타일 렌더와 측정, 실제 YouTube/Twitch/로컬 소스로 Make clips) — [neonclipping README](https://github.com/iamajmeena/neonclipping)
- Clips Kitty: IRL·잡담·팟캐스트는 "gets tested on real streams before release"라고만 적었고 정량 지표는 없다 — [clips-studio README](https://github.com/ColinGPT9/clips-studio)
- artbyjazi/autoclip은 솔직한 평가를 남겼다: "A 7B model returns valid JSON full of mediocre picks; a frontier model is noticeably better at spotting a real hook." — [artbyjazi/autoclip README](https://github.com/artbyjazi/autoclip)
- 연구 쪽 표준 벤치마크 도구: line/lighthouse(재현 가능한 MR-HD와 audio moment retrieval 라이브러리, Apache-2.0) — [lighthouse](https://github.com/line/lighthouse)
- 긴 스트림 처리 노하우를 프로젝트끼리 공유한 사례: AutoShorts 이슈 #45(10분 오디오 청크+겹침, VRAM 안전 파이프라인)에 reelsaw 개발자가 답했다. "cut chunks at long pauses rather than fixed minutes, with ~20% overlap, then dedupe candidates whose bounds snap to the same sentence" — [autoshorts #45](https://github.com/JayWebtech/autoshorts/issues/45)

**사용자 불만 (댓글 많은 이슈 기준)**
- autoclip: 미리보기 검은 화면, 2시간+1시간 게임 방송 분석에 DeepSeek 2.3위안이 들고 계속 과금, 가져오기·분석이 멈춤(#175). v1.5.0에서 DeepSeek 사고 모드 비활성, 출력 제한, 작업 중복 방지로 대응했다. 다운로드가 5%에서 멈춤(#163), 로컬 Whisper 자막 실패(#247), ★ 부풀리기 의혹(#59) — [#175](https://github.com/zhouxiaoka/autoclip/issues/175), [issues](https://github.com/zhouxiaoka/autoclip/issues)
- SupoClip: AssemblyAI `speech_model` 파라미터 폐기로 전사가 깨짐(#11, #56). 큐에 넣은 영상이 진행되지 않음(#2, 워커 heartbeat 추가로 종료) — [#2](https://github.com/FujiwaraChoki/supoclip/issues/2), [#56](https://github.com/FujiwaraChoki/supoclip/issues/56)
- OpenShorts: 로컬 모델 지원 요청(#17, 이후 `LLM_BASE_URL`로 해결), Gemini 과부하(#27), 생성 클립 로딩과 Auto Edit 실패(#18). 사용자 입력에서 오는 프롬프트 인젝션 보강(#36) — [issues](https://github.com/mutonby/openshorts/issues)
- AI-Youtube-Shorts-Generator: yt-dlp HTTP 403(#60), MuAPI 타임아웃(#55), 로컬 LLM 요청(#69) — [issues](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator/issues)
- Clips Kitty: macOS에서 실행해 본 사람이 없음(#62), Intel GPU 미감지(#227), CUDA(#223), 렌더 실패 WinError 32(#74). 기능 요청으로는 주제 프롬프트 기반 클립(#106)과 16:9 롱폼에서 9:16만 생성(#131) — [issues](https://github.com/ColinGPT9/clips-studio/issues)
- FunClip: fun-asr-nano와 SenseVoice ASR 실패(#161), 영어 대문자가 섞이면 매칭이 항상 실패하고 0건이면 원본을 조용히 반환(#198), 화자 분리 오류(#139), 자막 색 변경 불가(#135). 무음 제거는 여전히 TODO — [issues](https://github.com/modelscope/FunClip/issues), [README](https://github.com/modelscope/FunClip)
- AutoShorts(JayWebtech): Whisper를 설치했는데도 감지하지 못함(#18, #30, #47), Cut 단계에서 응답 없음(#19) — [issues](https://github.com/JayWebtech/autoshorts/issues)
- NeonClipping(공개 3일): 12%에서 멈춤(#16), YouTube 봇 체크(#37), PyAV 19 호환 오류(#2) — [issues](https://github.com/iamajmeena/neonclipping/issues)
- auto-editor: 오래된 대표 불만은 "cuts words instead of silence"(#582)와 출력 파일이 입력보다 큼(#58) — [issues](https://github.com/WyattBlue/auto-editor/issues)
- HN Show HN "AutoShorts – Local, GPU-accelerated AI video pipeline for creators"(72점/31댓글, 약 10개월 전): "로컬이라면서 OpenAI/Gemini가 먼저 나온다"("Misleading"), README가 LLM이 쓴 것 같다, 소셜 미디어 "slop"을 양산한다("Automating editing is by definition making it slop")는 비판이 나왔다. 작성자는 본인 게임 세션 하이라이트 용도라고 답했다 — [HN 46751675](https://news.ycombinator.com/item?id=46751675)
- HN Show HN OpenShorts(2026-03-08)는 1점, 댓글 0이었다 — [HN Algolia](https://hn.algolia.com/api/v1/search?query=clips%20shorts%20open%20source&tags=story&numericFilters=created_at_i%3E1767225600)

### Inferences
- stream2clip의 "시청자 댓글 타임스탬프 대비 평가"는 이들 대부분보다 앞선 약한 라벨 평가다. douyin-living처럼 **고정 특징 캐시 + 가중치 튜닝 + 라벨링 HTML 리포트**를 붙이면 신호 융합 가중치를 데이터로 정할 수 있다. 사람 라벨이 아니라 댓글 타임스탬프와 heatmap을 라벨로 쓸 수 있다는 점은 stream2clip만의 장점이다.
- 불만의 대부분은 외부 의존성 변화(AssemblyAI API 폐기, yt-dlp 403/봇 체크, PyAV 메이저 업데이트, DeepSeek 과금)에서 온다. autoclip이 yt-dlp를 `==2026.8.19`로 고정하고 douyin-living이 faster-whisper 1.x와 whisperx 3.x를 고정한 것처럼, 버전 고정과 `doctor`/헬스체크(hotclip, artbyjazi)를 갖추는 쪽이 신뢰성에서 이긴다.
- LLM을 선택 기능으로 넣는다면 비용 보호(최대 호출 수, 사고 모드 비활성, 출력 토큰 제한)를 처음부터 넣어야 한다. autoclip #175가 그 근거다.

### Gaps
- 오픈소스 클리퍼끼리 같은 데이터셋으로 하이라이트 정확도를 비교한 벤치마크는 찾지 못했다.
- Reddit 사용자 리뷰는 검색 결과에 없었다. OpusClip 등과 비교한 독립 품질 평가도 찾지 못했다.
- autoclip의 `docs/research/2026-10-what-drives-views` 연구 문서(조회수 요인 분석)는 README 링크만 확인했고 본문은 읽지 않았다.

## 4. MIT 프로젝트에서 재사용할 때 문제가 되는 라이선스와 의존성

### Takeaway
신작 상당수가 copyleft(AGPL: Clips Kitty 본체, hotclip, reelsaw, podcli, StreamClipper, ViralMint, NekoClipper, medusa-clip, GTAClipper / GPL-3.0: ViralCutter, hi-lite, palmier-pro)이거나, 비상업(SupoClip, 2026-11-19 v1.1로 다시 개정), 또는 무라이선스(AutoShorts 1.6k★, jiang-clips, imgly/videoclipper)다. MIT 프로젝트도 의존성을 따져야 한다. **OpenShorts(MIT)는 `ultralytics==8.4.46`(AGPL-3.0)을 고정 의존성으로 둔다.** 코드까지 재사용할 만한 MIT/Apache 레퍼런스는 SharkyClips, NeonClipping, ClipMint, douyin-living, autoclip(zhouxiaoka), opensource-clipping, biliup, bilive, lighthouse, auto-editor(Unlicense), Clips Kitty SDK(MIT)다.

### Cited Findings
- SupoClip LICENSE: "SupoClip Noncommercial Source License, Version 1.1 (November 19, 2026)", Licensor는 Shiori LLC다. "This license leaves intact rights already granted under earlier licenses"라고 적혀 있다. README는 "free for noncommercial use and for individual creators on their own hardware"라고 쓴다 — [supoclip LICENSE](https://github.com/FujiwaraChoki/supoclip/blob/main/LICENSE), [README](https://github.com/FujiwaraChoki/supoclip)
- OpenShorts: 핵심 앱은 MIT, `cloud/` 디렉터리(과금·관리 키·호스팅 인프라, `BILLING_ENABLED`)는 "OpenShorts Commercial License"(source-available)다. `requirements.txt`에 `ultralytics==8.4.46`, `mediapipe==0.10.14`, `faster-whisper==1.2.1`이 있다 — [openshorts README](https://github.com/mutonby/openshorts), [requirements.txt](https://github.com/mutonby/openshorts/blob/main/requirements.txt)
- Clips Kitty: 앱은 GNU AGPL-3.0-or-later, `sdk/python/`과 예제 플러그인은 MIT("your plugin can use any licence, and nothing has to be forked"), 농구 검출은 E-BARD(YOLOv8n, CC BY 4.0, 무수정) — [clips-studio README](https://github.com/ColinGPT9/clips-studio)
- SharkyClips(MIT) 의존성: faster-whisper, yt-dlp, sherpa-onnx(웃음·고함), opencv-python-headless(`<5`, "5.x dropped the bundled face model"), RapidOCR/PaddleOCR 모델(ONNX), Ollama Qwen 3.5 — [backend/requirements.txt](https://github.com/utkualsir/sharkyclips/blob/main/backend/requirements.txt), [README](https://github.com/utkualsir/sharkyclips)
- NeonClipping(MIT) 의존성: yt-dlp, faster-whisper, opencv-python-headless로 가볍다. 로컬 LLM으로 Gemma 4를 쓴다 — [requirements.txt](https://github.com/iamajmeena/neonclipping/blob/main/requirements.txt), [README](https://github.com/iamajmeena/neonclipping)
- hotclip(AGPL)이 쓰는 모델 중 YuNet과 FER+는 README가 "几 MB 的 MIT 协议模型"이라고 적는다. pyannote와 3D-Speaker로 화자를 분리한다 — [hotclip README](https://github.com/xixihhhh/hotclip)
- FunClip v2.2.0(2026-08-30)은 서드파티 MOSS-Transcribe-Diarize 경로(장시간 ASR, 타임스탬프, 익명 화자)를 추가했다 — [FunClip README](https://github.com/modelscope/FunClip)
- auto-editor: 저장소 전체가 Public Domain(Unlicense)이지만 "Binary artifacts in the Releases section may be under various open source licenses"이고, 온라인 앱과 데스크톱 앱의 고유 에셋은 별도 독점 라이선스다 — [auto-editor README](https://github.com/WyattBlue/auto-editor)
- biliup README 면책 조항: "for personal learning and research purposes only", "Please respect copyright and platform ToS" — [biliup README](https://github.com/biliup/biliup)
- 게시 대행 서비스 의존: OpenShorts·autoclip은 Upload-Post, AutoShorts는 PostOnce(설정 페이지에서 무료 체험으로 연결)를 쓴다. 둘 다 서드파티 SaaS 계정과 API 키가 필요하다 — [openshorts](https://github.com/mutonby/openshorts), [autoshorts](https://github.com/JayWebtech/autoshorts)
- AI-Youtube-Shorts-Generator는 기본값 `--mode api`가 유료 MuAPI이고, 로컬 모드는 따로 켜야 한다 — [README](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator)
- douyin-living(MIT)은 로그인한 브라우저 쿠키(`DY_LIVE_COOKIES` 등)가 필요하다 — [douyin-living README](https://github.com/CipherNoct/douyin-living)
- zenstory video-recap-skills(MIT)는 핵심 경로가 Python 표준 라이브러리와 ffmpeg/ffprobe뿐이고, 클라우드 ASR·TTS를 켤 때만 외부로 요청한다(원격 호출 공개 문서 별도) — [zenstory README](https://github.com/zenstory-ai/video-recap-skills)

### Inferences
- MIT 프로젝트로 "코드를 가져올 수 있는" 레퍼런스는 다음과 같다. 게시 API 연동·욕설 검증·큐는 SharkyClips(MIT), 오디오 우선 다운로드·선호 랭커는 NeonClipping(MIT), 평가·튜닝 스크립트는 douyin-living(MIT), 장시간 녹화 아키텍처는 biliup(MIT), 연구용 하이라이트 모델 비교는 lighthouse(Apache)다. hotclip, reelsaw, Clips Kitty 본체(AGPL)에서는 설계와 파라미터(신호 공진 규칙, PRP-Sliding-K, 20% 겹침 청크, organic retention 쿼리)만 가져와야 한다. 다만 Clips Kitty SDK가 MIT이므로 "stream2clip 검출기를 Clips Kitty 플러그인으로 내놓는" 방향은 가능하다.
- OpenShorts처럼 MIT 앱이 ultralytics(AGPL)를 고정 의존성으로 두는 패턴은 흔하다. stream2clip이 인물 검출을 추가한다면 MediaPipe(Apache), UltraFace, YuNet 같은 비 AGPL 검출기를 써야 한다. UltraFace와 TalkNet 라이선스는 이번에 확인하지 못했다(Gaps).
- 라이선스가 바뀌는 프로젝트(SupoClip은 AGPL → 비상업 → v1.1)는 특정 커밋의 라이선스를 기록해 두지 않으면 출처 추적이 어렵다. 이전 조사가 AGPL로 기록했다가 고친 것도 같은 이유다.

### Gaps
- UltraFace(reelsaw), TalkNet-ASD(Clips Kitty·OpenShorts류), E-BARD 외 모델, Gemma 4, Qwen 3.5, MOSS-Transcribe-Diarize, RapidOCR 모델 가중치의 라이선스 원문은 확인하지 못했다.
- OpenShorts가 ultralytics를 쓰면서 MIT 배포에 AGPL 의무를 어떻게 처리하는지(NOTICE 등)는 확인하지 못했다.
- Upload-Post와 PostOnce의 약관, 요금, TikTok·Instagram 공식 API 사용 여부는 각 README의 주장만 확인했다.
