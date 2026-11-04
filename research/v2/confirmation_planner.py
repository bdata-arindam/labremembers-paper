"""Oracle-free finite-menu planning for a bounded fixed-candidate response.

The policy receives scalar response sensitivity and declared apparatus bounds,
never response coefficients, simulator state or a clean-response evaluation.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math

Z95 = 1.959963984540054


@dataclass(frozen=True)
class PlannerInputs:
    lipschitz_l1: float
    rho_upper: float
    eta_upper: float
    lambda_lower: float = 1.0
    sigma: float = .03
    budget: float = 32.0
    wash_cost: float = .5
    fresh_cost: float = 4.0
    distance_initial: float = 2.0

    def validate(self):
        if not (self.lipschitz_l1>=0 and 0<=self.rho_upper<1 and
                0<=self.eta_upper<=1 and 0<self.lambda_lower<=1 and
                self.sigma>=0 and self.budget>=2 and self.wash_cost>=0 and
                self.fresh_cost>0 and self.distance_initial>=0):
            raise ValueError("Invalid planner inputs")


def block(distance, count, washes, info):
    """Summed predictable bias bound and final state-distance bound."""
    if count==0:
        return 0.0,distance
    retained=info.rho_upper*info.eta_upper**washes
    q=1-info.lambda_lower*(1-retained)
    power=q**count
    geometric=(1-power)/(1-q)
    return info.lipschitz_l1*retained*distance*geometric,distance*power


def evaluate_counts(n_routine,n_wash1,n_wash3,n_fresh,info):
    n=n_routine+n_wash1+n_wash3+n_fresh
    if n<2:
        return None
    spent=n_routine+n_wash1*(1+info.wash_cost)+n_wash3*(1+3*info.wash_cost)+n_fresh*info.fresh_cost
    if spent>info.budget+1e-9:
        return None
    distance=info.distance_initial
    summed_bias=0.0
    for count,washes in [(n_wash3,3),(n_wash1,1),(n_routine,0)]:
        contribution,distance=block(distance,count,washes,info)
        summed_bias+=contribution
    noise_radius=Z95*info.sigma/math.sqrt(n)
    half_width=summed_bias/n+noise_radius
    return {"n_routine":n_routine,"n_wash1":n_wash1,"n_wash3":n_wash3,
            "n_fresh":n_fresh,"n_assays":n,"wash_operations":n_wash1+3*n_wash3,
            "cost":spent,"summed_bias_bound":summed_bias,"mean_bias_bound":summed_bias/n,
            "noise_radius":noise_radius,"half_width":half_width,"final_distance_bound":distance}


def optimize_plan(info):
    """Exhaustively minimize final half-width in the declared finite menu."""
    info.validate()
    best=None
    best_key=None
    feasible_count=0
    b=info.budget
    c1=1+info.wash_cost
    c3=1+3*info.wash_cost
    for nf in range(int(math.floor(b/info.fresh_cost+1e-9))+1):
        after_f=b-nf*info.fresh_cost
        for n3 in range(int(math.floor(after_f/c3+1e-9))+1):
            after_3=after_f-n3*c3
            for n1 in range(int(math.floor(after_3/c1+1e-9))+1):
                after_1=after_3-n1*c1
                for nr in range(int(math.floor(after_1+1e-9))+1):
                    result=evaluate_counts(nr,n1,n3,nf,info)
                    if result is None: continue
                    feasible_count+=1
                    key=(result["half_width"],result["cost"],nf,result["wash_operations"],-nr)
                    if best_key is None or key<best_key:
                        best_key=key
                        best=result
    if best is None:
        raise ValueError("No plan with at least two assays fits the budget")
    best["feasible_count_tuples"]=feasible_count
    best["order"]=[{"kind":"wash_candidate","washes":3,"fresh":False,"count":best["n_wash3"]},
                   {"kind":"wash_candidate","washes":1,"fresh":False,"count":best["n_wash1"]},
                   {"kind":"candidate","washes":0,"fresh":False,"count":best["n_routine"]},
                   {"kind":"fresh_candidate","washes":0,"fresh":True,"count":best["n_fresh"]}]
    best["inputs"]=asdict(info)
    return best


def predictable_bounds(schedule,info):
    """Schedule items have fresh and washes fields; all nominal recipes equal x*."""
    distance=info.distance_initial
    rows=[]
    for step,action in enumerate(schedule):
        before=distance
        if action["fresh"]:
            retained=0.0
            bias=0.0
        else:
            retained=info.rho_upper*info.eta_upper**action["washes"]
            bias=info.lipschitz_l1*retained*distance
            distance*=1-info.lambda_lower*(1-retained)
        rows.append({"step":step,"bias_bound":bias,"distance_before":before,
                     "distance_after":distance,"retained_upper":retained})
    return rows


def expand_plan(plan):
    return [{"kind":b["kind"],"washes":b["washes"],"fresh":b["fresh"]}
            for b in plan["order"] for _ in range(b["count"])]


def fixture():
    cases=[]
    for name,info in [
        ("low_carryover",PlannerInputs(1.8,.02,.3,1.0)),
        ("high_carryover",PlannerInputs(1.8,.5,.3,1.0)),
        ("persistent_memory",PlannerInputs(1.8,.5,.3,.4)),
        ("broad_bounds",PlannerInputs(1.8,.8,.9,.4)),
        ("small_budget",PlannerInputs(1.8,.5,.3,1.0,budget=8))]:
        plan=optimize_plan(info)
        cases.append({"name":name,"plan":plan,"step_bounds":predictable_bounds(expand_plan(plan),info)})
    return {"kind":"deterministic fixed-final planner parity fixture","cases":cases,
            "fixed_final_z":Z95,"coverage_scope":"Conditional on externally valid bounds and independent Gaussian noise; fixed final schedules only."}


if __name__=="__main__":
    import json
    from pathlib import Path
    Path(__file__).with_name("planner_parity_fixture.json").write_text(json.dumps(fixture(),indent=2)+"\n")
