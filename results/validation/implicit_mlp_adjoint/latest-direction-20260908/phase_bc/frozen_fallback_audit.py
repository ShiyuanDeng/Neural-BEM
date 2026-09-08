"""Audit all 0..14 frozen production fallback halvings without saving weights."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT / 'solvers')]
import run_sdf_inverse_comparison as driver
from sdf_inverse.models import SirenImplicitField2D, build_siren_parameter_controller
from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from sdf_inverse.optimization import ComplexScatteredData, normalized_complex_residual
from sdf_inverse.forward import predict_paired_response
from sdf_inverse.implicit_adjoint import implicit_mlp_data_gradient, _eikonal, _flatten_gradient
from sdf_inverse.neural_optimization import maximum_curve_set_distance


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('frozen_fallback_metrics.json')
    folder = ROOT / 'results/validation/implicit_mlp_adjoint/rerun-20260907/star-bw96'
    metrics = json.loads((folder / 'metrics.json').read_text())
    saved = torch.load(folder / 'kress_model.pt', weights_only=True, map_location='cpu')
    constructor = dict(saved['constructor']); constructor['dtype'] = torch.float64
    model = SirenImplicitField2D(**constructor); model.load_state_dict(saved['state_dict'])
    controller = build_siren_parameter_controller(model); theta = controller.parameter_vector()
    geometry = OrderedSDFGeometryConfig(**saved['geometry_config']); config = saved['optimizer_config']
    archive = np.load(folder / 'kress_responses.npz')
    frequencies = metrics['train_frequencies_ghz']; experiment = metrics['experiment']
    columns = [int(np.where(np.isclose(archive['frequencies_ghz'], f))[0][0]) for f in frequencies]
    problem = driver._build_problem(frequencies, np.array(experiment['source_points_m']), np.array(experiment['receiver_points_m']))
    data = ComplexScatteredData(problem, archive['exact_scattered_response'][:, columns])
    rng = np.random.default_rng(config['random_seed']); bounds = np.array(geometry.bounds)
    points = torch.tensor(rng.uniform(bounds[0], bounds[1], (config['regularization_samples'], 2)), dtype=torch.float64)
    started = perf_counter()
    evaluations = 0

    def evaluate():
        nonlocal evaluations
        evaluations += 1
        forward = predict_paired_response(model, problem, geometry, solver='kress', retain_kress_state=True)
        residual, relative = normalized_complex_residual(forward.scattered_response, data.observed_scattered_response)
        loss = float(.5 * (residual @ residual))
        eikonal = float(_eikonal(model, points, create_graph=False).detach())
        return forward, loss, eikonal, loss + config['eikonal_weight'] * eikonal

    forward, loss, eikonal, objective = evaluate()
    data_gradient, diagnostic = implicit_mlp_data_gradient(model, data, geometry, forward_result=forward)
    parameters = tuple(model.parameters())
    regularizer_gradient = _flatten_gradient(torch.autograd.grad(config['eikonal_weight'] * _eikonal(model, points, create_graph=True), parameters, allow_unused=True), parameters)
    gradient = data_gradient + regularizer_gradient
    proposal = controller.project(theta - gradient * (config['learning_rate'] / max(float(np.max(np.abs(gradient))), 1.))) - theta
    result = {
        'scope': 'Every unchanged steepest-descent fallback trial from one frozen checkpoint; Adam historical moments are not replayed.',
        'checkpoint': str(folder.relative_to(ROOT) / 'kress_model.pt'),
        'checkpoint_sha256': hashlib.sha256((folder / 'kress_model.pt').read_bytes()).hexdigest(),
        'created_utc': datetime.now(timezone.utc).isoformat(), 'git': driver._git_provenance(),
        'acquisition': '8 paired source/receiver rows; diagonal only', 'source_count': 8, 'receiver_count': 8,
        'train_frequencies_ghz': frequencies, 'holdout_frequencies_ghz': [],
        'geometry_config': saved['geometry_config'], 'optimizer_config': config,
        'diagnostic_max_backtracks': 14, 'meaningful_boundary_step_floor_m': 1e-4,
        'step_floor_policy': 'reporting only; an accepted step below 0.1 mm is a crawl, not recovery evidence',
        'loss': loss, 'saved_loss': saved['training_loss'], 'objective': objective,
        'data_gradient_norm': float(np.linalg.norm(data_gradient)),
        'weighted_eikonal_gradient_norm': float(np.linalg.norm(regularizer_gradient)),
        'total_gradient_norm': float(np.linalg.norm(gradient)),
        'gradient_diagnostics': diagnostic, 'trials': [],
    }
    def flush():
        result['forward_evaluations'] = evaluations
        result['wall_seconds'] = perf_counter() - started
        output.write_text(json.dumps(result, indent=2) + '\n')
    flush()
    for backtrack in range(15):
        step = controller.project(theta + config['backtrack_factor']**backtrack * proposal) - theta
        controller.assign(theta + step)
        trial = {'backtracks': backtrack, 'maximum_weight_step': float(np.max(np.abs(step))), 'accepted': False, 'rejection_reasons': []}
        try:
            candidate, candidate_loss, candidate_eikonal, candidate_objective = evaluate()
            drift = maximum_curve_set_distance(forward.geometry_build.curve.points, candidate.geometry_build.curve.points)
            if drift > config['maximum_boundary_step_m']:
                trial['rejection_reasons'].append('boundary_motion_limit')
            if not (data_gradient @ proposal < 0 and candidate_loss < loss and candidate_loss <= loss + config['armijo_fraction'] * float(data_gradient @ step)):
                trial['rejection_reasons'].append('data_armijo')
            if not (gradient @ proposal < 0 and candidate_objective <= objective + config['armijo_fraction'] * float(gradient @ step)):
                trial['rejection_reasons'].append('regularized_armijo')
            trial.update(loss=candidate_loss, objective=candidate_objective, eikonal_loss=candidate_eikonal,
                         relative_loss_decrease=(loss - candidate_loss) / loss,
                         boundary_movement_m=float(drift), meaningful_boundary_step=bool(drift >= 1e-4),
                         conversion_error_m=candidate.geometry_build.maximum_conversion_error_m,
                         conversion_refinement_change_m=candidate.geometry_build.conversion_refinement_change_m,
                         accepted=not trial['rejection_reasons'])
        except OrderedSDFGeometryError as error:
            trial.update(rejection_reasons=list(getattr(error, 'rejection_reasons', ('extraction_topology',))),
                         error=f'{type(error).__name__}: {error}',
                         conversion_error_m=getattr(error, 'conversion_error_m', None),
                         conversion_refinement_change_m=getattr(error, 'conversion_refinement_change_m', None))
        finally:
            controller.assign(theta)
        result['trials'].append(trial)
        flush(); print(trial, flush=True)
    result['first_accepted_beyond_historical_8'] = next((trial for trial in result['trials'] if trial['accepted'] and trial['backtracks'] > 8), None)
    result['rejection_reason_counts'] = dict(Counter(reason for trial in result['trials'] for reason in trial['rejection_reasons']))
    result['stop_reason'] = 'completed_frozen_diagnostic_budget'
    result['checkpoint_weights_restored_exactly'] = bool(np.array_equal(theta, controller.parameter_vector()))
    flush()


if __name__ == '__main__':
    main()
