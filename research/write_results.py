"""Export interval tables and a readable executed-result note from summary.json."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
s=json.loads((HERE/"summary.json").read_text())
protocol=json.loads((HERE/"protocol.json").read_text())
data={r["name"]:r for r in s["regimes"]}
flat=[]
paired=[]
for r in s["regimes"]:
    for method,d in r["methods"].items():
        row={"regime":r["name"],"method":method,"n":d["n"],
             "true_good_count":r["true_good"]["count"]}
        for metric,v in d.items():
            if isinstance(v,dict) and "estimate" in v:
                row[metric]=v["estimate"]
                row[metric+"_ci95_low"],row[metric+"_ci95_high"]=v["ci95"]
                if "count" in v:
                    row[metric+"_count"]=v["count"]
                    row[metric+"_denominator"]=v["denominator"]
        flat.append(row)
    for comparator,d in r["paired_comparisons"].items():
        for metric,v in d["metrics"].items():
            paired.append({"regime":r["name"],"active_method":"active_confirmation",
                           "comparator":comparator,"metric":metric,"difference":v["estimate"],
                           "ci95_low":v["ci95"][0],"ci95_high":v["ci95"][1],
                           "n_pairs":d["n_pairs"]})
pd.DataFrame(flat).to_csv(HERE/"all_results_with_intervals.csv",index=False)
pd.DataFrame(paired).to_csv(HERE/"paired_comparisons.csv",index=False)


def pct(v):
    if v["estimate"] is None: return "undefined"
    lo,hi=v["ci95"]
    return f"{100*v['estimate']:.2f}% [{100*lo:.2f}, {100*hi:.2f}]"


def diff(v):
    lo,hi=v["ci95"]
    return f"{100*v['estimate']:+.2f} pp [{100*lo:+.2f}, {100*hi:+.2f}]"


lines=["# Executed benchmark results", "",
       "The frozen study found sequence-dependent false confirmation, but did not establish an advantage for adaptive controls over a history model with simple candidate repetition.","",
       f"The study used {s['campaigns_per_regime']} independent seed draws (10000–10399), reused across {s['number_of_regimes']} regimes, producing {s['total_policy_runs']:,} policy runs for {s['number_of_methods']} methods. Regime-specific uncertainty respects this pairing. All candidate formulations were frozen after a shared 24-assay discovery campaign; every confirmation policy had the same 16-unit budget cap.","",
       "## Three informative regimes", "",
       "Rates below use all 400 campaigns as their denominator. Brackets give Wilson 95% intervals. Correct acceptance is a yield, not sensitivity conditional on a truly good recipe.","",
       "| Regime | Method | False confirmations | Correct-acceptance yield | Unresolved | Mean absolute error |",
       "|---|---|---:|---:|---:|---:|"]
for name in ["strong_carryover","nonlinear_response_stress","severe_carryover"]:
    r=data[name]
    for method in ["sequence_repeat","candidate_repeat","wash_once","fresh_only","history_repeat","active_confirmation"]:
        d=r["methods"][method]
        lines.append(f"| {name} | {d['label']} | {pct(d['false_accept'])} | {pct(d['true_accept'])} | {pct(d['unresolved'])} | {d['absolute_error']['estimate']:.5f} |")
lines += ["","## Primary comparison: active controls versus history-model repetition","",
          "This comparison uses the same inference model and discovery evidence. Both methods had zero false acceptances in every evaluated regime. For an individual 0/400 rate, the Wilson 95% upper bound is 0.95%; zero observed events do not establish zero risk. The paired bootstrap differences for this all-zero outcome are degenerate and must not be interpreted as an equivalence result.","",
          "| Regime | Difference in correct-acceptance yield | Difference in unresolved rate | Difference in mean absolute error |",
          "|---|---:|---:|---:|"]
for r in s["regimes"]:
    d=r["paired_comparisons"]["history_repeat"]["metrics"]
    mae=d["absolute_error"]
    lines.append(f"| {r['name']} | {diff(d['true_accept'])} | {diff(d['unresolved'])} | {mae['estimate']:+.5f} [{mae['ci95'][0]:+.5f}, {mae['ci95'][1]:+.5f}] |")
lines += ["","## Interpretation","",
 "1. **Replaying history can reproduce the wrong formulation.** In nonlinear stress, predecessor-sequence replay produced 36 false confirmations out of 400 campaigns. Among its 267 accepted candidates, 36 were false (13.48%; Wilson 95% interval 9.90–18.10%). Ordinary candidate repetition produced 2/400 false confirmations, and history-model repetition produced 0/400. The requested recipe, preceding recipe and actual mixture are different objects.",
 "2. **Candidate repetition is a strong control.** Under last-mixture memory and a fixed repeated recipe, the composition discrepancy decays geometrically with each assay. A study that compares only with predecessor-sequence replay would overstate the need for adaptive action choice.",
 "3. **Adaptive controls did not beat the strongest simple baseline.** Under strong carryover, active controls accepted 229 truly good candidates, versus 235 for history-model repetition. The paired difference was −1.50 percentage points, with a 95% interval of −3.25 to +0.25. Under ineffective washing and costly washing the observed yield differences favored history-model repetition, but the multiple exploratory comparisons do not establish a universal ranking.",
 "4. **Model misspecification remains consequential.** Under nonlinear response stress, active controls and history-model repetition each correctly accepted 245/400 candidates. Active controls also falsely rejected 2 good candidates, versus none for history-model repetition. Its mean absolute fresh-response error was 0.01167, versus 0.00895; the paired increase was 0.00272, with a bootstrap 95% interval of 0.00174–0.00376. Fewer unresolved outcomes alone is not sufficient evidence of a better method.",
 "5. **Costs change the amount of evidence purchased.** Independent fresh assays cost four units by default, allowing four observations under the cap. Routine repetition permits sixteen. Fresh preparation removes modeled carryover but does not remove observation noise or the statistical difficulty of a near-threshold recipe. Costs are scenario assumptions, not measured laboratory time.",
 "6. **The study supports a benchmark and a mechanism, with a negative result for the proposed action rule.** The one-step covariance utility approximates clean-response variance reduction. It is not exact information gain, has no look-ahead, and does not explicitly minimize threshold decision error. These are plausible explanations to investigate in separately declared follow-up work, rather than conclusions identified causally by the present experiments.","",
 "## Scope and uncertainty","",
 "All outcomes are from synthetic dimensionless response surfaces. The primary quadratic response family is included in the inference model; nonlinear response, long memory and off-grid carryover are explicit stress cases. Initial residual composition and observation noise are assumed known. Independent fresh preparation is an available measured action. The policy cannot see the true composition, carryover parameters or clean response used by the scorer.","",
 "The benchmark reports all campaigns, including weak discoveries; there was no post hoc restriction to apparently successful discovery runs. Illustrations use development seed 7, declared before evaluation, and are separate from evaluation estimates. Fixed wash/fresh-only policies can leave a remainder smaller than their scheduled next action; equal caps do not imply equal spend. First decision cost is a hypothetical threshold-crossing statistic from runs that continued to budget, not an early-stopping experiment.","",
 "See protocol.json for exact pre-evaluation commitments and pilot changes, trial_results.csv for every policy run, all_results_with_intervals.csv for the full rate/count/denominator table, paired_comparisons.csv for differences, and examples.json for complete fixed-development trajectories.",""]
(HERE/"RESULTS.md").write_text("\n".join(lines))

frame=pd.read_csv(HERE/"trial_results.csv")
checks={}
checks["expected_row_count"]=len(frame)==s["total_policy_runs"]==48000
checks["unique_regime_seed_method"]=not frame.duplicated(["regime","seed","method"]).any()
checks["four_hundred_rows_per_regime_method"]=bool((frame.groupby(["regime","method"]).size()==400).all())
checks["evaluation_seeds_match"]=set(frame.seed)==set(range(10000,10400))
checks["candidate_mass_balance"]=bool(np.allclose(frame[["candidate_x0","candidate_x1","candidate_x2"]].sum(axis=1),1))
checks["budget_caps_respected"]=bool((frame.cost<=16+1e-8).all())
checks["decision_partition"]=bool((frame[["accepted","rejected","unresolved"]].astype(int).sum(axis=1)==1).all())
checks["false_accept_definition"]=bool((frame.false_accept==(frame.accepted & ~frame.true_good)).all())
checks["true_accept_definition"]=bool((frame.true_accept==(frame.accepted & frame.true_good)).all())
checks["truth_label_definition"]=bool((frame.true_good==(frame.true_clean_response>=s["threshold"])).all())
checks["same_frozen_truth_within_campaign"]=bool((frame.groupby(["regime","seed"]).true_clean_response.nunique()==1).all())
checks["frozen_sources_unchanged"]=all(hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest
                                        for name,digest in protocol["frozen_code_sha256"].items())
checks["summary_sources_match"]=all(hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest
                                     for name,digest in s["source_sha256"].items())
resource_ok=True
aggregate_ok=True
for r in s["regimes"]:
    g=frame[frame.regime==r["name"]]
    p=r["parameters"]
    expected=g.assays-g.fresh_assays+g.fresh_assays*p["fresh_cost"]+g.washes*p["wash_cost"]
    resource_ok &= bool(np.allclose(expected,g.cost))
    for method,d in r["methods"].items():
        group=g[g.method==method]
        for metric in ["accepted","rejected","unresolved","false_accept","true_accept","false_reject"]:
            aggregate_ok &= int(group[metric].sum())==d[metric]["count"]
checks["resource_cost_reconciles"]=resource_ok
checks["aggregates_match_raw_counts"]=aggregate_ok
validation={"data_checks":checks,"all_data_checks_passed":all(checks.values()),
            "pre_evaluation_unit_tests":{"count":9,"status":"passed","command":"python -m unittest -v test_lab_memory.py"},
            "independent_review":"Latent-data boundary, conditional BLR algebra, mixture utility covariance and aggregation denominators independently audited before evaluation.",
            "scope":"This checks computational integrity; it does not establish experimental validity or novelty."}
(HERE/"validation.json").write_text(json.dumps(validation,indent=2)+"\n")
if not all(checks.values()): raise AssertionError(checks)
print("Wrote interval tables, RESULTS.md and validation.json; all data integrity checks passed.")
