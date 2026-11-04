MEASURED OPV APPLICATION

This directory contains a secondary analysis of published measurements and
explicit response emulators. It does not contain newly synthesized materials
or an experimentally observed OPV carryover law.

Source and measurement
Langner et al., Beyond Ternary OPV: High-Throughput Experimentation and
Self-Driving Laboratories Optimize Multicomponent Systems, Advanced Materials
32, 1907801 (2020). https://doi.org/10.1002/adma.201907801

The response is relative spectral absorbance loss after 18 hours of roughly
one-sun illumination in ambient air. Lower values indicate greater film
photostability. This is not device efficiency. Inputs are four component mass
fractions summing to one: P3HT, PBQ-QF or PTB7-Th, PCBM and oIDTBR. Negative
source observations and all paired measurements are retained.

Exact numeric source
Repository: https://github.com/the-matter-lab/quaterny_opvs
Commit: 226c2f0df03a645166d793c4a4b76a4744af015e
File: experimental_data.xlsx
SHA256: 69ae8917cd63fe9391278df86722c0ebc2921af92dd1b27d9b957cb030a074ad
Expected size: 138962 bytes

Rebuild from the original source
Use Python with numpy, pandas, scipy and openpyxl installed. Run these commands
from the project root. They write derived files in this application directory.

  python application/retrieve_original_data.py
  python application/extract_measured_data.py
  python application/reconfirmation_analysis.py
  python application/validate_piecewise_affine.py
  python application/plot_piecewise_validation.py

The retrieval script pins the original commit and rejects a different hash.
If direct network access is restricted, obtain experimental_data.xlsx from
that pinned repository revision and place it here under the name
quaterny_opvs_experimental_data.xlsx. Verify its SHA256 before extraction.
The full project notebook also records the runtime and rebuild commands.

Files and distinctions
measured_observations_tidy.csv contains the 2562 source measurements.
measured_sda_replicate_pairs.csv contains all 240 source pairs with original
row IDs and campaign labels. The two HTE composition-means tables each have
1021 exact composition groups. Means are separate fitting targets, not
additional experimental observations.

measured_reconfirmation_summary.json describes threshold agreement at the
analysis criterion loss <= 0.10. There are 10 disagreements among 240 pairs.
Sample labels do not establish chronological order. A disagreement is not a
known false acceptance. The source lacks the preparation histories required
to identify carryover as a cause.

opv_piecewise_affine.py is the separately declared alternative response
emulator. piecewise_affine_validation.json reports composition-group holdout
coverage and errors. Its large exact-cell sensitivity bounds apply to the
ideal mathematical interpolant, with binary64 input means interpreted as
exact data. Floating-point evaluation approximates that interpolant. The
bounds do not certify the unknown physical material.

The primary cubic Bernstein emulator and controlled carryover simulations
live in research/v2. Synthetic memory added to a fitted response function
remains a simulation. The source measurements do not calibrate its retention,
washing, noise assumptions or relative action costs.

Rights and attribution
The source article has a verified CC BY-NC 4.0 record. The separate original
GitHub repository has no explicit license in the inspected metadata. We do
not assume that the article license automatically covers its workbook. The
workbook remains a research-use source download with unresolved separate
redistribution status. It is excluded from the public package in favor of
the pinned retrieval script. Clarify rights before redistributing its bytes.

The extraction scripts, new calculations, derived analysis tables and
emulators are clearly separated from original source material. No new license
notice for our code grants rights to the source workbook. The MIT notice in
the related Olympus repository does not establish an MIT license for this
original file. Derived tables retain source attribution and do not claim
exclusive ownership of the underlying published numerical facts.

DATA_PROVENANCE.txt contains full source locators, unit checks, replicate
structure, the Olympus metadata cross-check and licensing evidence. Its
original_download_manifest.json records the retrieval. Exact source bytes
were preserved unchanged during the research analysis.
