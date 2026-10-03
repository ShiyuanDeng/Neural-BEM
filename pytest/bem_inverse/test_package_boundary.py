"""The numerical API must work without research drivers or a repository cwd."""
import importlib
import os
from pathlib import Path
import pickle
import subprocess
import sys
import textwrap


ROOT = Path(__file__).resolve().parents[2]


def test_standalone_numerics_and_inverse_without_experiments(tmp_path):
    script = textwrap.dedent('''
        import importlib
        import importlib.abc
        import pkgutil
        import sys
        from dataclasses import replace
        import numpy as np

        class RejectResearch(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'experiments' or fullname.startswith(('experiments.', 'run_')):
                    raise AssertionError('Numerical package imported research code: '+fullname)

        sys.meta_path.insert(0, RejectResearch())
        import bem_inverse
        for module in pkgutil.walk_packages(bem_inverse.__path__, bem_inverse.__name__+'.'):
            importlib.import_module(module.name)
        from bem_inverse import FourierCurve, PointSourceAcquisition, Observation, Problem, Execution, fit
        from bem_inverse.geometry_selection import GEOMETRY_UPDATES, make_update
        from bem_inverse.geometry import resize
        from bem_inverse.physics import NodalKress
        from bem_inverse.modal_muller import ModalMuller, ModalSettings, token
        from bem_inverse.policy import CumulativePolicy, Operation

        class SmallBackend(NodalKress):
            def resolution_profile(self, storage_band):
                return dict(super().resolution_profile(storage_band), production=64, refined=128,
                            nodal_resolution=64)

        class ShortPolicy(CumulativePolicy):
            def operations(self, problem, physics):
                return (
                    Operation('audit', 'initial_audit', 'qualify start', 'start', 'fit'),
                    self._fit(problem, physics, 'standalone', problem.real, 1, 4, 300, iterations=2),
                    Operation('audit', 'final_audit', 'qualify endpoint', 'fit returned', 'return'),
                )

        execution = Execution(device='cpu', frequency_threads=1)
        physics = SmallBackend(execution)
        theta = np.linspace(0, 2*np.pi, 8, endpoint=False)
        scan = PointSourceAcquisition(5*np.column_stack((np.cos(theta), np.sin(theta))),
                                      5.5*np.column_stack((np.cos(theta+.03), np.sin(theta+.03))), 1e-6)
        truth = FourierCurve.circle()
        real = Observation(.6, scan, np.ones(8, complex)*1e-6, .25e9)
        damped = replace(real, wavenumber=.6*(1+.25j))
        real, damped = [replace(o, scattered=physics.evaluate(truth, o, .5, 128).prediction)
                        for o in (real, damped)]
        modal = ModalMuller(execution, ModalSettings(trace_minimum=16, trace_step=8, window_margin=16))
        np.testing.assert_allclose(modal.evaluate(truth, real, .5, token(16)).prediction,
                                   real.scattered, rtol=1e-8, atol=1e-15)
        for name in GEOMETRY_UPDATES:
            update = make_update(name, .05, execution)
            space = update.prepare(resize(truth, 4), 1, 4)
            np.testing.assert_array_equal(update.trial(space, np.zeros(3))[0].coefficients,
                                          space.curve.coefficients)
        problem = Problem(FourierCurve.circle(1.02), (real,), (damped,), .5)
        row = fit(problem, physics=physics, policy=ShortPolicy(fit_units=500, fit_seconds=60), output='run')
        assert row['outcome'] == 'COMPLETED_SCHEDULE', row['detail']
        assert row['initial_audit_passed'] and row['final_audit_passed']
        assert row['stages'][0]['accepted_steps'] > 0
        assert row['stages'][0]['final_loss'] < row['stages'][0]['initial_loss']
        assert not any(name == 'experiments' or name.startswith('experiments.') for name in sys.modules)
        print('Standalone nodal/modal fields, geometry choices and audited inverse passed.')
    ''')
    env = dict(os.environ, PYTHONPATH=str(ROOT/'solvers'), OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path, env=env,
                            text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout+'\n'+result.stderr
    assert (tmp_path/'run/fit_result.json').is_file()


def test_compatibility_modules_share_identity_and_mutations(monkeypatch):
    for name in ('problem', 'physics', 'policy', 'runner', 'geometry', 'geometry_selection',
                 'io', 'localization', 'full_matrix', 'damped_cuda', 'mie_grid', 'modal_geometry',
                 'modal_operator', 'modal_cuda', 'modal_muller', 'n_update', 'analytic_projection'):
        assert importlib.import_module('experiments.cleaned_interface.'+name) is importlib.import_module('bem_inverse.'+name)
    for name in ('geometry', 'geometry_runtime', 'forward', 'lm_backend', 'updates', 'validation'):
        assert importlib.import_module('experiments.shape_continuation.'+name) is importlib.import_module('bem_inverse.continuation.'+name)
    assert importlib.import_module('experiments.modal_atlas.mie_localize') is importlib.import_module('bem_inverse.mie_localize')

    from experiments.cleaned_interface import runner as old_runner
    from bem_inverse import runner
    marker = object()
    monkeypatch.setattr(old_runner, 'ProjectedUpdate', marker)
    assert runner.ProjectedUpdate is marker


def test_historical_class_lookups_and_new_pickle_roundtrip():
    from bem_inverse import FourierCurve, Problem
    # Protocol-0 GLOBAL lookups model the module names embedded in old pickles.
    assert pickle.loads(b'cexperiments.shape_continuation.geometry\nFourierCurve\n.') is FourierCurve
    assert pickle.loads(b'cexperiments.cleaned_interface.problem\nProblem\n.') is Problem
    curve = FourierCurve.circle(1.02, .03j)
    restored = pickle.loads(pickle.dumps(curve))
    import numpy as np
    np.testing.assert_array_equal(restored.coefficients, curve.coefficients)
    assert type(restored) is FourierCurve


def test_mixed_campaign_modules_export_canonical_geometry():
    for old, new, name in (
        ('nu003', 'spectral', 'SpectralProjectedUpdate'),
        ('nu005', 'certified', 'CertifiedSpectralUpdate'),
        ('nu006', 'batched', 'BatchedCertifiedUpdate'),
        ('nu007', 'device_certified', 'DeviceCertifiedUpdate'),
        ('n_reparam', 'n_reparam', 'reparameterize'),
    ):
        assert getattr(importlib.import_module('experiments.cleaned_interface.'+old), name) is getattr(
            importlib.import_module('bem_inverse.'+new), name)


def test_research_provenance_includes_extracted_implementations():
    from experiments.shape_continuation.run import provenance
    from experiments.shape_continuation.finite_path_study import frozen_sources
    from experiments.modal_atlas.contrast_screen import source_paths

    expected = {str(p.relative_to(ROOT)) for p in (ROOT/'solvers/bem_inverse').rglob('*.py')}
    assert expected
    assert expected <= provenance()['source_sha256'].keys()
    assert expected <= frozen_sources().keys()
    assert expected <= {str(p.relative_to(ROOT)) for p in source_paths()}
