"""Build linked audit views from one study-specific evidence register.

Manual source, method and whole-text reviews precede this reconciliation.
This script does not infer authorship, invent missing declarations or turn
unperformed execution/presentation checks into completed work.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"


def read_json(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    p = ROOT / path
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def write_json(path, obj):
    (ROOT / path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def blockmap(document):
    return {b["id"]: b for b in document["blocks"]}


def text_fields(document):
    yield "ABSTRACT", document.get("abstract", "")
    for b in document["blocks"]:
        bid = b["id"]
        if b["type"] in {"paragraph", "heading"}:
            yield bid, b.get("text", "")
        if b["type"] in {"table", "figure"}:
            yield bid + ".CAPTION", b.get("caption", "")
            if b.get("note"):
                yield bid + ".NOTE", b["note"]
        if b["type"] == "table":
            for ri, row in enumerate(b["rows"], 1):
                for ci, value in enumerate(row, 1):
                    if isinstance(value, str):
                        yield f"{bid}.R{ri:02d}.C{ci:02d}", value


def style_counts(document):
    fields = list(text_fields(document))
    return {
        "comma_before_and": sum(t.count(", and") for _, t in fields),
        "comma_before_or": sum(t.count(", or") for _, t in fields),
        "locations": [{"id": i, "comma_before_and": t.count(", and"), "comma_before_or": t.count(", or")} for i, t in fields if ", and" in t or ", or" in t],
        "protected": "Equations, code, exact hashes, URLs, technical identifiers and official bibliographic titles are not rewritten by this prose scan."
    }


BASELINE_FINDINGS = {
    "P009": ("W3", "MAJOR", "the measured relative absorbance loss is d and the modeled score is f = 1 − d", "Observed loss and a fitted mean response were not distinguished explicitly.", "Define d_obs separately from the fitted mean-loss emulator g(x); the frozen target remains f(x*) = 1 − g(x*)."),
    "P026": ("W3", "MINOR", "f(x) = Σ|α|=p βαBᵖα(x)", "The inline plain-text basis notation was difficult to parse and its definition was incomplete at this location.", "Move the explicit standard basis and derivative to native display equations E09/E10 with Appendix A definitions."),
    "P034": ("W3", "MAJOR", "Every policy completes the same available budget", "A common cap was confused with equal realized spending despite discrete action costs.", "State equal budget caps with potentially different realized spending."),
    "P042": ("W4", "MINOR", "A simple Gaussian scale inferred from central differences would conceal these extremes", "This sounded like a tested claim about a fitted Gaussian procedure that was not evaluated.", "State only that a summary of central differences does not describe the observed extremes."),
    "P045": ("W3", "MINOR", "represents only a limited look-ahead", "The heuristic uses immediate predictive covariance and does not implement a future-state look-ahead.", "Describe the actual immediate covariance objective and its omitted future-state effects."),
    "P054": ("W3", "MINOR", "Six initial replicate assays per cell", "The proposed physical replication unit was ambiguous.", "Specify independently prepared specimens, one target assay per specimen, plus charged predecessor and separate selection-calibration work."),
    "PA08": ("W3", "MINOR", "∂ᵢf(x) = pΣ|γ|=p−1 βγ+eᵢBᵖ⁻¹γ(x)", "Compact inline derivative notation needed a reviewable display and complete basis definition.", "Native E09/E10 now state the basis and derivative; the tangent-gradient proof is retained."),
    "PA09": ("W3", "MINOR", "with c > 1 and no integer remainder", "The sufficient crossover formula divides by sigma; positive noise and admissible sample counts should be explicit.", "State sigma > 0 and integer n/c; use exact counts for remainder cases."),
    "PA10": ("W3", "MINOR", "For a truly passing target with margin", "The power statement requires a fixed sample count, positive sigma and a deterministic valid mean-bias bound.", "State these assumptions before the Gaussian power bound.")
}

PASS_B_FINDINGS = {
    "P036": ("W3", "MAJOR", "receives the same discovery history, frozen candidate and hidden starting line state", "This wording could imply the policy observes the latent state, contrary to the implementation.", "Separate shared observable discovery input from equal hidden simulator initialization."),
    "P052": ("W3", "MINOR", "retained-volume fraction", "The model uses fixed-final-mass normalization and composition mass fractions.", "Use retained-mixture mass fraction."),
    "P037": ("W3", "MINOR", "Eight physical scenarios", "The noun could blur simulated preparation parameters with measured physical scenarios.", "Use eight simulated preparation scenarios.")
}

NOTES = {
    "P001": "Concrete nominal-versus-actual preparation problem and frozen-target motivation.",
    "P002": "Published carryover precedents are cited without transferring their apparatus calibration.",
    "P003": "Contribution scope includes the preserved negative finding and excludes a new-material claim.",
    "P004": "Measured pairs, emulators and external physical context remain distinct evidence types.",
    "P005": "Prior history/carryover theory and post-selection conditioning limits are explicit.",
    "P006": "Neighboring methods are conceptual comparators rather than unperformed numerical reproductions.",
    "P007": "Established mathematical ideas receive attribution and the novelty claim is bounded.",
    "P008": "The optimization claim is restricted to a declared certified-width objective.",
    "P009": "Observed loss, modeled mean loss and the fresh score target are now distinct.",
    "P010": "Mixture state and retained fraction have a stated fixed-final-mass meaning.",
    "P011": "Retention law and composition-only history mechanism are explicitly assumptions.",
    "P012": "Sharp-envelope statement includes known actual locations and Lipschitz consistency.",
    "P013": "Sharpness proof is supplied; hidden-location relaxation is explicitly nonsharp.",
    "P014": "Smooth-bump argument is limited to a finite transcript and distinguishes global statistical identification.",
    "P015": "Contraction and bias recursion are linked to the stated state model.",
    "P016": "Simplex diameter, fresh-state behavior and external validity of bounds are explicit.",
    "P017": "The geometric-sum bound distinguishes discarded and retained measurements.",
    "P018": "Natural flushing explains the strong repeat control; post hoc tails need correction.",
    "P019": "Fixed schedule, independent Gaussian errors and known noise scale are stated.",
    "P020": "Wrong-decision probability is separated from false fraction among accepted candidates.",
    "P021": "Fixed-final inference and optional-stopping correction are distinguished.",
    "P022": "Calibration error and emulator discrepancy are not absorbed into a nominal interval.",
    "P023": "The scheduling class and common-memory exchange assumptions are explicit.",
    "P024": "Ordering proof, fresh-state isolation, block formula and tie rules describe the implementation.",
    "P025": "Restricted optimality excludes tail discarding, adaptive choices and general empirical superiority.",
    "P026": "The polynomial family and explicit basis definition are identifiable.",
    "P027": "The sensitivity certificate is limited to the constructed emulator and policy information boundary.",
    "P028": "Source conditions and extracted measured-record counts are independently checked.",
    "P029": "Fraction units, negative values, shared source observations and metadata discrepancies are retained.",
    "P030": "Descriptive paired disagreements are not causal carryover or false-acceptance estimates.",
    "P031": "Grouped split, forced vertices, validation selection and one test assessment are traceable.",
    "P032": "Alternative interpolation and unmatched validation coverage have explicit limits.",
    "P033": "The preserved benchmark's synthetic target, grid, discovery and resource scale are stated.",
    "P034": "Cost caps and realized spending are separated; the heuristic is not exact information gain.",
    "P035": "Counts, shared seeds and the chronology of the later extension are not exaggerated.",
    "P036": "Observable policy inputs and hidden simulator initialization are separately described.",
    "P037": "Scenario parameters and supplied external envelopes remain simulation assumptions.",
    "P038": "Thirteen controls, fixed-final counts and per-case pairing are explicit.",
    "P039": "Sensitivity choices were declared before report execution; invalid noise is labeled a stress.",
    "P040": "Metric denominators, Wilson intervals, paired bootstrap and multiplicity limits are stated.",
    "P041": "All measured-pair counts reconcile to the source export; causal overinterpretation is excluded.",
    "P042": "Extremes and heterogeneous paired variation are retained without unsupported mechanism attribution.",
    "P043": "The v1 adaptive method's lack of advantage over same-model repetition is stated directly.",
    "P044": "Nonlinear and severe cases retain adverse outcomes and finite uncertainty for zero events.",
    "P045": "Mechanistic interpretation is conditional and describes the actual myopic covariance utility.",
    "P046": "Moderate emulator test fidelity is compared with the criterion without claiming physical certainty.",
    "P046b": "Secondary model coverage and large sensitivity bounds are reported with comparison limits.",
    "P047": "All-valid candidate cases and the resulting invalid-candidate denominator problem are explicit.",
    "P047b": "Post-run negative-prediction counts are exact derived emulator results; measured negative changes are retained and physical validation is not claimed.",
    "P048": "Improvement against costly fresh controls is quantified without claiming repeat-control dominance.",
    "P048b": "A result unfavorable to the planner is retained and reconciled with restricted optimality.",
    "P048c": "Wide bounds and abstention are not described as successful discovery.",
    "P049": "Misspecified-model false acceptance is reported with all-campaign denominators and zero-event limits.",
    "P049b": "Finite observed coverage below nominal is retained; common-noise dependence is explained.",
    "P049c": "Bound and noise stresses keep their assumptions and do not retrospectively retune the study.",
    "P050": "Conditional cost, bias and sampling-noise tradeoffs are interpretation rather than physical advice.",
    "P051": "Reference preparation and unresolved outcomes define the scientific claim.",
    "P052": "Published catalyst contamination and cleaning duration remain separate from OPV parameter calibration.",
    "P053": "Measured batch throughput and treatment durations are not equated to marginal fresh cost.",
    "P054": "The 120-assay physical grid is a proposed pilot with separate selection-calibration costs.",
    "P055": "Prospective logs and randomization are necessary follow-up requirements, not completed steps.",
    "P056": "Apparatus-specific regularity and noise assumptions remain open physical questions.",
    "P057": "The central physical, calibration, model-discrepancy and multiple-candidate limits are stated.",
    "P058": "Shared source data, reused seeds, no external validation and nonexhaustive novelty search are visible.",
    "P059": "The conclusion remains a conditional computational framework with a physical-validation gap.",
    "PA01": "Finite Lipschitz cone-envelope proof is internally complete and attributed as classical.",
    "PA02": "Response-band envelope proof requires nonempty feasibility; hidden locations lose sharpness.",
    "PA03": "Smooth bump construction includes boundary and response-range qualifications.",
    "PA04": "State contraction, geometric sum and fresh-state semantics are algebraically consistent.",
    "PA05": "Triangle-inequality coverage proof includes uniformity over admissible bias sequences.",
    "PA06": "Finite-horizon and contiguous-window union bounds are separate from the implemented fixed-final experiment.",
    "PA07": "Exchange proof has common noise, additive costs and no additional sequence restrictions.",
    "PA08a": "Display equations define the standard Bernstein basis and its ambient derivative.",
    "PA08": "Tangent-gradient range proof yields an upper bound only for the mathematical emulator.",
    "PA09": "Crossover is a conservative fixed-assumption sufficient condition with explicit count and noise requirements.",
    "PA10": "Power bound conditions on fixed n and deterministic valid mean bias; it is not a physical pilot power calculation.",
    "PR01": "Execution and demonstration claims depend on actual saved notebook/parity records; prose clarity is separate from completion.",
    "PR02": "Pinned data identity, unresolved workbook rights and unknown author declarations are explicit."
}


def evidence_for(pid):
    common = []
    if pid.startswith("PA") or pid in {f"P{i:03d}" for i in range(9, 28)} or pid in {"P007", "P008", "P050", "P051", "P059"}:
        common += ["research/theory_note.md", "research/v2/confirmation_planner.py"]
    if pid in {"P028", "P029", "P030", "P041", "P042", "PR02"}:
        common += ["application/DATA_PROVENANCE.txt", "application/extraction_log.json", "application/independent_measured_analysis_audit.md", "application/measured_reconfirmation_summary.json"]
    if pid in {"P031", "P032", "P046", "P046b"}:
        common += ["research/v2/emulator_validation.json", "application/piecewise_affine_validation.json", "application/independent_measured_analysis_audit.md"]
    if pid in {f"P{i:03d}" for i in range(33, 36)} or pid in {"P043", "P044", "P045"}:
        common += ["research/protocol.json", "research/summary.json", "research/independent_audit.md"]
    if pid in {f"P{i:03d}" for i in range(36, 41)} or pid.startswith(("P047", "P048", "P049")):
        common += ["research/v2/protocol.json", "research/v2/summary.json", "audit/v2_output_audit.json", "research/v2/opv_confirmation.py"]
    if pid == "P047b":
        common += ["research/v2/candidate_prediction_audit.json", "research/v2/trial_results.csv", "application/measured_observations_tidy.csv", "audit/manuscript_numeric_audit.json"]
    if pid in {"P052", "P053"}:
        common += ["application/autofsp/provenance.json", "application/autofsp/carryover_measurements.csv", "application/autofsp/reported_resource_times.csv", "application/opv_resource_provenance.json", "application/opv_reported_resource_times.csv"]
    if pid in {"P054", "P055", "P056"}:
        common += ["application/physical_validation_plan.json"]
    if pid in {"P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008"}:
        common += ["sources.json", "related_work.md"]
    if pid in {"P057", "P058"}:
        common += ["research/v2/protocol.json", "application/DATA_PROVENANCE.txt", "audit/v2_output_audit.json"]
    return sorted(set(common))


def main():
    baseline_path = "authoring/pass_a_baseline.json"
    pass_a_path = "audit/manuscript_pass_a_reviewed.json"
    pass_b_path = "audit/manuscript_pass_b_reviewed.json"
    final_path = "authoring/manuscript_content.json"
    baseline = read_json(baseline_path)
    pass_a = read_json(pass_a_path)
    pass_b_initial = read_json(pass_b_path)
    final = read_json(final_path)
    bm, am, bi, fm = map(blockmap, (baseline, pass_a, pass_b_initial, final))
    sources = read_json("sources.json")["sources"]
    source_by_id = {s["id"]: s for s in sources}
    numeric_audit = read_json("audit/v2_output_audit.json")
    paragraphs = []
    changes = []
    for pid, b in fm.items():
        if b["type"] != "paragraph":
            continue
        assert pid in NOTES, f"A new substantive paragraph needs manual review: {pid}"
        old = bm.get(pid, {}).get("text")
        atext = am.get(pid, {}).get("text")
        btext = bi.get(pid, {}).get("text")
        findings = []
        for stage, mapping in [("BASELINE/PASS_A", BASELINE_FINDINGS), ("PASS_B_INITIAL", PASS_B_FINDINGS)]:
            if pid in mapping:
                flag, severity, excerpt, rationale, repair = mapping[pid]
                assert excerpt not in b["text"], (pid, "flagged wording remains")
                findings.append({"stage": stage, "flag": flag, "rating": "MEDIUM", "research_severity": severity, "excerpt": excerpt, "rationale": rationale, "repair": repair, "disposition": "RESOLVED", "check_status": "PASS"})
        paragraph = {
            "paragraph_id": pid, "claim_id": "CL-" + pid,
            "baseline_text": old, "pass_a_text": atext, "pass_b_initial_text": btext,
            "final_text": b["text"], "baseline_rating": "MEDIUM" if pid in BASELINE_FINDINGS else ("LOW" if old else "NOT_ASSESSABLE"),
            "final_rating": "LOW", "final_flags": [], "final_rationale": NOTES[pid],
            "research_severity_remaining": "MAJOR" if pid == "PR01" else "NONE",
            "remaining_evidence_status": "NOT_ASSESSED" if pid == "PR01" else "SUPPORTED",
            "scope_qualification": "PR01 fresh-kernel notebook completion requires its actual execution record; the full scientific text has been read." if pid == "PR01" else "Evidence supports the paragraph within its stated assumptions and exclusions.",
            "findings": findings, "evidence_paths": evidence_for(pid),
            "reference_style_comparison": "INDETERMINATE: no author-supplied matched human/AI reference anchors.",
            "writing_process": "AI_ASSISTED_RECORD_SUPPORTED; not inferred from style"
        }
        paragraphs.append(paragraph)
        if old != b["text"]:
            changes.append({"change_id": "CHG-" + pid, "location": pid, "original_meaning": old, "pass_a_wording": atext, "pass_b_initial_wording": btext, "final_wording": b["text"], "reason": [f["repair"] for f in findings] or ["Evidence-supported results insertion, scope clarification or source-context addition."], "evidence_paths": evidence_for(pid), "meaning_check": "PASS within stated scope"})

    access = {}
    for s in sources:
        rid = f"REF{s['id']:02d}"
        if s["id"] == 12:
            level, status = "METADATA_ONLY; original mathematical text blocked", "PARTIAL"
        elif s["id"] in {3, 5, 11, 13}:
            level, status = "RELEVANT_PRIMARY_TEXT_INSPECTED", "PASS"
        elif s["id"] == 1:
            level, status = "INDEXED_PRIMARY_SECTION/TABLE/STATEMENT_INSPECTED", "PARTIAL"
        else:
            level, status = "PRIMARY_ABSTRACT_OR_AUTHOR_RECORD_INSPECTED", "PARTIAL"
        access[rid] = {
            "reference_id": rid, "displayed_id": s["id"], "metadata": s,
            "metadata_identity_status": "PASS", "access_level": level,
            "full_text_access_status": status,
            "inspected_evidence": s.get("verified"), "access_limits": s.get("access_limits", "Do not infer inspection of full methods or supplements from abstract access."),
            "supported_use": s["supports"], "excluded_use": s["does_not_support"],
            "publication_status": s["status"], "is_preprint": s["is_preprint"],
            "exhaustive_correction_retraction_check": "NOT_CHECKED; current inspected publisher/author record only",
            "bibliography_match": "PASS: manuscript ID, DOI, title and publication identity matched to source catalog"
        }
    occurrences = []
    refs_seen = set()
    for loc, text in text_fields(final):
        for oi, match in enumerate(re.finditer(r"\[([1-9][0-9]*(?:\s*,\s*[1-9][0-9]*)*)\]", text), 1):
            ids = [int(x) for x in match.group(1).split(",")]
            for n in ids:
                assert n in source_by_id, (loc, n)
                refs_seen.add(n)
                start = max(text.rfind(". ", 0, match.start()) + 2, 0)
                if start == 1:
                    start = 0
                excerpt = text[start:match.end()]
                relation = "QUALIFIED_SUPPORT" if n == 12 else "DIRECT_SUPPORT"
                if n in {10, 13} and loc.startswith(("P021", "PA05", "PA06")):
                    relation = "BACKGROUND_ONLY"
                occurrences.append({
                    "citation_occurrence_id": f"CIT-{loc}-{oi:02d}-REF{n:02d}",
                    "location": loc, "paragraph_or_block_id": loc.split(".")[0],
                    "claim_id": "CL-" + loc.split(".")[0], "reference_id": f"REF{n:02d}",
                    "grouped_bracket": match.group(0), "local_claim_excerpt": excerpt,
                    "relationship": relation,
                    "support_status": "PARTIAL" if n == 12 else "PASS",
                    "support_scope": ("Historical attribution is metadata-supported with original text inaccessible; the actual envelope construction is proved in Appendix A and independently audited." if n == 12 else source_by_id[n]["supports"]),
                    "verification_level": "SOURCE" if n != 12 else "SOURCE_METADATA_PLUS_METHOD_PROOF",
                    "not_implied": source_by_id[n]["does_not_support"]
                })
    assert refs_seen == set(range(1, 14)), ("Uncited or missing reference", refs_seen)
    for ref in final["references"]:
        rid = int(re.match(r"\[(\d+)\]", ref).group(1))
        assert source_by_id[rid]["doi"] in ref
        assert source_by_id[rid]["title"] in ref

    equation_proofs = {
        "E01": ("State-model assumption", "P010/P011", "Assumed physical mechanism; mass balance verified in code, not physically calibrated."),
        "E02": ("Sharp real-valued Lipschitz target envelope", "PA01/PA02", "Known actual locations and L-consistent values; hidden-location version only conservative."),
        "E03": ("Exact state contraction", "PA04", "Candidate-only shared-line state equation; nonnegative r and lambda ranges."),
        "E04": ("Preparation-bias and state-distance recursion", "PA04", "Valid external retention upper bounds, replacement lower bound and Lipschitz L."),
        "E05": ("Geometric repeat/tail mean-bias bound", "PA04", "Constant q below one; use limiting geometric sum at q=1."),
        "E06": ("Conservative fixed-final confidence interval", "PA05/PA06", "New confirmation noise; fixed retained set; known independent Gaussian sigma; valid bias envelope."),
        "E07": ("Adjacent-swap bias-bound identity", "PA07", "Equal weights; common lambda lower bound; additive action costs; no extra sequence constraints."),
        "E08": ("Bernstein simplex L1 sensitivity certificate", "PA08", "Complete standard multinomial basis; mathematical emulator only."),
        "E09": ("Standard multinomial Bernstein basis", "PA08a/PA08", "All nonnegative multi-indices of total degree p."),
        "E10": ("Ambient polynomial derivative identity", "PA08a/PA08", "Derivative of E09; simplex tangent range used in E08.")
    }
    equations = [{"equation_id": eid, "claim_id": "CL-" + eid, "statement": fm[eid]["text"], "meaning": meaning, "proof_locations": proof, "assumptions": assumptions, "method_check": "PASS", "novelty": "Application/derivation of established mathematics; no first-ever theorem claim", "evidence_paths": ["research/theory_note.md", "research/v2/confirmation_planner.py", "research/v2/opv_bernstein.py"], "presentation_check": "NOT_CHECKED_BY_THIS_REVIEWER; root render review is separate"} for eid, (meaning, proof, assumptions) in equation_proofs.items()]

    measured = read_json("application/measured_reconfirmation_summary.json")
    v1 = read_json("research/summary.json")
    v2 = read_json("research/v2/summary.json")
    fidelity = read_json("research/v2/emulator_validation.json")
    artifacts = sorted(set([baseline_path, pass_a_path, pass_b_path, final_path, "sources.json", "research/theory_note.md", "research/independent_audit.md", "application/independent_measured_analysis_audit.md", "audit/v2_output_audit.json", "audit/manuscript_numeric_audit.json", "audit/notebook_independent_audit.json", "research/notebook/notebook_execution_validation.json", "research/notebook/latest_execution_manifest.json", "audit/build_evidence_register.py", "audit/check_v2_results.py", "audit/check_manuscript_numbers.py", "research/v2/trial_results.csv", "research/trial_results.csv", "research/v2/summary.json", "research/summary.json"] + [p for row in paragraphs for p in row["evidence_paths"]]))
    scope = {
        "id": "SCOPE_RECORD", "mode": "NEW", "publisher": "unknown; publisher-neutral master", "page_target": None,
        "primary_question": "How can one frozen materials recipe be confirmed under an independent reference preparation when shared-line carryover can distort subsequent assays?",
        "claim_under_examination": "Under declared response/state/noise bounds, a fixed finite preparation schedule can minimize the specified conservative final interval width within its declared menu. Physical usefulness is not established.",
        "contribution_type": ["Conditional methods derivation", "Restricted finite-menu schedule planner", "Preserved negative benchmark", "Secondary analysis of published measurements", "Measured-data-informed simulation"],
        "setting": "Synthetic ternary benchmark and two OPV formulation emulators, with separately described published catalyst carryover context.",
        "period": "Computational session 3 November 2026; OPV source publication 2020; original measurement dates not asserted.",
        "estimands": ["Fresh mean score of one frozen nominal candidate", "Per-campaign false acceptance and true acceptance yield", "Conditional decision rates with explicit denominators", "Coverage, radius, cost and estimation error"],
        "principal_data": ["Pinned original measured OPV workbook", "V1 frozen synthetic campaigns", "V2 separately frozen campaigns", "Published AutoFSP quantities used only as context"],
        "comparators": v2["number_of_methods"],
        "exclusions": ["No new physical synthesis", "No measured OPV carryover estimation", "No unqualified physical confidence certificate", "No universal active-policy superiority", "No new general extension or concentration theorem", "No exhaustive novelty proof", "No journal acceptance prediction"],
        "authorized_scope_evolution": "User authorized deeper contribution, materials application and stronger comparisons. The extension followed the v1 negative result and was frozen before its own report campaigns. The physical pilot remains a post-results proposal."
    }
    settings = {
        "mode": "NEW", "journal_style": "publisher-neutral", "page_target": "not supplied",
        "numeric_citations": "Stable source-catalog IDs 1–13; not renumbered by first appearance because no venue-specific rule was supplied.",
        "editable_prose_punctuation": "Remove literal comma-before-and/or patterns by grammatical restructuring; protect math, code, exact identifiers, URLs and official titles.",
        "external_similarity_report": "NOT_RUN; no service or report was authorized/provided",
        "external_AI_detector": "NOT_RUN; no detector score or authorship classification claimed",
        "reference_style_anchors": "NONE_SUPPLIED; comparison INDETERMINATE",
        "review_independence": "Separate AI review agent using shared project records, with independent algebra/arithmetic checks. Not external human peer review."
    }
    declarations = {
        "author_names_and_order": "UNKNOWN", "affiliations": "UNKNOWN", "corresponding_author": "UNKNOWN", "ORCIDs": "UNKNOWN",
        "human_author_contributions": "UNKNOWN", "funding": "UNKNOWN", "conflicts": "UNKNOWN", "author_approval": "NOT_PROVIDED",
        "venue_and_submission_requirements": "UNKNOWN", "permissions_for_public_redistribution_of_original_workbook": "NOT_ESTABLISHED",
        "known_AI_assistance": "ChatGPT, GPT-6 Astra Pro, in this session assisted concept/method development, code, analysis, prose, visuals and review.",
        "provenance_basis": "RECORD_SUPPORTED; known current session only. Unknown prior writing history is not inferred.",
        "validation_limit": "Executed code and AI review do not constitute human scientific approval, independent laboratory validation or independent-team replication.",
        "ethics_statement": "No new participant/animal experiment was performed in the recorded computational work. No formal exemption, approval or institutional declaration has been invented.",
        "source_separation": "Funding, affiliations, acknowledgments and conflict declarations from cited papers were not copied into this study."
    }
    guardrails = [
        ("G01", "NO UNDOCUMENTED FACTUAL ASSUMPTIONS", "PASS", "Unknown identities, venue, funding and rights remain unknown. Assumed physical/noise parameters are labeled."),
        ("G02", "KEEP SCIENTIFIC ASSUMPTIONS EXPLICIT", "PASS", "Fixed-final Gaussian inference, pathwise bias bounds, emulator-only regularity and uncalibrated physical envelopes are explicit."),
        ("G03", "PRESERVE THE RESEARCH SCOPE", "PASS", "Scope and authorized extension chronology are retained; no new laboratory experiment is implied."),
        ("G04", "EXCLUDE OFF-TOPIC AND DISPROPORTIONATE CONTENT", "PASS", "Related work, theory, measurements, comparison and physical plan serve frozen-recipe confirmation."),
        ("G05", "TRACE ADDITIONS AND LABEL INFERENCES", "PASS", "Results, equations, citations and interpretation are linked here to their exact artifacts. Physical follow-up is a proposal."),
        ("G06", "DO NOT INVENT OR REWRITE STUDY HISTORY", "PASS", "V1 negative evidence precedes v2 design; frozen v1 records are preserved. No external preregistration is claimed."),
        ("G07", "MATCH CLAIM STRENGTH TO EVIDENCE", "PASS", "Restricted optimality and conditional coverage are separated from physical validity and empirical superiority."),
        ("G08", "KEEP CONTRADICTIONS AND LIMITATIONS VISIBLE", "PASS", "Adaptive-method losses, planner losses to tail repetition, weak emulator fidelity, all-valid cases and observed coverage below nominal remain visible."),
        ("G09", "PREVENT PROJECT AND SOURCE CONTAMINATION", "PASS", "Measured workbook, source emulator predictions, synthetic carryover, source-author declarations and this study's outputs are separated."),
        ("G10", "REPORT ONLY DEMONSTRATED WORK", "PARTIAL", "Campaign computation and numerical audit completed; PR01 fresh-kernel notebook and final rendered-document checks await their actual execution records.")
    ]
    open_issues = [
        {"id": "OPEN-NOTEBOOK", "status": "NOT_CHECKED", "severity": "MAJOR", "location": "PR01", "issue": "Fresh-kernel fully executed notebook and exact re-execution record must be verified before claiming that deliverable complete.", "resolution": "Root to provide execution log/output and final notebook identity; review record then updated."},
        {"id": "OPEN-PRESENTATION", "status": "NOT_CHECKED", "severity": "MINOR", "location": "DOCX/PDF/slides", "issue": "Scientific text review is complete; rendered page, equation and final exported punctuation QA is owned by root and not yet merged here."},
        {"id": "OPEN-PHYSICAL", "status": "MISSING", "severity": "MAJOR", "location": "P054–P058", "issue": "No matched OPV carryover histories, externally valid physical sensitivity bounds or marginal intervention cost measurements. No physical intervention study was performed."},
        {"id": "OPEN-AUTHORS", "status": "MISSING", "severity": "MAJOR", "location": "PR02", "issue": "Human author identities/order, affiliations, contributions, funding, conflicts and final approval are not supplied."},
        {"id": "OPEN-VENUE", "status": "MISSING", "severity": "MINOR", "location": "SCOPE_RECORD", "issue": "Target venue, length/format, required statements and acceptance criteria have not been supplied."},
        {"id": "OPEN-WORKBOOK-RIGHTS", "status": "PARTIAL", "severity": "MINOR", "location": "PR02/REF11", "issue": "Article CC BY-NC 4.0 is recorded; a separate explicit original-workbook redistribution license was not established. Preserve attribution and pinned retrieval instructions."},
        {"id": "OPEN-REF12-ACCESS", "status": "PARTIAL", "severity": "MINOR", "location": "CIT-P007/ P013/ PA01 to REF12", "issue": "Original McShane mathematical text inaccessible; metadata and historical attribution checked. Current proof independently supplied and audited."},
        {"id": "OPEN-STATUS-SEARCH", "status": "NOT_CHECKED", "severity": "MINOR", "location": "REF01–REF13", "issue": "Current source identity/status inspected; no comprehensive retraction/correction database search or exhaustive novelty search completed."},
        {"id": "OPEN-COVERAGE", "status": "PARTIAL", "severity": "MAJOR", "location": "P049b/T07", "issue": "Finite empirical coverage is below nominal in some Gaussian controls, including 183/200 tail coverage. It is reported and a targeted noise-index check found no arithmetic defect. It must not be relabeled universal empirical coverage validation. This finite realization does not logically refute the conditional mathematical statement."},
        {"id": "OPEN-EXTERNAL-VALIDATION", "status": "NOT_ASSESSED", "severity": "MAJOR", "location": "P058", "issue": "No external-team or human laboratory replication; internal checks are not external validation."}
    ]
    closest = [
        {"refs": ["REF01", "REF02"], "existing": "Physical carryover and control validation in materials automation", "our_boundary": "These studies motivate apparatus-history controls but do not calibrate OPV parameters."},
        {"refs": ["REF03"], "existing": "Hysteresis/history-aware Bayesian response models", "our_boundary": "History-aware modeling itself is not the novelty; same-model repeat control is required."},
        {"refs": ["REF04"], "existing": "Causal design under treatment carryover", "our_boundary": "The frozen fresh-response estimand and imperfect-preparation bounds need their own explicit assumptions."},
        {"refs": ["REF05"], "existing": "Persistent laboratory state and physical diagnosis of wall-film carryover", "our_boundary": "Closest recent overlap; contribution cannot rest on state tracking or diagnosis. Cited as a preprint."},
        {"refs": ["REF06", "REF07", "REF08"], "existing": "Adaptive workflow state, quality oversight and process-variation modeling", "our_boundary": "Conceptual neighbors; not falsely labeled reproduced numerical baselines."},
        {"refs": ["REF09"], "existing": "Noisy experiment-planner benchmarking with synthetic and experimental emulators", "our_boundary": "Contribution is a scoped preparation-confirmation benchmark and analysis, not first use of emulation."},
        {"refs": ["REF10", "REF12", "REF13"], "existing": "Time-uniform inference, Lipschitz extension and bias-aware uncertainty", "our_boundary": "Elementary application/derivation with a restricted schedule planner; no new general theorem claimed."},
        {"refs": ["REF11"], "existing": "Measured quaternary OPV photostability and autonomous optimization", "our_boundary": "Reanalysis and fitted emulation; source data do not establish OPV carryover causality."}
    ]
    register = {
        "register_id": "LAB-REMEMBERS-EVIDENCE-V1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "governing_protocol": {"name": "DYNAMITE C Universal, merged version 5, 11 October 2026", "path": "../upload/Research_Paper_Master_Prompt(1).txt", "sha256": hashlib.sha256((ROOT.parent / "upload/Research_Paper_Master_Prompt(1).txt").read_bytes()).hexdigest(), "read_scope": "Complete uploaded prompt read; NEW workflow with records applied."},
        "status_vocabulary": {"claim_states": ["SUPPORTED", "CONFLICTING", "MISSING", "NOT_ASSESSED", "NOT_APPLICABLE"], "check_states": ["PASS", "FAIL", "PARTIAL", "BLOCKED", "NOT_CHECKED", "NOT_APPLICABLE"], "verification_levels": ["INTERNAL", "ARITHMETIC", "SOURCE", "METHOD", "EXECUTION", "EXTERNAL_VALIDATION", "PRESENTATION"]},
        "scope_record": scope, "settings": settings, "author_declarations": declarations,
        "review_versions": {"first_assembled_baseline": {"path": baseline_path, "sha256": sha(baseline_path), "note": "Retained layout-stage first prose draft; temporary layout abstract and incomplete temporary bibliography are not scientific final text."}, "pass_a_reviewed": {"path": pass_a_path, "sha256": sha(pass_a_path)}, "pass_b_initial_reviewed": {"path": pass_b_path, "sha256": sha(pass_b_path)}, "pass_b_final_text": {"path": final_path, "sha256": sha(final_path)}},
        "review_coverage": {"pass_a": "Whole first assembled substantive text read; scientific/editorial findings recorded and repaired.", "pass_b": "Whole first 132-block final candidate, abstract and 13-reference bibliography read. Three localized wording repairs, the F04 overlap clarification and the later P047b post-run audit paragraph were separately read and verified against exact evidence.", "final_block_count": len(final["blocks"]), "paragraph_count_final": len(paragraphs), "equation_count": len(equations), "reference_count": len(sources), "citation_relationship_count": len(occurrences), "no_authorship_classifier": True},
        "sections": [{"section_id": b["id"], "title": b["text"], "level": b.get("level")} for b in final["blocks"] if b["type"] == "heading"],
        "paragraph_screen": paragraphs, "change_trace": changes,
        "claims": [{"claim_id": "CL-" + p["paragraph_id"], "locations": [p["paragraph_id"]], "statement": p["final_text"], "status": p["remaining_evidence_status"], "qualification": p["scope_qualification"], "evidence_paths": p["evidence_paths"], "citation_occurrences": [o["citation_occurrence_id"] for o in occurrences if o["paragraph_or_block_id"] == p["paragraph_id"]]} for p in paragraphs],
        "equations": equations,
        "algorithms": [{"algorithm_id": "ALG-ACTIVE", "description": "Immediate squared predictive covariance divided by prospective variance and cost; a moment-based heuristic.", "status": "SUPPORTED", "paths": ["research/lab_memory.py", "research/v2/opv_confirmation.py"], "limits": "Not exact expected information gain, no multistep state-value planning and no guaranteed empirical superiority."}, {"algorithm_id": "ALG-BOUNDED-PLAN", "description": "Enumerate feasible candidate-only action counts; stronger wash first for shared actions; fresh last; minimize fixed-final bound radius.", "status": "SUPPORTED", "paths": ["research/v2/confirmation_planner.py", "research/theory_note.md"], "limits": "Finite menu, equal weights and all included observations; tail or general adaptive policies excluded."}],
        "experiments": [{"experiment_id": "EXP-V1", "type": "synthetic", "execution": "PASS", "campaigns": 4800, "policy_runs": 48000, "record": "research/summary.json", "audit": "research/independent_audit.md"}, {"experiment_id": "EXP-MEASURED-PAIRS", "type": "secondary descriptive analysis", "execution": "PASS", "pairs": 240, "record": "application/measured_reconfirmation_summary.json", "audit": "application/independent_measured_analysis_audit.md"}, {"experiment_id": "EXP-EMULATOR", "type": "grouped held-out fitting", "execution": "PASS", "record": "research/v2/emulator_validation.json", "audit": "application/independent_measured_analysis_audit.md"}, {"experiment_id": "EXP-V2", "type": "measured-data-informed simulation", "execution": "PASS", "main_campaigns": 3200, "sensitivity_campaigns": 1600, "policy_runs": 62400, "record": "research/v2/summary.json", "audit": "audit/v2_output_audit.json"}, {"experiment_id": "EXP-PHYSICAL-PROPOSAL", "type": "proposed 120-target-assay pilot", "execution": "NOT_CHECKED", "record": "application/physical_validation_plan.json", "qualification": "Not performed; selection calibration and predecessor preparations require additional charged work."}],
        "results": [{"result_id": "RES-PAIRS", "status": "SUPPORTED", "locations": ["T02", "P041", "P042", "F01"], "values": measured, "verification": "ARITHMETIC", "limits": "Finite-source descriptive agreement; no causal carryover, true false acceptance or population confidence claim."}, {"result_id": "RES-V1", "status": "SUPPORTED", "locations": ["T03", "P043", "P044", "P045"], "artifact": "research/summary.json", "key_claim": "Adaptive confirmation did not demonstrate superiority over same-model repetition.", "verification": "ARITHMETIC_AND_METHOD"}, {"result_id": "RES-FIDELITY", "status": "SUPPORTED", "locations": ["T04", "P046", "P046b", "F02"], "values": fidelity, "secondary_artifact": "application/piecewise_affine_validation.json", "limits": "Emulator fidelity and sensitivity are not physical validation; holdout protocols differ."}, {"result_id": "RES-V2", "status": "SUPPORTED", "locations": ["T05", "T06", "P047", "P048", "P048b", "P048c", "P049", "P049c", "F03", "F04"], "artifact": "research/v2/summary.json", "audit": "audit/v2_output_audit.json", "verification": "ARITHMETIC_AND_METHOD", "limits": "Per-case comparisons; supplied bounds and synthetic carryover; many all-valid candidates; no pooled independent material replication."}, {"result_id": "RES-COVERAGE", "status": "CONFLICTING", "locations": ["T07", "P049b"], "values": numeric_audit["empirical_coverage_validation"], "qualification": "Finite empirical coverage does not uniformly attain nominal 95%; conditional mathematical proof and arithmetic checks are distinct evidence."}],
        "tables_and_figures": [{"id": b["id"], "type": b["type"], "caption": b.get("caption"), "data_check": "PASS", "presentation_check": "NOT_CHECKED_BY_THIS_REVIEWER; root rendering record pending", "source_path": b.get("path")} for b in final["blocks"] if b["type"] in {"table", "figure"}],
        "citation_occurrences": occurrences, "references": access, "closest_work_matrix": closest,
        "guardrails": [{"id": i, "rule": name, "status": status, "basis": basis} for i, name, status, basis in guardrails],
        "punctuation_checks": {"baseline": style_counts(baseline), "pass_a_snapshot": style_counts(pass_a), "pass_b_final_source": style_counts(final), "post_render": "NOT_CHECKED; root export review pending"},
        "execution_and_arithmetic_audit": numeric_audit,
        "artifact_inventory": [{"path": p, "sha256": sha(p), "present": (ROOT / p).exists()} for p in artifacts],
        "open_issues": open_issues,
        "overall_assessment": {"scientific_text_review": "COMPLETE_WITH_STATED_SOURCE_ACCESS_LIMITS", "numerical_output_reconciliation": "PASS_WITH_SCOPED_CHECKS", "empirical_coverage_validation": "PARTIAL", "physical_validation": "NOT_PERFORMED", "human_author_approval": "NOT_PROVIDED", "submission_readiness": "NOT_READY_FOR_SUBMISSION", "journal_strength": "A defensible computational methods/failure-analysis draft with measured-data context. Physical usefulness, external validation and sufficient venue-specific originality remain unresolved; no acceptance guarantee or first-ever claim."}
    }
    # Integrate completed dependencies from their actual receipts. These are
    # separate verification levels, not an upgrade to physical validity.
    notebook_audit = read_json("audit/notebook_independent_audit.json")
    layout = read_json("audit/final_layout_review.json")
    numeric_text = read_json("audit/manuscript_numeric_audit.json")
    slide_receipt_path = "authoring/presentation_v2_qa/when_the_lab_remembers_presentation_v2.validation.json"
    slides = read_json(slide_receipt_path)
    assert notebook_audit["status"] == "PASS" and all(notebook_audit["checks"].values())
    assert layout["source_sha256"] == sha(final_path) == numeric_text["manuscript_sha256"]
    assert layout["docx_sha256"] == sha("output/when_the_lab_remembers_manuscript.docx")
    assert layout["pdf_sha256"] == sha("output/when_the_lab_remembers_manuscript.pdf")
    assert slides["finalSha256"] == sha("output/when_the_lab_remembers_presentation_v2.pptx")
    assert layout["visual_review"]["pages_inspected_after_final_render"] == list(range(1, 19))
    assert layout["punctuation_checks"]["docx_comma_before_and_or"] == 0
    assert layout["punctuation_checks"]["pdf_comma_before_and_or"] == 0
    register["governing_protocol"]["path"] = "audit/user_research_paper_master_prompt.txt"
    assert sha(register["governing_protocol"]["path"]) == register["governing_protocol"]["sha256"]
    register["notebook_execution_verification"] = notebook_audit
    register["notebook_log_recovery"] = read_json("research/notebook/reconfirmation_log_recovery.json")
    register["manuscript_numeric_verification"] = numeric_text
    register["presentation_verification"] = {
        "manuscript": layout,
        "presentation": {"receipt_path": slide_receipt_path, "sha256": slides["finalSha256"], "slide_count": 12, "layout_warning_count": slides["presentationLayout"]["warning_count"], "native_chart_count": 3, "native_table_count": 7, "visual_review": "All 12 slides inspected and accepted by the root/deck agents; see editorial_audit.json.", "editorial_record": "authoring/presentation_v2_qa/editorial_audit.json", "native_powerpoint_application_opened": False, "verification_scope": "Rendered previews, package structure and source-data reconciliation; not a native PowerPoint application test."}
    }
    register["resolved_completion_dependencies"] = [
        {"id": "OPEN-NOTEBOOK", "status": "PASS", "basis": "Actual 17-cell fresh-kernel notebook inspected. Counts 1–17, no errors, 67 unchanged inputs, 13 successful logged commands and six byte-identical reproduced CSVs. Recovered one empty log exactly from captured notebook streams with matching original hash; recovery receipt retained."},
        {"id": "OPEN-PRESENTATION", "status": "PASS", "basis": "Root final 18-page inspection receipt matches source, DOCX and PDF hashes. All tables/equations/figures inspected; exported punctuation and page-boundary checks clear. Final 12-slide package matches its named validation receipt."}
    ]
    register["open_issues"] = [issue for issue in register["open_issues"] if issue["id"] not in {"OPEN-NOTEBOOK", "OPEN-PRESENTATION"}]
    for p in register["paragraph_screen"]:
        if p["paragraph_id"] == "PR01":
            p["research_severity_remaining"] = "NONE"
            p["remaining_evidence_status"] = "SUPPORTED"
            p["scope_qualification"] = "The actual fresh-kernel notebook and command/result records have been independently inspected; internal execution is not external physical validation. The later P047b audit is separately executed post-run analysis."
            p["evidence_paths"] += ["audit/notebook_independent_audit.json", "research/notebook/notebook_execution_validation.json", "research/notebook/latest_execution_manifest.json", "research/notebook/reconfirmation_log_recovery.json"]
    for c in register["claims"]:
        if c["claim_id"] == "CL-PR01":
            c["status"] = "SUPPORTED"
            c["qualification"] = "Actual execution and exact reproduction inspected; no external validation inferred."
            c["evidence_paths"] += ["audit/notebook_independent_audit.json", "research/notebook/latest_execution_manifest.json"]
    register["claims"].append({"claim_id": "CL-ABSTRACT", "locations": ["ABSTRACT"], "statement": final["abstract"], "status": "SUPPORTED", "qualification": "Abstract condenses the same conditional derivations and audited results; no physical validation or universal method superiority claimed.", "evidence_paths": ["research/theory_note.md", "research/summary.json", "research/v2/summary.json", "application/measured_reconfirmation_summary.json", "audit/manuscript_numeric_audit.json"]})
    for b in final["blocks"]:
        if b["type"] in {"table", "figure", "equation"}:
            register["claims"].append({"claim_id": "CL-"+b["id"], "locations": [b["id"]], "statement": b.get("caption", b.get("text", "")), "status": "SUPPORTED", "qualification": "Mathematical and numerical meaning checked within declared assumptions; equation rendering checked by root.", "evidence_paths": ["audit/manuscript_numeric_audit.json", "audit/final_layout_review.json"] if b["type"] != "equation" else ["research/theory_note.md", "audit/final_layout_review.json"]})
    for equation in register["equations"]:
        equation["presentation_check"] = "PASS: root inspected final rendered native equation; final_layout_review.json matches output hashes"
    for block in register["tables_and_figures"]:
        block["presentation_check"] = "PASS: root final-page inspection; attributed to root, not a separate visual inspection by this reviewer"
    for guardrail in register["guardrails"]:
        if guardrail["id"] == "G10":
            guardrail["status"] = "PASS"
            guardrail["basis"] = "Actual campaign execution, fresh-kernel notebook, output reconciliation and final rendering are documented. Physical trials, external validation and unknown author declarations are explicitly not claimed."
    for result in register["results"]:
        if result["result_id"] == "RES-COVERAGE":
            result["status"] = "SUPPORTED"
            result["qualification"] = "Observed finite coverage shortfall is supported. Empirical nominal-coverage validation remains PARTIAL; the observation does not logically refute the stated conditional mathematical result."
    register["results"].append({"result_id": "RES-CANDIDATE-SIGN", "status": "SUPPORTED", "locations": ["P047b"], "artifact": "research/v2/candidate_prediction_audit.json", "verification": "ARITHMETIC", "audit": "audit/manuscript_numeric_audit.json", "chronology": "Post-run descriptive audit of existing frozen predictions; zero new campaigns and no retuning.", "limits": "Negative emulator predictions help explain easy-case prevalence but are not measured physical stability. Negative measured changes also occur in the retained source."})
    register["punctuation_checks"]["post_render"] = {"status": "PASS", "docx_comma_before_and": 0, "docx_comma_before_or": 0, "pdf_comma_before_and": 0, "pdf_comma_before_or": 0, "basis": "Root final extraction checks; see final_layout_review.json. Historical quoted drafts and source records are preserved."}
    register["overall_assessment"]["notebook_completion"] = "PASS: actual fully executed notebook with exact experiment reproduction"
    register["overall_assessment"]["document_and_slide_presentation"] = "PASS_FOR_RECORDED_CHECKS"
    final_artifacts = ["audit/user_research_paper_master_prompt.txt", "audit/final_layout_review.json", "research/notebook/reconfirmation_log_recovery.json", "research/notebook/when_the_lab_remembers_executed.ipynb", "research/notebook/when_the_lab_remembers_executed.html", "output/when_the_lab_remembers_manuscript.docx", "output/when_the_lab_remembers_manuscript.pdf", "output/when_the_lab_remembers_presentation_v2.pptx", slide_receipt_path, "authoring/presentation_v2_qa/editorial_audit.json", "research/v2/candidate_prediction_audit.json", "audit/check_notebook_execution.py", "journal_readiness.md"]
    for p in final_artifacts:
        register["artifact_inventory"].append({"path": p, "sha256": sha(p), "present": (ROOT/p).exists()})
    claim_ids = {c["claim_id"] for c in register["claims"]}
    assert all(c["claim_id"] in claim_ids for c in register["citation_occurrences"])
    write_json("audit/evidence_register.json", register)
    write_json("audit/PROJECT_SETTINGS.json", {"source_register": "evidence_register.json", **settings})
    profile = {"profile_name": "DYNAMITE_C_PROFILE", "version": 1, "purpose": "Reusable review rules only; study facts live in evidence_register.json.", "modes": ["NEW", "REVISE", "FINAL"], "required_records": ["SCOPE_RECORD", "stable IDs", "claims/equations/results/citations", "Pass A and Pass B", "paragraph screen", "open issues"], "claim_states": register["status_vocabulary"]["claim_states"], "check_states": register["status_vocabulary"]["check_states"], "verification_levels": register["status_vocabulary"]["verification_levels"], "guardrails": [{"id": i, "rule": name} for i, name, _, _ in guardrails], "citation_rules": "Verify each occurrence; separate metadata, access and support; preserve preprint status and limitations.", "provenance_rule": "Known assistance records do not classify authorship or predict detector scores.", "punctuation_rule": settings["editable_prose_punctuation"], "completion_rule": "Report only actually executed or inspected work; submission readiness is distinct from review completion.", "adapter_status": "A JSON manuscript register adapter was executed on this study. No universal conversion adapter is claimed."}
    write_json("audit/DYNAMITE_C_PROFILE.json", profile)

    with (AUDIT / "paragraph_screen.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["paragraph_id", "baseline_rating", "final_rating", "research_severity_remaining", "remaining_evidence_status", "final_rationale"])
        writer.writeheader()
        for p in paragraphs:
            writer.writerow({k: p[k] for k in writer.fieldnames})
    with (AUDIT / "citation_occurrences.csv").open("w", newline="") as stream:
        fields = ["citation_occurrence_id", "location", "reference_id", "relationship", "support_status", "local_claim_excerpt", "support_scope", "not_implied"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in occurrences:
            writer.writerow({k: row[k] for k in fields})
    author_text = "# Author-facing declarations and settings\n\nThis view is generated from `audit/evidence_register.json`. It is a completion record, not a declaration that unknown facts have been confirmed.\n\n## Known assistance\n\n" + declarations["known_AI_assistance"] + " " + declarations["validation_limit"] + " No external similarity or AI-detector service was run. No detector score or authorship probability is asserted.\n\n## Information requiring the human authors\n\n"
    for key in ["author_names_and_order", "affiliations", "corresponding_author", "ORCIDs", "human_author_contributions", "funding", "conflicts", "author_approval", "venue_and_submission_requirements", "permissions_for_public_redistribution_of_original_workbook"]:
        author_text += f"- **{key.replace('_', ' ').capitalize()}:** {declarations[key]}.\n"
    author_text += "\n## Manuscript settings\n\nThe manuscript is a new publisher-neutral draft. No page target or venue format was supplied. Numeric citations retain stable IDs 1–13. Editable prose removes comma-before-and/or patterns while protecting equations, code, official titles, identifiers and exact provenance strings. Source-author affiliations, funding and acknowledgments are not this study's declarations.\n\n## Readiness\n\nThe computational findings and manuscript can be reviewed now. Submission readiness remains incomplete because author declarations and approval are missing, the target venue is unknown and the proposed physical validation has not occurred. The original workbook's separate redistribution status also requires clarification before including it in a public release. A guaranteed journal acceptance or an extremely uncommon first-ever contribution is not established by this review.\n"
    (AUDIT / "author_facing_declarations.md").write_text(author_text)
    report = f"""# Linked scientific and manuscript review

The authoritative study-specific record is `audit/evidence_register.json`; the CSV, settings and declaration files are views of that record. This report concerns source text, methods, saved numerical outputs and the completed execution/presentation receipts. It distinguishes every verification scope from physical validation.

## Review coverage

Mode: NEW. The retained first assembled draft has SHA256 `{sha(baseline_path)}`. The final reviewed manuscript source has SHA256 `{sha(final_path)}`. The whole scientific text, abstract and 13-reference bibliography were read. The final paragraph screen covers {len(paragraphs)} substantive paragraphs; all ten displayed equations were checked. There are {len(occurrences)} separately assessed citation/reference relationships, including split grouped citations. No matched writing-style reference anchors were supplied, so reference-style comparison is indeterminate. Current AI assistance is known from the work record rather than inferred from prose.

## Repairs recorded across both passes

Pass A separated noisy measured loss from the fitted mean target, corrected equal-budget language, clarified replication units and added missing assumptions to the crossover and power statements. It also replaced an unperformed Gaussian-method implication and made the immediate covariance heuristic precise. The Bernstein basis and derivative now have explicit display equations. Pass B separated hidden simulator state from observable policy inputs, corrected retained volume to retained-mixture mass and labeled the scenario set as simulated. The detailed before/after record uses stable paragraph IDs in the register.

## Mathematical and numerical result

The cone-envelope proof, contraction recurrence, preparation-bias bound, fixed-final confidence interval, finite-count ordering argument and Bernstein tangent-gradient bound are internally consistent under their stated assumptions. These are applications and model-specific derivations of established ideas. The schedule minimizes the declared conservative radius in a finite equally weighted action class; it is not a general adaptive optimum. Tail averaging remains a valid competing design outside that class.

The v2 independent output audit reconciled 62,400 saved rows, 97 structural/hash checks, 4,736 rate/denominator/Wilson calculations, 3,232 means and 1,248 paired point estimates. The largest continuous discrepancy was 2.22e−16. All inspected frozen source hashes matched. No evaluation seed was added or retuned by this review. The paired-bootstrap mechanism was checked; every bootstrap random realization was not independently recomputed.

Observed 95% interval coverage is not uniformly 95% in the finite simulation. In the no-carryover PBQ case, the fixed tail control covers 183/200 targets: 91.5% with Wilson interval 86.81%–94.63%. Fresh-only covers 186/200. Reconstructing the already-used noise draws reproduces the tail's 17 misses with no index or mean-denominator discrepancy. Common noise across cases prevents treating repeated shortfalls as independent replications. This result remains a substantive limitation of empirical coverage validation; arithmetic PASS is not a universal coverage-validation PASS.

## Source support and novelty limits

All 13 reference identities are linked to the manuscript. Relevant primary text was inspected for hysteresis, VERID, Langner and bias-aware inference. Other claims use primary abstracts or indexed primary sections and are limited to what those support. The original McShane text remained inaccessible; metadata and historical attribution are checked and the current envelope proof is supplied explicitly. No uninspected theorem number is attributed to it. A comprehensive correction/retraction database check and exhaustive novelty search were not performed.

VERID is a particularly close preprint: persistent laboratory state and causal diagnosis of wall-film carryover already exist. The contribution must therefore rest on the explicitly defined fresh-response task, conditional bound/planner analysis, strong controls and transparent failure findings. No first-ever general theorem or experimentally validated materials discovery is claimed.

## Remaining completion and submission issues

The actual fresh-kernel notebook contains 17 executed code cells with counts 1–17 and no error or unexecuted cells. Its 67 recorded inputs remain unchanged; all six compared raw/summary CSVs are byte-identical to the frozen records after 48,000 v1 and 62,400 v2 policy runs. One retained command log was initially empty. Its exact 1,254 original bytes were recovered from captured notebook stdout, matching the original manifest hash; the recovery and empty observation are preserved. The late P047b negative-prediction audit is explicitly separate post-run analysis of existing results, not an invented original notebook output.

Root's final review covers all 18 manuscript pages and all 12 presentation slides. The matched manuscript outputs contain seven native tables, ten native equations, four figures and 13 references. The final source, DOCX and PDF punctuation checks are clear. Package/render checks do not assert that the PPTX was opened in native Microsoft PowerPoint.

Human authorship, contributions, affiliations, funding, conflicts and final approval remain unknown. The original OPV workbook lacks an established separate redistribution license in the inspected repository. No matched OPV carryover/calibration/cost experiment or independent-team replication has been performed. These are tracked open issues, not hidden by manuscript completion.

Review completion and submission readiness are separate: this is a supported computational draft with a secondary materials-data application, not a certified strong-journal submission or a physically validated autonomous laboratory method.
"""
    (AUDIT / "review_report.md").write_text(report)
    print(json.dumps({"register": "audit/evidence_register.json", "paragraphs": len(paragraphs), "equations": len(equations), "citation_relationships": len(occurrences), "references": len(sources), "punctuation": style_counts(final), "final_text_sha256": sha(final_path)}, indent=2))


if __name__ == "__main__":
    main()
