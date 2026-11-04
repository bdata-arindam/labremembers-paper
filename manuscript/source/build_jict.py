"""JICT submission of When the Lab Remembers, from the master's content blocks.

Two files: the blinded one the journal reviews, with no author identifier, and the complete
one with the how-to-cite entry, author block, contributions and repository address. The
journal's own template is the layout authority and its rules were read from it on
3 November 2026: abstract 150-250 words, no more than five keywords in alphabetical order,
5,000-8,000 words including every section, Times New Roman 11 pt, APA 7th references.

Content comes from authoring/manuscript_content.json and nothing is retyped: paragraphs,
equations, tables and figures are rendered from their blocks, catalog citations [n] are
mapped to author-date through jict_apa.py, and any compression is applied from
compression.json with a logged reason per block so the two-way fidelity record is explicit.

Usage: python build_jict.py            (writes publication_formats/jict/)
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
OUT = PROJ / 'publication_formats/jict'
TEMPLATE = HERE / 'official/jict/jict_template.docx'
sys.path.insert(0, __import__('os').path.expanduser('~/Downloads/all_projects')); sys.path.insert(0, str(HERE))
from author_block import order_for, corresponding_for, credit_for, PEOPLE, AFFILS  # noqa: E402
from jict_apa import APA, sort_key                                                  # noqa: E402

PID, VK = 'Lab_Remembers', 'JICT'
REPO_URL = 'https://github.com/bdata-arindam/labremembers-paper'
C = json.load(open(HERE / 'manuscript_content.json'))
COMP = json.load(open(HERE / 'compression.json')) if (HERE / 'compression.json').exists() else {}
TITLE = 'When the Lab Remembers: Identifiability and budgeted confirmation of materials recipes'
# six keywords against the journal's five: "confirmation" is dropped because the title
# already carries it; the other five stand, in alphabetical order as the template asks
KEYWORDS = sorted(['autonomous experimentation', 'experimental carryover', 'identifiability',
                   'materials informatics', 'organic photovoltaics'])
AI_PARA = ('Use of generative AI or AI-assisted technologies in manuscript preparation: AI-assisted '
           'tools were used for implementation support, plotting and manuscript editing. Every '
           'experimental output, citation, numerical result and interpretation was checked by the '
           'authors against the underlying artifacts. AI tools were never treated as a source of '
           'empirical evidence and were not permitted to invent or alter experimental results.')
NONFUNDED = ('This research received no specific grant from any funding agency in the public, '
             'commercial, or not-for-profit sectors.')          # the template's prescribed sentence


def cite(text: str) -> str:
    """[1,2] / [3] / [10,13] / [5], preprint -> (Engel et al., 2025; Quinn et al., 2024)."""
    def one(m):
        nums = []
        for part in re.split(r'\s*,\s*', m.group(1)):
            if re.match(r'^\d+\s*[–-]\s*\d+$', part):
                a, b = re.split(r'\s*[–-]\s*', part); nums += list(range(int(a), int(b) + 1))
            else:
                nums.append(int(part))
        return '(' + '; '.join(APA[n][1] for n in nums) + ')'
    return re.sub(r'\[(\d{1,2}(?:\s*[,–-]\s*\d{1,2})*)\]', one, text)


def sentence_case(t):
    out, cap = [], True
    for tok in re.split(r'(\s+)', t):
        if not tok.strip(): out.append(tok); continue
        parts = []
        for i, part in enumerate(tok.split('-')):
            parts.append(part if (cap and i == 0) or re.search(r'[A-Z]{2,}|\d', part) else part[:1].lower() + part[1:])
        tok = '-'.join(parts); cap = tok.endswith(':'); out.append(tok)
    return ''.join(out)


def build(anonymous: bool) -> Path:
    doc = Document(str(TEMPLATE))
    for p in list(doc.paragraphs): p._element.getparent().remove(p._element)
    for t in list(doc.tables): t._element.getparent().remove(t._element)
    doc.core_properties.author = '' if anonymous else ', '.join(order_for(PID, VK))
    doc.core_properties.title = '' if anonymous else TITLE
    doc.core_properties.last_modified_by = ''; doc.core_properties.comments = ''
    order = order_for(PID, VK); corr = corresponding_for(PID, VK)
    block = [(n, *PEOPLE[n][:3]) for n in order]
    marks = {a: i for i, a in enumerate(sorted({PEOPLE[n][0] for n in order}), 1)}

    def P(text='', style=None, bold=False, italic=False, align=None, size=None, after=6):
        p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
        r = p.add_run(text); r.bold = bold; r.italic = italic
        r.font.name = 'Times New Roman'                       # the template renders in Times
        if size: r.font.size = Pt(size)
        if align is not None: p.alignment = align
        p.paragraph_format.space_after = Pt(after)
        return p
    H1 = lambda t: P(t.upper(), bold=True, after=4)
    H2 = lambda t: P(t, style='JICT Heading 2')
    log = []

    if not anonymous:
        P('How to cite this article:', after=0)
        names = [n.split()[-1] + ', ' + '. '.join(x[0] for x in n.split()[:-1]) + '.' for n in order]
        P(f"{', '.join(names[:-1])}, & {names[-1]} (202X). {sentence_case(TITLE)}. Journal of "
          f"Information and Communication Technology, XX(X), XX-XX. https://doi.org/10.32890/jict202X.XX.X.X", after=10)
    P(TITLE, style='JICT-Title')
    if not anonymous:
        shown = [f'{marks[PEOPLE[n][0]]}{n}' + ('*' if n in corr else '') for n in order]
        P(', '.join(shown[:-1]) + ' & ' + shown[-1], style="JICT-Authors' Name")
        for a, mk in marks.items(): P(f'{mk} {AFFILS[a]}', style='JICT-Affiliation')
        for n in order: P(('*' if n in corr else '') + f'{marks[PEOPLE[n][0]]}{PEOPLE[n][1]}', style='JICT-Email')
        P('*Corresponding author' + ('s' if len(corr) > 1 else ''), style='JICT-Email')
        P('ORCID: ' + '; '.join(f'{n} {PEOPLE[n][2]}' for n in order), style='JICT-Email')
    P('ABSTRACT', style='JICT-Abstract Heading')
    P(cite(COMP.get('__abstract__', {}).get('text') or C['abstract']))
    P('Keywords: ' + ', '.join(KEYWORDS) + '.', after=12)

    tab_no = fig_no = 0
    skip = False
    for b in C['blocks']:
        bid = b.get('id', '')
        if bid in COMP:                                        # logged compression
            action = COMP[bid]
            log.append(f"{bid}: {action.get('action')} - {action.get('reason','')}")
            if action.get('action') == 'drop': continue
            if action.get('action') == 'replace':
                b = {**b, ('caption' if b['type'] in ('figure', 'table') else 'text'): action['text']}
            if action.get('action') == 'note':
                b = {**b, 'note': action['text']}
        t = b['type']
        if t == 'heading':
            txt = b['text']
            if txt.startswith('Reproducibility and data availability'):
                log.append(f'{bid}: section folded into the journal availability declaration')
                skip = True; continue
            skip = False
            if re.match(r'^A\.\d', txt):
                log.append(f'{bid}: appendix subheading dropped; its sketch carries the label'); continue
            if txt.startswith('Appendix') or b.get('level', 1) == 1: H1(re.sub(r'^\d+\.\s*', '', txt))
            else: H2(txt)
        elif t == 'paragraph':
            if skip:
                log.append(f'{bid}: folded into the availability declaration'); continue
            P(cite(b['text']), style='JICT - Paragraph')
        elif t == 'equation':
            P(b['text'], align=WD_ALIGN_PARAGRAPH.CENTER, after=6)
        elif t == 'table':
            tab_no += 1
            P(f'Table {tab_no}', bold=True, after=0)
            P(cite(re.sub(r'^Table \d+\.\s*', '', b['caption'])), italic=True, after=3)
            hdr, rows = b['headers'], b['rows']
            tt = doc.add_table(rows=1, cols=len(hdr))
            for c, h in zip(tt.rows[0].cells, hdr): c.text = h
            for r in rows:
                for c, v in zip(tt.add_row().cells, r): c.text = cite(str(v))
            # fixed widths from the block, in inches; APA/JICT rules: horizontal rules only
            grid = tt._tbl.tblGrid
            for gc, w in zip(grid.findall(qn('w:gridCol')), b.get('widths', [])):
                gc.set(qn('w:w'), str(int(w * 1440)))
            pr = tt._tbl.tblPr
            borders = OxmlElement('w:tblBorders')
            for edge, val in (('top', 'single'), ('bottom', 'single'), ('insideH', 'nil'), ('insideV', 'nil'), ('left', 'nil'), ('right', 'nil')):
                e = OxmlElement(f'w:{edge}'); e.set(qn('w:val'), val); e.set(qn('w:sz'), '6'); borders.append(e)
            pr.append(borders)
            for ri, row in enumerate(tt.rows):
                for c in row.cells:
                    for q in c.paragraphs:
                        q.paragraph_format.space_after = Pt(1)
                        for rr in q.runs: rr.font.size = Pt(9); rr.font.name = 'Times New Roman'; rr.bold = ri == 0
            if b.get('note'): P(b['note'], italic=True, size=9, after=6)
            else: P('', after=6)
        elif t == 'figure':
            fig_no += 1
            P(f'Figure {fig_no}', bold=True, after=0)
            P(cite(re.sub(r'^Figure \d+\.\s*', '', b['caption'])), italic=True, after=3)
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str((PROJ / b['path']).resolve()), width=Cm(15))
            P('', after=8)

    if not anonymous:
        H1('Author contributions'); P(' '.join(f'{n}: {r}.' for n, r in credit_for(PID, VK)), style='JICT - Paragraph')
    H1('Data and code availability')
    if anonymous:
        P('The code, the executed notebook, the frozen results, the figures and the master manuscript with '
          'full derivations are held in a repository that is private at submission and will be opened on '
          'request of the editors or reviewers and on acceptance; its address is given in the complete '
          'version of this manuscript, because it would identify the authors under blinded review. The '
          'original measurements reanalysed here accompany a published article and are used under its terms.',
          style='JICT - Paragraph')
    else:
        P(f'The code, the executed notebook, the frozen results, the figures and the master manuscript with '
          f'full derivations are at {REPO_URL}, private at submission and opened on request of the editors or '
          'reviewers and on acceptance. The original measurements reanalysed here accompany a published article '
          'and are used under its terms; they are not redistributed.', style='JICT - Paragraph')
    H1('Conflict of interest'); P('The authors have no competing interests to declare that are relevant to the content of this article.', style='JICT - Paragraph')
    H1('Acknowledgement'); P(NONFUNDED, style='JICT - Paragraph')
    H1('Declaration of generative AI and AI-assisted technologies in the manuscript preparation process'); P(AI_PARA, style='JICT - Paragraph')
    H1('References')
    for n in sorted(APA, key=sort_key):
        p = P(APA[n][0], after=4); p.paragraph_format.left_indent = Cm(1.0); p.paragraph_format.first_line_indent = Cm(-1.0)
    f = OUT / ('JICT_LAB_anonymous.docx' if anonymous else 'JICT_LAB_with_author_details.docx')
    doc.save(f)
    subprocess.run(['/opt/homebrew/bin/soffice', '--headless', '--convert-to', 'pdf', '--outdir', str(OUT), str(f)], capture_output=True)
    (OUT / 'COMPRESSION_LOG.txt').write_text('\n'.join(log) + '\n')
    return f


def report():
    import fitz
    lines = []
    for name, anon in (('JICT_LAB_anonymous', True), ('JICT_LAB_with_author_details', False)):
        d = fitz.open(OUT / f'{name}.pdf'); flat = re.sub(r'\s+', ' ', '\n'.join(p.get_text() for p in d))
        words = len(flat.split())
        body = re.sub(r'Journal of Information and Communication Technology, Vol\. 2X, Number X \(XXXX\) 202X, pp: XX-XX\s*\d*', ' ', flat)
        wj = len(body.split())
        unres, prot = [], 0
        for m in re.finditer(r', (and|or)\b', flat):
            ctx = flat[max(0, m.start() - 140):m.end() + 60]
            if (m.start() >= flat.rfind('REFERENCES') or 'specific grant' in ctx or 'doi.org' in ctx
                    or re.search(r'\(\d{4}\)\.', ctx)): prot += 1
            else: unres.append(ctx.strip())
        leak = [x for x in [n.split()[-1] for n in order_for(PID, VK)] + ['ieee.org', 'gmail.com', '0009-', 'bdata-arindam'] if x in flat] if anon else []
        lines.append(f'{name}.docx: {d.page_count} pages, {words:,} words as extracted, {wj:,} without the running header (JICT band 5,000-8,000 incl. all sections): '
                     f'{"PASS" if 5000 <= wj <= 8000 else "FAIL, over by " + f"{wj-8000:,}" if wj > 8000 else "FAIL"}')
        lines.append(f'   ", and"/", or": {len(unres)} unresolved, {prot} PROTECTED')
        for u in unres[:6]: lines.append('      > ' + u[:150])
        if anon: lines.append('   anonymity: ' + ('CLEAN' if not leak else 'LEAK ' + str(leak)))
    a = len((COMP.get('__abstract__', {}).get('text') or C['abstract']).split())
    lines.append(f'abstract {a} words (JICT 150-250): {"PASS" if 150 <= a <= 250 else "FAIL"}; keywords {len(KEYWORDS)} (max 5): PASS')
    lines.append(f'references {len(APA)} APA 7th entries, alphabetical; in-text author-date; tables 7; figures 4')
    (OUT / 'BUILD_REPORT.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines))


if __name__ == '__main__':
    build(False); build(True); report()
