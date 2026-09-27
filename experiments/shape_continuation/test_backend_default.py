"""SPD-012: CUDA is the default (auto) backend, with an exact CPU pin and OOM fallback."""
import numpy as np
import pytest

from gpr_bem_kress import cuda_assembly

from . import forward
from .forward import forward_backend, ordered_calls, shape_jacobian, solve
from .geometry import FourierCurve
from .test_lm_backend import acquisition

torch = pytest.importorskip("torch")
needs_cuda = pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
CURVE = FourierCurve(np.array([.08, .1 + .05j, 1.15]))
WAVENUMBERS = (.8, 1.0, 1.25, 1.5, 1.8)


def run(wavenumber=1.25):
    return solve(CURVE, wavenumber, .5, acquisition(), 96)


def test_selection_rules(monkeypatch):
    monkeypatch.delenv("SC_FORWARD_BACKEND", raising=False)
    assert forward_backend() == ("cuda" if cuda_assembly.available() else "cpu")
    monkeypatch.setenv("SC_FORWARD_BACKEND", "cpu")
    assert forward_backend() == "cpu"
    monkeypatch.setenv("SC_FORWARD_BACKEND", "gpu")
    with pytest.raises(ValueError):
        forward_backend()
    monkeypatch.setattr(cuda_assembly, "available", lambda: False)
    monkeypatch.setenv("SC_FORWARD_BACKEND", "auto")
    assert forward_backend() == "cpu" and run().backend == "cpu"
    monkeypatch.setenv("SC_FORWARD_BACKEND", "cuda")
    with pytest.raises(RuntimeError):
        forward_backend()


@needs_cuda
def test_default_uses_cuda_and_cpu_pins_the_reference(monkeypatch):
    monkeypatch.delenv("SC_FORWARD_BACKEND", raising=False)
    default = run()
    monkeypatch.setenv("SC_FORWARD_BACKEND", "cpu")
    reference = run()
    assert default.backend == "cuda" and isinstance(default.factors, cuda_assembly.DeviceFactors)
    assert reference.backend == "cpu" and isinstance(reference.factors, tuple)
    assert np.linalg.norm(default.prediction - reference.prediction) <= 1e-12 * np.linalg.norm(reference.prediction)


@needs_cuda
def test_default_cuda_values_do_not_depend_on_thread_count(monkeypatch):
    monkeypatch.delenv("SC_FORWARD_BACKEND", raising=False)
    observations = [(k, acquisition()) for k in WAVENUMBERS]
    runs = []
    for threads in (1, 8):
        with ordered_calls(lambda o: solve(CURVE, o[0], .5, o[1], 96), observations, threads) as calls:
            runs.append([call().prediction for call in calls])
    assert all(np.array_equal(a, b) for a, b in zip(*runs))


@needs_cuda
def test_assembly_out_of_memory_falls_back_only_under_auto(monkeypatch):
    def exhausted(*args, **kwargs):
        raise torch.OutOfMemoryError("simulated")
    monkeypatch.setenv("SC_FORWARD_BACKEND", "cpu")
    reference = run()
    monkeypatch.setattr(cuda_assembly, "build_system_matrix", exhausted)
    monkeypatch.delenv("SC_FORWARD_BACKEND", raising=False)
    before = cuda_assembly.fallback_counts().get("forward assembly", 0)
    with pytest.warns(RuntimeWarning, match="CUDA out of memory"):
        state = run()
    assert state.backend == "cpu-fallback" and isinstance(state.factors, tuple)
    assert np.array_equal(state.prediction, reference.prediction)
    assert cuda_assembly.fallback_counts()["forward assembly"] == before + 1
    monkeypatch.setenv("SC_FORWARD_BACKEND", "cuda")
    with pytest.raises(torch.OutOfMemoryError):
        run()


@needs_cuda
def test_reciprocal_solve_out_of_memory_uses_the_host_factors(monkeypatch):
    monkeypatch.delenv("SC_FORWARD_BACKEND", raising=False)
    state = run()
    basis = np.cos(np.outer(2 * np.pi * np.arange(96) / 96, np.arange(1, 4)))
    expected = shape_jacobian(state, basis)
    solve_device = torch.linalg.lu_solve

    def exhausted(*args, **kwargs):
        raise torch.OutOfMemoryError("simulated")
    monkeypatch.setattr(torch.linalg, "lu_solve", exhausted)
    with pytest.warns(RuntimeWarning, match="reciprocal solve"):
        fallback = shape_jacobian(state, basis)
    assert np.linalg.norm(fallback - expected) <= 1e-12 * np.linalg.norm(expected)
    monkeypatch.setattr(torch.linalg, "lu_solve", solve_device)
    monkeypatch.setenv("SC_FORWARD_BACKEND", "cuda")
    strict = run()
    monkeypatch.setattr(torch.linalg, "lu_solve", exhausted)
    with pytest.raises(torch.OutOfMemoryError):
        shape_jacobian(strict, basis)


def test_forward_module_records_backend_field():
    assert "backend" in forward.ForwardState.__dataclass_fields__
