"""B7 table derivatives and B5/B8 frequency blocks, including masked material fits."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest

from bem_inverse import Execution, FourierCurve, Observation, PlaneWaveAcquisition, Problem
from bem_inverse.b5_residual import evaluate_blocks
from bem_inverse.b7_data_jacobian import table_hadamard, hadamard
from bem_inverse.data_blocks import FrequencyBlocks
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings, forward_solve
from bem_inverse.geometry_selection import make_update
from bem_inverse.fit_stage import fit_stage
from bem_inverse.stage_types import FitStage, BackendConfig, stage_record
from bem_inverse.work import Ledger
from bem_inverse.material import MaterialUnknown
from test_table_forward import acquisition


def test_table_contraction_matches_each_paired_contraction():
    rng = np.random.default_rng(42)
    z = lambda shape: rng.normal(size=shape)+1j*rng.normal(size=shape)
    traces, reciprocal, weights = z((11, 3)), z((11, 19)), z((17, 4))
    table = table_hadamard(traces, reciprocal, weights, 5, -.67)
    for s in range(3):
        for r in range(19):
            paired = hadamard(traces[:, s:s+1], reciprocal[:, r:r+1], weights, 5, -.67)
            np.testing.assert_allclose(table[s, r], paired[0], atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize('masked', [False, True])
def test_table_derivative_matches_complete_slider_trial(masked):
    acq = acquisition(np.arange(21).reshape(3, 7)%3 != 0 if masked else None)
    obs = Observation(1., acq, np.ones(acq.data_shape), 1.)
    curve = FourierCurve.circle(.8, .15-.2j)
    from bem_inverse.continuation.geometry import resize
    curve = resize(curve, 8)
    context = ModalMuller(Execution(device='cpu', frequency_threads=1), ModalSettings(table_mode=True))
    update, trial = make_update('slider', 1., context.execution)
    space = update.prepare(curve, 3, 8)
    state = forward_solve(curve, obs, .33, 512, context=context)
    direction = np.arange(1, 8, dtype=float); direction /= np.linalg.norm(direction)
    analytic = context.derivative(state, update, space)@direction
    errors = []
    for h in [2e-3, 1e-3]:
        plus, _ = trial(h*direction, prepared=space)
        minus, _ = trial(-h*direction, prepared=space)
        a = forward_solve(plus, obs, .33, 512, context=context).prediction
        b = forward_solve(minus, obs, .33, 512, context=context).prediction
        errors.append(np.linalg.norm((a-b)/(2*h)-analytic)/np.linalg.norm(analytic))
    assert errors[1] < errors[0]*.35 and errors[1] < 1e-3


def test_frequency_blocks_equal_weight_and_derivative_order():
    observations = [SimpleNamespace(scattered=np.ones(n)*(1+2j)) for n in [2, 7]]
    layout = FrequencyBlocks.from_observations(observations, [.5, .5])
    prediction = tuple(1.1*o.scattered for o in observations)
    evaluation = evaluate_blocks(None, prediction, (), layout)
    assert evaluation.loss == pytest.approx(.005)
    assert evaluation.relative_l2 == pytest.approx(.1)
    assert layout.maximum_relative(prediction) == pytest.approx(.1)
    assert layout.offsets.tolist() == [0, 2, 9]
    derivatives = tuple(np.c_[o.scattered, 2j*o.scattered] for o in observations)
    direction = np.array([.3, -.4])
    h = 1e-5
    shifted = tuple(p+h*d@direction for p, d in zip(prediction, derivatives))
    difference = (evaluate_blocks(None, shifted, (), layout).residual-evaluation.residual)/h
    np.testing.assert_allclose(layout.normalize(derivatives)@direction, difference, atol=1e-11)


def test_variable_acquisition_requires_explicit_problem_option():
    acq = acquisition()
    other = PlaneWaveAcquisition(acq.directions[:2], acq.receivers)
    observations = tuple(Observation(k, a, np.ones(a.data_shape), k) for k, a in [(1., acq), (2., other)])
    with pytest.raises(ValueError, match='one acquisition'):
        Problem(FourierCurve.circle(), observations, None, .33)
    Problem(FourierCurve.circle(), observations, None, .33, allow_variable_acquisition=True)
    stage = FitStage('table', observations, (.5, .5), 3, 8, 512, 2, resolution_kind='modal', ragged_data=True)
    assert stage_record(stage)['data_offsets'] == [0, 21, 35]
    assert 'ragged_data' not in stage_record(replace(stage, ragged_data=False))


def test_ragged_material_column_and_entry_reuse_with_radius_model():
    from test_resolution_resume import ScalarUpdate, scalar_trial
    from bem_inverse.physics import Prediction
    class Physics:
        execution = SimpleNamespace(frequency_threads=1)
        def forward(self, curve, obs, contrast, nodes):
            radius = curve.coefficients[-1].real
            return Prediction(np.full(obs.scattered.size, contrast*radius*obs.wavenumber, complex), {},
                              (contrast, obs.wavenumber))
        def derivative(self, state, update, space):
            eta, k = state._handle
            return np.full((state.prediction.size, 1), eta*k, complex)
    observations = tuple(SimpleNamespace(scattered=np.full(n, .6*1.6*k, complex), wavenumber=k)
                         for n, k in [(2, 1.), (3, 2.)])
    stage = FitStage('ragged', observations, (.5, .5), 0, 1, 8, 2, 100, ragged_data=True)
    physics = Physics()
    def run(entry=None, material=None):
        ledger = Ledger(cap=500, clock=lambda: 0., endpoint_reserve=0)
        ledger.begin_stage(stage.label, stage.quota)
        return fit_stage(FourierCurve.circle(1.8) if entry is None else entry.curve,
                         stage, .5, ScalarUpdate(), BackendConfig(), ledger, physics=physics,
                         forward_solve=physics.forward, geometry_update=scalar_trial,
                         retain_final=True, entry=None if entry is None else entry.final_entry,
                         material=material)
    material_result = run(material=MaterialUnknown())
    assert material_result.accepted_steps and material_result.contrast != .5
    initial = run()
    repeated = run(initial)
    assert repeated.entry_reused and repeated.accepted_steps
