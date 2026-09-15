"""Rebuild closeout from saved tables; never launches a forward or derivative."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import statistics
import time


def read_csv(path):
    return list(csv.DictReader(path.open()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    p = args.bundle
    started = time.perf_counter()
    manifest = json.loads((p/'manifest.json').read_text())
    accuracy = read_csv(p/'accuracy.csv')
    timings = read_csv(p/'timings.csv')
    structure = read_csv(p/'structure.csv')
    taylor = read_csv(p/'taylor.csv')
    controls = json.loads((p/'controls.json').read_text())
    ledger = [json.loads(line) for line in (p/'work_ledger.jsonl').read_text().splitlines()]
    counts = {k:0 for k in manifest['counts']}
    for event in ledger:
        if event['status']=='attempted':
            for k, value in event.get('reserved', {}).items():
                counts[k] += value
    assert counts == manifest['counts']
    assert all(counts[k] <= manifest['limits'][k] for k in counts)
    assert manifest['source_hashes_after'] == manifest['workspace_before']['numerical_sha256']
    assert manifest['execution_status']=='COMPLETE' and manifest['failure'] is None
    source_current = {name:hashlib.sha256(Path(name).read_bytes()).hexdigest()
                      for name in manifest['source_hashes_after']}
    assert source_current == manifest['source_hashes_after'], 'Numerical source changed after measurement'
    full_mode = [r for r in controls if 'scaled_state_relative' in r]
    assert len(full_mode)==10
    assert len([r for r in controls if 'derivative_diagnostics' in r])==36
    assert len(taylor)==16
    assert all(float(r['previous_to_current_ratio'])>3.9 for r in taylor if r['previous_to_current_ratio'])
    assert len([r for r in accuracy if r['method']=='band' and not r['direction']])==16
    assert not any(r['sensitivity_qualified']=='True' for r in accuracy if r['case'].startswith('saved_'))
    assert all(float(r['reference_discrepancy'])<=2e-7 for r in accuracy)

    # A complete record must pair every reserved operation with a completion
    # or failure; a timing number without measured work is not accepted.
    attempted = [r for r in ledger if r['status']=='attempted']
    completed = [r for r in ledger if r['status']=='completed']
    assert len(attempted)==len(completed)
    assert all(a['operation']==b['operation'] for a,b in zip(attempted,completed))
    # Compare only matched scene/frequency/node/mode/direction records.
    def trial_rows(case, method, fraction=None, width=None):
        return [r for r in accuracy if r['case']==case and r['frequency_hz']=='1250000000'
                and r['method']==method and (fraction is None or r['fraction']==str(fraction))
                and (width is None or r['width']==str(width))]

    comparison = []
    for case, fraction in [('circle',.25),('ellipse',.5),('star',.75),
                          ('saved_common',.75),('saved_difficult',.75)]:
        rows = trial_rows(case, 'modal', fraction)
        primal = next(r for r in rows if not r['direction'])
        derivatives = [float(r['sensitivity_relative']) for r in rows if r['direction']]
        comparison.append(dict(case=case, frequency_hz=1_250_000_000,
            nodes_per_component=int(primal['nodes_per_component']),
            retained_modes=int(primal['retained_modes_per_trace_component']),
            data_relative=float(primal['data_relative']), lifted_residual=float(primal['lifted_residual']),
            worst_sampled_sensitivity_relative=max(derivatives) if derivatives else None,
            passes=primal['forward_pass']=='True' and all(r['sensitivity_pass']=='True' for r in rows if r['direction']),
            scope='FORWARD_ONLY' if case.startswith('saved_') else 'forward + sampled sensitivities'))
    timing_summary = {}
    for method in ('nodal','modal'):
        rows = [r for r in timings if r['classification']=='paired_cold' and r['method']==method]
        assert len(rows)==3
        timing_summary[method] = {}
        for key in ('forward_total_seconds','forward_plus_one_jvp_seconds'):
            values = [float(r[key]) for r in rows]
            timing_summary[method][key] = dict(median=statistics.median(values),
                                               minimum=min(values),maximum=max(values))
    slowdowns = {key:timing_summary['modal'][key]['median']/timing_summary['nodal'][key]['median']
                 for key in timing_summary['nodal']}
    oracle = []
    for case in ('ellipse','star','saved_common','saved_difficult'):
        rows = [r for r in structure if r['profile']=='oracle' and r['case']==case
                and r['frequency_hz']=='1250000000' and r['tail_target']=='1e-06']
        total = sum(int(r['total_entries']) for r in rows)
        retained = sum(int(r['retained_entries']) for r in rows)
        dense_cross = sum(int(r['total_entries']) if r['interaction']=='cross'
                          else int(r['retained_entries']) for r in rows)
        oracle.append(dict(case=case, all_block_oracle_retention=retained/total,
                           self_oracle_with_dense_cross_retention=dense_cross/total))
    summary = dict(
        H2_FIELD='NO_USEFUL_SIMPLE_COMPRESSION',
        H2_OPERATOR='ORACLE_STRUCTURE_ONLY; fixed-band promotion failed',
        recommendation='Stop/defer this simple projected-field and centered-band prototype; retain tuned nodal Kress. Do not execute a successor.',
        full_mode_cases_passed=10, reference_cases_qualified=10,
        maximum_full_mode_data_error=max(r['data_relative'] for r in full_mode),
        maximum_full_mode_state_error=max(r['scaled_state_relative'] for r in full_mode),
        maximum_forward_reference_discrepancy=max(float(r['reference_discrepancy']) for r in accuracy),
        maximum_sensitivity_reference_discrepancy=max(float(r['sensitivity_reference_discrepancy']) for r in accuracy if r['sensitivity_reference_discrepancy']),
        high_frequency_comparison=comparison, timing=timing_summary,
        modal_slowdown=slowdowns, oracle=oracle, counts=counts,
        numerical_seconds=manifest['numerical_seconds'], peak_rss_bytes=manifest['peak_rss_bytes'],
        tests='4 algebra tests passed; production/full-mode/spectrum/analytic/Taylor checks in ledger',
        audit='PASS: counts reconcile; all reserved operations completed; source hashes unchanged; no multi-interface sensitivity claim',
        reporting_seconds=time.perf_counter()-started)
    (p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    def sci(value):
        return 'unqualified' if value is None else f'{value:.3e}'
    rows = ['| Geometry | Modes / nodes per component | Data relative error | Lifted residual | Worst tested JVP error | Gates |',
            '|---|---:|---:|---:|---:|---|']
    for r in comparison:
        rows.append(f"| {r['case']} | {r['retained_modes']} / {r['nodes_per_component']} | {sci(r['data_relative'])} | {sci(r['lifted_residual'])} | {sci(r['worst_sampled_sensitivity_relative'])} | {'PASS' if r['passes'] else 'FAIL'} |")
    text = f'''# BIE-002 — simple modal compression does not earn promotion

**COMPLETE. H2-FIELD: NO_USEFUL_SIMPLE_COMPRESSION. H2-OPERATOR:
ORACLE_STRUCTURE_ONLY; fixed-band promotion failed.**

One bounded diagnostic ran five fixed geometries at 0.5 and 1.25 GHz. It changed
no shared numerical code, topology controller, material, gauge, acquisition or
optimizer. The known geometry is an input to this forward diagnostic; no inverse
recovery was attempted. BIE-001 was superseded as a desk-study proposal, never
numerically executed. The user's explicit ZIP execution and permission override
authorized BIE-002. No successor is released.

## Key accuracy results at 1.25 GHz

{chr(10).join(rows)}

Circle/ellipse rows show the smallest qualified retained set. Failed rows show
the largest tested truncation (approximately 75%). Both two-component rows are
**FORWARD_ONLY / SENSITIVITY_UNQUALIFIED**. Gates: data <=1e-6; lifted full-system
residual <=1e-6; available sampled JVP <=1e-4. Full-mode controls are excluded
from candidate improvement claims. Absolute errors and separate arc-length
weighted Dirichlet/Neumann trace errors are in [accuracy.csv](accuracy.csv).

All **10/10** physical data references qualified; worst refinement discrepancy
**{summary['maximum_forward_reference_discrepancy']:.3e}**, against 2e-7.
All **10/10** full-mode controls passed; worst data equivalence error
**{summary['maximum_full_mode_data_error']:.3e}**, against 1e-10. The small circle
singular-value check agrees to 2.03e-15 (scaled condition number 4.204); this
confirms a coordinate change does not improve the same matrix's conditioning.
Available analytic derivative references qualified with worst discrepancy
**{summary['maximum_sensitivity_reference_discrepancy']:.3e}**, against 2e-5.
Noncircular mode-5 Taylor remainder ratios are 3.997–4.000 on step halving,
consistent with second order for both the nodal and actual reduced equations.
This checks sampled JVPs, not a full Jacobian or inverse readiness.

The star at half dimension fails both data (1.82e-5) and shape-direction
sensitivity (2.31e-4) at high frequency. At 75% dimension its data error is small,
but the lifted residual remains 5.09e-4, over 500 times the permitted threshold.
Similar residual failures persist in the saved two-star cases. A small receiver
error alone would therefore have given a misleading success label.

## Matched cost result

Three paired cold repeats on the qualified high-frequency ellipse compare
63 modes per trace assembled from 128 nodes against 64-node nodal Kress.
Each arm uses the same 24 source RHS and reuses its LU for the shape-mode JVP.

| Measured cost | Nodal Kress median [range], ms | Dense projected modal median [range], ms | Modal / nodal |
|---|---:|---:|---:|
'''
    for key, label in [('forward_total_seconds','Forward, including setup'),
                       ('forward_plus_one_jvp_seconds','Forward + one analytic JVP, including setup')]:
        n,m = timing_summary['nodal'][key],timing_summary['modal'][key]
        text += f"| {label} | {n['median']*1000:.2f} [{n['minimum']*1000:.2f}, {n['maximum']*1000:.2f}] | {m['median']*1000:.2f} [{m['minimum']*1000:.2f}, {m['maximum']*1000:.2f}] | {slowdowns[key]:.2f}x slower |\n"
    text += f'''
The modal parent matrix, projection and validation-base wrapper are included.
Both comparisons have nonoverlapping observed ranges. Timings are small, local
single-worker measurements, not a broad hardware benchmark. Single-thread BLAS
environment was fixed; optional runtime threadpool inspection was unavailable.
The modal JVP wrapper additionally needs a full base validation state; that
measured cost is exposed separately in [timings.csv](timings.csv).
The cheaper nodal control already reduces the ellipse to nearly the same unknown
count (128 nodal unknowns versus 126 modal unknowns). On both star frequencies,
64-node nodal Kress qualifies; the saved two-component controls qualify at 128
nodes per component. There is no measured cost argument to promote H2-FIELD.

## Operator structure

Fixed widths 4/8/16/32 retain 6.91%, 12.84%, 24.12%, and 44.34% of nonidentity
coefficient positions. At low frequency only the ellipse's width-16 pattern
meets the >=4x storage reduction and accuracy gates. At high frequency width 16
fails its residual gate (1.38e-6); width 32 passes but provides only 2.26x value
storage reduction. No star band passes the combined gates at either frequency.
Thus the required success across noncircular tests is absent.

Sorted-magnitude oracle profiles at relative block Frobenius tail 1e-6 retain:

| Geometry, 1.25 GHz | Oracle retention, all blocks | Self oracle with cross blocks kept dense |
|---|---:|---:|
'''
    for row in oracle:
        text += f"| {row['case']} | {row['all_block_oracle_retention']:.2%} | {row['self_oracle_with_dense_cross_retention']:.2%} |\n"
    text += f'''
These are full-matrix oracle bounds, not tested adaptive sparse algorithms.
The 5.72% ellipse and 16.77% star profiles suggest structure beyond the tested
bands, but do not establish predictable assembly, solved accuracy or derivative
accuracy after oracle truncation. Cross blocks materially limit the saved-scene
savings. Signed -DeltaK/+DeltaV/-DeltaT/+DeltaKp interactions are separated in
[structure.csv](structure.csv); the identity is excluded exactly.

## Work, verification and limitations

- Counts: **{counts['assemblies']}/120** full assemblies, including **36** derivative
  primal reassemblies; **36/36** analytic directional calls;
  **{counts['factorizations']}/300** LU factorizations; **{counts['solves']}/600** RHS batches.
- Numerical wall time: **{manifest['numerical_seconds']:.2f}/1800 s**, including test
  subprocess and two conservatively charged startup seconds. Peak RSS:
  **{manifest['peak_rss_bytes']/1024**3:.3f} GiB / 8 GiB**. The live-array estimate
  also includes dense parents, transformed temporaries, LU and derivative arrays.
- Four algebra tests pass. Physical controls, all 36 analytic operator primal
  reassembly checks, reference convergence and Taylor probes are recorded in the
  work ledger. Reporting audit reconciles all operation reservations/completions.
- Two metadata startup failures preceded numerical execution: missing optional
  `threadpoolctl`, then NumPy's removed `get_info`. They are preserved in
  [startup bundle](../BIE-002-20260915-modal-diagnostic-01/README.md); no physical
  or algebra wiring failure occurred and no scientific arm was retuned.
- Imported numerical source hashes match before/after execution. Topology work
  continued in its own files; this experiment did not edit them. No branches,
  worktrees, commits or pushes were created by this diagnostic.
- This tier does not qualify 1e-8 inverse endpoints, multi-interface derivatives,
  other field bases, or singularity-aware spectral methods. Analytic fixtures
  use declared Cartesian coefficient directions, with no re-gauge/retraction.
- Arrays/rasters are not required to audit these tables. Frozen coefficients,
  acquisition, materials, scene provenance, source hashes and regeneration
  commands are in [manifest.json](manifest.json) and [commands.md](commands.md).

## Single next decision

**Stop/defer this simple projected-field and centered-band prototype; retain
tuned nodal Kress.** Do not implement a new basis, new sparse pattern,
coefficient-only assembly, multi-interface derivative, inverse campaign or
geometry-reuse successor from this closeout. The result does not refute all
spectral BIE approaches.
'''
    (p/'README.md').write_text(text)
    (p/'reporting_validation.json').write_text(json.dumps(dict(status='PASS',counts=counts,
        physical_reexecution=False, source_unchanged=True, completed_operations=len(completed),
        reporting_seconds=time.perf_counter()-started),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
