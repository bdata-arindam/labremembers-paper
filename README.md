# When the Lab Remembers: Identifiability and budgeted confirmation of materials recipes

**Authors** Arindam Chakraborty, Sambit Dhar, Soham Marik, Surajit Sinha

**Affiliations** Arindam Chakraborty (Independent Researcher, Leander, TX, United States); Sambit Dhar (Independent Researcher, Little Rock, Arkansas, United States); Soham Marik (Independent Researcher, Leander, TX, United States); Surajit Sinha (Independent Researcher, Leander, TX, United States)

**Corresponding authors** Arindam Chakraborty, Sambit Dhar, Soham Marik

**ORCID** Arindam Chakraborty 0009-0001-8152-5508; Sambit Dhar 0009-0001-3694-5589; Soham Marik 0009-0004-2308-9631; Surajit Sinha 0009-0003-1222-8096

**Submitted to** F1000Research (Taylor & Francis), open post-publication peer review

**CRediT** Arindam Chakraborty: Conceptualization; Methodology, Formal Analysis. Sambit Dhar: Formal analysis, editing. Soham Marik: Methodology; Investigation; Formal analysis; Writing-Edits. Surajit Sinha: Investigation; Validation, Writing - Edits.

**Funding** No funding was received for conducting this study.

**Competing interests** The authors have no competing interests to declare that are relevant to the content of this article.

**Ethics** No institutional determination applies to this study.

**Rights** Article under Creative Commons Attribution (CC BY 4.0). Code in this repository under the MIT licence (LICENSE); scored results and extracted tables under CC BY 4.0 (results/LICENSE.txt).

This repository is public, as F1000Research requires of underlying data and code before submission; the version underlying the article is archived at Zenodo under the DOI given in the article’s availability statements.

## What the work is

The abstract of the submitted manuscript, in the authors' own words:

Preparation history can make the material measured in an autonomous campaign differ from its recorded recipe. We study confirmation of one frozen recipe under independent fresh preparation. A finite-data analysis distinguishes underdetermination without quantitative regularity from sharp response envelopes under a known Lipschitz bound; a mass-balance memory model yields a contraction-based preparation-bias bound and a conditional fixed-final confidence interval; an exchange argument establishes stronger-wash-first ordering for fixed action counts and enumeration minimizes interval width within a restricted equally weighted preparation menu. Reanalysing original organic-photovoltaic measurements finds 10 threshold disagreements among 240 paired formulations at an illustrative absorbance-loss criterion, without establishing carryover causality. A preserved synthetic benchmark of 48,000 policy runs does not demonstrate superiority of an adaptive heuristic over same-model repetition. A separate extension of 62,400 runs with two measured-data-informed response emulators shows the planner improving true-acceptance yield over costly fresh-only measurement by 3.5 and 4.0 percentage points in high-carryover cases but losing 3.0 points to fixed burn-in/tail repetition when washing is ineffective; strong persistent-memory stress produces 12 false acceptances in 200 campaigns for the misspecified adaptive model and finite observed coverage falls below nominal 95% in some controls. Emulator test errors are moderate and its certificates do not certify physical materials. The contribution is a reproducible conditional confirmation framework with explicit efficiency and failure boundaries; platform-specific carryover, response bounds and marginal costs still require experimental validation.

## What is in this repository

- `application/` the measured-data retrieval, extraction and reconfirmation code with its provenance records — 46 files, 3.1 MB
- `research/` the benchmark and extension code, the executed notebook and its recovery log — 81 files, 14.0 MB
- `protocols/` the evidence register, numeric audit, both writing-pass reviews and the independent notebook audit — 19 files, 1.0 MB
- `results/` the scored summaries of the v1 benchmark, the v2 extension, the measured pairs and the emulators — 47 files, 5.8 MB
- `figures/` the four figures as published — 4 files, 0.5 MB
- `manuscript/` both JICT files, the cover letter, the build report, the compression log and the master manuscript with full derivations — 13 files, 4.3 MB

The submitted manuscript is `manuscript/JICT_LAB_anonymous.pdf` for review, 17 pages, with `JICT_LAB_with_author_details.pdf` as the complete version. The appendix of the submitted text keeps each statement and a one-line proof sketch; `manuscript/master_when_the_lab_remembers_manuscript.pdf` carries the full derivations and `manuscript/COMPRESSION_LOG.txt` records every block condensed for the journal’s word band with its reason.

Raw run streams under research/notebook/runs stay in the working repository. What is carried here is the scored result a reader can check against the manuscript.

## Data provenance

The measured organic-photovoltaic data are the original workbook accompanying Langner et al. (2020), retrieved at a pinned repository commit with its SHA256 recorded in `application/original_repository_commit.json`; they are used under the published article’s terms and are not redistributed here. Every simulated quantity is labelled as such in the manuscript.

## Substitutions in this published copy

Paths naming the account on the build machine were replaced by `~/`. `protocols/PUBLISHED_COPY_SUBSTITUTIONS.txt` lists every rewrite.
