"""Execute the complete notebook in a fresh kernel, then export HTML and audit."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import os
import time
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from ipykernel.inprocess.manager import InProcessKernelManager
from ipykernel.inprocess.blocking import BlockingInProcessKernelClient

HERE=Path(__file__).resolve().parent
path=HERE/"when_the_lab_remembers_executed.ipynb"
os.environ["LAB_REMEMBERS_ROOT"]=str(HERE.parent.parent)
notebook=nbformat.read(path,as_version=4)
start=time.perf_counter()

def on_cell_start(cell,cell_index,**kwargs):
    if cell.cell_type=="code":
        print(f"Executing code cell at notebook index{cell_index}: {cell.source.splitlines()[0][:100]}",flush=True)

class InProcessClientAdapter(BlockingInProcessKernelClient):
    """Adapt public in-process API signatures; outputs remain real kernel messages."""
    def wait_for_ready(self,timeout=None):
        return super().wait_for_ready()

    def _dispatch_to_kernel(self,message):
        # In-process streams need the active request header for nbclient's routing.
        self.kernel.stdout.set_parent(message)
        self.kernel.stderr.set_parent(message)
        return super()._dispatch_to_kernel(message)


class FreshInProcessManager(InProcessKernelManager):
    def client(self,**kwargs):
        kwargs["kernel"]=self.kernel
        return InProcessClientAdapter(parent=self,session=self.session,**kwargs)

    def shutdown_kernel(self,now=False,restart=False):
        return super().shutdown_kernel()


# This script is launched in a new Python interpreter. The kernel has a new
# user namespace and exchanges actual Jupyter messages without network sockets.
manager=FreshInProcessManager()
client=NotebookClient(notebook,km=manager,timeout=2400,allow_errors=False,
                      resources={"metadata":{"path":str(HERE)}},record_timing=True,
                      on_cell_start=on_cell_start)
try:
    client.execute()
finally:
    nbformat.write(notebook,path)
    manager.shutdown_kernel()

code_cells=[c for c in notebook.cells if c.cell_type=="code"]
errors=[o for c in code_cells for o in c.get("outputs",[]) if o.get("output_type")=="error"]
counts=[c.execution_count for c in code_cells]
assert all(isinstance(c,int) for c in counts),"A code cell was not executed"
assert len(set(counts))==len(counts),"Execution counts are not unique"
assert not errors,"Notebook contains an error output"
html,_=HTMLExporter().from_notebook_node(notebook)
(HERE/"when_the_lab_remembers_executed.html").write_text(html)
report={"fresh_kernel":True,"kernel":"IPython InProcessKernel in a newly launched Python interpreter",
        "execution_engine":"nbclient with public in-process client/manager API adapter",
        "transport":"in-process Jupyter messages; no TCP or Unix sockets", "code_cells":len(code_cells),
        "execution_counts":counts,"unexecuted_code_cells":0,"error_outputs":0,
        "elapsed_seconds":time.perf_counter()-start,"completed_utc":datetime.now(timezone.utc).isoformat(),
        "notebook_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "html_sha256":hashlib.sha256((HERE/"when_the_lab_remembers_executed.html").read_bytes()).hexdigest()}
(HERE/"notebook_execution_validation.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
