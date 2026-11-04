"""Descriptive, literal reanalysis of measured OPV paired responses."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
protocol=json.loads((ROOT/'reconfirmation_protocol.json').read_text())
source=ROOT/'measured_sda_replicate_pairs.csv'
d=pd.read_csv(source)
t=protocol['threshold']
d['sample1_pass']=d.sample_1<=t
d['sample2_pass']=d.sample_2<=t
d['both_pass']=d.sample1_pass & d.sample2_pass
d['sample1_pass_sample2_fail']=d.sample1_pass & ~d.sample2_pass
d['sample1_fail_sample2_pass']=~d.sample1_pass & d.sample2_pass
d['both_fail']=~d.sample1_pass & ~d.sample2_pass
d['threshold_disagreement']=d.sample1_pass!=d.sample2_pass
fields=['both_pass','sample1_pass_sample2_fail','sample1_fail_sample2_pass','both_fail','threshold_disagreement']
rows=[]
for system in ['pbq_qf','ptb7_th']:
 for campaign in ['all','sda_merit1','sda_merit2']:
  g=d[d.system.eq(system)]
  if campaign!='all': g=g[g.campaign.eq(campaign)]
  x={"system":system,"campaign":campaign,"n_pairs":len(g),
     **{k:int(g[k].sum()) for k in fields},
     'sample1_pass_count':int(g.sample1_pass.sum()),
     'sample2_pass_count':int(g.sample2_pass.sum()),
     'mean_difference_2_minus_1':float((g.sample_2-g.sample_1).mean()),
     'median_absolute_difference':float((g.sample_2-g.sample_1).abs().median()),
     'maximum_absolute_difference':float((g.sample_2-g.sample_1).abs().max())}
  x['disagreement_fraction']=x['threshold_disagreement']/len(g)
  den=x['sample1_pass_count']
  x['sample2_fail_among_sample1_pass']=x['sample1_pass_sample2_fail']/den if den else None
  rows.append(x)
assert len(d)==240 and not d[fields[:4]].sum(axis=1).ne(1).any()
summary={'protocol':protocol,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'total_pairs':len(d),'total_disagreements':int(d.threshold_disagreement.sum()),'rows':rows,
 'interpretation':'Measured threshold disagreement, not causal attribution or ground-truth classification error.'}
(ROOT/'measured_reconfirmation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
pd.DataFrame(rows).to_csv(ROOT/'measured_reconfirmation_counts.csv',index=False)
d.to_csv(ROOT/'measured_reconfirmation_labelled_pairs.csv',index=False)

figdir=ROOT/'figures';figdir.mkdir(exist_ok=True)
navy='#182B3A';teal='#167D8D';orange='#D87838'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,
 'axes.spines.right':False,'text.color':navy,'axes.labelcolor':navy})
fig,axes=plt.subplots(1,2,figsize=(6.6,3.2),sharex=True,sharey=True)
for ax,system,title in zip(axes,['pbq_qf','ptb7_th'],['PBQ-QF system','PTB7-Th system']):
 g=d[d.system.eq(system)]
 ax.plot([0,.75],[0,.75],color='#A0AFB4',lw=.8,zorder=0)
 ax.axvline(t,color=navy,lw=.8,ls='--');ax.axhline(t,color=navy,lw=.8,ls='--')
 for flag,color,label,z in [(False,teal,'Same threshold side',2),(True,orange,'Different threshold side',3)]:
  q=g[g.threshold_disagreement.eq(flag)]
  ax.scatter(q.sample_1,q.sample_2,s=15 if not flag else 26,c=color,alpha=.7,edgecolors='white',linewidths=.2,label=label,zorder=z)
 ax.set_title(title,fontweight='bold')
 ax.set_xlim(-.015,.75);ax.set_ylim(-.015,.75)
 ax.set_xlabel('Sample 1 measured loss')
 ax.text(.03,.94,f'{int(g.threshold_disagreement.sum())}/{len(g)} disagreements',transform=ax.transAxes,va='top',fontsize=8)
axes[0].set_ylabel('Sample 2 measured loss')
handles,labels=axes[1].get_legend_handles_labels()
fig.legend(handles,labels,loc='lower center',ncol=2,frameon=False,bbox_to_anchor=(.55,-.02),fontsize=8)
fig.tight_layout(rect=(0,.06,1,1))
for ext in ['png','svg']:
 fig.savefig(figdir/f'paired_measured_responses.{ext}',dpi=240,bbox_inches='tight')
plt.close(fig)
print(json.dumps({'total_pairs':len(d),'total_disagreements':int(d.threshold_disagreement.sum()),'system_summaries':[r for r in rows if r['campaign']=='all']},indent=2))
