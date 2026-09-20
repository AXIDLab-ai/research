# ODD+D · TRACE · STRESS 대응표

문서에 항목이 있다는 사실과 그 항목의 검증 완료를 구분한다. 기준 문헌: [ODD 2020](https://doi.org/10.18564/jasss.4259), [ODD+D](https://doi.org/10.1016/j.envsoft.2013.06.003), [TRACE](https://doi.org/10.1016/j.ecolmodel.2014.01.018), [STRESS](https://doi.org/10.1080/17477778.2018.1442155). 실제 투고 시 저널의 최신 요구와 원문을 함께 확인한다.

## ODD 7개 항목

| 항목 | 명세·구현 |
|---|---|
| 목적과 패턴 | ODD §1, protocol RQ, calibration.moments |
| 개체·상태·척도 | ODD §2, config.Config, model.Simulation |
| 과정·일정 | ODD §3, Simulation.step |
| 설계 개념 | ODD §4, model / observation / optional learning |
| 초기화 | ODD §5, Bundle / Simulation.__init__ / birth |
| 입력 | ODD §6, data.prepare_excel / Bundle |
| 하위모형 | ODD §7, scores / competing_offers / step / emit / survey_view |

## ODD+D 인간 의사결정 보완

다음은 ODD+D 질문을 본 연구에 대응시킨 구현 체크리스트이다. 공식 원문 질문의 번호나 문구를 그대로 전재한 목록은 아니다.

| 관점 | 구현 또는 명시적 범위 |
|---|---|
| 이론적 기반 | 평가 유인·불완전 정보·지원용량 제한, protocol |
| 개인 목표 | 운영사 noisy signal + 평가상 이점; 정부 장기 목적과 분리 |
| 선택 대안 | 공통 후보풀에서 제한된 quota만큼 제안 |
| 의사결정 규칙 | 경쟁 제안 및 후보의 무작위 선호 |
| 의사결정 시간 | 연초 배분·선택, 연말 실현, 다음 연도 반영 |
| 이질성 | 신호 정밀도, 지원역량, 초기 규모를 분리 |
| 정보·인지 제약 | noisy quality, misclassified speed, 과거 평가 스냅샷 |
| 예측 | logistic 평가 예상; 참 미래 결과 비공개 |
| 적응 | α와 λ에 따른 선택 변화; 기본형 학습 아님 |
| 상호작용·집단 | 후보 경쟁, 포트폴리오 내 용량 희석 |
| 근거·대안·불확실성 | 행동 파라미터 미식별, E4–E6, E7 별도 명세 |

## TRACE 8개 영역

| 영역 | 산출물·상태 |
|---|---|
| Problem formulation | 연구 질문, 정책행동과 장기 성과 명세 |
| Model description | ODD, 코드 대응표 |
| Data evaluation | prepare/audit 산출물; 원자료는 비공개 |
| Conceptual model evaluation | 27세계·영효과·가정 대안 명세; 전문가 검토 미수행 |
| Implementation verification | 필요 불변량 아래에 명시; 자동 테스트 미추가·미실행 |
| Model output verification | diagnose 구현; 회복·극단값·반복수 진단 실행 미수행 |
| Model analysis | E3–E7 구현; 논문용 전체 배치 미실행 |
| Model output corroboration | 시간 이전 진단 가능; 신규 독립자료에 의한 검증 없음 |

검증 시 확인할 불변량: 비음수 정수 quota 합=N; 기업 중복선정 없음; 미래정보 비사용; 동일 seed 재현; λ=0 정책 중복 결과 일치; age0 transition 없음; 흡수 퇴출; h1…H 합산; 동일 약정예산; N=0/J=1/후보부족 처리; 온라인 기록과 survey view 분리. 이 항목들은 향후 검증 요청 시 실행할 확인 대상이며 현 버전의 통과 기록이 아니다.

## STRESS 20개 공통 항목

| 항목 | 대응 |
|---|---|
| 1.1 목적 | protocol 연구 질문 |
| 1.2 출력 | reporting.METRICS 및 model.finish |
| 1.3 목표 | 조건부 기제와 정책순위 변화; 인과효과 아님 |
| 2.1 개념도 | README 과정도, ODD 구조 |
| 2.2 모형 논리 | ODD §3·7 |
| 2.3 시나리오 논리 | protocol E3–E6, experiments.variants |
| 2.4 알고리즘 | 전이 softmax, 경쟁제안, quota, LHS, Q-learning |
| 2.5 구성요소 | firms/operators/government/environment |
| 3.1 자료 출처 | metadata + source hash; 합성/실제 구분 |
| 3.2 입력 모수 | config, accepted.json, run spec |
| 3.3 전처리 | data.prepare_excel, E0 audit |
| 3.4 입력 가정 | ODD 입력·관측·bank borrowing |
| 4.1 초기화 | 공통 5년 이력; 정상상태 주장 없음 |
| 4.2 실행 길이 | warmup+cohorts−1+H 마지막 연도 |
| 4.3 추정 | 독립 반복·paired MCSE·precision plan |
| 5.1 소프트웨어 | requirements / pyproject / manifest versions |
| 5.2 난수 | SeedSequence namespaces, replicate IDs |
| 5.3 실행 | CLI plan/execute/resume, failures.jsonl |
| 5.4 하드웨어 | manifest platform; 자원 보고는 실행 환경에서 보완 |
| 6.1 코드 | 독립 저장소 패키지; 원자료 비공개, 합성 모드 제공 |

## 투고용 표·그림 흐름

1. 주분석: 정책 격자, 데이터 범위, 보정 적합성과 허용 집합, 두 주결과, 주분석 Pareto/regret.
2. 별도 robustness: 전이/배출/결측/시차/재표본 대안.
3. 별도 메커니즘 제거·반사실 모형 세계: α=0, θ=0, 시차=0 등. 실증 인과적 falsification으로 호칭하지 않음.
4. Discussion 직전 가설/명제 요약표: 기대 방향·필요 조건·실험 번호·증거 수준·지지 여부를 결과 확정 후 작성. 결과 없는 상태에서 지지 여부를 채우지 않음.

그림1은 질문·행위자·정보 흐름, 그림2는 latent state/online observation/survey view를 분리한 측정모형, 이후 그림은 연구 명제별로 배치한다. 결과가 나오기 전 개념도에 우월 정책이나 지지 결과를 넣지 않는다.
