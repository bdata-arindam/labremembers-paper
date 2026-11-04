"""Whitespace-only Markdown cleanup after execution; preserve all code/output."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import re
import nbformat
from nbconvert import HTMLExporter

HERE=Path(__file__).resolve().parent
path=HERE/"when_the_lab_remembers_executed.ipynb"
html_path=HERE/"when_the_lab_remembers_executed.html"
validation_path=HERE/"notebook_execution_validation.json"
before_notebook=hashlib.sha256(path.read_bytes()).hexdigest()
before_html=hashlib.sha256(html_path.read_bytes()).hexdigest()
notebook=nbformat.read(path,as_version=4)
def protected_cells(nb):
    return json.dumps([c for c in nb.cells if c.cell_type!="markdown"],sort_keys=True)
protected=protected_cells(notebook)
replacements={"at most0.10":"at most 0.10","at least95%":"at least 95%",
              "seeds10000":"seeds 10000","seeds200000":"seeds 200000",
              "first100":"first 100","degree\\(p\\)":"degree \\(p\\)",
              "most95%":"most 95%","by\\(B_t\\)":"by \\(B_t\\)",
              "have\\(B_t=0\\)":"have \\(B_t=0\\)",
              "change\\(D_t\\)":"change \\(D_t\\)",
              "uses\\(":"uses \\(","bounds\\(":"bounds \\("}
def clean(text):
    for old,new in replacements.items():text=text.replace(old,new)
    return text
changed=[]
for index,cell in enumerate(notebook.cells):
    if cell.cell_type!="markdown":continue
    new=clean(cell.source)
    if new!=cell.source:
        # Explicitly reject any non-whitespace content change.
        assert re.sub(r"\s+","",new)==re.sub(r"\s+","",cell.source)
        cell.source=new;changed.append(index)
assert protected_cells(notebook)==protected
nbformat.write(notebook,path)
html,_=HTMLExporter().from_notebook_node(notebook)
html_path.write_text(html)
builder=HERE/"build_notebook.py"
source=builder.read_text()
def replace_markdown(match):
    return match.group(1)+clean(match.group(2))+match.group(3)
source=re.sub(r'(md\(r?"""\n?)(.*?)("""\))',replace_markdown,source,flags=re.S)
builder.write_text(source)
report=json.loads(validation_path.read_text())
report["post_execution_formatting"]={"kind":"Whitespace-only Markdown cell cleanup and HTML re-export",
    "changed_markdown_cell_indices":changed,"code_outputs_and_execution_counts_unchanged":True,
    "previous_notebook_sha256":before_notebook,"previous_html_sha256":before_html,
    "formatted_utc":datetime.now(timezone.utc).isoformat()}
report["notebook_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
report["html_sha256"]=hashlib.sha256(html_path.read_bytes()).hexdigest()
validation_path.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
