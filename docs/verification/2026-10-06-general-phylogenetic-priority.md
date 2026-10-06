# 2026-10-06 전체 종 근연 관계 우선 비교

## 변경

오리 두 종의 특별 동점 규칙을 제거하고 활성 전체 종에 `taxonomy-phylogeny-ecology-v2`를 적용했다. 같은 속·같은 과를 우선하며, 같은 분류 범위에서 검증된 계통 합성 공통 조상 관계를 생태 점수보다 먼저 반영한다. 자료가 없는 종은 분류 자료로 표시하며 멀다고 단정하지 않는다. 표시 점수는 분류·생태 일치 점수로 명시했다.

Aves 1.6 / Clements2025 phylogeny-only 원본과 연구별 지원 주석을 고정 파일·해시로 검증했다. 실제 활성 AviList 11,131종의 taxon ID·학명·영어 이름을 공식 Extended XLSX와 대조한 뒤 Avibase 종 개념을 crosswalk에 연결했다. 9,518종에 근거가 적용되며 나머지 1,613종은 분류 자료로 표시한다. 분류 제약 연구 ot_2019/ot_2770, 추정 추가 종, 연구 tip 근거가 없는 종은 계통 근거로 쓰지 않는다. 원 연구 출처와 충돌 정보도 전달한다.

## 검증

- Python 전체: 548 tests, OK; 외부 통합 환경 조건에 따른 40 skipped.
- 프런트엔드 전체: 125 tests, pass 125, fail 0.
- 분류판·개념집합·taxon ID·학명 변경 시 기존 계통 근거 미적용.
- 파서 중복·미완성·다중 root·미지원 branch length 거부, polytomy 유지.
- 공식 XLSX와 활성 종 과학명/영문명/sequence 불일치 및 중복 거부.
- 고유 Avibase를 통한 공식 속 이동 허용; 식별자가 다른 분할·통합·중복 거부.
- 비분류 연구 근거 없는 조상 분기가 순위를 높이지 않음.
- synthetic topology에서 오리·해오라기·박새 등 동일 규칙으로 생태 점수보다 계통 근거 우선.
- 실제 고정 계통수에서 흰뺨검둥오리–청둥오리 관계가 고방오리보다 안쪽 공통 조상; 해오라기–Nankeen Night Heron 관계가 왜가리보다 안쪽 공통 조상.
- 실제 전체 후보 조사: 오리, 해오라기, 박새, 매류, 비둘기에서 서로 다른 계통 관계 순위 확인.
- graphify AST update 완료; git diff --check 통과.

## 협업

Orca run `run_ed90d2e734cb`: Claude 원본/지원 주석/분류 제약 연구 감사, GPT 고정 데이터 파서·종 개념 연결·runtime·검증 구현, Antigravity 독립 순위 정책 검토. 원본·적용 범위·재생성 명령은 `docs/phylogenetic-relations.md`에 기록했다. n8n 새 스케줄은 등록하지 않고 고정 공개 파일의 재현 가능한 수집 경로를 사용했다.

## NAS TEST 배포 및 공개 응답

- Code commit `595954e246e7ddd75550da3832d725b7b11d288a`, origin/dev push 완료.
- NAS release `/home/kimdove/RobinGraph-phylogeny-595954e`, image `robingraph-api:test-phylogeny-595954e`; OCI revision과 실제 TEST 컨테이너 이미지 일치 확인.
- Archive SHA-256 `980ecd5d87b2b6bb10068b513293ac870f026b2db29a37587b05113ed903ea81`; NAS archive/manifest 검증 완료.
- TEST preflight/update/verify 완료, health status ok/neo4j/test. PROD 변경 없음.
- 공개 https://robingraph-test.dove-nest.com : 배포 검증기 passed=true, OpenAPI/응답 계약 일치.
- `/v1/taxa/similar` 실제 5종 요청 모두 method v2, 전체 후보 11,130, coverage 9,518 확인.
- 흰뺨검둥오리: 청둥오리 → Indian Spot-billed Duck → Philippine Duck. 첫 두 종은 같은 계통 공통 조상 단계이며 서로의 표시 우열은 생태/학명 규칙으로 결정.
- 해오라기: Nankeen Night Heron 먼저 표시, 공통 조상 연구 2개. 같은 속의 계통 자료 없는 멸종 종은 분류 근거만 표시.
- Parus major: Parus cinereus(박새,80점) → Parus monticolus(작은노랑배박새,90점) → Pseudopodoces humilis. 생태 가점보다 계통 근거가 앞섬을 실제 응답에서 확인.
- Accipiter nisus: Accipiter rufiventris → A. striatus → A. madagascariensis.
- Columba livia: Columba rupestris(낭비둘기) → C. leuconota → C. oenas(분홍가슴비둘기).
- `/v1/chat` 흰뺨검둥오리 관련 종 질문: v2와 청둥오리 첫 후보, 규칙 설명·일치점수·근거 반환 확인.
- 공개 `/static/chat.js` SHA-256 `5c5a2bf4a6ac5f36dc7b951acbfc1b52697eeb8474e3a737149a3ba5d65ce6c1`가 현재 커밋 파일과 일치.
- Obsidian MCP 문서: `Work/RobinGraph/2026-10-06-전체종-근연관계우선-계통근거-NAS배포.md` 생성 및 Work/index 링크 추가.
