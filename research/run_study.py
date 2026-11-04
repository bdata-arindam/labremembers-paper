"""Reproduce frozen simulation, per-campaign data, uncertainty and illustrations."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time
import numpy as np
import pandas as pd
import scipy
from lab_memory import (REGIMES, METHODS, METHOD_LABELS, THRESHOLD, SIGMA,
                        campaign, parity_fixture)

HERE = Path(__file__).resolve().parent
RATE_FIELDS = ["accepted","false_accept","true_accept","rejected","false_reject",
               "true_reject","unresolved"]
MEAN_FIELDS = ["absolute_error","cost","assays","target_assays","fresh_assays",
               "washes","conditioning_assays"]
PAIRED_FIELDS = ["false_accept","true_accept","false_reject","unresolved",
                 "absolute_error","cost","fresh_assays","washes"]
COMPARATORS = ["history_repeat","candidate_repeat","fresh_only","history_fixed",
               "active_no_cost"]


def json_default(value):
    if isinstance(value,np.generic):
        return value.item()
    if isinstance(value,np.ndarray):
        return value.tolist()
    raise TypeError(type(value).__name__)


def write_json(path,data):
    path.write_text(json.dumps(data,indent=2,default=json_default,allow_nan=False)+"\n")


def rate(count,denominator):
    """Wilson 95% interval; zero denominator is undefined rather than zero."""
    count,denominator = int(count),int(denominator)
    if denominator == 0:
        return {"count":count,"denominator":0,"estimate":None,"ci95":[None,None]}
    p = count/denominator
    z = 1.959963984540054
    d = 1+z*z/denominator
    mid = (p+z*z/(2*denominator))/d
    half = z*np.sqrt(p*(1-p)/denominator+z*z/(4*denominator**2))/d
    return {"count":count,"denominator":denominator,"estimate":p,
            "ci95":[max(0.,mid-half),min(1.,mid+half)]}


def boot_mean(values,indices):
    values = np.asarray(values,float)
    boot = values[indices].mean(axis=1)
    return {"estimate":float(values.mean()),
            "ci95":np.quantile(boot,[.025,.975]).tolist()}


def aggregate(frame,n_boot=5000):
    records = []
    flat = []
    for ridx,regime in enumerate(REGIMES):
        subset = frame[frame.regime==regime.name]
        seeds = sorted(subset.seed.unique())
        n = len(seeds)
        indices = np.random.default_rng(990_000+ridx).integers(0,n,size=(n_boot,n))
        canonical = subset[subset.method==METHODS[0]].set_index("seed").loc[seeds]
        n_good = int(canonical.true_good.sum())
        record = {"name":regime.name,"parameters":asdict(regime),"n_campaigns":n,
                  "true_good":rate(n_good,n),"methods":{},"paired_comparisons":{}}
        for method in METHODS:
            g = subset[subset.method==method].set_index("seed").loc[seeds]
            # Every method confirms exactly the same frozen candidate per seed.
            if not np.allclose(g.true_clean_response,canonical.true_clean_response):
                raise AssertionError("Unpaired candidate truth")
            out = {"label":METHOD_LABELS[method],"n":n}
            for field in RATE_FIELDS:
                out[field] = rate(g[field].sum(),n)
            out["false_fraction_among_accepted"] = rate(g.false_accept.sum(),g.accepted.sum())
            out["false_accept_given_invalid"] = rate(g.false_accept.sum(),n-n_good)
            out["true_accept_given_valid"] = rate(g.true_accept.sum(),n_good)
            out["false_reject_given_valid"] = rate(g.false_reject.sum(),n_good)
            for field in MEAN_FIELDS:
                out[field] = boot_mean(g[field].to_numpy(),indices)
            has_cross = g.first_decision_cost.notna()
            out["first_threshold_crossing"] = rate(has_cross.sum(),n)
            out["descriptive_mean_first_crossing_cost"] = (
                float(g.loc[has_cross,"first_decision_cost"].mean()) if has_cross.any() else None)
            out["first_crossing_note"] = "Hypothetical early crossing; simulation continued to the full policy budget cap."
            record["methods"][method] = out
            flat.append({"regime":regime.name,"method":method,"n":n,"n_true_good":n_good,
                         **{k:out[k]["estimate"] for k in RATE_FIELDS+MEAN_FIELDS+
                            ["false_fraction_among_accepted","false_accept_given_invalid","true_accept_given_valid","false_reject_given_valid"]}})
        active = subset[subset.method=="active_confirmation"].set_index("seed").loc[seeds]
        for other in COMPARATORS:
            comp = subset[subset.method==other].set_index("seed").loc[seeds]
            out = {"direction":"active_confirmation minus comparator", "n_pairs":n,
                   "bootstrap_replicates":n_boot,"metrics":{}}
            for field in PAIRED_FIELDS:
                difference = active[field].to_numpy(float)-comp[field].to_numpy(float)
                out["metrics"][field] = boot_mean(difference,indices)
            record["paired_comparisons"][other]=out
        records.append(record)
    return records,pd.DataFrame(flat)


def export_development_examples():
    examples=[]
    for name in ["strong_carryover","ineffective_wash","nonlinear_response_stress"]:
        regime=next(r for r in REGIMES if r.name==name)
        _,example=campaign(7,regime,record=True)
        example["selection"]="Fixed development seed 7, declared before evaluation; illustrative, not a performance estimate."
        examples.append(example)
    primary=examples[0]
    distances=[np.linalg.norm(np.array(t["action"]["nominal"])-t["private"]["actual"],ord=1)
               for t in primary["discovery"]]
    step=int(np.argmax(distances))
    primary["mechanism_illustration_step"] = step
    primary["mechanism_step_selection"]="Largest composition discrepancy during fixed development-seed discovery; display-only choice."
    data={"kind":"fixed-development-seed illustrations","examples":examples}
    write_json(HERE/"examples.json",data)
    write_json(HERE/"parity_fixture.json",parity_fixture())
    return data


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--n",type=int,default=None)
    parser.add_argument("--start-seed",type=int,default=None)
    parser.add_argument("--bootstrap",type=int,default=5000)
    args=parser.parse_args()
    protocol=json.loads((HERE/"protocol.json").read_text())
    if protocol["status"] != "frozen before evaluation":
        raise RuntimeError("Freeze protocol.json before evaluation.")
    n=args.n or protocol["planned_campaigns_per_regime"]
    first=args.start_seed if args.start_seed is not None else protocol["evaluation_seed_start"]
    if first<10000:
        raise ValueError("Evaluation seeds must be disjoint from development seeds 0-19.")
    t0=time.perf_counter()
    allrows=[]
    for regime in REGIMES:
        rows=[]
        for seed in range(first,first+n):
            result,_=campaign(seed,regime,budget=protocol["primary_budget"])
            rows.extend(result)
        allrows.extend(rows)
        # Checkpoint completed regimes, retaining every simulated campaign.
        pd.DataFrame(allrows).to_csv(HERE/"trial_results.csv",index=False)
        print(f"{regime.name}: {n} campaigns complete; elapsed {time.perf_counter()-t0:.1f} s",flush=True)
    frame=pd.DataFrame(allrows)
    regimes,flat=aggregate(frame,args.bootstrap)
    flat.to_csv(HERE/"summary_table.csv",index=False)
    summary={"title":protocol["title"],"scope":protocol["scope"],
             "generated_utc":datetime.now(timezone.utc).isoformat(),
             "evaluation_seed_start":first,"evaluation_seed_end":first+n-1,
             "campaigns_per_regime":n,"number_of_regimes":len(REGIMES),
             "number_of_methods":len(METHODS),"total_campaigns":n*len(REGIMES),
             "total_policy_runs":len(frame),"threshold":THRESHOLD,"sigma":SIGMA,
             "primary_budget":protocol["primary_budget"],
             "bootstrap_replicates":args.bootstrap,
             "uncertainty":f"Regime-specific Wilson 95% intervals for rates; {args.bootstrap} paired campaign-seed percentile bootstrap replicates for method differences. No pooled independence assumption across regimes.",
             "rare_event_caveat":"A paired percentile interval can collapse to [0,0] if no discordant binary events are observed. This is not evidence of equivalence; inspect Wilson intervals and event counts.",
             "continuous_uncertainty":"Campaign bootstrap 95% intervals for means.",
             "first_decision_note":"A hypothetical crossing during a continuing fixed-budget run, not an executed stopping policy.",
             "software":{"python":platform.python_version(),"numpy":np.__version__,
                         "scipy":scipy.__version__,"pandas":pd.__version__},
             "source_sha256":{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                              for name in ["protocol.json","lab_memory.py","run_study.py"]},
             "regimes":regimes,"elapsed_seconds":time.perf_counter()-t0}
    write_json(HERE/"summary.json",summary)
    export_development_examples()
    print(f"Saved {len(frame)} policy runs and full summaries in {time.perf_counter()-t0:.1f} s",flush=True)


if __name__=="__main__":
    main()
