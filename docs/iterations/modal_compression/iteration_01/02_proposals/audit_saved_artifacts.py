"""Read saved evidence only; no solver imports, numerical experiments or edits.

Run from any directory. Stdout is the JSON audit; redirect to a chosen file.
"""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
BUNDLE = ROOT / "results/experiments/laurent_fgm_20260918"


def read(relative):
    return json.loads((BUNDLE / relative).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


provenance = {}
for path in sorted(BUNDLE.glob("*/provenance.json")):
    record = json.loads(path.read_text())
    differences = []
    for name, expected in record["sources"].items():
        source = ROOT / name
        actual = digest(source) if source.exists() else None
        if actual != expected:
            differences.append(dict(path=name, recorded=expected, current=actual))
    provenance[path.parent.name] = dict(
        recorded_sources=len(record["sources"]), differences=differences)

selected = [r for r in read("decay/selected.json") if r["tolerance"] == 1e-6]
noncircular = [r for r in selected if r["curve"] != "circle"]
refinement = [
    {k: r[k] for k in ("curve", "order", "untruncated_error",
                      "truncated_vs_reference", "nonzeros")}
    for r in read("refinement/refinement.json")
    if r["order"] == 33 and r["kd"] == 10 and r["rule"] == "jwy_mu1.2"
]
heldout = read("broadband/heldout.json")
rank80 = {}
for curve in ("ellipse", "kite", "crescent"):
    rows = [r for r in heldout if r["curve"] == curve and r["rank"] == 80]
    rank80[curve] = dict(
        evaluated_frequencies=[r["kd"] for r in rows],
        worst_field_error=max(r["field_error"] for r in rows),
        worst_gradient_error=max(r["gradient_error"] for r in rows),
    )
pdf = next((ROOT / "docs/iterations/modal_compression").glob("*.pdf"))
key_files = [
    BUNDLE / "decay/selected.json", BUNDLE / "refinement/refinement.json",
    BUNDLE / "broadband/heldout.json",
    ROOT / "experiments/laurent_fgm/run_broadband.py",
    ROOT / "experiments/laurent_fgm/run_transfer.py",
    ROOT / "experiments/laurent_fgm/run_penalty.py",
    ROOT / "experiments/laurent_fgm/curves.py",
]
audit = dict(
    review_date="2026-09-21",
    scope="Read-back and source comparison only; no numerical reruns",
    report=dict(path=str(pdf.relative_to(ROOT)), sha256=digest(pdf)),
    checked_input_hashes={str(p.relative_to(ROOT)): digest(p) for p in key_files},
    source_provenance=provenance,
    scaling_has_provenance_json=(BUNDLE / "scaling/provenance.json").exists(),
    refinement_kd10_order33=refinement,
    noncircular_gradient_selected_1e6=dict(
        cases=len(noncircular),
        retention_min=min(r["gradient_retained"] for r in noncircular),
        retention_max=max(r["gradient_retained"] for r in noncircular),
        trace_errors_over_1e6=sum(r["gradient_trace_error"] > 1e-6
                                for r in noncircular),
        worst_trace_error=max(r["gradient_trace_error"] for r in noncircular),
        worst_matrix_error=max(r["gradient_matrix_error"] for r in noncircular),
        note="Trace threshold is a diagnostic comparison, not an original gate.",
    ),
    broadband_rank80=rank80,
    source_review_findings=[
        "run_broadband and run_transfer rescale ko by the perturbed diameter; "
        "their geometry directions hold kD fixed, not physical frequency.",
        "run_decay and run_penalty use fixed physical ko in their perturbations.",
        "run_penalty searches gradient bands starting at the field band; "
        "its lower inequality is imposed by the search.",
        "curves._reach uses finite sampling plus one local Nelder-Mead search; "
        "it does not certify a globally zero-free complex strip.",
        "run_affine.iterations and run_broadband discard GMRES info and solution; "
        "the saved iteration counts do not independently certify residuals.",
    ],
)
print(json.dumps(audit, indent=2, allow_nan=False))
