"""SC-029: pin the unchanged harness and reuse the declared active-space checks."""
from pathlib import Path
from experiments.shape_continuation import atlas_strategy_tests as st


def main():
    output = Path(__file__).resolve().parent
    # This bundle already contains its wrapper; the base preparation expects
    # a fresh directory, so record its identical provenance schema directly.
    inputs = {str(p.relative_to(st.sc.ROOT)): st.ad.digest(p) for c in st.CASES for p in
              (st.source_folder(c)/n for n in ("observations.json","truth.json","oracle_check.json"))}
    for c in st.CASES:
        assert st.sc.read(st.source_folder(c)/"oracle_check.json")["passed"]
    base = st.ad.BASE / "SC-028-atlas-strategies/qualification.json"
    diag = st.ad.BASE / "SC-028-active-band-diagnostic/diagnostic.json"
    fields, active = st.sc.read(base), st.sc.read(diag)
    rows = []
    for f,d in zip(fields["rows"],active["rows"]):
        assert (f["case"],f["frequency_hz"]) == (d["case"],d["frequency_hz"])
        rows.append(dict(case=f["case"],frequency_hz=f["frequency_hz"],field_relative=f["field_relative"],
            jacobian_column_relative=d["band_max_relative"]["19"],band=19,
            passed=f["field_relative"] <= 1e-6 and d["band_max_relative"]["19"] <= 1e-6))
    evidence = [base, diag, diag.with_name("diagnose.py"), *[
        st.ad.BASE/"SC-025-band-policies/runs/ladder"/c/"result.json" for c in st.CASES]]
    plan = st.sc.ROOT / "docs/iterations/shape_frequency_continuation/iteration_11/03_plan.md"
    assert not (output / "manifest.json").exists(), "Use a fresh bundle"
    st.sc.write(output / "manifest.json", dict(experiment="SC-029",source_sha256=st.sc.source_hashes(),inputs=inputs,
        plan=str(plan.relative_to(st.sc.ROOT)),plan_sha256=st.ad.digest(plan),
        qualification_evidence={str(p.relative_to(st.sc.ROOT)):st.ad.digest(p) for p in evidence},
        cases=st.CASES,prefixes=st.PREFIXES,suffixes=st.SUFFIXES,extra_frequencies_hz=st.EXTRA_HZ,
        prefix_cap=st.PREFIX_CAP,path_cap=st.PATH_CAP,path_seconds=st.PATH_SECONDS))
    st.sc.write(output / "qualification.json",dict(rows=rows,passed=all(r["passed"] for r in rows),
        reused_from=[str(base.relative_to(st.sc.ROOT)),str(diag.relative_to(st.sc.ROOT))],
        new_work_units=0,original_comparisons_work_units=96,
        limitation="M<=19 at the six recorded endpoints; P=48 remains unqualified"))
    assert all(r["passed"] for r in rows)


if __name__ == "__main__":
    main()
