"""Data-only initialization for the frozen benchmark's optional CLI modes."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.exploratory_continuation.indicators import threshold_circles
from experiments.initialization_followup.run import full_indicators, seed_state
from gpr_bem_kress import Material
from sdf_inverse.radial_topology import evaluate_current_domain_topological_derivative
from sdf_inverse.work_accounting import collect_work


def initialize(data, config, *, method, matrix_path=None):
    """No scene, target, held-out samples, or target count enters this call."""
    if method not in ('topo', 'lsm'):
        raise ValueError('Data-only initialization must be topo or lsm.')
    if method == 'lsm' and matrix_path is None:
        raise ValueError('LSM needs explicit full-matrix input; paired observations cannot supply it.')
    p = data.forward_problem
    center, radius = np.asarray(config.inspection_center), config.inspection_radius_m
    x, y = np.meshgrid(np.linspace(center[0]-radius, center[0]+radius, 81),
                       np.linspace(center[1]-radius, center[1]+radius, 81))
    points = np.stack((x, y), axis=-1)
    metadata = dict(method=method, threshold=.6, grid_size=81,
        uses_truth=False, uses_holdout=False, input_contract='original paired training')
    with collect_work() as work:
        if matrix_path is None:
            values = evaluate_current_domain_topological_derivative(
                None, data, points.reshape(-1, 2)).values.reshape(x.shape)
        else:
            matrix_path = Path(matrix_path)
            record = json.loads(matrix_path.with_suffix('.json').read_text())
            digest = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
            if record['matrix_sha256'] != digest:
                raise ValueError('Full-matrix qualification hash does not match its input.')
            if max(record['refinement_relative'], record['original_pair_relative']) > 1e-5:
                raise ValueError('Full-matrix observations did not qualify.')
            with np.load(matrix_path, allow_pickle=False) as saved:
                if p.num_frequencies != 1 or bool(saved['legacy_atlas_constants']):
                    raise ValueError('This adapter requires one exactly matched physical frequency.')
                for name in ('sources', 'receivers'):
                    np.testing.assert_array_equal(saved[name], getattr(p, name[:-1]+'_points'))
                for name, value in [('strength', p.source_strengths[0]),
                    ('frequency_hz', p.angular_frequencies[0]/(2*np.pi)),
                    ('eps0', p.eps0), ('mu0', p.mu0),
                    ('exterior_epsr', p.exterior.epsr), ('interior_epsr', p.interior.epsr)]:
                    if not np.isclose(saved[name], value, rtol=1e-13, atol=0):
                        raise ValueError('Full-matrix input mismatch: '+name)
                matrix = saved['observed']
                diagonal_error = np.linalg.norm(np.diag(matrix)-data.observed_scattered_response[:, 0])/np.linalg.norm(data.observed_scattered_response[:, 0])
                if diagonal_error > 1e-5:
                    raise ValueError('Full-matrix diagonal differs from original training data.')
                ke = Material(p.exterior.epsr).wavenumber(p.angular_frequencies[0], p.eps0, p.mu0)
                ki = Material(p.interior.epsr).wavenumber(p.angular_frequencies[0], p.eps0, p.mu0)
                sample, td = full_indicators(matrix, p.source_points, p.receiver_points,
                    points, ke, ki, complex(p.source_strengths[0]))
                values = -sample['indicator'].reshape(x.shape) if method == 'lsm' else td
            metadata.update(input_contract='explicit additional full-matrix initialization data; fitting remains paired',
                matrix_path=str(matrix_path.resolve()), matrix_sha256=digest,
                original_pair_relative=float(diagonal_error), added_complex_measurements=matrix.size-p.num_pairs,
                lsm_discrepancy_attained_fraction=float(sample['discrepancy_attained'].mean()),
                lsm_relative_rhs_discrepancy=.01)
        seeds, _ = threshold_circles(points, values, center=center,
            inspection_radius=radius, threshold=.6)
        state = seed_state(seeds)
    metadata.update(seeds=[asdict(s) for s in seeds], work=work.snapshot())
    return state, metadata


def apply_initializer(output, spec, method, matrix_directory=None):
    import run_topology_scene_benchmark as benchmark
    if method == 'current':
        return
    config = benchmark.controller_config(spec, 'H')
    for scene in spec['scenes']:
        data, _ = benchmark.shared_data(output, scene, spec)
        matrix_path = None if matrix_directory is None else Path(matrix_directory)/(scene['id']+'.npz')
        state, record = initialize(data, config, method=method, matrix_path=matrix_path)
        directory = output/'scenes'/scene['id']
        original = directory/'initial_state.json'
        (directory/'original_initial_state.json').write_bytes(original.read_bytes())
        benchmark.driver.write_json(original, benchmark.driver.serialize_state(state))
        benchmark.driver.write_json(directory/'initializer.json', record)
