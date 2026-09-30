"""Reproduce the PDF's three archived stages using an independent native service.

Uses the existing LM physics hook; no solver monkeypatches and no new data.
The fixed coefficient windows and beta=.05 apply only to these replay fixtures.
"""
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict
from functools import partial
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.signal import fftconvolve

from integration_checks import ArrayGeometry
from verify import OUTPUT
from experiments.modal_muller_research.coefficient_fields import RegularWaves
from experiments.cleaned_interface.geometry import ProjectedUpdate
from experiments.cleaned_interface.io import curve_from, portable
from experiments.modal_atlas.damped_screen import fitting_data
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, fit_stage

ROOT = Path('results/validation/modal_atlas/MA-005/runs')


class NativePhysics:
    def __init__(self):
        self.cache = OrderedDict()
        self.counts = dict(geometry_builds=0, evaluations=0, derivatives=0, wave_builds=0)

    @contextmanager
    def ordered_calls(self, function, items):
        yield [partial(function, item) for item in items]

    def evaluate(self, curve, observation, contrast, resolution):
        key = curve.coefficients.tobytes()
        if key not in self.cache:
            prepared = ArrayGeometry(curve, 160 if curve.band > 24 else 128)
            prepared.waves_cache = {}
            self.cache[key] = prepared
            self.counts['geometry_builds'] += 1
            if len(self.cache) > 2:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        prepared = self.cache[key]
        cutoff = (96 if resolution == 512 else 128) if curve.band > 24 else (64 if resolution == 512 else 96)
        ko = observation.wavenumber
        a = prepared.assemble(ko, ko*np.sqrt(contrast), cutoff)
        factors = lu_factor(a)
        if ko not in prepared.waves_cache:
            prepared.waves_cache[ko] = RegularWaves(prepared.geometry, ko, prepared.band, 64, 48)
            self.counts['wave_builds'] += 1
        waves = prepared.waves_cache[ko]
        acq = observation.acquisition
        state = lu_solve(factors, waves.rhs(acq.sources, acq.strength, cutoff))
        prediction = np.diag(waves.receiver(acq.receivers, cutoff)@state)
        self.counts['evaluations'] += 1
        return SimpleNamespace(prediction=prediction, curve=curve, ko=ko, contrast=contrast,
                               cutoff=cutoff, factors=factors, state=state, waves=waves, acq=acq)

    def derivative(self, forward, update, space):
        f = forward
        nm = 2*f.cutoff+1
        reciprocal = lu_solve(f.factors, f.waves.rhs(f.acq.receivers, 1., f.cutoff))[:nm]
        moments = fftconvolve(f.state[:nm], reciprocal, axes=0)
        normal = f.curve.modes*f.curve.coefficients
        weight = fftconvolve(space.derivatives, normal[::-1, None].conj(), axes=0)
        weight = (weight+weight[::-1].conj())/2
        n = min(2*f.curve.band, 2*f.cutoff)
        weight = weight[2*f.curve.band-n:2*f.curve.band+n+1]
        moments = moments[2*f.cutoff-n:2*f.cutoff+n+1]
        self.counts['derivatives'] += 1
        return 2*np.pi*(f.ko**2*(f.contrast-1))*moments[::-1].T@weight


def main():
    label = sys.argv[1]
    assert label in ['stage_2_damped', 'release_M11', 'fixed_M43']
    arm = 'DF' if label == 'fixed_M43' else 'D'
    folder = ROOT/arm/'c13.3/shifted_rotated_c'
    config_path = ROOT/'D/c13.3/shifted_rotated_c/configuration.json'
    configuration = json.loads(config_path.read_text())
    expected = json.loads((folder/(label+'.json')).read_text())
    accepted = json.loads((folder/'accepted.json').read_text())['states']
    initial = next(r for r in accepted if r['stage'] == label and r['iteration'] == 0)
    curve = curve_from(initial['curve'])
    stage_record = dict(next(r for r in configuration['stages'] if r['label'] == (
        'fixed_M37' if label == 'fixed_M43' else label)))
    stage_record.update(label=label, update_modes=expected['M'])
    real, damped, _ = fitting_data(13.3, 'shifted_rotated_c')
    pool = real+damped
    ks = [complex(k['real'], k['imag']) if isinstance(k, dict) else k
          for k in stage_record.pop('wavenumbers')]
    stage_record['observations'] = tuple(next(o for o in pool if abs(o.wavenumber-k) < 1e-14) for k in ks)
    stage = FitStage(**stage_record)
    config = BackendConfig(**configuration['backend'])
    ledger = Ledger(cap=13412, seconds=1800)
    ledger.begin_stage(label, stage.quota)
    physics = NativePhysics()
    def on_accept(iteration, evaluation):
        print(json.dumps(dict(stage=label, accepted_index=iteration, loss=evaluation.loss,
                              physics=physics.counts, seconds=ledger.snapshot()['seconds'])), flush=True)
    result = fit_stage(curve, stage, 13.3, ProjectedUpdate(.05), config, ledger,
                       on_accept=on_accept, physics=physics)
    actual_status = [r['status'] for r in result.trials]
    expected_status = [r['status'] for r in expected['trials']]
    exact = curve_from(expected['curve'])
    comparison = dict(stage=label, accepted_steps=result.accepted_steps,
        expected_accepted_steps=expected['accepted_steps'], trial_statuses_equal=actual_status == expected_status,
        trials=len(actual_status), expected_trials=len(expected_status), final_loss=result.final_loss,
        expected_final_loss=expected['final_loss'], loss_relative=abs(result.final_loss/expected['final_loss']-1),
        coefficient_difference=float(np.linalg.norm(result.curve.coefficients-exact.coefficients)),
        endpoint_maximum_difference_units=float(np.max(np.abs(result.curve.values(8192)-exact.values(8192)))),
        outcome=result.outcome, expected_outcome=expected['outcome'], stop=result.stop_reason,
        expected_stop=expected['stop'], seconds=result.seconds, counts=physics.counts,
        expected_solves=sum(expected['work']['solves'].values()),
        expected_derivatives=sum(expected['work']['reciprocal_batches'].values()))
    record = dict(comparison=comparison, native_result=asdict(result),
                  initial=initial, stage=asdict(stage), config=asdict(config),
                  source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [Path(__file__), OUTPUT/'verify.py', OUTPUT/'integration_checks.py']},
                  archive_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in [folder/(label+'.json'), folder/'accepted.json', config_path]})
    (OUTPUT/('replay_'+label+'.json')).write_text(json.dumps(portable(record), indent=2)+'\n')
    print(json.dumps(comparison, indent=2), flush=True)


if __name__ == '__main__':
    main()
