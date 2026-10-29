# 도감 팝업 재오픈 실제 TEST 검증

- 2026-10-29 actual TEST /chat, Chromium headless CDP. API mock 없음. 대상 녹색비둘기 Treron sieboldii.
- 수정 전 390×844에서 닫힌 구성표 scale 0.833333, 펼침 scale 유지, 팝업 닫고 재오픈하면 앞면 scale 0.700088로 축소. details.open이 유지되지만 collapsedFitHeight를 초기화하여 펼친 높이를 새 기준으로 측정함.
- 수정 후 390×844 및 1280×800 각각 구성표 2개 펼침 → 팝업 닫기 → 재오픈 3회 확인. 매회 토글 닫힘·앞면 초기화·첫 baseline scale 복원·Enter 뒷면 전환 모두 통과. 양쪽 dialog 가로 범위 정상, 문서 가로 넘침 없음.
- 추가: 팝업 닫힌 동안 390→1280 viewport 변경 후 재오픈 정상. 새 1280 baseline과 다시 펼치고 닫은 재오픈 scale 동일, 토글 닫힘·앞면 정상.
- 최초 재현 popup-browser-results.json, 수정 후 popup-browser-after-results.json, 닫힌 resize popup-browser-resize-results.json. screenshots/reopened-before.png는 수정 전 앞면, reopened-390.png/reopened-1280.png는 반복 확인 후 Enter로 돌아간 뒷면, closed-resize-1280.png는 닫힌 resize 후 재오픈 앞면.
- 실제 다른 종으로 전환하는 브라우저 검증과 물리 모바일·Safari·Firefox는 미실행. 같은 카드 반복 재오픈 및 닫힌 viewport 변경은 실측. 사진 외부 로드 실패가 있었지만 카드 fit 검증과 분리.
- 코드 외 검증용 수정 없음. 서명 토큰·전체 API 응답 저장 없음. 검증 Chromium 종료.
