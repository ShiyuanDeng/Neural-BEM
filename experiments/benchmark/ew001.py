"""Approved EW-001 circle controls and measured CUDA contraction cost gate.

Numerical commands require exclusive compute.lock then shared source.lock.
The ON-003 driver and numerical modules remain unchanged. Cost runs use a
fresh process so the circle reference archive cannot shadow maintained code.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
from time import perf_counter

from . import on003

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/validation/cleaned_interfaces/EW-001'
OLD = ROOT / 'results/validation/cleaned_interfaces/ON-003'
SPLITS = (0.5, 0.4, 0.35)
GATE = 1e-7
SOURCE_PATHS = ('experiments/benchmark/ew001.py', 'experiments/benchmark/on003.py',
                'solvers/bem_inverse/on003_ewald.py',
                'solvers/bem_inverse/on003_circle_reference.py',
                'solvers/bem_inverse/modal_cuda.py', 'solvers/bem_inverse/modal_operator.py',
                'solvers/bem_inverse/modal_geometry.py', 'solvers/bem_inverse/modal_muller.py')


def read(path):
    return json.loads(Path(path).read_text())


def provenance():
    return dict(utc=datetime.now(timezone.utc).isoformat(),
                source_hashes={p: on003.digest(ROOT / p) for p in SOURCE_PATHS},
                git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                manifest_sha256=on003.digest(OUT / 'manifest.json'))


def prepare():
    OUT.mkdir(exist_ok=False)
    for name in ('manifest.json', 'reference_HEAD_sources.tar.gz'):
        (OUT / name).write_bytes((OLD / name).read_bytes())
        assert on003.digest(OUT / name) == on003.digest(OLD / name)
    manifest = read(OUT / 'manifest.json')
    assert on003.digest(OUT / 'reference_HEAD_sources.tar.gz') == manifest['reference_archive_sha256']
    on003.write(OUT / 'launch.json', dict(experiment='EW-001', authorization='go on EW-001',
                 scope='registered Q1/Q2 only', reference_copies_verified=True, **provenance()))


def row_key(row):
    return tuple(row[k] for k in ('contrast', 'frequency_hz', 'kind', 'grid', 'trace_cutoff', 'block'))


def compare_rows(new, old):
    a, b = {row_key(r): r for r in new}, {row_key(r): r for r in old}
    if len(a) != len(new) or len(b) != len(old) or set(a) != set(b):
        raise ValueError('Circle row coverage changed')
    difference = max(abs(a[k]['normalized_max_diagonal_error'] -
                         b[k]['normalized_max_diagonal_error']) for k in a)
    return dict(rows=len(a), maximum_absolute_normalized_error_difference=difference,
                tolerance=1e-12, passed=difference <= 1e-12)


def circle(xi):
    if xi != 1:
        if not read(OUT / 'reproduction.json')['passed']:
            raise RuntimeError('QUALIFICATION_INCOMPLETE: reproduction gate failed')
    # Scoped in-process destination override. The reference archive and every
    # numerical operation in ON-003 run() are reused without modification.
    original = on003.OUT
    try:
        on003.OUT = OUT
        result = on003.run(xi)
    finally:
        on003.OUT = original
    result.update(experiment='EW-001', provenance=provenance())
    folder = OUT / f'stage_A_xi{xi}'
    on003.write(folder / 'receipt.json', result)
    if xi == 1:
        check = compare_rows(result['rows'], read(OLD / 'stage_A_xi1/receipt.json')['rows'])
        on003.write(OUT / 'reproduction.json', check)
        print('REPRODUCTION', check, flush=True)
        if not check['passed']:
            raise RuntimeError('QUALIFICATION_INCOMPLETE: reproduction gate failed')
    return result


def terminal(circle_passed, ratios):
    if not circle_passed:
        return 'CIRCLE_FAILS_AT_UNREGISTERED_SPLIT'
    # Two registered trace widths; report each and require cost plausibility
    # at both, rather than selecting the more favourable resolution afterward.
    if all(r < 0.5 for r in ratios):
        return 'CIRCLE_QUALIFIED_AND_COST_PLAUSIBLE'
    return 'CIRCLE_QUALIFIED_BUT_UNECONOMIC_2D'


def costs():
    import numpy as np
    import torch
    from bem_inverse.io import curve_from
    from bem_inverse.modal_muller import ModalMuller
    from bem_inverse.physics import Execution
    from bem_inverse import modal_cuda
    if not torch.cuda.is_available():
        raise RuntimeError('Registered RTX 5090 unavailable')
    folder = OUT / 'costs'
    folder.mkdir(exist_ok=False)
    endpoint = ROOT / 'results/validation/cleaned_interfaces/PC-001/M1/runs/kite__c4/result.json'
    observations = ROOT / 'results/validation/cleaned_interfaces/TG-002/inputs/kite/c4/observations.json'
    curve = curve_from(read(endpoint)['final_curve'])
    frequencies = read(observations)['frequencies_hz']
    assert len(frequencies) == 19
    waves = [2*np.pi*f*np.sqrt((4*np.pi*1e-7)*8.854187817e-12*6.)*.05 for f in frequencies]
    torch.set_num_threads(1)
    current = []
    for cutoff in (128, 160):
        service = ModalMuller(Execution(device='cuda', frequency_threads=1))
        torch.cuda.synchronize()
        start = perf_counter()
        geometry = service._geometry(curve, cutoff + service.settings.window_margin, 'cuda')
        torch.cuda.synchronize()
        geometry_seconds = perf_counter() - start
        repetitions = []
        for repeat in range(4):
            per_frequency = []
            for frequency, ko in zip(frequencies, waves):
                torch.cuda.synchronize()
                start = perf_counter()
                matrix, info = modal_cuda.muller_matrix(geometry, ko, ko*2, cutoff,
                                                       tolerance=service.settings.radial_tolerance)
                torch.cuda.synchronize()
                elapsed = perf_counter() - start
                assert np.all(np.isfinite(matrix))
                per_frequency.append(dict(frequency_hz=frequency, seconds=elapsed,
                                          radial_degree=info['radial_degree']))
            repetitions.append(dict(repeat=repeat, kind='cold' if repeat == 0 else 'warm',
                                    seconds=sum(r['seconds'] for r in per_frequency),
                                    per_frequency=per_frequency))
            on003.write(folder / f'current_K{cutoff}.json', dict(K_trace=cutoff,
                         geometry_seconds=geometry_seconds, repetitions=repetitions))
        current.append(dict(K_trace=cutoff, window=cutoff + service.settings.window_margin,
                     geometry_seconds=geometry_seconds, repetitions=repetitions,
                     warm_median_service_seconds=median(r['seconds'] for r in repetitions[1:])))
        print('CURRENT', cutoff, current[-1]['warm_median_service_seconds'], flush=True)
        del geometry, service, matrix
        torch.cuda.empty_cache()
    contractions = []
    torch.manual_seed(1001)
    for width in (257, 129):
        for dtype, label in ((torch.complex128, 'complex128'), (torch.complex64, 'complex64')):
            torch.cuda.reset_peak_memory_stats()
            a = torch.randn((256**2, width), dtype=dtype, device='cuda')
            d = torch.randn((256**2,), dtype=dtype, device='cuda')
            weighted = torch.empty_like(a)
            output = torch.empty((width, width), dtype=dtype, device='cuda')
            left = a.conj().T
            repeats = []
            for repeat in range(4):
                torch.cuda.synchronize()
                start = perf_counter()
                torch.mul(d[:, None], a, out=weighted)
                torch.mm(left, weighted, out=output)
                torch.cuda.synchronize()
                elapsed = perf_counter() - start
                repeats.append(dict(repeat=repeat, kind='cold' if repeat == 0 else 'warm', seconds=elapsed))
            assert bool(torch.isfinite(output).all())
            contraction = dict(N_grid=256**2, N_trace=width, dtype=label, repetitions=repeats,
                               warm_median_seconds=median(r['seconds'] for r in repeats[1:]),
                               peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                               operation='A.conj().T @ (D[:,None] * A); weighting included; operands resident')
            contraction['projected_19_frequency_two_media_seconds'] = 190*contraction['warm_median_seconds']
            contractions.append(contraction)
            on003.write(folder / f'contraction_{width}_{label}.json', contraction)
            print('CONTRACTION', width, label, contraction['warm_median_seconds'], flush=True)
            del a, d, weighted, output, left
            torch.cuda.empty_cache()
    # Historical counters are summed assembly thread seconds / assembly calls,
    # with no division by frequency threads in this per-call cross-check.
    historical = []
    for path in sorted((ROOT / 'results/validation/cleaned_interfaces/ON-001/all_B/runs').glob('*/fit_result.json')):
        physics = read(path)['physics']
        count = physics['counts']['assembly']
        historical.append(dict(case=path.parent.name, assembly_calls=count,
                               assembly_seconds=physics['seconds']['assembly'],
                               seconds_per_assembly=physics['seconds']['assembly']/count,
                               path=str(path.relative_to(ROOT)), sha256=on003.digest(path)))
    qualified = next(r for r in contractions if r['N_trace'] == 257 and r['dtype'] == 'complex128')
    ratios = [qualified['projected_19_frequency_two_media_seconds']/r['warm_median_service_seconds']
              for r in current]
    result = dict(experiment='EW-001', stage='Q2', current=current, contractions=contractions,
                  lower_bound_over_current_by_K_trace=dict(zip(('128', '160'), ratios)),
                  lower_bound_factor=190, historical_on001=historical,
                  historical_median_seconds_per_assembly=median(r['seconds_per_assembly'] for r in historical),
                  device=torch.cuda.get_device_name(), torch_version=torch.__version__,
                  cuda_version=torch.version.cuda, endpoint_sha256=on003.digest(endpoint),
                  observations_sha256=on003.digest(observations),
                  maintained_import=str(modal_cuda.__file__), **provenance(),
                  exclusions='map construction, near corrections and transfers excluded from Ewald lower bound; '
                             'current includes matrix return to host, both media and lazy radial extension; '
                             'geometry preparation reported separately; no full fields or derivatives',
                  precision_note='complex64 context only; decision uses complex128 N_trace=257')
    on003.write(folder / 'receipt.json', result)
    return result


def summarize():
    import math
    reproduction = read(OUT / 'reproduction.json')
    summaries = []
    for xi in SPLITS:
        receipt = read(OUT / f'stage_A_xi{xi}/receipt.json')
        for size in (128, 256):
            grid = next(r for r in receipt['grids'] if r['grid'] == size)
            for cutoff in (64, 128):
                rows = [r for r in receipt['rows'] if r['grid'] == size and r['trace_cutoff'] == cutoff]
                maximum = {b: max(r['normalized_max_diagonal_error'] for r in rows if r['block'] == b)
                           for b in ('V', 'K', 'Kprime', 'T')}
                summaries.append(dict(xi_over_kstar=xi, grid=size, trace_cutoff=cutoff,
                        maximum_by_block=maximum, passed=all(v <= GATE for v in maximum.values()),
                        tau_q_max_squared=grid['tau_m2']*(math.pi*size/grid['L_m'])**2,
                        tail_term=math.exp(-grid['tau_m2']*(math.pi*size/grid['L_m'])**2),
                        near_refinement_absolute=max(r['near_refinement_absolute'] for r in receipt['near_controls']),
                        far_radial_multiplier_difference=max(r['multiplier_max_difference'] for r in grid['far_quadrature'])))
    cost = read(OUT / 'costs/receipt.json')
    passed = any(r['passed'] and r['grid'] == 256 and r['trace_cutoff'] == 128 for r in summaries)
    status = terminal(passed, list(cost['lower_bound_over_current_by_K_trace'].values())) if reproduction['passed'] else 'QUALIFICATION_INCOMPLETE'
    result = dict(experiment='EW-001', status=status, reproduction=reproduction, gate=GATE,
                  circle=summaries, costs=cost['lower_bound_over_current_by_K_trace'],
                  coverage='circle diagonal screen and contraction lower bound only; '
                           'curved blocks/full fields/derivatives/inverse integration unrun')
    on003.write(OUT / 'summary.json', result)
    print(json.dumps(result, indent=2))
    return result


def verify():
    import numpy as np
    launch = read(OUT / 'launch.json')
    assert launch['reference_copies_verified']
    for name in ('manifest.json', 'reference_HEAD_sources.tar.gz'):
        assert on003.digest(OUT / name) == on003.digest(OLD / name)
    rows_checked = 0
    for xi in (1, *SPLITS):
        folder = OUT / f'stage_A_xi{xi}'
        receipt = read(folder / 'receipt.json')
        controls = read(folder / 'near_and_flat_controls.json')
        labels = {label: i for i, label in enumerate(controls['wave_order'])}
        for size in (128, 256):
            with np.load(folder / f'grid{size}_arrays.npz') as arrays:
                modes = arrays['modes']
                for row in (r for r in receipt['rows'] if r['grid'] == size):
                    o, i = labels[row['exterior']], labels[row['interior']]
                    candidate = arrays[f'near_{o}']+arrays[f'far_{o}']-arrays[f'near_{i}']-arrays[f'far_{i}']
                    reference = arrays[f'exact_{o}']-arrays[f'exact_{i}']
                    block = dict(V=0, K=1, Kprime=1, T=2)[row['block']]
                    use = abs(modes) <= row['trace_cutoff']
                    scale = max(float(np.max(abs(reference[block, use]))), 1e-14)
                    error = float(np.max(abs(candidate[block, use]-reference[block, use])))/scale
                    assert abs(error-row['normalized_max_diagonal_error']) <= 1e-14
                    rows_checked += 1
        for p, digest in receipt['provenance']['source_hashes'].items():
            assert on003.digest(ROOT / p) == digest, p
    summary = read(OUT / 'summary.json')
    cost = read(OUT / 'costs/receipt.json')
    assert 'on003_reference' not in cost['maintained_import']
    assert len(cost['historical_on001']) == 30
    assert summary['status'] == terminal(any(r['passed'] and r['grid'] == 256 and r['trace_cutoff'] == 128
                                            for r in summary['circle']), list(summary['costs'].values()))
    result = dict(passed=True, rebuilt_diagonal_rows=rows_checked,
                  reference_copies_and_source_hashes_verified=True, historical_receipts=30)
    on003.write(OUT / 'verification.json', result)
    print('VERIFIED', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'circle', 'costs', 'summarize', 'verify'))
    parser.add_argument('--xi', type=float, choices=(1, *SPLITS))
    args = parser.parse_args()
    if args.command == 'circle':
        if args.xi is None:
            parser.error('circle requires --xi')
        circle(1 if args.xi == 1 else args.xi)
    else:
        globals()[args.command]()


if __name__ == '__main__':
    main()
