"""Build the reproducible notebook; execution is performed by execute_notebook.py."""
from pathlib import Path
import importlib.metadata
import nbformat as nbf

HERE=Path(__file__).resolve().parent
nb=nbf.v4.new_notebook()
nb.metadata.kernelspec={"name":"lab-remembers-repro","display_name":"Lab Remembers Reproduction","language":"python"}
cells=[]
md=lambda s:cells.append(nbf.v4.new_markdown_cell(s.strip()))
code=lambda s:cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# When the Lab Remembers — complete executed research notebook

This notebook actually reruns **every v1 experiment, every v2 main experiment and every predeclared v2 sensitivity**. It also regenerates the measured OPV data analysis, repeats the locked emulator fitting and held-out evaluation, runs the scientific checks, recreates figures and compares the fresh results with the frozen study files. It does not substitute cached CSVs for execution.

The evidence has three distinct levels: measured OPV replicate responses; mathematical emulators informed by measured formulation data; and synthetic carryover experiments. A confidence guarantee for an emulator under declared apparatus/noise bounds does not certify a real material or establish that carryover caused a measured replicate disagreement.

## Run this notebook yourself

Keep the complete project folder structure. Install the versions in `requirements_notebook.txt`, select that Python environment, and **Run All**. The first cell finds the project root automatically; set the `LAB_REMEMBERS_ROOT` environment variable or edit `PROJECT_ROOT` if necessary. The full execution takes several minutes and writes a new isolated rerun directory. Frozen original study files are never overwritten.

The executable source is bundled at [v1 simulator](../lab_memory.py), [v1 runner](../run_study.py), [v2 policies](../v2/opv_confirmation.py), [v2 planner](../v2/confirmation_planner.py), [cubic emulator](../v2/opv_bernstein.py), and [v2 runner](../v2/run_v2.py). Configuration and assumptions are in [v1 protocol](../protocol.json), [v2 protocol](../v2/protocol.json), and [theory note](../theory_note.md).
""")
code(r"""
from pathlib import Path
from datetime import datetime, timezone
import os, sys, json, hashlib, shutil, subprocess, time, platform, importlib.metadata
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from IPython.display import display, Markdown, Image, Code

def find_project_root():
    if os.environ.get('LAB_REMEMBERS_ROOT'):
        return Path(os.environ['LAB_REMEMBERS_ROOT']).expanduser().resolve()
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if (candidate/'research/lab_memory.py').exists() and (candidate/'application').exists():
            return candidate.resolve()
    raise FileNotFoundError('Set LAB_REMEMBERS_ROOT to the unzipped lab_remembers project.')

PROJECT_ROOT = find_project_root()
RUN_TAG = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
RUN_ROOT = PROJECT_ROOT/'research'/'notebook'/'runs'/RUN_TAG/'rerun_project'
RUN_ROOT.mkdir(parents=True, exist_ok=False)
LOG_ROOT = RUN_ROOT.parent/'logs'
LOG_ROOT.mkdir()
pd.set_option('display.max_columns', 30)
pd.set_option('display.max_rows', 5000)
notebook_started = time.perf_counter()
packages = ['numpy','scipy','pandas','matplotlib','openpyxl','nbformat','nbclient','nbconvert','ipykernel']
environment = {'python':sys.version, 'executable':sys.executable, 'platform':platform.platform(),
               'packages':{p:importlib.metadata.version(p) for p in packages},
               'project_root':str(PROJECT_ROOT), 'run_root':str(RUN_ROOT), 'run_tag':RUN_TAG}
print(json.dumps(environment, indent=2))
""")
md("""
## Isolated source and data snapshot

Only source code, protocols and input data are copied into this new directory. The evaluation outputs will be created by the actual runs below. The manifest records the exact files used, including the original workbook, grouped data, source code, protocols and locked emulator coefficients.
""")
code(r"""
def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

inputs = []
for relative in ['research','research/v2']:
    source_dir=PROJECT_ROOT/relative
    destination=RUN_ROOT/relative
    destination.mkdir(parents=True,exist_ok=True)
    allowed_json={'protocol.json','protocol_draft.json','emulator_models.json','emulator_validation.json'}
    for path in source_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix=='.py' or path.name in allowed_json or path.name in {'requirements.txt','theory_note.md'}:
            shutil.copy2(path,destination/path.name)
            inputs.append(path.relative_to(PROJECT_ROOT))

for path in (PROJECT_ROOT/'application').rglob('*'):
    if path.is_file() and path.suffix in {'.py','.json','.csv','.xlsx','.txt','.md','.npz'} and '__pycache__' not in path.parts:
        relative=path.relative_to(PROJECT_ROOT)
        destination=RUN_ROOT/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
        inputs.append(relative)

input_manifest={str(p):sha256(PROJECT_ROOT/p) for p in sorted(set(inputs))}
manifest={'environment':environment,'input_sha256':input_manifest,
          'frozen_v1_protocol':json.loads((PROJECT_ROOT/'research/protocol.json').read_text()),
          'frozen_v2_protocol':json.loads((PROJECT_ROOT/'research/v2/protocol.json').read_text())}
(RUN_ROOT.parent/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
critical=['application/quaterny_opvs_experimental_data.xlsx','research/protocol.json',
          'research/lab_memory.py','research/run_study.py','research/v2/protocol.json',
          'research/v2/opv_confirmation.py','research/v2/confirmation_planner.py',
          'research/v2/emulator_models.json']
display(pd.DataFrame([{'input':p,'sha256':input_manifest[p]} for p in critical]))
assert not (RUN_ROOT/'research/trial_results.csv').exists()
assert not (RUN_ROOT/'research/v2/trial_results.csv').exists()
print(f'Copied {len(input_manifest)} source/input files; neither evaluation CSV exists yet.')
""")
code(r"""
run_logs=[]
def run_python(relative, *arguments):
    from uuid import uuid4
    script=RUN_ROOT/relative
    command=[sys.executable,str(script),*map(str,arguments)]
    log_name=relative.replace('/','__').replace('.py','')+'__'+uuid4().hex+'.log'
    log_path=LOG_ROOT/log_name
    started=time.perf_counter()
    with log_path.open('w') as log:
        process=subprocess.Popen(command,cwd=script.parent,stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in process.stdout:
            log.write(line);log.flush()
            print(f'[{script.name}] {line}',end='')
        return_code=process.wait()
    record={'script':relative,'command':command,'return_code':return_code,
            'elapsed_seconds':time.perf_counter()-started,'log':str(log_path),
            'log_sha256':sha256(log_path)}
    run_logs.append(record)
    if return_code!=0:
        raise RuntimeError(f'{relative} failed with exit code {return_code}; see {log_path}')
    return record

run_python('research/test_lab_memory.py')
run_python('research/v2/test_v2.py')
""")
md(r"""
## Measured OPV evidence, regenerated from the original workbook

The authors' data are from Langner et al., *Beyond Ternary OPV: High-Throughput Experimentation and Self-Driving Laboratories Optimize Multicomponent Systems*, DOI [10.1002/adma.201907801](https://doi.org/10.1002/adma.201907801). Duplicate compositions and both SDA replicate readings are preserved. Negative degradation readings are retained. The two systems share some constituent measurements, so they are not fully independent material replications.

The declared threshold is degradation at most 0.10. Replicate threshold disagreement is descriptive evidence of measurement/reconfirmation difficulty. Neither reading is assumed to be ground truth, and these data do not identify carryover causally.
""")
code(r"""
run_python('application/extract_measured_data.py')
run_python('application/reconfirmation_analysis.py')
measured=json.loads((RUN_ROOT/'application/measured_reconfirmation_summary.json').read_text())
display(pd.DataFrame(measured['rows']))
display(Markdown(f"The recomputation found **{measured['total_disagreements']} of {measured['total_pairs']}** paired formulations on opposite sides of the declared threshold."))
display(Image(filename=str(RUN_ROOT/'application/figures/paired_measured_responses.png')))
for name in ['pbq_qf_hte_composition_means.csv','ptb7_th_hte_composition_means.csv','measured_sda_replicate_pairs.csv']:
    assert sha256(RUN_ROOT/'application'/name)==sha256(PROJECT_ROOT/'application'/name)
print('Workbook extraction reproduced all frozen grouped/paired CSV hashes.')
""")
md(r"""
## Published resource and carryover context

These primary-source tables are contextual evidence, not a transfer calibration. The OPV publication reports batch preparation and processing durations; overlapping batch processes cannot be summed to infer a marginal fresh/routine assay-cost ratio. The separate AutoFSP measurements use a different apparatus and a different carryover definition, so they are not a calibration of the OPV retained-mass fraction. All simulated cost ratios and apparatus bounds remain declared assumptions.
""")
code(r"""
for relative in ['application/opv_reported_resource_times.csv',
                 'application/autofsp/reported_resource_times.csv',
                 'application/autofsp/carryover_measurements.csv']:
    display(Markdown(f'### {relative}'))
    display(pd.read_csv(RUN_ROOT/relative))
""")
md(r"""
## Response emulator: grouped development selection and untouched held-out fidelity

The primary family is a prespecified cubic Bernstein polynomial. Ridge strength is selected using validation composition groups only; the family is not changed after seeing held-out accuracy. The final train+validation fit is locked before its test error is computed. A separate, predeclared piecewise-affine interpolator supplies an emulator-sensitivity case.

For degree \(p\), the emulator's full-simplex L1 certificate is

\[
L=\frac p2\max_{|\gamma|=p-1,i,j}|\beta_{\gamma+e_i}-\beta_{\gamma+e_j}|.
\]

This follows from the range of the directional derivative on the simplex tangent space. It certifies this mathematical emulator only. Empirical pairwise slopes do not provide a valid upper bound for an unknown material's global sensitivity. The confirmation policy receives the scalar certificate, not the coefficients or clean response function.
""")
code(r"""
run_python('research/v2/opv_bernstein.py')
emulator=json.loads((RUN_ROOT/'research/v2/emulator_validation.json').read_text())
emulator_table=pd.DataFrame([{'system':system,**record['held_out'],
                            'L1_certificate':record['lipschitz_l1'],'ridge':record['selected_ridge']}
                           for system,record in emulator.items()])
display(emulator_table)
assert sha256(RUN_ROOT/'research/v2/emulator_models.json')==sha256(PROJECT_ROOT/'research/v2/emulator_models.json')
assert sha256(RUN_ROOT/'research/v2/emulator_validation.json')==sha256(PROJECT_ROOT/'research/v2/emulator_validation.json')
print('Locked emulator coefficients, selected ridge strengths and held-out validation reproduce exactly.')
run_python('application/validate_piecewise_affine.py')
piecewise=json.loads((RUN_ROOT/'application/piecewise_affine_validation.json').read_text())
display(pd.DataFrame([{'system':name,'coverage':d['validation']['coverage'],
                      **d['validation']['pooled_covered_metrics'],
                      'L1_certificate':d['full_data_emulator']['lipschitz_l1']}
                     for name,d in piecewise['results'].items()]))
""")
md(r"""
## Apparatus memory, confidence and preparation planning

With fixed final batch mass, actual composition is

\[
z_t=(1-r_t)x_t+r_t h_{t-1},\qquad r_t=\rho\eta^{k_t},\qquad
h_t=(1-\lambda)h_{t-1}+\lambda z_t.
\]

Fresh preparation measures the nominal candidate independently and leaves the shared line's residual unchanged. Under candidate-only shared-line actions and externally valid bounds, define

\[
\bar r_t=\bar\rho\bar\eta^{k_t},\quad
D_t=[1-\underline\lambda(1-\bar r_t)]D_{t-1},\quad
B_t=L\bar r_tD_{t-1},\quad D_0=2.
\]

Then the latent observation differs from the fresh candidate response by at most\(B_t\). Fresh actions have \(B_t=0\) and do not change \(D_t\). For a schedule and selection of observations fixed before confirmation outcomes, independent Gaussian noise gives the fixed-final interval

\[
\bar Y\ \pm\ \left[\bar B+1.959963984540054\frac{\sigma}{\sqrt n}\right].
\]

This interval has conditional coverage at least 95% for the frozen candidate **when all stated bounds and the noise assumption hold**. It is not an optional-stopping or false-discovery-rate guarantee. A separate finite-horizon sub-Gaussian construction uses \(\sigma\sqrt{2\log(2T/\alpha)/n}\); it is not substituted silently into the fixed-final experiment.

The preplanned policy enumerates counts of routine, one-wash, three-wash and fresh candidate assays. For two adjacent retained bounds \(r_a\le r_b\), exchanging their order changes the total bias bound by

\[
S_{ab}-S_{ba}=LD\underline\lambda(r_a-r_b)\le0,
\]

while the downstream residual bound is unchanged. Thus strongest washes first minimize summed bias for fixed counts. The optimizer is exact only within this finite menu of fixed schedules using all observations with equal weights. The discard-four control is outside that class and can be better. Fresh placement is fixed last; placement equivalence applies only to the final equal-weight radius objective.

At equal fresh/routine cost, an all-fresh schedule has zero modeled bias and the largest affordable sample count. Any claimed advantage of shared-line preparation must therefore be conditional on cost assumptions.
""")
code(r"""
sys.path.insert(0,str(RUN_ROOT/'research/v2'))
import confirmation_planner as planner
import inspect
display(Code(inspect.getsource(planner.block),language='python'))
display(Code(inspect.getsource(planner.optimize_plan),language='python'))
test_plan=planner.optimize_plan(planner.PlannerInputs(1.8,.5,.3,.4,budget=8,fresh_cost=1))
display(pd.DataFrame([{k:v for k,v in test_plan.items() if not isinstance(v,(dict,list))}]))
assert test_plan['n_fresh']==8 and test_plan['mean_bias_bound']==0
print('Equal-cost fresh-control identity checked from the executable planner.')
""")
md(r"""
## Execute every frozen computational experiment

The v1 and v2 scripts below are independent after preparation of the input data, so they run concurrently in two subprocesses. Both execute the full frozen seed lists and all methods. Their command lines, return codes, wall times and complete output logs are retained. No reduced-size demonstration run replaces the report experiments.

V1 uses report seeds 10000–10399, twelve regimes and ten policies. V2 uses report seeds 200000–200199 in each main case, and the declared first 100 seeds for each sensitivity. Development seeds remain separate. The v2 sensitivities include the Delaunay emulator, broad calibration bounds, empirical replicate-contrast noise and equal fresh/routine cost.
""")
code(r"""
with ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(run_python,'research/run_study.py'),
             pool.submit(run_python,'research/v2/run_v2.py')]
    completed=[future.result() for future in futures]
display(pd.DataFrame(completed)[['script','return_code','elapsed_seconds','log_sha256']])
""")
code(r"""
run_python('research/make_figures.py')
run_python('research/write_results.py')
run_python('research/v2/make_v2_figures.py')
run_python('research/v2/audit_noise_coverage.py')
run_python('research/v2/write_v2_results.py')
baseline=json.loads((RUN_ROOT/'research/summary.json').read_text())
extension=json.loads((RUN_ROOT/'research/v2/summary.json').read_text())
display(pd.DataFrame([{'study':'v1','policy_runs':baseline['total_policy_runs'],
                       'cases':baseline['number_of_regimes'],'methods':baseline['number_of_methods']},
                      {'study':'v2','policy_runs':extension['total_policy_runs'],
                       'cases':extension['number_of_cases'],'methods':extension['number_of_methods']}]))
""")
md("""
## Reproducibility comparison against frozen originals

The following comparison reads the frozen originals only after the fresh computations finish. It checks complete raw result rows, numerical values and deterministic hashes. Time stamps and run-duration metadata are expected to differ and are not treated as scientific discrepancies.
""")
code(r"""
comparisons=[]
for relative in ['research/trial_results.csv','research/v2/trial_results.csv',
                 'research/all_results_with_intervals.csv','research/v2/all_results_with_intervals.csv',
                 'research/paired_comparisons.csv','research/v2/paired_comparisons.csv']:
    original=pd.read_csv(PROJECT_ROOT/relative)
    rerun=pd.read_csv(RUN_ROOT/relative)
    pd.testing.assert_frame_equal(original,rerun,check_exact=True)
    comparison={'artifact':relative,'rows':len(rerun),'all_values_exactly_equal':True,
                'sha256_equal':sha256(PROJECT_ROOT/relative)==sha256(RUN_ROOT/relative),
                'rerun_sha256':sha256(RUN_ROOT/relative)}
    comparisons.append(comparison)
display(pd.DataFrame(comparisons))
assert all(r['sha256_equal'] for r in comparisons)
for relative in ['research/validation.json','research/v2/validation.json']:
    check=json.loads((RUN_ROOT/relative).read_text())
    assert check.get('all_checks_passed',check.get('all_data_checks_passed',False))
    display(Markdown(f'**{relative}: every integrity check passed.**'))
""")
md("""
## Full v1 results

Every method and regime is shown below. False confirmation uses all campaigns as its denominator; false fraction among accepts and sensitivity among truly qualifying candidates are separately available in the complete interval table. Zero observed events do not establish zero risk, and a degenerate paired bootstrap interval is not evidence of equivalence.
""")
code(r"""
v1_table=pd.read_csv(RUN_ROOT/'research/all_results_with_intervals.csv')
v1_columns=['regime','method','n','true_good_count','false_accept_count','false_accept',
            'false_accept_ci95_low','false_accept_ci95_high','true_accept','false_reject',
            'unresolved','absolute_error','cost']
display(v1_table[v1_columns])
display(Image(filename=str(RUN_ROOT/'research/figures/figure_primary_rates.png')))
display(Image(filename=str(RUN_ROOT/'research/figures/figure_paired_effects.png')))
""")
code(r"""
display(Markdown((RUN_ROOT/'research/RESULTS.md').read_text()))
""")
md("""
## Full v2 main and sensitivity results

The table includes every policy in every case, with counts and intervals computed from the fresh rerun. Many discoveries already meet the illustrative target; true-good prevalence is therefore essential when interpreting a zero false-acceptance count. A zero denominator for invalid-candidate conditional rates is undefined, not zero.
""")
code(r"""
v2_table=pd.read_csv(RUN_ROOT/'research/v2/all_results_with_intervals.csv')
v2_columns=['system','condition','scenario','method','n','true_good_count','false_accept_count',
            'false_accept','true_accept','false_reject','unresolved','interval_coverage',
            'ci_halfwidth','absolute_error','cost']
display(v2_table[v2_columns])
paired_v2=pd.read_csv(RUN_ROOT/'research/v2/paired_comparisons.csv')
display(paired_v2[paired_v2.metric.isin(['false_accept','true_accept','ci_halfwidth'])])
""")
code(r"""
coverage_audit=json.loads((RUN_ROOT/'research/v2/coverage_noise_audit.json').read_text())
display(pd.DataFrame(coverage_audit['records']))
display(Markdown(coverage_audit['interpretation']))
""")
md("""
The preceding noise audit is a reconstruction of the same report draws. It does not add trials or tune away an unfavorable coverage result. In particular, the empirical shortfall remains part of the reported study.
""")
code(r"""
for figure in ['figure_v2_emulator_fidelity.png','figure_v2_policy_yield.png',
               'figure_v2_radius_frontier.png','figure_v2_robustness.png']:
    display(Image(filename=str(RUN_ROOT/'research/v2/figures'/figure)))
display(Markdown((RUN_ROOT/'research/v2/RESULTS.md').read_text()))
""")
md(r"""
## Limits and conclusions that the notebook can support

The v1 null comparison is retained: a complex adaptive control rule need not outperform repetition with the same history model. The v2 result is a conditional preparation-planning construction whose exact scope is a finite schedule menu and an equal-weight confidence radius. It is not a universal best policy. The physically meaningful questions are when the line can be cleared cheaply, how trustworthy the supplied calibration bounds are, and whether fresh preparation is actually more costly.

Measured response predictions have visible held-out errors. The theorem certifies the emulator, while the measured-data analysis reports literal replicate disagreements without causal attribution. Unknown true-material smoothness, unverified apparatus bounds, misspecified noise and unmeasured costs remain unresolved experimental requirements. None is hidden by a zero observed simulation error rate.

The complete proofs and qualifications are retained in the bundled theory note. All numerical statements in the result sections above are generated from the executed data.
""")
code(r"""
display(Markdown((RUN_ROOT/'research/theory_note.md').read_text()))
""")
md("""
## Execution record and artifact manifest

All command logs and newly generated outputs remain in the isolated rerun directory. The final manifest includes environment versions, inputs, seeds/protocols, commands, return codes, elapsed time and the exact comparison results. This notebook has no skipped code cells and execution is configured to fail on any exception.
""")
code(r"""
original_changes=[p for p,h in input_manifest.items() if sha256(PROJECT_ROOT/p)!=h]
assert not original_changes, f'Original source/input files changed during execution: {original_changes}'
assert all(r['return_code']==0 for r in run_logs)
elapsed=time.perf_counter()-notebook_started
execution_manifest={**manifest,'run_logs':run_logs,'comparisons':comparisons,
                    'elapsed_seconds':elapsed,'original_inputs_unchanged':True,
                    'all_commands_successful':True,'all_raw_and_summary_values_exactly_reproduced':True,
                    'result_artifacts':[str(p.relative_to(RUN_ROOT)) for p in RUN_ROOT.rglob('*')
                                        if p.is_file() and p.suffix in {'.csv','.json','.png','.svg','.md'}]}
manifest_path=RUN_ROOT.parent/'execution_manifest.json'
manifest_path.write_text(json.dumps(execution_manifest,indent=2)+'\n')
(PROJECT_ROOT/'research/notebook/latest_execution_manifest.json').write_text(json.dumps(execution_manifest,indent=2)+'\n')
display(pd.DataFrame(run_logs)[['script','return_code','elapsed_seconds','log_sha256']])
print(f'All full experiments and checks completed in {elapsed:.1f} seconds.')
print(f'Execution manifest: {manifest_path}')
print(f'Isolated result tree: {RUN_ROOT}')
""")

nb.cells=cells
path=HERE/"when_the_lab_remembers_executed.ipynb"
nbf.write(nb,path)
requirements=['numpy','scipy','pandas','matplotlib','openpyxl','nbformat','nbclient','nbconvert','ipykernel']
(HERE/"requirements_notebook.txt").write_text("\n".join(f"{p}=={importlib.metadata.version(p)}" for p in requirements)+"\n")
print(f"Built {len(cells)} cells ({sum(c.cell_type=='code' for c in cells)} executable code cells): {path}")
