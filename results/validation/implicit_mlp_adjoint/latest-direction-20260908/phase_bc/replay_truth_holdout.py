"""Verify post-optimization holdout replay on the already completed three-step run."""
import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'solvers')]
import run_sdf_inverse_comparison as driver
from sdf_inverse.models import SirenImplicitField2D, build_siren_parameter_controller
from sdf_inverse.geometry import OrderedSDFGeometryConfig

metrics = json.loads((OUT / 'start-at-truth/metrics.json').read_text())
row = metrics['solvers']['kress']
saved = torch.load(OUT / 'start-at-truth/kress_model.pt', weights_only=True, map_location='cpu')
constructor = dict(saved['constructor']); constructor['dtype'] = torch.float64
model = SirenImplicitField2D(**constructor); model.load_state_dict(saved['state_dict'])
controller = build_siren_parameter_controller(model)
final = controller.parameter_vector().copy()
with (OUT / 'start-at-truth/kress_trajectory.csv').open() as stream:
    iterations = tuple(SimpleNamespace(iteration=int(record['iteration']), parameter_vector=np.array([float(record['raw_' + name]) for name in controller.names])) for record in csv.DictReader(stream))
experiment = metrics['experiment']
problem = driver._build_problem(metrics['holdout_frequencies_ghz'], np.array(experiment['source_points_m']), np.array(experiment['receiver_points_m']))
archive = np.load(OUT / 'start-at-truth/kress_responses.npz')
truth = archive['exact_scattered_response'][:, len(metrics['train_frequencies_ghz']):]
report = driver._replay_accepted_holdout(model, controller, SimpleNamespace(iterations=iterations), problem, truth, OrderedSDFGeometryConfig(**saved['geometry_config']), solver='kress')
expected = np.array([record['holdout_relative_l2'] for record in row['accepted_iterate_diagnostics']])
actual = np.array([record['holdout_relative_l2'] for record in report['records']])
report.update(
    scope='Post-optimization evaluation of saved accepted weights; no neural inverse rerun.',
    original_callback_holdout_relative_l2=expected.tolist(),
    maximum_absolute_holdout_difference=float(np.max(np.abs(actual - expected))),
    same_holdout_values=bool(np.allclose(actual, expected, rtol=2e-12, atol=1e-13)),
    final_accepted_weights_restored_exactly=bool(np.array_equal(final, controller.parameter_vector())),
    original_inverse_callback_inclusive_seconds=row['inverse_wall_seconds'],
    original_holdout_forward_seconds=row['evaluation_only_holdout_forward_seconds'],
    original_inverse_minus_measured_holdout_forward_seconds=row['inverse_wall_seconds'] - row['evaluation_only_holdout_forward_seconds'],
    timing_note='Original experiment ran before post-optimization replay isolation. Its original inverse time includes holdout callbacks; subtracting measured holdout forward time leaves a small unmeasured callback bookkeeping overhead. Future driver runs time holdout replay entirely separately.',
)
(OUT / 'post_optimization_holdout_replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if not report['same_holdout_values'] or not report['final_accepted_weights_restored_exactly']:
    raise SystemExit('Accepted holdout replay failed validation')
