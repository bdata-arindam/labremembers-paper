"""Render the held-out alternative-emulator predictions saved by validation."""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
frame=pd.read_csv(HERE/'piecewise_affine_heldout_predictions.csv')
info=json.loads((HERE/'piecewise_affine_validation.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(7.5,3.5),sharex=True,sharey=True)
for ax,key,title,color in zip(axes,['pbq_qf','ptb7_th'],['PBQ-QF system','PTB7-Th system'],['#157b75','#557fa3']):
    data=frame[(frame.system==key)&frame.inside_training_hull]
    stats=info['results'][key]['validation']['pooled_covered_metrics']
    ax.plot([-.05,.8],[-.05,.8],color='#a6a6a6',lw=1,ls='--',zorder=1)
    ax.scatter(data.degradation_mean,data.heldout_prediction,s=9,alpha=.42,color=color,edgecolors='none',zorder=2)
    ax.set(xlim=(-.05,.8),ylim=(-.05,.8),xlabel='Measured composition-group mean',title=title)
    ax.text(.04,.95,f"MAE {stats['mae']:.3f}\nRMSE {stats['rmse']:.3f}\n$R^2$ {stats['r_squared']:.3f}",transform=ax.transAxes,va='top',fontsize=9,bbox={'facecolor':'white','edgecolor':'none','alpha':.8})
    ax.grid(alpha=.14)
axes[0].set_ylabel('Held-out interpolation prediction')
fig.suptitle('Alternative OPV emulator: composition-group validation',fontsize=12,y=1.02)
fig.text(.5,-.02,'5 folds · 1008 / 1021 compositions covered per system · 13 outside-hull groups excluded\nMeasured degradation is relative absorbance loss; predictions are interpolation outputs.',ha='center',fontsize=8,color='#555555')
fig.tight_layout()
fig.savefig(HERE/'opv_interpolation_validation.png',dpi=260,bbox_inches='tight')
fig.savefig(HERE/'opv_interpolation_validation.pdf',bbox_inches='tight')
