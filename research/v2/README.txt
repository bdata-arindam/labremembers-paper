# V2: bounded preplanned confirmation on OPV-informed emulators

This extension uses measured quaternary organic photovoltaic formulation data to construct two explicitly labeled response emulators. It combines them with synthetic carryover, known Gaussian observation noise and assumed resource costs. Neither the response emulator nor the original OPV measurements verify a physical carryover mechanism.

The completed frozen run contains **3,200 main case–campaign scenarios and 1,600 predeclared sensitivity scenarios**, each evaluated by thirteen policies, for **62,400 policy runs**. There are 200 independent report seed values, reused across cases; pooled independence is not claimed. The main run took about 486 seconds in the execution environment.

## Reproduce

Keep this directory under `research/v2/` and retain the sibling project directory `application/`, which supplies measured data and the independent Delaunay emulator.

```bash
python opv_bernstein.py
python -m unittest -v test_v2.py
python run_v2.py
python make_v2_figures.py
python audit_noise_coverage.py
python write_v2_results.py
```

The first command repeats the exact prespecified cubic-family development selection and held-out validation. Report coefficients and validation outcomes were locked before policy evaluation; no response-family tuning was performed after seeing held-out fidelity or policy outcomes. Run these commands in a copied project directory to preserve the frozen originals.

The complete notebook in `../notebook/` performs this reproduction and the entire v1 study in a separate output tree, including measured-data reanalysis, proofs, all case tables, figures, logs and comparisons with frozen results.

## What is new

The earlier covariance-based adaptive policy did not establish an advantage over repetition with the same history model. The v2 extension adds a stronger prespecified discard-four repetition control, conditional bias-aware intervals and a preparation planner that chooses its entire schedule before observing confirmation outcomes.

The planner receives only a scalar response Lipschitz certificate, apparatus parameter bounds, noise level and costs. It never receives emulator coefficients, actual residual composition or clean response values. The scientific target is whether a frozen nominal recipe has fresh-emulator degradation at most 0.10, an illustrative criterion. Candidate recipes have total donor fraction between 1/6 and 5/6, matching the source paper's donor:acceptor eligibility restriction.

## Measured data and emulator limits

Each system has 1,041 HTE rows and 1,021 unique compositions. Duplicate measurements are grouped by composition for emulator fitting, while raw replicate values remain available in `application/`. The two material systems share measurements on the zero-second-donor face, so they are not fully independent material replications.

The prespecified cubic Bernstein fit uses 715 training, 152 validation and 154 test composition groups per system. Both systems selected ridge strength 0.01 on validation MAE. Held-out MAE is approximately 0.04390 for PBQ-QF and 0.05097 for PTB7-Th, with R² approximately 0.606 and 0.485. These errors are material relative to the 0.10 criterion. They prevent interpreting an emulator confidence interval as a real-material certificate.

The cubic emulators' global L1 bounds are 1.66314 and 1.88188. For standard degree-p Bernstein coefficients, the certificate is half p times the largest range among coefficient neighbors associated with a degree-(p−1) multi-index. The proof uses the gradient range on the simplex tangent space. The much larger bounds of the independently fixed piecewise-affine emulator are retained in sensitivity cases, including their resulting conservatism.

No predictions or measured losses are clamped to 0–1. Observation noise is added after latent evaluation. The assumed independent Gaussian standard deviation of 0.03 is a simulation condition; the measured replicate distribution does not establish this calibration.

## Confidence construction and its scope

For a shared-line candidate assay with k washes, the retained-fraction bound is `r_bar=rho_upper*eta_upper**k`. Starting from distance bound `D=2` in the L1 simplex norm, the predictable response-bias bound is `B=L*r_bar*D`, followed by the distance update `D=(1-lambda_lower*(1-r_bar))*D`. Fresh assays have zero modeled bias and leave the shared-line distance unchanged.

Every bounded primary schedule and any discard rule is chosen before confirmation outcomes. Its final interval is the mean retained observation plus or minus the sum of the mean bias bound and `1.959963984540054*sigma/sqrt(n)`. This has conditional coverage at least 95% for the frozen emulator response under the stated parameter, response-regularity and independent-Gaussian assumptions. It is not an optional-stopping guarantee, a guarantee about false fraction among accepted claims, or a certificate for the unknown physical material.

The separate theorem in `../theory_note.md` also gives a finite-horizon simultaneous sub-Gaussian construction. That radius is distinguished from the fixed-final Gaussian interval used in this experiment.

### Restricted optimality of the planner

The menu contains routine, one-wash, three-wash and independent fresh candidate assays. For each feasible integer count tuple, the planner puts stronger washes first and fresh assays last. The adjacent-swap identity proves that this order minimizes summed bias bounds for those fixed counts, while the downstream distance bound is unchanged. Exhaustive count enumeration then minimizes the final half-width within this menu of fixed schedules using all observations equally.

This optimality does not cover adaptive policies, discarded samples, unequal weighting or response-model-based estimators. The bounded discard-four repetition control can outperform it and remains a primary comparator. Realized spending may be below the budget cap. Fresh placement is immaterial to the final equal-weight objective but can affect an early-stopping objective, which was not executed here.

At equal fresh and routine cost, fresh preparation weakly dominates this certified-width objective: it offers zero modeled bias and the maximum affordable number of observations. The equal-cost sensitivity is therefore an essential domain boundary, rather than a calibrated OPV cost claim.

## Cases and controls

The eight main cases per system include zero, 0.001, 0.01, 0.10 and 0.40 carryover fractions, ineffective washing, moderately persistent memory (lambda 0.45) and strongly persistent memory (lambda 0.05). The final case is an intentionally severe, uncalibrated stress. Main confirmation budget is 32 assumed units. Routine assays cost one, a wash 0.5 and independent fresh preparation four by default.

Thirteen policies include sequence replay, naive repetition, naive discard-four repetition, naive wash/fresh controls, history-model repetition, adaptive covariance controls, the same adaptive rule with conditioning removed, bounded repetition, bounded discard-four repetition, bounded wash/fresh controls and the preplanned policy.

Four predeclared sensitivity groups use the first 100 primary report seeds in the low/high-carryover cases of both systems: the Delaunay emulator, broad apparatus bounds, empirical replicate-contrast noise and equal fresh/routine cost. The empirical-noise sensitivity deliberately violates the main Gaussian/noise-bound assumption. It preserves observed contrast outliers and is not a verified model of real laboratory noise.

All methods within a campaign share the Gaussian or resampled noise draw at a given assay index. Routine, tail and bounded-repetition comparisons therefore have identical underlying observations. Results across cases share this noise block and are not independent calibration repetitions.

## Observed coverage shortfall

The finite report block does not attain nominal 95% coverage in every case. In the PBQ-QF no-carryover case, the bounded discard-four interval covers 183 of 200 candidates (91.5%), and the independent-fresh interval covers 186 of 200 (93%). The corresponding low-carryover results reuse the same noise block.

`audit_noise_coverage.py` reconstructs only the already-used stage-21 random streams. Tail indices 4–31 contain 17 standardized errors beyond the nominal normal cutoff; the first eight fresh observations give 14. Stored mean errors agree with the reconstructed means to approximately 7×10⁻¹⁶. No indexing or normalization defect was found. The shortfall is retained; no new seeds, extra trials or altered intervals were used to remove it. This audit does not constitute empirical proof of general calibration.

## Artifacts

| File | Role |
|---|---|
| `protocol.json` | Frozen assumptions, cases, seeds, sensitivities, review and hashes |
| `emulator_models.json` | Locked primary coefficients and scalar emulator certificates |
| `emulator_validation.json` | Development selection and held-out accuracy |
| `trial_results.csv` | Every policy outcome, interval, action count and cost |
| `summary.json` | All cases, exact denominators, Wilson intervals and paired bootstrap comparisons |
| `all_results_with_intervals.csv` | Complete method/case table |
| `paired_comparisons.csv` | Paired differences and 95% bootstrap intervals |
| `planning_diagnostics.csv` | Deterministic count/radius/cost frontiers |
| `coverage_noise_audit.json` | Retained undercoverage reconstruction |
| `coverage_noise_reconstruction.csv` | Per-seed standardized errors from that reconstruction |
| `RESULTS.md` | Numerical interpretation and limits |
| `validation.json` | Full dataset/hash/resource/coupling integrity checks |
| `examples.json` | Complete predeclared development trajectories |
| `planner_parity_fixture.json` | Exact deterministic fixture for the live planner port |
| `figures/` | Four compact 6.6-inch figures in PNG and SVG |

Rate confidence intervals are per-case Wilson intervals. Method differences and continuous means use 5,000 paired seed bootstrap replicates. Zero-event paired intervals can collapse and are not equivalence evidence. No multiplicity-adjusted confirmatory superiority claim is made.
