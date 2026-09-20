# 문헌 대비 위치와 명제의 사전 명세

기존 연구설계에서 검토한 문헌을 코드의 메커니즘과 연결한다. 이 문서는 새로운 체계적 문헌고찰이 아니며 아래 논문의 모든 본문·부록을 재검증했다는 뜻이 아니다. 논문 제출 전에 직접적인 선행 시뮬레이션과 최신 인접 연구를 대조해야 한다.

## 알려진 선행 기여와 이번 연구가 추가로 보여야 할 것

| 선행 영역 | 이미 알려진 점 | 이번 연구의 추가 증거 후보 |
|---|---|---|
| 성장·수익성의 시간적 관계 | 성장과 수익성의 순서·성과 상태 전이는 기존 주제 | 평가 시점의 차이가 중개자 적응·후속 배분을 거쳐 장기 결과를 바꾸는 조건 |
| 창업 보조금과 장기 성과 | 자원축적·장기 성과·정책수단 비교는 기존 주제 | 같은 약정예산에서 기한×배분강도×운영사 적응의 결합 |
| 공공·민간 하이브리드 VC | 인센티브 구조를 시뮬레이션한 선례 존재 | 보상분배 계약 대신 평가·추천권 피드백과 지연형 선별의 연결 |
| 실패의 과소 관측 | 실패 누락의 학습 편의는 이미 알려짐 | 과거 기록 보존과 온라인 정보가 정책 반응 경로에 미치는 조건부 차이 |
| 다중과업 대리인 | 측정 가능한 과업에 대한 유인 편향은 기존 이론 | 지원 희석·후보 경쟁·시차와 만날 때의 경계 조건 |

## 결과를 보기 전 명제 틀

다음은 결과가 아니라 실험으로 평가할 조건부 명제다. 식별되지 않은 조건을 숨긴 무조건적 가설로 바꾸지 않는다.

| 명제 | 필요한 조건·반례 | 실험·관찰량 |
|---|---|---|
| P1: 짧은 평가와 강한 배분 반응은 지연형의 선정 비중을 낮출 수 있다 | α>0, 평가 예상에 시차가 반영됨. 속도 정보오류가 경로를 약화시킬 수 있음 | h×λ×α, slow_share |
| P2: 지연형 비중 감소가 장기 성과 악화로 이어지는지는 잠재력–지연 관계에 달린다 | ρ<0이면 방향이 반대일 수 있음. 느린 기업이 더 우수하다고 가정하지 않음 | ρ 세계별 두 주결과·regret |
| P3: 집중 배분의 이익은 좋은 선별/지원과 용량 희석 사이의 관계에 달린다 | θ=0, 능력 동일, 희석 없음 등에서 경로가 바뀔 수 있음 | 능력·지원·희석 제거, HHI와 성과 |
| P4: 차등 평가나 탐색 몫의 우위는 정보의 질과 행동 반응에 의존한다 | 속도 분류가 부정확하거나 반응이 약하면 이점이 줄거나 역전 가능 | 오분류·신호·α, Pareto와 regret |
| P5: 실패 후 기록 소실은 평가와 배분의 경로를 바꿀 수 있다 | 영향 방향은 unknown 처리·기준 지표에 의존; 항상 상향 편의라 단정하지 않음 | archive×δ×metric |

지원 여부 칸은 본실험 이후 채운다. E1의 관측자료 재평가, E3의 모형 조건부 결과, E4–E6의 민감도는 서로 다른 근거이다. 명제의 기제가 코드에 정의돼 있다는 사실만으로 명제의 실증적 지지를 얻는 것은 아니다.

## 핵심 참고문헌

- Davidsson, Steffens & Fitzsimmons (2009), *Growing profitable or growing from profits?* [JBV](https://doi.org/10.1016/j.jbusvent.2008.04.003).
- Steffens, Davidsson & Fitzsimmons (2009), *Performance Configurations over Time.* [ETP](https://doi.org/10.1111/j.1540-6520.2008.00283.x).
- Söderblom et al. (2015), *Inside the black box of outcome additionality.* [Research Policy](https://doi.org/10.1016/j.respol.2015.05.009).
- Hottenrott & Richstein (2020), *Start-up subsidies: Does the policy instrument matter?* [Research Policy](https://doi.org/10.1016/j.respol.2019.103888).
- Jääskeläinen, Maula & Murray (2007), *Profit distribution and compensation structures in publicly and privately funded hybrid venture capital funds.* [Research Policy](https://doi.org/10.1016/j.respol.2007.02.021). 직접적인 선행 시뮬레이션의 전체 가정 대조가 중요하다.
- Denrell (2003), *Vicarious Learning, Undersampling of Failure, and the Myths of Management.* [Organization Science](https://doi.org/10.1287/orsc.14.2.227.15164).
- Kerr, Nanda & Rhodes-Kropf (2014), *Entrepreneurship as Experimentation.* [JEP](https://doi.org/10.1257/jep.28.3.25).
- Holmström & Milgrom (1991), *Multitask Principal–Agent Analyses.* [JLEO](https://doi.org/10.1093/jleo/7.special_issue.24).
- Nosek et al. (2018), *The preregistration revolution.* [PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC5856500/).

RP는 정책 설계와 중개구조의 조건에 초점을 둘 때, JBV는 투자자의 선택·벤처 성장 이론을 직접 확장할 때 더 자연스러운 후보이다. 어느 저널이든 단순 시뮬레이터 제작이나 지표 보정 자체만으로 이론적 기여를 확보하지 못한다.
