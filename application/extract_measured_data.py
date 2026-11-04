"""Read the authors' workbook without modification; preserve measured values.

No response clipping, interpolation, or response synthesis occurs here.
Source workbook: Langner et al., DOI 10.1002/adma.201907801.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
RAW=HERE/'quaterny_opvs_experimental_data.xlsx'
EXPECTED_SHA='69ae8917cd63fe9391278df86722c0ebc2921af92dd1b27d9b957cb030a074ad'
assert hashlib.sha256(RAW.read_bytes()).hexdigest()==EXPECTED_SHA
SYSTEMS={'System 01':('pbq_qf','PBQ-QF'),'System 02':('ptb7_th','PTB7-Th')}
rows=[];profiles={};replicates=[]
for sheet,(key,donor) in SYSTEMS.items():
    raw=pd.read_excel(RAW,sheet_name=sheet,header=None)
    assert list(raw.iloc[2,:4])==['P3HT',donor,'PCBM','oIDTBR']
    profile={}
    for protocol,start in [('hte',0),('sda_merit1',6),('sda_merit2',14)]:
        width=5 if protocol=='hte' else 7
        block=raw.iloc[3:,start:start+width].copy()
        block=block.dropna(subset=list(block.columns[:4]))
        x=block.iloc[:,:4].astype(float).to_numpy()
        assert np.isfinite(x).all() and np.all(x>=0)
        assert np.allclose(x.sum(axis=1),1,rtol=0,atol=5e-15)
        responses=block.iloc[:,4:5 if protocol=='hte' else 6].astype(float).to_numpy()
        assert np.isfinite(responses).all()
        cycles=None if protocol=='hte' else pd.to_numeric(block.iloc[:,6]).ffill().astype(int).to_numpy()
        for i,(index,row) in enumerate(block.iterrows()):
            for replicate in range(responses.shape[1]):
                rows.append({'system':key,'second_donor':donor,'protocol':protocol,
                             'source_sheet':sheet,'source_excel_row':int(index)+1,
                             'formulation_id':f'{key}_{protocol}_row{int(index)+1:04d}',
                             'replicate':replicate+1,'cycle':None if cycles is None else int(cycles[i]),
                             'p3ht_fraction':x[i,0],'second_donor_fraction':x[i,1],
                             'pcbm_fraction':x[i,2],'oidtbr_fraction':x[i,3],
                             'degradation':responses[i,replicate]})
            if responses.shape[1]==2:
                replicates.append({'system':key,'protocol':protocol,'source_excel_row':int(index)+1,
                                   'campaign':protocol,'formulation_id':f'{key}_{protocol}_row{int(index)+1:04d}',
                                   'second_donor':donor,'cycle':int(cycles[i]),
                                   'p3ht_fraction':x[i,0],'second_donor_fraction':x[i,1],
                                   'pcbm_fraction':x[i,2],'oidtbr_fraction':x[i,3],
                                   'sample_1':responses[i,0],'sample_2':responses[i,1],
                                   'difference_2_minus_1':responses[i,1]-responses[i,0]})
        profile[protocol]={'formulation_rows':len(x),'response_measurements':responses.size,
                           'unique_exact_compositions':len(np.unique(x,axis=0)),
                           'composition_sum_min':float(x.sum(axis=1).min()),
                           'composition_sum_max':float(x.sum(axis=1).max()),
                           'minimum_measured_degradation':float(responses.min()),
                           'maximum_measured_degradation':float(responses.max()),
                           'negative_measurements':int((responses<0).sum()),
                           'cycles':None if cycles is None else sorted(set(cycles.tolist()))}
    profiles[key]=profile
long=pd.DataFrame(rows)
long['cycle']=long.cycle.astype('Int64')
long.to_csv(HERE/'measured_observations_tidy.csv',index=False,float_format='%.17g')
reps=pd.DataFrame(replicates)
reps.to_csv(HERE/'measured_sda_replicate_pairs.csv',index=False,float_format='%.17g')
feature_cols=['p3ht_fraction','second_donor_fraction','pcbm_fraction','oidtbr_fraction']
for key in SYSTEMS.values():
    key=key[0]
    hte=long[(long.system==key)&(long.protocol=='hte')].copy()
    hte.to_csv(HERE/f'{key}_hte_measured.csv',index=False,float_format='%.17g')
    grouped=hte.groupby(feature_cols,sort=True,dropna=False).agg(
        degradation_mean=('degradation','mean'),replicate_count=('degradation','size'),
        degradation_sd=('degradation','std'),degradation_min=('degradation','min'),
        degradation_max=('degradation','max'),
        source_excel_rows=('source_excel_row',lambda v:';'.join(map(str,v)))).reset_index()
    grouped.to_csv(HERE/f'{key}_hte_composition_means.csv',index=False,float_format='%.17g')
    multi=grouped[grouped.replicate_count>1]
    diff=reps[reps.system==key].difference_2_minus_1.to_numpy()
    profiles[key]['replicate_disagreement']={
        'hte_duplicate_composition_groups':int(len(multi)),
        'hte_extra_measurements':int(len(hte)-len(grouped)),
        'hte_largest_within_composition_range':float((multi.degradation_max-multi.degradation_min).max()),
        'sda_pairs':int(len(diff)),
        'sda_mean_difference_2_minus_1':float(diff.mean()),
        'sda_rms_difference':float(np.sqrt(np.mean(diff**2))),
        'sda_median_absolute_difference':float(np.median(np.abs(diff))),
        'sda_max_absolute_difference':float(np.max(np.abs(diff))),
        'sda_pooled_within_pair_sd':float(np.sqrt(np.mean(diff**2)/2)),
        'noise_note':'Descriptive replicate disagreement; pooled within-pair SD assumes independent equal-variance replicate errors, not verified here.'}
# Numeric audit of Olympus copies, not reliance on their material metadata.
comparisons=[]
for alias in ['photo_pce10','photo_wf3']:
    csv=HERE/f'olympus_{alias}_data.csv'
    if not csv.exists():continue
    arr=pd.read_csv(csv,header=None).to_numpy(float)
    for sheet,(key,donor) in SYSTEMS.items():
        h=long[(long.system==key)&(long.protocol=='hte')]
        a=h[feature_cols+['degradation']].to_numpy(float)
        filtered=a[a[:,-1]>=0]
        comparisons.append({'olympus_alias':alias,'original_sheet':sheet,
                            'original_second_donor':donor,
                            'comparison':'Rows in original order; exclude negative outcome only, no feature permutation.',
                            'rows':len(arr),'shape_matches':arr.shape==filtered.shape,
                            'max_abs_difference':float(np.max(np.abs(arr-filtered))) if arr.shape==filtered.shape else None})
profile={'source_sha256':EXPECTED_SHA,'source_units':'Four component mass fractions in [0,1], sum one. Header wt.-% is interpreted using actual numbers and supporting-information Table S1 weight-fraction definition.',
         'response':'Measured relative spectral absorbance loss after 18 h light treatment; source labels arbitrary units. Lower is more photostable. Negative PCBM observation retained.',
         'systems':profiles,'total_measurements':len(long),'olympus_numeric_audit':comparisons,
         'chronology_note':'Source spreadsheet row order is retained for provenance, not asserted to be experimental order. SDA cycle labels are explicit; blank cycle cells forward-filled within each four-formulation batch. Within-batch execution order and carryover/reset logs are absent.',
         'pooling_note':'Systems share compositions on the zero-second-donor face and some identical measurements. Do not claim the two data tables are fully statistically independent.'}
(HERE/'measured_data_profile.json').write_text(json.dumps(profile,indent=2,allow_nan=False)+'\n')
print(json.dumps(profile,indent=2))
