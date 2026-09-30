"""Build the comparison tables from completed, sequential benchmark receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def main():
    records = {name: json.loads((HERE / (name + '.json')).read_text())
               for name in ('single', 'catalog')}
    for record in records.values():
        assert record['status'] == 'COMPLETE'
        for source, digest in record['source_hashes'].items():
            assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest, source
        for group in record['medians']:
            selected = [r for r in record['rows']
                        if all(r[k] == group[k] for k in ('fixture', 'method', 'resolution_token'))]
            assert len(selected) == 3, (group['fixture'], len(selected))
            assert {r['repetition'] for r in selected} == {0, 1, 2}

    def group(part, fixture, method, token):
        return next(r for r in records[part]['medians'] if r['fixture'] == fixture
                    and r['method'] == method and r['resolution_token'] == token)

    labels = {'C_real_2.5GHz': 'C, real 2.5 GHz', 'C_damped_1GHz': 'C, damped 1 GHz',
              'DF_endpoint_real_2.5GHz': 'Large C endpoint, real 2.5 GHz',
              'DF_endpoint_catalog19': 'Large C endpoint, 19 real frequencies'}

    def method_name(row):
        if row['method'] == 'modal_cpu':
            large = row['fixture'].startswith('DF_')
            cutoff = (96 if large else 64) if row['resolution_token'] == 512 else (128 if large else 96)
            return f'Modal CPU, Ku={cutoff}'
        return f"Kress {'CUDA' if row['method'] == 'nodal_cuda' else 'CPU'}, N={row['resolution_token']}"

    text = [
        '# Modal Chebyshev versus maintained cleaned-interface Kress', '',
        '2026-09-30. A matched comparison of the independent Chebyshev review prototype '
        'and the actual `NodalKress` service at repository HEAD `1723dbee`. '
        '**The modal path computes fields and shape Jacobians on the tested fixtures, '
        'but is not a complete, registered cleaned-interface backend. Latest CUDA Kress '
        'remains faster for these forward workloads and reaches a lower observed error floor.**', '',
        '## What was compared', '',
        '- CPU: Intel Core Ultra 9 285K. GPU: NVIDIA RTX 5090 (32 GB). '
        'Python 3.9.25, NumPy 2.0.2, SciPy 1.13.1, PyTorch 2.8.0+cu128; double precision.',
        '- Kress: maintained `experiments.cleaned_interface.physics.NodalKress`, '
        '`acceleration=spd016`, `geometry=both`, explicit CUDA with four frequency workers. '
        'Receipts verify real CUDA / damped CUDA and no fallback. CPU Kress uses one frequency worker.',
        '- Modal: unchanged independent `chebyshev-review-20260930/replay.py:NativePhysics`, '
        'one CPU frequency worker; BLAS uses one thread for every method. '
        'This compares implementations currently available, not hypothetical equally optimized GPU implementations.',
        '- All fixtures use contrast 13.3 and the same 24 paired point-source observations. '
        'The small C has geometry band K=24 and update band M=24; the saved DF endpoint has K=192, M=67. '
        'Damping means multiplication of the real wavenumber by `1+0.25i`.',
        '- Modal coefficient window B=128 / 160 for the small / large C; radial degree 100, '
        'log degree 260, assumed log lower endpoint beta=0.05. Source/receiver angular order 64 '
        'and series length 48. Profile tokens 512/1024 map to Ku=64/96 on the small C and '
        'Ku=96/128 on the endpoint; they are not modal node counts.',
        '- Three sequential repetitions, with method order rotated/reversed; CUDA synchronization '
        'at timing boundaries. Tables report medians; raw JSON records every observation and min/max ranges. '
        'The timings include complete matrix assembly, factorization, incident fields and receiver evaluation.',
        '- **New geometry forward** includes modal geometry preparation and every required frequency-specific '
        'source expansion. **Same geometry forward** retains modal geometry/source expansions; '
        'both methods rebuild and factor their matrices. **Jacobian** reuses forward factors. '
        'Imports, CUDA startup and one-time damped ray-table construction are excluded.',
        '- SC geometry-update preparation is excluded equally from both physics timings: '
        'about 0.107 s for K=24/M=24 and 2.276 s for K=192/M=67 in the single-frequency run. '
        'Thus these are not full LM iteration or inverse-campaign speed ratios.', '',
        '## Precision', '',
        'Errors below are relative Euclidean field errors and relative Frobenius Jacobian errors '
        'against independently evaluated **2048-node CPU Kress**. These measure agreement with '
        'a refined numerical reference, not certified error against an exact solution. '
        'Kress 512 and 1024 already agree at roughly roundoff on these smooth fixtures.', '',
        '| Fixture | Method | Field error | Jacobian error | Worst Jacobian column |',
        '|---|---|---:|---:|---:|']
    for row in records['single']['medians']:
        if row['method'] == 'nodal_cpu':
            continue
        raw = [r for r in records['single']['rows'] if all(r[k] == row[k]
               for k in ('fixture', 'method', 'resolution_token'))]
        text.append(f"| {labels[row['fixture']]} | {method_name(row)} | {row['worst_fields']:.3g} | "
                    f"{row['worst_jacobian']:.3g} | {max(r['worst_jacobian_column'] for r in raw):.3g} |")
    text += ['', 'Higher Ku is necessary for high precision. For example, the endpoint improves '
             'from roughly 1.6e-10 field / 8.7e-8 Jacobian error at Ku=96 to '
             '1.8e-12 / 5.2e-12 at Ku=128. The fast profile is therefore not the same '
             'accuracy as the refined profile. These fixture comparisons meet the current field '
             'and Jacobian-column refinement thresholds; that is not a full cleaned-interface audit.', '',
             'The earlier independent review also found a roughly 7.2e-9 damped field-error floor '
             'at 2.5 GHz on the saved C, unchanged by increasing Ku from 64 to 96. '
             'The successful 1 GHz damped check here does not establish uniform accuracy for '
             'larger complex wavenumbers. See the [mathematical and numerical review]'
             '(../../../../docs/iterations/cleaned_interfaces/node_free_modal_muller_review.md).', '',
             '## Single-frequency runtime', '',
             'All entries are seconds. The CPU control is included to separate the modal '
             'algorithm from the advantage of the maintained GPU implementation.', '',
             '| Fixture | Method | New geometry forward | Same geometry forward | Jacobian | New forward + Jacobian |',
             '|---|---|---:|---:|---:|---:|']
    keys = ('cold_geometry_forward_seconds', 'same_geometry_forward_seconds',
            'retained_factor_jacobian_seconds', 'cold_forward_plus_jacobian_seconds')
    for row in records['single']['medians']:
        text.append(f"| {labels[row['fixture']]} | {method_name(row)} | " +
                    ' | '.join(f"{row['medians'][k]:.6f}" for k in keys) + ' |')

    text += ['', '## Full 19-frequency forward workload', '',
             'Saved DF endpoint, all 19 real frequencies from 0.25 to 2.5 GHz. '
             'Geometry preparation is paid once per batch and source expansions once per frequency. '
             'The precision reference is CPU Kress N=1024 across the entire catalog; '
             'the highest-frequency endpoint also has the independent N=2048 check above.', '',
             '| Method | New geometry forward (s) | Same geometry forward (s) | Jacobian (s) | New forward + Jacobian (s) | Worst frequency field error | Aggregate Jacobian error |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for row in records['catalog']['medians']:
        text.append(f"| {method_name(row)} | " +
                    ' | '.join(f"{row['medians'][k]:.6f}" for k in keys) +
                    f" | {row['worst_fields']:.3g} | {row['worst_jacobian']:.3g} |")

    ratios = []
    for part, record in records.items():
        for q in record['qualifications']:
            fixture = q['fixture']
            nodal = group(part, fixture, 'nodal_cuda', 512)
            for token in (512, 1024):
                modal = group(part, fixture, 'modal_cpu', token)
                ratios.append(dict(fixture=fixture, modal_profile_token=token,
                    baseline='nodal_cuda_512', modal_over_nodal={
                        k: modal['medians'][k] / nodal['medians'][k] for k in keys}))
    text += ['', 'Because N=512 already reaches the reference error floor here, it is the useful '
             'Kress baseline. Comparing only against N=1024 would charge Kress for refinement '
             'that does not improve these fields appreciably. The smaller modal Jacobian cost '
             'does not offset its forward setup and assembly cost in these workloads.', '',
             '## Is it a complete replacement?', '',
             '| Capability | Maintained cleaned-interface Kress | Independent modal prototype |',
             '|---|---|---|',
             '| Boundary to receiver fields | Implemented for the CI single-curve, equal-density contract | Demonstrated on selected fixtures |',
             '| Shape Jacobian | Implemented through the backend contract | Demonstrated; two complete finite-trial directional checks and three archived LM stages reproduced |',
             '| Real / damped frequencies | Implemented; SPD-016 damped envelope and failure/fallback rules | Selected real and damped cases verified; cancellation and source-series limits remain |',
             '| Resolution and error control | Production/refined node profiles plus runner audit | Fixed experimental Ku/B/degrees; no general adaptive selection or valid geometry-bound certificate |',
             '| Localization and observable frontier | Backend methods implemented | Missing from this service |',
             '| Input validation, diagnostics and failure handling | Backend validation, residuals, device/failure receipts | Partial; no equivalent full service contract |',
             '| Registration and full CI runs | Registered; full 36-case inverse campaign executed | Not registered; three stage replays, no full 36-case native campaign |', '',
             'The existing Kress campaign has its own inverse-policy retention failures; its completion '
             'does not mean all inverse cases passed. Conversely, localization/frontier are integration '
             'requirements of the cleaned interface, not missing terms in the modal forward equations.', '',
             'The modal source/receiver expansion additionally requires all points outside its coefficient '
             'bounding circle. Its fixed beta=0.05 is an assumption for these fixtures. '
             'The proposed finite-window Parseval test cannot certify that bound or curve simplicity. '
             'Increasing Ku alone cannot cure coefficient-window, radial/log degree or source-series error.', '',
             '**Use maintained nodal Kress as the current production backend. The Chebyshev modal '
             'implementation is a promising, independently checked research forward/Jacobian solver; '
             'accuracy on these fixtures is comparable at roughly 11–12 digits when refined, '
             'but neither completeness nor a speed advantage over latest CUDA Kress has been established.**', '',
             '## Reproduce and inspect', '',
             'Run from the repository root with CUDA access; run the parts sequentially:', '', '```bash',
             'env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\\n  /home/drdeng/miniconda3/envs/EMNerf/bin/python \\\n  results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/benchmark.py single',
             'env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\\n  /home/drdeng/miniconda3/envs/EMNerf/bin/python \\\n  results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/benchmark.py catalog',
             '/home/drdeng/miniconda3/envs/EMNerf/bin/python \\\n  results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/summarize.py',
             '```', '',
             '[single.json](single.json) and [catalog.json](catalog.json) contain per-repetition timings, '
             'accuracy, execution receipts, reference specifications, environment and SHA-256 source hashes. '
             '[summary.json](summary.json) records ratios to CUDA Kress N=512. '
             'The summarizer verifies completion, three repetitions per group and source hashes. '
             'Production solver and optimizer sources are unchanged.', '']
    (HERE / 'README.md').write_text('\n'.join(text))
    summary = dict(ratios=ratios, input_hashes={name+'.json': hashlib.sha256(
        (HERE/(name+'.json')).read_bytes()).hexdigest() for name in records})
    (HERE / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
