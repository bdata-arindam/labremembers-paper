"""Reconcile all numerical manuscript tables with independently audited outputs."""
from pathlib import Path
import json
import re
import hashlib
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT/path).read_text())


def main():
    manuscript = read("authoring/manuscript_content.json")
    blocks = {b["id"]: b for b in manuscript["blocks"]}
    measured = read("application/measured_reconfirmation_summary.json")
    v1 = read("research/summary.json")
    v2 = read("research/v2/summary.json")
    fidelity = read("research/v2/emulator_validation.json")
    case_map = {r["case"]["name"]: r for r in v2["cases"]}
    checks = []

    def ok(cid, truth, scope):
        assert truth, cid
        checks.append({"id": cid, "status": "PASS", "scope": scope})

    source_pairs = {r["system"]: r for r in measured["rows"] if r["campaign"] == "all"}
    for row, system in zip(blocks["T02"]["rows"], ["pbq_qf", "ptb7_th"]):
        r = source_pairs[system]
        expected = [r[k] for k in ["n_pairs", "both_pass", "sample1_pass_sample2_fail", "sample1_fail_sample2_pass", "both_fail"]]
        ok("T02-"+system, row[1:] == expected, "Every numerical count in measured-agreement table")

    strong = next(r for r in v1["regimes"] if r["name"] == "strong_carryover")
    for row, method in zip(blocks["T03"]["rows"], ["sequence_repeat", "candidate_repeat", "fresh_only", "history_repeat", "active_confirmation"]):
        m = strong["methods"][method]
        ok("T03-"+method, row[1:4] == [m[k]["count"] for k in ["false_accept", "true_accept", "unresolved"]] and row[4] == f'{m["absolute_error"]["estimate"]:.5f}', "All counts and displayed MAE")
    ok("T03-VALID", strong["true_good"]["count"] == 264, "Valid-candidate count in table note")

    for row, system in zip(blocks["T04"]["rows"], ["pbq_qf", "ptb7_th"]):
        f = fidelity[system]
        expected = [f["held_out"]["n"], f'{f["held_out"]["mae"]:.5f}', f'{f["held_out"]["rmse"]:.5f}', f'{f["held_out"]["r2"]:.4f}', f'{f["lipschitz_l1"]:.5f}']
        ok("T04-"+system, row[1:] == expected, "All displayed held-out error and certificate values")

    scenario_names = ["no_carryover", "trace_carryover", "low_carryover", "moderate_carryover", "high_carryover", "ineffective_wash", "persistent_memory", "strongly_persistent_stress"]
    expected_cases = [f"{system}__main__{scenario}" for system in ["pbq_qf", "ptb7_th"] for scenario in scenario_names]
    for row, key in zip(blocks["T05"]["rows"], expected_cases):
        c = case_map[key]
        methods = ["bounded_planner", "bounded_tail4", "bounded_fresh"]
        expected = [c["true_good"]["count"]] + [c["methods"][m]["true_accept"]["count"] for m in methods] + [f'{c["methods"]["bounded_planner"]["ci_halfwidth"]["estimate"]:.5f}']
        ok("T05-"+key, row[1:] == expected, "All valid-count, true-acceptance and radius cells")
        ok("T05-ZERO-FA-"+key, all(c["methods"][m]["false_accept"]["count"] == 0 for m in methods), "Zero observed errors in table note; no zero-risk inference")

    selected_cases = [f"{system}__main__{scenario}" for system in ["pbq_qf", "ptb7_th"] for scenario in ["high_carryover", "ineffective_wash", "persistent_memory"]]
    for row, key in zip(blocks["T06"]["rows"], selected_cases):
        for cell, comparator in zip(row[1:], ["bounded_fresh", "bounded_tail4"]):
            stat = case_map[key]["paired_comparisons"]["bounded_planner__minus__"+comparator]["metrics"]["true_accept"]
            parsed = list(map(float, re.findall(r"[-+]?\d+(?:\.\d+)?", cell)))
            expected = [round(stat["estimate"]*100, 1), *[round(x*100, 2) for x in stat["ci95"]]]
            ok("T06-"+key+"-"+comparator, np.allclose(parsed, expected, atol=1e-12), "Displayed paired percentage-point effect and both interval endpoints; copied from saved bootstrap summary, not reestimated")

    c = case_map["pbq_qf__main__no_carryover"]
    for row, method in zip(blocks["T07"]["rows"], ["bounded_planner", "bounded_tail4", "bounded_fresh"]):
        stat = c["methods"][method]["interval_coverage"]
        expected = [f'{stat["count"]} / {stat["denominator"]}', f'{stat["estimate"]*100:.1f}', f'{stat["ci95"][0]*100:.2f}–{stat["ci95"][1]*100:.2f}']
        ok("T07-"+method, row[1:] == expected, "Coverage count, rate and both Wilson endpoints")

    main_cases = [r for r in v2["cases"] if r["case"]["condition"] == "main"]
    ok("P047-ALL-VALID", sum(r["true_good"]["count"] == 200 for r in main_cases) == 9, "Nine of sixteen primary cases have all-valid candidates")
    ok("P047-RUN-COUNTS", v2["total_policy_runs"] == 62400 and v2["main_case_campaigns"] * v2["number_of_methods"] == 41600 and 62400-41600 == 20800, "Main, sensitivity and total policy-run counts")
    raw = pd.read_csv(ROOT/"research/v2/trial_results.csv")
    selected = raw.drop_duplicates(["case", "seed"])
    for system, scenario, expected in [("pbq_qf", "no_carryover", 200), ("pbq_qf", "trace_carryover", 200), ("pbq_qf", "low_carryover", 200), ("ptb7_th", "no_carryover", 180)]:
        g = selected[(selected.system == system) & (selected.condition == "main") & (selected.scenario == scenario)]
        ok("P047b-NEGATIVE-"+system+"-"+scenario, len(g) == 200 and int(g.true_degradation.lt(0).sum()) == expected, "Post-run count of negative fitted mean loss; not measured physical stability")
    measured_raw = pd.read_csv(ROOT/"application/measured_observations_tidy.csv")
    ok("P047b-MEASURED-NEGATIVES", int(measured_raw.degradation.lt(0).sum()) == 2, "Two retained source observations have negative measured degradation; no sign-based impossibility claim")
    for system in ["pbq_qf", "ptb7_th"]:
        g = raw[(raw.system == system) & (raw.condition == "main") & (raw.scenario == "high_carryover") & (raw.method == "bounded_planner")]
        ok("P048-PLAN-"+system, bool((g.wash3_assays.eq(2) & g.assays.eq(29) & g.fresh_assays.eq(0) & g.cost.eq(32)).all()), "Two three-wash assays followed by 27 routine assays")
    severe = case_map["ptb7_th__main__strongly_persistent_stress"]
    ok("P049-COUNTS", severe["true_good"]["count"] == 26 and severe["methods"]["active_confirmation"]["false_accept"]["count"] == 12 and severe["methods"]["history_repeat"]["false_accept"]["count"] == 10 and severe["methods"]["bounded_planner"]["true_accept"]["count"] == 17, "Severe-memory prevalence and reported false/true acceptances")
    broad = [r for r in v2["cases"] if r["case"]["condition"] == "broad_bounds"]
    ok("P049c-BROAD", len(broad) == 4 and all(r["methods"]["bounded_tail4"]["unresolved"]["count"] == 100 for r in broad), "All four broad-bound tails unresolved")
    equal = raw[raw.condition.eq("equal_fresh_cost") & raw.method.eq("bounded_planner")]
    ok("P049c-EQUAL-FRESH", bool(equal.fresh_assays.eq(32).all()), "Declared equal-cost planner uses 32 fresh assays")
    dcase = case_map["pbq_qf__delaunay_sensitivity__high_carryover"]
    ok("P049c-DELAUNAY", dcase["methods"]["bounded_planner"]["false_accept"]["count"] == 1, "Reported Delaunay high-carryover false acceptance")
    diagnostics = pd.read_csv(ROOT/"research/v2/planning_diagnostics.csv")
    g = diagnostics[(diagnostics.system == "pbq_qf") & (diagnostics.scenario == "high_carryover") & (diagnostics.condition == "broad_bounds") & diagnostics.fresh_cost.eq(4)]
    ok("F04-BROAD-OVERLAP", len(g) == 4 and bool(g.n_fresh.eq((g.budget/4).astype(int)).all()) and np.allclose(g.half_width, norm.ppf(.975)*.03/np.sqrt(g.n_fresh), atol=1e-14), "Broad-bound planner and fresh-only curves coincide for all four displayed budgets")
    ok("P054-PILOT-ARITHMETIC", 2*(3*3+1)*6 == 120, "120 target assays exclude charged predecessor and candidate-selection calibration work")
    for block in [b for b in manuscript["blocks"] if b["type"] == "figure"]:
        ok("FIGURE-EXISTS-"+block["id"], (ROOT/block["path"]).exists(), "Referenced image file exists; visual QA is a separate root check")
    record = {"audit_id": "AUDIT-MANUSCRIPT-NUMBERS", "generated_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS", "command": "python audit/check_manuscript_numbers.py", "manuscript_sha256": hashlib.sha256((ROOT/"authoring/manuscript_content.json").read_bytes()).hexdigest(), "checks": checks, "scope": "All numerical cells in T02–T07, key textual/count/sensitivity assertions and the final F04 overlap note. Source-output arithmetic is separately audited. T01 is a literature comparison, not a numerical result table.", "limits": "Rounded table values are reconciled to independently audited saved outputs. Bootstrap intervals are copied consistently from frozen summary records; this script does not independently rerun all bootstrap resamples. No new campaigns or seed changes."}
    (ROOT/"audit/manuscript_numeric_audit.json").write_text(json.dumps(record, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({"status":"PASS", "checks":len(checks), "manuscript_sha256":record["manuscript_sha256"]},indent=2))


if __name__ == "__main__":
    main()
