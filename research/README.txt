# When the Lab Remembers — reproducible computational study

This directory contains the complete first benchmark for confirming a frozen, optimizer-selected nominal formulation when a shared experimental line retains some previous mixture. All performance values are synthetic and dimensionless. There are no measured materials properties or laboratory experiments in this baseline study.

The executed result is deliberately reported as obtained: predecessor-sequence replay can falsely confirm a nominal recipe, while ordinary repeated dispensing often flushes the residual. The proposed adaptive control rule did not establish an advantage over the strongest control, which uses the same history model and repeatedly measures the candidate. See **RESULTS.md** for the numerical interpretation and uncertainty.

## Reproduce

Python 3.12.14 was used. Package versions are pinned in `requirements.txt`.

```bash
python -m pip install -r requirements.txt
python -m unittest -v test_lab_memory.py
python run_study.py
python make_figures.py
python write_results.py
```

The main run used about 247 seconds in the execution environment. It writes 48,000 policy rows: 400 seeds × 12 regimes × 10 methods. The same 400 seeded surface draws are reused across regimes, so the 4,800 regime–seed scenarios are not independent for pooled statistical inference. Confidence intervals and paired method comparisons are computed separately for each regime.

`protocol.json` was frozen before evaluation seeds 10000–10399 were run. Pilot seeds 0–9 were used only during development; the original pilot output is retained as `pilot_rows.csv`. The protocol records pre-evaluation additions, including the strong repetition control, the no-cost ablation, cost sensitivities and off-grid/severe carryover stresses. Frozen core source hashes are checked in `validation.json`.

The command-line options `--n`, `--start-seed`, and `--bootstrap` support a separately labeled reproduction or extension. A different run overwrites generated output files in this directory, so use a copied directory for a new experiment. Changes to the scientific protocol should be declared before new report seeds are used.

## Physical state and scientific target

A nominal ternary recipe is a vector of nonnegative mass fractions summing to one. Each shared-line assay has fixed final mass or volume. With retained fraction `r`, the actual composition is

```text
actual = (1 - r) * nominal + r * residual
r = rho * eta ** number_of_washes
```

Thus `rho` is a fraction of the **final batch**, not a contaminant-to-new-material mass ratio. `eta` is the residual multiplier per wash. A wash reduces the retained contribution; no solvent blank or unmodeled fourth component is used. The primary memory rule makes the residual equal to the last actual mixture. The long-memory stress instead updates it as `(1-lambda) * previous_residual + lambda * actual`, with `lambda=0.45`.

The initial residual is the known priming mixture `[1,0,0]`. Observation noise is independent Normal with known standard deviation `0.03`. These known quantities are favorable assumptions, explicitly retained as limitations.

An independent **fresh preparation and assay** measures the commanded recipe with no modeled carryover, while leaving the shared line residual unchanged. This is a real observable action inside the simulation, distinct from the scorer's private clean-response oracle. Its default cost is four assumed units; routine or conditioning assays cost one and each wash costs 0.5. Cost sensitivities use wash costs 0.1/0.5/2 and fresh costs 2/4/8.

The scientific target is whether the frozen nominal recipe, when independently prepared fresh, has a dimensionless response of at least `0.85`. It is not a general claim about intrinsic material properties. The policy observes commanded actions and noisy responses. Actual compositions, true carryover and noiseless fresh responses are accessible only to the simulator/scorer and optional illustration displays.

## Discovery and confirmation

Discovery is a stateless Bayesian quadratic UCB campaign over a ternary grid in increments of 0.1. Eight distinct recipes are selected randomly, then sixteen further distinct recipes maximize posterior mean plus 1.5 posterior latent standard deviations. The frozen candidate is the tested nominal recipe with the highest final posterior mean. Every confirmation method receives the same candidate, full discovery history and starting shared-line state for that seed and regime.

Inference uses six quadratic Bernstein mixture features: `a², b², c², 2ab, 2ac, 2bc`. This is a finite-dimensional Bayesian linear model, not a Gaussian-process implementation. The history model averages 24 particles with `rho` in `[0,.1,.25,.4,.55,.7]` and `eta` in `[.05,.2,.5,.8]`. Each particle has an independent Gaussian coefficient prior with mean `[.6]*6` and covariance `.25 I`. Posterior weights follow normal predictive likelihoods. The assumed state update is the primary last-mixture memory rule.

The adaptive policy evaluates routine candidate measurement, one- and three-wash candidate measurement, independent fresh measurement, and a measured conditioning assay at each pure component vertex. Conditioning is a single costed assay, followed by a new choice; there is no two-step look-ahead. The action score is

```text
Cov(clean candidate response, next observation)^2
------------------------------------------------
       Var(next observation) * action cost
```

The covariance and variance come from moment matching the joint particle mixture. This is a linear-projection variance reduction surrogate; it is not exact expected Bayesian model-average posterior variance reduction or threshold entropy gain.

Every policy has a fixed confirmation budget cap of 16 units. The simulation continues through its affordable prescribed actions. The final decision is accept at posterior/naive probability at least 0.975, reject at at most 0.025, and unresolved otherwise; at least two commanded candidate assays are required. A conditioning vertex equal to the candidate counts as a target assay. There is no finite-sample or arbitrary-misspecification reliability guarantee for these baseline probabilities.

| Method key | Action rule | Decision evidence |
|---|---|---|
| `candidate_repeat` | Routine candidate repeatedly | Naive confirmation-target mean and known noise |
| `sequence_repeat` | Alternate original discovery predecessor and candidate | Naive confirmation-target mean |
| `randomized_predecessor` | Alternate random pure-component predecessor and candidate | Naive confirmation-target mean |
| `wash_once` | One wash before each candidate | Naive confirmation-target mean |
| `wash_three` | Three washes before each candidate | Naive confirmation-target mean |
| `fresh_only` | Independent fresh candidate every time | Naive fresh-target mean |
| `history_fixed` | Cycle routine, one wash, fresh; use routine if next scheduled action cannot fit | Full history model |
| `history_repeat` | Routine candidate repeatedly | Full history model |
| `active_confirmation` | Maximize the cost-divided covariance score | Full history model |
| `active_no_cost` | Maximize the same score without cost division | Full history model |

The primary comparison is `active_confirmation` against `history_repeat`, holding the inference model and discovery evidence constant. Fixed-wash and fresh-only policies preserve their stated action rule and can leave an unspendable remainder; equal budget caps do not imply equal realized spend. All preparation types exist in the simulated action environment; each fixed policy intentionally follows its own restricted rule.

## Data files and figures

| File | Contents |
|---|---|
| `protocol.json` | Frozen design, seeds, assumptions, costs, changes made after the pilot, source hashes |
| `trial_results.csv` | Every evaluation seed–regime–method result, including true class, decision, error and cost |
| `summary.json` | Counts, explicit denominators, Wilson intervals, bootstrap means and paired differences |
| `summary_table.csv` | Compact per-regime/per-method point estimates |
| `all_results_with_intervals.csv` | Full machine-readable counts, denominators and confidence interval endpoints |
| `paired_comparisons.csv` | Primary and secondary paired differences with bootstrap intervals |
| `RESULTS.md` | Readable numerical interpretation including unfavorable and null findings |
| `examples.json` | Full development-seed-7 discovery and confirmation trajectories in three declared regimes |
| `parity_fixture.json` | Deterministic supplied-noise fixture for checking a browser port |
| `validation.json` | Core source-hash and full dataset integrity checks |
| `figures/` | Seven figures, each in 220-dpi PNG and vector SVG |

The figures show rates with individual Wilson intervals, the primary matched-model comparison, response estimation error, resource costs, cost sensitivity, a composition mechanism illustration and a development trajectory. The actual mixture and true fresh response appear only in explicitly marked simulator illustrations; they are absent from policy decisions.

## Statistical interpretation

False confirmation per campaign is `false accepts / all campaigns`. False fraction among accepted is `false accepts / accepts`, and is undefined when no candidate is accepted. True acceptance per campaign is a yield; sensitivity is separately reported as `true accepts / truly good candidates`. Rejections, false rejections and unresolved outcomes are reported separately.

Rate intervals are Wilson 95% intervals. Continuous means and paired method differences use 5,000 percentile bootstrap replicates over seed within regime. A binary paired bootstrap interval can collapse to `[0,0]` when no discordant events occurred; this does not establish equivalence or eliminate unobserved risk. The first non-unresolved threshold crossing is descriptive only: the simulation did not stop there. There is no multiplicity-adjusted confirmatory significance claim across the scenario comparisons.

The primary response family is a concave quadratic and is included in the inference model. Nonlinear response, long memory and off-grid parameters test selected departures, not arbitrary apparatus behavior. Assumed costs and carryover levels are controlled scenarios, not measured laboratory distributions. The baseline supports a reproducible mechanism and comparison study; a claim of laboratory-ready certification would require additional assumptions and experimental evidence.
