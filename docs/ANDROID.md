# 안드로이드 앱

휴대폰에서 다시보기 주소로 하이라이트를 찾고 Shorts를 만드는 앱. 실험 단계. 요약은 [README](../README.md#안드로이드-앱베타), 테스트 범위는 [TESTING](TESTING.md)

| &numsp;&numsp;&numsp;&numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp;&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| 화면 | Kotlin, Jetpack Compose. 한국어 기본, 일본어, 영어. 데스크톱 앱과 같은 어두운 브랜드 색(`brand.py`), 왼쪽 위의 로고(`lockup_on-dark`), 마스코트 키리(시작 화면 윙크, 결과 없음 집중, 완성 컷). 실행 아이콘은 키리형 앱 아이콘(`stream2clip_kiri`)의 적응형 아이콘(라벤더 배경, 원형과 둥근 사각형 마스크에서 귀와 클립 배지가 잘리지 않는 크기), Android 13 이상의 테마 아이콘은 로고 심볼 |
| 검출, 제목, 설명란 | 데스크톱과 같은 `stream2clip` 파이썬 패키지를 Chaquopy로 앱 안에서 실행(`android/app/src/main/python/s2c_android.py`가 연결). `src/stream2clip`을 그대로 넣고 `gui` 폴더만 제외 |
| 클립 제작 | Media3 Transformer와 휴대폰 하드웨어 인코더. 하이라이트 구간만 다시보기 스트림에서 읽음 |
| 정보와 채팅 | 치지직, SOOP은 데스크톱과 같은 다시보기 채팅 API. YouTube 채팅 다시보기와 방송 정보는 yt-dlp를 앱 안에서 실행(안드로이드 앱은 다른 프로그램 실행 불가) |

## 사용 순서

1. 다시보기 주소 붙여넣기. 치지직, SOOP, YouTube 앱의 공유 메뉴에서 stream2clip을 골라도 주소 입력
2. 형태 선택: Shorts(세로, 15~90초) 또는 가로 클립(1~3분). 데스크톱 `--preset shorts`, `clip`과 같은 구간 길이
3. **하이라이트 찾기**: 방송 정보, 채팅 다시보기 받기, 검출 순서로 진행 표시
4. 하이라이트마다 **제목, 설명 복사**(제안 제목과 설명란 전체), **원본에서 보기**(사이트별 시각 링크), **Shorts 만들기**. 연필 단추로 **제목(YouTube)**(100자까지, 글자 수 표시)과 **영상 문구**(영상 위쪽 글자) 고치기. 영상 문구의 기본값은 `[이름]` 없이 자르지 않은 대사(방송 제목). 3줄을 넘으면 글자를 70%까지 줄인 뒤에도 넘칠 때만 끝을 줄임표로
5. 여러 하이라이트의 **Shorts 만들기**를 누르면 차례로 제작(앞 영상이 끝나면 다음 시작). 휴대폰 인코더와 내려받기를 나눠 쓰지 않아 각각 빨리 끝남
6. 만든 영상은 `Movies/stream2clip`에 저장. **영상 열기**, **공유**(YouTube 앱 등)

| &numsp;&numsp;&numsp;형&NoBreak;태&numsp;&numsp;&numsp; | 결과 |
|:---:|---|
| Shorts | 1080x1920. 방송 화면 전체를 가운데에 두고 나머지를 같은 화면을 흐리게 확대해 채움(데스크톱 `blur` 레이아웃과 같은 흐림 정도와 밝기, GPU 셰이더 1회 처리). 30fps, 8 Mbps H.264(데스크톱 클립과 같은 30fps, YouTube 권장 1080p30 비트레이트). 위쪽에 영상 문구(너비의 8%, 한국 키리누키 Shorts 제목 띠와 같은 한 줄 약 5%, 3줄까지), 왼쪽 아래에 `원본: 채널` |
| 가로 클립 | 1920x1080. 방송 화면 그대로, 제목과 출처 표기 |

## 빌드

| &numsp;&numsp;&numsp;&numsp;준&NoBreak;비&numsp;&numsp;&numsp;&numsp; | 내용 |
|:---:|---|
| JDK | 17 |
| Android SDK | `platforms;android-36`, `build-tools;36.0.0`, `platform-tools`. `android/local.properties`에 `sdk.dir` 기록(저장소에는 미포함) |
| 빌드용 파이썬 | 3.13. Chaquopy가 pip와 바이트코드 컴파일에 쓰며 앱의 파이썬과 같은 버전이어야 함. 앱의 파이썬이 3.13인 이유는 Chaquopy가 numpy 1.26.2, Pillow 11.0.0을 제공하는 최신 버전이라서(3.14용 없음). Windows는 `py install 3.13`으로 기존 파이썬 옆에 설치 |

```powershell
cd android
.\gradlew.bat assembleDebug
```

- 결과: `android/app/build/outputs/apk/debug/app-debug.apk`
- 첫 빌드에서 Gradle, Android Gradle Plugin, Kotlin, Compose, Media3, Chaquopy, 앱용 파이썬과 numpy, Pillow, yt-dlp를 내려받음
- 단위 테스트: `.\gradlew.bat testDebugUnitTest`(브리지 결과 읽기, 시각 표기). 브리지 자체는 PC의 pytest(`tests/test_android_bridge.py`)로 확인

## 에뮬레이터

공식 Android 에뮬레이터는 Windows 하이퍼바이저 플랫폼(WHPX)으로 가속. `emulator -accel-check`가 사용 가능하다고 하면 그대로 사용(WSL2, Docker Desktop이 켜진 PC에서 확인). 사용할 수 없다고 하면 관리자 PowerShell에서 켠 뒤 재부팅

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform
```

```powershell
avdmanager create avd -n s2c -k "system-images;android-36;google_apis;x86_64" -d pixel_7
emulator -avd s2c -gpu host
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

- `-gpu host`: PC의 그래픽 칩 사용. 자동 선택이 소프트웨어 렌더러(SwiftShader)가 되면 Shorts의 흐린 배경 셰이더를 CPU가 처리해 매우 느림
- 에뮬레이터의 H.264 인코더는 소프트웨어라서 클립 제작이 실기기보다 느림
- 주소 입력: 에뮬레이터 키보드는 `adb shell input text`의 주소를 바꿔 입력하는 경우가 있어, 공유와 같은 경로로 전달

```powershell
adb shell am start -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT "https://chzzk.naver.com/video/VIDEO_NO" -n io.github.budongjw.stream2clip/.MainActivity
```

## 확인 내용

에뮬레이터(Android 16, x86_64)에서 실제 치지직 다시보기 1개로 확인

| &numsp;&numsp;&numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp;&numsp;&numsp; | 결과 |
|:---:|---|
| 하이라이트 찾기 | 방송 정보, 채팅 983개 수신, 하이라이트 10개까지 약 25초. 게임 이름(치지직 다시보기 정보), 채널, 근거(한국어) 표시 |
| 제목, 해시태그 | `[김목사] 방송 제목`, `#김목사 #버튜버 #치지직 #키리누키`(데스크톱과 같은 형식, 휴대폰 언어가 영어여도 방송 제목의 언어로) |
| 공유로 입력 | 문장 속 주소만 골라 입력 |
| Shorts 만들기 | 치지직 다시보기 스트림에서 90초 구간을 직접 읽어 제작 시작. 진행률 표시 |
| 첫 실행 | 파이썬 압축 해제를 배경에서 진행해 화면은 바로 표시 |

- 실기기(arm64)는 미검증. 실기기의 하드웨어 인코더 속도, 저장 후 갤러리 표시, YouTube 앱으로 공유는 다음 확인 대상

## 데스크톱과 다른 점

| &numsp;&numsp;&numsp;&numsp;&numsp;항&NoBreak;목&numsp;&numsp;&numsp;&numsp;&numsp; | 휴대폰 앱 |
|:---:|---|
| 검출 신호 | 채팅과 YouTube의 많이 다시 본 구간. 영상 음량, 웃음소리, 노래 구간 검출은 영상 전체를 받아야 해서 제외 |
| 자막 | 없음. 받아쓰기(faster-whisper)는 안드로이드용 휠이 없어 다음 단계(whisper.cpp 검토) |
| 제목 | 자막이 없어 방송 제목이 대사 자리에 들어감. 게시 전 수정 필요. 제목 언어는 방송 제목의 문자로 결정(자막 없는 데스크톱과 같은 방식) |
| 업로드 | 앱 안의 YouTube 업로드 없음. 공유 메뉴로 YouTube 앱에 전달 |
| 효과, 배경 음악 | 없음 |

## 라이선스

| &numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;구&NoBreak;성&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp;&numsp; | 라이선스 |
|:---:|---|
| Chaquopy | MIT |
| Media3, AndroidX, Jetpack Compose | Apache-2.0 |
| yt-dlp | Unlicense |
| numpy | BSD-3-Clause |
| Pillow | MIT-CMU |
| Kotlin 표준 라이브러리 | Apache-2.0 |
