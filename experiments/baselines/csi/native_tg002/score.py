"""Native CSI scoring and two pre-fit truth-image self-tests."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy.io import loadmat

from experiments.baselines.csi.registered_metrics import score_field
from experiments.comparison import scoring as G
from . import fit as F


def image_scores(case, chi_image, x_m, y_m):
    """x is the first MATLAB index; susceptibility is relative to background."""
    _, truth, true_image = G.truth_for(case)
    x = np.asarray(x_m, float).ravel(); y = np.asarray(y_m, float).ravel()
    values = np.asarray(chi_image)
    if values.shape != (len(x), len(y)) or not np.isfinite(values).all():
        raise ValueError('invalid image shape or nonfinite image')
    scores, image = score_field(values, values.shape, x, y, truth)
    return dict(area_error=scores[0]['area_error'],
                threshold_sensitivity={f'area_error_at_{row["fraction"]:g}': row['area_error'] for row in scores[1:]},
                material_l2=float(np.linalg.norm(image-true_image)/np.linalg.norm(true_image)),
                thresholds=scores, susceptibility='relative to background; true value 3',
                protocol=G.PROTOCOL)


def residual(predicted, observed):
    predicted = np.asarray(predicted).ravel(); observed = np.asarray(observed).ravel()
    if predicted.shape != (24,) or observed.shape != (24,):
        raise ValueError('exactly 24 readings required')
    if not np.isfinite(predicted).all() or not np.isfinite(observed).all() or np.linalg.norm(observed) == 0:
        raise ValueError('nonfinite field or zero observed norm')
    return float(np.linalg.norm(predicted-observed)/np.linalg.norm(observed))


def bem_rows(root):
    rows = []
    for case in ['circle__c4', 'kite__c4']:
        folder = F.REPO/'results/bem/default_clean_uc_sf0.5'/case
        score = F.read(folder/'score.json'); fit = F.read(folder/'fit.json')
        rows.append(dict(case=case, area_error=score['area_error'], material_l2=score['material_l2'],
                         field_residual=float(fit['residual'][0]), runtime_seconds=fit.get('case_seconds'),
                         sources={str(p): F.sha(p) for p in [folder/'score.json', folder/'fit.json']}))
    F.write(root/'checks/bem_rows.json', dict(rows=rows))


def self_tests(root):
    """No inversion: re-predict the adapter's exact same dual-cell image."""
    folder = root/'checks/run_self_tests'
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'check.json').exists():
        raise RuntimeError('self-test result exists; keep it, do not silently rerun')
    started = F.now()
    result = dict(passed=False, started_utc=started, no_fit_started=True)
    try:
        source = root/'checks/forward_circle__c4__clean/truth_1.25mm.mat'
        reference_path = source.with_name('check.json')
        reference = F.read(reference_path)
        if reference.get('passed') is not True:
            raise RuntimeError('adapter forward check has not passed')
        data = loadmat(source, simplify_cells=True)
        result['fixture_sha256'] = F.sha(source)
        result['forward_check_sha256'] = F.sha(reference_path)
        scored = image_scores('circle__c4', data['chi_image'], data['x_m'], data['y_m'])
        # A 1.25 mm raster, then interpolation to 201 cells, has discretization error.
        # Two percent is a near-zero frame check, not a reconstruction pass limit.
        result['area_error_limit'] = .02
        result['true_image_scores'] = scored
        result['area_passed'] = scored['area_error'] < .02
        sample = F.resource_sample()
        F.write(folder/'launch_resources.json', sample)
        if not sample['allowed']:
            raise RuntimeError('MATLAB active or less than 32 GiB available for self-test')
        supported, probe = F.scope_supported()
        F.write(folder/'scope_probe.json', dict(supported=supported, output=probe))
        # systemd worked during preparation; do not run an unbounded prediction.
        if not supported:
            raise RuntimeError('self-test requires working 8 GiB systemd scope')
        shutil.copyfile(source, folder/'truth_input.mat')
        command = ['systemd-run', '--user', '--scope', '-p', 'MemoryMax=8G', '-p', 'MemorySwapMax=0',
                   *F.matlab_command('self_test', root/'inputs/circle__c4__clean', folder, 0)]
        with (folder/'matlab.log').open('x') as log:
            run = subprocess.run(command, cwd=F.REPO, env=dict(os.environ, CUDA_VISIBLE_DEVICES='',
                                 OMP_NUM_THREADS='8', MKL_NUM_THREADS='8'), stdout=log, stderr=subprocess.STDOUT)
        result['returncode'] = run.returncode
        if run.returncode:
            raise RuntimeError('prediction self-test failed; see matlab.log')
        actual = loadmat(folder/'prediction.mat', simplify_cells=True)
        for key in ['chi_image', 'x_m', 'y_m', 'observed_native']:
            if not np.allclose(actual[key], data[key], rtol=1e-12, atol=1e-14):
                raise ValueError(f'self-test changed fixture or frame: {key}')
        actual_error = residual(actual['predicted_native'], actual['observed_native'])
        saved_error = residual(data['predicted_native'], data['observed_native'])
        expected = float(reference['coarse_relative_error'])
        result.update(field_residual=actual_error, saved_field_residual=saved_error,
                      adapter_coarse_relative_error=expected,
                      prediction_relative_difference=float(np.linalg.norm(actual['predicted_native']-data['predicted_native']) /
                                                           np.linalg.norm(data['observed_native'])),
                      residual_match_tolerance=1e-10)
        result['prediction_passed'] = abs(actual_error-expected) <= 1e-10 and abs(saved_error-expected) <= 1e-10
        result['passed'] = bool(result['area_passed'] and result['prediction_passed'] and
                                result['prediction_relative_difference'] <= 1e-10)
        bem_rows(root)
    except Exception as error:
        result['failure'] = repr(error)
        raise
    finally:
        result['finished_utc'] = F.now()
        F.write(folder/'check.json', result)
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise RuntimeError('native scoring self-tests did not pass')


def score(root, case, data):
    folder = root/'fits'/f'{case}__{data}'
    state = F.read(folder/'state.json')
    if state['state'] not in ('completed', 'failed'):
        raise RuntimeError('fit still active')
    result = dict(case=case, data=data, method='classical CSI', runtime_seconds=state['wall_seconds'],
                  peak_family_rss_bytes=state['peak_family_rss_bytes'], failures=[], scored_utc=F.now())
    if state['state'] == 'failed':
        result['failures'].append(state.get('failure', f'returncode {state.get("returncode")}'))
    final = folder/'final_image.mat'
    if final.exists():
        image = loadmat(final, simplify_cells=True)
        result.update(image_scores(case, image['chi_image'], image['x_m'], image['y_m']))
        result['native_fit_seconds'] = float(image['native_seconds'])
    else:
        result['failures'].append('final image missing')
    prediction = folder/'prediction.mat'
    if prediction.exists():
        fields = loadmat(prediction, simplify_cells=True)
        result['field_residual'] = residual(fields['predicted_native'], fields['observed_native'])
        result['field_readings'] = 24
    else:
        result.update(field_residual=None, field_readings=24)
        result['failures'].append('final-image prediction missing')
    cost_path = folder/'costs.json'
    history = F.read(cost_path)['rows'] if cost_path.exists() else []
    result['csi_own_costs'] = history[-1] if history else None
    result['csi_own_cost_note'] = 'printed rounded data/state costs; distinct from native field residual'
    F.write(folder/'score.json', result)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['circle__c4', 'kite__c4'])
    parser.add_argument('--data', choices=['clean', 'n1d0'], default='clean')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--copy-bem-rows', action='store_true')
    args = parser.parse_args(); root = args.run_dir.resolve()
    if args.self_test:
        self_tests(root)
    elif args.copy_bem_rows:
        (root/'checks').mkdir(parents=True, exist_ok=True)
        bem_rows(root)
    else:
        if args.case is None:
            parser.error('--case required for scoring')
        score(root, args.case, args.data)


if __name__ == '__main__':
    main()
