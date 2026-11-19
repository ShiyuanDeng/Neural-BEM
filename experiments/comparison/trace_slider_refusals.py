"""Inspect saved slider steps and count clean stages with no candidate solve."""
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import root
from shapely import STRtree, linestrings
from shapely.geometry import LinearRing

from bem_inverse import checks
from bem_inverse.continuation.geometry import FourierCurve, grid_size, resize
from bem_inverse.io import curve_from, read, write
from experiments.comparison.compare_clean_schedules import OUT, stage_settings, write_rows

ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = ROOT / 'docs/iterations/investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes'
MEASURED = ROOT / 'results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cuda/attempt_01'
GREEN, ORANGE, GRAY = '#15775c', '#b64d28', '#52514e'


def at(curve, parameters, derivative=0):
    return np.exp(1j * np.outer(parameters, curve.modes)) @ (curve.coefficients * (1j * curve.modes)**derivative)


def crossings(curve, count):
    points = curve.nodes(count).points
    segments = linestrings(np.stack([points, np.roll(points, -1, axis=0)], axis=1))
    i, j = STRtree(segments).query(segments, predicate='crosses')
    pairs = np.column_stack((i[i < j], j[i < j]))
    return dict(samples=count, segments=pairs.tolist(), solver_count=checks.self_intersections(points),
                zero_tolerance_count=checks.self_intersections(points, 0))


def replay(stage, mm):
    hist = stage['history']
    before, accepted = [curve_from(row['coefficients']) for row in hist[-2:]]
    step = stage['accepted_steps']
    trials = [t for t in stage['trials'] if t['iteration'] == step]
    refused, final = trials[-2:]
    assert refused['reason'] == 'self_intersection' and final['status'] == 'accepted'
    assert refused['damping'] == final['damping'] and refused['backtrack'] + 1 == final['backtrack']
    candidate = FourierCurve(before.coefficients + 2 * (accepted.coefficients - before.coefficients))
    counts = (grid_size(accepted.band), 32768)
    rejected_checks = [crossings(candidate, n) for n in counts]
    pairs = np.array(rejected_checks[-1]['segments'])
    assert pairs.shape == (2, 2)

    def difference(t):
        dz = np.diff(at(candidate, t))[0]
        return [dz.real, dz.imag]

    parameters = []
    for pair in pairs:
        seed = (pair + .5) * 2 * np.pi / counts[-1]
        t = root(difference, seed, tol=1e-12).x
        assert max(abs(seed-t)) < 2*np.pi/counts[-1] and np.linalg.norm(difference(t))*mm < 1e-8
        parameters.append(t)
    parameters = np.array(parameters)

    def perpendicular(t):
        return np.real(np.diff(at(accepted, t)) * np.conj(at(accepted, t, 1)))

    closest = root(perpendicular, parameters.mean(axis=0), tol=1e-12)
    assert closest.success
    gap_nm = float(abs(np.diff(at(accepted, closest.x))[0]) * mm * 1e6)
    points = at(candidate, parameters[:, 0])
    report = dict(stage=stage['stage'], step=step, accepted_step_m=final['step_norm_m'],
                  refused_step_m=refused['step_norm_m'], refused_backtrack=refused['backtrack'],
                  accepted_checks=[crossings(accepted, n) for n in counts], refused_checks=rejected_checks,
                  exact_crossing_parameters=parameters.tolist(), crossing_spacing_um=abs(np.diff(points)[0])*mm*1000,
                  accepted_neck_parameters=closest.x.tolist(), accepted_neck_clearance_nm=gap_nm)
    return report, accepted, candidate


def draw(report, accepted, refused, mm):
    fig, (whole, gap) = plt.subplots(1, 2, figsize=(8.7, 3.6), constrained_layout=True)
    z = accepted.values(8192)*mm
    centre = np.asarray(report['accepted_neck_parameters'])
    origin = at(accepted, centre).mean()
    whole.plot(z.real, z.imag, color=GREEN)
    whole.scatter([origin.real*mm], [origin.imag*mm], c=ORANGE, zorder=3)
    whole.set(xlabel='x (mm)', ylabel='y (mm)', title='Stage-four entry', aspect='equal')
    direction = at(accepted, centre[:1], 1)[0]
    direction /= abs(direction)
    normal_gap = (np.diff(at(accepted, centre))[0]/direction).imag
    for curve, color, label in [(accepted, GREEN, 'Accepted'), (refused, ORANGE, 'Refused at twice the step')]:
        branches = []
        for t in centre:
            z = (at(curve, np.linspace(t-.006, t+.006, 1501))-origin)/direction * mm * 1000
            order = np.argsort(z.real)
            x = np.linspace(-75, 75, 501)
            assert z.real.min() < x.min() < x.max() < z.real.max()
            branches.append(np.interp(x, z.real[order], z.imag[order]))
        gap.plot(x, np.sign(normal_gap)*(branches[1]-branches[0])*1000, color=color, label=label)
    gap.axhline(0, color=GRAY, ls=':', lw=1)
    gap.set(xlabel='Distance along the neck (µm)', ylabel='Signed gap between branches (nm)',
            title='The refused trial crosses twice')
    gap.legend(frameon=False, fontsize=8)
    fig.savefig(ACTIVITY/'figures/cylinder_trial_crossing.png', dpi=180)
    plt.close(fig)


def main():
    fit = read(MEASURED/'fit.json')
    mm = fit['geometry_settings']['length_unit_m'] * 1000
    stages = {s['stage']: read(MEASURED/'local'/(s['stage']+'.json')) for s in fit['stages']}
    accepted_checks = []
    for name, stage in stages.items():
        for row in stage['history']:
            curve = curve_from(row['coefficients'])
            # This is the exact check used by the slider. Also check fine-grid proper crossings.
            checks.check_intersection(curve.nodes(grid_size(curve.band)).points)
            simple = LinearRing(curve.nodes(32768).points).is_simple
            accepted_checks.append(dict(stage=name, step=row['iteration'], sample_count=grid_size(curve.band),
                                        fine_ring_simple=simple))
    stage4 = curve_from(stages['ladder_4_real']['history'][0]['coefficients'])
    stage3 = curve_from(stages['ladder_3_real']['curve'])
    assert np.array_equal(resize(stage3, stage4.band).coefficients, stage4.coefficients)
    reports = []
    (ACTIVITY/'figures').mkdir(exist_ok=True)
    for name in ['ladder_3_real', 'full_1_M11']:
        report, accepted, candidate = replay(stages[name], mm)
        reports.append(report)
        if name == 'ladder_3_real':
            draw(report, accepted, candidate, mm)
    reasons = {name: dict(Counter(t.get('reason', t['status']) for t in stage['trials']))
               for name, stage in stages.items()}
    write(OUT/'measured_trial_crossings.json', dict(accepted_states=accepted_checks,
                                                    trial_counts=reasons, replays=reports))
    rows = []
    for source in sorted((ROOT/'results/bem/default_clean_uc_fc').glob('*/fit.json')):
        result = read(source)
        passed = read(source.parent/'score.json')['area_error'] <= .05
        settings = stage_settings(result['decisions'])
        all_trials = result['geometry_work']['trial_constructions']
        refused = result['geometry_work']['refused_trials']
        candidates = []
        for stage in result['stages']:
            name = stage['stage']
            solved = stage['work']['solves'].get(name+':candidate', 0)
            candidates.append(solved / len(settings[name]['weights']))
        all_accounted = all(x.is_integer() for x in candidates) and sum(candidates) + refused == all_trials
        for stage in result['stages']:
            label = stage['stage']
            trials = stage.get('trials')
            rows.append(dict(case=result['case'], passed=passed, stage=label, stop=stage['stop'],
                             steps=stage['accepted_steps'], proposals=stage['geometry_proposals'],
                             candidate_solves=stage['work']['solves'].get(label+':candidate', 0),
                             fit_trial_constructions=all_trials, fit_slider_refusals=refused,
                             fit_candidates_in_full_frequency_batches=sum(candidates),
                             fit_slider_refusals_account_for_all_unsolved=all_accounted,
                             trials_saved=trials is not None,
                             refusal_reasons=None if trials is None else dict(Counter(
                                 t['reason'] for t in trials if t['status'] == 'refused'))))
    write_rows(OUT/'original_trial_coverage.csv', rows)


if __name__ == '__main__':
    main()
