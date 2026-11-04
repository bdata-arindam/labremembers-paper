"""Reconstruct only already-used report noise; no new trials, seeds or tuning."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import binom

HERE=Path(__file__).resolve().parent
frame=pd.read_csv(HERE/"trial_results.csv")
zcrit=1.959963984540054
records=[];detail=[]
for method,start,stop in [("bounded_repeat",0,32),("bounded_tail4",4,32),("bounded_fresh",0,8)]:
    g=frame[(frame.system=="pbq_qf")&(frame.condition=="main")&
            (frame.scenario=="no_carryover")&(frame.method==method)].sort_values("seed")
    expected=[]
    for seed in g.seed:
        # Independent reconstruction of the explicitly declared seed namespace.
        noise=np.random.default_rng(np.random.SeedSequence([int(seed),21])).normal(0,.03,32)
        expected.append(float(np.mean(noise[start:stop])))
    expected=np.array(expected);observed=(g.estimate-g.true_clean_response).to_numpy(float)
    se=.03/np.sqrt(stop-start)
    standardized=expected/se
    exceed=np.abs(standardized)>zcrit
    covered=(g.ci_low<=g.true_clean_response)&(g.true_clean_response<=g.ci_high)
    misses=int((~covered).sum());n=len(g)
    max_error=float(np.max(abs(observed-expected)))
    assert max_error<2e-14
    # The routine control retains a small declared bias allowance even when the
    # actual scenario has zero carryover. Reconstruct its full recorded interval.
    reconstructed_misses=abs(expected)>g.ci_halfwidth.to_numpy(float)
    assert np.array_equal(~covered.to_numpy(),reconstructed_misses)
    if method in ["bounded_tail4","bounded_fresh"]:
        assert np.array_equal(~covered.to_numpy(),exceed)
    records.append({"method":method,"case":"pbq_qf__main__no_carryover","n_campaigns":n,
                    "noise_indices_zero_based":[start,stop-1],"included_assays":stop-start,
                    "declared_sigma":.03,"standard_error":se,"critical_value":zcrit,
                    "standardized_mean":float(np.mean(standardized)),
                    "standardized_sample_sd":float(np.std(standardized,ddof=1)),
                    "absolute_standardized_exceedances":int(exceed.sum()),"coverage_misses":misses,
                    "interval_bias_allowance":float(g.mean_bias_bound.iloc[0]),
                    "observed_coverage":float(covered.mean()),
                    "maximum_saved_vs_reconstructed_mean_error":max_error,
                    "unadjusted_binomial_upper_tail_at_p05":float(binom.sf(misses-1,n,.05)),
                    "indexing_and_normalization_match":True})
    for seed,z,err,inside in zip(g.seed,standardized,observed-expected,covered):
        detail.append({"method":method,"seed":int(seed),"reconstructed_standardized_noise":float(z),
                       "saved_minus_reconstructed_error":float(err),"interval_covered":bool(inside)})
out={"purpose":"Check a concrete empirical undercoverage finding using the existing report seed block only.",
     "records":records,"new_report_seeds":0,
     "interpretation":"No indexing or normalization defect was found. The empirical coverage shortfall is retained. The same finite noise block is shared across cases and methods, so repeated case counts are not independent calibration replications. Binomial tail probabilities are descriptive, unadjusted checks of this one prespecified block, not a repair of observed coverage or empirical proof of universal calibration.",
     "scope":"The main mathematical statement is conditional coverage under the exact noise/bias assumptions; simulation frequencies on one finite common-random-number block can differ. Real OPV noise is not established as Gaussian with known sigma0.03."}
(HERE/"coverage_noise_audit.json").write_text(json.dumps(out,indent=2)+"\n")
pd.DataFrame(detail).to_csv(HERE/"coverage_noise_reconstruction.csv",index=False)
print(json.dumps(out,indent=2))
