"""Shared execution defaults for explicit inverse entry points and workers."""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from functools import wraps
import os

from gpr_bem_kress.execution import current_execution, execution


@dataclass(frozen=True)
class InverseRuntime:
    profile: str
    jacobian: str
    kernels: str
    device: str = "cpu"
    analytic_constraint_policy: str = "fd_compatible"
    shape_derivative: str = "operator"
    reciprocal_min_nodes: int = 128
    continuation_backend: str = "full_kress"
    continuation_readiness: bool = False


PROFILES = {
    "fast": InverseRuntime("fast", "auto", "real_bessel"),
    "reference": InverseRuntime("reference", "fd", "reference"),
    "reciprocal": InverseRuntime("reciprocal", "auto", "real_bessel", shape_derivative="reciprocal"),
    "compiled": InverseRuntime("compiled", "auto", "real_bessel", shape_derivative="reciprocal",
                               continuation_backend="compiled", continuation_readiness=True),
}
DEFAULT_PROFILE = "compiled"
_override = ContextVar("inverse_runtime", default=None)
ENVIRONMENT_VARIABLE = "SDF_INVERSE_RUNTIME"


def current_runtime():
    """Environment selection also reaches independently spawned workers."""
    selected = _override.get()
    if selected is not None:
        return selected
    name = os.environ.get(ENVIRONMENT_VARIABLE, DEFAULT_PROFILE)
    if name not in PROFILES:
        raise ValueError(f"{ENVIRONMENT_VARIABLE} must be one of {tuple(PROFILES)}.")
    return PROFILES[name]


def runtime_metadata():
    return asdict(current_runtime())


def jacobian_selection(state, requested=None):
    mode = current_runtime().jacobian if requested is None else requested
    if mode == "auto":
        from .explicit_fourier import CartesianFourierCurveState
        return "analytic" if all(isinstance(c, CartesianFourierCurveState) for c in state.components) else "fd"
    return mode


def jacobian_work_bound(state, directions):
    if jacobian_selection(state) == "fd":
        return 2 * directions
    return 1 + directions * (2 if current_runtime().analytic_constraint_policy == "fd_compatible" else 1)


@contextmanager
def inverse_runtime(profile=DEFAULT_PROFILE):
    """Select a profile for a Python call; explicit execution contexts override it."""
    if profile not in PROFILES:
        raise ValueError(f"Inverse runtime must be one of {tuple(PROFILES)}.")
    token = _override.set(PROFILES[profile])
    try:
        yield current_runtime()
    finally:
        _override.reset(token)


def inverse_execution(function):
    """Apply inverse defaults only when no caller supplied an execution context."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        selected = current_runtime()
        context = (execution(kernels=selected.kernels, device=selected.device)
                   if current_execution() is None else nullcontext())
        with context:
            return function(*args, **kwargs)
    return wrapped


def add_runtime_argument(parser):
    parser.add_argument("--inverse-runtime", choices=tuple(PROFILES), default=None,
        help="compiled (default): reduced Kress for multi-object Cartesian fits at "
             "256 or more nodes, guarded reciprocal derivatives, and training-only "
             "readiness in the TOP-025 full pipeline; fast: operator derivatives "
             "and fast CPU kernels; reciprocal: guarded reciprocal derivatives; "
             "reference: FD and reference CPU kernels. Comparison profiles run "
             "the full continuation schedule. Inherited by worker processes.")


def configure_runtime_argument(args):
    if args.inverse_runtime is not None:
        os.environ[ENVIRONMENT_VARIABLE] = args.inverse_runtime
    return runtime_metadata()
