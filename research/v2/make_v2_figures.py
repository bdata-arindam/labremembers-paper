"""Compact6.6-inch publication figures from the completed v2 artifacts."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from confirmation_planner import Z95

HERE=Path(__file__).resolve().parent
OUT=HERE/"figures";OUT.mkdir(exist_ok=True)
NAVY="#182B3A";TEAL="#167D8D";ORANGE="#D87838"
COLORS={"bounded_planner":TEAL,"bounded_tail4":ORANGE,"bounded_fresh":NAVY}
LABELS={"bounded_planner":"Preplanned","bounded_tail4":"Repeat, discard4","bounded_fresh":"Independent fresh"}
SCENARIOS={"no_carryover":"No carryover","trace_carryover":"Trace (0.001)","low_carryover":"Low (0.01)",
           "moderate_carryover":"Moderate (0.10)","high_carryover":"High (0.40)",
           "ineffective_wash":"Ineffective wash","persistent_memory":"Memory λ=0.45",
           "strongly_persistent_stress":"Memory λ=0.05"}
SYSTEMS={"pbq_qf":"PBQ-QF system","ptb7_th":"PTB7-Th system"}
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.titlesize":10,
 "axes.labelsize":9,"xtick.labelsize":8,"ytick.labelsize":8,"legend.fontsize":8,
 "axes.spines.top":False,"axes.spines.right":False,"text.color":NAVY,
 "axes.labelcolor":NAVY,"xtick.color":NAVY,"ytick.color":NAVY,"axes.edgecolor":"#A7B1B8"})


def save(fig,name):
    fig.savefig(OUT/(name+".png"),dpi=260,bbox_inches="tight")
    fig.savefig(OUT/(name+".svg"),bbox_inches="tight")
    plt.close(fig)


def policy_yield(summary):
    cases=[r for r in summary["cases"] if r["case"]["condition"]=="main"]
    fig,axes=plt.subplots(1,2,figsize=(6.6,4.5),sharey=True)
    for ax,system in zip(axes,SYSTEMS):
        rows=[r for r in cases if r["case"]["system"]==system]
        for i,r in enumerate(rows):
            for method,off in zip(COLORS,[-.18,0,.18]):
                p=r["methods"][method]["true_accept"]
                value=100*p["estimate"];lo,hi=np.array(p["ci95"])*100
                ax.errorbar(value,i+off,xerr=[[max(0,value-lo)],[max(0,hi-value)]],fmt="o",color=COLORS[method],markersize=3.5,capsize=2,lw=1)
        ax.set_title(SYSTEMS[system],fontweight="bold")
        ax.set_xlabel("Correct accepts / all campaigns (%)")
        ax.set_xlim(-2,103);ax.set_ylim(7.55,-.55);ax.grid(axis="x",alpha=.18)
    axes[0].set_yticks(range(8),[SCENARIOS[r["case"]["scenario"]] for r in cases if r["case"]["system"]=="pbq_qf"])
    handles=[Line2D([0],[0],marker="o",linestyle="none",color=COLORS[m],label=LABELS[m]) for m in COLORS]
    fig.legend(handles=handles,ncol=3,frameon=False,loc="lower center",bbox_to_anchor=(.58,-.025))
    fig.tight_layout(rect=(0,.035,1,1))
    save(fig,"figure_v2_policy_yield")


def frontier():
    data=pd.read_csv(HERE/"planning_diagnostics.csv")
    fig,axes=plt.subplots(1,2,figsize=(6.6,3.4),sharey=True)
    for ax,condition,title in zip(axes,["main","broad_bounds"],["Declared narrower bounds","Broad apparatus bounds"]):
        rows=data[(data.system=="pbq_qf")&(data.scenario=="high_carryover")&
                  (data.condition==condition)&(data.fresh_cost==4)].sort_values("budget")
        x=rows.budget.to_numpy()
        planner=rows.half_width.to_numpy()
        fresh=Z95*.03/np.sqrt(np.floor(x/4))
        tail=[]
        for _,r in rows.iterrows():
            n=int(r.budget)-4;q=1-r.lambda_lower*(1-r.rho_upper)
            b=r.lipschitz_l1*r.rho_upper*2*q**4*(1-q**n)/(1-q)/n
            tail.append(b+Z95*.03/np.sqrt(n))
        for vals,m in [(planner,"bounded_planner"),(tail,"bounded_tail4"),(fresh,"bounded_fresh")]:
            ax.plot(x,vals,"o-",color=COLORS[m],markersize=4,label=LABELS[m],lw=1.4)
        ax.set_xscale("log",base=2);ax.set_yscale("log")
        ax.set_xticks(x,[str(int(v)) for v in x]);ax.grid(alpha=.18,which="both")
        ax.set_title(title,fontweight="bold");ax.set_xlabel("Assumed budget units")
    axes[0].set_ylabel("Certified fixed-final half-width")
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,ncol=3,frameon=False,loc="lower center",bbox_to_anchor=(.55,-.025))
    fig.tight_layout(rect=(0,.05,1,1));save(fig,"figure_v2_radius_frontier")


def fidelity():
    pred=pd.read_csv(HERE/"emulator_heldout_predictions.csv")
    values=json.loads((HERE/"emulator_validation.json").read_text())
    fig,axes=plt.subplots(1,2,figsize=(6.6,3.25),sharex=True,sharey=True)
    extent=[min(pred.measured_degradation_mean.min(),pred.predicted_degradation.min())-.02,
            max(pred.measured_degradation_mean.max(),pred.predicted_degradation.max())+.02]
    for ax,system in zip(axes,SYSTEMS):
        g=pred[pred.system==system];m=values[system]["held_out"]
        ax.plot(extent,extent,color=NAVY,lw=.8,zorder=0)
        ax.axhline(.1,color=ORANGE,ls="--",lw=.7);ax.axvline(.1,color=ORANGE,ls="--",lw=.7)
        ax.scatter(g.measured_degradation_mean,g.predicted_degradation,s=11,color=TEAL,alpha=.65,edgecolor="none")
        ax.set_title(SYSTEMS[system],fontweight="bold")
        ax.set_xlabel("Held-out measured degradation")
        ax.set_xlim(extent);ax.set_ylim(extent)
        ax.text(.04,.96,f"MAE={m['mae']:.3f}\nR²={m['r2']:.3f}; n={m['n']}",transform=ax.transAxes,va="top",fontsize=8,
                bbox={"facecolor":"white","edgecolor":"none","alpha":.8})
    axes[0].set_ylabel("Cubic-emulator prediction")
    fig.tight_layout();save(fig,"figure_v2_emulator_fidelity")


def robustness(summary):
    conditions=["main","broad_bounds","delaunay_sensitivity","empirical_contrast_noise","equal_fresh_cost"]
    labels={"main":"Narrower bounds","broad_bounds":"Broad bounds","delaunay_sensitivity":"Delaunay emulator",
            "empirical_contrast_noise":"Empirical-noise stress","equal_fresh_cost":"Fresh cost=1"}
    fig,axes=plt.subplots(1,2,figsize=(6.6,4.5),sharey=True)
    cases={r["case"]["name"]:r for r in summary["cases"]}
    ys=[]
    for system in SYSTEMS:
        for condition in conditions:
            ys.append((system,condition))
    for ax,field,title in zip(axes,["interval_coverage","true_accept"],["Interval coverage","Correct-acceptance yield"]):
        for i,(system,condition) in enumerate(ys):
            r=cases[f"{system}__{condition}__high_carryover"]
            if condition=="empirical_contrast_noise":ax.axhspan(i-.43,i+.43,color="#F9EEE6",zorder=-2)
            for method,off in [("bounded_planner",-.12),("bounded_tail4",.12)]:
                p=r["methods"][method][field]
                v=100*p["estimate"];lo,hi=np.array(p["ci95"])*100
                ax.errorbar(v,i+off,xerr=[[max(0,v-lo)],[max(0,hi-v)]],fmt="o",color=COLORS[method],markersize=3.5,capsize=2,lw=1)
        ax.set_xlim(-2,103);ax.set_ylim(len(ys)-.5,-.5);ax.grid(axis="x",alpha=.18)
        ax.set_title(title,fontweight="bold");ax.set_xlabel("% of campaigns; Wilson95% CI")
    axes[0].axvline(95,color=NAVY,lw=.7,ls="--")
    axes[0].set_yticks(range(len(ys)),[("PBQ " if system=="pbq_qf" else "PTB ")+labels[c] for system,c in ys])
    handles=[Line2D([0],[0],marker="o",linestyle="none",color=COLORS[m],label=LABELS[m]) for m in ["bounded_planner","bounded_tail4"]]
    fig.legend(handles=handles,ncol=2,loc="lower center",frameon=False,bbox_to_anchor=(.6,-.02))
    fig.tight_layout(rect=(0,.045,1,1));save(fig,"figure_v2_robustness")


if __name__=="__main__":
    summary=json.loads((HERE/"summary.json").read_text())
    policy_yield(summary);frontier();fidelity();robustness(summary)
    print("Saved4compact6.6-inch publication figures, PNG260dpi andSVG.")
