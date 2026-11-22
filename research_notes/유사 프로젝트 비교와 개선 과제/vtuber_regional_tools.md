# 일본, 한국, 중국 키리누키 편집 생태계와 VTuber 전용 도구 (2026-11 기준)

조사일: 2026-11-22. 앞선 보고서(`reports/키리누키 영상 레퍼런스 검토.md` 4, 6, 7, 8절과 `reports/버튜버 영상 작업 프로젝트 레퍼런스.md` 2절)에 이미 있는 내용(텔롭 기본형, 글꼴, 화자 색, ちょい見せ, Opus Clip, Eklipse, hotclip, bilive, biliup, ClipRadar, Highlight Analyzer, Holodex API, LiveTL 등)은 반복하지 않고, 새로 찾은 도구와 작업 단계만 적는다.

표기 규칙: "(검색 요약만)"은 원문 페이지를 열지 못했거나 열지 않고 검색 결과 요약으로만 확인한 항목이다. 날짜가 2025년 이전인 자료는 "(오래된 자료)"로 표시했다. 제품 회사가 쓴 블로그는 "(판매자 자료)"로 표시했다.

## 1. 일본: 切り抜き 편집자가 2026년에 쓰는 도구와 텔롭 관례

### Takeaway
일본 편집자의 기본 도구는 여전히 Premiere Pro, DaVinci Resolve(무료), AviUtl 계열, CapCut, Vrew이고, 2026-07에 AviUtl ExEdit2가 정식판이 되었다. 새로 늘어난 것은 채팅 그래프 웹 서비스(CommentClip)와 개인 개발 데스크톱 앱(V-Choki, V-Cut), 채팅과 자막을 함께 분석하는 SaaS(KIRARI)이며, 모두 세로 Shorts 초안 수준이다. stream2clip에 없는 것은 "채팅 그래프를 보며 클릭으로 이동하는 탐색 화면", "타임스탬프 목차 내보내기", "편집자 본인 캐릭터(立ち絵, 표정 차분) 층"이다.

### Cited Findings

**편집 소프트웨어**
- AviUtl ExEdit2는 2026-07-07 v2.0.54에서 베타를 끝내고 정식판이 되었다. 2025-07 첫 베타 이후 약 1년간 50개 넘는 베타가 나왔다. 64비트 Windows 10 이상, DirectX 11.3, AVX2가 필요하다. 기사는 텔롭, PSD, AI 기능은 다루지 않는다 — [窓の杜 2026-07-09](https://forest.watch.impress.co.jp/docs/news/2123628.html)
- AviUtl2 첫 테스트판은 2025-07-07 공개, 기존 拡張編集 플러그인과 통합, 일부 구 플러그인은 미지원 — [Game*Spark 2025-07-08](https://www.gamespark.jp/article/2025/07/08/154794.html)
- PSDToolKit(立ち絵 PSD 표정 차분 도구)은 2026-01-09에 AviUtl2를 지원했다는 비공식 안내. 플러그인은 AviUtl2용으로 새로 대응했는지 개별 확인하라고 권고 (검색 요약만) — [vip-jikkyo.net AviUtl2 가이드](https://vip-jikkyo.net/aviutl2-guide)
- KIRARI 블로그(판매자 자료, 2026-04-01 갱신)가 꼽은 편집 도구: DaVinci Resolve(무료), AviUtl(무료, Windows), CapCut(무료), Premiere Pro(월 ¥2,728부터), Final Cut Pro(¥45,000, Mac). 보조 도구: Canva, Photoshop, VREW, Whisper, OBS Studio, yt-dlp, VOICEVOX, DOVA-SYNDROME, 効果音ラボ, 甘茶の音楽工房. 다른 AI 클립 도구로 OpusClip, Vrew, CapCut AI, ストクリ — [KIRARI 切り抜き 가이드](https://www.kirari.io/blog/vtuber-clip-guide)
- 일반 해설 글은 유료는 Premiere Pro, 무료는 DaVinci Resolve 무료판을 권하고, 초보에게 Filmora, Movavi, CapCut, Vrew를 든다. 보조로 Audacity(음성 속도), VOICEVOX, Vrew, Gladia, Google AI Studio 사용 예 (검색 요약만) — [bloomeria.jp 2026](https://bloomeria.jp/blog/clip-video-editing-beginner-guide), [3freebgm.com 2025](https://3freebgm.com/archives/column/%E3%80%902025%E5%B9%B4%E6%9C%80%E6%96%B0%E3%80%91%E5%88%87%E3%82%8A%E6%8A%9C%E3%81%8D%E5%8B%95%E7%94%BB%E3%81%AE%E4%BD%9C%E3%82%8A%E6%96%B9%E3%81%A8%E3%81%8A%E3%81%99%E3%81%99%E3%82%81%E3%81%AE)
- 제작 시간은 소재 길이의 2~3배이고, 가장 오래 걸리는 단계는 장면 고르기 (검색 요약만) — [SNS ENGINE(PEACE) 칼럼](https://sns-engine.peace-inc.jp/blog/kirinuki-douga-tsukurikata)

**YMM4(ゆっくりMovieMaker4)의 立ち絵, 표정 차분**
- YMM4의 표정 전환은 두 방식: 보이스 아이템의 "立ち絵" 칸에서 대사와 함께 바꾸기, 또는 표정 아이템을 따로 두어 대사와 무관한 시점에 바꾸기. 표정 아이템에 간단한 애니메이션도 붙일 수 있다 — [Bluemist, note](https://note.com/bluemist/n/n03b9a08695a7)
- 캐릭터 설정에 표정 차분을 등록해 두면 대본에서 표정을 지정해 불러온다. 눈, 입의 00번 파일만 깜빡임과 입 움직임에 쓰이고 01번 이후는 정지 표정 차분 (검색 요약만) — [YMM4 공식 FAQ 立ち絵機能](https://manjubox.net/ymm4/faq/%E7%AB%8B%E3%81%A1%E7%B5%B5%E6%A9%9F%E8%83%BD/%E7%AB%8B%E3%81%A1%E7%B5%B5%E6%A9%9F%E8%83%BD%E3%81%AE%E4%BD%BF%E3%81%84%E6%96%B9/), [knb-mayumi.com](https://knb-mayumi.com/ymm4-character/)
- YMM4는 대사를 입력하면 음성과 텔롭이 같이 생성되지만 기본 글자가 작아 안전 영역에 맞춰 키워야 하고, 자막에 효과를 걸어 말풍선을 만든다 (검색 요약만) — [signyamo.blog](https://signyamo.blog/ymm4_use/), [katojishi.com](https://katojishi.com/movie/59-%E5%8B%95%E3%81%8F%E7%AB%8B%E3%81%A1%E7%B5%B5%E3%81%AE%E4%BD%9C%E3%82%8A%E6%96%B9%E3%81%BE%E3%81%A8%E3%82%81-%EF%BD%9E-ymm4%E3%81%AE%E4%BD%BF%E3%81%84%E6%96%B9%E3%82%92%E3%81%AA%E3%82%8B%E3%81%B9/)
- PSD 立ち絵를 PSDTool로 YMM4에서 쓰는 방법 해설이 별도로 있다 (검색 결과 제목만) — [julius0401.com](https://julius0401.com/psdtool-ymm4/)

**유료 편집 대행(코코나라)의 작업 항목**
- VTuber 본인이 맡기는 切り抜き 대행 상품은 텔롭과 자막, 컷, 소재 삽입, 소리와 색 조정, SE와 BGM, 효과, 썸네일을 묶어 팔고, 의뢰할 때 영상 소재, 立ち絵 소재, 자를 구간을 넘기는 흐름 (검색 요약만) — [coconala 2750272](https://coconala.com/services/2750272), [coconala 4071638](https://coconala.com/services/4071638), [coconala 3407856](https://coconala.com/services/3407856)

**채팅(コメント) 분석 도구**
- CommentClip: 아카이브 URL을 붙이면 채팅을 모아 30초 단위 막대그래프로 표시, 재생 위치에 맞춰 채팅이 흐르고 탐색 가능, 가장 활발한 구간 자동 강조, 막대 클릭으로 이동, 긴 방송은 가로 스크롤, 분석 기록 재열람. YouTube만 지원(Twitch 예정). 무료 월 5개, 스탠더드 월 ¥980 무제한. 草 집계, 슈퍼챗, CSV나 타임스탬프 내보내기는 언급 없음. 운영자 미표기(© 2026) — [comment-clip.com](https://comment-clip.com/)
- コメグラフ(stream-comment.net): Twitch, YouTube 댓글 분석 切り抜き 지원 도구였으나 사이트 운영 종료 공지 — [stream-comment.net](https://www.stream-comment.net/)
- Highlight Analyzer(Chrome 확장): 웃음 양과 댓글 속도를 그래프로 그리고 타임스탬프가 붙은 목차를 만드는 기능 (검색 요약만, 앞 보고서에도 있음) — [Chrome 웹스토어](https://chromewebstore.google.com/detail/highlight-analyzeryoutube/pcicbonbpknjgpmofodbaiiljfhdbpok?hl=ja)
- 개인이 만든 "YouTube 영상 페이지에 채팅 수 그래프를 표시하는 확장" 글 두 편 (검색 요약만) — [note diy_smile 1](https://note.com/diy_smile/n/n5e0a1cc725ce), [note diy_smile 2](https://note.com/diy_smile/n/ncab82df8e6bd)
- VTuber 시청용 확장 가운데 시청자 수, 슈퍼챗 합계를 그래프로 보여 주고 아카이브에서는 댓글 수를 집계해 그래프로 보여 주는 기능 소개 (검색 요약만) — [blog.yuki0311.com](https://blog.yuki0311.com/youtube-feature-rich/)
- 질문 게시판에 "라이브 아카이브의 볼거리를 쉽게 찾는 방법"을 묻는 切り抜き 편집자 질문이 있다 (검색 결과 제목만) — [Yahoo!知恵袋](https://detail.chiebukuro.yahoo.co.jp/qa/question_detail/q12314501927)

**切り抜き AI 서비스, 개인 개발 앱 (2026)**
- KIRARI(판매자 자료): "채팅 열기 × 자막 텍스트를 AI가 분석"해 후보 장면 제안, 세로 Shorts와 자막 생성 후 사용자가 수정. 대상 방송은 3시간까지, YouTube URL 입력만 언급, 무료 가입 시 1회 내보내기. 레이아웃 템플릿이나 번역은 언급 없음 — [KIRARI](https://www.kirari.io/blog/vtuber-clip-guide)
- V-Choki: 2026-03 개인 개발자가 공개한 데스크톱 앱. 영상을 클라우드에 올리지 않고 로컬 Whisper 전사와 얼굴 추적으로 세로 영상을 만든다 (검색 요약만, 원문 note 페이지는 조회 시 404) — [note roomliveman_k](https://note.com/roomliveman_k/n/n725392e4725a)
- V-Cut: "VTuber 切り抜き 자동 작성 소프트를 출시했다"는 pixivFANBOX 글. 기능, 가격, 날짜는 본문을 열지 못해 미확인(검색 요약은 2026-02 출시라고 함) — [sushino.fanbox.cc](https://sushino.fanbox.cc/posts/11418172)
- vibs.jp 블로그가 2026-04~08에 "VTuber 切り抜き AI 자동 생성", "무료 편집 도구 7선" 글을 냈으나 본문이 유료 응답(402)으로 막혀 미확인. 검색 요약은 "범용 도구 대부분은 VTuber 방송 특유의 채팅 열기를 분석하지 않는다"고 적었다 (판매자 자료로 보임) — [vibs.jp 2026-06-10](https://vibs.jp/blog/2026-06-10-2b513e1a), [vibs.jp 2026-08-05](https://vibs.jp/blog/2026-08-05-3bb1be0a)
- aipicks.jp는 AI가 음량이나 발화량으로 "열기"를 추정해 빗나가기 쉬우니 "자르고 싶은 유형을 먼저 말로 적어 넘기고", 후보를 많이 받아 사람이 고르라고 권한다. 출연자 목소리나 얼굴을 AI에 넣을 때는 본인 동의와 사무소 확인이 필수 (검색 요약만) — [aipicks.jp VTuber AI 활용 2026](https://aipicks.jp/mag/vtuber-ai-use-cases-2026)

**화면 위 흐르는 댓글(ニコニコ風)**
- Danmaku for YouTube, Flow YouTube Chat, SeikiSoViewer는 시청자 쪽에서 YouTube 채팅을 니코니코식으로 흘려 보여 주는 확장이다. SeikiSoViewer는 표시 위치, 속도 설정과 해당 장면으로 이동하는 시간 메모 기능이 있다. 切り抜き 영상에 흐르는 댓글을 구워 넣는 방법이나 관례는 검색되지 않았다 (검색 요약만) — [Danmaku for YouTube](https://chromewebstore.google.com/detail/danmaku-for-youtube/ogdgebockbglaopidjgfbffdfohdeadj), [smhn.info Flow YouTube Chat 2021](https://smhn.info/202103-how-to-use-flow-youtube-chat) (오래된 자료), [SeikiSoViewer](https://addons.mozilla.org/addon/seikisoviewer/)

### Inferences
- 일본 편집자의 탐색 단계는 "채팅 그래프를 보고 막대를 눌러 이동"하는 방식이 표준 UX가 되었다(CommentClip, Highlight Analyzer, 개인 확장 다수). stream2clip은 하이라이트를 자동으로 고르지만, 사람이 전체 방송의 그래프를 보고 직접 구간을 고르는 화면이 기능 목록에 없다. 자동 검출을 믿지 않는 편집자에게는 이 화면이 진입점이 된다.
- Highlight Analyzer의 "타임스탬프 목차"는 원본 방송 댓글란에 올리는 タイムスタンプ 문화와 연결된다. stream2clip은 이미 후보 구간과 대사를 갖고 있으므로 "타임스탬프 목차 텍스트 내보내기"는 비용이 아주 작다.
- 대행 상품이 VTuber에게 立ち絵 소재를 받는 점, YMM4의 표정 아이템 구조로 볼 때, "편집자 또는 탤런트의 立ち絵와 표정 차분을 츳코미 자막에 맞춰 바꾸는 층"은 일본 편집에서 익숙한 요소다. stream2clip의 아바타 상자는 방송 화면에서 잘라 오는 것이라 이 층과 다르다.
- 2026년 일본 AI 서비스(KIRARI, V-Choki)는 세로 Shorts 초안에 머물고, 가로 5~10분 모음, 화자 색, 기획사 가이드라인 점검은 보이지 않는다. 이 부분은 stream2clip이 앞선다.

### Gaps
- ホロジュール는 hololive 일정 사이트로 알려져 있으나 채팅 분석 기능이 있는지 확인하지 못했다. "Vchat"이라는 이름의 채팅 분석 도구는 찾지 못했다.
- ストクリ가 어떤 서비스인지(정식 이름, 운영사) 확인하지 못했다.
- Premiere Pro용 切り抜き 텔롭 mogrt 템플릿(縁取り, 화자 색)의 구체적 배포처는 찾지 못했다. 검색 결과는 CapCut의 일반 mogrt 안내뿐이었다.
- 切り抜き 영상에 니코니코식 흐르는 댓글을 넣는 관례가 있는지, 있다면 얼마나 쓰는지 근거를 찾지 못했다(앞 보고서 8절 미확인 사항 그대로).
- V-Cut, V-Choki의 실제 기능과 라이선스는 원문 미확인.

## 2. 한국: 버튜버 클립, 키리누키 편집자가 쓰는 도구와 한국 특유 요구

### Takeaway
한국 편집자는 Premiere Pro(레거시 타이틀 기반 예능 자막 프리셋)와 DaVinci Resolve(무료 예능 자막 프리셋), Vrew를 쓰고, 짤방, 그린스크린 효과, 효과음 사이트를 따로 찾아 붙인다. 2026년에는 CHZZK, SOOP 다시보기 채팅을 분석해 세로 숏폼 초안과 YouTube 다중 채널 업로드까지 해 주는 국내 서비스 Captus가 나왔다. stream2clip에 없는 것은 "스타일 프리셋(템플릿) 저장과 공유", "짤 이미지와 효과 오버레이 층", "방송 종료 후 자동 분석 루틴", "GIF/짤 내보내기"다.

### Cited Findings

**편집 도구와 예능 자막**
- 디시인사이드 버츄얼 스트리머 갤러리 장문 편집 가이드(2022-11-29, 오래된 자료): Premiere Pro 2019~2022 권장. 자막은 "텍스트"(기본)와 "레거시 타이틀"(디자인 자유도 높음) 두 종류이고 레거시 타이틀은 2022 이후 단종되어 2023부터 텍스트로 변환된다. 평소 대사는 텍스트, 감정이나 강조 대사는 레거시 타이틀. 효과와 자막 프리셋은 저장해 재사용하고, 무료 프리셋은 YouTube나 vidyssey.com에서 구한다 — [dcinside 1020458](https://gall.dcinside.com/mini/board/view/?id=virtual_streamer&no=1020458)
- 같은 글의 소재 출처: 이미지 pngtree, irasutoya, pixabay. 짤방은 jjalbang.today. 화면 효과는 "green screen", "chroma key"에 효과 이름을 붙여 검색(예: sakura greenscreen). 효과음 soundeffect-lab.info, sounds-resource.com. 음악 YouTube 오디오 보관함, NCS, 브금대통령, Incompetech. 일부 음원은 설명란 크레딧 링크 필요 — [dcinside 1020458](https://gall.dcinside.com/mini/board/view/?id=virtual_streamer&no=1020458)
- 같은 글의 작업 단계: 원본 받기 → 글꼴 선택 → 컷, 배치, 자막 → 음악, 효과음, 자막 효과 → 3회 교정, 다음 날 재검토("혼자 보면 안 보임"). 첫 10분 영상에 17시간 걸렸고 지금은 절반 이하. 원본 받기는 4K Downloader, 히토미 다운로더, youtube-dl — [dcinside 1020458](https://gall.dcinside.com/mini/board/view/?id=virtual_streamer&no=1020458)
- 루리웹: DaVinci Resolve 무료판으로 기능의 90%를 쓸 수 있고, 무료 프리셋으로 예능 자막 같은 형식과 효과를 쓸 수 있다는 반응. 자막은 말 시작과 끝 타이밍을 고려해 넣으라는 조언 (검색 요약만, 작성일 미확인) — [루리웹 56792930](https://bbs.ruliweb.com/etcs/board/300781/read/56792930), [루리웹 55185273](https://bbs.ruliweb.com/community/board/300143/read/55185273)
- 에펨코리아 입문 추천글은 "국내 예능처럼 편집해 놓아 처음 보는 사람이 보기 편한" 키리누키 채널을 추천한다 (검색 요약만) — [fmkorea 4366974892](https://www.fmkorea.com/4366974892)
- Vrew 공식 페이지: 음성 인식 자동 자막, 무음 구간 한 번에 줄이기, 디자인 자막 템플릿, 효과음 1000개, 100개 이상 언어 번역(원문과 번역 자막을 함께 표시), 기존 영상에서 재미있는 부분만 잘라 Shorts/TikTok 만들기. 화자 구분, 짤 스티커는 언급 없음 — [vrew.ai/ko](https://vrew.ai/ko/)
- Vrew 모바일 서비스는 2026-07-01 0시에 종료되었다(App Store 안내). Vrew 3.0은 2025-05 출시로 AI 기능이 늘었다 (검색 요약만) — [App Store Vrew](https://apps.apple.com/kr/app/vrew-%EB%B8%8C%EB%A3%A8/id1477811799), [ITmedia 2025-06-26](https://www.itmedia.co.jp/news/articles/2506/26/news115.html)
- 클리앙 사용기: Vrew 자동 자막 품질이 아직 부족하고 자막 프리셋이 적지만 Premiere 등으로 옮겨 고치기 쉽다(SRT 내보내기) (검색 요약만, 작성일 미확인) — [clien 13496596](https://www.clien.net/service/board/use/13496596)
- 한국어 AI 편집 도구 비교 글 대부분은 제품 홍보 블로그이고 수치가 서로 맞지 않는다. 예능 자막에 맞춰 짤과 효과음을 자동으로 고르는 기능은 검증된 근거가 없었다(Digen의 "지역 밈 추천" 주장은 독립 근거 없음) (검색 요약만) — [digen.ai 2026](https://resource.digen.ai/ai-dongyeongsang-jamag-cuga-bangbeob-2026/)

**CHZZK, SOOP 플랫폼 기능**
- CHZZK 클립은 2024-05 정식 출시 때 열렸고 구간과 레이아웃을 편집해 공유한다. 스트리머가 스튜디오 > 방송관리 > 방송하기에서 "클립 만들기"를 허용해야 시청자가 만들 수 있다 — [한국경제 2024-05-09](https://www.hankyung.com/article/202405096863Y), [네이트 뉴스 2024-05-09](https://news.nate.com/view/20240509n22637) (오래된 자료)
- 2024-12-23부터 CHZZK 클립이 네이버에 노출되고 클립 광고 수익을 스트리머가 정산, 이후 조회수 기반 "클립 광고 인센티브 프로그램" 정식 오픈 (검색 요약만) — [fmkorea 8780879390](https://www.fmkorea.com/8780879390)
- 나무위키 패치 내역: 클립 제작 쿨타임 삭제, 최대 길이 2분으로 증가, 생성 직후 URL/iframe 공유, 앱에서 다시보기로 클립 제작, 실시간/주간 인기 클립 (검색 요약만, 날짜 미표기) — [나무위키 치지직](https://namu.wiki/w/%EC%B9%98%EC%A7%80%EC%A7%81). 앞 보고서는 "CHZZK 클립 최대 1분"(etnews 2024-08-04)으로 적어 충돌한다. 공식 공지 확인 필요
- SOOP은 2024 말 로드맵에서 다시보기 하이라이트 생성 AI "SHARK"를 예고했으나 실제 출시는 확인하지 못했다. AI 매니저 "쌀사(SARSA)"는 2025-04 출시, 방송 설정, 연출, 채팅 관리, 방송 요약 — [테크M 2025 로드맵](https://www.techm.kr/news/articleView.html?idxno=133989), [뉴시스 2026-03-17](https://www.newsis.com/view/NISX20260316_0003550160)
- CHZZK는 2026 하반기 목표로 AI "라이브 매니저"(가칭)를, 2026-06 월드컵 전 목표로 스포츠 경기의 골, 수비, 함성을 감지해 하이라이트 클립을 자동 생성하는 "스포터(SPORTER)"를 개발 중이라고 보도됨. 자막 기능은 언급 없음 — [뉴시스 2026-03-17](https://www.newsis.com/view/NISX20260316_0003550160)

**국내 서드파티 서비스**
- Captus(captus.kr, © 2026): CHZZK, SOOP 다시보기 채팅을 분석("채팅이 몰린 곳이 곧 하이라이트"). 총 채팅, 분당 평균, 최고 반응 구간, 채팅 흐름 그래프. 점수(예: 92, 87, 81)와 타임스탬프, 제목이 붙은 구간 목록. 반응 구간마다 제목과 자막을 넣은 세로 숏폼 초안. 기본 템플릿 15개와 사용자 저장 템플릿(화면 배치와 자막 스타일). 자막과 캔버스를 고치는 타임라인 편집기, MP4 내보내기. CHZZK/SOOP 로그인 후 방송이 끝나면 자동 분석하는 루틴. YouTube 제목, 설명 자동 입력, 채널과 공개 범위를 골라 "여러 채널에 한 번에" 업로드. 무료 시작, 유료 요금 미표기. 대상은 스트리머 본인 — [captus.kr](https://captus.kr/)

### Inferences
- 한국 예능 자막은 "평소 대사 스타일 + 강조 대사 스타일"의 2단 구조가 기본이고(레거시 타이틀 분리), 편집자들은 프리셋을 저장해 돌려 쓴다. stream2clip에 화자 색과 강조 텔롭(앞 보고서 2순위)이 들어가면, 다음 단계는 이 스타일 묶음을 "프리셋 파일"로 저장, 가져오기, 공유하는 기능이다. Captus의 "기본 15개 + 사용자 저장 템플릿"이 같은 요구를 보여 준다.
- 짤방, 그린스크린 효과, 일러스트(irasutoya 등)를 붙이는 작업이 한국 키리누키의 수작업 비중이 큰 부분이다. stream2clip은 BGM/SFX 라이선스 추적을 갖고 있으므로, 같은 구조로 "이미지/짤/효과 소재 + 라이선스 표기"를 확장하는 것이 자연스럽다. 자동 선택은 근거가 약하므로 "자막 줄에 소재를 수동 지정하는 슬롯" 수준이 현실적이다.
- Captus는 스트리머 본인용이고 CHZZK/SOOP 로그인을 전제로 한다. 팬 편집자가 남의 방송을 다루는 경우, 기획사 가이드라인 점검, 가로 모음, 번역 자막은 Captus 페이지에 없다. stream2clip은 이 부분에서 차별되지만, "방송 종료 후 자동 분석"과 "여러 채널 업로드"는 Captus가 앞선다.
- 3회 교정 관행으로 보아, 업로드 전 자막 검수 목록(오탈자, 한 줄 길이, 초당 글자 수 초과, 화면 밖 넘침)을 자동 점검해 주는 기능이 편집자 시간을 줄인다.

### Gaps
- "브루"는 Vrew의 한국어 이름이다. 그 밖의 한국 전용 예능 자막 자동화 도구는 검증된 것을 찾지 못했다.
- 네이버 블로그, 티스토리의 2025~2026 버튜버 클립 편집 글은 이번 검색에 잡히지 않았다. 한국 자료 대부분이 2022년 전후 커뮤니티 글이다.
- CHZZK 클립 최대 길이(1분 또는 2분)는 공식 공지로 확인하지 못했다.
- SOOP SHARK의 실제 출시 여부와 범위, SOOP Catch 편집기 기능은 확인하지 못했다.
- CapCut의 한국어 예능 자막 템플릿 구성은 확인하지 못했다.

## 3. 중국: Bilibili 切片 자동화 생태계

### Takeaway
중국은 "녹화(录播姬, blrec, DDTV) → webhook → 탄막 ASS 변환(DanmakuFactory) → 压制(탄막 굽기) → 切片 → B站 업로드"가 도구 사슬로 굳어 있고, 2026년에는 탄막, 오디오, 음성, 추세 신호를 합치고 여러 사람이 검토하는 BiliLiveCut(MIT) 같은 도구가 더해졌다. 특히 LiveDanmaku는 YouTube 채팅을 탄막으로 구워 넣는 PySide6 GUI라서 stream2clip과 구조가 가장 비슷하다. stream2clip에 없는 핵심은 "탄막(채팅) 오버레이 굽기", "녹화기 webhook 연동", "여러 사람 검토 대기열", "B站 업로드"다.

### Cited Findings

**녹화와 탄막**
- 录播姬(BililiveRecorder)는 일반 탄막, SuperChat, 선물, 舰长 구매를 저장할 수 있다 — [录播姬 문서 弹幕录制](https://rec.danmuji.org/user/danmaku/)
- DanmakuFactory는 XML 탄막을 ASS로 바꾸고, v1.6x부터 录播姬의 선물, 舰长 구매, SuperChat 데이터 변환을 지원한다(대부분의 도구는 일반 탄막만 읽음) (검색 요약만) — [hihkm/DanmakuFactory](https://github.com/hihkm/DanmakuFactory)
- 压制는 ASS를 ffmpeg로 굽는 방식이 일반적이다(예: `ffmpeg -hwaccel cuda -i input.flv -vf ass=subtitle.ass -c:v libx264 -c:a copy -crf 18`). cuda 가속은 화질 손실이 있으나 빠르다. 분할 녹화 파일은 concat으로 먼저 합친다 (검색 요약만) — [bilibili opus 741395386519781417](https://www.bilibili.com/opus/741395386519781417), [vego6.cn](http://www.vego6.cn/%E5%88%A9%E7%94%A8-ffmpeg-%E5%8E%8B%E5%88%B6%E7%9B%B4%E6%92%AD%E5%BC%B9%E5%B9%95%E5%B0%8F%E8%AE%B0/)
- 녹화 프로그램의 타임스탬프와 탄막 서버 사이에 지연 차이가 있어 ffmpeg `-itsoffset`으로 미세 조정한다는 개인 경험담(미검증) (검색 요약만) — [vego6.cn](http://www.vego6.cn/%E5%88%A9%E7%94%A8-ffmpeg-%E5%8E%8B%E5%88%B6%E7%9B%B4%E6%92%AD%E5%BC%B9%E5%B9%95%E5%B0%8F%E8%AE%B0/)

**통합 도구**
- biliLive-tools(renmu123, GPL-3.0, 약 1.7k★): 斗鱼, 虎牙, B站, 抖音, 小红书, TikTok 녹화(FFmpeg, mesio, 录播姬 엔진). DanmakuFactory 기반 XML→ASS GUI, 녹화 파일 자동 탄막 压制, 일괄 压制, 변환, 합치기, FLV 수리. "탄막과 高能进度条(고에너지 진행 막대)로 빠르게 좋은 구간을 찾고 일괄 내보내기". LLM 기반 노래(翻唱) 분할과 가사 인식. B站 업로드, 클라우드 드라이브 동기화, 斗鱼/虎牙 녹화본 B站 자동 업로드. 录播姬, blrec, DDTV, oneliverec의 webhook으로 처리 시작 — [GitHub renmu123/biliLive-tools](https://github.com/renmu123/biliLive-tools), [docs.irenmu.com](https://docs.irenmu.com/)
- biliLive-tools2(포크로 보임): B站에서 舰长과 SC를 추가로 지원, 탄막과 高能进度条로 구간 찾기 (검색 요약만) — [1873452687/biliLive-tools2](https://github.com/1873452687/biliLive-tools2)
- BiliLiveCut(원본 StarGazerQQD/BiliLiveCut, MIT, v0.1.19.1 Alpha, main 650커밋, 포크 여럿): "녹화 → 전사 → 하이라이트 식별 → 사람 검토 → 切片과 문안 생성 → 선택적 업로드". ASR은 Fun-ASR-Nano, Paraformer, Whisper, 보조로 SenseVoice. 하이라이트는 "탄막, 오디오, 음성, 추세 신호" 융합. 수동 수정, 여러 사람 검토, 자막, 표지, 백그라운드 렌더, 작업 상태 저장. 기존 녹화본과 탄막 파일 가져오기. 기본은 수동 업로드 모드(업로드 재료만 생성). SC/선물 신호 언급 없음 — [Aethey/BiliLiveCut(포크)](https://github.com/Aethey/BiliLiveCut), [StarGazerQQD/BiliLiveCut](https://github.com/StarGazerQQD/BiliLiveCut)
- bilibili-live-replay: 노래 방송 주인용. 클라우드 자동 녹화와 비공개 업로드, Feishu(飞书)로 사람 검토, 자막, 곡 인식, 곡별 切片. Python 도구와 Agent 스킬 (검색 요약만) — [zhangdongming0607/bilibili-live-replay](https://github.com/zhangdongming0607/bilibili-live-replay)
- blive_Recorder: B站 탄막 포함 명령줄 녹화와 자동 업로드, ffmpeg 불필요. 작성자는 갱신 중단, AutoUpload_Blrec로 이동 (검색 요약만) — [qqyuanxinqq/blive_Recorder](https://github.com/qqyuanxinqq/blive_Recorder)
- ChopperBot: 虎牙, 斗鱼, 抖音, B站 대상 클립 생성과 게시 봇, 切片, 제목, 표지, 설명 자동 생성 (검색 요약만) — [isomd/ChopperBot](https://github.com/isomd/ChopperBot)
- 必剪: B站 공식 편집 앱, 게임 하이라이트 인식 기능 소개(이미 있는 녹화를 편집하는 도구). B站 공식 "라이브 하이라이트 자동 切片" 기능은 확인되지 않음 (검색 요약만) — [App Store 必剪](https://apps.apple.com/cn/app/1299589486)

**YouTube 채팅 탄막 도구 (stream2clip과 가장 닮은 사례)**
- LiveDanmaku(lilililinyuu, GPL-3.0, febr30th/DanmakuStudio 수정판, Python 3.12+, PySide6, 0★, 55커밋, © 2026): YouTube 방송 감시와 자동 녹화(`--live-from-start`), 녹화 중 끊지 않고 구간 저장, 녹화 후 전체 채팅 다시보기로 교체. yt-dlp 채팅 JSON → 탄막 XML. 高潮点 분석은 "앞뒤 구간보다 뚜렷이 빽빽하거나 전체 중앙값보다 뚜렷이 높은" 구간, 한 구간 최대 5분, 상위 N개. 탄막 스타일: 글꼴, 크기(기본 25pt), 글꼴 대체 목록(검색, 즐겨찾기), 글자 불투명도 0.7, 이모트 불투명도 1.0, 흐름 속도(px/s, 기본 300, 0~2000), 최대 줄 수, 최대 폭 비율, 위아래 여백, 멤버와 일반 사용자 스타일 분리. 실시간 미리보기, 실제 영상 프레임으로 PNG 미리보기, "테스트 구간만 내보내기". NVENC, QSV, CPU 자동 대체. `--download-sections`로 구간만 다운로드. GIF 변환(속도, fps, 해상도, 팔레트). SC 표시 언급 없음 — [GitHub lilililinyuu/LiveDanmaku](https://github.com/lilililinyuu/LiveDanmaku)

**자막(熟肉)과 권리**
- 중국 팬 자막 작업은 Aegisub(파형, 화면, 자막을 한 창에서 밀리초 단위 타이밍)가 고전이고, Arctime(쉬운 UI, 음성 인식 자동 타이밍), Subtitle Edit가 대안 (검색 요약만) — [少数派 47557](https://sspai.com/post/47557) (오래된 자료), [HackMD subtitle note](https://hackmd.io/@NC-vvs/subtitle-note)
- VTuber 切片의 "转熟"(옮겨 와서 번역 자막을 붙임)에 로컬 Whisper로 일본어를 인식해 SRT/ASS를 만드는 글, 사람 목소리를 먼저 분리한 뒤 인식하고 Aegisub로 타이밍을 맞추는 흐름 (검색 요약만) — [CSDN](https://bbs.csdn.net/weixin_29041195/article/details/100250085), [bilibili cv35618868](https://www.bilibili.com/read/cv35618868/)
- 切片 권리: 라이브 화면은 시청각 저작물이고 방송인의 초상과 목소리도 보호된다는 법률 해설. 서면 허가 없는 상업적 切片은 침해라는 주장(2026-10 기사) — [腾讯新闻 2026-10-11](https://news.qq.com/rain/a/20261011A077QL00?id=20261011A077QL00&path=a&app=news&suid=&redirect_pc=1)
- B站 등 크리에이터 센터에 "内容授权/二创授权" 입구가 있다는 설명, 일부 허가는 "자르고 자막 넣기는 되지만 말의 뜻을 바꾸면 안 됨", "오해를 부르는 자막 금지" 같은 경계를 둔다는 설명. 출처가 상업 홍보, 해설 글이라 품질이 낮다 (검색 요약만) — [知乎 1926389850736661715](https://zhuanlan.zhihu.com/p/1926389850736661715), [企鹊桥](https://www.qiqueqiao.com/blog/22630.html)
- 2026 판매자 대상 안내는 원본 녹화, 허가 계약서, 배포 기록을 보관해 신고에 대비하라고 권한다(전자상거래 切片 맥락이라 B站 VTuber 切片에 그대로 적용되지는 않음) (검색 요약만) — [shangjiazhushou.com](https://shangjiazhushou.com/article/23972839-2669)

### Inferences
- 중국 생태계에서 stream2clip이 가져올 만한 것은 업로드 자동화보다 **탄막 굽기의 설정 항목**이다. LiveDanmaku의 설정(속도, 줄 수, 폭 비율, 여백, 멤버 스타일, 실제 프레임 미리보기, 테스트 구간 내보내기)은 그대로 기능 명세로 쓸 수 있다. 다만 LiveDanmaku와 biliLive-tools는 GPL-3.0이므로 코드는 가져오지 말고 설정 항목만 참고해야 한다. DanmakuFactory는 외부 프로세스로 쓰는 편이 안전하다(라이선스는 이번에 확인하지 못함).
- SC, 선물, 舰长을 탄막 ASS에서 따로 그리는 기능(DanmakuFactory 1.6x)은 stream2clip의 슈퍼챗 신호와 연결된다. 슈퍼챗을 "검출 신호"로만 쓰지 말고 "화면에 카드로 표시"하는 용도가 있다.
- "녹화기 webhook → 처리 시작" 구조(biliLive-tools)는 이미 录播姬, blrec, DDTV, ytarchive를 쓰는 사용자를 끌어올 수 있다. stream2clip이 직접 녹화를 만들기보다 "폴더 감시 또는 webhook 수신 → 자동 분석"을 두는 편이 작다.
- 여러 사람 검토(BiliLiveCut), 飞书 검토(bilibili-live-replay), 승인/거절(cliptrans)은 모두 "후보 → 사람 확인 → 렌더" 단계를 상태로 저장한다. 팀으로 운영하는 클립 채널에는 후보 목록을 파일로 내보내고 다시 들여오는 수준만으로도 쓸모가 있다.
- B站 업로드는 중국어권 사용자에게만 의미가 있고, biliup이 이미 하므로 직접 만들기보다 biliup CLI 호출 플러그인이 맞다.

### Gaps
- DDTV, blrec의 2026년 切片 기능 여부는 확인하지 못했다.
- B站 "高能进度条"의 데이터를 외부 도구가 어떻게 받는지(API 엔드포인트, 공개 여부)는 확인하지 못했다.
- "切片man" 전용 규범이나 B站 공식 VTuber 切片 규정 원문은 찾지 못했다.
- DanmakuFactory의 라이선스는 이번에 확인하지 못했다.
- 중일 이중 자막(熟肉)의 표준 배치 규칙(위아래 순서, 글꼴 크기 비율)은 찾지 못했다.

## 4. VTuber 전용 도구 (지역 무관): 채팅 오버레이, Live2D 표정, 번역 커뮤니티, 클립 채널 등록

### Takeaway
채팅을 영상에 그려 넣는 도구는 Twitch 쪽(TwitchDownloader, MIT)만 성숙했고, YouTube 채팅을 파일로 렌더하는 오픈소스는 LiveDanmaku(탄막식, GPL) 외에 찾지 못했다. 번역 클립 작업은 "보기 → 자르기 → 번역 → 타이밍과 조판 → 썸네일, 업로드"로 나뉘고, 번역 자체는 줄지 않는다는 것이 2026년 업계 글의 결론이다. 기획사 등록은 にじさんじ처럼 필수인 곳이 있고, 중국은 二创授权 입구를 쓴다.

### Cited Findings

**채팅 오버레이 렌더**
- TwitchDownloader(MIT): 채팅을 JSON, HTML, TXT로 받고, JSON에서 채팅 렌더 영상을 만든다. BTTV, FFZ, 7TV 정적·움직이는 이모트, Twemoji 또는 Noto Color 이모지, 폭과 높이(예: `-w 422 -h 1080`), `--framerate 30`, `--update-rate 0`, `--font-size 18`. Twitch만 지원 — [GitHub lay295/TwitchDownloader](https://github.com/lay295/TwitchDownloader)
- Twitch Videochat(Tailszefox)은 VOD 옆에 채팅 다시보기를 실시간으로 붙여 한 파일로 합친다. TwitchChatVideo(cairthenn)는 채팅 다시보기 영상을 만들지만 긴 영상은 오래 걸린다. 둘 다 Twitch 전용 (검색 요약만) — [Tailszefox/twitch_videochat](https://github.com/Tailszefox/twitch_videochat), [cairthenn/TwitchChatVideo](https://www.github.com/cairthenn/TwitchChatVideo)
- mpv-youtube-chat은 yt-dlp `live_chat.json`을 받아 재생 중에만 겹쳐 보여 주고 파일로 렌더하지 않는다. YT-Live-Chat-Replayer는 JSON으로 채팅을 다시 보여 주는 GUI이고 렌더러가 아니다 (검색 요약만) — [mpv-youtube-chat](https://awesome.ecosyste.ms/projects/github.com%2Fbanchouboo%2Fmpv-youtube-chat), [AntonisTorb/YT-Live-Chat-Replayer](https://github.com/AntonisTorb/YT-Live-Chat-Replayer)
- 라이브용 OBS 채팅 오버레이(aaronpk/live-chat-overlay, mmlTools OBS Lua 스크립트)는 방송 중 표시용이다 (검색 요약만) — [aaronpk/live-chat-overlay](https://www.github.com/aaronpk/live-chat-overlay), [mmlTools](https://github.com/mmlTools/youtube-live-chat-overlay-script-obs-studio)

**번역 클립 작업 흐름**
- AutoClip(autoclip.dev, 판매자 자료, 2026-04-26 작성, 2026-11-16 갱신): 4~8시간 아카이브는 1.5배속으로도 3~5시간을 봐야 하고, 자동화는 이를 순위 목록으로 바꾼다. 자르기 약 10분, 타이밍, 조판, 세로 구도, 썸네일, 업로드, 설명란에 1~2시간. "번역은 줄지 않고 줄어서도 안 된다". 일본어 자동 자막은 영어보다 눈에 띄게 약하고, 기계 번역은 시청자가 바로 알아챈다. 화면 "고유화"(미세 변형)는 허가가 되지 않고 수동 신고를 막지 못하며 화질만 떨어뜨린다. 요금제별 원본 길이 한도 2/5/10시간 — [AutoClip 번역 작업 흐름](https://autoclip.dev/blog/vtuber-clip-channel-translation-workflow)
- cliptrans(gaato, AGPL-3.0-or-later, 2026-10-23 보관 처리, 0★): Holodex API 키로 방송 목록 탐색, yt-dlp, ffmpeg, faster-whisper, LLM 번역. `glossary.toml`에 **ASR 결과의 고유명사 교정**과 번역 용어를 함께 둔다. SRT, VTT, ASS 내보내기. 자막에서 클립 후보를 뽑아 저장, 승인, 거절 — [GitHub gaato/cliptrans](https://github.com/gaato/cliptrans)
- Holodex-Plus 확장 변경 기록에 Holodex v3용 "TLDex Relay", "TL Client"가 있다(라이브 번역 중계). 클립 번역 작업용 기능 설명은 없음 (검색 요약만) — [Holodex-Plus CHANGELOG](https://github-redirect.dependabot.com/XangelMusic/Holodex-Plus/blob/dev/CHANGELOG.md)

**Live2D, 立ち絵 표정 오버레이**
- 클립 편집 쪽의 표정 차분 오버레이는 YMM4 표정 아이템, PSDToolKit(AviUtl2 대응) 같은 일본 편집기 기능으로 처리된다(1절 참고). 클립 편집기에 Live2D 모델을 직접 불러와 표정을 바꾸는 전용 도구는 이번 조사에서 찾지 못했다 — [Bluemist, note](https://note.com/bluemist/n/n03b9a08695a7), [vip-jikkyo.net](https://vip-jikkyo.net/aviutl2-guide)

**클립 채널 허가, 등록 흐름**
- KIRARI 가이드: 사전에 기획사 가이드라인 확인, にじさんじ는 "등록 양식 신청이 필수"이고 미등록 게시는 규약 위반, 설명란에 원본 URL, 제목, 채널 표기는 거의 모든 기획사 조건, 주 2~3개 게시 권장 — [KIRARI](https://www.kirari.io/blog/vtuber-clip-guide)
- 중국은 크리에이터 센터의 二创授权 입구나 방송인 운영팀, MCN을 통한 허가가 언급된다(근거 약함, 3절) — [知乎](https://zhuanlan.zhihu.com/p/1926389850736661715)

### Inferences
- YouTube 채팅을 파일로 렌더하는 MIT/Apache 오픈소스가 없다는 점은 stream2clip이 채울 수 있는 빈칸이다. stream2clip은 이미 채팅 JSON과 ASS 렌더 경로(karaoke 자막)를 갖고 있으므로, "옆 패널형 채팅(TwitchDownloader식, 가로 클립용)"과 "흐르는 탄막(B站식)" 두 모드를 ASS로 생성하는 것이 비용 대비 효과가 크다. 멤버 배지, 슈퍼챗 색 카드, 이모트는 YouTube 채팅 데이터에 들어 있다.
- cliptrans의 "ASR 고유명사 교정 용어집"은 stream2clip 번역 용어집을 전사 단계로 넓히는 아이디어다(예: faster-whisper의 initial prompt나 hotwords에 탤런트 이름 넣기, 전사 후 치환). cliptrans는 AGPL이므로 아이디어만 쓴다.
- AutoClip 글의 시간 배분대로라면 번역 클립 채널의 병목은 "보기"와 "번역, 조판"이다. stream2clip의 하이라이트 검출이 "보기"를 줄이고, 원문 자막 위에 번역을 덮어쓰는 편집 화면(단어 단위 타이밍 유지)이 "조판"을 줄인다.
- 기획사 등록 상태와 허가 번호, 허가 증빙(캡처, 메일)을 탤런트별로 저장하는 기록부는 일본(にじさんじ 등록), 한국(스텔라이브 설문), 중국(二创授权) 모두에 공통으로 쓸 수 있다.

### Gaps
- Holodex 웹의 클립 제출, 번역 언어 필터, TLdex 기능의 공식 문서를 이번에 확인하지 못했다(앞 보고서의 Holodex API 내용만 유효).
- 번역 커뮤니티(영어 hololive 클리퍼)가 2026년에 쓰는 조판 도구(Aegisub 외)의 실제 비율은 찾지 못했다.
- 클립 영상에 채팅 오버레이를 넣는 비율이 일본, 한국에서 어느 정도인지 근거가 없다.

## 5. stream2clip 사용자에게 가장 도움이 될 기능

### Takeaway
근거와 구현 비용을 함께 보면, (1) 채팅 그래프 탐색 화면과 타임스탬프 목차 내보내기, (2) 채팅/탄막 오버레이 굽기(옆 패널, 흐르는 탄막, 슈퍼챗 카드), (3) 자막 스타일 프리셋 저장과 공유(예능 자막, 텔롭 2단 구조), (4) 녹화기 webhook과 폴더 감시에 의한 방송 후 자동 분석, (5) 전사 단계 고유명사 용어집이 가장 효과가 크다. 짤과 立ち絵 표정 층, 검토 대기열, GIF 내보내기, B站 업로드는 그 다음이다.

### Cited Findings
- 채팅 그래프와 클릭 이동이 일본, 한국 도구의 공통 화면: CommentClip(30초 막대, 클릭 이동) — [comment-clip.com](https://comment-clip.com/); Captus(채팅 흐름 그래프, 점수 구간 목록) — [captus.kr](https://captus.kr/); Highlight Analyzer(그래프와 타임스탬프 목차) — [Chrome 웹스토어](https://chromewebstore.google.com/detail/highlight-analyzeryoutube/pcicbonbpknjgpmofodbaiiljfhdbpok?hl=ja)
- 탄막 굽기 설정 항목의 구체 예: LiveDanmaku — [GitHub](https://github.com/lilililinyuu/LiveDanmaku); SC, 선물, 舰长 ASS 변환: DanmakuFactory — [GitHub](https://github.com/hihkm/DanmakuFactory); 녹화 자동 压制: biliLive-tools — [GitHub](https://github.com/renmu123/biliLive-tools)
- 스타일 프리셋 수요: Captus 기본 15개 + 사용자 템플릿 — [captus.kr](https://captus.kr/); Premiere 프리셋 저장, 재사용 관행 — [dcinside 1020458](https://gall.dcinside.com/mini/board/view/?id=virtual_streamer&no=1020458); Vrew 디자인 자막 템플릿 — [vrew.ai/ko](https://vrew.ai/ko/)
- 방송 후 자동 처리: Captus 자동 분석 루틴 — [captus.kr](https://captus.kr/); 录播姬/blrec/DDTV webhook — [biliLive-tools](https://github.com/renmu123/biliLive-tools); LiveDanmaku 채널 감시와 자동 녹화 — [GitHub](https://github.com/lilililinyuu/LiveDanmaku)
- ASR 고유명사 교정 용어집 — [cliptrans](https://github.com/gaato/cliptrans)
- 여러 사람 검토: BiliLiveCut — [GitHub](https://github.com/Aethey/BiliLiveCut); 승인/거절: cliptrans — [GitHub](https://github.com/gaato/cliptrans)
- 사람 목소리 분리 후 전사 — [bilibili cv35618868](https://www.bilibili.com/read/cv35618868/) (검색 요약만)
- GIF 변환 — [LiveDanmaku](https://github.com/lilililinyuu/LiveDanmaku); 짤방 소재 사용 관행 — [dcinside 1020458](https://gall.dcinside.com/mini/board/view/?id=virtual_streamer&no=1020458)
- 여러 YouTube 채널 동시 업로드 — [captus.kr](https://captus.kr/)
- 노래 곡별 분할과 가사 인식: biliLive-tools LLM 翻唱 분할 — [GitHub](https://github.com/renmu123/biliLive-tools); bilibili-live-replay 곡 인식, 곡별 切片 (검색 요약만) — [GitHub](https://github.com/zhangdongming0607/bilibili-live-replay)

### Inferences

stream2clip에 없는 기능 목록(조정자가 준 현재 기능 목록 기준. 이미 일부 있으면 해당 항목은 확장 과제로 본다):

| 순위 | 기능 | 구체 내용 | 근거 지역 | 비용 감각 | 라이선스 주의 |
|:---:|---|---|---|---|---|
| 1 | 채팅 그래프 탐색 화면 | 전체 방송의 채팅량, 반응어(草, ㅋㅋ), 슈퍼챗, heatmap 곡선을 겹친 타임라인. 클릭하면 미리보기 이동, 드래그로 구간 지정, 자동 후보를 그래프 위 표시 | 일본(CommentClip, Highlight Analyzer), 한국(Captus) | 중. 신호 데이터는 이미 있음 | 없음 |
| 1 | 타임스탬프 목차 내보내기 | 후보 구간과 대표 대사로 `00:12:34 ○○` 형식 텍스트 생성(원본 방송 댓글, 모음 영상 챕터용) | 일본(Highlight Analyzer) | 소 | 없음 |
| 1 | 채팅 오버레이 굽기 | 모드 2개: 옆 패널형(이름 색, 멤버 배지, 이모지, 가로 클립용), 흐르는 탄막형(속도, 최대 줄 수, 폭 비율, 여백, 불투명도). 슈퍼챗/멤버 가입 카드. 실제 프레임 미리보기와 테스트 구간 렌더. 반응 구간에만 켜기 옵션 | 중국(LiveDanmaku, DanmakuFactory, biliLive-tools), 글로벌(TwitchDownloader) | 중. ASS 생성으로 가능 | LiveDanmaku, biliLive-tools는 GPL. 설정 항목만 참고 |
| 1 | 자막 스타일 프리셋 | 평소 대사, 강조(감정) 대사, 츳코미, 상황 설명의 스타일 묶음을 파일로 저장, 가져오기, 공유. 일본 텔롭, 한국 예능 자막 기본 프리셋 동봉 | 한국(레거시 타이틀 2단 구조, 프리셋 공유), 한국(Captus 템플릿), Vrew | 소~중 | 글꼴 재배포 라이선스 확인 |
| 2 | 방송 후 자동 분석 | 폴더 감시(ytarchive, 录播姬 출력 폴더) 또는 녹화기 webhook 수신 → 채팅 확보 → 후보 생성 → 알림. 사람 확인 후 렌더 | 한국(Captus), 중국(biliLive-tools, biliup) | 중 | 녹화기는 외부 프로세스 |
| 2 | 전사용 고유명사 용어집 | 번역 용어집을 전사 단계로 확장. 탤런트 이름, 고정 밈을 ASR 힌트와 전사 후 치환에 사용 | 글로벌(cliptrans) | 소 | cliptrans AGPL, 아이디어만 |
| 2 | 짤, 이미지, 효과 소재 층 | 자막 줄에 반응 이미지, 그린스크린 효과, 일러스트를 붙이는 슬롯. BGM/SFX처럼 소재 라이선스와 크레딧 기록 | 한국(짤방, irasutoya, 그린스크린) | 중 | 소재별 이용 약관 |
| 2 | 立ち絵, 표정 차분 층 | 편집자 또는 탤런트가 제공한 立ち絵(PNG 차분 또는 PSD 레이어)를 츳코미 자막, 감정 태그에 맞춰 전환 | 일본(YMM4 표정 아이템, PSDToolKit, 대행 상품의 立ち絵 제공) | 중 | 立ち絵 소재 약관 |
| 2 | 업로드 전 자막 검수 | 한 줄 글자 수, 초당 글자 수, 화면 밖 넘침, 용어집 불일치, 맞춤법 후보 목록 | 한국(3회 교정 관행), 일본(세로 텔롭 8~10자 규칙, 앞 보고서) | 소 | 없음 |
| 3 | 후보 검토 대기열 | 후보 목록을 파일로 내보내고 승인/거절/메모를 다시 들여오기. 여러 사람이 나눠 검토 | 중국(BiliLiveCut, 飞书 검토), 글로벌(cliptrans) | 소~중 | 없음 |
| 3 | 사람 목소리 분리 후 전사 | 게임 BGM이 큰 방송에서 선택 설치형 분리(python-audio-separator 등) 후 faster-whisper | 중국(转熟 흐름) | 소. 선택 설치 | 앞 보고서의 MIT 후보 사용 |
| 3 | GIF/짧은 반복 영상 내보내기 | 3~6초 구간을 GIF/WebP로(커뮤니티 짤, X 게시용) | 한국(짤 문화), 중국(LiveDanmaku GIF) | 소 | 없음 |
| 3 | 원문과 번역 이중 자막 | 한 화면에 원문(작게)과 번역(크게) 두 줄, 위치와 크기 비율 설정 | Vrew 원문+번역 동시 표시, 중국 熟肉 | 소 | 없음 |
| 3 | 여러 채널, 다른 플랫폼 업로드 | YouTube 다중 채널 선택, B站은 biliup CLI 플러그인 | 한국(Captus), 중국(biliup) | 중 | biliup MIT |
| 3 | 허가 기록부 | 탤런트별 등록 상태, 허가 번호, 허가 증빙 파일 경로와 날짜 저장. 기존 기획사 프로필과 연결 | 일본(にじさんじ 등록 필수), 중국(二创授权) | 소 | 없음 |
| 제외 | 노래 곡별 切片 | 중국에서 흔하지만 곡 저작권 위험이 커서 기존 노래 제외 방침 유지. 본인 채널용 챕터 표시 정도만 | 중국(biliLive-tools, bilibili-live-replay) | - | 곡 저작권 |
| 제외 | 화면 미세 변형(고유화) | 허가가 되지 않고 신고를 막지 못한다는 업계 설명 | 글로벌(AutoClip) | - | - |

- 1순위 네 항목은 stream2clip이 이미 가진 데이터(채팅 JSON, 신호 곡선, ASS 렌더, 대사 전사)를 화면과 출력으로 바꾸는 일이라 새 의존성이 거의 없다.
- 채팅 오버레이는 일본, 한국 관례 근거가 약하므로(1절, 4절 Gaps) 기본값은 끄고, 중국어권과 영어 번역 클립 사용자를 위한 선택 기능으로 두는 편이 맞다.
- 자동 업로드는 중국 도구도 기본을 "수동 업로드 재료만 생성"으로 둔다(BiliLiveCut). stream2clip의 기존 YouTube 업로드도 사람 확인을 기본으로 유지하는 것이 맞다.

### Gaps
- stream2clip에 이미 채팅 그래프 화면, 이중 자막, 프리셋 저장이 일부 있는지는 이 조사 범위(외부 도구 조사)에서 코드로 확인하지 않았다. 보고서 작성 시 저장소와 대조해야 한다.
- 각 기능의 실제 사용자 수요(설문, 요청 수)는 근거가 없다. 순위는 여러 지역 도구에 같은 기능이 나타나는 빈도와 구현 비용으로만 정했다.
