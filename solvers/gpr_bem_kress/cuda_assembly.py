"""Opt-in CUDA assembly and factorization of one Kress/Müller interface (SPD-011).

The operator is ``build_muller_system`` term for term: the same pair
invariants, power-log near series, Hankel differences, Kress weights and
closed diagonal limits, evaluated for every pair at once in float64 and
complex128 on one CUDA device. Real Bessel values come from a port of the
Cephes j0/y0/j1/y1 that SciPy uses (``xsf/cephes/j0.h``, ``j1.h``). Order two
uses the stable recurrence for Y; for J it uses the recurrence at x >= 2 and
the power series below.

``build_multicomponent_muller_matrix`` (SPD-013) places these self blocks and
the smooth exterior cross-component kernels into the multi-component system.
Only distinct, real, positive wavenumbers are supported; use ``supported`` to
keep the CPU reference otherwise. The sampled series/direct overlap
diagnostic of the CPU builder is not computed. Torch is imported lazily.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import sys
import threading
import warnings

import numpy as np

from periodic_kress import kress_log_weights

from ._kernels import EULER_GAMMA, validate_wavenumber
from .geometry import adapt_periodic_curve
from .operators import MullerAssemblyConfig, _diagonal_split_limits


def _array(values):
    return "{" + ", ".join(repr(float(v)) for v in values) + "}"


# Coefficients verbatim from SciPy's xsf/cephes/j0.h and j1.h.
_J0 = dict(
    PP=(7.96936729297347051624E-4, 8.28352392107440799803E-2, 1.23953371646414299388E0, 5.44725003058768775090E0,
        8.74716500199817011941E0, 5.30324038235394892183E0, 9.99999999999999997821E-1),
    PQ=(9.24408810558863637013E-4, 8.56288474354474431428E-2, 1.25352743901058953537E0, 5.47097740330417105182E0,
        8.76190883237069594232E0, 5.30605288235394617618E0, 1.00000000000000000218E0),
    QP=(-1.13663838898469149931E-2, -1.28252718670509318512E0, -1.95539544257735972385E1, -9.32060152123768231369E1,
        -1.77681167980488050595E2, -1.47077505154951170175E2, -5.14105326766599330220E1, -6.05014350600728481186E0),
    QQ=(6.43178256118178023184E1, 8.56430025976980587198E2, 3.88240183605401609683E3, 7.24046774195652478189E3,
        5.93072701187316984827E3, 2.06209331660327847417E3, 2.42005740240291393179E2),
    YP=(1.55924367855235737965E4, -1.46639295903971606143E7, 5.43526477051876500413E9, -9.82136065717911466409E11,
        8.75906394395366999549E13, -3.46628303384729719441E15, 4.42733268572569800351E16, -1.84950800436986690637E16),
    YQ=(1.04128353664259848412E3, 6.26107330137134956842E5, 2.68919633393814121987E8, 8.64002487103935000337E10,
        2.02979612750105546709E13, 3.17157752842975028269E15, 2.50596256172653059228E17),
    RP=(-4.79443220978201773821E9, 1.95617491946556577543E12, -2.49248344360967716204E14, 9.70862251047306323952E15),
    RQ=(4.99563147152651017219E2, 1.73785401676374683123E5, 4.84409658339962045305E7, 1.11855537045356834862E10,
        2.11277520115489217587E12, 3.10518229857422583814E14, 3.18121955943204943306E16, 1.71086294081043136091E18),
)
_J1 = dict(
    RP=(-8.99971225705559398224E8, 4.52228297998194034323E11, -7.27494245221818276015E13, 3.68295732863852883286E15),
    RQ=(6.20836478118054335476E2, 2.56987256757748830383E5, 8.35146791431949253037E7, 2.21511595479792499675E10,
        4.74914122079991414898E12, 7.84369607876235854894E14, 8.95222336184627338078E16, 5.32278620332680085395E18),
    PP=(7.62125616208173112003E-4, 7.31397056940917570436E-2, 1.12719608129684925192E0, 5.11207951146807644818E0,
        8.42404590141772420927E0, 5.21451598682361504063E0, 1.00000000000000000254E0),
    PQ=(5.71323128072548699714E-4, 6.88455908754495404082E-2, 1.10514232634061696926E0, 5.07386386128601488557E0,
        8.39985554327604159757E0, 5.20982848682361821619E0, 9.99999999999999997461E-1),
    QP=(5.10862594750176621635E-2, 4.98213872951233449420E0, 7.58238284132545283818E1, 3.66779609360150777800E2,
        7.10856304998926107277E2, 5.97489612400613639965E2, 2.11688757100572135698E2, 2.52070205858023719784E1),
    QQ=(7.42373277035675149943E1, 1.05644886038262816351E3, 4.98641058337653607651E3, 9.56231892404756170795E3,
        7.99704160447350683650E3, 2.82619278517639096600E3, 3.36093607810698293419E2),
    YP=(1.26320474790178026440E9, -6.47355876379160291031E11, 1.14509511541823727583E14, -8.12770255501325109621E15,
        2.02439475713594898196E17, -7.78877196265950026825E17),
    YQ=(5.94301592346128195359E2, 2.35564092943068577943E5, 7.34811944459721705660E7, 1.87601316108706159478E10,
        3.88231277496238566008E12, 6.20557727146953693363E14, 6.87141087355300489866E16, 3.97270608116560655612E18),
)
_DECLARATIONS = "\n".join(
    [f"  const double J0{name}[] = {_array(values)};" for name, values in _J0.items()]
    + [f"  const double J1{name}[] = {_array(values)};" for name, values in _J1.items()])

# One pass returns J0, Y0, J1, Y1, J2, Y2 for x > 0 (Cephes control flow; x < 1e-5 J0 limit kept).
_BESSEL = """
template <typename T> void cephes_bessel012(T x, T& j0, T& y0, T& j1, T& y1, T& j2, T& y2) {
%s
  auto polevl = [](double z, const double* c, int n) {
    double a = c[0];
    for (int i = 1; i <= n; ++i) a = a * z + c[i];
    return a;
  };
  auto p1evl = [](double z, const double* c, int n) {
    double a = z + c[0];
    for (int i = 1; i < n; ++i) a = a * z + c[i];
    return a;
  };
  const double SQRT2OPI = 7.9788456080286535587989E-1, PIO4 = 0.78539816339744830962;
  const double THPIO4 = 2.35619449019234492885, TWOOPI = 0.63661977236758134308;
  const double DR1 = 5.78318596294678452118E0, DR2 = 3.04712623436620863991E1;
  const double Z1 = 1.46819706421238932572E1, Z2 = 4.92184563216946036703E1;
  if (x <= 5.0) {
    double z = x * x;
    j0 = x < 1.0e-5 ? 1.0 - z / 4.0 : (z - DR1) * (z - DR2) * polevl(z, J0RP, 3) / p1evl(z, J0RQ, 8);
    y0 = polevl(z, J0YP, 7) / p1evl(z, J0YQ, 7) + TWOOPI * log(x) * j0;
    j1 = polevl(z, J1RP, 3) / p1evl(z, J1RQ, 8) * x * (z - Z1) * (z - Z2);
    y1 = x * (polevl(z, J1YP, 5) / p1evl(z, J1YQ, 8)) + TWOOPI * (j1 * log(x) - 1.0 / x);
  } else {
    double w = 5.0 / x, q = 25.0 / (x * x), p, r, xn;
    p = polevl(q, J0PP, 6) / polevl(q, J0PQ, 6);
    r = polevl(q, J0QP, 7) / p1evl(q, J0QQ, 7);
    xn = x - PIO4;
    j0 = (p * cos(xn) - w * r * sin(xn)) * SQRT2OPI / sqrt(x);
    y0 = (p * sin(xn) + w * r * cos(xn)) * SQRT2OPI / sqrt(x);
    double z = w * w;
    p = polevl(z, J1PP, 6) / polevl(z, J1PQ, 6);
    r = polevl(z, J1QP, 7) / p1evl(z, J1QQ, 7);
    xn = x - THPIO4;
    j1 = (p * cos(xn) - w * r * sin(xn)) * SQRT2OPI / sqrt(x);
    y1 = (p * sin(xn) + w * r * cos(xn)) * SQRT2OPI / sqrt(x);
  }
  y2 = 2.0 * y1 / x - y0;
  if (x >= 2.0) {
    j2 = 2.0 * j1 / x - j0;
  } else {
    double h = 0.25 * x * x, term = 0.5 * h, sum = term;
    for (int m = 0; m < 24; ++m) {
      term *= -h / ((m + 1.0) * (m + 3.0));
      sum += term;
    }
    j2 = sum;
  }
}
""" % _DECLARATIONS


_initialization = threading.Lock()
_device_work = threading.Lock()
_fallbacks = Counter()


@lru_cache(maxsize=None)
def available():
    """Whether torch can use a CUDA device in this process."""
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def out_of_memory(exc):
    """Whether ``exc`` is a device out-of-memory error; never imports torch."""
    torch = sys.modules.get("torch")
    return torch is not None and isinstance(exc, torch.OutOfMemoryError)


def record_fallback(kind):
    """Count one CPU fallback after device out-of-memory, release cached blocks, and warn."""
    with _initialization:
        _fallbacks[kind] += 1
    torch = sys.modules.get("torch")
    if torch is not None:
        torch.cuda.empty_cache()
    warnings.warn(f"CUDA out of memory during {kind}; this call used the CPU reference instead.",
                  RuntimeWarning, stacklevel=3)


def fallback_counts():
    """CPU fallbacks after device out-of-memory in this process, by kind."""
    with _initialization:
        return dict(_fallbacks)


@lru_cache(maxsize=None)
def _device_ready(device):
    """One-time kernel compilation and lazy CUDA linear-algebra setup.

    Torch's lazy linalg initialization is not safe when several threads make
    the first call at once, so the first use runs once under a lock.
    """
    import torch
    kernel = torch.cuda.jiterator._create_multi_output_jit_fn(_BESSEL, num_outputs=6)
    kernel(torch.ones(1, dtype=torch.float64, device=device))
    matrix = torch.eye(2, dtype=torch.complex128, device=device)
    torch.linalg.lu_solve(*torch.linalg.lu_factor_ex(matrix)[:2], matrix)
    torch.cuda.synchronize(device)
    return kernel


def _ready(device):
    with _initialization:
        return _device_ready(str(device))


def bessel012(x):
    """J0, Y0, J1, Y1, J2, Y2 of a positive float64 CUDA tensor."""
    return _ready(x.device)(x)


def supported(curve, k_exterior, k_interior):
    """Whether this backend reproduces the CPU system for the inputs.

    Single ``PeriodicCurve2D`` interfaces (SPD-011) and ``OrderedBoundary2D``
    multi-component boundaries (SPD-013) with distinct real positive wavenumbers.
    """
    from ordered_boundary import OrderedBoundary2D, PeriodicCurve2D
    try:
        exterior, interior = complex(k_exterior), complex(k_interior)
    except TypeError:
        return False
    return (isinstance(curve, (PeriodicCurve2D, OrderedBoundary2D)) and exterior.imag == 0
            and interior.imag == 0 and exterior.real > 0 and interior.real > 0 and exterior != interior)


def _series(radius, k_exterior, k_interior, terms):
    """Device port of ``_kernels._series_radial_differences`` with the same scalar algebra."""
    import torch
    log_radius = torch.log(radius)
    values = [torch.zeros(radius.shape, dtype=torch.complex128, device=radius.device) for _ in range(6)]
    g, radial_first, radial_anisotropy, g_log, radial_first_log, radial_anisotropy_log = values
    coefficient_exterior = 1.0 + 0.0j
    coefficient_interior = 1.0 + 0.0j
    harmonic = 0.0
    log_exterior = np.log(k_exterior)
    log_interior = np.log(k_interior)
    for mode in range(terms):
        if mode:
            harmonic += 1.0 / mode
        difference = coefficient_exterior - coefficient_interior
        p_coefficient = complex(-difference / (2.0 * np.pi))
        q_coefficient = complex(difference * (0.25j + (np.log(2.0) - EULER_GAMMA + harmonic) / (2.0 * np.pi)) + (
            coefficient_interior * log_interior - coefficient_exterior * log_exterior) / (2.0 * np.pi))
        power = 2 * mode
        radius_power = radius ** power
        value = p_coefficient * log_radius + q_coefficient
        g += radius_power * value
        g_log += radius_power * p_coefficient
        if mode:
            derivative_power = radius ** (power - 2)
            radial_first += derivative_power * (power * value + p_coefficient)
            radial_anisotropy += derivative_power * (power * (power - 2) * value + (2 * power - 2) * p_coefficient)
            radial_first_log += derivative_power * power * p_coefficient
            radial_anisotropy_log += derivative_power * power * (power - 2) * p_coefficient
        next_mode = mode + 1
        coefficient_exterior *= -0.25 * k_exterior ** 2 / next_mode ** 2
        coefficient_interior *= -0.25 * k_interior ** 2 / next_mode ** 2
    return values


def _direct(radius, k_exterior, k_interior):
    """Device port of ``_kernels._direct_radial_differences`` for real wavenumbers."""
    import torch
    ko, ki = float(k_exterior.real), float(k_interior.real)
    je0, ye0, je1, ye1, je2, ye2 = bessel012(ko * radius)
    ji0, yi0, ji1, yi1, ji2, yi2 = bessel012(ki * radius)
    delta_h0 = torch.complex(je0, ye0) - torch.complex(ji0, yi0)
    delta_h1 = ko * torch.complex(je1, ye1) - ki * torch.complex(ji1, yi1)
    delta_h2 = ko ** 2 * torch.complex(je2, ye2) - ki ** 2 * torch.complex(ji2, yi2)
    scale = -1.0 / (2.0 * np.pi)
    delta_j0 = je0 - ji0
    delta_j1 = ko * je1 - ki * ji1
    delta_j2 = ko ** 2 * je2 - ki ** 2 * ji2
    real = lambda values: torch.complex(values, torch.zeros_like(values))
    return [0.25j * delta_h0, -0.25j * delta_h1 / radius, 0.25j * delta_h2,
            real(scale * delta_j0), real(-scale * delta_j1 / radius), real(scale * delta_j2)]


def _tensor(values, device):
    import torch
    return torch.tensor(np.asarray(values), device=device)  # copies read-only arrays


def _difference_blocks(adapter, exterior, interior, settings, device):
    """Device ``build_muller_difference_blocks`` V, K, Kp, T for one component (weighted)."""
    import torch
    count = adapter.num_nodes
    diagonal_log, diagonal_remainder = _diagonal_split_limits(adapter, exterior, interior)
    points, normals = _tensor(adapter.points, device), _tensor(adapter.normals, device)
    dx = points[:, None, 0] - points[None, :, 0]
    dy = points[:, None, 1] - points[None, :, 1]
    distance = torch.sqrt(dx * dx + dy * dy)
    target_projection = dx * normals[:, None, 0] + dy * normals[:, None, 1]
    source_projection = dx * normals[None, :, 0] + dy * normals[None, :, 1]
    normal_dot = normals[:, None, 0] * normals[None, :, 0] + normals[:, None, 1] * normals[None, :, 1]
    off_diagonal = ~torch.eye(count, dtype=torch.bool, device=device)
    maximum_wave = max(abs(exterior), abs(interior))
    near = off_diagonal & (maximum_wave * distance <= settings.near_argument)
    direct = off_diagonal & ~near

    radial = [torch.zeros((count, count), dtype=torch.complex128, device=device) for _ in range(6)]
    for mask, values in ((near, lambda r: _series(r, exterior, interior, settings.series_terms)),
                         (direct, lambda r: _direct(r, exterior, interior))):
        if bool(mask.any()):
            for destination, source in zip(radial, values(distance[mask])):
                destination[mask] = source
    green, radial_first, radial_anisotropy, green_log, radial_first_log, radial_anisotropy_log = radial
    safe = torch.where(off_diagonal, distance, torch.ones_like(distance))
    projection_product = target_projection * source_projection / safe ** 2
    kernels = dict(
        V=(green, green_log),
        K=(-radial_first * source_projection, -radial_first_log * source_projection),
        Kp=(radial_first * target_projection, radial_first_log * target_projection),
        T=(-radial_first * normal_dot - radial_anisotropy * projection_product,
           -radial_first_log * normal_dot - radial_anisotropy_log * projection_product),
    )

    offsets = (torch.arange(count, device=device)[:, None] - torch.arange(count, device=device)[None, :]) % count
    kress_by_offset = kress_log_weights(count)
    log_by_offset = np.zeros(count, dtype=np.float64)
    log_by_offset[1:] = np.log(4.0 * np.sin(np.pi * np.arange(1, count) / count) ** 2)
    weight_rows = _tensor(kress_by_offset, device)[offsets]
    log_rows = _tensor(log_by_offset, device)[offsets]
    source_speed = _tensor(adapter.theta_speeds, device)[None, :]
    diagonal = torch.arange(count, device=device)
    blocks = {}
    for name, (kernel, logarithmic) in kernels.items():
        zero = torch.zeros((), dtype=torch.complex128, device=device)
        kernel_grid = torch.where(off_diagonal, kernel, zero)
        logarithmic_grid = torch.where(off_diagonal, logarithmic, zero)
        rows = source_speed * (adapter.theta_step * kernel_grid + 0.5 * logarithmic_grid * (
            weight_rows - adapter.theta_step * log_rows))
        rows[diagonal, diagonal] = _tensor(
            kress_by_offset[0] * diagonal_log[name] + adapter.theta_step * diagonal_remainder[name], device)
        blocks[name] = rows
    return blocks


def _cross_blocks(target, source, k_exterior, device):
    """Device ``multicomponent._exterior_cross_blocks_from_adapters`` V, K, Kp, T (weighted)."""
    import torch
    wave = float(k_exterior.real)
    targets, target_normals = _tensor(target.points, device), _tensor(target.normals, device)
    sources, source_normals = _tensor(source.points, device), _tensor(source.normals, device)
    dx = targets[:, None, 0] - sources[None, :, 0]
    dy = targets[:, None, 1] - sources[None, :, 1]
    radius = torch.sqrt(dx * dx + dy * dy)
    if bool((radius <= 0.0).any()):
        raise FloatingPointError("cross-component kernel evaluation requires positive distances.")
    target_projection = dx * target_normals[:, None, 0] + dy * target_normals[:, None, 1]
    source_projection = dx * source_normals[None, :, 0] + dy * source_normals[None, :, 1]
    normal_dot = (target_normals[:, None, 0] * source_normals[None, :, 0]
                  + target_normals[:, None, 1] * source_normals[None, :, 1])
    j0, y0, j1, y1, j2, y2 = bessel012(wave * radius)
    green = 0.25j * torch.complex(j0, y0)
    radial_first = -0.25j * wave * torch.complex(j1, y1) / radius
    radial_anisotropy = 0.25j * wave ** 2 * torch.complex(j2, y2)
    projection_product = target_projection * source_projection / radius ** 2
    weights = _tensor(source.arc_length_weights, device)[None, :]
    return dict(V=green * weights, K=-radial_first * source_projection * weights,
                Kp=radial_first * target_projection * weights,
                T=(-radial_first * normal_dot - radial_anisotropy * projection_product) * weights)


def _compose(blocks, count, device):
    import torch
    matrix = torch.empty((2 * count, 2 * count), dtype=torch.complex128, device=device)
    matrix[:count, :count] = -blocks["K"]
    matrix[:count, count:] = blocks["V"]
    matrix[count:, :count] = -blocks["T"]
    matrix[count:, count:] = blocks["Kp"]
    identity = torch.arange(2 * count, device=device)
    matrix[identity, identity] += 1.0
    if not bool(torch.isfinite(matrix).all()):
        raise FloatingPointError("CUDA Müller system composition produced non-finite entries.")
    return matrix


def build_muller_matrix(curve, k_exterior, k_interior, *, config=None, device="cuda"):
    """Device ``[[I-dK, dV], [-dT, I+dKp]]``, as ``build_muller_system(...).system_matrix``."""
    from ordered_boundary import PeriodicCurve2D
    settings = MullerAssemblyConfig() if config is None else config
    if not isinstance(curve, PeriodicCurve2D) or not supported(curve, k_exterior, k_interior):
        raise ValueError("CUDA Kress assembly needs one periodic curve and distinct real positive wavenumbers.")
    adapter = adapt_periodic_curve(curve)
    exterior = validate_wavenumber(k_exterior, name="k_exterior")
    interior = validate_wavenumber(k_interior, name="k_interior")
    # One device assembly at a time per process bounds transient device memory.
    with _device_work:
        blocks = _difference_blocks(adapter, exterior, interior, settings, device)
        return _compose(blocks, adapter.num_nodes, device)


def build_multicomponent_muller_matrix(boundary, k_exterior, k_interior, *, config=None, device="cuda"):
    """Device ``build_multicomponent_muller_system(...).system_matrix`` (SPD-013).

    Self blocks are the single-interface Kress exterior-minus-interior blocks;
    cross blocks are the ordinary exterior trapezoid kernels. The CPU
    ``adapt_multicomponent_boundary`` topology and clearance validation runs first.
    """
    import torch
    from ordered_boundary import OrderedBoundary2D
    from .multicomponent import MultiComponentAssemblyConfig, adapt_multicomponent_boundary
    settings = MultiComponentAssemblyConfig() if config is None else config
    if not isinstance(boundary, OrderedBoundary2D) or not supported(boundary, k_exterior, k_interior):
        raise ValueError("CUDA multicomponent assembly needs an ordered boundary and distinct real "
                         "positive wavenumbers.")
    adapter = adapt_multicomponent_boundary(boundary, config=settings)
    exterior = validate_wavenumber(k_exterior, name="k_exterior")
    interior = validate_wavenumber(k_interior, name="k_interior")
    count = boundary.num_nodes
    with _device_work:
        blocks = {name: torch.zeros((count, count), dtype=torch.complex128, device=device)
                  for name in ("V", "K", "Kp", "T")}
        pieces = tuple(zip(adapter.component_adapters, boundary.component_slices))
        for target_index, (target, rows) in enumerate(pieces):
            for source_index, (source, columns) in enumerate(pieces):
                part = (_difference_blocks(target, exterior, interior, settings.self_assembly, device)
                        if target_index == source_index else _cross_blocks(target, source, exterior, device))
                for name, values in part.items():
                    blocks[name][rows, columns] = values
        return _compose(blocks, count, device)


def build_system_matrix(curve, k_exterior, k_interior, *, device="cuda"):
    """Device system matrix for either a single curve or an ordered multi-component boundary."""
    from ordered_boundary import OrderedBoundary2D
    builder = build_multicomponent_muller_matrix if isinstance(curve, OrderedBoundary2D) else build_muller_matrix
    return builder(curve, k_exterior, k_interior, device=device)


class DeviceFactors:
    """LU factors from the device that solve host right-hand sides with the residual guard.

    ``host`` keeps the system matrix in host memory, as on the CPU path. The
    first solve uses the device matrix and factors it was built with; the
    factors then move to host memory too. Later solves (reciprocal Jacobians)
    upload both for one call, so retained states hold no device memory. With
    ``fallback``, a device out-of-memory error solves on the host from the
    same LU factors.
    """

    def __init__(self, matrix, *, fallback=False):
        import torch
        self.fallback = bool(fallback)
        _ready(matrix.device)
        with _device_work:
            lu, pivots, info = torch.linalg.lu_factor_ex(matrix)
            if int(info) != 0:
                raise FloatingPointError("Singular dense Müller system.")
        self.device = matrix.device
        self.host = matrix.cpu().numpy()
        self.host.setflags(write=False)
        self._resident = (matrix, lu, pivots)
        self._offloaded = None
        self._lock = threading.Lock()

    def _operands(self):
        import torch
        with self._lock:
            resident, self._resident = self._resident, None
            if resident is not None:
                self._offloaded = (resident[1].cpu().numpy(), resident[2].cpu().numpy())
                return resident
            lu, pivots = self._offloaded
        return tuple(torch.tensor(v, device=self.device) for v in (self.host, lu, pivots))

    def solve(self, rhs):
        """Return ``(solution, relative residual)``; host complex arrays in and out."""
        try:
            return self._solve_device(rhs)
        except Exception as exc:
            if not (self.fallback and out_of_memory(exc)):
                raise
            record_fallback("reciprocal solve")
            return self._solve_host(rhs)

    def _solve_host(self, rhs):
        from scipy.linalg import lu_solve
        with self._lock:
            if self._resident is not None:
                resident, self._resident = self._resident, None
                self._offloaded = (resident[1].cpu().numpy(), resident[2].cpu().numpy())
            lu, pivots = self._offloaded
        # Torch returns LAPACK getrf pivots (one-based); SciPy expects zero-based.
        solution = lu_solve((lu, pivots.astype(np.int64) - 1), np.asarray(rhs, dtype=np.complex128))
        residual = np.linalg.norm(self.host @ solution - rhs) / max(np.linalg.norm(rhs), np.finfo(float).tiny)
        return solution, float(residual)

    def _solve_device(self, rhs):
        import torch
        matrix, lu, pivots = self._operands()
        b = torch.as_tensor(np.ascontiguousarray(rhs, dtype=np.complex128), device=self.device)
        column = b.ndim == 1
        if column:
            b = b[:, None]
        x = torch.linalg.lu_solve(lu, pivots, b)
        residual = float(torch.linalg.norm(matrix @ x - b)) / max(float(torch.linalg.norm(b)),
                                                                  np.finfo(float).tiny)
        solution = x.cpu().numpy()
        return (solution[:, 0] if column else solution), residual


__all__ = ["DeviceFactors", "available", "bessel012", "build_muller_matrix", "build_multicomponent_muller_matrix",
           "build_system_matrix", "fallback_counts", "out_of_memory", "record_fallback", "supported"]
