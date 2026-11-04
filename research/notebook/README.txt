# Complete executed notebook

`when_the_lab_remembers_executed.ipynb` contains the complete research workflow, and `when_the_lab_remembers_executed.html` is its readable executed export. The notebook runs the actual experiment entrypoints, rather than loading cached result tables in place of execution.

It regenerates the original-workbook data extraction, measured replicate analysis, published resource-context tables, locked cubic emulator development/test evaluation, independent piecewise-affine validation, both scientific test suites, all 48,000 v1 policy runs and all 62,400 v2 main/sensitivity policy runs. It then recreates figures/tables, reconstructs the retained coverage shortfall and compares complete raw/summary results with the frozen originals.

## Run locally

Keep the full project tree. The redistributed bundle excludes the authors' original workbook. Before rerunning, retrieve the pinned original workbook with `python application/retrieve_original_data.py` from the project root. That script uses the recorded source revision and verifies the workbook's SHA-256. Review `application/DATA_PROVENANCE.txt` and the source data's terms; this retrieval requires an internet connection. The notebook's extraction step expects the verified workbook at `application/quaterny_opvs_experimental_data.xlsx`.

Install the package versions in `requirements_notebook.txt`, open the notebook with that Python environment and select **Run All**. The first cell searches parent directories for the project root. Set `LAB_REMEMBERS_ROOT` if the notebook is opened from another location.

The v1 and v2 experiment scripts run concurrently after data/emulator preparation, with independent output paths and complete command logs. Every run creates a new directory under `runs/`; frozen original outputs are never overwritten. The complete execution can take several minutes.

The accompanying `build_notebook.py` creates the source notebook. `execute_notebook.py` executes it and exports HTML. In this execution environment, local TCP and Unix-domain sockets are prohibited. The executor therefore uses an actual IPython in-process kernel hosted in a newly launched Python interpreter, with a fresh user namespace, and drives it through `nbclient`. A small adapter handles public client API signatures and routes real kernel stream messages to their active cell. Execution counts, display outputs and errors come from the kernel; none is fabricated.

This transport choice changes no scientific source, random seeds or outputs. On an unrestricted local Jupyter installation the notebook may be run with a normal fresh Python kernel.

For a clean regenerated notebook, run `python build_notebook.py` and then `python execute_notebook.py` from this directory after retrieving the original workbook. The builder now assigns a unique log filename to each invocation, so repeated calls cannot overwrite a previous basename. This logging improvement was made after the archived notebook execution; the delivered executed notebook preserves its original code, outputs and counters exactly.

## Validation outputs

`notebook_execution_validation.json` records the completed code-cell counts, any error/unexecuted cells, execution time and final notebook/HTML hashes. `latest_execution_manifest.json` records the full environment, original input hashes, frozen configurations, actual subprocess commands, exit codes, log hashes, complete-result comparisons and the isolated output location.

All rate tables use their explicit denominators. The notebook retains the original adaptive-policy null result, modest held-out material-emulator fidelity and the observed 183/200 coverage shortfall. Conditional emulator theory is distinguished from experimental evidence throughout.

The final notebook received a documented whitespace-only Markdown formatting pass after execution. Its code, outputs and execution counters were preserved exactly; the HTML was re-exported and final hashes were refreshed in the execution validation record.

`kernel_transport_attempts.json` retains verbatim excerpts of the unsuccessful TCP/Unix kernel-start attempts and identifies the successful execution route. `reconfirmation_log_recovery.json` documents one retained log found empty during review. Its exact original bytes were recovered from actual captured notebook stream output and verified against the original manifest's SHA-256 before restoration. The observed empty file and a separately labeled recovered copy are both retained. The original execution manifest and all scientific results remain unchanged; the cause of the empty file was not established.
