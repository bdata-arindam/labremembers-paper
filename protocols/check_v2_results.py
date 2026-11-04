"""Independent reconciliation of frozen v2 outputs; no campaign is rerun."""
from pathlib import Path
import hashlib
import json
import math
import platform
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "research" / "v2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k, n):
    if n == 0:
        return [None, None]
    z = norm.ppf(.975)
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    rad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0., center - rad), min(1., center + rad)]


def main():
    summary = json.loads((V2 / "summary.json").read_text())
    protocol = json.loads((V2 / "protocol.json").read_text())
    data = pd.read_csv(V2 / "trial_results.csv")
    checks = []
    failures = []
    max_errors = {"rate_estimate": 0., "wilson_endpoint": 0., "mean_estimate": 0., "paired_estimate": 0.}

    def check(name, condition, detail=None):
        entry = {"id": name, "status": "PASS" if bool(condition) else "FAIL"}
        if detail is not None:
            entry["detail"] = detail
        checks.append(entry)
        if not condition:
            failures.append(entry)

    check("V2_ROWS", len(data) == 62400 == summary["total_policy_runs"])
    check("V2_CASES", data["case"].nunique() == 32 == summary["number_of_cases"])
    check("V2_METHODS", data.method.nunique() == 13 == summary["number_of_methods"])
    check("V2_UNIQUE_KEYS", not data.duplicated(["case", "seed", "method"]).any())
    campaigns = data[["case", "seed"]].drop_duplicates()
    main_campaigns = data.loc[data.condition.eq("main"), ["case", "seed"]].drop_duplicates()
    check("V2_CAMPAIGN_COUNTS", len(campaigns) == 4800 and len(main_campaigns) == 3200)
    group = data.groupby(["case", "seed"])
    invariant_cols = ["true_clean_response", "true_degradation", "true_good", "candidate_x0", "candidate_x1", "candidate_x2", "candidate_x3"]
    check("V2_MATCHED_CANDIDATES", bool((group[invariant_cols].nunique() == 1).all().all()))
    check("V2_ALL_METHODS_EACH_CAMPAIGN", bool((group.method.nunique() == 13).all()))
    check("V2_CANDIDATE_MASS", bool(np.allclose(data[[f"candidate_x{i}" for i in range(4)]].sum(axis=1), 1., atol=1e-12)))
    donor = data.candidate_x0 + data.candidate_x1
    check("V2_DONOR_ELIGIBILITY", bool(((donor >= 1/6 - 1e-12) & (donor <= 5/6 + 1e-12)).all()))
    check("V2_TRUTH_RULE", bool((data.true_good == (data.true_clean_response >= .9)).all()))
    check("V2_ERROR_ARITHMETIC", bool(np.allclose(data.absolute_error, abs(data.estimate - data.true_clean_response), atol=2e-15)))
    check("V2_BUDGET_CAP", bool((data.cost <= data.budget + 1e-9).all()))
    check("V2_DECISION_PARTITION", bool((data[["accepted", "rejected", "unresolved"]].sum(axis=1) == 1).all()))
    check("V2_MIN_TARGET_COUNT", bool((data.loc[~data.unresolved, "target_assays"] >= 2).all()))
    for label, rule in {
        "false_accept": data.accepted & ~data.true_good,
        "true_accept": data.accepted & data.true_good,
        "false_reject": data.rejected & data.true_good,
        "true_reject": data.rejected & ~data.true_good,
    }.items():
        check("V2_" + label.upper(), bool((data[label] == rule).all()))
    bounded = data[data.method.str.startswith("bounded_")]
    check("V2_INTERVAL_COVERAGE_FLAGS", bool((bounded.interval_covered.astype(bool) == ((bounded.ci_low <= bounded.true_clean_response) & (bounded.true_clean_response <= bounded.ci_high))).all()))
    check("V2_INTERVAL_WIDTH", bool(np.allclose((bounded.ci_high - bounded.ci_low) / 2, bounded.ci_halfwidth, atol=2e-15)))
    expected_width = bounded.mean_bias_bound + norm.ppf(.975) * .03 / np.sqrt(bounded.n_included)
    check("V2_FIXED_FINAL_RADIUS", bool(np.allclose(expected_width, bounded.ci_halfwidth, atol=2e-15)))
    planner = data[data.method.eq("bounded_planner")]
    check("V2_EXECUTED_VS_PLANNED_WIDTH", bool(np.allclose(planner.ci_halfwidth, planner.planned_halfwidth, atol=2e-14)))
    expected_valid = ~data.condition.eq("empirical_contrast_noise")
    check("V2_NOISE_STRESS_LABEL", bool((data.certificate_assumptions_valid == expected_valid).all()))

    rate_checks = 0
    mean_checks = 0
    paired_checks = 0
    for case in summary["cases"]:
        case_name = case["case"]["name"]
        frame = data[data["case"].eq(case_name)]
        seed_truth = frame.drop_duplicates("seed")
        check("CASE_N_" + case_name, len(seed_truth) == case["n_campaigns"])
        check("CASE_TRUE_GOOD_" + case_name, int(seed_truth.true_good.sum()) == case["true_good"]["count"])
        for method, stats in case["methods"].items():
            g = frame[frame.method.eq(method)]
            denominators = {
                "false_fraction_among_accepted": int(g.accepted.sum()),
                "false_accept_given_invalid": int((~g.true_good).sum()),
                "true_accept_given_valid": int(g.true_good.sum()),
                "false_reject_given_valid": int(g.true_good.sum()),
            }
            numerator_cols = {
                "false_fraction_among_accepted": "false_accept",
                "false_accept_given_invalid": "false_accept",
                "true_accept_given_valid": "true_accept",
                "false_reject_given_valid": "false_reject",
                "interval_coverage": "interval_covered",
            }
            for key, value in stats.items():
                if not isinstance(value, dict):
                    continue
                if "count" in value:
                    k = int(g[numerator_cols.get(key, key)].sum())
                    n = denominators.get(key, len(g))
                    assert value["count"] == k and value["denominator"] == n, (case_name, method, key)
                    expected = None if n == 0 else k / n
                    if expected is None:
                        assert value["estimate"] is None and value["ci95"] == [None, None]
                    else:
                        er = abs(value["estimate"] - expected)
                        ei = float(np.max(np.abs(np.asarray(value["ci95"]) - wilson(k, n))))
                        max_errors["rate_estimate"] = max(max_errors["rate_estimate"], er)
                        max_errors["wilson_endpoint"] = max(max_errors["wilson_endpoint"], ei)
                        assert er < 1e-14 and ei < 1e-13
                    rate_checks += 1
                elif "estimate" in value and key in g.columns:
                    er = abs(float(g[key].mean()) - value["estimate"])
                    max_errors["mean_estimate"] = max(max_errors["mean_estimate"], er)
                    assert er < 2e-12, (case_name, method, key, er)
                    mean_checks += 1
        for comp in case["paired_comparisons"].values():
            a = frame[frame.method.eq(comp["active"])].set_index("seed").sort_index()
            b = frame[frame.method.eq(comp["comparator"])].set_index("seed").sort_index()
            assert a.index.equals(b.index) and len(a) == comp["n_pairs"]
            for metric, values in comp["metrics"].items():
                er = abs(float((a[metric].astype(float) - b[metric].astype(float)).mean()) - values["estimate"])
                max_errors["paired_estimate"] = max(max_errors["paired_estimate"], er)
                assert er < 2e-12, (case_name, metric, er)
                paired_checks += 1
    check("V2_ALL_SUMMARY_RATES_AND_WILSON", True, {"comparisons": rate_checks})
    check("V2_ALL_SUMMARY_MEANS", True, {"comparisons": mean_checks})
    check("V2_ALL_PAIRED_POINT_ESTIMATES", True, {"comparisons": paired_checks})
    for fn, expected in summary["source_sha256"].items():
        check("V2_FROZEN_HASH_" + fn, sha(V2 / fn) == expected)

    # This diagnostic reconstructs only already-used random numbers. It does
    # not add seeds, alter intervals, rerun discovery or retune any method.
    subset = data[(data.condition == "main") & (data.scenario == "no_carryover") & (data.system == "pbq_qf")]
    noise_diagnostics = []
    for method, n, start in [("bounded_repeat", 32, 0), ("bounded_tail4", 28, 4), ("bounded_fresh", 8, 0)]:
        g = subset[subset.method.eq(method)].sort_values("seed")
        means = []
        for seed in g.seed:
            errors = np.random.default_rng(np.random.SeedSequence([int(seed), 21])).normal(0., .03, 32)
            means.append(errors[start:start+n].mean())
        means = np.asarray(means)
        z = means / (.03 / np.sqrt(n))
        residual = float(np.max(np.abs((g.estimate - g.true_clean_response).to_numpy() - means)))
        assert residual < 1e-12
        noise_diagnostics.append({
            "method": method, "n_included": n, "zero_based_noise_slice": [start, start+n],
            "max_estimator_minus_truth_minus_reconstructed_noise": residual,
            "standardized_noise_exceedances": int((abs(z) > norm.ppf(.975)).sum()),
            "reported_interval_failures": int((~g.interval_covered.astype(bool)).sum()),
            "standardized_noise_mean": float(z.mean()),
            "standardized_noise_sd_ddof1": float(z.std(ddof=1)),
            "max_abs_standardized_noise": float(abs(z).max()),
        })
    check("V2_COVERAGE_NOISE_INDEX_DIAGNOSTIC", True)
    main_cov = []
    for case in summary["cases"]:
        if case["case"]["condition"] != "main":
            continue
        for method, stats in case["methods"].items():
            if "interval_coverage" in stats:
                main_cov.append({"case": case["case"]["name"], "method": method, **stats["interval_coverage"]})
    lower_than_nominal_upper = [r for r in main_cov if r["ci95"][1] < .95]
    result = {
        "audit_id": "AUDIT-V2-OUTPUTS", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL", "status_scope": "Arithmetic, bookkeeping, frozen-source identity and targeted indexing checks only. This is not a PASS for empirical nominal coverage or physical validation.",
        "command": "python audit/check_v2_results.py", "exit_state": "success" if not failures else "assertion/check failure",
        "input_sha256": {"research/v2/trial_results.csv": sha(V2 / "trial_results.csv"), "research/v2/summary.json": sha(V2 / "summary.json"), "research/v2/protocol.json": sha(V2 / "protocol.json")},
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "counts": {"policy_rows": len(data), "case_campaigns": len(campaigns), "main_case_campaigns": len(main_campaigns), "cases": 32, "methods": 13},
        "checks": checks, "failures": failures, "max_numeric_errors": max_errors,
        "coverage_noise_diagnostic": noise_diagnostics,
        "empirical_coverage_validation": {
            "status": "PARTIAL", "nominal": .95,
            "finding": "Bounded tail repetition covers 183/200 no-carryover targets (91.5%; Wilson 95% interval 86.81%–94.63%). The same seed-indexed noise is reused across cases; repeated low-coverage rows are not independent replication. Fresh-only covers 186/200 (93%). The finite-simulation shortfalls are retained and cannot be called empirical validation of 95% coverage.",
            "main_case_method_rows_with_wilson_upper_below_nominal": lower_than_nominal_upper,
            "limits": "Conditional mathematical coverage follows from stated assumptions and proof; a finite Monte Carlo proportion can differ. The diagnostic finds no noise-index or denominator defect in the zero-carryover check. It does not prove that every implementation path is error free. No retuning, additional seeds or coverage repair occurred."
        },
        "independence": "A separate review agent reconciled saved policy outputs and reconstructed existing random-number streams. The review shares the source data and software environment. It is not an independent human or external-team replication.",
        "not_checked_here": ["All bootstrap interval random realizations were not recomputed; pairing logic and all paired point estimates were checked.", "Physical material bounds and laboratory validity were not assessed from new measurements.", "The notebook and final document presentation are separate review stages."]
    }
    (ROOT / "audit" / "v2_output_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": result["status"], "checks": len(checks), "comparisons": {"rates": rate_checks, "means": mean_checks, "paired": paired_checks}, "max_numeric_errors": max_errors, "coverage_status": "PARTIAL"}, indent=2))


if __name__ == "__main__":
    main()
