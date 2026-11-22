# 클립 특수효과용 무료 에셋, 폰트의 라이선스와 효과를 제한하는 기획사·플랫폼 규칙

조사일 2026-11-22. 아래 "확인"은 모두 2026-11-22에 공식 페이지(또는 명시한 2차 자료)를 직접 열어 본 결과. 인용은 원문 그대로이며 짧게 줄였음. 법적 판단이 아니라 stream2clip 라이선스 표와 업로드 전 점검을 만들기 위한 자료. 기존 `reports/무료 BGM 효과음 레퍼런스.md`와 같은 기준(수익 창출 영상, 크레디트, 앱·저장소 동봉, 자동 내려받기, 공식 원문 주소와 날짜)으로 정리.

## 1. 이모지 세트 (Noto Color Emoji, Twemoji, OpenMoji, Fluent Emoji, JoyPixels/Apple): 재배포와 크레디트

### Takeaway
동봉(설치 프로그램, 저장소)에 가장 안전한 것은 Fluent Emoji(MIT)와 Noto Emoji(폰트 OFL 1.1, 이미지 Apache 2.0)이며 영상 크레디트도 사실상 불필요. Twemoji 그래픽은 CC BY 4.0이라 영상마다 크레디트가 필요하고, OpenMoji는 CC BY-SA 4.0이라 수정(외곽선, 색 변경) 시 동일 라이선스 조건이 붙으므로 기본 동봉에서 제외하고 사용자 추가 에셋으로만 다루는 편이 안전.

### Cited Findings

| 세트 | 라이선스(원문) | 크레디트 | 동봉 | 저장소 최근 push | 공식 원문 |
|:---:|---|---|---|---|---|
| Noto Emoji (Google) | 폰트: "Emoji fonts (under the fonts subdirectory) are under the SIL Open Font License, version 1.1." / "Tools and most image resources are under the Apache license, version 2.0." / 국기: "in the public domain or otherwise exempt from copyright" | OFL·Apache 모두 영상 크레디트 요구 조항 없음(배포 시 고지 유지) | 가능. OFL은 사본에 "contain the above copyright notice and this license" | 2026-10-26 | [README](https://raw.githubusercontent.com/googlefonts/noto-emoji/main/README.md), [LICENSE](https://github.com/googlefonts/noto-emoji/blob/main/LICENSE) |
| Twemoji (jdecked 포크, v17.0 / Unicode 17.0, CDN 17.0.3) | "Graphics licensed under CC-BY 4.0" / "Code licensed under the MIT License" | 필요. README: "will accept a mention in a project README or an 'About' section or footer on a website" | 가능(CC BY 4.0 고지 유지) | 2026-06-01 | [github.com/jdecked/twemoji](https://github.com/jdecked/twemoji) |
| OpenMoji | "Creative Commons Share Alike License 4.0 (CC BY-SA 4.0)" | 필수. 권장 문구 "All emojis designed by OpenMoji – the open-source emoji and icon project. License: CC BY-SA 4.0". 영상은 설명란, 엔딩 크레디트, 첫 등장 시 작은 각주 | 가능하나 SA 조건 유지 필요 | 2026-11-04 (GitHub API spdx_id `CC-BY-SA-4.0`) | [openmoji.org/faq](https://openmoji.org/faq/) |
| Fluent Emoji (Microsoft) | MIT, "Copyright (c) Microsoft Corporation." | 영상 크레디트 불필요(MIT는 사본에 고지 포함만 요구) | 가능. "shall be included in all copies or substantial portions of the Software" | 2026-08-24 | [LICENSE](https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/LICENSE) |

- Noto Emoji README는 PNG/SVG에 별도 라이선스를 적지 않고 "most image resources"만 Apache 2.0이라고 함. 어떤 이미지가 예외인지 명시 없음(국기만 명시된 예외) — [Noto Emoji README](https://raw.githubusercontent.com/googlefonts/noto-emoji/main/README.md)
- Noto 국기 PNG는 "transforms have been applied to standardize the size"이며 그에 맞는 SVG는 없음 — [Noto Emoji README](https://raw.githubusercontent.com/googlefonts/noto-emoji/main/README.md)
- Noto 폰트 LICENSE의 저작권 줄은 "Copyright 2013 Google LLC." — [LICENSE](https://github.com/googlefonts/noto-emoji/blob/main/LICENSE)
- Twemoji는 고정 크레디트 문구를 주지 않으며 CC의 모범 사례 안내를 "a bit onerous"라고 표현. HTML/JS 소스 내 언급도 충분하다고 봄(웹 기준 안내만 있고 영상 기준 안내는 없음) — [jdecked/twemoji](https://github.com/jdecked/twemoji)
- Twemoji 그래픽 라이선스 파일은 CC "Attribution 4.0 International" 전문 — [LICENSE-GRAPHICS](https://raw.githubusercontent.com/jdecked/twemoji/main/LICENSE-GRAPHICS)
- OpenMoji: 상업적 이용 가능("for any purpose, even commercially"), 리믹스·변형 시 "under the same license CC BY-SA 4.0 as OpenMoji"로 배포해야 함. 컬러폰트판은 "very early alpha stage and not intended to use in production!" — [openmoji.org/faq](https://openmoji.org/faq/)
- OpenMoji 크레디트는 OpenMoji 프로젝트가 보증하는 듯한 표현 금지("not in any way that suggests the OpenMoji Project endorses you") — [openmoji.org/faq](https://openmoji.org/faq/)
- Fluent Emoji 저장소는 이모지마다 `3D`, `Color`, `Flat` 등 폴더를 둠(예: `assets/Grinning face/3D`). README 페이지에 상표·사용 제한 언급 없음 — [GitHub API contents](https://api.github.com/repos/microsoft/fluentui-emoji/contents/assets/Grinning%20face), [github.com/microsoft/fluentui-emoji](https://github.com/microsoft/fluentui-emoji)

### Inferences
- 기본 동봉 후보: Fluent Emoji(MIT, 크레디트 불필요, 3D 스타일이 예능 자막과 잘 맞음)와 Noto Emoji 이미지(Apache 2.0). Apache 2.0은 재배포 시 라이선스 사본과 NOTICE 유지가 조건이므로 설치 프로그램에 `LICENSE` 파일을 함께 넣어야 함(Apache 2.0 본문은 이번에 열지 않음, 일반 조건으로 기재).
- Twemoji를 쓰면 CC BY 4.0이므로 영상 설명란에 크레디트가 필요하다고 보고 점검에서 "크레디트 필요"로 처리. 권장 문구 예: "Twemoji (CC BY 4.0, github.com/jdecked/twemoji)". 저작권자 표기 문구(예: Twitter, Inc and other contributors)는 이번에 확인하지 못함.
- OpenMoji는 SA 때문에 (1) 동봉 시 MIT로 재라이선스할 수 없어 별도 라이선스 파일 필요, (2) 외곽선·색 변경 같은 수정은 "변경 저작물"이 되어 CC BY-SA 조건이 따라옴. 클립 영상 전체가 SA 대상이 되는지는 CC 4.0의 "Adapted Material" 해석에 달려 있어 모호. 점검에서 "SA, 크레디트 필수, 수정 시 주의" 경고 권장.
- 라이선스 키 제안: `fluent-emoji-mit`, `noto-emoji-apache-2.0`, `noto-emoji-font-ofl-1.1`, `twemoji-cc-by-4.0`, `openmoji-cc-by-sa-4.0`.

### Gaps
- JoyPixels, Apple Color Emoji의 약관은 이번 세션에서 열지 않음. 일반적으로 무료 재배포 라이선스가 없는 것으로 알려져 있으나 원문 확인 전이므로 "허용하지 않음"은 미확인 상태로 표기 필요.
- Fluent Emoji의 움직이는(animated) 버전이 저장소에 있는지, 같은 MIT 적용인지 확인하지 못함(저장소 목록에서 3D/Color/Flat만 확인).
- Twemoji 그래픽의 정확한 저작권자 줄, Noto Emoji 이미지 중 Apache 예외 대상.

## 2. 일본 무료 소재와 해외 동영상 소재 사이트 (いらすとや, 集中線, ニコニ・コモンズ, Pixabay, Mixkit, Videvo, Pexels, 그린스크린 팩)

### Takeaway
모든 사이트가 "영상 속 사용"은 대체로 허용하지만 "소재 파일 자체의 재배포·앱 수록"은 거의 모두 금지 또는 모호. いらすとや는 영상 1개(썸네일 포함) 20점 제한과 "画像編集アプリの素材として収録" 금지가 핵심이고, Videvo는 Freepik(현재 magnific.com 약관)으로 흡수되어 무료 사용 시 출처 표기 필수 및 AI 목적 사용 금지로 바뀜. 따라서 오버레이 영상은 (a) 코드 생성 또는 (b) 사용자 직접 추가로 처리하고 동봉은 하지 않는 것이 BGM 때와 같은 결론.

### Cited Findings

| 출처 | 수익 창출 영상 | 크레디트 | 앱·저장소 동봉 | 자동 내려받기 | 기타 | 공식 원문(확인일 2026-11-22) |
|:---:|---|---|---|---|---|---|
| いらすとや | 상업 이용은 "一つの作成物の中に20点まで" 무료. YouTube는 "一つの動画にサムネイルを含め20点以内" | 불필요("必要ありません") | 불가: "画像編集アプリの素材として収録することもできません", "素材の再配布はお断り" | 미기재 | 21점 이상은 "一点につき1,100円（税込）", 합계 점수 기준 | [irasutoya.com/p/faq.html](https://www.irasutoya.com/p/faq.html) |
| Pixabay (영상 포함) | 가능 | 불필요 | 불가(단독 배포 금지) | 금지: "Bulk, large-scale or systematic copying of Content is strictly prohibited" | 약관 "Last updated: 20 October, 2026" | [pixabay.com/service/terms](https://pixabay.com/service/terms/) |
| Mixkit Stock Video Free | 가능("YouTube videos", "Commercial projects") | 불필요("Attribution is not required") | 모호(아래) | 금지: User Terms 9.10 "use scripts or bots to mass download Items" | User Terms "Last revised: October 2, 2025" | [mixkit.co/license](https://mixkit.co/license/) (모달 `/license/modal/videoFree/`), [mixkit.co/terms](https://mixkit.co/terms/) |
| Pexels | 가능(광고, 판매 템플릿까지 예시) | 불필요("Attribution is not required.") | 모호: "Don't redistribute or sell the photos and videos on other stock photo or wallpaper platforms" | 미기재(라이선스 페이지) | 무수정 판매 금지 | [pexels.com/license](https://www.pexels.com/license/) |
| Videvo → Freepik → Magnific | 무료 사용은 출처 표기 조건부 | 필수(무료 사용자) | 불가: "database, archive" 수록 금지 | 금지(robots, spiders) | AI 목적 사용 금지. 약관 November 2026 | [magnific.com/legal/terms-of-use](https://www.magnific.com/legal/terms-of-use) |
| Mirin's Stock Footage (miirriin, 集中線 그린백·알파·흑배경판) | 가능("free for commercial and non-commercial purposes") | 불필요("attribution is not required") | 불가: "Post the files on any website for others to download or copy", "Give away as part of any other collection of media" | 금지(data mining, robots) | "Use for AI training" 금지. 약관 2025/10/1 | [miirriin.com/en/terms-conditions](https://miirriin.com/en/terms-conditions/), [소재 페이지](https://miirriin.com/?p=5719) |

- いらすとや: 영상은 "1映像ではなく1商品（1番組）につき20点まで". 수익 창출이 없는 공공·비영리 개인 영상은 21점 이상 가능. "広告掲載に限らず利益が発生するものは商用利用" — [いらすとや FAQ](https://www.irasutoya.com/p/faq.html)
- いらすとや: 가공은 "元の素材のイメージを保ったもの"면 가능, "いらすとやのものと分からなくするための加工"은 불가. AI 관련 규정은 FAQ 페이지에 없음. 페이지에 개정일 표시 없음 — [いらすとや FAQ](https://www.irasutoya.com/p/faq.html)
- いらすとや: 앱은 광고나 과금이 있으면 상업 이용, "「課金をすることでイラストやキャラクターが手に入る」といった形ではご利用できません" — [いらすとや FAQ](https://www.irasutoya.com/p/faq.html)
- Pixabay "Standalone"은 "no creative effort has been applied to the Content"이고 필터, 색 변경, 크기 조정, 자르기만 한 것도 Standalone. 다른 요소와 결합한 새 창작물은 Standalone 아님 — [Pixabay Terms](https://pixabay.com/service/terms/)
- Pixabay: 영상 오버레이나 앱·소프트웨어 수록은 Content License 절에 언급 없음. 데이터 마이닝·스크래핑은 "including without limitation for machine learning purposes" 금지 — [Pixabay Terms](https://pixabay.com/service/terms/)
- Pixabay 요약 페이지: "You cannot sell or distribute Content ... on a Standalone basis", 오해를 부르는 사용 금지 — [Pixabay License Summary](https://pixabay.com/service/license-summary/)
- Mixkit Stock Video Free License 모달 원문: "You're permitted to download, copy, modify, distribute, publicly perform and broadcast the Items. Your rights are non-exclusive, worldwide, sub-licensable and ongoing." Video Templates Free License, Art Free License도 같은 문장 — [Mixkit License](https://mixkit.co/license/)
- Mixkit User Terms 제한: 9.2 "sell physical or digital copies of Items without first altering them by applying human skill and effort", 9.4 "aggregate or collate an Item(s) and make available on a stock or inventory basis", 9.5 "use ... any Item, to build a similar or competitive product or service", 9.9 워터마크·저작권 고지 제거 금지 — [Mixkit Terms](https://mixkit.co/terms/)
- Pexels: "Don't sell unaltered copies of a photo or video", 식별 가능한 인물을 나쁘게 묘사 금지, 인물·브랜드의 보증 암시 금지. AI 언급 없음 — [Pexels License](https://www.pexels.com/license/)
- Videvo: `videvo.net`과 `videvo.net/terms-of-use/`가 각각 `freepik.com/videos`, `freepik.com//terms-of-use/`로 301 이동, `freepik.com/legal/terms-of-use`는 다시 `magnific.com/legal/terms-of-use`로 301 이동 — WebFetch 리다이렉트 응답(2026-11-22)
- Magnific 약관 8.1: 무료 이용은 "conditioned upon any use by the User being duly attributed to the Website/Company", 표기 방식은 "as indicated by the Company at any given time"(고정 문구 없음). Premium·Plus·Pro 구독 시 표기 면제. "for any machine learning and/or artificial intelligence purposes" 금지, "resell, assign, transfer or sublicense" 금지. 약관에 Videvo·Freepik 이름 언급 없음 — [Magnific Terms](https://www.magnific.com/legal/terms-of-use)
- 集中線 무료 소재 일반: "「商用利用OK」と書かれていても素材主体での再配布が禁止されているサイトが多く" — [Filmora 解説記事](https://filmora.wondershare.jp/video-editing/speed-lines-free-material.html)(편집 앱 회사의 2차 자료)
- BOOTH의 集中線 소재는 유료(1점 250円), 투과 AVI·PNG 연번 — 검색 요약 기준 [booth.pm/ja/items/8585062](https://booth.pm/ja/items/8585062)(본문 미확인)

### Inferences
- いらすとや는 stream2clip에 동봉 불가(편집 앱 수록 금지 명시). 사용자 추가 에셋으로 받을 때 라이선스 표에 "작품당 20점(썸네일 포함), 수익 창출 영상은 상업 이용"을 넣고, 점검에서 클립 1개(썸네일 포함)의 いらすとや 이미지 수를 세어 20 초과 시 오류 처리하는 `count_limit` 항목 권장. 모음 영상(compilation)은 "1商品（1番組）" 기준이므로 클립들을 합친 전체 개수로 계산해야 함.
- Pixabay·Mixkit·Pexels 오버레이(라이트 릭, 그린스크린 효과)를 클립에 합성하는 것은 "다른 요소와 결합한 새 창작물"에 해당해 허용 범위로 보임. 반면 오버레이 파일을 앱에 넣어 배포하는 것은 Pixabay의 Standalone 배포, Mixkit 9.4(재고 형태 제공)·9.5(유사 서비스), Pexels의 재배포 금지에 걸릴 수 있어 동봉하지 않음. Mixkit 라이선스 문장 자체는 "distribute", "sub-licensable"을 허용해 User Terms와 긴장 관계 → 모호로 표기.
- Videvo 소재는 이제 Magnific(구 Freepik) 약관을 따르는 것으로 보이며, 무료 사용 시 출처 표기 필수. 예전에 받은 Videvo 파일은 받을 당시의 라이선스(Videvo Free/Attribution/CC 3.0)를 사용자가 기록해야 함(옛 라이선스 원문은 이번에 확인 못함).
- 집중선, 플래시, 라이트 릭, 페이드·와이프 전환은 ffmpeg/libass로 코드 생성이 가능하므로(전략 a) 외부 소재 의존을 줄이는 것이 라이선스 측면에서 가장 단순.
- 라이선스 키 제안: `irasutoya`(count_limit=20, no_bundle), `pixabay`, `mixkit-video-free`, `pexels`, `magnific-free`(attribution), `miirriin`(no_bundle), `nicommons-<조건>`.

### Gaps
- ニコニ・コモンズ 공식 이용 조건 페이지를 열지 못함(`commons.nicovideo.jp/license`, `/help` 모두 404). 2차 자료상 작품마다 조건을 권리자가 지정하고 CC 라이선스를 쓰는 작품도 있음 — [ニコニコ大百科](https://dic.nicovideo.jp/t/a/%E3%83%8B%E3%82%B3%E3%83%8B%E3%83%BB%E3%82%B3%E3%83%A2%E3%83%B3%E3%82%BA). "ニコニコ外での利用", "営利目的での利用", 친자 등록 규정은 미확인.
- YouTube의 그린스크린 효과 팩(업로더 배포)의 "일반적 조건"에 대한 신뢰할 만한 자료를 찾지 못함. 업로더마다 설명란 조건이 다르며 YouTube 표준 라이선스 자체는 재사용 허락이 아님(일반 지식, 미확인).
- Pexels·Pixabay 영상 API의 이용 조건(앱에서 검색·미리보기 제공 가능 여부)은 이번 범위에서 확인하지 않음.
- Mixkit 영상 라이선스가 "도구·템플릿 수록"을 따로 금지하는지(BGM 보고서의 효과음 라이선스에는 있었음) 영상 모달에는 해당 문장 없음.

## 3. 한국 무료 에셋과 한국어 무료 폰트 (예능 자막 템플릿, 무료 효과 소스, 공공누리, 눈누 폰트)

### Takeaway
한국어 텔롭용 무료 폰트는 대부분 OFL(배민 주아·도현·연성 등의 Google Fonts판, Gmarket Sans, Pretendard, 나눔, Black Han Sans)이라 영상 번인과 앱 동봉이 모두 가능. 여기어때 잘난체는 OFL이 아닌 자체 라이선스로 영상 사용과 소프트웨어 번들은 허용하지만 "임의 수정/개작하여 재배포" 금지라 서브셋 동봉은 피해야 함. 예능 자막 템플릿·효과 소스는 공식 라이선스 문서가 있는 무료 출처를 찾지 못했고 판매형은 재배포 금지가 일반적.

### Cited Findings

| 폰트 | 라이선스 | 영상 번인 | 앱 동봉 | 주의 | 근거 |
|:---:|---|---|---|---|---|
| 배민 주아체(Jua), 도현체(Do Hyeon), 연성체(Yeon Sung) | Google Fonts판 `license: "OFL"`, designer "Woowahan Brothers" | 가능 | 가능(OFL) | Google Fonts판은 2018년판 | [google/fonts ofl/jua 등 METADATA.pb](https://raw.githubusercontent.com/google/fonts/main/ofl/jua/METADATA.pb) |
| 배민 글꼴 전반(꾸불림체 등, 산돌구름 배포) | 산돌구름 표기 "OFL 상업용 임베딩 로고•CI" | "영상물 자막 ... UCC 등 사용 가능" | "라이선스 전문을 표시하는 경우 다른 소프트웨어와 번들, 재배포 또는 판매" 가능 | 폰트 파일 "자체를 유상으로 판매하는 것은 금지" | [산돌구름 배민 꾸불림체](https://www.sandollcloud.com/free-font/21096/BM-Kkubulim)(검색 요약) |
| 여기어때 잘난체·잘난체 고딕 | 자체 라이선스, 지재권 ㈜여기어때컴퍼니 | 영상 "사용 가능" | 가능: 저작권 안내와 라이선스 전문 포함 시 번들·재배포·판매 가능. "임베딩 된 폰트는 별도 판매 불가" | "글꼴 자체를 유료로 판매하거나 어떠한 형태로든 임의 수정/개작하여 글꼴을 재배포 하는 것은 금지" | [산돌구름 잘난체 고딕](https://www.sandollcloud.com/free-font/19493/Jalnan-Gothic) |
| Gmarket Sans | "'SIL Open Font License'에 따라 개인 또는 기업이 영리적, 비영리적 목적으로 자유롭게 사용" | 가능 | 가능(OFL) | 페이지에 OFL 전문·버전 없음 | [corp.gmarket.com/fonts](https://corp.gmarket.com/fonts/) |
| Pretendard (v1.3.9, CDN 기준) | SIL OFL | 가능 | "글꼴 단독 판매를 제외한 모든 상업적 행위 및 수정, 재배포가 가능" | OFL 버전 표기 없음(링크만) | [github.com/orioncactus/pretendard](https://github.com/orioncactus/pretendard) |
| 나눔글꼴 | OFL(2010년 전환) | 가능 | 저작권 안내와 라이선스 전문 포함 시 번들·재배포·판매 가능, 단독 유료 판매 금지 | 수정 시 수정본도 OFL | [네이버 보도자료](https://navercorp.com/media/pressReleasesDetail?seq=27958)(검색 요약), Google Fonts Nanum Gothic `license: "OFL"` [METADATA](https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/METADATA.pb) |
| Black Han Sans, Gamja Flower, Sunflower, Dongle, Gowun Dodum, Noto Sans KR | 모두 Google Fonts `license: "OFL"` | 가능 | 가능 | Noto Sans KR 저작권 줄에 "Reserved Font Name 'Source'" | [google/fonts ofl/*/METADATA.pb](https://github.com/google/fonts/tree/main/ofl) |

- 공공누리 제1유형 "출처표시"(상업·비상업, 2차적 저작물 작성 가능), 제2유형 "출처표시 + 상업적 이용금지", 제3유형 "출처표시 + 변경금지", 제4유형 "출처표시 + 상업적 이용금지 + 변경금지" — [공공누리 유형 안내](https://www.kogl.or.kr/info/license.do)
- 공공누리 출처 표시 예시: "본 저작물은 'OOO(기관명)'에서 'OO년'작성하여 공공누리 제O유형으로 개방한 '저작물명(작성자:OOO)'을 이용하였으며" + 다운로드 주소 문장. 기관이 후원하는 듯한 오인 표시 금지 — [공공누리 유형 안내](https://www.kogl.or.kr/info/license.do)
- 잘난체: CI/BI 상표 등록 불가, 단순 변형은 "글꼴의 조형성을 해치지 않는 범위 내에서" 허용, 출처 표기 예시 "이 상품에는 ㈜여기어때컴퍼니가 제공한 여기어때 잘난체·잘난체 고딕이 적용되어 있습니다." 산돌구름은 이 정보가 "법적 권리를 보장하는 것은 아니므로" 원저작자 확인을 권고 — [산돌구름 잘난체 고딕](https://www.sandollcloud.com/free-font/19493/Jalnan-Gothic)
- 유료 자막 템플릿 판매 페이지는 "해당 상품의 재배포는 금지", "템플릿 및 자막 무료 배포 혹은 공유 시 법령에 따라 처벌" 같은 조건을 둠 — 검색 요약 기준 [kmong.com/gig/686899](https://kmong.com/gig/686899), [kmong.com/gig/503717](https://kmong.com/gig/503717)(본문 미확인)
- 무료 영상 소스의 "상업적 이용 가능하지만 출처 표기 필수" 유형 구분 — [brunch @ainote/210](https://brunch.co.kr/@ainote/210)(블로그, 2차 자료)

### Inferences
- 기본 동봉 한국어 텔롭 폰트 후보: Black Han Sans(굵은 고딕), Do Hyeon, Jua(둥근), Gmarket Sans Bold, Pretendard Black. 모두 OFL이므로 원본 파일 그대로 넣고 `OFL.txt`와 저작권 줄을 함께 두면 됨. 영상에 번인된 자막 자체에는 크레디트 의무 없음(OFL FAQ 1.1, 1.13, 4절 참조).
- 잘난체는 동봉 가능하지만 서브셋(필요 글리프만 남기기)이 "수정/개작하여 재배포"로 해석될 위험이 있어 원본 그대로 넣거나 사용자 설치 폰트로만 지원.
- 배민 글꼴은 우아한형제들 원문을 확인하지 못했으므로 동봉 시 Google Fonts의 OFL판(Jua, Do Hyeon, Yeon Sung)을 쓰는 것이 출처가 분명함. 한나체·을지로체·꾸불림체 등은 산돌구름 요약만 확인.
- 예능 자막 템플릿·효과 소스는 라이선스 근거가 약하므로 stream2clip은 자막 스타일(테두리, 그림자, 색 박스, 튀어오름)을 ASS 스타일과 코드로 생성(전략 a)하고, 외부 템플릿은 사용자 추가 + "라이선스 미확인" 경고로 처리.
- 공공누리 자료는 BGM 보고서의 공유마당 처리와 같이 `kogl-1`~`kogl-4` 키로 기록. 제3·4유형(변경금지)은 클립에 합성·자르기만 해도 변경으로 볼 수 있어 점검에서 ND 경고, 제2·4유형은 수익 창출 영상에서 NC 오류.

### Gaps
- 우아한형제들 공식 글꼴 페이지(woowahan.com/fonts)는 스크립트로만 렌더링되어 원문을 읽지 못함. 나눔글꼴 공식 도움말(help.naver.com)은 가져오기 차단.
- 눈누(noonnu.cc) 목록의 개별 표기는 열지 않음. 눈누는 원저작자 라이선스를 옮긴 2차 자료이므로 원문 확인이 필요.
- 예능 자막 무료 템플릿을 배포하는 공식 무료 출처(라이선스 문서가 있는 곳)를 찾지 못함.
- Gmarket Sans의 OFL 버전, Reserved Font Name 여부.

## 4. 일본어 텔롭 폰트 (M PLUS, Noto Sans/Serif CJK, Dela Gothic One, RocknRoll One, Zen Maru Gothic, 源ノ角ゴシック, けいふぉんと!, やさしさゴシック)

### Takeaway
질문에 나온 Google Fonts 일본어 폰트는 Kosugi Maru(Apache 2.0)를 빼고 모두 OFL로 확인되어 영상 번인, 원본 그대로 동봉, ASS 렌더링에 제약이 없음. 단 Noto Sans JP와 源ノ角ゴシック은 Reserved Font Name 'Source'가 있어 서브셋·수정본을 배포하려면 이름을 바꿔야 함. けいふぉんと!(Apache 2.0, 2014년 기사 기준)와 やさしさゴシック(M+ + IPA)는 원문 미확인이라 동봉에서 제외 권장.

### Cited Findings

| 폰트 | 라이선스 | 디자이너 | 저작권 줄 | 근거 |
|:---:|---|---|---|---|
| M PLUS Rounded 1c | OFL | Coji Morishita, M+ Fonts Project | "Copyright 2016 The Rounded M+ Project Authors." | [METADATA](https://raw.githubusercontent.com/google/fonts/main/ofl/mplusrounded1c/METADATA.pb) |
| M PLUS 1p / M PLUS 1 / M PLUS 2 | OFL | Coji Morishita | M PLUS 1·2: "Copyright 2021 The M+ FONTS Project Authors" | [ofl/mplus1p](https://raw.githubusercontent.com/google/fonts/main/ofl/mplus1p/METADATA.pb), [ofl/mplus1](https://raw.githubusercontent.com/google/fonts/main/ofl/mplus1/METADATA.pb) |
| Dela Gothic One | OFL | artakana | "Copyright 2020 The Dela Gothic Project Authors" | [ofl/delagothicone](https://raw.githubusercontent.com/google/fonts/main/ofl/delagothicone/METADATA.pb) |
| RocknRoll One | OFL | Fontworks Inc. | "Copyright 2020 The RocknRoll Project Authors" | [ofl/rocknrollone](https://raw.githubusercontent.com/google/fonts/main/ofl/rocknrollone/METADATA.pb) |
| Zen Maru Gothic / Zen Kaku Gothic New | OFL | Yoshimichi Ohira | "Copyright 2021 The Zen Maru Gothic Authors" | [ofl/zenmarugothic](https://raw.githubusercontent.com/google/fonts/main/ofl/zenmarugothic/METADATA.pb) |
| Noto Sans JP | OFL | Google | "(c) 2014-2021 Adobe ... with Reserved Font Name 'Source'." | [ofl/notosansjp](https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/METADATA.pb) |
| Noto Serif JP | OFL | Google | "(c) 2017-2024 Adobe" | [ofl/notoserifjp](https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifjp/METADATA.pb) |
| 源ノ角ゴシック (Source Han Sans) | OFL 1.1 | Adobe | "Copyright 2014-2025 Adobe ... with Reserved Font Name 'Source'. Source is a trademark of Adobe" | [adobe-fonts/source-han-sans LICENSE.txt](https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/LICENSE.txt) |
| Noto Sans CJK | OFL 1.1 | Google/Adobe | — | [notofonts/noto-cjk Sans/LICENSE](https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE) |
| Mochiy Pop One, Reggae One, Rampart One, DotGothic16, Train One, Potta One, Darumadrop One, Hachi Maru Pop, Kiwi Maru, Yusei Magic | 모두 OFL | FONTDASU, Fontworks, Font Zone 108, Maniackers Design, Nonty 등 | 각 METADATA | [google/fonts ofl/](https://github.com/google/fonts/tree/main/ofl) |
| Kosugi Maru | APACHE2 | MOTOYA | — | [apache/kosugimaru](https://raw.githubusercontent.com/google/fonts/main/apache/kosugimaru/METADATA.pb) |

- OFL FAQ 1.1: "allow you to use their font software as such for any kind of design work." / 1.13: "Referencing or embedding an OFL font in any document does not change the license of the document itself." — [OFL FAQ](https://openfontlicense.org/ofl-faq/)
- OFL FAQ 1.3: "The intent of the license is to allow aggregation or bundling with software under restricted licensing as well." / 1.5: 판매도 "as long some other font or software is also on the disk, so the OFL font is not sold by itself" — [OFL FAQ](https://openfontlicense.org/ofl-faq/)
- OFL FAQ 1.20: "At a minimum you must include the copyright statement, the license notice and the license text." / 1.10: OFL 전문 없이 배포 가능한 유일한 경우는 프로그램 안에 임베드·번들된 경우 — [OFL FAQ](https://openfontlicense.org/ofl-faq/)
- OFL FAQ 2.6: 사용하지 않는 글리프 제거를 포함한 부분 삭제는 수정이며 "would not normally allow the use of RFNs" / 3.1: 예약 이름이 있으면 수정 시 "change the internal names of the font" — [OFL FAQ](https://openfontlicense.org/ofl-faq/)
- けいふぉんと!: "フォントはApache_License_2.0で配布されています", 상업 이용 "特に制限していない", 작자 요청 "「けいおん！」の名誉を傷つける場面での使用はご遠慮", 가나 이외 문자는 Source Han Sans, M+ OUTLINE FONTS, Source Han Mono 등 기반 (2014-09-20 기사) — [GIGAZINE](https://gigazine.net/news/20140920-k-font/)
- けいふぉんと! 제작자는 Do-Font, 가나는 『けいおん!』에서 착안 — [Fonts In Use](https://www.fontsinuse.com/typefaces/231258/kei-font)(2차 자료)
- やさしさゴシック(Kato Masashi): 독자 디자인 가나 + M+ FONTS 영숫자·한자 + 부족분 IPA 폰트, 상업·비상업 무료 이용과 재배포 가능. 볼드판은 IPA 폰트 미포함 (2012~2014년 기사) — [窓の杜 2012-03-19](https://forest.watch.impress.co.jp/docs/review/20120319_519130.html), [窓の杜 2014-10-22](https://forest.watch.impress.co.jp/docs/review/20141022_672288.html)

### Inferences
- 텔롭용 굵은·둥근 일본어 폰트 후보(동봉 가능, OFL): Dela Gothic One(아주 굵은 고딕, 강조 자막), RocknRoll One(둥근 극태), M PLUS Rounded 1c(굵기 여러 개, 일반 자막), Zen Maru Gothic(둥근, 부드러운 말투), Mochiy Pop One·Potta One(팝, 귀여움), Reggae One·Rampart One(충격, 개그). 굵기 수와 가나·한자 수록 범위는 이번에 확인하지 않음.
- 일본어 전용 폰트(예: Dela Gothic One)는 한글이 없고, 한국어 폰트는 가나가 없을 가능성이 커서 언어별 폰트 대체(libass/fontconfig 폴백 또는 자막 줄별 폰트 지정)가 필요(글리프 범위 미확인).
- stream2clip이 폰트를 동봉하면 원본 TTF/OTF + `OFL.txt` + 저작권 줄을 `fonts/<이름>/`에 그대로 두는 방식이 OFL FAQ 1.20을 충족. 앱 크기를 줄이려고 서브셋하면 Noto Sans JP·源ノ角ゴシック은 이름을 바꿔야 하므로(FAQ 2.6, 3.1) 서브셋하지 않는 편이 단순. 렌더링된 영상에는 OFL이 적용되지 않음(FAQ 1.1, 1.13).
- Kosugi Maru는 Apache 2.0이라 동봉 시 Apache 라이선스 사본 필요(본문 미확인, 일반 조건).
- けいふぉんと!는 Apache 2.0이라는 2014년 기사와 OFL 기반 폰트(Source Han Sans) 혼합이라는 설명이 겹쳐 라이선스 구성이 모호하고, 특정 작품 관련 작자 요청이 있으므로 동봉하지 않고 사용자 설치 폰트로만 지원.

### Gaps
- けいふぉんと!, やさしさゴシック의 현재 공식 배포 페이지와 동봉 라이선스 파일은 열지 않음(기사가 2012~2014년). 질문의 "07やさしさゴシック"이 Kato Masashi의 やさしさゴシック과 같은 폰트인지 확인하지 못함.
- IPA 폰트 라이선스(파생 프로그램의 이름 변경·배포 조건) 원문은 이번에 열지 않음 — [moji.or.jp/ipafont/license](https://moji.or.jp/ipafont/license/) 후보.
- Google Fonts FAQ(fonts.google.com/faq)는 스크립트 렌더링이라 본문을 읽지 못해 OFL FAQ로 대체.
- Kosugi Maru의 MOTOYA 저작권 줄.

## 5. Lottie·움직이는 스티커 (LottieFiles, Noto 움직이는 이모지, Telegram/Discord 스티커)

### Takeaway
Noto 움직이는 이모지는 CC BY 4.0(크레디트 필요, 동봉 가능)으로 가장 명확한 무료 움직이는 스티커 출처. LottieFiles 공개 무료 애니메이션은 Lottie Simple License로 상업 사용·수정·배포와 크레디트 생략을 허용하지만, LottieFiles 사이트 전체 약관의 자동 수집 금지와 "Free Plan" 상업 사용 금지 문구가 겹쳐 앱 동봉이나 자동 수집은 피해야 함.

### Cited Findings
- Noto 움직이는 이모지: "The artwork is available under the CC BY 4.0 license." (2022-09-13 게시), 컬렉션은 googlefonts.github.io/noto-emoji-animation — [Google Developers Blog](https://developers.googleblog.com/updates-to-emoji-new-characters-new-animation-new-color-customization-and-more)
- Noto 움직이는 이모지 사이트는 .svg, lottie.json, .webp, .gif 형식을 제공하고, Flutter·Rust 패키지가 이 Lottie 파일을 CC BY 4.0 아트워크로 묶어 배포 — 검색 요약 기준 [pub.dev animated_emoji](https://pub.dev/packages/animated_emoji), [animated-emojis-rs](https://www.github.com/rbozan/animated-emojis-rs)(공식 페이지 본문은 스크립트 렌더링이라 미확인)
- Lottie Simple License (FL 9.13.21), "Copyright © 2021 Design Barn Inc.": 상업 목적 포함 사용·수정·배포 허용("including for commercial purposes"), 수정본은 "deemed derivative works", 배포 시 "must contain (and be subject to) the same terms and conditions of this license" — [LottieFiles License](https://lottiefiles.com/page/license)
- Lottie Simple License 제한: "does not include the right to collect or compile Files from LottieFiles" ... "to replicate or develop a similar or competing service". 크레디트: "Use of Files without attributing the creator(s) of the Files is permitted", 크레디트를 넣으면 "should be visible to the end user" — [LottieFiles License](https://lottiefiles.com/page/license)
- LottieFiles 약관 "Last Modified: 10th November 2026": 공개 무료 애니메이션은 Lottie Simple License에 동의하는 것으로 하며 복제·배포 제한에서 제외. 데이터 마이닝과 "any robot, spider, or other automatic device" 금지. "Any use of animations created under the Individual Plan or Free Plan for commercial purposes constitutes a breach of these terms." AI 학습 언급 없음 — [LottieFiles Terms](https://lottiefiles.com/page/terms-and-conditions)

### Inferences
- LottieFiles 약관의 "Free Plan ... commercial purposes" 금지 문장은 LottieFiles 도구로 "만든(created)" 애니메이션에 대한 것으로 읽히나, 공개 무료 애니메이션의 상업 허용(Simple License)과 충돌하는 것처럼 보일 수 있어 모호로 표기. 수익 창출 클립에 쓰는 사용자 에셋은 "Lottie Simple License, 크레디트 선택, 동봉·자동 수집 금지"로 기록하고 점검에서 경고 수준.
- Noto 움직이는 이모지는 CC BY 4.0이라 동봉 가능하지만 사용한 클립마다 설명란 크레디트 필요(예: "Noto Animated Emoji by Google, CC BY 4.0"). 크레디트가 필요 없는 정적 Fluent/Noto 이미지에 코드로 튀어오름·흔들림을 주는 방식(전략 a)이 크레디트 부담이 가장 적음.
- ffmpeg/libass는 Lottie JSON을 직접 그리지 못하므로 WebP/GIF판을 쓰거나 별도 렌더러(rlottie 등)로 PNG 연번 변환이 필요(기술 사항, 이번에 확인하지 않음).
- Telegram·Discord 스티커는 개별 작가나 플랫폼이 권리를 가진 그림이며 재사용 라이선스가 부여되지 않으므로 stream2clip 라이선스 표에서 "허용 안 됨"으로 두는 것이 합리적(약관 원문은 확인하지 않음).

### Gaps
- Noto 움직이는 이모지 공식 페이지의 라이선스 문구와 형식 목록을 직접 읽지 못함(블로그 문장으로만 확인). 저장소 `googlefonts/noto-emoji-animation`은 404.
- Telegram 스티커·Discord 스티커 약관의 재사용 조항 원문 미확인.
- LottieFiles 무료 애니메이션 중 작가가 다른 라이선스를 붙인 경우의 처리.

## 6. 효과를 제한하는 기획사 가이드라인과 YouTube 규칙 (hololive, にじさんじ, ぶいすぽっ!, あおぎり高校, YouTube 변경·합성 콘텐츠, 재사용 콘텐츠)

### Takeaway
네 기획사 모두 효과 자체(집중선, 플래시, 이모지)를 금지하지 않지만, 공통으로 "오해를 부르는 편집"(にじさんじ는 "画像・文字・音声等を追加するなどして" 명시)과 과장된 썸네일·제목을 금지하고, ぶいすぽっ!·hololive는 창작성 없는 단순 자르기를 2차 창작으로 보지 않음. YouTube는 미적 효과(특수 효과 필터 등)를 변경·합성 콘텐츠 공개 대상에서 제외하고, 재사용 콘텐츠 정책은 "substantive editing"을 보여 주는 음향·시각 효과를 수익 창출 허용 예시로 둠. 실존 인물이 하지 않은 말을 한 것처럼 만드는 음성 변경·AI는 공개 대상이며 あおぎり·ぶいすぽっ!는 AI 사용 표기를 별도로 요구.

### Cited Findings

**hololive (cover, 2026年8月31日改訂)** — [hololivepro.com/terms](https://hololivepro.com/terms/)
- 2차 창작 범위: "単なる改変の域を出ないもの等の創作性に欠けるものは、二次創作とはみなさず"
- 금지: "公式と詐称、または公式と誤解・誤認されうるもの", "タレントが不快と感じる創作活動はお控えください", "公序良俗に反するもの", "第三者の名誉・品位等を傷つけるもの"
- 클립 가이드라인: 클립 안의 제3자 콘텐츠는 "当該コンテンツ権利者の利用規約等の定めを遵守", 내용·"サムネイルその他事情により、削除手続きを行うことがございます", Content ID 등 "自動識別機能の登録は禁止"
- 음악 가이드라인: "当社楽曲から所属タレントの音声を抽出しセリフ生成をしたもの"는 허용하지 않음
- 외모·음성 변경, 효과 추가를 직접 다루는 조항은 없음

**にじさんじ (ANYCOLOR, 2025年5月23日改定)** — [anycolor.co.jp/guidelines](https://www.anycolor.co.jp/guidelines)
- 제5조 2항: 발언·영상·음성을 "トリミングしたり、画像・文字・音声等を追加するなどして" 의도적으로 (1) "誤解を生じさせるよう誘導", (2) 허위 정보 유포, (3) 명예·신용 훼손을 일으키는 행위 금지
- 제5조 3항: "本意とは離れた内容または刺激的な内容を含む文字もしくは画像を使用する行為も禁止"(썸네일)
- 제5조 1항: 클립 채널 등록 양식 등록과 설명란에 원 방송 URL 기재. 제4조 2항: 공식 작품으로 오인시키는 표현 금지
- 외모·음성 변경, AI 음성 합성, 다른 캐릭터 추가는 직접 언급 없음

**ぶいすぽっ! (Brave group, 영문판 "Revised on September 17, 2026")** — [vspo.jp/en/?p=437](https://vspo.jp/en/?p=437)
- 사전 허가제: 클립 신청 양식으로 "obtain prior permission", 허가 번호와 "the URL of the original video or livestream"을 설명란에 기재(X 게시는 번호 불필요)
- 금지: "lack creativity and consist solely of clips cut from the original video or livestream", 노래방·3D 라이브 노래 부분 재게시, "Exaggerated descriptions in thumbnails or video titles", 공식 오인 표현, 폭력·그로테스크·성적 묘사
- 수익: 게시 채널이 수익 창출 중이고 ぶいすぽっ! 멤버가 나오는 영상의 총수익이 월 100,000엔 이상("reaches 100,000 yen or more per month")이면 지정 메일로 신고. 멤버 일러스트를 썸네일·영상에 쓰려면 허가 코드 필요
- 게시 시점: YouTube 방송 종료 1시간 후, Twitch는 24시간 후. AI 일러스트는 "#AIIllustration" 사용

**あおぎり高校 (viviON, 2026年7月3日改定)** — [vhs-city.com/aogirihighschool/guidelines/fanfic](https://vhs-city.com/aogirihighschool/guidelines/fanfic) (aogirihighschool.com에서 301 이동)
- 제3조 5항: 가이드라인 준수 시 "当社への申請や連絡は不要". 제7조 2항: "趣味やファンとしての活動の範囲内に限り" 클립 수익 가능, 사업·영리 목적 금지
- 제7조 3항: 원 영상 URL과 제목 필수, 아카이브 공개 전 게시 자제, "視聴者の誤解を生じさせるような切り抜き動画の公開は禁止", 허위 정보 유포 클립 금지, 수정·삭제 요청에 즉시 대응
- 제3조 6항: AI 사용 시 "AI利用を示すハッシュタグ（「#AIイラスト」等）、またはAI利用を示す文面" 필수. Q&A: 동영상은 설명란에 "#AIイラスト」「#生成AI」等" 기재, 썸네일에 AI를 썼을 때도 같음
- 제4조: 공식 오인 표현, 공식 허가를 받았다는 명기, 이미지 훼손, 원저작물 그대로 복제, 한정 콘텐츠 사용, "他者に不快感を与える表現" 금지
- AI 표기 추가 개정 보도(2026-02-18) — [GameBusiness.jp](https://www.gamebusiness.jp/article/2026/02/18/26221.html)

**YouTube 변경·합성 콘텐츠 공개** — [support.google.com/youtube/answer/14328491](https://support.google.com/youtube/answer/14328491?hl=en) (페이지에 개정일 없음)
- 공개 필요: AI로 생성되거나 의미 있게 변경되어 "when it appears realistic"인 콘텐츠. 예: "Makes a real person appear to say or do something they didn't do", "Alters footage of a real event or place", "Generates a realistic scene that didn't actually occur"
- 공개 불필요: 비현실적 콘텐츠, "Minor edits are ones that are primarily aesthetic" — "Applying beauty filters", "Color adjustment or lighting filters", "Special effects filters, like adding background blur or vintage effects". 제작 보조(대본, 썸네일, 제목 등)도 불필요
- 음성: "Cloning one's own voice to create voice overs or dubs"와 "voice or audio repair"는 불필요. 타인 음성 복제는 직접 언급 없음

**YouTube 수익 창출 정책: 비진정성(inauthentic)·재사용 콘텐츠** — [support.google.com/youtube/answer/1311392](https://support.google.com/youtube/answer/1311392?hl=en)
- 2025-07-15 "repetitious content"를 "inauthentic content"로 이름 변경. 재사용 콘텐츠 정책은 변경 없음
- 수익 허용 예시 9번째: "Edited footage with audio and visual effects on top of the video's reused content that demonstrates substantive editing and shows it's unique to your channel". 그 밖에 "Edited footage from other creators where you add a storyline and commentary", "Reaction videos where you comment on the original video"
- 수익 불허 예시: "Clips of moments from your favorite show edited together with little or no narrative", "Content downloaded or copied from another online source without any substantive modifications", "Content that gets views from mostly non-verbal reactions to your videos without added voice commentary"
- 원 제작자의 허락이 있어도 적용("applies even if you have permission from the original creator")
- 비진정성: "content that looks like it's made with a template", "AI-generated content made with generic or unoriginal templates"는 불허, 같은 인트로·아웃트로 사용은 허용

### Inferences
- 집중선, 플래시, 라이트 릭, 전환, 이모지 스티커, 프레임, 텔롭은 YouTube 기준 "Special effects filters"류의 미적 편집으로 변경·합성 콘텐츠 공개 대상이 아님. stream2clip이 Data API 업로드 시 합성 콘텐츠 표시를 켤 필요는 효과만으로는 없음.
- 음성 변조(피치 변경 등 단순 효과)는 공개 대상이 아닐 가능성이 크지만, AI 음성 변환·대사 생성으로 탤런트가 하지 않은 말을 하게 만들면 YouTube 공개 대상이고 hololive(음성 추출 후 대사 생성 불허), にじさんじ 제5조 2항(음성 추가로 오해 유도)에 걸림. stream2clip은 탤런트 음성의 AI 변환·생성 기능을 제공하지 않는 것이 안전.
- 효과의 "오해 유도" 위험: 반응 이미지·이모지·자막을 원래 맥락과 다른 감정(분노, 다툼)으로 붙이거나 다른 탤런트·캐릭터 이미지를 합성하면 にじさんじ 제5조 2항, あおぎり 제7조 3항(4), hololive "タレントが不快と感じる創作" 금지에 걸릴 수 있음. 자동 효과는 채팅 반응 분류(웃음, 놀람, 귀여움, 환호)처럼 실제 반응에 근거해 배치하고, 썸네일·제목의 과장 문구는 ぶいすぽっ! "Exaggerated descriptions", にじさんじ 제5조 3항 점검 항목으로 경고.
- "효과를 많이 넣으면 독창적 기여가 되는가": YouTube는 음향·시각 효과를 허용 예시에 넣었지만 "substantive editing"과 채널 고유성을 조건으로 하며, 해설·서사가 거의 없는 장면 모음과 비언어적 반응 위주 콘텐츠는 불허 예시. 템플릿처럼 똑같은 효과를 기계적으로 반복하면 "inauthentic content"(템플릿형)로 볼 여지. 따라서 효과만으로 충분하다고 단정할 수 없고 자막 해설·편집 서사가 함께 필요하다고 보는 것이 안전(모호).
- 기획사 측도 hololive("創作性に欠けるもの"), ぶいすぽっ!("lack creativity")가 단순 자르기를 배제하므로 같은 방향. 다만 어느 정도의 효과가 창작성으로 인정되는지 기준은 없음.
- AI 표기 점검: 썸네일이나 이미지에 생성 AI를 쓴 경우 あおぎり는 설명란에 "#生成AI" 등, ぶいすぽっ!는 AI 일러스트에 "#AIIllustration" 필요. stream2clip이 AI 생성 이미지를 쓰지 않으면 해당 없음.
- 기획사별 점검 항목 제안: にじさんじ(등록 여부, 원 방송 URL), ぶいすぽっ!(허가 번호, 원 방송 URL, 방송 종료 1시간 후 게시, 노래 부분 제외), あおぎり(원 영상 URL과 제목, 아카이브 공개 후 게시), hololive(Content ID 등록 금지, 제3자 콘텐츠 조건 준수). 원 방송 URL은 네 곳 공통으로 설명란에 자동 기재 가능.

### Gaps
- ぶいすぽっ! 일본어 원문 페이지 주소와 일본어판 개정일(영문판만 확인).
- 네 기획사 모두 "외모 변경"(얼굴 확대, 왜곡, 필터)이나 "음성 변조"를 직접 다룬 조항이 없어 일반 금지 조항으로만 판단 가능.
- YouTube 변경·합성 콘텐츠 페이지가 VTuber 아바타(실존 인물의 가상 외형)를 "real person"으로 보는지 언급 없음.
- 재사용 콘텐츠 정책에서 "substantive editing"의 구체적 기준(효과 개수, 비율)은 공개되지 않음.
