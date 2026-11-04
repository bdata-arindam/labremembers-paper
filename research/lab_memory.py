"""A transparent computational benchmark for confirmation under carryover.

No experimental materials data are used. All quantities are dimensionless.
The policy sees actions and noisy measurements, never World.surface or World.rho.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import copy
import math
import numpy as np
from scipy.special import ndtr, logsumexp

THRESHOLD = 0.85
SIGMA = 0.03
RHO_GRID = np.array([0.0, 0.1, 0.25, 0.4, 0.55, 0.7])
ETA_GRID = np.array([0.05, 0.2, 0.5, 0.8])
GRID = np.array([(r, e) for r in RHO_GRID for e in ETA_GRID])
VERTICES = np.eye(3)
METHODS = ["candidate_repeat", "sequence_repeat", "randomized_predecessor",
           "wash_once", "wash_three", "fresh_only", "history_fixed",
           "active_confirmation", "history_repeat", "active_no_cost"]
HISTORY_METHODS = ["history_fixed", "active_confirmation", "history_repeat",
                   "active_no_cost"]
METHOD_LABELS = {
    "candidate_repeat": "Candidate repetition",
    "sequence_repeat": "Predecessor sequence repetition",
    "randomized_predecessor": "Randomized predecessor",
    "wash_once": "One wash before each assay",
    "wash_three": "Three washes before each assay",
    "fresh_only": "Independent fresh verification",
    "history_fixed": "History model, fixed controls",
    "active_confirmation": "Active confirmation",
    "history_repeat": "History model, candidate repetition",
    "active_no_cost": "Active controls, no cost penalty",
}


def features(x):
    """Six quadratic Bernstein mixture features; shape (...,3)->(...,6)."""
    x = np.asarray(x, dtype=float)
    a, b, c = np.moveaxis(x, -1, 0)
    return np.stack([a*a, b*b, c*c, 2*a*b, 2*a*c, 2*b*c], axis=-1)


def candidate_pool():
    return np.array([[i/10, j/10, (10-i-j)/10]
                     for i in range(11) for j in range(11-i)])


@dataclass
class Action:
    nominal: np.ndarray
    washes: int = 0
    fresh: bool = False
    kind: str = "candidate"

    def json(self):
        return {"nominal": np.asarray(self.nominal).tolist(),
                "washes": self.washes, "fresh": self.fresh, "kind": self.kind}


@dataclass
class Regime:
    name: str
    rho: float
    eta: float
    memory_lambda: float = 1.0
    nonlinear: bool = False
    wash_cost: float = 0.5
    fresh_cost: float = 4.0


REGIMES = [
    Regime("no_carryover", 0.0, 0.2),
    Regime("weak_carryover", 0.1, 0.2),
    Regime("strong_carryover", 0.4, 0.2),
    Regime("ineffective_wash", 0.4, 0.8),
    Regime("long_memory_stress", 0.4, 0.5, memory_lambda=0.45),
    Regime("nonlinear_response_stress", 0.4, 0.2, nonlinear=True),
    Regime("cheap_wash", 0.4, 0.2, wash_cost=0.1),
    Regime("expensive_wash", 0.4, 0.2, wash_cost=2.0),
    Regime("cheap_fresh", 0.4, 0.2, fresh_cost=2.0),
    Regime("expensive_fresh", 0.4, 0.2, fresh_cost=8.0),
    Regime("off_grid_stress", 0.32, 0.35),
    Regime("severe_carryover", 0.7, 0.2),
]


class Surface:
    """Random concave quadratic performance index, optionally misspecified.

    Score is an abstract dimensionless objective, not conductivity or any
    experimentally calibrated property. Concentration mixing alone is physical.
    """
    def __init__(self, seed: int, nonlinear=False):
        rng = np.random.default_rng(seed)
        self.center = rng.dirichlet([1.5, 1.5, 1.5])
        self.peak = float(rng.uniform(0.80, 1.02))
        self.weights = rng.uniform(0.5, 1.1, 3)
        self.nonlinear = nonlinear
        self.phase = rng.uniform(0, 2*np.pi, 2)
        self.bump_center = rng.dirichlet([1.2, 1.2, 1.2])
        # Exact Bernstein coefficients of the matched quadratic family.
        v = self.quadratic(VERTICES)
        self.coefs = np.array([*v,
            2*self.quadratic(np.array([.5,.5,0]))-.5*(v[0]+v[1]),
            2*self.quadratic(np.array([.5,0,.5]))-.5*(v[0]+v[2]),
            2*self.quadratic(np.array([0,.5,.5]))-.5*(v[1]+v[2])])

    def quadratic(self, x):
        x = np.asarray(x)
        return self.peak - .35*np.sum(self.weights*(x-self.center)**2, axis=-1)

    def __call__(self, x):
        x = np.asarray(x)
        y = self.quadratic(x)
        if self.nonlinear:
            y = y + .10*np.sin(8*x[...,0]+self.phase[0])*np.sin(7*x[...,1]+self.phase[1])
            y = y + .12*np.exp(-np.sum((x-self.bump_center)**2, axis=-1)/.025)-.03
        return y

    def json(self):
        return {"center": self.center.tolist(), "peak": self.peak,
                "weights": self.weights.tolist(), "coefs": self.coefs.tolist(),
                "nonlinear": self.nonlinear, "phase": self.phase.tolist(),
                "bump_center": self.bump_center.tolist()}


def action_cost(action, regime):
    return regime.fresh_cost if action.fresh else 1.0 + action.washes*regime.wash_cost


class World:
    """Fixed-final-mass batch mixing: r is retained fraction of final mixture."""
    def __init__(self, surface, regime, seed):
        self.surface = surface
        self.regime = regime
        self.h = np.array([1.,0.,0.])
        self.rng = np.random.default_rng(seed)

    def assay(self, action, noise=None):
        x = np.asarray(action.nominal)
        before = self.h.copy()
        retained = 0.0 if action.fresh else self.regime.rho*self.regime.eta**action.washes
        actual = x.copy() if action.fresh else (1-retained)*x + retained*self.h
        noiseless = float(self.surface(actual))
        eps = float(self.rng.normal(0,SIGMA)) if noise is None else float(noise)
        y = noiseless+eps
        if not action.fresh:
            self.h = ((1-self.regime.memory_lambda)*self.h +
                      self.regime.memory_lambda*actual)
        private = {"actual": actual.tolist(), "residual_before": before.tolist(),
                   "residual_after": self.h.tolist(), "retained_fraction": retained,
                   "noiseless": noiseless, "noise": eps}
        return y, private


class BayesianLinear:
    def __init__(self):
        self.mean = np.full(6, .6)
        self.cov = .25*np.eye(6)

    def predict(self, phi):
        phi = np.asarray(phi)
        return phi@self.mean, np.einsum("...i,ij,...j->...",phi,self.cov,phi)

    def update(self, phi, y):
        v = self.cov@phi
        s = SIGMA**2+phi@v
        self.mean += v*(y-phi@self.mean)/s
        self.cov -= np.outer(v,v)/s
        self.cov = (self.cov+self.cov.T)/2


class HistoryModel:
    """Policy-side latent-grid inference. No reference to the true World."""
    def __init__(self):
        self.rhos = GRID[:,0].copy()
        self.etas = GRID[:,1].copy()
        g = len(GRID)
        self.mean = np.full((g,6), .6)
        self.cov = np.repeat((.25*np.eye(6))[None], g, axis=0)
        self.logw = np.full(g, -np.log(g))
        self.h = np.repeat(np.array([[1.,0.,0.]]), g, axis=0)

    def weights(self):
        return np.exp(self.logw-logsumexp(self.logw))

    def action_features(self, action):
        if action.fresh:
            actual = np.repeat(np.asarray(action.nominal)[None], len(GRID), axis=0)
        else:
            r = self.rhos*self.etas**action.washes
            actual = (1-r[:,None])*np.asarray(action.nominal)+r[:,None]*self.h
        return features(actual), actual

    def update(self, action, y):
        phi, actual = self.action_features(action)
        mu = np.einsum("gi,gi->g", phi,self.mean)
        v = np.einsum("gij,gj->gi",self.cov,phi)
        s = np.maximum(SIGMA**2+np.einsum("gi,gi->g",phi,v),1e-12)
        err = y-mu
        self.logw += -.5*(np.log(2*np.pi*s)+err**2/s)
        self.logw -= logsumexp(self.logw)
        self.mean += v*(err/s)[:,None]
        self.cov -= np.einsum("gi,gj->gij",v,v)/s[:,None,None]
        self.cov = (self.cov+np.swapaxes(self.cov,1,2))/2
        if not action.fresh:
            self.h = actual

    def target(self, candidate):
        phi = features(candidate)
        mus = self.mean@phi
        vs = np.maximum(np.einsum("i,gij,j->g",phi,self.cov,phi),1e-14)
        w = self.weights()
        mu = float(w@mus)
        var = max(float(w@(vs+mus**2)-mu**2),1e-14)
        p = float(w@ndtr((mus-THRESHOLD)/np.sqrt(vs)))
        return {"mean":mu,"variance":var,"probability":p,
                "rho_mean":float(w@self.rhos),"eta_mean":float(w@self.etas)}

    def utility(self, action, candidate, cost):
        phi, _ = self.action_features(action)
        pclean = features(candidate)
        mu_y = np.einsum("gi,gi->g",phi,self.mean)
        vy = SIGMA**2+np.einsum("gi,gij,gj->g",phi,self.cov,phi)
        mu_clean = self.mean@pclean
        cov_within = np.einsum("i,gij,gj->g",pclean,self.cov,phi)
        w = self.weights()
        mean_y = w@mu_y
        mean_clean = w@mu_clean
        cov = w@(cov_within+mu_clean*mu_y)-mean_clean*mean_y
        var_y = max(float(w@(vy+mu_y**2)-mean_y**2),1e-14)
        return float(cov**2/var_y/cost)


def decision(probability, n_target):
    if n_target < 2:
        return "unresolved"
    if probability >= .975:
        return "accept"
    if probability <= .025:
        return "reject"
    return "unresolved"


def naive_target(ys):
    if not ys:
        return {"mean":None,"variance":None,"probability":.5,
                "rho_mean":None,"eta_mean":None}
    mu = float(np.mean(ys))
    var = SIGMA**2/len(ys)
    return {"mean":mu,"variance":var,
            "probability":float(ndtr((mu-THRESHOLD)/math.sqrt(var))),
            "rho_mean":None,"eta_mean":None}


def discovery(seed, regime):
    surface = Surface(seed, nonlinear=regime.nonlinear)
    world = World(surface,regime,seed+111_111)
    infer = BayesianLinear()
    hm = HistoryModel()
    pool = candidate_pool()
    phi = features(pool)
    available = np.ones(len(pool),dtype=bool)
    rng = np.random.default_rng(seed+222_222)
    history = []
    chosen = []
    for t in range(24):
        if t < 8:
            idx = int(rng.choice(np.flatnonzero(available)))
        else:
            mu,v = infer.predict(phi)
            score = mu+1.5*np.sqrt(np.maximum(v,0))
            score[~available] = -np.inf
            idx = int(np.argmax(score))
        available[idx] = False
        chosen.append(idx)
        action = Action(pool[idx].copy())
        y,private = world.assay(action)
        infer.update(phi[idx],y)
        hm.update(action,y)
        history.append({"step":t,"action":action.json(),"y":y,"private":private})
    mus,_ = infer.predict(phi[chosen])
    selected_pos = int(np.argmax(mus))
    candidate = pool[chosen[selected_pos]].copy()
    predecessor = (np.array([1.,0.,0.]) if selected_pos == 0 else
                   np.array(history[selected_pos-1]["action"]["nominal"]))
    return {"surface":surface,"world":world,"model":hm,"candidate":candidate,
            "predecessor":predecessor,"history":history,
            "selected_discovery_step":selected_pos,
            "apparent_response":history[selected_pos]["y"]}


def available_active_actions(candidate):
    return [Action(candidate.copy(),0,False,"candidate"),
            Action(candidate.copy(),1,False,"wash_candidate"),
            Action(candidate.copy(),3,False,"wash_candidate"),
            Action(candidate.copy(),0,True,"fresh_candidate")] + [
            Action(v.copy(),0,False,"conditioning") for v in VERTICES]


def run_confirmation(common, method, seed, regime, budget=16., record=False):
    world = World(common["surface"],regime,seed+333_333+METHODS.index(method)*10_007)
    world.h = common["world"].h.copy()
    model = copy.deepcopy(common["model"])
    candidate = common["candidate"]
    rng = np.random.default_rng(seed+444_444+METHODS.index(method)*10_009)
    spent = 0.
    observations = []
    trace = []
    n_target = 0
    n_fresh = 0
    n_washes = 0
    n_conditioning = 0
    action_number = 0
    first_decision = None
    first_decision_cost = None
    first_decision_correct = None
    active = available_active_actions(candidate)
    last_stats = model.target(candidate) if method in HISTORY_METHODS else naive_target([])
    while True:
        if method in ["candidate_repeat", "history_repeat"]:
            action = Action(candidate.copy())
        elif method == "sequence_repeat":
            action = (Action(common["predecessor"].copy(),kind="conditioning")
                      if action_number%2==0 else Action(candidate.copy()))
        elif method == "randomized_predecessor":
            action = (Action(VERTICES[int(rng.integers(3))].copy(),kind="conditioning")
                      if action_number%2==0 else Action(candidate.copy()))
        elif method == "wash_once":
            action = Action(candidate.copy(),washes=1,kind="wash_candidate")
        elif method == "wash_three":
            action = Action(candidate.copy(),washes=3,kind="wash_candidate")
        elif method == "fresh_only":
            action = Action(candidate.copy(),fresh=True,kind="fresh_candidate")
        elif method == "history_fixed":
            k = action_number%3
            action = (Action(candidate.copy()) if k==0 else
                      Action(candidate.copy(),washes=1,kind="wash_candidate") if k==1 else
                      Action(candidate.copy(),fresh=True,kind="fresh_candidate"))
            if spent+action_cost(action,regime)>budget+1e-9:
                action = Action(candidate.copy())
        elif method in ["active_confirmation", "active_no_cost"]:
            feasible = [a for a in active if spent+action_cost(a,regime)<=budget+1e-9]
            if not feasible:
                break
            action = max(feasible,key=lambda a:model.utility(
                a,candidate,action_cost(a,regime) if method=="active_confirmation" else 1.0))
        else:
            raise ValueError(method)
        cost = action_cost(action,regime)
        if spent+cost>budget+1e-9:
            break
        y, private = world.assay(action)
        spent += cost
        n_fresh += int(action.fresh)
        n_washes += action.washes
        n_conditioning += int(action.kind == "conditioning")
        model.update(action,y)
        # A conditioning vertex can itself equal a vertex-valued candidate.
        is_target = np.allclose(action.nominal,candidate,atol=1e-12,rtol=0)
        if is_target:
            observations.append(y)
            n_target += 1
        last_stats = (model.target(candidate) if method in HISTORY_METHODS
                      else naive_target(observations))
        state = decision(last_stats["probability"],n_target)
        if state != "unresolved" and first_decision is None:
            first_decision = state
            first_decision_cost = spent
            # Truth remains local to evaluation; it never affects an action.
            good = bool(common["surface"](candidate)>=THRESHOLD)
            first_decision_correct = (state=="accept") == good
        if record:
            trace.append({"step":action_number,"action":action.json(),"cost":cost,
                          "cumulative_cost":spent,"y":y,"stats":last_stats,
                          "decision":state,"n_target":n_target,"private":private})
        action_number += 1
    final = decision(last_stats["probability"],n_target)
    truth = float(common["surface"](candidate))
    good = truth>=THRESHOLD
    result = {"seed":seed,"regime":regime.name,"method":method,"budget":budget,
              "candidate_x0":candidate[0],"candidate_x1":candidate[1],"candidate_x2":candidate[2],
              "true_clean_response":truth,"target":THRESHOLD,"true_good":good,
              "decision":final,"accepted":final=="accept","rejected":final=="reject",
              "unresolved":final=="unresolved","false_accept":final=="accept" and not good,
              "true_accept":final=="accept" and good,"false_reject":final=="reject" and good,
              "true_reject":final=="reject" and not good,
              "posterior_or_naive_mean":last_stats["mean"],
              "probability_good":last_stats["probability"],
              "absolute_error":abs(last_stats["mean"]-truth) if last_stats["mean"] is not None else None,
              "cost":spent,"assays":action_number,"target_assays":n_target,
              "fresh_assays":n_fresh,"washes":n_washes,"conditioning_assays":n_conditioning,
              "estimated_rho":last_stats["rho_mean"],
              "first_decision":first_decision,"first_decision_cost":first_decision_cost,
              "first_decision_correct":first_decision_correct}
    return result, trace


def campaign(seed, regime, budget=16., record=False):
    common = discovery(seed,regime)
    rows = []
    traces = {}
    for method in METHODS:
        row, trace = run_confirmation(common,method,seed,regime,budget,record)
        rows.append(row)
        if record:
            traces[method] = trace
    if record:
        example = {"seed":seed,"regime":asdict(regime),"surface":common["surface"].json(),
                   "threshold":THRESHOLD,"sigma":SIGMA,"budget":budget,
                   "candidate":common["candidate"].tolist(),
                   "predecessor":common["predecessor"].tolist(),
                   "selected_discovery_step":common["selected_discovery_step"],
                   "apparent_response":common["apparent_response"],
                   "true_clean_response":float(common["surface"](common["candidate"])),
                   "discovery":common["history"],"confirmation":traces,"results":rows,
                   "model":{"rho_grid":RHO_GRID.tolist(),"eta_grid":ETA_GRID.tolist(),
                            "prior_mean":[.6]*6,"prior_cov_diagonal":[.25]*6}}
        return rows,example
    return rows,None


def parity_fixture():
    model = HistoryModel()
    surf = Surface(7)
    regime = Regime("parity",.4,.2)
    world = World(surf,regime,1)
    candidate = np.array([.3,.5,.2])
    actions = [Action(np.array([.2,.3,.5])),
               Action(np.array([.5,.4,.1]),washes=1),
               Action(candidate.copy(),fresh=True,kind="fresh_candidate"),
               Action(np.array([0.,1.,0.]),kind="conditioning"),
               Action(candidate.copy(),washes=3)]
    rows=[]
    for a,eps in zip(actions,[.01,-.02,.015,0.,-.005]):
        y,private=world.assay(a,noise=eps)
        model.update(a,y)
        utilities=[model.utility(b,candidate,action_cost(b,regime))
                   for b in available_active_actions(candidate)]
        rows.append({"action":a.json(),"noise":eps,"y":y,"private":private,
                     "target":model.target(candidate),"utilities":utilities,
                     "particle_weights":model.weights().tolist()})
    return {"surface":surf.json(),"regime":asdict(regime),"candidate":candidate.tolist(),
            "sigma":SIGMA,"rows":rows}
