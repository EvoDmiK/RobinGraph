# 국내 통칭·이칭 및 닭 품종 이름 추가 조사

검토일: 2026-10-03. 후보 파일은 `additional-name-candidates.json`이다. 실제 API에서 사용하는 승인 자료는 `src/robingraph/retrieval/name_relations.json`이며, 조사는 최초 네 예시로 제한하지 않는다.

| 조사 이름 | 연결 대상 | 검증 방식 |
|---|---|---|
| 학·단정학·선학 | Grus japonensis | [한국학중앙연구원 두루미 항목](https://encykorea.aks.ac.kr/Article/E0060759)의 이칭과 학명 직접 확인 |
| 공작·남객·월조·화리 | Pavo cristatus | [한국학중앙연구원 공작 항목](https://encykorea.aks.ac.kr/Article/E0004423)의 이름과 학명 확인. 단순 관상 사육을 가축화로 판정하지 않음 |
| 백조 | Cygnus columbianus, Cygnus cygnus, Cygnus olor | [백조 항목](https://encykorea.aks.ac.kr/Article/E0022384)의 국내 세 후보와 [NIBR 조류 센서스](https://www.nibr.go.kr/aiibook/catImage/12/2015-2016.pdf)의 국명·학명 대조 |
| 백로 | Ardea alba, Ardea intermedia, Egretta garzetta | [백로 항목](https://encykorea.aks.ac.kr/Article/E0022091)의 통칭 범위와 [NIBR 한국의 백로 번식지](https://www.nibr.go.kr/aiibook/access/ecatalogt.jsp?Dir=1055&callmode=admin&catimage=&eclang=ko&start=14&um=s)의 학명 대조 |
| 오골계·백봉오골계·연산오계 | 가축 닭 품종 → Gallus gallus 기원 관계 | [오골계 항목](https://encykorea.aks.ac.kr/Article/E0038105)이 가축 닭과 서로 다른 품종 이름을 명시. [Wang et al. 닭 기원 연구](https://www.nature.com/articles/s41422-020-0349-y)와 연결하는 두 단계의 편집적 매핑 |
| 토종닭 | 가축 닭 계통 → Gallus gallus 기원 관계 | [국립축산과학원 토종닭 복원·산업화](https://nias.go.kr/front/soboarddown.do?boardSeqNum=311&cmCode=M090814151125016&fileSeqNum=326)의 토종닭 개념 확인. 원종 연결은 위 닭 연구를 통한 편집적 매핑 |
| 재래닭 | 가축 닭 계통 → Gallus gallus 기원 관계 | [국립축산과학원 유전자원 보유 현황](https://nias.go.kr/front/soboarddown.do?boardSeqNum=8003&cmCode=M091023193927309&fileSeqNum=3791)에 기록된 이름. 토종닭·교배계와 같은 품종으로 병합하지 않음 |

## 범위와 보류

- 백조·백로 후보는 위 자료에서 확인한 국내 범위다. 전 세계 고니류·백로과 종을 전부 수록한 목록으로 표시하지 않는다.
- 문화적 이칭은 검색어로만 연결한다. 옛 생태 기술, 현재 법적 보호 등급, 약효, 장수 관련 민속 주장을 형질 데이터로 전환하지 않는다.
- 품종 이름은 독립된 이름 노드로 유지한다. 해당 이름이 야생 아종이라는 주장이나 품종 사진·체중·보전 등급의 대체는 하지 않는다.
- 백공작·흰 비둘기는 색상만으로 종이나 가축형을 확정할 수 없어 보류한다. 국내 명칭 자료와 기원 자료가 확보되면 서로 다른 후보를 구분해 추가한다.
- 특정 가금 브랜드·교잡 품종과 서양 닭·오리 품종 전체는 개별 근거를 검토하기 전까지 추가하지 않는다.
- 승인 대상 학명은 프로젝트가 고정한 AviList v2025b 원본과 대조한다. NAS에서의 적용 여부는 별도의 배포 검증 사항이다.
