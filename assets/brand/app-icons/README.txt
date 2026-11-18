stream2clip 앱 아이콘 & 파비콘 (컨셉 v0.1)

두 가지 시안
  stream2clip       심볼형 — 로고 심볼 (기본 추천)
  stream2clip_kiri  키리형 — 마스코트 얼굴 + 클립 카드 배지. 32px 이하는 심볼로 자동 대체

windows/  .ico — 16·20·24·32·40·48·64·96·128·256px 내장 (설치 파일·바탕화면·작업 표시줄)
macos/    .icns — 16~1024px, macOS 규격 여백(1024 중 824 영역) + 그림자 / 1024 PNG 원본
linux/    PNG 16~512px (hicolor 아이콘 테마용)
web/      favicon.ico(16·32·48), favicon.svg, apple-touch-icon, android-chrome 192·512,
          site.webmanifest, head-snippet.html (웹 페이지 <head>에 붙여 넣기)

24px 이하에서는 REC 점·재생 삼각형을 빼고 선을 굵게 한 단순화 심볼을 씁니다.

적용 예
  Electron: BrowserWindow({ icon }) 및 electron-builder의 win.icon / mac.icon / linux.icon
  Tauri:    src-tauri/icons 에 .ico/.icns/PNG 교체
  PyInstaller: --icon windows/stream2clip.ico
