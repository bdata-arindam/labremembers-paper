"""Four-component confirmation benchmark with an explicit latent-data boundary."""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from functools import lru_cache
import copy
import json
import math
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.special import ndtr, logsumexp
from confirmation_planner import (PlannerInputs, optimize_plan, expand_plan,
                                  predictable_bounds, Z95)
from opv_bernstein import CubicOPV, APPLICATION

HERE=Path(__file__).resolve().parent
THRESHOLD=.90
SIGMA=.03
VERTICES=np.eye(4)
METHODS=["sequence_repeat","candidate_repeat","tail_repeat4","wash_once","fresh_only",
         "history_repeat","active_confirmation","active_no_conditioning",
         "bounded_repeat","bounded_tail4","bounded_wash_once","bounded_fresh","bounded_planner"]
LABELS={"sequence_repeat":"Predecessor sequence replay","candidate_repeat":"Naive candidate repetition",
 "tail_repeat4":"Naive repetition, discard first 4","wash_once":"Naive one-wash repetition",
 "fresh_only":"Naive independent fresh verification","history_repeat":"History model, candidate repetition",
 "active_confirmation":"Adaptive covariance controls","active_no_conditioning":"Adaptive controls, no conditioning",
 "bounded_repeat":"Bounded candidate repetition","bounded_tail4":"Bounded repetition, discard first 4",
 "bounded_wash_once":"Bounded one-wash repetition","bounded_fresh":"Bounded independent fresh verification",
 "bounded_planner":"Bound-optimal preplanned confirmation"}
MODEL_METHODS={"history_repeat","active_confirmation","active_no_conditioning"}
BOUNDED_METHODS={m for m in METHODS if m.startswith("bounded_")}


def features(x):
    x=np.asarray(x,float)
    return np.stack([x[...,i]**2 for i in range(4)]+
                    [2*x[...,i]*x[...,j] for i in range(4) for j in range(i+1,4)],axis=-1)


def candidate_pool():
    return np.array([[a/10,b/10,c/10,(10-a-b-c)/10]
                     for a in range(11) for b in range(11-a) for c in range(11-a-b)
                     if 1/6<= (a+b)/10 <=5/6])


@dataclass(frozen=True)
class Case:
    system: str
    scenario: str
    condition: str
    rho: float
    eta: float
    memory_lambda: float
    rho_upper: float
    eta_upper: float
    lambda_lower: float
    family: str = "cubic_bernstein"
    noise: str = "gaussian"
    fresh_cost: float = 4.
    wash_cost: float = .5
    budget: float = 32.
    n_campaigns: int = 200

    @property
    def name(self):
        return f"{self.system}__{self.condition}__{self.scenario}"

    def json(self):
        return {"name":self.name,**asdict(self)}


def make_cases(protocol):
    cases=[]
    for system in protocol["measured_data"]["systems"]:
        main=[]
        for s in protocol["main_scenarios"]:
            c=Case(system,s["name"],"main",s["rho"],s["eta"],s["lambda"],
                   s["rho_upper"],s["eta_upper"],s["lambda_lower"])
            main.append(c);cases.append(c)
        for c in main:
            if c.scenario not in protocol["predeclared_sensitivities"]["scenarios"]:continue
            cases.append(replace(c,condition="delaunay_sensitivity",family="piecewise_affine",n_campaigns=100))
            cases.append(replace(c,condition="broad_bounds",rho_upper=.8,eta_upper=.9,lambda_lower=.4,n_campaigns=100))
            cases.append(replace(c,condition="empirical_contrast_noise",noise="empirical_contrast",n_campaigns=100))
            cases.append(replace(c,condition="equal_fresh_cost",fresh_cost=1.,n_campaigns=100))
    return cases


class PiecewiseScore:
    def __init__(self,system):
        sys.path.insert(0,str(APPLICATION))
        from opv_piecewise_affine import PiecewiseAffineOPV
        self._degradation=PiecewiseAffineOPV.from_system(system)
        self.lipschitz_l1=self._degradation.lipschitz_l1
        self.family="piecewise_affine"
        self.system=system

    def __call__(self,x):
        return 1.-self._degradation(x)


@lru_cache(maxsize=4)
def get_surface(system,family):
    return CubicOPV.from_saved(system) if family=="cubic_bernstein" else PiecewiseScore(system)


@lru_cache(maxsize=2)
def contrast_noise(system):
    frame=pd.read_csv(APPLICATION/"measured_sda_replicate_pairs.csv")
    differences=frame.loc[frame.system==system,"difference_2_minus_1"].to_numpy(float)/2
    return np.r_[differences,-differences]


def make_rng(seed,stage):
    return np.random.default_rng(np.random.SeedSequence([int(seed),int(stage)]))


@dataclass
class Action:
    nominal: np.ndarray
    washes: int = 0
    fresh: bool = False
    kind: str = "candidate"

    def json(self):
        return {"nominal":np.asarray(self.nominal).tolist(),"washes":self.washes,
                "fresh":self.fresh,"kind":self.kind}


def cost(a,case):
    return case.fresh_cost if a.fresh else 1+a.washes*case.wash_cost


class World:
    """Only this simulator and the final scorer evaluate the latent emulator."""
    def __init__(self,surface,case,seed,stage=11,noise_mode="gaussian"):
        self.surface=surface
        self.case=case
        self.h=np.array([1.,0.,0.,0.])
        self.rng=make_rng(seed,stage)
        self.noise_mode=noise_mode

    def assay(self,a,noise=None):
        before=self.h.copy()
        r=0. if a.fresh else self.case.rho*self.case.eta**a.washes
        actual=a.nominal.copy() if a.fresh else (1-r)*a.nominal+r*self.h
        latent=float(self.surface(actual))
        if noise is None:
            eps=(float(self.rng.normal(0,SIGMA)) if self.noise_mode=="gaussian" else
                 float(self.rng.choice(contrast_noise(self.case.system))))
        else:eps=float(noise)
        if not a.fresh:
            self.h=(1-self.case.memory_lambda)*self.h+self.case.memory_lambda*actual
        return latent+eps,{"actual":actual.tolist(),"residual_before":before.tolist(),
                           "residual_after":self.h.tolist(),"latent_response":latent,
                           "noise":eps,"retained_fraction":r}


class LinearModel:
    def __init__(self):
        self.mean=np.full(10,.6)
        self.cov=.25*np.eye(10)

    def predict(self,phi):
        return phi@self.mean,np.einsum("...i,ij,...j->...",phi,self.cov,phi)

    def update(self,phi,y):
        v=self.cov@phi;s=SIGMA**2+phi@v
        self.mean+=v*(y-phi@self.mean)/s
        self.cov-=np.outer(v,v)/s
        self.cov=(self.cov+self.cov.T)/2


class HistoryModel:
    """Policy sees only known envelopes, commands and noisy observations."""
    def __init__(self,rho_upper,eta_upper):
        rs=[r for r in [0,.001,.01,.05,.1,.25,.4,.7] if r<=rho_upper+1e-12]
        es=[e for e in [.05,.2,.5,.8] if e<=eta_upper+1e-12]
        grid=np.array([(r,e) for r in rs for e in es])
        self.rhos=grid[:,0];self.etas=grid[:,1]
        n=len(grid)
        self.mean=np.full((n,10),.6)
        self.cov=np.repeat((.25*np.eye(10))[None],n,axis=0)
        self.logw=np.full(n,-np.log(n))
        self.h=np.repeat(np.array([[1.,0.,0.,0.]]),n,axis=0)

    def weights(self):return np.exp(self.logw-logsumexp(self.logw))

    def action_features(self,a):
        if a.fresh:
            actual=np.repeat(a.nominal[None],len(self.rhos),axis=0)
        else:
            retained=self.rhos*self.etas**a.washes
            actual=(1-retained[:,None])*a.nominal+retained[:,None]*self.h
        return features(actual),actual

    def update(self,a,y):
        phi,actual=self.action_features(a)
        mu=np.einsum("gi,gi->g",phi,self.mean)
        v=np.einsum("gij,gj->gi",self.cov,phi)
        s=np.maximum(SIGMA**2+np.einsum("gi,gi->g",phi,v),1e-14)
        error=y-mu
        self.logw+=-.5*(np.log(2*np.pi*s)+error**2/s)
        self.logw-=logsumexp(self.logw)
        self.mean+=v*(error/s)[:,None]
        self.cov-=np.einsum("gi,gj->gij",v,v)/s[:,None,None]
        self.cov=(self.cov+np.swapaxes(self.cov,1,2))/2
        if not a.fresh:self.h=actual

    def target(self,x):
        phi=features(x);mus=self.mean@phi
        variances=np.maximum(np.einsum("i,gij,j->g",phi,self.cov,phi),1e-14)
        w=self.weights();mu=float(w@mus)
        return {"mean":mu,"variance":max(float(w@(variances+mus**2)-mu**2),1e-14),
                "probability":float(w@ndtr((mus-THRESHOLD)/np.sqrt(variances))),
                "rho_mean":float(w@self.rhos)}

    def utility(self,a,candidate,price):
        phi,_=self.action_features(a);clean=features(candidate)
        mus=np.einsum("gi,gi->g",phi,self.mean)
        vars_y=SIGMA**2+np.einsum("gi,gij,gj->g",phi,self.cov,phi)
        target_means=self.mean@clean
        within=np.einsum("i,gij,gj->g",clean,self.cov,phi)
        w=self.weights();mu_y=w@mus;mu_t=w@target_means
        covariance=w@(within+mus*target_means)-mu_y*mu_t
        variance=max(float(w@(vars_y+mus**2)-mu_y**2),1e-14)
        return float(covariance**2/variance/price)


def discovery(seed,case,surface,record=False):
    world=World(surface,case,seed)
    stateless=LinearModel();history_model=HistoryModel(case.rho_upper,case.eta_upper)
    pool=candidate_pool();phi=features(pool)
    available=np.ones(len(pool),bool)
    rng=make_rng(seed,12)
    chosen=[];history=[]
    for step in range(32):
        if step<12:
            idx=int(rng.choice(np.flatnonzero(available)))
        else:
            mean,var=stateless.predict(phi)
            scores=mean+1.5*np.sqrt(np.maximum(var,0))
            scores[~available]=-np.inf
            idx=int(np.argmax(scores))
        available[idx]=False;chosen.append(idx)
        action=Action(pool[idx].copy())
        y,private=world.assay(action)
        stateless.update(phi[idx],y);history_model.update(action,y)
        row={"step":step,"action":action.json(),"y":y}
        if record:row["private"]=private
        history.append(row)
    means,_=stateless.predict(phi[chosen])
    selected=int(np.argmax(means))
    candidate=pool[chosen[selected]].copy()
    predecessor=(np.array([1.,0.,0.,0.]) if selected==0 else pool[chosen[selected-1]].copy())
    return {"world":world,"model":history_model,"candidate":candidate,
            "predecessor":predecessor,"history":history,"selected_step":selected,
            # This is the sole response-oracle information supplied to bounded policies.
            "lipschitz_certificate":float(surface.lipschitz_l1)}


@lru_cache(maxsize=256)
def cached_plan(info):return optimize_plan(info)


def inference(ys,biases,method,model,candidate):
    if method in MODEL_METHODS:
        return {**model.target(candidate),"ci_low":None,"ci_high":None,
                "half_width":None,"mean_bias_bound":None,"n_included":len(ys)}
    start=4 if method in ["tail_repeat4","bounded_tail4"] else 0
    selected=np.asarray(ys[start:],float)
    n=len(selected)
    if n==0:
        return {"mean":None,"probability":.5,"ci_low":None,"ci_high":None,
                "half_width":None,"mean_bias_bound":None,"n_included":0}
    mean=float(np.mean(selected));noise_radius=Z95*SIGMA/math.sqrt(n)
    mean_bias=float(np.mean(biases[start:])) if method in BOUNDED_METHODS else 0.
    width=mean_bias+noise_radius
    return {"mean":mean,"probability":None if method in BOUNDED_METHODS else float(ndtr((mean-THRESHOLD)/(SIGMA/math.sqrt(n)))),
            "ci_low":mean-width,"ci_high":mean+width,"half_width":width,
            "mean_bias_bound":mean_bias,"n_included":n}


def decide(stats,method,n_target):
    if stats["n_included"]<2 or n_target<2:return "unresolved"
    if method in BOUNDED_METHODS:
        if stats["ci_low"]>=THRESHOLD:return "accept"
        if stats["ci_high"]<THRESHOLD:return "reject"
    else:
        if stats["probability"]>=.975:return "accept"
        if stats["probability"]<=.025:return "reject"
    return "unresolved"


def active_actions(candidate,conditioning=True):
    actions=[Action(candidate.copy()),Action(candidate.copy(),1,False,"wash_candidate"),
             Action(candidate.copy(),3,False,"wash_candidate"),Action(candidate.copy(),0,True,"fresh_candidate")]
    if conditioning:actions += [Action(v.copy(),kind="conditioning") for v in VERTICES]
    return actions


def confirm(common,method,seed,case,surface,record=False):
    # Same noise at assay index across methods; no method-dependent seed offset.
    world=World(surface,case,seed,stage=21,noise_mode=case.noise)
    world.h=common["world"].h.copy()
    model=copy.deepcopy(common["model"]) if method in MODEL_METHODS else None
    candidate=common["candidate"]
    info=PlannerInputs(common["lipschitz_certificate"],case.rho_upper,case.eta_upper,
                       case.lambda_lower,SIGMA,case.budget,case.wash_cost,case.fresh_cost)
    plan=cached_plan(info) if method=="bounded_planner" else None
    scheduled=expand_plan(plan) if plan else None
    actions=active_actions(candidate,method!="active_no_conditioning")
    spent=0.;ys=[];biases=[];trace=[];distance=info.distance_initial
    n_assays=0;n_fresh=0;n_washes=0;n_conditioning=0;n_wash1=0;n_wash3=0
    while True:
        if method=="bounded_planner":
            if n_assays==len(scheduled):break
            a=scheduled[n_assays]
            action=Action(candidate.copy(),a["washes"],a["fresh"],a["kind"])
        elif method=="sequence_repeat":
            action=Action(common["predecessor"].copy(),kind="conditioning") if n_assays%2==0 else Action(candidate.copy())
        elif method in ["wash_once","bounded_wash_once"]:
            action=Action(candidate.copy(),1,False,"wash_candidate")
        elif method in ["fresh_only","bounded_fresh"]:
            action=Action(candidate.copy(),0,True,"fresh_candidate")
        elif method in ["active_confirmation","active_no_conditioning"]:
            feasible=[a for a in actions if spent+cost(a,case)<=case.budget+1e-9]
            if not feasible:break
            action=max(feasible,key=lambda a:model.utility(a,candidate,cost(a,case)))
        else:action=Action(candidate.copy())
        price=cost(action,case)
        if spent+price>case.budget+1e-9:break
        bias=None
        if method in BOUNDED_METHODS:
            retained=0. if action.fresh else info.rho_upper*info.eta_upper**action.washes
            bias=info.lipschitz_l1*retained*distance
            if not action.fresh:distance*=1-info.lambda_lower*(1-retained)
        y,private=world.assay(action)
        spent+=price;n_assays+=1
        n_fresh+=int(action.fresh);n_washes+=action.washes
        n_wash1+=int(action.washes==1);n_wash3+=int(action.washes==3)
        n_conditioning+=int(action.kind=="conditioning")
        if model is not None:model.update(action,y)
        is_target=np.allclose(action.nominal,candidate,atol=1e-12,rtol=0)
        if is_target:
            ys.append(y)
            biases.append(bias if bias is not None else 0.)
        if record:
            trace.append({"step":n_assays-1,"action":action.json(),"y":y,"cost":price,
                          "cumulative_cost":spent,"predictable_bias_bound":bias,"private":private})
    stats=inference(ys,biases,method,model,candidate)
    outcome=decide(stats,method,len(ys))
    # Evaluation begins here: latent fresh truth never affects a policy choice.
    truth=float(surface(candidate));good=truth>=THRESHOLD
    covered=(stats["ci_low"]<=truth<=stats["ci_high"]) if method in BOUNDED_METHODS else None
    valid=(case.noise=="gaussian" and case.rho<=case.rho_upper and
           case.eta<=case.eta_upper and case.memory_lambda>=case.lambda_lower)
    result={"seed":seed,"case":case.name,"system":case.system,"scenario":case.scenario,
            "condition":case.condition,"family":case.family,"method":method,
            **{f"candidate_x{i}":float(candidate[i]) for i in range(4)},
            "true_clean_response":truth,"true_degradation":1-truth,"true_good":good,
            "target":THRESHOLD,"decision":outcome,"accepted":outcome=="accept",
            "rejected":outcome=="reject","unresolved":outcome=="unresolved",
            "false_accept":outcome=="accept" and not good,"true_accept":outcome=="accept" and good,
            "false_reject":outcome=="reject" and good,"true_reject":outcome=="reject" and not good,
            "estimate":stats["mean"],"absolute_error":abs(stats["mean"]-truth),
            "probability_good":stats["probability"],"ci_low":stats["ci_low"],"ci_high":stats["ci_high"],
            "ci_halfwidth":stats["half_width"],"interval_covered":covered,
            "mean_bias_bound":stats["mean_bias_bound"],"n_included":stats["n_included"],
            "certificate_assumptions_valid":valid,"lipschitz_certificate":info.lipschitz_l1,
            "rho_upper":info.rho_upper,"eta_upper":info.eta_upper,"lambda_lower":info.lambda_lower,
            "cost":spent,"budget":case.budget,"assays":n_assays,"target_assays":len(ys),
            "fresh_assays":n_fresh,"washes":n_washes,"wash1_assays":n_wash1,
            "wash3_assays":n_wash3,"conditioning_assays":n_conditioning,
            "planned_halfwidth":plan["half_width"] if plan else None}
    return result,trace


def campaign(seed,case,record=False):
    surface=get_surface(case.system,case.family)
    common=discovery(seed,case,surface,record)
    rows=[];traces={}
    for method in METHODS:
        row,trace=confirm(common,method,seed,case,surface,record)
        rows.append(row)
        if record:traces[method]=trace
    example=None
    if record:
        example={"seed":seed,"case":case.json(),"candidate":common["candidate"].tolist(),
                 "selected_discovery_step":common["selected_step"],"discovery":common["history"],
                 "confirmation":traces,"results":rows,"lipschitz_certificate":common["lipschitz_certificate"],
                 "selection":"Development seed100007 fixed before report evaluation; mechanism illustration only."}
    return rows,example
