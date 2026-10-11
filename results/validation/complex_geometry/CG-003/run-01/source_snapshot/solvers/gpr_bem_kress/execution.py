"""Scoped, optional kernel/linear-algebra execution; reference CPU is default.

Settings use context variables so a benchmark does not monkeypatch another
caller's numerical functions. All arrays retain double precision.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
import numpy as np
from scipy import linalg, special


@dataclass
class Execution:
    kernels: str = "reference"
    device: str = "cpu"
    counts: dict = field(default_factory=dict)
    seconds: dict = field(default_factory=dict)

    def record(self, name, seconds=0.0, count=1):
        self.counts[name] = self.counts.get(name, 0) + count
        self.seconds[name] = self.seconds.get(name, 0.0) + seconds


_active = ContextVar("kress_execution", default=None)


def current_execution():
    return _active.get()


def record(name, seconds=0.0, count=1):
    context = _active.get()
    if context is not None:
        context.record(name, seconds, count)


@contextmanager
def execution(*, kernels="reference", device="cpu"):
    if kernels not in ("reference", "real_bessel") or device not in ("cpu", "cuda"):
        raise ValueError("Unsupported Kress execution selection.")
    if device == "cuda":
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is unavailable.")
    context = Execution(kernels, device)
    token = _active.set(context)
    try:
        yield context
    finally:
        _active.reset(token)


def _real_order_argument(order, argument):
    context = _active.get()
    if context is None or context.kernels == "reference":
        return None
    if not np.isscalar(order) or order not in (-3, -2, -1, 0, 1, 2, 3):
        return None
    z = np.asarray(argument)
    if np.any(z.imag != 0) or not np.all(z.real > 0) or not np.all(np.isfinite(z)):
        return None
    return abs(int(order)), z.real, (-1 if abs(int(order)) % 2 else 1) if order < 0 else 1


def jv(order, argument):
    real = _real_order_argument(order, argument)
    if real is None:
        return special.jv(order, argument)
    n, x, sign = real
    return sign * (special.j0(x) if n == 0 else special.j1(x) if n == 1 else special.jv(n, x))


def hankel1(order, argument):
    real = _real_order_argument(order, argument)
    if real is None:
        return special.hankel1(order, argument)
    n, x, sign = real
    j = special.j0(x) if n == 0 else special.j1(x) if n == 1 else special.jv(n, x)
    y = special.y0(x) if n == 0 else special.y1(x) if n == 1 else special.yn(n, x)
    return sign * (j + 1j * y)


def to_cuda(array):
    import torch
    # A copy also keeps read-only solver arrays out of writable Torch views.
    started = perf_counter()
    result = torch.from_numpy(np.array(array, copy=True, order="C")).cuda()
    torch.cuda.synchronize()
    record("host_to_device", perf_counter() - started)
    return result


class Factorization:
    def __init__(self, matrix):
        context = _active.get()
        self.device = "cpu" if context is None else context.device
        started = perf_counter()
        if self.device == "cuda":
            import torch
            a = to_cuda(matrix)
            self.factors = torch.linalg.lu_factor(a)
            torch.cuda.synchronize()
        else:
            self.factors = linalg.lu_factor(matrix)
        record("factorization", perf_counter() - started)

    def solve_native(self, rhs):
        started = perf_counter()
        if self.device == "cuda":
            import torch
            value = torch.linalg.lu_solve(*self.factors, rhs)
            torch.cuda.synchronize()
        else:
            value = linalg.lu_solve(self.factors, rhs)
        record("rhs_solve", perf_counter() - started)
        return value

    def solve(self, rhs):
        if self.device == "cuda":
            return self.solve_native(to_cuda(rhs)).cpu().numpy()
        return self.solve_native(rhs)


def solve_dense(matrix, rhs):
    context = _active.get()
    if context is None or context.device == "cpu":
        started = perf_counter()
        result = np.linalg.solve(matrix, rhs)
        record("dense_factor_and_solve", perf_counter() - started)
        return result
    return Factorization(matrix).solve(rhs)
