# 무료 BGM, 효과음 레퍼런스

조사일 2026-11-22. 쇼츠 제작 시 무료 배경 음악과 효과음을 넣는 기능(v0.15)의 근거 자료. 이용 조건은 각 사이트의 공식 약관 페이지에서 확인한 내용만 기재하며, 확인하지 못한 항목은 미확인으로 표기

## 1. 결론

| 항목 | 내용 |
|:---:|---|
| 음원 배포 | 외부 무료 음원은 저장소와 설치 프로그램에 포함하지 않음. 대부분의 사이트가 음원 파일 자체의 재배포를 금지하며, 효과음 라보는 영상 편집 앱의 기본 효과음으로 넣는 것을 재배포로 명시 |
| 자동 내려받기 | 구현하지 않음. OpenTracks(구 DOVA-SYNDROME)는 봇 수집, Uppbeat는 내려받기 스크립트, Mixkit은 대량 내려받기 봇, Pixabay와 Free Music Archive는 스크래핑 금지. Pixabay API는 음원을 제공하지 않음 |
| 내장 효과음 | 코드로 합성(numpy). 파일 배포, 크레디트, 라이선스 확인이 모두 불필요 |
| 사용자 음원 | 사용자가 직접 내려받은 파일을 음원 목록(`sounds.json`)에 출처 주소, 라이선스, 크레디트 문구와 함께 기록. 설명란 크레디트와 업로드 전 점검에 사용 |
| 점검 | 라이선스 표의 항목마다 공식 원문 주소와 확인 날짜 보유. 점검 목록이며 법적 판단이 아님 |

## 2. 음원 사이트별 이용 조건

### 해외

| 출처 | 수익 창출 영상 | 크레디트 | 앱, 저장소 동봉 | 자동 내려받기, API | Content ID | 공식 원문 |
|:---:|---|---|---|---|---|---|
| YouTube 오디오 보관함 | 가능 | 일반 곡 불필요, CC 곡은 Studio의 문구를 설명란에 기재 | 미확인(Studio 내부 약관, 로그인 필요) | API 없음, Studio에서만 내려받기 | 오디오 보관함 곡은 소유권 주장 대상 아님 | support.google.com/youtube/answer/3376882 |
| Pixabay 음악, 효과음 | 가능 | 불필요(권장 문구 제시) | 불가(단독 파일 배포 금지) | API에 음원 없음, 스크래핑 금지 | 방패 표시 곡은 Content ID 등록 곡 | pixabay.com/service/terms (2026-10-20) |
| Freesound | CC0, CC BY만 가능 | CC BY는 제목, 사용자명, 주소, 라이선스 | CC0, CC BY 가능 | API 키 필요, API 자체는 비영리 무료 | 낮음 | freesound.org/help/faq |
| Incompetech (Kevin MacLeod) | 가능 | 필수, 정해진 3줄 문구 | CC BY 4.0 조건으로 가능 | API 없음 | 높음(사전 등록, 크레디트로 이의 제기) | incompetech.com/music/royalty-free/faq.html |
| Free Music Archive | 곡별 라이선스 | 제목, 작가, 주소, 라이선스 | 곡별 라이선스 | API 없음, 자동 요청 금지 | 미기재 | freemusicarchive.org/License_Guide |
| ccMixter | CC BY 가능, NC 불가 | 정해진 문구 | CC BY 가능 | 조회 API(키 언급 없음) | 미기재 | ccmixter.org/terms |
| Openverse | 항목별 라이선스 | 응답의 `attribution` 필드 | 항목별 라이선스 | API 키 없이 사용 가능, 스크래핑 금지 | 출처별 | docs.openverse.org/terms_of_service.html |
| Uppbeat 무료 | 가능(개인 크리에이터, 유료 광고 제외) | 필수(내려받을 때 받은 문구) | 불가 | 내려받기 스크립트 금지 | 크레디트로 해제, 허용 목록은 유료 | uppbeat.io/uppbeat-basic-license |
| Bensound 무료 | 무료 공개 영상 | 필수, 영상마다 라이선스 코드 | 불가 | API 없음 | 허용 목록 유료 | bensound.com/terms-and-conditions (2026-06-22) |
| Mixkit | 가능 | 불필요 | 불가(효과음은 도구, 템플릿 사용 금지) | 대량 내려받기 봇 금지 | 해당 음원 등록 금지 | mixkit.co/license |
| Kenney, OpenGameArt | 가능 | CC0 불필요, 그 외 라이선스 조건 | CC0, CC BY 가능 | API 없음 | 낮음 | kenney.nl/support, opengameart.org/content/faq |
| BBC Sound Effects | 불가 | 정해진 문구 | 불가 | API 없음 | 해당 없음 | sound-effects.bbcrewind.co.uk/licensing |
| Sonniss GDC 번들 | 가능 | 불필요 | 불가(SDK, 템플릿 포함 금지) | API 없음 | 미기재 | sonniss.com/gdc-bundle-license (2.0, 2026-08-27 시행) |

- Bensound 무료 라이선스는 영상을 생성하는 앱이나 소프트웨어에서의 사용을 금지. stream2clip 점검에서 오류로 처리
- BBC Sound Effects는 소셜 미디어 업로드 금지. 수익 창출이 없는 Shorts에도 사용 불가
- Creative Commons 4.0 계열은 음악을 영상에 맞춰 넣는 것(싱크)을 변경 저작물로 간주. ND 라이선스는 배경 음악으로 사용 불가

### 일본, 한국

| 출처 | 수익 창출 영상 | 크레디트 | 앱, 저장소 동봉 | 자동 내려받기 | Content ID | 공식 원문 |
|:---:|---|---|---|---|---|---|
| OpenTracks (구 DOVA-SYNDROME) | 가능 | 불필요(작곡가별 조건 우선) | 불가 | 봇 수집 금지 | 등록 금지, 오인 주장은 이의 제기 | opentracks.com/help/articles/license/ |
| 효과음 라보 | 가능 | 선택 | 불가(편집 앱 기본 효과음, 템플릿은 재배포) | 미기재 | 사용 영상 등록 금지 | soundeffect-lab.info/agreement/ |
| 마왕혼 | 가능 | 선택(음악：魔王魂) | 불가 | 미기재 | 오인 주장은 사이트에 연락 | maou.audio/rule/ |
| OtoLogic | 가능 | 필수(CC BY 4.0) | 크레디트 유지 시 가능 | 미기재 | 사용 영상 등록은 위반 | otologic.jp/free/license.html |
| 아마차 음악 공방 | 가능 | 선택, 편곡 시 필수 | 불가 | 미기재 | 등록 금지 | amachamusic.chagasi.com/terms.html |
| 포켓 사운드 | 가능 | 필수(무료 사용 시) | 불가 | 미기재 | 이의 제기로 해제 | pocket-se.info/rules/ (2025-09-06) |
| 고모리 다이라 | 가능 | 선택 | 불명확 | 미기재 | 미기재 | taira-komori.net/welcome.html |
| Springin' Sound Stock | 가능 | 선택 | 불가 | 명시 없음 | 등록 금지 | springin.org/sound-stock/guideline/ |
| 브금대통령 | 영상 사이트 업로드 가능, 광고 영상과 라이브 방송은 유료 | 필수(출처와 링크) | 불가 | 미기재(구글 로그인, 채널 구독 확인 필요) | 미기재 | bgmpresident.com/policy.html |
| 공유마당 | 작품별 라이선스 | 필수(작품, 저작자, 출처, 라이선스) | 작품별 | 대량 전송 제한 | 미기재 | gongu.copyright.or.kr 이용약관 |
| 뮤팟 무료 | 조회 수익만 가능 | 미확인 | 불가 | 영리 목적 스크래핑 금지 | 미기재 | mewpot.com/qna/music_copyright |
| 셀바이뮤직 무료 | 미확인 | 필수 | 불가 | 미기재 | 미기재 | sellbuymusic.com/ko/legal/terms (2025-12-01) |

- DOVA-SYNDROME은 2026-09-15에 OpenTracks로 이름 변경. 기존 DOVA-SYNDROME 표기 크레디트도 유효
- 마왕혼의 현재 약관에는 CC BY 4.0 언급 없음. 저작자 사칭 금지, 음원 재배포와 판매 금지, AI 편곡과 학습 금지의 3개 조항
- 효과음공방, 아티스트 BGM은 공식 페이지를 찾지 못함
- 공유마당 음원은 별도 키 없이 해당 작품의 CC 라이선스 키(`cc-by-4.0` 등)와 작품 주소로 기록
- 뮤팟은 무료 BGM의 크레디트 조건을 확인하지 못하여 라이선스 표에서 제외

### 기획사 가이드라인

| 기획사 | 배경 음악, 효과음 관련 내용 | 원문 |
|:---:|---|---|
| hololive | 직접 언급 없음. 클립에 넣은 제3자 콘텐츠는 해당 권리자의 조건을 따라야 하며, 수익화는 제3자 조건을 어기지 않는 경우에만 가능. 클립의 Content ID 등록 금지 | hololivepro.com/terms (2026-08-31 개정) |
| にじさんじ | 직접 언급 없음. 의도적으로 오해를 부르는 음성 추가 금지(제5조 2항), 다른 권리자의 가이드라인 준수(제1조 3항) | anycolor.co.jp/guidelines (2025-05-23 개정) |

## 3. YouTube 관련 사항

| 항목 | 내용 | 근거 |
|:---:|---|---|
| Shorts 길이 | 2024-10-15 이후 업로드한 3분 이하의 세로 또는 정사각형 영상은 Shorts | support.google.com/youtube/answer/15424877 |
| 소유권 주장 | 1분이 넘는 Shorts에 유효한 소유권 주장이 있으면 전 세계 차단, 추천과 수익 창출 제외. 채널 불이익은 없으며 이의 제기 가능 | 같은 페이지 |
| 무료 음원의 소유권 주장 | 무료 사이트의 작곡가가 곡을 Content ID에 등록하는 경우가 많음. 제공처의 라이선스 문구나 코드로 이의 제기, 일부는 채널 허용 목록 제공(대부분 유료) | 각 사이트 안내 |
| 음량 | YouTube 공식 수치는 미공개. 측정 자료상 -14 LUFS 기준으로 큰 소리만 낮추며 작은 소리는 키우지 않음 | meterplugs.com 2019-09 |
| Data API | 업로드한 영상에 오디오 보관함 곡을 연결하는 항목 없음. 설명란 크레디트만 가능 | developers.google.com/youtube/v3/docs/videos |

## 4. 기술 레퍼런스

### 오픈소스 프로젝트

| 프로젝트 | 라이선스 | 배경 음악, 효과음 처리 |
|:---:|---|---|
| NaufalRizqullah/opensource-clipping | MIT | ffmpeg. 분위기별 폴더에서 무작위 선택, `-stream_loop -1`, `sidechaincompress`(threshold 0.08, ratio 5, attack 100, release 1000) 덕킹. 효과음, 라이선스 정보 없음. `amix` 기본 정규화로 음성까지 작아짐 |
| harry0703/MoneyPrinterTurbo | MIT | MoviePy. 고정 음량 0.2, 반복, 3초 페이드 아웃. 덕킹, 효과음 없음. 기본 곡의 출처 불명확 |
| RayVentura/ShortGPT | MIT | MoviePy. 고정 음량 0.11. 덕킹, 효과음 없음 |
| gyoridavid/short-video-maker | MIT | Remotion. 곡별 분위기 태그와 구간, 사전 `loudnorm`. YouTube 오디오 보관함 곡만 사용한다는 출처 안내 보유 |
| wyzowl/sfx-kit | CC0 | 효과음마다 타격 지점(`sync.at`) 메타데이터. stream2clip의 `hit` 항목에 반영 |
| FunClip, autoclip, auto-shorts | MIT | 배경 음악, 효과음 기능 없음 |

- 조사한 프로젝트 중 음원별 라이선스와 크레디트를 기록하는 곳과 효과음을 자동 배치하는 곳은 없음

### ffmpeg 필터

| 필터 | 사용 방식 | 주의 사항 |
|:---:|---|---|
| `amix` | `normalize=0`, `duration=first`, `dropout_transition=0` | 기본값(정규화)은 입력 수만큼 음성을 낮추고 효과음이 끝나면 다시 키움. `normalize`는 ffmpeg 4.4부터 |
| `sidechaincompress` | 클립 소리를 `asplit`으로 나눠 기준 신호로 사용. ratio 8, attack 50ms, release 600ms | 기준값보다 소리가 클수록 많이 줄어드므로 기준값을 클립마다 측정한 음량에서 계산 |
| `-stream_loop -1` | 배경 음악 입력 반복 | `aloop`는 샘플을 메모리에 보관 |
| `adelay` | `delays=밀리초:all=1`로 효과음 배치 | `all`은 ffmpeg 4.3부터 |
| `apad` | `whole_dur=길이`로 클립 소리를 클립 길이까지 채움 | `duration=first`의 길이 보장 |
| `alimiter` | `level=0`(자동 레벨 끔), 한도 -1dBFS | 기본값은 출력을 0dB로 키움 |
| `loudnorm` | 미적용. 2단계(측정 후 `linear=true`) 방식이 권장 | 1단계 방식은 동적 처리로 음량이 출렁이며 192kHz로 바꾸므로 `aresample` 필요 |

### 음량 기준

| 항목 | 수치 | 근거 |
|:---:|---|---|
| 해설과 음악의 차이 | 10 LU 이상, 비전문가는 약 4 LU 더 큰 차이 선호 | Torcoli 외, JAES 2019 |
| 접근성 기준 | 배경 소리는 말소리보다 20dB 낮게 | WCAG G56 |
| stream2clip 기본값 | 말하지 않는 동안 클립 소리보다 12dB 낮게, 말하는 동안 덕킹으로 추가 감소 | 위 범위(12~20 LU)의 중간 |

### 효과음 배치

- 채팅 급증은 실제 장면보다 늦음(Twitch 기준 23~27초, Lightor, ICDE 2020). stream2clip의 최고 순간은 채팅 지연 보정 후의 시각
- 채팅 반응 종류로 효과음 선택: 웃음, 놀람, 귀여움, 환호의 4분류(`auto`)
- 과다 사용 주의(편집 안내서의 공통 권고). 클립당 효과음 개수는 사용자가 지정

## 5. 이번 업데이트의 구성

| 구성 | 파일 | 내용 |
|:---:|---|---|
| 합성 명령 | `ffmpeg.py` | `AudioLayer`, `AudioMix`, `mix_filters`, `ExportOptions.mix` |
| 음원과 계획 | `soundtrack.py` | 내장 효과음 합성, 음원 목록, 음량 측정, 클립별 계획, 크레디트, 라이선스 표와 점검 |
| 클립 제작 | `pipeline.py`, `compliance.py` | `make_clips(soundtrack=)`, 설명란 크레디트, 업로드 전 점검, `clips.json`, 모음 영상 크레디트 |
| 명령줄 | `cli.py` | `--bgm`, `--bgm-under`, `--bgm-volume`, `--bgm-start`, `--no-duck`, `--sfx`, `--sfx-under`, `--sounds`, `sounds` 명령 |
| 앱 | `gui/highlights.py` | 내보내기 설정의 배경 음악, 효과음, 넣을 때 |

## 6. 필요한 것

### 사용자 준비

1. 음원 사이트에서 직접 내려받기(자동 내려받기 미지원)
2. `stream2clip sounds add 파일 --license 키 --title --author --url`로 기록. 사이트가 정한 크레디트 문구가 있으면 `--credit`에 그대로 입력
3. 내려받은 페이지 주소와 파일 이름 보관(소유권 주장 이의 제기 자료)
4. 외부 음원을 넣은 클립은 1분 이내 권장
5. 게시 전 `clip_XX.txt`의 크레디트와 점검 결과 확인

### 미확인 항목

| 항목 | 내용 |
|:---:|---|
| YouTube 오디오 보관함 | YouTube 밖에서의 사용 조건, 재배포 조건(Studio 내부 약관) |
| Uppbeat | 크레디트 문구의 정확한 형식 |
| 브금대통령, 셀바이뮤직 | 크레디트 문구의 정확한 형식 |
| Freesound | 무료 오픈소스 도구의 API 사용이 비영리에 해당하는지 |
| Openverse | 익명 사용의 요청 한도(공식 수치 미공개) |
| Openverse 분류 | 분류(category) 값은 Jamendo 곡에만 있어 Freesound 효과음은 분류로 찾을 수 없음. stream2clip은 길이로 구분(효과음 30초 미만, 음악 30초~10분) |
| Shorts 음량 | 일반 영상과 다른 정규화 여부 |
| 덕킹 값 | 다른 방송과 다른 곡에서의 확인(방송 1개, 곡 1개로 측정과 청취 완료, 7절) |

### 후속 과제

| 과제 | 상태 | 내용 |
|:---:|---|---|
| 음량 정규화 | 완료(v0.15) | `--loudness`, 앱의 -14 LUFS로 맞추기. 2단계 `loudnorm`, 최대값 -1.5 dBTP |
| 음원 검색 | 완료(v0.15) | `sounds search`, `sounds add --openverse`. 곡 정보와 원본 페이지만 표시하고 파일은 받지 않음 |
| 앱의 음원 목록 | 완료(v0.15) | 하이라이트 창의 목록: 추가, 라이선스 선택, 크레디트 입력과 미리보기, 빼기, 배경 음악으로 쓰기 |
| 효과음 위치 | 완료(v0.15) | 최고 순간 주변의 소리 시작점에 맞춤, 효과음 사이 최소 간격(`--sfx-gap`), 말하는 도중을 피하는 배치. 자동 자막의 줄 사이는 실제 말 끊김과 달라 소리로 판정. 짧은 클립 30개에서 위치(20ms 이내)와 간격 확인, 끝에서 잘리는 이동 수정. 효과음 5~6개를 넣은 클립 30개에서 배치 128개 모두 위치와 간격 확인, 소리 깨짐 없음 |
| 실측 | 일부 완료 | 실제 방송 클립의 덕킹 수치 측정과 청취 확인 완료. 실제 업로드 후 소유권 주장 여부는 미확인 |

## 7. 실제 방송 클립 덕킹 측정

측정일 2026-11-22. 실제 방송 1개(85분, 대화와 게임 음악)의 하이라이트 5개(50~90초)에 lofi 음악 1곡(65초, 반복)을 적용

| 항목 | 방법 |
|:---:|---|
| 기록 | 클립 소리, 제품과 같은 음량의 덕킹 전 음악, 제품과 같은 `sidechaincompress` 설정의 덕킹 후 음악을 각각 WAV로 기록 |
| 비교 단위 | 100ms 구간의 소리 크기. 시작과 끝 2초(페이드)는 제외 |
| 소리가 나는 순간 | 클립 소리가 클립의 말하는 부분 평균보다 20dB 이내인 구간 |
| 가림 위험 | 소리가 나는 순간 중 음악이 클립 소리와 6dB 이내로 가까운 비율 |

| 설정 | 가림 위험 | 클립 전체 기준 음악 차이(LU) | 조용한 부분의 남은 감소 | 100ms마다 4dB 넘는 변화 |
|:---:|---|---|---|---|
| 덕킹 시작 15dB 아래, 비율 8 (이전 기본값) | 16.7% | 15.1~18.1 | 0.5dB | 4.1% |
| 덕킹 시작 22dB 아래, 비율 8 (현재 기본값) | 9.0% | 15.5~19.5 | 0.9dB | 5.0% |
| 덕킹 시작 22dB 아래, 비율 4 | 10.6% | 15.6~19.3 | 0.9dB | 4.4% |
| 덕킹 시작 20dB 아래, 비율 6 | 11.9% | 15.4~18.8 | 0.8dB | 4.8% |
| 음악 3dB 낮춤(15dB 아래 유지) | 12.8% | 18.1~21.1 | 0.5dB | 4.1% |
| 기준 신호에 말소리 대역 필터 | 21.0% | 15.1~18.1 | 0.4dB | 4.1% |

- 이전 기본값에서는 작게 말하는 부분(-40~-45dBFS)이 덕킹 시작점보다 낮아 음악(-33dBFS 전후)에 묻힘. 시작점을 낮추어 개선
- 말소리 대역 필터는 기준 신호의 크기를 줄여 덕킹이 덜 걸리므로 역효과
- 게임 음악이 큰 구간 1곳은 현재 기본값에서도 가림 위험 27%. 음악을 더 낮추려면 `--bgm-under 15`(가림 위험 4.7%, 말하는 동안 음악 차이 약 27dB로 음악이 거의 들리지 않음)
- 한계: 방송 1개, 곡 1개, 수치 측정. 직접 들어 보는 확인 필요
