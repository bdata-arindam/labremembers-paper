"""Recover exact original log bytes from retained, genuinely executed output."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import nbformat

HERE=Path(__file__).resolve().parent
manifest_path=HERE/"latest_execution_manifest.json"
manifest_bytes=manifest_path.read_bytes()
manifest=json.loads(manifest_bytes)
entry=next(r for r in manifest["run_logs"] if r["script"]=="application/reconfirmation_analysis.py")
log_path=Path(entry["log"])
observed=log_path.read_bytes()
observed_stat=log_path.stat()
notebook_path=HERE/"when_the_lab_remembers_executed.ipynb"
nb=nbformat.read(notebook_path,as_version=4)
prefix="[reconfirmation_analysis.py] "
captures=[]
for index,cell in enumerate(nb.cells):
    if cell.cell_type!="code":continue
    text="".join(o.get("text","") for o in cell.get("outputs",[]) if o.get("output_type")=="stream")
    lines=[line[len(prefix):] for line in text.splitlines(keepends=True) if line.startswith(prefix)]
    if lines:captures.append((index,"".join(lines).encode()))
assert len(captures)==1,"Recovery is ambiguous"
cell_index,recovered=captures[0]
digest=hashlib.sha256(recovered).hexdigest()
assert digest==entry["log_sha256"],"Captured output does not reproduce original recorded log bytes"
backup=log_path.with_name(log_path.stem+".observed_empty_before_recovery.log")
recovery_copy=log_path.with_name(log_path.stem+".recovered_from_notebook.log")
backup.write_bytes(observed)
recovery_copy.write_bytes(recovered)
log_path.write_bytes(recovered)
assert manifest_path.read_bytes()==manifest_bytes
bad=[]
for item in manifest["run_logs"]:
    if hashlib.sha256(Path(item["log"]).read_bytes()).hexdigest()!=item["log_sha256"]:
        bad.append(item["script"])
assert not bad
report={"kind":"Documented exact recovery of a retained command log", "recovered_utc":datetime.now(timezone.utc).isoformat(),
        "manifest_unchanged":True,"manifest_sha256":hashlib.sha256(manifest_bytes).hexdigest(),
        "notebook_sha256":hashlib.sha256(notebook_path.read_bytes()).hexdigest(),
        "script":entry["script"],"recorded_original_log_sha256":entry["log_sha256"],
        "observed_log_bytes_before_recovery":len(observed),
        "observed_log_sha256_before_recovery":hashlib.sha256(observed).hexdigest(),
        "observed_log_mtime_utc":datetime.fromtimestamp(observed_stat.st_mtime,timezone.utc).isoformat(),
        "retained_empty_observation":str(backup),"recovered_copy":str(recovery_copy),
        "restored_original_path":str(log_path),"source_notebook_cell_index":cell_index,
        "source_notebook_execution_count":nb.cells[cell_index].execution_count,
        "transformation":"Concatenate retained real stdout stream outputs for that cell; select lines beginning with the helper's exact script-name prefix; remove only that prefix, retaining original line endings.",
        "recovered_bytes":len(recovered),"recovered_sha256":digest,
        "all_manifest_log_hashes_now_match":True,
        "cause":"The exact cause of the empty retained file is not established. A filename collision was suggested but is not asserted as proven.",
        "scientific_runs_repeated":False,"notebook_code_outputs_counters_changed":False}
(HERE/"reconfirmation_log_recovery.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
