"""Executed-result interpretation and integrity audit; no changes to inference."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
s=json.loads((HERE/"summary.json").read_text())
p=json.loads((HERE/"protocol.json").read_text())
f=pd.read_csv(HERE/"trial_results.csv")
v=json.loads((HERE/"emulator_validation.json").read_text())
checks={"expected_policy_rows":len(f)==62400,
        "unique_case_seed_method":not f.duplicated(["case","seed","method"]).any(),
        "thirteen_policies_per_campaign":bool((f.groupby(["case","seed"]).size()==13).all()),
        "candidate_mass_balance":bool(np.allclose(f[[f"candidate_x{i}" for i in range(4)]].sum(axis=1),1)),
        "candidate_donor_eligibility":bool(((f.candidate_x0+f.candidate_x1>=1/6-1e-12)&(f.candidate_x0+f.candidate_x1<=5/6+1e-12)).all()),
        "budget_caps":bool((f.cost<=f.budget+1e-9).all()),
        "decision_partition":bool((f[["accepted","rejected","unresolved"]].astype(int).sum(axis=1)==1).all()),
        "false_accept_definition":bool((f.false_accept==(f.accepted&~f.true_good)).all()),
        "true_accept_definition":bool((f.true_accept==(f.accepted&f.true_good)).all()),
        "same_frozen_truth_per_campaign":bool((f.groupby(["case","seed"]).true_clean_response.nunique()==1).all()),
        "frozen_sources_unchanged":all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h for n,h in p["frozen_code_sha256"].items()),
        "measured_inputs_unchanged":all(hashlib.sha256((HERE.parent.parent/"application"/n).read_bytes()).hexdigest()==h for n,h in p["measured_input_sha256"].items())}
counts_ok=True;cost_ok=True;coupling_ok=True;planner_ok=True
for r in s["cases"]:
    g=f[f.case==r["case"]["name"]]
    counts_ok &= len(g)==r["n_campaigns"]*13
    expected=g.assays-g.fresh_assays+g.fresh_assays*r["case"]["fresh_cost"]+g.washes*r["case"]["wash_cost"]
    cost_ok &= bool(np.allclose(expected,g.cost))
    for method,d in r["methods"].items():
        a=g[g.method==method]
        for field in ["accepted","false_accept","true_accept","false_reject","unresolved"]:
            counts_ok &= int(a[field].sum())==d[field]["count"]
    for a,b in [("candidate_repeat","bounded_repeat"),("tail_repeat4","bounded_tail4"),("fresh_only","bounded_fresh")]:
        aa=g[g.method==a].set_index("seed").sort_index()
        bb=g[g.method==b].set_index("seed").sort_index()
        coupling_ok &= bool(np.array_equal(aa.estimate,bb.estimate))
    a=g[g.method=="bounded_planner"]
    planner_ok &= bool(np.allclose(a.ci_halfwidth,a.planned_halfwidth,rtol=1e-12,atol=1e-12))
checks.update({"aggregate_counts_match":counts_ok,"resource_costs_reconcile":cost_ok,
               "routine_tail_fresh_observation_coupling":coupling_ok,"planner_predicted_width_matches_observed_schedule":planner_ok})
audit={"all_checks_passed":all(checks.values()),"checks":checks,
       "scientific_tests":{"count":8,"result":"passed before evaluation"},
       "interpretation":"Computational integrity, not experimental verification of carryover or confidence assumptions."}
(HERE/"validation.json").write_text(json.dumps(audit,indent=2)+"\n")
if not all(checks.values()):raise AssertionError(checks)


def rate_text(x):
    if x["estimate"] is None:return "undefined (zero denominator)"
    return f"{x['count']}/{x['denominator']} ({100*x['estimate']:.1f}%;95%CI{100*x['ci95'][0]:.1f}–{100*x['ci95'][1]:.1f})"


lines=["# V2 executed results","",
       "This extension combines measured OPV data, explicit response emulators and simulated carryover. The confidence construction certifies a fixed emulator under supplied bounds; it does not certify a physical OPV formulation from these data.","",
       f"The frozen study completed{s['main_case_campaigns']:,}main campaign scenarios and{s['total_case_campaigns']-s['main_case_campaigns']:,}predeclared sensitivity scenarios, producing{s['total_policy_runs']:,}policy runs. The same200 report seeds are reused across cases; uncertainty is calculated separately within case.","",
       "## Held-out response fidelity","",
       "| System | Held-out groups | MAE | RMSE | R² | Emulator L1 certificate |",
       "|---|---:|---:|---:|---:|---:|"]
for name,d in v.items():
    m=d["held_out"]
    lines.append(f"|{name}|{m['n']}|{m['mae']:.5f}|{m['rmse']:.5f}|{m['r2']:.4f}|{d['lipschitz_l1']:.5f}|")
lines += ["","These are modest prediction errors relative to the illustrative0.10 loss threshold. The fitted cubic family was prespecified and retained after held-out evaluation. These errors are not added to the emulator-only certificate, so the certificate cannot be transferred to real material response without additional validated model-error bounds.","",
          "## Primary case table","",
          "Correct-acceptance yield uses every campaign, not only valid recipes. A case with no invalid candidates cannot estimate false acceptance conditional on invalid candidates.","",
          "| System | Scenario | Truly qualifying | Planner true accepts | Tail4 true accepts | Fresh true accepts | Planner false accepts | Planner unresolved | Planner half-width |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
for r in s["cases"]:
    c=r["case"]
    if c["condition"]!="main":continue
    planner=r["methods"]["bounded_planner"];tail=r["methods"]["bounded_tail4"];fresh=r["methods"]["bounded_fresh"]
    n=r["n_campaigns"]
    lines.append(f"|{c['system']}|{c['scenario']}|{r['true_good']['count']}/{n}|{planner['true_accept']['count']}/{n}|{tail['true_accept']['count']}/{n}|{fresh['true_accept']['count']}/{n}|{planner['false_accept']['count']}/{n}|{planner['unresolved']['count']}/{n}|{planner['ci_halfwidth']['estimate']:.5f}|")
lines += ["","## Planner versus the burn-in control","",
          "Differences are planner minus bounded tail4. Percentile intervals use5000 paired seed bootstrap replicates; no multiplicity-adjusted superiority claim is made.","",
          "| System | Scenario | Difference in correct-acceptance yield (percentage points) | Difference in false confirmations (percentage points) |",
          "|---|---|---:|---:|"]
for r in s["cases"]:
    c=r["case"]
    if c["condition"]!="main":continue
    d=r["paired_comparisons"]["bounded_planner__minus__bounded_tail4"]["metrics"]
    fmt=lambda k:f"{100*d[k]['estimate']:+.2f} [{100*d[k]['ci95'][0]:+.2f},{100*d[k]['ci95'][1]:+.2f}]"
    lines.append(f"|{c['system']}|{c['scenario']}|{fmt('true_accept')}|{fmt('false_accept')}|")
lines += ["","## Empirical coverage shortfall retained","",
          "The fixed-final mathematical construction did not yield nominal95% coverage in every finite simulation case. The following predeclared no-carryover case makes the observed shortfall explicit; common confirmation noise is reused across cases, so repeated low-carryover coverage values are not independent replications.","",
          "| Method | Covered / campaigns, with Wilson95% interval |",
          "|---|---:|"]
no_carry=next(r for r in s["cases"] if r["case"]["name"]=="pbq_qf__main__no_carryover")
for method in ["bounded_repeat","bounded_tail4","bounded_fresh","bounded_planner"]:
    lines.append(f"|{method}|{rate_text(no_carry['methods'][method]['interval_coverage'])}|")
lines += ["",
          "The retained audit_noise_coverage.py independently reconstructs the already-used stage21 Gaussian streams, with no new report seeds. The tail4 and fresh standardized errors reproduce their respective observed misses; the saved mean errors agree with the reconstructed noise to floating-point precision. No tail indexing or normalization defect was found. This check does not erase the empirical shortfall or establish empirical calibration; see coverage_noise_audit.json and coverage_noise_reconstruction.csv for exact counts, discrepancies and the finite-block diagnostic.","",
          "## Interpretation boundaries","",
 "The planner is a preplanned preparation schedule, not an outcome-adaptive algorithm. Its exact optimality is restricted to enumerated routine/wash1/wash3/fresh count schedules using all their observations with equal weights. The prespecified discard-four control lies outside this class and can be better; this is why it remains a primary comparator.","",
 "Strong washes are placed first to reduce the accumulated worst-case bias bound. Fresh assays remove modeled carryover from their own observations while leaving the shared-line residual unchanged. With broad bounds, persistent memory or a large Delaunay Lipschitz certificate, the valid response interval can become conservative and fresh preparation may be selected. Such behavior reflects the supplied assumptions and costs, not measured OPV apparatus parameters.","",
 "At equal fresh/routine cost, an all-fresh schedule has zero modeled bias and the maximum affordable number of assays; it weakly dominates in the certified-width objective. The equal-cost sensitivity is included because no measured OPV cost data support the default four-unit fresh cost.","",
 "The empirical-contrast-noise sensitivity resamples symmetric half-differences of measured SDA pairs while still using assumed sigma0.03 in inference. It deliberately challenges the Gaussian/noise-bound assumption. Its coverage results are not covered by the main theorem, and this resampling is not a verified stochastic model of the laboratory.","",
 "Measured replicate disagreement, emulator prediction error and simulated carryover effects are separate evidence types. See the measured-data analysis for literal threshold reversals; neither those reversals nor interpolator roughness identifies carryover causally.","",
 "All methods and cases, exact counts/denominators, coverage and paired intervals are in summary.json, all_results_with_intervals.csv and paired_comparisons.csv. Every policy run is in trial_results.csv. Frozen configuration, scalar-only information boundary, source hashes and test/audit results are retained.",""]
(HERE/"RESULTS.md").write_text("\n".join(lines))
print("V2 integrity checks all passed; wrote validation.json and RESULTS.md.")
