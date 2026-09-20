# Model card — TIPS Policy Lab 1.0

## Intended use

Conditional policy-mechanism research: evaluation horizon × allocation intensity × intermediary adaptation. Interactive exploration in Streamlit; calibrated replicated experiments via Python CLI. Research questions concern evaluation design and long-term portfolio performance under stated assumptions.

## Not supported

Causal treatment effects of TIPS, official compliance evaluation, company-specific investment advice, firm valuation, EBITDA, leverage effects, IRR, identifiable optimal policy or unconditional welfare. Selected-firm observations do not identify the applicant/rejected-firm counterfactual. Industry codes do not identify actual technology stages or true commercialisation times.

## Inputs and privacy

Public default data are generated from a transparent synthetic process and contain no real firm records. The original workbook is processed locally into ignored `data_private` or, if enabled by the deployer, in a Streamlit user session. Pseudonymised firm/operator histories remain private. Source layout, hash, units and zero/closure rules accompany processing. Only synthetic bundles are globally cached.

## Model and evidence

Five financial states; absorbing exit; duration-dependent transition logits; sector pooled empirical kernels; joint conditional revenue/profit emissions; separate precision/support capacities; shared candidate competition; past-information-only allocation; separate online and survey observations.

Observation-based quantities include selected composition and financial patterns. Support effect, operator adaptation, candidate quality and speed, their correlation, applicant pool and online archival properties are assumptions. Nuisance parameters are calibrated within structural worlds. Empty admissible sets are not replaced by best fits.

## Outputs and uncertainty

Primary: accumulated age-1-to-H operating profit per fixed committed budget and sustained-profit attainment counts. Unit cost 1 is a normalisation, not observed public cost. Asset write-offs, capital distributions and exit proceeds are not modelled. Auxiliary: revenue, exit, concentration, speed share and latent quality diagnostics.

MCSE reflects random simulation uncertainty only. Bootstrap inputs, admissible parameter sets, structural worlds and normative choices remain separate. Regret and Pareto comparisons are conditional on the enumerated options and worlds; scenario shares are not probabilities.

## Status

Research implementation; original-input preparation performed locally. Automatic tests, synthetic recovery, full empirical calibration, policy batches and deployment verification have not been performed for this edition. See IMPLEMENTATION_STATUS.md. No empirical policy recommendation is shipped with the code.
