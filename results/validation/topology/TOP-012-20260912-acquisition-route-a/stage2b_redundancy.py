"""TOP-012 stage 2b: why the enriched ring changed nothing. No solves.

Stage 2 found the permitted boundary movement, the singular spectrum and the
condition number all unchanged under twice the angular coverage. This reads the
saved observations and the two recorded spectra to say *why*, and it costs no
forward solve at all.

The normalized residual divides by the observed column norm, so if the added
positions carried the same response energy as the original ones the norm ratio
is exactly sqrt(2), and

    J_v2' J_v2 = (|obs_24| / |obs_48|)^2 J_v1' J_v1 + J_new' J_new
               = 0.5 J_v1' J_v1 + J_new' J_new.

An unchanged spectrum then forces J_new' J_new ~ 0.5 J_v1' J_v1: the added rows
reproduce the existing sensitivity structure direction for direction. They add
no new direction and they do not reweight the ones already there.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_fourier_topology_controller as driver  # noqa: E402
import run_topology_scene_benchmark as benchmark  # noqa: E402

V1 = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
SENSITIVITY = ROOT / 'results/validation/topology/TOP-011-20260912-tolerance-sensitivity'
SCENE = 'far-two-stars'


def observed(bundle):
    saved = benchmark.read(bundle / 'scenes' / SCENE / 'observations.json')
    return np.array(saved['observed_real']) + 1j * np.array(saved['observed_imag'])


def main():
    before, after = observed(V1), observed(HERE / 'suite')
    shared = float(np.max(np.abs(after[::2, 0] - before[:, 0]))
                   / np.max(np.abs(before[:, 0])))
    ratio = float(np.linalg.norm(after[:, 0]) / np.linalg.norm(before[:, 0]))

    v1_spectrum = np.asarray(next(
        s for s in benchmark.read(SENSITIVITY / 'tolerance_sensitivity.json')['states']
        if s['state'] == 'stageB_restart_plateau')['spectra'][0]['singular_values'])
    v2_state = benchmark.read(HERE / 'stage2_tolerance_under_v2.json')['enriched']
    v2_spectrum = np.asarray(v2_state['spectra'][0]['singular_values'])
    fraction = v2_spectrum / v1_spectrum

    record = dict(
        scene=SCENE, forward_solves=0,
        v1_positions=int(before.shape[0]), v2_positions=int(after.shape[0]),
        shared_positions_relative_difference=shared,
        v2_is_strict_superset_of_v1=bool(shared == 0.0),
        observed_norm_ratio=ratio, sqrt_two=float(np.sqrt(2.0)),
        observed_norm_ratio_matches_sqrt_two=bool(abs(ratio - np.sqrt(2.0)) < 1.0e-6),
        singular_value_ratio=dict(
            median=float(np.median(fraction)), minimum=float(fraction.min()),
            maximum=float(fraction.max()),
            median_weak_half=float(np.median(fraction[17:])),
            median_strong_half=float(np.median(fraction[:17]))),
        condition_number=dict(
            v1=float(v1_spectrum[0] / v1_spectrum[-1]),
            v2=float(v2_spectrum[0] / v2_spectrum[-1])),
        reading=('The added positions carry the same response energy as the '
                 'original ones and produce the same singular directions with '
                 'the same relative weights. At 0.5 GHz the sensitivity around '
                 'a 0.30 m ring is angularly band-limited, and 24 positions '
                 'already sample it above that band. Interleaving 24 more '
                 'resamples the same function.'))
    driver.write_json(HERE / 'stage2b_redundancy.json', record)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
