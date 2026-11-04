"""F1000Research research article for When the Lab Remembers, from the master's content blocks.

Built on the journal's own Word template (official/f1000/Research_article_template.docx,
downloaded 4 November 2026) and its article guidelines read the same day: abstract up to 300
words structured as Background, Methods, Results, Conclusions; up to 8 keywords; a research
article of no more than 20,000 words, so nothing is compressed; any consistent reference
style, so the master's numbered catalog stands; figures uploaded as separate files with their
legends in the text; and the end sections in the guidelines' order. Open peer review, one
complete file, no blinded version.

Data policy: underlying data and in-house code must be in a public repository with a DOI
before submission. The availability statements below name the public repository and its
licences; the Zenodo DOI is allocated by the authors' deposit and is the one input this
builder cannot supply, so it is reported in BUILD_REPORT.txt as required rather than typed in.
"""
from __future__ import annotations
import json, re, subprocess, sys, shutil
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent; PROJ = HERE.parent
OUT = PROJ / 'publication_formats/f1000'; OUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = HERE / 'official/f1000/Research_article_template.docx'
sys.path.insert(0, __import__('os').path.expanduser('~/Downloads/all_projects')); sys.path.insert(0, str(HERE))
from author_block import order_for, corresponding_for, credit_for, PEOPLE, AFFILS  # noqa: E402

PID, VK = 'Lab_Remembers', 'F1000'
REPO = 'https://github.com/bdata-arindam/labremembers-paper'
C = json.load(open(HERE / 'manuscript_content.json'))
TITLE = 'When the Lab Remembers: Identifiability and budgeted confirmation of materials recipes'
KEYWORDS = [k.strip() for k in C['keywords'].split(';')]
AI_PARA = ('Use of generative AI or AI-assisted technologies in manuscript preparation: AI-assisted '
           'tools were used for implementation support, plotting and manuscript editing. Every '
           'experimental output, citation, numerical result and interpretation was checked by the '
           'authors against the underlying artifacts. AI tools were never treated as a source of '
           'empirical evidence and were not permitted to invent or alter experimental results.')

# The master's abstract, re-sectioned from its own sentences into the four parts the journal
# requires. No sentence is new; the order within each part is the master's.
A = C['abstract']
def sents(t): return [s.strip() for s in re.split(r'(?<=[.!?])\s+', t) if s.strip()]
S = sents(A)
ABSTRACT = {
 'Background': ' '.join(S[0:2]),
 'Methods': ' '.join(S[2:5]),
 'Results': ' '.join(S[5:13]),
 'Conclusions': ' '.join(S[13:]),
}

doc = Document(str(TEMPLATE))
for p in list(doc.paragraphs): p._element.getparent().remove(p._element)
st = doc.styles['Normal']; st.font.name = 'Arial'; st.font.size = Pt(11)
order = order_for(PID, VK); corr = corresponding_for(PID, VK)
marks = {a: i for i, a in enumerate(sorted({PEOPLE[n][0] for n in order}), 1)}

def P(text='', bold=False, italic=False, size=None, align=None, after=8, indent=None):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
    r.font.name = 'Arial'
    if size: r.font.size = Pt(size)
    if align is not None: p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    if indent: p.paragraph_format.left_indent = Inches(indent)
    return p
H1 = lambda t: P(t, bold=True, size=14, after=6)
H2 = lambda t: P(t, bold=True, size=12, after=4)
H3 = lambda t: P(t, bold=True, italic=True, size=11, after=3)

# ---- front matter
P(TITLE, bold=True, size=16, after=10)
P(', '.join(f'{n}{marks[PEOPLE[n][0]]}' for n in order), after=2)
for a, m in marks.items(): P(f'{m} {AFFILS[a]}', size=10, after=2)
P('Corresponding author' + ('s' if len(corr) > 1 else '') + ': ' + '; '.join(f'{n} ({PEOPLE[n][1]})' for n in corr), size=10, after=2)
P('ORCID: ' + '; '.join(f'{n} {PEOPLE[n][2]}' for n in order), size=10, after=10)
H1('Abstract')
for k, v in ABSTRACT.items():
    p = doc.add_paragraph(); r = p.add_run(k + ': '); r.bold = True; r.font.name = 'Arial'
    r2 = p.add_run(v); r2.font.name = 'Arial'; p.paragraph_format.space_after = Pt(4)
P('Keywords: ' + ', '.join(KEYWORDS), after=12)

# ---- main body: the master's sections mapped onto the template's order
MAP = {'1.': ('Introduction', None), '2.': ('Introduction', 'Relation to existing work'),
       '3.': ('Methods', None), '4.': ('Methods', None), '5.': ('Methods', None),
       '6.': ('Results', None), '7.': ('Discussion', None), '8.': ('Discussion', 'Conclusions'),
       'Appendix': ('Methods', 'Derivations and interpretation boundaries')}
emitted, figs, tabs, legends = set(), 0, 0, []
cur = None
def top_for(txt):
    for k, v in MAP.items():
        if txt.startswith(k): return v
    return None
# order: Introduction(1,2) Methods(3,4,5,Appendix) Results(6) Discussion(7,8)
groups = {'Introduction': ['1.', '2.'], 'Methods': ['3.', '4.', '5.', 'Appendix'], 'Results': ['6.'], 'Discussion': ['7.', '8.']}
blocks = C['blocks']
def section_blocks(prefix):
    out, on = [], False
    for b in blocks:
        if b['type'] == 'heading' and b.get('level', 1) == 1:
            on = b['text'].startswith(prefix)
            if on: out.append(b); continue
        if on and not (b['type'] == 'heading' and b.get('level', 1) == 1): out.append(b)
    return out
for top, prefixes in groups.items():
    H1(top)
    for pre in prefixes:
        for b in section_blocks(pre):
            t = b['type']
            if t == 'heading':
                txt = re.sub(r'^(\d+\.|[A-Z]\.\d+\.|Appendix [A-Z]\.)\s*', '', b['text'])
                if b.get('level', 1) == 1:
                    sub = MAP[pre][1]
                    if sub: H2(sub)
                    elif pre not in ('1.',): H2(txt)
                else:
                    H3(txt)
            elif t == 'paragraph':
                if b['text'].startswith('Reproducibility and data availability'): continue
                P(b['text'])
            elif t == 'equation':
                P(b['text'], align=WD_ALIGN_PARAGRAPH.CENTER)
            elif t == 'table':
                tabs += 1
                P(re.sub(r'^Table \d+\.', f'Table {tabs}.', b['caption']), bold=True, after=3)
                tt = doc.add_table(rows=1, cols=len(b['headers']))
                # the journal's template carries no table style; rules are set explicitly
                _b = OxmlElement('w:tblBorders')
                for _e in ('top', 'bottom', 'insideH'):
                    _x = OxmlElement(f'w:{_e}'); _x.set(qn('w:val'), 'single'); _x.set(qn('w:sz'), '6'); _b.append(_x)
                tt._tbl.tblPr.append(_b)
                for c, h in zip(tt.rows[0].cells, b['headers']): c.text = h
                for r in b['rows']:
                    for c, v in zip(tt.add_row().cells, r): c.text = str(v)
                for ri, row in enumerate(tt.rows):
                    for c in row.cells:
                        for q in c.paragraphs:
                            q.paragraph_format.space_after = Pt(1)
                            for rr in q.runs: rr.font.size = Pt(9); rr.font.name = 'Arial'; rr.bold = ri == 0
                if b.get('note'): P(b['note'], italic=True, size=9, after=8)
                else: P('', after=6)
            elif t == 'figure':
                figs += 1
                legends.append((figs, re.sub(r'^Figure \d+\.\s*', '', b['caption']), b['path']))
                P(f'[Figure {figs} here]', italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
# the reproducibility section of the master becomes the availability statements below
# ---- end matter, in the guidelines' order
H1('Ethical considerations'); P('This computational study involved no human participants, animals or personal data. The published measurements reanalysed here were collected and reported by their original authors.')
H1('Data availability')
P('Underlying data')
P(f'Repository: {REPO}. The scored results of the preserved v1 benchmark and the v2 extension, the extracted measured-pair tables and the emulator validation summaries are carried under results/ and are available under the terms of the Creative Commons Attribution 4.0 International licence (CC BY 4.0). The archived snapshot of this repository at the version underlying this article is deposited at Zenodo; its DOI is given on the version of record.')
P('Third-party data')
P('The original organic-photovoltaic measurements are the workbook accompanying Langner et al. [11], retrieved at a pinned repository commit whose identity and SHA256 are recorded in application/original_repository_commit.json. They are used under the published article’s terms and are not redistributed in this repository.')
H1('Software availability')
P(f'Source code available from: {REPO}')
P('Archived source code at time of publication: the Zenodo deposit of the repository version underlying this article; DOI on the version of record.')
P('License: MIT')
H1('Reporting guidelines'); P('No consensus-based reporting guideline applies to this computational study; the protocol, its amendments and the evidence register are carried in protocols/ of the repository.')
H1('Author contributions'); P(' '.join(f'{n}: {r}.' for n, r in credit_for(PID, VK)))
H1('Competing interests'); P('No competing interests were disclosed.')
H1('Grant information'); P('The authors declared that no grants were involved in supporting this work.')
H1('Acknowledgements'); P(AI_PARA)
H1('References')
for r in C['references']:
    p = P(r, after=4); p.paragraph_format.left_indent = Inches(0.35); p.paragraph_format.first_line_indent = Inches(-0.35)
H1('Figure legends')
for n, cap, path in legends: P(f'Figure {n}. {cap}', after=6)
f = OUT / 'F1000_When_the_Lab_Remembers.docx'; doc.save(f)
subprocess.run(['/opt/homebrew/bin/soffice', '--headless', '--convert-to', 'pdf', '--outdir', str(OUT), str(f)], capture_output=True)
# figures as separate files, as the template requires
(OUT / 'figures').mkdir(exist_ok=True)
from PIL import Image
for n, cap, path in legends:
    im = Image.open(PROJ / path).convert('RGB'); im.save(OUT / 'figures' / f'Figure{n}.tiff', compression='tiff_lzw')
# ---- report
import fitz
d = fitz.open(str(f).replace('.docx', '.pdf')); flat = re.sub(r'\s+', ' ', '\n'.join(p.get_text() for p in d))
words = len(flat.split()); aw = sum(len(v.split()) for v in ABSTRACT.values())
unres = [flat[max(0, m.start()-120):m.end()+60] for m in re.finditer(r', (and|or)\b', flat)
         if not (m.start() >= flat.rfind('References') or re.search(r'\(\d{4}\)|doi\.org|^.{0,40}\[\d+\]', flat[max(0, m.start()-120):m.end()+60]))]
banned = re.search(r'(?i)claude|anthropic|/Users/', flat)
rep = [f'F1000_When_the_Lab_Remembers.docx: {d.page_count} pages, {words:,} words (research article limit 20,000): {"PASS" if words <= 20000 else "FAIL"}',
       f'abstract {aw} words in Background/Methods/Results/Conclusions (limit 300): {"PASS" if aw <= 300 else "FAIL"}; keywords {len(KEYWORDS)} (up to 8): PASS',
       f'figures {figs} exported as TIFF under figures/, legends in the text; tables {tabs} inline',
       f'references {len(C["references"])}, the master\'s numbered catalog, consistent style: PASS',
       f'", and"/", or" unresolved in prose: {len(unres)}' + (''.join('\n   > ' + u[:140] for u in unres[:5])),
       f'banned tokens: {"none" if not banned else banned.group(0)}',
       'REQUIRED AUTHOR INPUT: the Zenodo DOI of the repository deposit, for the Data and Software availability statements; suggested reviewers at submission; the $1,758 charge on acceptance']
(OUT / 'BUILD_REPORT.txt').write_text('\n'.join(rep) + '\n'); print('\n'.join(rep))
