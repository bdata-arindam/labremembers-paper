"""Inspect actual executed notebook, hashes and retained command provenance."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    directory = ROOT / "research/notebook"
    validation = json.loads((directory/"notebook_execution_validation.json").read_text())
    manifest = json.loads((directory/"latest_execution_manifest.json").read_text())
    notebook = json.loads((directory/"when_the_lab_remembers_executed.ipynb").read_text())
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    errors = [o for c in cells for o in c.get("outputs", []) if o.get("output_type") == "error"]
    unexecuted = [i for i, c in enumerate(cells) if c.get("execution_count") is None]
    checks = {
        "cell_counts_match": len(cells) == validation["code_cells"] == 17 and [c["execution_count"] for c in cells] == list(range(1, 18)),
        "no_errors_or_unexecuted": not errors and not unexecuted,
        "notebook_hash": digest(directory/"when_the_lab_remembers_executed.ipynb") == validation["notebook_sha256"],
        "html_hash": digest(directory/"when_the_lab_remembers_executed.html") == validation["html_sha256"]
    }
    input_mismatches = [p for p, expected in manifest["input_sha256"].items() if not (ROOT/p).exists() or digest(ROOT/p) != expected]
    checks["all_recorded_inputs_unchanged"] = not input_mismatches
    run_root = Path(manifest["environment"]["run_root"])
    comparisons = []
    for row in manifest["comparisons"]:
        original = ROOT/row["artifact"]
        rerun = run_root/row["artifact"]
        matches = digest(original) == digest(rerun) == row["rerun_sha256"]
        comparisons.append({"artifact": row["artifact"], "rows": row["rows"], "hash_match": matches})
    checks["six_result_hashes_match"] = len(comparisons) == 6 and all(r["hash_match"] for r in comparisons)
    logs = []
    for row in manifest["run_logs"]:
        path = Path(row["log"])
        logs.append({"script": row["script"], "command": row["command"], "return_code": row["return_code"], "path": str(path), "recorded_sha256": row["log_sha256"], "actual_sha256": digest(path) if path.exists() else None, "log_hash_match": path.exists() and digest(path) == row["log_sha256"]})
    checks["all_command_logs_match"] = all(r["return_code"] == 0 and r["log_hash_match"] for r in logs)
    body = "\n".join("".join(c.get("source", [])) for c in notebook["cells"])
    result = {
        "audit_id": "AUDIT-NOTEBOOK-INDEPENDENT", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python audit/check_notebook_execution.py",
        "status": "PASS" if all(checks.values()) else "PARTIAL",
        "checks": checks, "n_code_cells": len(cells), "execution_counts": [c["execution_count"] for c in cells],
        "error_outputs": len(errors), "recorded_input_count": len(manifest["input_sha256"]), "input_mismatches": input_mismatches,
        "result_comparisons": comparisons, "command_logs": logs, "execution_validation": validation,
        "manifest_path": "research/notebook/latest_execution_manifest.json", "manifest_sha256": digest(directory/"latest_execution_manifest.json"),
        "scope": "Independent inspection of actual executed notebook outputs, recorded hashes and command logs; not an additional rerun or human validation. Execution used nbclient with a real in-process IPython kernel in a newly launched interpreter.",
        "postrun_candidate_audit_mentioned_in_notebook": "candidate_prediction_audit" in body or "negative predicted" in body,
        "postrun_candidate_audit_scope": "The late manuscript P047b result is a separate post-run descriptive audit of existing outputs, with zero new campaigns. It is not silently attributed to one of the original 17 notebook code cells.",
        "interpretation": "A completed notebook and exact result reproduction do not constitute external scientific or physical validation. Any retained-log discrepancy is a provenance issue to resolve or disclose separately from result-value reproduction."
    }
    (ROOT/"audit/notebook_independent_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({"status": result["status"], "checks": checks, "commands": len(logs)}, indent=2))


if __name__ == "__main__":
    main()
