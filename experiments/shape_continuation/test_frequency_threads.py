"""SPD-010: threaded frequency solves give the serial values and ledger order exactly."""
import numpy as np
import pytest

from . import lm_backend
from .forward import ordered_calls
from .geometry import FourierCurve
from .lm_backend import BackendConfig, Ledger, Objective, fit_stage
from .test_lm_backend import observations, stage
from .updates import BorgesUpdate

THREADS = (1, 3, 8)
WAVENUMBERS = (.8, 1.0, 1.25, 1.5, 1.8)


@pytest.fixture(autouse=True)
def cpu_reference(monkeypatch):
    """SPD-010's exactness claims are about the CPU reference; CUDA tests opt in explicitly."""
    monkeypatch.setenv("SC_FORWARD_BACKEND", "cpu")


def record(ledger):
    snapshot = ledger.snapshot()
    snapshot.pop("seconds")
    return snapshot


def test_ordered_calls_consume_in_order_and_stop_at_the_first_failure():
    def square(i):
        if i == 5:
            raise FloatingPointError(i)
        return i * i

    for threads in THREADS:
        seen = []
        with ordered_calls(square, range(10), threads) as calls:
            with pytest.raises(FloatingPointError):
                for index, call in enumerate(calls):
                    seen.append(index)
                    assert call() == index * index
        assert seen == list(range(6))


def test_objective_values_and_work_do_not_depend_on_thread_count(monkeypatch):
    contrast = .5
    obs = observations(FourierCurve(np.array([.08, .1 + .05j, 1.15])), WAVENUMBERS, contrast)
    update = BorgesUpdate(1.0)
    curve, _ = update.regauge(FourierCurve.circle(1.0), 24)
    fit = stage(obs)
    results = []
    for threads in THREADS:
        monkeypatch.setenv("SC_FREQUENCY_THREADS", str(threads))
        ledger = Ledger(cap=4000, seconds=600)
        ledger.begin_stage("s", None)
        objective = Objective(fit, contrast, BackendConfig(), ledger)
        production = objective.production(curve, "initial_objective")
        space = update.prepare(curve, fit.update_modes, fit.curve_modes)
        jacobian = objective.jacobian(production, update, space)
        refined = objective.refined(curve)
        results.append((production.prediction, production.residual, jacobian, refined.prediction,
                        record(ledger)))
    for other in results[1:]:
        for a, b in zip(results[0][:4], other[:4]):
            assert np.array_equal(a, b)
        assert other[4] == results[0][4]


def test_failure_charges_and_discards_exactly_as_the_serial_loop(monkeypatch):
    contrast = .5
    obs = observations(FourierCurve.circle(1.1), WAVENUMBERS, contrast)
    curve = FourierCurve.circle(1.0)
    solve = lm_backend.solve

    def failing(shape, wavenumber, *args, **kwargs):
        if wavenumber == WAVENUMBERS[2]:
            raise FloatingPointError("injected")
        return solve(shape, wavenumber, *args, **kwargs)

    monkeypatch.setattr(lm_backend, "solve", failing)
    records = []
    for threads in THREADS:
        monkeypatch.setenv("SC_FREQUENCY_THREADS", str(threads))
        ledger = Ledger(cap=4000, seconds=600)
        ledger.begin_stage("s", None)
        assert Objective(stage(obs), contrast, BackendConfig(), ledger).production(curve, "trial") is None
        records.append(record(ledger))
    assert records[0]["solves"] == {"s:trial": 3} and records[0]["failed"] == {"s:trial": 1}
    assert all(r == records[0] for r in records[1:])


def test_fit_stage_trajectory_is_bit_identical_across_thread_counts(monkeypatch):
    contrast = .5
    obs = observations(FourierCurve(np.array([.08, .1 + .05j, 1.15])), (1.0, 1.25, 1.5), contrast)
    update = BorgesUpdate(1.0)
    initial, _ = update.regauge(FourierCurve.circle(1.0), 24)
    runs = []
    for threads in THREADS:
        monkeypatch.setenv("SC_FREQUENCY_THREADS", str(threads))
        ledger = Ledger(cap=4000, seconds=600)
        ledger.begin_stage("s", None)
        result = fit_stage(initial, stage(obs, iterations=4), contrast, update,
                           BackendConfig(step_bounds_m=(.12, .18, .06)), ledger)
        for row in result.history:
            row["work"].pop("seconds")
        runs.append((result.curve.coefficients, result.history, result.trials, result.acceptance_checks,
                     result.outcome, result.stop_reason))
    for other in runs[1:]:
        assert np.array_equal(runs[0][0], other[0])
        assert other[1:] == runs[0][1:]


def test_threads_share_the_fit_local_validation_cache_with_serial_counts(monkeypatch):
    from ordered_boundary.validation_cache import validation_cache
    contrast = .5
    obs = observations(FourierCurve.circle(1.1), WAVENUMBERS, contrast)
    curve = FourierCurve.circle(1.0)
    counts = []
    for threads in THREADS:
        monkeypatch.setenv("SC_FREQUENCY_THREADS", str(threads))
        ledger = Ledger(cap=4000, seconds=600)
        ledger.begin_stage("s", None)
        with validation_cache("cache") as cache:
            Objective(stage(obs), contrast, BackendConfig(), ledger).production(curve, "trial")
            counts.append(dict(cache.counts))
    assert counts[0]["self_intersection.misses"] == 1
    assert all(c == counts[0] for c in counts[1:])


def test_cuda_backend_objective_agrees_with_the_cpu_reference(monkeypatch):
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable")
    contrast = .5
    obs = observations(FourierCurve(np.array([.08, .1 + .05j, 1.15])), WAVENUMBERS, contrast)
    update = BorgesUpdate(1.0)
    curve, _ = update.regauge(FourierCurve.circle(1.0), 24)
    fit = stage(obs)
    results = {}
    for backend in ("cpu", "cuda"):
        monkeypatch.setenv("SC_FORWARD_BACKEND", backend)
        ledger = Ledger(cap=4000, seconds=600)
        ledger.begin_stage("s", None)
        objective = Objective(fit, contrast, BackendConfig(), ledger)
        production = objective.production(curve, "initial_objective")
        assert all(isinstance(state.matrix, np.ndarray) for state in production.forwards)
        space = update.prepare(curve, fit.update_modes, fit.curve_modes)
        results[backend] = (production.prediction, objective.jacobian(production, update, space),
                            objective.refined(curve).prediction, record(ledger))
    for cpu, cuda in zip(results["cpu"][:3], results["cuda"][:3]):
        assert np.linalg.norm(cuda - cpu) <= 1e-12 * np.linalg.norm(cpu)
    assert results["cuda"][3] == results["cpu"][3]


def test_cuda_backend_matches_the_cpu_reference_for_two_objects(monkeypatch):
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable")
    from gpr_bem_kress.cuda_assembly import DeviceFactors
    from .forward import shape_jacobian, solve
    from .test_lm_backend import acquisition
    from .test_multi_object import pair
    scene, update = pair()
    space = update.prepare(scene, 2, 16)
    results = {}
    for backend in ("cpu", "cuda"):
        monkeypatch.setenv("SC_FORWARD_BACKEND", backend)
        state = solve(scene, 1.3, .4, acquisition(8), 128)
        assert isinstance(state.factors, DeviceFactors) == (backend == "cuda")
        results[backend] = (state.prediction, shape_jacobian(state, update.velocities(space, state.curve)))
    for cpu, cuda in zip(results["cpu"], results["cuda"]):
        assert np.linalg.norm(cuda - cpu) <= 1e-12 * np.linalg.norm(cpu)
