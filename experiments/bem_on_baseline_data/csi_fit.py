"""One BEM fit on a CC-CSI table (dataset settings in ``DATASETS``), default method, resumable at case level.

Default method unchanged: centred 65 mm circle, ``modal_muller`` + ``slider``, localization
none, no warm-up, real data only, recovered contrast (the comparison's weak start), no noise
level declared, series limit 1e-9, 13,412 work units. The only CSI-specific parts:

- the frequency rule of the measured cylinder (coordinator, review stop 1): ladder stages are
  catalog prefixes, one frequency at a time, up to the highest frequency at or below half the
  catalog top; then the whole catalog. On 1-8 GHz: 1; 1-2; 1-3; 1-4; then 1-8 GHz.
  Simulated TG-002 tables (reported pass) use 0.5, 1, 1.5, 2 and 2.5 GHz: five ladder stages,
  one frequency at a time, quotas (1000, 1000, 1000, 1000, 4000), then the whole list. The
  early look used 1-3 GHz, ladder 1; 1-2; 1-3 GHz, quotas (1000, 3000, 4000);
- frequency-block (ragged) stages, shown equal to the rectangular default to round-off at
  review stop 2;
- length unit 0.05 m, origin at the acquisition centre, bounds +-0.3 m (the default's sizes).

The fit never reads truth. Scoring against truth runs after ``fit`` returns, with the unedited
``experiments/comparison/scoring.py``. Rerunning the same command skips a finished case; an
unfinished attempt is kept and a new attempt starts from the start (no tuning reruns).
"""
from csi_runtime import ROOT, memory_available_gib, peak_memory_gib, provenance  # noqa: E402  first: pins BLAS/OpenMP threads before numpy loads
import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
import signal
import threading
import time
import traceback
from pathlib import Path

import numpy as np

from bem_inverse import Execution, FourierCurve, Problem
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings, forward_solve
from bem_inverse.io import curve_from, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.real_only_policy import RealOnlyPolicy
from bem_inverse.runner import fit

import csi_data as D

START_RADIUS_M = .065
BOUNDS_M = ((-.3, -.3), (.3, .3))
EPSILON, MINIMUM_START = 1e-3, .05          # the comparison's weak-scatterer start (MR-001)
# CPU cross-check stops at 120 s and waits for the GPU pass. The GPU pass has no elapsed-time
# stop (the user, 18 Nov 2026: time targets are reports, not stops); it ended at 3600 s before.
WALL = dict(cpu=120., cuda=float('inf'))
THREADS = dict(cpu=1, cuda=4)               # CPU: one thread per fit; GPU: the default's 4
START_MEMORY_GIB, GUARD_MEMORY_GIB = 16.5, 14.   # start leaves >= 14.5 GiB after a ~2 GiB peak
MEASURED_CASE = 'dielTM_dec8f'
# Reported five-frequency pass. The early look at 1-3 GHz stays in results/bem/baseline_data/csi_cases.
RESULTS = Path('results/bem/baseline_data/csi_five_frequency/2026-11-18')
# Dataset-level settings (coordinator, 18 Nov 2026). Never per case. The simulated list is the
# one setting the user chooses. Reported pass, the user at 03:39 UTC: "Use [0.5, 1, 1.5, 2, 2.5]
# GHz for all ten C-simulated BEM cases". The early look used (1, 2, 3) on the eight-frequency
# tables.
DATASETS = dict(measured=dict(frequencies_ghz=None),          # all eight
                simulated=dict(frequencies_ghz=(.5, 1., 1.5, 2., 2.5)))
# Ladder rule, fixed by the coordinator before any result on such a list: one frequency at a
# time, lowest first, up to the larger of 3 GHz (about the top of the default TG-002 ladder in
# wavenumber) and half the top frequency; then the default all-frequency stages on the list.
LADDER_FLOOR_HZ = 3e9
# Quotas: first and last stage as the default (1000 and 4000); the default's middle 3000 units
# are shared equally by the middle stages. The ladder total stays 8000 for any stage count.
LADDER_QUOTAS = {3: (1000, 3000, 4000),                   # default four with the middle two merged
                 4: RealOnlyPolicy().prefix_quotas,       # the default (1000, 1250, 1750, 4000)
                 5: (1000, 1000, 1000, 1000, 4000)}       # five-frequency list, fixed before any result
FREQUENCY_RULE = ('ladder: one frequency at a time, lowest first, up to max(3 GHz, top/2); '
                  'then the default all-frequency stages on the whole list')


def dataset(case):
    return 'measured' if case == MEASURED_CASE else 'simulated'


def ladder(frequencies_hz):
    """The fixed CSI frequency rule, from the list's frequencies only."""
    limit = max(LADDER_FLOOR_HZ, max(frequencies_hz)/2)
    return tuple(f for f in sorted(frequencies_hz) if f <= limit)


@dataclass(frozen=True)
class CsiPolicy(RealOnlyPolicy):
    """RealOnlyPolicy with the CSI ladder and frequency-block stages; nothing else changes."""
    name: str = 'real_only_csi'

    def _fit(self, *args, **kwargs):
        operation = super()._fit(*args, **kwargs)
        return replace(operation, stage=replace(operation.stage, ragged_data=True))


def policy_for(real, device):
    frequencies = [o.frequency_hz for o in real]
    rungs = ladder(frequencies)
    if len(rungs) not in LADDER_QUOTAS:
        raise ValueError(f'The frequency rule gives {len(rungs)} ladder stages; quotas exist for {sorted(LADDER_QUOTAS)}.')
    if tuple(frequencies[:len(rungs)]) != rungs:
        raise ValueError('The ladder must be a prefix of the catalog.')
    return CsiPolicy(prefix_frequencies_hz=rungs, prefix_quotas=LADDER_QUOTAS[len(rungs)], fit_seconds=WALL[device])


def case_input(case):
    if case == MEASURED_CASE:
        return Path(D.MEASURED)
    shape = case.split('__')[0]
    return ROOT/D.SIMULATED.format(shape=shape)


def truth_for(case):
    """Scoring only, after the fit returns."""
    if case == MEASURED_CASE:
        return FourierCurve.circle(.015/D.LENGTH_M, .030j/D.LENGTH_M), 3., 'nominal (0,+30) mm, r 15 mm, eps 3 +/- 0.3'
    from experiments.benchmark import scenes as S
    shape, contrast = case.split('__c')
    return S.truth_fixture(shape), float(contrast), f'frozen TG-002 truth_fixture("{shape}")'


def weak_start(context, initial, observation):
    """The comparison's rule (experiments/comparison/bem.py weak_start), on the table context."""
    nodes = context.resolution_profile(initial.band)['production']
    started = time.perf_counter()
    state = forward_solve(initial, observation, 1.+EPSILON, nodes, context=context)
    p, d = np.asarray(state.prediction).reshape(-1), np.asarray(observation.scattered).reshape(-1)
    susceptibility = EPSILON*float(np.real(np.vdot(p, d))/np.real(np.vdot(p, p)))
    return max(1.+susceptibility, MINIMUM_START), dict(
        rule='weak', epsilon=EPSILON, frequency_hz=observation.frequency_hz, nodes=nodes,
        estimated_susceptibility=susceptibility, clipped=1.+susceptibility < MINIMUM_START,
        seconds=time.perf_counter()-started)


def memory_guard(out, stop):
    def watch():
        while not stop.wait(2.):
            available = memory_available_gib()
            if available < GUARD_MEMORY_GIB:
                (out/'guard_stop.json').write_text(json.dumps(dict(
                    available_gib=available, limit_gib=GUARD_MEMORY_GIB, utc=time.time()))+'\n')
                os.kill(os.getpid(), signal.SIGTERM)
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread


def gpu_peak_gib():
    try:
        import torch
        return torch.cuda.max_memory_allocated()/1024**3 if torch.cuda.is_available() else None
    except Exception:
        return None


def final_fields(context, real, curve, contrast):
    nodes = context.resolution_profile(curve.band)['production']
    residual = []
    for observation in real:
        p = np.asarray(forward_solve(curve, observation, contrast, nodes, context=context).prediction).reshape(-1)
        residual.append(float(np.linalg.norm(p-observation.scattered)/np.linalg.norm(observation.scattered)))
    return residual, nodes


def score(case, curve, contrast):
    from experiments.comparison.scoring import region, region_scores
    truth, true_contrast, note = truth_for(case)
    found, repaired = region([D.LENGTH_M*curve.values(16384)])
    actual, _ = region([D.LENGTH_M*truth.values(16384)])
    scores = region_scores(found, actual)
    centre = None if found.is_empty else (1e3*found.centroid.x, 1e3*found.centroid.y)
    return dict(truth=note, true_contrast=true_contrast, contrast=contrast,
                contrast_error=(contrast-true_contrast)/true_contrast, repaired_ring=repaired,
                centre_mm=centre, true_centre_mm=(1e3*actual.centroid.x, 1e3*actual.centroid.y),
                equivalent_radius_mm=float(np.sqrt(scores['area_mm2']/np.pi)), **scores)


def summarize(case, context, real, result):
    """The reported record, from the saved fit result; truth is read only in ``score``."""
    curve = curve_from(result['final_curve'])
    final_contrast = float(result['final_contrast'])
    stages = result['stages']
    residual, nodes = final_fields(context, real, curve, final_contrast)
    return dict(outcome=result['outcome'], detail=result['detail'],
                last_stage=stages[-1]['stage'] if stages else None,
                stages=[dict(stage=s['stage'], M=s['M'], outcome=s['outcome'], accepted_steps=s['accepted_steps'],
                             seconds=s['seconds'], final_loss=s['final_loss'], contrast=s['contrast'])
                        for s in stages],
                fit_seconds=result['fit_and_localization_seconds'], work_units=result['fit_and_localization_units'],
                contrast=final_contrast, final_residual_nodes=nodes,
                final_residual={f'{o.frequency_hz/1e9:g}GHz': r for o, r in zip(real, residual)},
                score=score(case, curve, final_contrast), bookkeeping='complete')


def complete(attempt, case, device):
    """Finish the record of an attempt whose fit returned but whose record step failed; no new fit."""
    first = json.loads((attempt/'metrics.json').read_text()) if (attempt/'metrics.json').exists() else {}
    (attempt/'metrics_first_write.json').write_text(json.dumps(first, indent=1)+'\n')
    real, _, _ = D.observations(case_input(case), DATASETS[dataset(case)]['frequencies_ghz'])
    context = ModalMuller(Execution(device=device, frequency_threads=THREADS[device]), ModalSettings(table_mode=True))
    record = dict(case=case, device=device, **summarize(case, context, real, json.loads((attempt/'fit.json').read_text())))
    record.update({k: first.get(k) for k in ('case_seconds', 'peak_memory_gib', 'gpu_peak_allocated_gib')},
                  completed_from='fit.json by a later record step', completion_provenance=provenance())
    write(attempt/'metrics.json', record)
    if not (attempt/'bulk_manifest.json').exists():
        files = [dict(path=str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p), bytes=p.stat().st_size,
                      sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted((attempt/'local').rglob('*')) if p.is_file()]
        write(attempt/'bulk_manifest.json', dict(files=files))
    return record


def attempt_dir(base, case, device):
    """Next attempt folder, or None when one is finished. A returned fit with a failed record is completed."""
    for attempt in sorted(base.glob('attempt_*')):
        metrics = attempt/'metrics.json'
        if metrics.exists() and json.loads(metrics.read_text()).get('bookkeeping') == 'complete':
            return None, metrics
        if (attempt/'fit.json').exists():   # the fit returned; only its record is missing or failed
            complete(attempt, case, device)
            return None, metrics
    number = len(list(base.glob('attempt_*')))+1
    return base/f'attempt_{number:02d}', None


def run(case, device, out_root):
    base = Path(out_root).resolve()/case/device
    out, finished = attempt_dir(base, case, device)
    if finished is not None:
        print(f'{case} {device}: finished, {finished}', flush=True)
        return json.loads(finished.read_text())
    available = memory_available_gib()
    if available < START_MEMORY_GIB:
        raise SystemExit(f'Only {available:.1f} GiB available; need {START_MEMORY_GIB} GiB to start.')
    out.mkdir(parents=True)
    stop = threading.Event()
    memory_guard(out, stop)
    started = time.perf_counter()
    path = case_input(case)
    name = dataset(case)
    real, _, source = D.observations(path, DATASETS[name]['frequencies_ghz'])
    source['sha256_checked_against_frozen_file'] = name == 'simulated'   # checked in main() before any attempt
    execution = Execution(device=device, frequency_threads=THREADS[device])
    context = ModalMuller(execution, ModalSettings(table_mode=True))
    policy = policy_for(real, device)
    initial = FourierCurve.circle(START_RADIUS_M/D.LENGTH_M, 0j)
    contrast, start = weak_start(context, initial, real[0])
    problem = Problem(initial, real, None, contrast, length_unit_m=D.LENGTH_M, origin_m=0j, bounds_m=BOUNDS_M)
    material = MaterialUnknown()
    manifest = dict(case=case, device=device, input=dict(source, path=str(path)), provenance=provenance(),
                    settings=dict(solver='modal_muller', geometry_update='slider', localization='none',
                                  start='centred 65 mm circle', data='real only, no noise level declared',
                                  material=material.settings(), contrast_start=start, start_contrast=contrast,
                                  execution=asdict(execution), modal_settings=asdict(context.settings),
                                  length_unit_m=D.LENGTH_M, origin_m=0., bounds_m=BOUNDS_M,
                                  dataset=name, dataset_settings=DATASETS[name], frequency_rule=FREQUENCY_RULE,
                                  ladder_hz=policy.prefix_frequencies_hz, policy=policy.plan(problem, context)))
    write(out/'manifest.json', manifest)
    record = dict(case=case, device=device)
    try:
        result = fit(problem, solver='modal_muller', physics=context,
                     forward_solve=lambda *a: forward_solve(*a, context=context),
                     policy=policy, output=out/'local', geometry_update='slider', material=material,
                     on_event=lambda e: print(case, device, e['operation']['label'], e['reason'], flush=True))
        write(out/'fit.json', result)
        record.update(summarize(case, context, real, json.loads((out/'fit.json').read_text())))
    except Exception:
        record.update(outcome='WORKER_EXCEPTION', detail=traceback.format_exc())
    record.update(case_seconds=time.perf_counter()-started, peak_memory_gib=peak_memory_gib(),
                  gpu_peak_allocated_gib=gpu_peak_gib(), memory_available_end_gib=memory_available_gib())
    stop.set()
    files = [dict(path=str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p), bytes=p.stat().st_size,
                  sha256=hashlib.sha256(p.read_bytes()).hexdigest())
             for p in sorted((out/'local').rglob('*')) if p.is_file()]
    write(out/'bulk_manifest.json', dict(files=files))
    write(out/'metrics.json', record)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True, help=f'{MEASURED_CASE} or <shape>__c4 (simulated)')
    parser.add_argument('--device', choices=('cpu', 'cuda'), required=True)
    parser.add_argument('--out', default=str(ROOT/RESULTS))
    parser.add_argument('--checks', default=str(ROOT/RESULTS/'adapter_checks'),
                        help='folder of csi_forward_check.py case files; a simulated fit needs its passing check')
    args = parser.parse_args()
    args.out, args.checks = str(Path(args.out).resolve()), str(Path(args.checks).resolve())
    if dataset(args.case) == 'simulated':
        digest = D.verify_sha256(case_input(args.case))      # frozen table, before any attempt
        check = Path(args.checks)/f'{args.case}.json'
        checked = json.loads(check.read_text()) if check.exists() else None
        summary = checked['summary'] if checked else None
        selected = list(DATASETS['simulated']['frequencies_ghz'])
        if not summary or not summary['adapter_checks_pass'] or not summary['one_percent_rule']:
            raise SystemExit(f'No passing adapter check and 1% rule on {selected} GHz at {check}; run csi_forward_check.py first.')
        # The check must be of this very table and of this frequency list (not an early-look check).
        if checked['frozen_sha256_verified'] != digest or list(summary['rule_frequencies_ghz']) != selected:
            raise SystemExit(f'The check at {check} is of another table or frequency list; rerun csi_forward_check.py.')
    run(args.case, args.device, args.out)


if __name__ == '__main__':
    main()
