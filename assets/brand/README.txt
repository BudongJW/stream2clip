stream2clip 컨셉 로고 및 컨셉 이미지 (v0.1)
================================================

[ 메인 이미지 ]
01_concept-logo-sheet@2x.png              로고 시트 (2880×2160)
02_concept-image_keyvisual@2x.png         컨셉 이미지, 키 비주얼 (3840×2160)
02_concept-image_keyvisual_1920x1080.png  동일 이미지, FHD 크기
03_github-social-preview_1280x640.png     GitHub 소셜 프리뷰 (업로드용 규격)
03_github-social-preview@2x.png           동일 이미지, 2배 크기

[ logo/svg ]  벡터 원본 (크기와 무관하게 선명)
symbol_color_on-light.svg   밝은 배경용 컬러 심볼
symbol_color_on-dark.svg    어두운 배경용 컬러 심볼
symbol_mono_black.svg       단색 (검정)
symbol_mono_white.svg       단색 (흰색)
symbol_small_16px.svg       16px 이하용 단순화 버전 (점, 삼각형 생략, 선 굵게)
app-icon_dark.svg           앱 아이콘, 다크
app-icon_pink.svg           앱 아이콘, 핑크

[ logo/png ]  투명 배경 PNG
위 SVG의 1024px 버전
lockup_on-dark.png, lockup_on-light.png   심볼과 워드마크의 가로형 로고

[ logo/favicon ]
favicon.ico (16, 32, 48px), favicon_32.png, favicon_512.png, apple-touch-icon_180.png

[ app-icons ]  앱 아이콘 및 파비콘 (상세 내용: app-icons/README.txt)
windows/  stream2clip.ico, stream2clip_kiri.ico  (16~256px 10개 크기 내장)
macos/    .icns, 1024px PNG
linux/    PNG 16~512px
web/      favicon.ico, favicon.svg, apple-touch-icon, android-chrome, site.webmanifest
- 심볼형(stream2clip)이 기본, 키리형(stream2clip_kiri)은 마스코트 얼굴. 24px 이하는 단순화 심볼
- 앱은 심볼형 사용: 창 아이콘 = src/stream2clip/gui/assets/icon_*.png, 실행 파일 = windows/stream2clip.ico

[ mascot ]  마스코트 키리 SD 이모트 5종 (상세 내용: mascot/README.txt)
kiri_wink, kiri_laugh, kiri_surprised, kiri_cut, kiri_focus
크기: 512, 112, 56, 28px 투명 PNG
- 앱(하이라이트 창)은 56px, 112px을 src/stream2clip/gui/assets/kiri_*.png 로 복사하여 사용

[ 컬러 ]
잉크 #15131F, 페이퍼 #F7F4FA, 라이브 핑크 #FF4F8B, 하이라이트 #FFD84D

[ 서체 ]
워드마크, 영문: Outfit / 국문: Noto Sans KR / 타임코드: JetBrains Mono (전부 Google Fonts)

[ 폰트 관련 유의 사항 ]
- 이 PNG는 Outfit 폰트를 받을 수 없는 환경에서 렌더링되어 영문 워드마크와 영문 문구는
  유사한 기하학 산세리프인 Poppins로, 타임코드는 DejaVu Sans Mono로 대체
- 원래 디자인(Outfit)과 글자 형태가 일부 다름
- 심볼, 앱 아이콘, 파비콘은 순수 도형이므로 원본과 동일

[ GitHub 소셜 프리뷰 적용 ]
저장소 Settings의 General, Social preview에서 Edit, Upload an image 선택 후
03_github-social-preview_1280x640.png 업로드
