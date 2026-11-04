"""Execute the declared alternative-emulator validation without response tuning."""
from pathlib import Path
import json,hashlib,platform
import numpy as np
import pandas as pd
import scipy
from opv_piecewise_affine import PiecewiseAffineOPV,FEATURES,BASIS

HERE=Path(__file__).resolve().parent
protocol=json.loads((HERE/'piecewise_affine_protocol.json').read_text())
seed=protocol['holdout']['seed'];n_folds=protocol['holdout']['kind']
results={};all_predictions=[]
def metrics(y,p):
    residual=p-y
    return {'n':len(y),'mae':float(np.mean(np.abs(residual))),'rmse':float(np.sqrt(np.mean(residual**2))),
            'r_squared':float(1-np.sum(residual**2)/np.sum((y-y.mean())**2))}
for system in protocol['systems']:
    frame=pd.read_csv(HERE/f'{system}_hte_composition_means.csv',float_precision='round_trip')
    x=frame[FEATURES].to_numpy();y=frame.degradation_mean.to_numpy()
    permutation=np.random.default_rng(seed).permutation(len(x))
    folds=np.array_split(permutation,5);prediction=np.full(len(y),np.nan);assigned=np.zeros(len(y),int)
    fold_reports=[]
    for fold,test in enumerate(folds,1):
        train=np.setdiff1d(np.arange(len(x)),test)
        model=PiecewiseAffineOPV(x[train],y[train],system,compute_exact_bounds=False)
        p=model.predict(x[test],strict=False);prediction[test]=p;assigned[test]=fold
        mask=np.isfinite(p)
        fold_reports.append({'fold':fold,'training_groups':len(train),'heldout_groups':len(test),'covered_groups':int(mask.sum()),
                             'excluded_outside_training_hull':int((~mask).sum()),'coverage':float(mask.mean()),
                             **metrics(y[test][mask],p[mask]),'training_hull_volume':model.hull_volume,
                             'numerical_zero_volume_cells':model.zero_volume_count})
    mask=np.isfinite(prediction)
    full=PiecewiseAffineOPV(x,y,system)
    # Only validation/model checks, unrelated to downstream policy outcomes.
    observed_error=float(np.max(np.abs(full(x)-y)))
    rng=np.random.default_rng(seed+100)
    a=rng.dirichlet(np.ones(4),size=20000);b=rng.dirichlet(np.ones(4),size=20000)
    ya=full(a);yb=full(b)
    l1quot=np.abs(ya-yb)/np.linalg.norm(a-b,ord=1,axis=1)
    l2quot=np.abs(ya-yb)/np.linalg.norm(a-b,ord=2,axis=1)
    assert np.all(l1quot<=full.lipschitz_l1*(1+1e-12))
    assert np.all(l2quot<=full.lipschitz_l2*(1+1e-12))
    assert observed_error<1e-10
    results[system]={'validation':{'method':'5-fold shuffled composition-group cross-validation; NumPy default_rng permutation split into five folds',
                                    'seed':seed,'total_composition_groups':len(y),'covered_groups':int(mask.sum()),
                                    'excluded_outside_training_hull':int((~mask).sum()),'coverage':float(mask.mean()),
                                    'pooled_covered_metrics':metrics(y[mask],prediction[mask]),'folds':fold_reports},
                      'full_data_emulator':full.report,
                      'verification':{'maximum_error_at_group_means':observed_error,'random_pair_count':len(a),
                                      'maximum_sampled_L1_quotient':float(l1quot.max()),'maximum_sampled_L2_quotient':float(l2quot.max()),
                                      'random_pair_note':'Diagnostic only; rigorous emulator bound comes from every-cell exact rational gradient calculation, not sampled pairs.'},
                      'material_claim_limit':'The bound certifies the constructed interpolant only. It does not bound an unknown physical response or empirically establish carryover.'}
    frame['fold']=assigned;frame['heldout_prediction']=prediction;frame['inside_training_hull']=mask
    frame['system']=system;all_predictions.append(frame)
    np.savez_compressed(HERE/f'{system}_piecewise_affine_arrays.npz',composition=full.x,measured_group_mean=full.y,
                        orthonormal_basis=BASIS,simplices=full.simplices,valid_cell=full.valid,
                        affine_gradient4=full.gradient4,affine_intercept=full.intercept)
    print(system,results[system]['validation']['pooled_covered_metrics'],'coverage',mask.mean(),'L1',full.lipschitz_l1,flush=True)
pd.concat(all_predictions,ignore_index=True).to_csv(HERE/'piecewise_affine_heldout_predictions.csv',index=False,float_format='%.17g')
output={'role':protocol['role'],'protocol':protocol,'results':results,
        'source_sha256':protocol['source_sha256'],
        'software':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pandas':pd.__version__},
        'source_hashes':{p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ['piecewise_affine_protocol.json','opv_piecewise_affine.py','validate_piecewise_affine.py']},
        'interpretation':'Interpolation predictions are model outputs, not measured outcomes. Large global bounds are reported without tuning the response or geometry to improve policy performance.'}
(HERE/'piecewise_affine_validation.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
