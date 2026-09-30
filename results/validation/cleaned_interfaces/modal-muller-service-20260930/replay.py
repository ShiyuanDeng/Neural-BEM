"""Replay three archived MA-005 stages through the maintained modal_muller service.

The unchanged LM loop runs through the cleaned physics hook, starting from each
archived stage's initial curve, with its observations, configuration, quota and
SC-035 update. Resolution tokens come from the service's own profile. Saved
steps are never replayed.
Usage: replay.py {stage_2_damped|release_M11|fixed_M43} [frequency_threads]
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from experiments.cleaned_interface.geometry import ProjectedUpdate
from experiments.cleaned_interface.io import curve_from, write
from experiments.cleaned_interface.modal_muller import ModalMuller
from experiments.cleaned_interface.physics import Execution
from experiments.modal_atlas.damped_screen import fitting_data
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, fit_stage

OUT = Path(__file__).resolve().parent
ROOT = Path('results/validation/modal_atlas/MA-005/runs')
SOURCES = [Path(__file__), *sorted(Path('experiments/cleaned_interface').glob('modal_*.py')),
           Path('experiments/cleaned_interface/physics.py'), Path('experiments/shape_continuation/lm_backend.py')]


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    label = sys.argv[1]
    threads = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    assert label in ('stage_2_damped', 'release_M11', 'fixed_M43')
    arm = 'DF' if label == 'fixed_M43' else 'D'
    folder = ROOT/arm/'c13.3/shifted_rotated_c'
    config_path = ROOT/'D/c13.3/shifted_rotated_c/configuration.json'
    configuration = read(config_path)
    expected = read(folder/(label+'.json'))
    initial = next(r for r in read(folder/'accepted.json')['states'] if r['stage'] == label and r['iteration'] == 0)
    curve = curve_from(initial['curve'])
    record = dict(next(r for r in configuration['stages'] if r['label'] == ('fixed_M37' if label == 'fixed_M43' else label)))
    record.update(label=label, update_modes=expected['M'])
    real, damped, _ = fitting_data(13.3, 'shifted_rotated_c')
    wavenumbers = [complex(k['real'], k['imag']) if isinstance(k, dict) else k for k in record.pop('wavenumbers')]
    record['observations'] = tuple(next(o for o in real+damped if abs(o.wavenumber-k) < 1e-14) for k in wavenumbers)
    service = ModalMuller(Execution(device='cpu', frequency_threads=threads))
    profile = service.resolution_profile(record['curve_modes'])
    record.update(nodes=profile['production'], refined_nodes=profile['refined'])
    stage = FitStage(**record)
    ledger = Ledger(cap=13412, seconds=1800)
    ledger.begin_stage(label, stage.quota)

    def accepted(iteration, evaluation):
        print(json.dumps(dict(stage=label, accepted_index=iteration, loss=evaluation.loss,
                              counts=service.receipt()['counts'], seconds=ledger.snapshot()['seconds'])), flush=True)
    result = fit_stage(curve, stage, 13.3, ProjectedUpdate(.05), BackendConfig(**configuration['backend']), ledger,
                       on_accept=accepted, physics=service)
    keys = ('iteration', 'damping', 'backtrack', 'status')
    solves = sum(v for k, v in expected['work']['solves'].items() if k.startswith(label+':'))
    derivatives = sum(v for k, v in expected['work']['reciprocal_batches'].items() if k.startswith(label+':'))
    receipt = service.receipt()
    difference = result.curve.coefficients-curve_from(expected['curve']).coefficients
    band = len(difference)//2
    spectrum = np.zeros(8192, complex)
    spectrum[np.arange(-band, band+1) % 8192] = difference
    endpoint = float(np.max(np.abs(np.fft.ifft(spectrum)*8192)))
    comparison = dict(stage=label, trials=len(result.trials), expected_trials=len(expected['trials']),
        trials_equal=[tuple(r[k] for k in keys) for r in result.trials] == [tuple(r[k] for k in keys) for r in expected['trials']],
        accepted_indices_equal=[r['iteration'] for r in result.history] == [r['iteration'] for r in expected['history']],
        accepted_steps=result.accepted_steps, expected_accepted_steps=expected['accepted_steps'],
        same_exit=result.outcome == expected['outcome'] and result.stop_reason == expected['stop'],
        outcome=result.outcome, stop=result.stop_reason,
        stage_solves=solves, stage_reciprocal_batches=derivatives,
        service_evaluations=receipt['counts']['evaluations'], service_derivatives=receipt['counts']['derivatives'],
        stage_work_equal=solves == receipt['counts']['evaluations'] and derivatives == receipt['counts']['derivatives'],
        final_loss=result.final_loss, archived_loss=expected['final_loss'],
        final_loss_relative=abs(result.final_loss/expected['final_loss']-1),
        endpoint_maximum_difference_units=endpoint, endpoint_maximum_difference_metres=.05*endpoint,
        coefficient_difference=float(np.linalg.norm(difference)),
        resolution=dict(production=stage.nodes, refined=stage.refined_nodes,
                        windows=profile['coefficient_workspace']),
        seconds=result.seconds, frequency_threads=threads, stage_seconds=receipt['stage_seconds'])
    write(OUT/f'replay_{label}.json', dict(comparison=comparison, result=asdict(result), receipt=receipt,
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        source_hashes={str(p): digest(p) for p in SOURCES},
        archive_hashes={str(p): digest(p) for p in (folder/(label+'.json'), folder/'accepted.json', config_path)}))
    print(json.dumps(comparison, indent=2), flush=True)


if __name__ == '__main__':
    main()
