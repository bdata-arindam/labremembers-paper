"""Execute every frozen v2 primary and predeclared sensitivity case."""
from __future__ import annotations
from datetime import datetime,timezone
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import time
import numpy as np
import pandas as pd
import scipy
from opv_confirmation import (make_cases,campaign,METHODS,LABELS,BOUNDED_METHODS,
                              THRESHOLD,SIGMA,get_surface,cached_plan)
from confirmation_planner import PlannerInputs

HERE=Path(__file__).resolve().parent
RATES=["accepted","rejected","unresolved","false_accept","true_accept","false_reject","true_reject"]
MEANS=["absolute_error","cost","assays","target_assays","fresh_assays","washes","conditioning_assays"]
COMPARISONS=[("bounded_planner","bounded_fresh"),("bounded_planner","bounded_tail4"),
             ("bounded_planner","bounded_repeat"),("active_confirmation","history_repeat"),
             ("active_confirmation","active_no_conditioning"),("candidate_repeat","tail_repeat4")]
DIFFERENCES=["false_accept","true_accept","false_reject","unresolved","absolute_error","cost"]


def json_default(value):
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,np.ndarray):return value.tolist()
    raise TypeError(type(value).__name__)


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,default=json_default,allow_nan=False)+"\n")


def rate(count,n):
    count,n=int(count),int(n)
    if n==0:return {"count":count,"denominator":0,"estimate":None,"ci95":[None,None]}
    p=count/n;z=1.959963984540054;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {"count":count,"denominator":n,"estimate":p,"ci95":[max(0.,center-radius),min(1.,center+radius)]}


def boot(values,index):
    values=np.asarray(values,float)
    return {"estimate":float(np.mean(values)),"ci95":np.quantile(values[index].mean(axis=1),[.025,.975]).tolist()}


def aggregate(frame,cases):
    records=[];flat=[];paired=[]
    for case_index,case in enumerate(cases):
        subset=frame[frame.case==case.name]
        seeds=sorted(subset.seed.unique());n=len(seeds)
        idx=np.random.default_rng(np.random.SeedSequence([990001,case_index])).integers(0,n,(5000,n))
        first=subset[subset.method==METHODS[0]].set_index("seed").loc[seeds]
        good=int(first.true_good.sum())
        rec={"case":case.json(),"n_campaigns":n,"true_good":rate(good,n),"methods":{},"paired_comparisons":{}}
        for method in METHODS:
            g=subset[subset.method==method].set_index("seed").loc[seeds]
            if not np.allclose(g.true_clean_response,first.true_clean_response):raise AssertionError("Candidate pairing lost")
            out={"label":LABELS[method],"n":n}
            for k in RATES:out[k]=rate(g[k].sum(),n)
            out["false_fraction_among_accepted"]=rate(g.false_accept.sum(),g.accepted.sum())
            out["false_accept_given_invalid"]=rate(g.false_accept.sum(),n-good)
            out["true_accept_given_valid"]=rate(g.true_accept.sum(),good)
            out["false_reject_given_valid"]=rate(g.false_reject.sum(),good)
            for k in MEANS:out[k]=boot(g[k].to_numpy(),idx)
            if method in BOUNDED_METHODS:
                out["interval_coverage"]=rate(g.interval_covered.astype(bool).sum(),n)
                out["ci_halfwidth"]=boot(g.ci_halfwidth.to_numpy(float),idx)
                out["mean_bias_bound"]=boot(g.mean_bias_bound.to_numpy(float),idx)
            rec["methods"][method]=out
            row={"case":case.name,"system":case.system,"condition":case.condition,"scenario":case.scenario,
                 "method":method,"n":n,"true_good_count":good}
            for metric,v in out.items():
                if isinstance(v,dict) and "estimate" in v:
                    row[metric]=v["estimate"];row[metric+"_ci95_low"],row[metric+"_ci95_high"]=v["ci95"]
                    if "count" in v:row[metric+"_count"]=v["count"];row[metric+"_denominator"]=v["denominator"]
            flat.append(row)
        for active,comparator in COMPARISONS:
            a=subset[subset.method==active].set_index("seed").loc[seeds]
            b=subset[subset.method==comparator].set_index("seed").loc[seeds]
            result={"active":active,"comparator":comparator,"direction":"active minus comparator","n_pairs":n,"metrics":{}}
            fields=DIFFERENCES+(["ci_halfwidth"] if active in BOUNDED_METHODS and comparator in BOUNDED_METHODS else [])
            for metric in fields:
                delta=a[metric].to_numpy(float)-b[metric].to_numpy(float)
                v=boot(delta,idx);result["metrics"][metric]=v
                paired.append({"case":case.name,"active":active,"comparator":comparator,"metric":metric,
                               "difference":v["estimate"],"ci95_low":v["ci95"][0],"ci95_high":v["ci95"][1],"n_pairs":n})
            rec["paired_comparisons"][active+"__minus__"+comparator]=result
        records.append(rec)
    pd.DataFrame(flat).to_csv(HERE/"all_results_with_intervals.csv",index=False)
    pd.DataFrame(paired).to_csv(HERE/"paired_comparisons.csv",index=False)
    return records


def planning_diagnostics(cases):
    rows=[]
    for case in cases:
        if case.scenario not in ["low_carryover","high_carryover"] or case.condition not in ["main","broad_bounds","delaunay_sensitivity"]:continue
        surface=get_surface(case.system,case.family)
        for budget in [8.,16.,32.,64.]:
            for fresh_cost in [1.,2.,4.,8.]:
                info=PlannerInputs(surface.lipschitz_l1,case.rho_upper,case.eta_upper,case.lambda_lower,
                                   SIGMA,budget,case.wash_cost,fresh_cost)
                plan=cached_plan(info)
                rows.append({"case":case.name,"system":case.system,"scenario":case.scenario,
                             "condition":case.condition,"family":case.family,**asdict(info),
                             **{k:v for k,v in plan.items() if not isinstance(v,(list,dict))}})
    pd.DataFrame(rows).to_csv(HERE/"planning_diagnostics.csv",index=False)


def main():
    protocol=json.loads((HERE/"protocol.json").read_text())
    if protocol["status"]!="frozen before evaluation":raise RuntimeError("Freeze v2 before report seeds")
    cases=make_cases(protocol)
    start=time.perf_counter();allrows=[];case_times=[]
    for case in cases:
        t=time.perf_counter();rows=[]
        for seed in range(200000,200000+case.n_campaigns):
            result,_=campaign(seed,case)
            rows.extend(result)
        allrows.extend(rows)
        pd.DataFrame(allrows).to_csv(HERE/"trial_results.csv",index=False)
        case_times.append({"case":case.name,"seconds":time.perf_counter()-t})
        print(f"{case.name}: {case.n_campaigns} campaigns; elapsed {time.perf_counter()-start:.1f} s",flush=True)
    frame=pd.DataFrame(allrows)
    records=aggregate(frame,cases)
    examples=[]
    for name in ["high_carryover","strongly_persistent_stress"]:
        case=next(c for c in cases if c.system=="pbq_qf" and c.condition=="main" and c.scenario==name)
        _,example=campaign(100007,case,record=True);examples.append(example)
    write_json(HERE/"examples.json",{"kind":"predeclared development illustrations","examples":examples})
    planning_start=time.perf_counter();planning_diagnostics(cases)
    source_names=["protocol.json","opv_confirmation.py","confirmation_planner.py","opv_bernstein.py","run_v2.py","emulator_models.json"]
    summary={"title":protocol["title"],"generated_utc":datetime.now(timezone.utc).isoformat(),
             "scope":"Measured-OPV-informed emulators with synthetic, uncalibrated carryover and assumed resource costs.",
             "total_case_campaigns":sum(c.n_campaigns for c in cases),"main_case_campaigns":sum(c.n_campaigns for c in cases if c.condition=="main"),
             "total_policy_runs":len(frame),"number_of_methods":len(METHODS),"number_of_cases":len(cases),
             "main_seed_start":200000,"main_seed_end":200199,"sensitivity_seed_end":200099,
             "paired_seed_note":"The same200 seeded campaigns are reused across cases; no pooled independence is claimed.",
             "threshold":THRESHOLD,"sigma_assumed":SIGMA,"budget":32,"bootstrap_replicates":5000,
             "confidence_scope":"Bounded fixed-final intervals have conditional95% Gaussian coverage under supplied parameter/Lipschitz/noise assumptions. This is emulator-only; empirical-contrast noise deliberately violates the noise assumption.",
             "rare_event_caveat":"Zero-width paired bootstrap intervals with no discordant events do not establish equivalence; inspect individual counts and Wilson intervals.",
             "source_sha256":{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in source_names},
             "software":{"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__,"pandas":pd.__version__},
             "case_times":case_times,"planning_diagnostics_seconds":time.perf_counter()-planning_start,
             "elapsed_seconds":time.perf_counter()-start,"cases":records}
    write_json(HERE/"summary.json",summary)
    print(f"Saved {len(frame)} v2 policy runs in {time.perf_counter()-start:.1f} s",flush=True)


if __name__=="__main__":main()
