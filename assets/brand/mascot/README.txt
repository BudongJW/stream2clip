stream2clip 마스코트 키리 SD 이모트 5종 (컨셉 v0.2)

kiri_wink      윙크: 기본, 인사
kiri_laugh     빵 터짐: 웃긴 장면
kiri_surprised 깜짝: 반전, 사고
kiri_cut       컷: 클립 완성
kiri_focus     편집 집중: 작업 중, 로딩

크기: 512, 112, 56, 28px, 투명 배경 PNG
원본: source 폴더의 kiri_<이름>.png (이모트별 1장)
기록: source/manifest.json (이모트 목록, 원본별 생성 도구, 프롬프트, 시드, 배경 처리 방식)
생성: Qwen-Image(시안 A)로 생성 후 Krea Flux Kontext Dev로 표정 편집. v0.1 원본의 프롬프트와 시드는 미기록

제작 절차
- 이 폴더의 PNG는 직접 고치지 않음. 원본을 바꾼 후 아래 명령으로 다시 생성
    python packaging/build_mascot.py
- 처리 순서: 배경 제거, 가장자리 정리, 크기별 축소, 앱에 넣는 크기(112, 56px)를 src/stream2clip/gui/assets에 복사
- 생성 결과 확인: 어두운 배경과 밝은 배경에 올린 그림 저장
    python packaging/build_mascot.py --sheet sheet.png
- 원본과 생성물의 일치 검사
    python packaging/build_mascot.py --check

새 이모트 추가
- 원본 조건: 정사각형, 512px 이상, 캐릭터 1명, 이모트 1개당 1장
- 배경: 캐릭터에 없는 단색 권장(초록 #00FF00). 흰색이나 크림색 배경은 후드와 구분되지 않아 함께 지워짐
- 등록
    python packaging/build_mascot.py --add 이름 원본.png --background #00FF00 --generator "도구 이름" --prompt "프롬프트" --seed 시드
- --background 값: auto(이미 투명한 그림은 그대로, 단색 배경은 테두리에서 안쪽으로 제거), transparent(투명도 유지), #RRGGBB(해당 색을 그림 전체에서 제거)
- 앱에 표시하려면 src/stream2clip/gui/qt.py의 MOODS와 표시 위치 코드에 이름 추가 필요
- 생성 도구, 프롬프트, 시드를 함께 기록해야 같은 캐릭터로 다시 제작 가능

캐릭터 기준 (새 그림 생성 시 유지할 항목)
- 분홍 단발, 앞머리, 노란 마름모 머리핀
- 검은 고양이 귀 헤드폰(귀 안쪽 노랑, 이어컵 분홍 포인트)
- 크림색 후드, 소매의 분홍 가위 무늬
- 굵은 검은 외곽선, 단색 채색의 SD 비율 상반신

유의 사항
- v0.2에서 가장자리의 연보라색 테두리 제거(v0.1 원본의 바깥 2px을 안쪽으로 정리)
- 그림이 화면 밖으로 잘린 부분(깜짝의 효과선, 컷의 왼쪽)은 원본 그대로이며 다시 생성해야 해결
- 방송 플랫폼에 업로드하기 전 각 플랫폼의 이모트 규격과 AI 생성물 정책 확인 필요
