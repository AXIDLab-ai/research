# ODD: TIPS Policy Lab, research edition 1.0

This is the specification of the implemented model, not a claim of empirical verification. Monetary units are million nominal KRW for the original workbook and arbitrary units for synthetic data. Time is a calendar-year offset, not exact elapsed months.

## 1. Purpose and patterns

Question: under what conditions does the interaction of evaluation horizon, allocation intensity and intermediary adaptation change long-term portfolio outcomes? Main outcomes are operating profit accumulated over ages 1…H divided by a fixed committed budget, and the number of firms attaining two adjacent positive-profit years within 1…H. These are neither equity value nor social welfare, EBITDA, IRR or identified additionality of TIPS.

Calibration patterns: state occupancy, financial distribution quantiles, zeros, recorded closure, missing finance and adjacent-state changes. The measured sector/cohort composition and operator-size distribution initialise the model. They are not evidence of operator ability. Data describe selected firms; the hypothetical applicant pool is a scenario assumption.

## 2. Entities, state variables and scales

- **Firm:** candidate ID, birth cohort, sector, latent quality q, true speed class τ, noisy observed speed, operator, financial state, duration in state, AR(1) shock, cumulative profit and evaluation records.
- **Financial states:** 0 = low revenue/nonpositive profit; 1 = high revenue/nonpositive profit; 2 = low revenue/positive profit; 3 = high revenue/positive profit; 4 = absorbing exit. Threshold is configurable. These are financial states, not observed clinical, certification or technology milestones. Missingness is not a sixth economic state.
- **Operator:** annual integer quota, portfolio, sector-specific signal precision, sector-specific support ability and capacity. Precision and ability are generated separately, with configurable correlation. Initial size is independent of ability.
- **Government:** quota weights, evaluation window, observed snapshots, shrinkage prior and allocation rule. It cannot see q, true speed, future outcomes or the retrospective survey mask.
- **Environment:** hypothetical entrants, sector composition, common macro shocks and fixed per-entry public cost. No geography, market equilibrium or firm-to-firm knowledge spillovers.
- **Research scale:** J=50, N=400; 5 common-history years, 10 intervention cohorts, last-cohort follow-up H=8. The app uses a smaller explicit demonstration scale. Initial history is not claimed to establish stationarity.

## 3. Process overview and scheduling

One tick is one year. At t:

1. Score evaluation snapshots from years t−window…t−1. No current-year outcome is used.
2. Update quota weights and allocate integers by largest remainder, with seeded tie-breaking.
3. Generate a shared candidate pool; give each operator noisy quality signals.
4. Operators simultaneously offer places to their preferred available candidates. Firms with multiple offers use a pre-generated random preference; unfilled operators offer again. A firm receives at most one place.
5. Count all living firms within the support period; allocate operator capacity equally. Age-zero firms consume capacity but have no same-year transition or support-induced outcome change.
6. Existing firms transition and emit joint revenue/profit. New firms draw their initial state and initial emissions.
7. Generate online missingness and detected closure. Store due evaluation snapshots; update accounting and duration.
8. Advance to t+1. Last entry is warmup+cohorts−1; last tick is that year+H. Base tail stops entry. Continuing-tail sensitivity includes the resulting support dilution and reports tail cost separately.

## 4. Design concepts

**Emergence:** selection composition, long-term performance, concentration and slow-firm shares follow interaction. No preferred-policy advantage is inserted into the ranking.

**Adaptation:** an operator combines a noisy quality signal x with an evaluation incentive αλ logistic(x + 0.5(h−observed delay)). The coefficient and α are assumptions, not estimated behaviour. Firms do not manipulate accounts. α=0 removes adaptation.

**Objectives:** operator utility is a transparent score, not a structural VC return model. Government policy comparisons use two separately reported long-run outcomes, without an arbitrary weighted welfare sum.

**Learning:** the base model updates scores, not beliefs about true ability. Optional E7 is a separate tabular Q-learning extension; it does not alter the base model.

**Prediction and sensing:** operators see noisy quality and speed, not future realised states. Government sees only allowed past snapshots. A scenario that improves speed classification does not reveal latent quality or future exits.

**Interaction:** common candidate competition and capacity dilution within portfolios. **Collectives:** operator portfolios; sectors have no independent agency.

**Stochasticity:** PCG64 via NumPy SeedSequence with (seed, replicate, channel, year, cohort). Candidate IDs index complete candidate arrays before policy selection. Macro, transitions, emissions, observations and preferences have separate channels. Parameter changes that change population dimensions are not claimed to preserve identical individuals.

**Observation:** latent model ledger, online actor observations, and retrospective survey view are distinct. Missing financial observations never become failed firms. In the model ledger only, post-exit economic flows are zero. No such zero is imputed into empirical financial records.

## 5. Initialisation

Sectors C/J/M/G/Other and initial state frequencies come from the declared calibration split, with pseudocounts. Operator initial size weights are resampled from the observed selected-firm size distribution. Sector weights have a configurable tilt.

Candidate q is standard normal. Delay propensity has correlation ρ with q and is cut at −0.43, +0.43 into 2/3/5-year classes. Observed speed flips to either other class with the specified error probability. Speed classes are hypothetical; KSIC does not identify true commercialisation time.

`sector_delay_shift` adds a configurable offset to each sector's delay propensity (C/J/M/G/Other). Its default is zero for every sector; any nonzero sector ordering is a stated scenario, not an inferred technological ranking. Firms continue evolving until the simulation's final tick even after their outcome window H ends, so later exits can still affect archived evaluations. Only ages 1…H enter the primary outcome.

Signal noise is signal_noise × exp(−0.25a). Support ability is exp(0.3b−0.045). a and b are normal with configurable correlation. Capacity K_j = max(N × support_years × initial_weight_j, tiny). Homogeneous-ability and no-dilution experiments remove those mechanisms separately.

## 6. Input data

`prepare` reads the original workbook's `창업기업RAW`, header row 3, selection P, operator C, broad sector T, closure K/L, annual revenue GO:GZ, profit IS:JD, assets JE:JP and employment FB:FM. Raw company names are not exported, but pseudonymised histories remain private. The current source layout is explicit and is not a general-purpose spreadsheet schema detector.

Preselection observations are excluded. All final-analysis flags are retained. Triple-zero finances have retain/unknown alternatives. Recorded closure year is not moved earlier; suspended, M&A and listed flags are retained separately. Missing closure date is counted, not imputed. Positive finance in the recorded closure year is treated as ambiguous for transition-kernel estimation.

Calibration split: cohorts ≤2019 and ages 0–2. The next observed adjacent-year state gives a transition count. A sector row is shrunk toward the pooled row with strength 10; pooled cells start at 0.5. Initial-state cells start at 0.5. Exit is absorbing. Sparse state emissions borrow the pooled same-state bank when sector n<5; an empty pooled state raises an error rather than inventing private-data values.

## 7. Submodels

### Evaluation and allocation

Eligible means evaluated within the most recent five evaluation years, not five entry cohorts. Unknown cases receive δ in {0, 0.5, 1}, or are excluded from the denominator. Score = (sum known successes + δ × unknown + κp0)/(eligible + κ). Empty denominator returns p0. Detected exit at the evaluation date scores zero. The optional erasure rule removes archived snapshots only after a firm's actual simulated exit has occurred.

w_t = (1−λ)w_(t−1) + λ[(1−ε)softmax(βS) + ε/J]. β=2, κ=5, p0=0.5 by default. Equal allocation is a separate benchmark. Fixed allocation is λ=0. Its duplicate horizon/exploration settings are omitted, giving 37 distinct grid policies. Warmup uses the same fixed policy and h=3 for all comparisons.

### Semi-Markov transition

For sector s, source state z, destination k, logits are log(B_s,z,k) + A_i,t × d_k plus fitted revenue/profit/exit intercepts, where d = (−0.3, 0.3, 0.3, 0.7, −0.5). A combines quality, capped age, capped duration, timing relative to speed, macro shock, AR(1) firm shock and support_effect × ability × effort. Softmax normalises the row. Exit remains absorbing. Different positive destinations can be reached directly; regression is allowed. Duration adds semi-Markov dependence but its coefficient is a scenario/nuisance parameter, not an identified hazard mechanism.

Support effort = min(1,K/A) for ages less than support_years, else zero; no-dilution sets effort=1 during eligibility. True q affects dynamics, never government scores directly. `age_effect`, `duration_effect` and three intercepts are nuisance parameters explored by calibration. Operator support effect, adaptation and quality–delay correlation define structural worlds and are not identified from this selected sample.

### Financial emissions

Within a state, sort the empirical joint revenue/profit bank by profit and select by a normal-CDF rank formed from quality, persistent shock and an independent innovation. Joint pairs preserve observed dependence and exact zeros/negative values. Alternative independent draws break joint dependence; the zero-mass-preserving signed lognormal alternative changes tails and clips values back to the state's definition. All financial emissions use calibration-split observations only. Bank borrowing and static early-age banks constrain extrapolation, particularly at ages 6–10.

### Online and survey observation

Online missingness uses an assumed annual rate; recorded closure is detected with configurable probability. A due snapshot is frozen except for the explicit erase-after-exit alternative. Two-year-profit evaluation requires observed adjacent years.

`survey_view` masks financial history conditional on the firm's final simulated recorded exit status, using rates from retrospective empirical histories. It is a parsimonious observation model, not a reconstruction of survey response dates or government archival systems. Different empirical follow-up lengths make this approximation material; online scoring never uses it.

### Long-term accounting and optional learning

Sum profit over ages 1…H, optionally discounted by age. Sustained-profit attainment persists after a later exit. Budget denominator is promised N×cohorts×unit_cost, not only filled places; spent and unused budgets are reported. Quality is a latent diagnostic only.

E7 restricts actions to λ×ε combinations. Q states discretise past score mean/dispersion, unknown share, concentration and elapsed decision period. Training reward uses observed online profits, with missing=0 explicitly treated as a normative proxy. Tail rewards are delayed to the last decision. Separate seed namespaces train and evaluate against fixed/common3 policies. The finite discretisation is partially observed and is not a proof of optimal policy; the base 37-policy study remains primary.
