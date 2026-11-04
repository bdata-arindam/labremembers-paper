"""Post-run descriptive audit of selected emulator predictions; no experiments."""
from pathlib import Path
import hashlib
import json
import pandas as pd

HERE=Path(__file__).resolve().parent
source=HERE/"trial_results.csv"
frame=pd.read_csv(source)
assert (frame.groupby(["case","seed"]).true_degradation.nunique()==1).all()
# The candidate is common to policies; retain one row per case and seed.
selected=frame[frame.method=="bounded_planner"]
records=[]
for (system,condition,scenario),g in selected.groupby(["system","condition","scenario"],sort=True):
    values=g.true_degradation
    records.append({"system":system,"condition":condition,"scenario":scenario,
                    "family":g.family.iloc[0],"unique_seed_count":int(g.seed.nunique()),
                    "selected_nominal_recipe_count":int(len(g[[f"candidate_x{i}" for i in range(4)]].drop_duplicates())),
                    "negative_predicted_loss_count":int((values<0).sum()),
                    "negative_predicted_loss_fraction":float((values<0).mean()),
                    "selected_fitted_loss_min":float(values.min()),
                    "selected_fitted_loss_median":float(values.median()),
                    "selected_fitted_loss_max":float(values.max()),
                    "qualifying_candidate_count":int(g.true_good.sum())})
out={"kind":"Post-run descriptive audit requested after inspection of the frozen v2 results",
     "source":"trial_results.csv","source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
     "selection":"One bounded_planner row per case and seed, after checking that fitted candidate loss is identical across policies.",
     "interpretation":"Negative values are fitted-emulator predictions, not new measured losses. Source negative observations were retained and predictions were not clipped. Frequent optimizer selection of negative fitted losses contributes to easy-case qualifying prevalence and demonstrates emulator dependence; this is not a claim that negative measured changes are physically impossible.",
     "new_campaigns":0,"frozen_outputs_modified":False,"records":records}
(HERE/"candidate_prediction_audit.json").write_text(json.dumps(out,indent=2)+"\n")
print('Saved candidate_prediction_audit.json from frozen rows; no studies rerun.')
