"""Publication-style figures from the executed study; no hard-coded outcomes."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from lab_memory import METHOD_LABELS, Surface

HERE=Path(__file__).resolve().parent
OUT=HERE/"figures"
OUT.mkdir(exist_ok=True)
NAVY="#182B3A"
TEAL="#167D8D"
ORANGE="#D87838"
PURPLE="#765B8A"
GRAY="#A6AFB3"
COLORS={"active_confirmation":TEAL,"history_repeat":ORANGE,
        "candidate_repeat":NAVY,"fresh_only":PURPLE}
RATE_COLORS={**COLORS,"sequence_repeat":"#A33D35"}
SHORT={"active_confirmation":"Active controls",
       "history_repeat":"History model + repeats",
       "candidate_repeat":"Naive repeats",
       "fresh_only":"Fresh verification","sequence_repeat":"Sequence replay"}
REGIME_LABELS={"no_carryover":"No carryover","weak_carryover":"Weak carryover",
 "strong_carryover":"Strong carryover","ineffective_wash":"Ineffective washing",
 "long_memory_stress":"Long-memory stress","nonlinear_response_stress":"Nonlinear-response stress",
 "cheap_wash":"Cheap wash","expensive_wash":"Costly wash","cheap_fresh":"Cheap fresh prep",
 "expensive_fresh":"Costly fresh prep","off_grid_stress":"Off-grid parameters",
 "severe_carryover":"Severe carryover"}
MAIN=["no_carryover","weak_carryover","strong_carryover","ineffective_wash",
      "off_grid_stress","severe_carryover","long_memory_stress","nonlinear_response_stress"]
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":11,"axes.labelcolor":NAVY,
 "text.color":NAVY,"axes.edgecolor":"#B9C1C6","xtick.color":NAVY,"ytick.color":NAVY,
 "axes.titleweight":"bold","axes.spines.top":False,"axes.spines.right":False,
 "figure.facecolor":"white","axes.facecolor":"white","savefig.facecolor":"white"})


def save(fig,name):
    fig.savefig(OUT/(name+".png"),dpi=220,bbox_inches="tight")
    fig.savefig(OUT/(name+".svg"),bbox_inches="tight")
    plt.close(fig)


def point(ax,x,y,ci,color,marker="o",size=5):
    lo,hi=ci
    ax.errorbar(x,y,xerr=[[max(0,x-lo)],[max(0,hi-x)]],fmt=marker,
                color=color,markersize=size,capsize=2,linewidth=1.15)


def rates(summary):
    data={r["name"]:r for r in summary["regimes"]}
    fig,axes=plt.subplots(1,3,figsize=(14.6,7.6),sharey=True)
    fields=[("false_accept","False confirmations"),("true_accept","Correct-acceptance yield"),
            ("unresolved","Unresolved")]
    methods=list(RATE_COLORS)
    offsets=np.linspace(-.25,.25,len(methods))
    for ax,(field,title) in zip(axes,fields):
        for i,name in enumerate(MAIN):
            if "stress" in name:
                ax.axhspan(i-.43,i+.43,color="#F4F1EC",zorder=-2)
            for method,off in zip(methods,offsets):
                rec=data[name]["methods"][method][field]
                point(ax,100*rec["estimate"],i+off,np.array(rec["ci95"])*100,RATE_COLORS[method])
        ax.set_title(title,pad=14)
        ax.set_xlabel("% of all campaigns (Wilson 95% CI)")
        ax.grid(axis="x",alpha=.2)
        ax.set_ylim(len(MAIN)-.55,-.55)
        if field=="false_accept":
            maxhi=max(data[name]["methods"][m][field]["ci95"][1] for name in MAIN for m in methods)
            ax.set_xlim(-.4,max(5,100*maxhi+1))
        else:
            maxhi=max(data[name]["methods"][m][field]["ci95"][1] for name in MAIN for m in methods)
            ax.set_xlim(-1,101 if field=="true_accept" else min(101,max(30,100*maxhi+3)))
    axes[0].set_yticks(range(len(MAIN)),[REGIME_LABELS[n] for n in MAIN])
    handles=[Line2D([0],[0],marker="o",color=RATE_COLORS[m],label=SHORT[m],linestyle="none") for m in methods]
    fig.legend(handles=handles,loc="lower center",ncol=5,frameon=False,bbox_to_anchor=(.54,-.025),fontsize=10)
    fig.suptitle(f"Confirmation after a 16-unit budget cap · {summary['campaigns_per_regime']} campaigns per regime",fontsize=16,y=1.01)
    fig.text(.01,-.06,"Synthetic dimensionless responses. Shading marks structural/parameter stress tests. Yield uses all campaigns, including truly invalid candidates.",fontsize=9)
    fig.tight_layout()
    save(fig,"figure_primary_rates")


def paired(summary):
    data={r["name"]:r for r in summary["regimes"]}
    names=[r["name"] for r in summary["regimes"]]
    fig,axes=plt.subplots(1,2,figsize=(12,8.6),sharey=True)
    for ax,field,title in zip(axes,["false_accept","true_accept"],
                             ["False-confirmation rates","Change in correct-acceptance yield"]):
        for i,name in enumerate(names):
            if field=="false_accept":
                for method,off in [("active_confirmation",-.12),("history_repeat",.12)]:
                    rec=data[name]["methods"][method][field]
                    point(ax,100*rec["estimate"],i+off,np.array(rec["ci95"])*100,COLORS[method],size=5)
            else:
                rec=data[name]["paired_comparisons"]["history_repeat"]["metrics"][field]
                point(ax,100*rec["estimate"],i,np.array(rec["ci95"])*100,TEAL,size=6)
                ax.axvline(0,color=NAVY,linewidth=1,linestyle="--",zorder=-2)
        ax.set_title(title,pad=14)
        if field=="false_accept":
            ax.set_xlabel("% of campaigns (individual Wilson 95% CI)")
            ax.set_xlim(-.04,1.05)
            handles=[Line2D([0],[0],marker="o",color=COLORS[m],label=SHORT[m],linestyle="none")
                     for m in ["active_confirmation","history_repeat"]]
            ax.legend(handles=handles,loc="lower right",frameon=False,fontsize=9)
        else:
            ax.set_xlabel("Active minus history-model repeats\n(percentage points; paired bootstrap 95% CI)")
        ax.grid(axis="x",alpha=.2)
        ax.set_ylim(len(names)-.6,-.6)
    axes[0].set_yticks(range(len(names)),[REGIME_LABELS[n] for n in names])
    fig.suptitle("Primary action-selection comparison",fontsize=16,y=1.01)
    fig.text(.01,-.04,"Same frozen candidate and inference model. Zero false accepts in 400 cases gives a 0.95% Wilson upper bound; it does not establish zero risk.",fontsize=9)
    fig.tight_layout()
    save(fig,"figure_paired_effects")


def accuracy(summary):
    names=[r["name"] for r in summary["regimes"]]
    data={r["name"]:r for r in summary["regimes"]}
    fig,ax=plt.subplots(figsize=(9.5,8.5))
    for i,name in enumerate(names):
        if "stress" in name: ax.axhspan(i-.43,i+.43,color="#F4F1EC",zorder=-2)
        for method,off in zip(COLORS,np.linspace(-.25,.25,len(COLORS))):
            rec=data[name]["methods"][method]["absolute_error"]
            point(ax,rec["estimate"],i+off,rec["ci95"],COLORS[method])
    ax.set_yticks(range(len(names)),[REGIME_LABELS[n] for n in names])
    ax.set_ylim(len(names)-.6,-.6)
    ax.set_xlim(left=0)
    ax.set_xlabel("Mean absolute error in fresh nominal response (bootstrap 95% CI)")
    ax.set_title("How accurately is the nominal candidate estimated?",pad=16)
    ax.grid(axis="x",alpha=.2)
    handles=[Line2D([0],[0],marker="o",color=COLORS[m],label=SHORT[m],linestyle="none") for m in COLORS]
    fig.legend(handles=handles,loc="lower center",ncol=2,frameon=False,bbox_to_anchor=(.6,-.015))
    fig.tight_layout()
    save(fig,"figure_estimation_error")


def resource_mix(summary):
    regime=next(r for r in summary["regimes"] if r["name"]=="strong_carryover")
    methods=list(regime["methods"])
    fig,ax=plt.subplots(figsize=(11.5,6.6))
    left=np.zeros(len(methods))
    p=regime["parameters"]
    arrays=[[],[],[],[]]
    for m in methods:
        d=regime["methods"][m]
        v=lambda k:d[k]["estimate"]
        arrays[0].append(v("assays")-v("fresh_assays")-v("conditioning_assays"))
        arrays[1].append(v("conditioning_assays"))
        arrays[2].append(v("washes")*p["wash_cost"])
        arrays[3].append(v("fresh_assays")*p["fresh_cost"])
    for vals,label,color in zip(arrays,["Routine candidate assays","Conditioning assays","Wash operations","Fresh preparations"],
                                [NAVY,GRAY,TEAL,ORANGE]):
        ax.barh(range(len(methods)),vals,left=left,height=.66,label=label,color=color)
        left+=np.asarray(vals)
    ax.axvline(16,color=NAVY,linestyle="--",linewidth=1)
    ax.set_yticks(range(len(methods)),[METHOD_LABELS[m] for m in methods])
    ax.invert_yaxis()
    ax.set_xlim(0,16.6)
    ax.set_xlabel("Mean assumed cost units spent (budget cap = 16)")
    ax.set_title("What each policy spends · strong carryover",pad=16)
    ax.legend(loc="lower center",bbox_to_anchor=(.52,-.24),ncol=2,frameon=False)
    ax.grid(axis="x",alpha=.15)
    fig.tight_layout()
    save(fig,"figure_resource_mix")


def cost_sensitivity(summary):
    data={r["name"]:r for r in summary["regimes"]}
    fig,axes=plt.subplots(2,2,figsize=(12,8.2))
    sweeps=[(["cheap_fresh","strong_carryover","expensive_fresh"],[2,4,8],"Independent fresh assay cost"),
            (["cheap_wash","strong_carryover","expensive_wash"],[.1,.5,2],"Cost per wash")]
    for column,(names,x,label) in enumerate(sweeps):
        for row,(field,ylabel,mul) in enumerate([("true_accept","Correct-acceptance yield (% of all campaigns)",100),
                                              ("absolute_error","Mean absolute fresh-response error",1)]):
            ax=axes[row,column]
            for m in COLORS:
                rs=[data[n]["methods"][m][field] for n in names]
                ys=np.array([r["estimate"] for r in rs])*mul
                ci=np.array([r["ci95"] for r in rs])*mul
                ax.errorbar(x,ys,yerr=np.array([ys-ci[:,0],ci[:,1]-ys]),
                            marker="o",color=COLORS[m],label=SHORT[m],capsize=3,linewidth=1.5)
            ax.set_xticks(x)
            ax.set_xlabel(label+" (assumed units)")
            ax.set_ylabel(ylabel)
            ax.grid(alpha=.15)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="lower center",ncol=4,frameon=False,bbox_to_anchor=(.54,-.035))
    fig.suptitle("Cost sensitivity with the same 16-unit cap and strong carryover",fontsize=16,y=1.01)
    fig.tight_layout()
    save(fig,"figure_cost_sensitivity")


def mechanism(examples):
    example=examples["examples"][0]
    idx=example["mechanism_illustration_step"]
    record=example["discovery"][idx]
    nominal=np.array(record["action"]["nominal"])
    actual=np.array(record["private"]["actual"])
    residual=np.array(record["private"]["residual_before"])
    surf=Surface(example["seed"])
    grid=np.array([[i/60,j/60,(60-i-j)/60] for i in range(61) for j in range(61-i)])
    xy=lambda a:np.array([a[...,1]+.5*a[...,2],np.sqrt(3)/2*a[...,2]])
    gx,gy=xy(grid)
    fig,axes=plt.subplots(1,2,figsize=(12,5.4),gridspec_kw={"width_ratios":[1.15,1]})
    ax=axes[0]
    cs=ax.tricontourf(gx,gy,surf(grid),levels=14,cmap="YlGnBu")
    ax.plot([0,1,.5,0],[0,0,np.sqrt(3)/2,0],color=NAVY,linewidth=1.3)
    nx,ny=xy(nominal); ax.plot(nx,ny,"o",color=ORANGE,markersize=10,label="Commanded recipe")
    rx,ry=xy(residual); ax.plot(rx,ry,"s",color="white",markeredgecolor=NAVY,markersize=8,label="Previous residual")
    ax.plot([nx,rx],[ny,ry],color="white",linewidth=2,linestyle="--")
    axx,axy=xy(actual); ax.plot(axx,axy,"D",color=TEAL,markeredgecolor="white",markersize=10,label="Actual mixture")
    ax.text(-.03,-.03,"A",ha="center",va="top",fontweight="bold")
    ax.text(1.03,-.03,"B",ha="center",va="top",fontweight="bold")
    ax.text(.5,np.sqrt(3)/2+.03,"C",ha="center",fontweight="bold")
    ax.set_xlim(-.06,1.06); ax.set_ylim(-.05,np.sqrt(3)/2+.08)
    ax.set_aspect("equal"); ax.axis("off")
    fig.colorbar(cs,ax=ax,fraction=.04,pad=.04,label="Abstract response index")
    ax.set_title("How line history changes the mixture",pad=20)
    ax.legend(loc="lower center",bbox_to_anchor=(.55,-.2),frameon=False,ncol=1,fontsize=10)
    ax=axes[1]
    x=np.arange(3)
    ax.bar(x-.17,nominal,width=.32,color=ORANGE,label="Commanded")
    ax.bar(x+.17,actual,width=.32,color=TEAL,label="Actual")
    ax.set_xticks(x,["A","B","C"])
    ax.set_ylim(0,1.1)
    ax.set_yticks(np.linspace(0,1,6))
    ax.set_ylabel("Mass fraction in fixed final batch")
    ax.set_title(f"Logged discovery assay {idx+1} (development seed 7)",pad=16)
    ax.legend(frameon=False)
    ax.grid(axis="y",alpha=.15)
    for j,(n,a) in enumerate(zip(nominal,actual)):
        ax.text(j-.17,n+.025,f"{n:.2f}",ha="center",fontsize=10)
        ax.text(j+.17,a+.025,f"{a:.2f}",ha="center",fontsize=10)
    fig.suptitle("Carryover changes the composition behind the reported recipe",fontsize=16,y=1.04)
    fig.text(.01,-.09,"Illustrative fixed development case; largest logged composition discrepancy shown. The policy cannot see the simulator's true surface or actual mixture.",fontsize=9)
    fig.tight_layout()
    save(fig,"figure_mechanism")


def trajectory(examples):
    example=examples["examples"][0]
    fig,axes=plt.subplots(2,1,figsize=(10,7.6),sharex=True)
    for m in COLORS:
        trace=example["confirmation"][m]
        x=[t["cumulative_cost"] for t in trace]
        means=[t["stats"]["mean"] for t in trace]
        axes[0].plot(x,means,"o-",color=COLORS[m],label=SHORT[m],markersize=4)
        deviation=[np.linalg.norm(np.array(t["private"]["actual"])-example["candidate"],ord=1)
                   for t in trace]
        axes[1].plot(x,deviation,"o-",color=COLORS[m],label=SHORT[m],markersize=4)
    axes[0].axhline(example["threshold"],color=ORANGE,linestyle="--",label="Acceptance threshold")
    axes[0].axhline(example["true_clean_response"],color=NAVY,linestyle=":",label="Scoring-only true fresh response")
    axes[0].set_ylabel("Estimated fresh response")
    axes[0].legend(loc="best",frameon=False,ncol=2,fontsize=9)
    axes[0].set_title("Fixed development seed 7 · strong carryover",pad=15)
    axes[1].set_ylabel("Actual-mixture L1 distance\nfrom frozen candidate")
    axes[1].set_xlabel("Cumulative assumed cost units")
    axes[1].set_xlim(0,16.3)
    axes[1].set_ylim(bottom=-.02)
    for ax in axes: ax.grid(alpha=.15)
    fig.text(.01,-.025,"Fixed development illustration. Peaks may be intentional conditioning assays. Actual mixture and true fresh response are scoring-only quantities.",fontsize=9)
    fig.tight_layout()
    save(fig,"figure_development_trajectory")


if __name__=="__main__":
    summary=json.loads((HERE/"summary.json").read_text())
    examples=json.loads((HERE/"examples.json").read_text())
    rates(summary); paired(summary); accuracy(summary); resource_mix(summary)
    cost_sensitivity(summary); mechanism(examples); trajectory(examples)
    print("Saved 7 scientific figures in PNG and SVG.")
