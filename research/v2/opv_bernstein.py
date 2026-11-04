"""Measured-data-informed cubic response emulator, kept private from policies."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
APPLICATION=HERE.parent.parent/"application"
FRACTIONS=["p3ht_fraction","second_donor_fraction","pcbm_fraction","oidtbr_fraction"]
SYSTEMS=["pbq_qf","ptb7_th"]
RIDGES=[1e-6,1e-4,.01,.1,1.,10.]


def multiindices(total,dimension):
    if dimension==1:
        return [(total,)]
    return [(i,)+tail for i in range(total+1)
            for tail in multiindices(total-i,dimension-1)]


@lru_cache(maxsize=16)
def basis_spec(degree,dimension):
    alphas=np.array(multiindices(degree,dimension),int)
    multipliers=np.array([math.factorial(degree)/np.prod([math.factorial(int(k)) for k in a])
                          for a in alphas])
    return alphas,multipliers


def bernstein(x,degree=3):
    x=np.asarray(x,float)
    alphas,multipliers=basis_spec(degree,x.shape[-1])
    return np.prod(x[...,None,:]**alphas,axis=-1)*multipliers


def lipschitz_certificate(coefs,degree=3,dimension=4):
    alphas=multiindices(degree,dimension)
    lookup={a:float(c) for a,c in zip(alphas,coefs)}
    biggest=0.
    for gamma in multiindices(degree-1,dimension):
        neighbors=[]
        for i in range(dimension):
            a=list(gamma);a[i]+=1
            neighbors.append(lookup[tuple(a)])
        biggest=max(biggest,max(neighbors)-min(neighbors))
    raw=degree*.5*biggest
    return float(np.nextafter(raw*(1+1e-12),np.inf)) if raw else 0.


@dataclass
class CubicOPV:
    system: str
    degradation_coefs: np.ndarray
    lipschitz_l1: float
    family: str = "cubic_bernstein"

    def __call__(self,x):
        # Higher is better; negative measured degradation values remain valid.
        return 1.-bernstein(x,3)@self.degradation_coefs

    @classmethod
    def from_saved(cls,system):
        model=json.loads((HERE/"emulator_models.json").read_text())[system]
        return cls(system,np.array(model["degradation_coefs"]),model["lipschitz_l1"])


def ridge_fit(phi,y,ridge):
    center=float(np.mean(y))
    coefs=np.linalg.solve(phi.T@phi+ridge*np.eye(phi.shape[1]),phi.T@(y-center))
    return coefs+center


def metrics(y,pred):
    err=np.asarray(pred)-np.asarray(y)
    return {"n":len(y),"mae":float(np.mean(abs(err))),"rmse":float(np.sqrt(np.mean(err**2))),
            "r2":float(1-np.sum(err**2)/np.sum((y-np.mean(y))**2))}


def fit_primary():
    all_models={}
    validations={}
    predictions=[]
    for system in SYSTEMS:
        source=APPLICATION/(system+"_hte_composition_means.csv")
        frame=pd.read_csv(source).sort_values(FRACTIONS).reset_index(drop=True)
        x=frame[FRACTIONS].to_numpy(float)
        y=frame.degradation_mean.to_numpy(float)
        # Keep full-simplex support in development, group all repeated recipes.
        vertices=np.flatnonzero(np.isclose(x.max(axis=1),1.) & np.isclose((x>1e-12).sum(axis=1),1))
        other=np.setdiff1d(np.arange(len(x)),vertices)
        perm=np.random.default_rng(880001).permutation(other)
        n_train=int(np.floor(.70*len(other)))
        n_val=int(np.floor(.15*len(other)))
        train=np.r_[vertices,perm[:n_train]]
        val=perm[n_train:n_train+n_val]
        test=perm[n_train+n_val:]
        phi=bernstein(x,3)
        choices=[]
        for ridge in RIDGES:
            coefs=ridge_fit(phi[train],y[train],ridge)
            score=metrics(y[val],phi[val]@coefs)
            choices.append({"ridge":ridge,"validation":score})
        selected=min(choices,key=lambda d:(d["validation"]["mae"],-d["ridge"]))
        dev=np.r_[train,val]
        coefs=ridge_fit(phi[dev],y[dev],selected["ridge"])
        L=lipschitz_certificate(coefs)
        # Lock this complete model before revealing any held-out fidelity value.
        model={"system":system,"degree":3,"dimension":4,
               "degradation_coefs":coefs.tolist(),"multiindices":multiindices(3,4),
               "lipschitz_l1":L,"ridge":selected["ridge"],"training_groups":len(train),
               "validation_groups":len(val),"final_development_groups":len(dev),
               "held_out_groups":len(test),"split_seed":880001,
               "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
               "certificate_scope":"Cubic fitted emulator only; no global true-material regularity guarantee."}
        all_models[system]=model
        (HERE/"emulator_models.json").write_text(json.dumps(all_models,indent=2)+"\n")
        pred=phi[test]@coefs
        validations[system]={"selection_grid":choices,"selected_ridge":selected["ridge"],
                             "held_out":metrics(y[test],pred),"lipschitz_l1":L,
                             "split":{"train":len(train),"validation":len(val),"test":len(test),
                                      "forced_training_vertices":len(vertices)},
                             "model_sha256":hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()}
        for i,value in zip(test,pred):
            predictions.append({"system":system,"composition_group":int(i),
                                **dict(zip(FRACTIONS,x[i])),"measured_degradation_mean":float(y[i]),
                                "predicted_degradation":float(value),
                                "replicate_count":int(frame.iloc[i].replicate_count)})
        split=np.full(len(x),"test",object);split[train]="train";split[val]="validation"
        with_split=frame.copy();with_split["split"]=split
        with_split.to_csv(HERE/(system+"_grouped_split.csv"),index=False)
    (HERE/"emulator_validation.json").write_text(json.dumps(validations,indent=2)+"\n")
    pd.DataFrame(predictions).to_csv(HERE/"emulator_heldout_predictions.csv",index=False)
    return validations


if __name__=="__main__":
    print(json.dumps(fit_primary(),indent=2))
