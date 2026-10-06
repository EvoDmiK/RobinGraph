# 근연 관계 가중합 점수

`taxonomy-phylogeny-ecology-v3`: 계통 50 + 분류 30(같은 속 20·같은 과 10) + 서식 환경 10 + 먹이 생태 10. 전체 후보를 점수 내림차순으로 정렬한다. 공통 조상 단계의 순서를 k/N으로 정규화하며 depth 숫자 간격을 거리로 쓰지 않는다. 같은 공통 조상은 같은 계통 기여를 받는다. 계통 자료가 없으면 해당 항목을 제외하고 나머지 50%를 100점으로 환산하며 화면·API·채팅에 분류·생태 대체 점수와 자료 부족을 표시한다. 가중치는 초기 서비스 정책이며 진화 거리나 확률을 측정한 값은 아니다. 자세한 계약은 `docs/phylogenetic-relations.md`에 기록했다.

## 검증

- Python 전체 실제 DB 통합 포함: 549 실행, 실패 0, 오류 0, 건너뛰기 0.
- 프런트엔드 전체: 126 통과, 실패 0, 건너뛰기 0.
- 상대 공통 조상 점수·생태 동점 해소·depth 숫자 간격 불변·대체 점수·소수점 API/화면 표시·기여 합과 총점 검증.
- TEST DB와 분리한 일회용 Neo4j 컨테이너 및 PostgreSQL 스키마에서 검증하고 정리했다. 기존 Fixture 555개와 논문 노드 168개 유지 확인.
- graphify AST update 및 git diff --check 완료.

## NAS TEST 배포

- Runtime commit `f1a1e60d063b0b4632cbb38fa20e559993d1b716`, origin/dev push 완료.
- NAS `/home/kimdove/RobinGraph-weighted-f1a1e60`, image `robingraph-api:test-weighted-f1a1e60` healthy. 이미지 OCI revision 일치 확인. PROD 기존 image 유지.
- Archive SHA-256 `c18eed6e87a8ace6ad1634e319f41531d43c90a75758e3184099130bf7eb3fc1`, 전송 후 archive 및 manifest 107개 파일 검증 완료.
- TEST preflight/update/verify 및 공개 배포 계약 검증 passed=true.
- 공개 API 실제 5종 모두 v3·가중치·점수 내림차순·기여 합·자료 범위 메타데이터 검증. 채팅도 v3와 소수점 점수를 반환한다.
- 흰뺨검둥오리: 청둥오리 100 → Indian Spot-billed Duck 100 → Philippine Duck 98.21.
- 해오라기: Nankeen Night Heron 100 → Calherodius leuconotus 75.24 → Egretta caerulea 75.24.
- Parus major: 작은노랑배박새 88.48 → 박새(Parus cinereus) 80 → Machlolophus nuchalis 75.45. 가중합 전환으로 생태 가점이 최종 순위에 영향을 주는 실제 사례다.
- Accipiter nisus: Accipiter rufiventris 100 → A. striatus 98.08 → A. madagascariensis 96.15.
- 집비둘기: 낭비둘기 90 → Columba leuconota 87.37 → Columba guinea 84.74.
- 계통 자료가 없는 Nycticorax mauritianus 조회: 상위 후보 모두 60점, taxonomy_ecology_fallback·phylogeny_available=false·available_weight=50 확인.
