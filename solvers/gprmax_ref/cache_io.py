"""Cache for gprMax reference runs.

gprMax lives in its own conda environment (a different Python version, a
compiled Cython extension) that the main ``EMNerf`` test environment cannot
import. So the FDTD run itself is a script invoked once by hand with the
``gprMax`` env's interpreter (see ``run_case.py``); the *result* is cached here
as plain JSON, keyed by a hash of every physical and numerical parameter that
could change the answer. Reading the cache has no dependency on gprMax being
installed at all, which is what lets
``pytest/solver_comparisons/test_circle_comparison.py`` and
``pytest/solver_comparisons/test_square_comparison.py``
show a gprMax row without ever launching gprMax itself.

The preferred high-frequency format is one cache entry per frequency, with
cell size scaled by background-medium wavelength and the Ricker pulse centered
on that frequency. ``load_frequency_sweep`` assembles those per-frequency
entries back into the old sweep-shaped result and falls back to legacy
whole-sweep blobs when the scaled entries are absent.

Adding a new geometry or material combination just works: it hashes to a new
key and gets its own cache entry. Nothing here is specific to "this test
case" beyond the parameters passed in.
"""

from __future__ import annotations

import cmath
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

try:  # package import (pytest: ``from gprmax_ref import cache_io``)
    from . import build_scene
except ImportError:  # top-level import (run_case.py puts this dir on sys.path)
    import build_scene

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def case_key(params: dict[str, Any]) -> str:
    """A stable hash of every parameter that determines the FDTD answer."""

    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def load(params: dict[str, Any]) -> dict[str, Any] | None:
    """Return the cached result for ``params``, or ``None`` on a cache miss."""

    path = cache_path(case_key(params))
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save(params: dict[str, Any], result: dict[str, Any]) -> Path:
    """Write ``result`` under the key derived from ``params``.

    ``result`` should already be JSON-plain (no numpy arrays / complex
    scalars); see ``run_case.py`` for the conversion.
    """

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = case_key(params)
    path = cache_path(key)
    payload = {"key": key, "params": params, "result": result}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path

# The canonical numerical settings used for every cached case in this repo.
# Anyone regenerating a cache entry with ``run_case.py`` must use these (they
# are already ``run_case.py``'s argparse defaults) or the hash -- and hence
# the lookup from a test -- will not match.
DEFAULT_CELL_SIZE = 1.0e-3
DEFAULT_WAVEFORM = "ricker"
DEFAULT_CENTER_FREQUENCY = 1.5e9
DEFAULT_TIME_WINDOW = 15e-9
DEFAULT_PML_CELLS = 12
GPRMAX_VERSION = "3.1.7"
DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH = 30.0
SCENE_DECIMAL_PLACES = 6


def build_params(
    *,
    target_shape: str,
    target_size: float,
    target_parameters: dict[str, Any] | None = None,
    standoff: float,
    tx_rx_offset: float,
    sand_epsr: float,
    sand_sigma: float,
    plastic_epsr: float,
    plastic_sigma: float,
    eps0: float,
    mu0: float,
    frequencies_hz: list[float],
    cell_size: float = DEFAULT_CELL_SIZE,
    waveform: str = DEFAULT_WAVEFORM,
    center_frequency: float = DEFAULT_CENTER_FREQUENCY,
    time_window: float = DEFAULT_TIME_WINDOW,
    pml_cells: int = DEFAULT_PML_CELLS,
) -> dict[str, Any]:
    """The single parameter set both ``run_case.py`` and test code must build
    identically, so a lookup here matches what a run there produced."""

    params = dict(
        target_shape=target_shape,
        target_size=target_size,
        standoff=standoff,
        tx_rx_offset=tx_rx_offset,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        plastic_epsr=plastic_epsr,
        plastic_sigma=plastic_sigma,
        eps0=eps0,
        mu0=mu0,
        frequencies_hz=sorted(frequencies_hz),
        cell_size=cell_size,
        waveform=waveform,
        center_frequency=center_frequency,
        time_window=time_window,
        pml_cells=pml_cells,
        gprmax_version=GPRMAX_VERSION,
    )
    if target_parameters:
        params["target_parameters"] = dict(sorted(target_parameters.items()))
    return params


def sand_phase_wavelength(
    frequency_hz: float,
    *,
    sand_epsr: float,
    sand_sigma: float,
    eps0: float,
    mu0: float,
) -> float:
    """Return the wavelength from the real phase constant in the background medium."""

    frequency = float(frequency_hz)
    if frequency <= 0.0:
        raise ValueError("frequency_hz must be positive.")
    angular_frequency = 2.0 * math.pi * frequency
    complex_epsr = float(sand_epsr) + float(sand_sigma) / (1j * angular_frequency * float(eps0))
    wavenumber = angular_frequency * cmath.sqrt(float(mu0) * float(eps0) * complex_epsr)
    phase_constant = abs(float(wavenumber.real))
    if phase_constant <= 0.0:
        raise ValueError("Could not compute a positive phase constant for the background medium.")
    return 2.0 * math.pi / phase_constant


def frequency_scaled_cell_size(
    frequency_hz: float,
    *,
    sand_epsr: float,
    sand_sigma: float,
    eps0: float,
    mu0: float,
    cells_per_wavelength: float = DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
    max_cell_size: float = DEFAULT_CELL_SIZE,
) -> float:
    """Cell size for a per-frequency gprMax run.

    Low frequencies keep the historical ``max_cell_size`` so curved-target
    staircasing does not get worse. Higher frequencies shrink the cell size to
    keep at least ``cells_per_wavelength`` samples across the background-medium
    phase wavelength. The returned value is rounded to the precision emitted in
    gprMax scene files, so cache keys describe the grid actually run.
    """

    if cells_per_wavelength <= 0.0:
        raise ValueError("cells_per_wavelength must be positive.")
    if max_cell_size <= 0.0:
        raise ValueError("max_cell_size must be positive.")
    wavelength = sand_phase_wavelength(
        frequency_hz,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        eps0=eps0,
        mu0=mu0,
    )
    raw_cell_size = min(float(max_cell_size), wavelength / float(cells_per_wavelength))
    rounded = round(raw_cell_size, SCENE_DECIMAL_PLACES)
    if rounded <= 0.0:
        raise ValueError("Rounded cell size is zero; reduce SCENE_DECIMAL_PLACES or the frequency.")
    return rounded


DEFAULT_HARMONIC_WAVEFORM = "contsine"
# gprMax's ``contsine`` ramps its amplitude linearly to 1 over the first
# ``1 / (0.25 * freq)`` = 4 periods (see gprMax/waveforms.py), then holds a
# steady sin(2*pi*f*t). These size the run so the receiver has settled into
# that steady state before the extraction window, without hand-tuning a fixed
# wall-clock time_window the way the legacy Ricker sweep does.
DEFAULT_HARMONIC_RAMP_PERIODS = 4.0
# Secondary reflections (PML residual, multi-bounce off the target) travel a
# physical distance comparable to the direct transit path, so they arrive
# after a comparable *absolute time*, not a comparable *period count* -- a
# flat settle_periods here would starve at high frequency, where each period
# is short in absolute time even though transit_periods itself grows (shorter
# wavelength). Measured: a flat 3-period settle left circle's 8 GHz gprMax
# error an order of magnitude worse than the legacy Ricker sweep's, while
# 0.5-2.5 GHz matched; scaling the settle margin off transit *time* instead
# fixed it. Expressed as a multiplier on the direct transit time.
DEFAULT_HARMONIC_SETTLE_TRANSIT_MULTIPLIER = 1.0
DEFAULT_HARMONIC_EXTRACTION_PERIODS = 6.0
DEFAULT_HARMONIC_TRANSIT_SAFETY = 1.15


def harmonic_time_window(
    frequency_hz: float,
    *,
    domain_x: float,
    domain_y: float,
    sand_epsr: float,
    sand_sigma: float,
    eps0: float,
    mu0: float,
    ramp_periods: float = DEFAULT_HARMONIC_RAMP_PERIODS,
    settle_transit_multiplier: float = DEFAULT_HARMONIC_SETTLE_TRANSIT_MULTIPLIER,
    extraction_periods: float = DEFAULT_HARMONIC_EXTRACTION_PERIODS,
    transit_safety: float = DEFAULT_HARMONIC_TRANSIT_SAFETY,
) -> float:
    """Physical run length for a ``contsine`` harmonic FDTD run.

    Long enough for: the wave to cross the domain diagonal (a conservative
    stand-in for the longest Tx-target-Rx or Tx-Rx path actually used), a
    settling margin for secondary/PML reflections sized as a multiple of that
    same transit *time* (see ``DEFAULT_HARMONIC_SETTLE_TRANSIT_MULTIPLIER``),
    the source's built-in 4-period ramp, and a trailing window of
    ``extraction_periods`` used to fit the steady-state phasor.
    """

    period = 1.0 / float(frequency_hz)
    wavelength = sand_phase_wavelength(
        frequency_hz,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        eps0=eps0,
        mu0=mu0,
    )
    phase_velocity = wavelength * float(frequency_hz)
    transit_distance = math.hypot(float(domain_x), float(domain_y)) * float(transit_safety)
    transit_time = transit_distance / phase_velocity
    settle_time = float(settle_transit_multiplier) * transit_time
    ramp_time = float(ramp_periods) * period
    extraction_time = float(extraction_periods) * period
    total_time = transit_time + settle_time + ramp_time + extraction_time
    # Round like frequency_scaled_cell_size does: cmath.sqrt/hypot can differ
    # in their last 1-2 bits across platforms (observed between conda envs),
    # which would otherwise change this value -- and hence the cache key --
    # by a physically meaningless amount depending on which machine generated
    # the cache. 15 decimal places keeps ~7 significant figures at this
    # nanosecond scale, far finer than gprMax's own dt quantisation.
    return round(total_time, 15)


def harmonic_extraction_seconds(
    frequency_hz: float,
    *,
    extraction_periods: float = DEFAULT_HARMONIC_EXTRACTION_PERIODS,
) -> float:
    """Trailing window length, in seconds, used to fit the steady-state phasor."""

    return float(extraction_periods) / float(frequency_hz)


def build_harmonic_params_from_base(
    params: dict[str, Any],
    frequency_hz: float,
    *,
    cells_per_wavelength: float = DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
    max_cell_size: float | None = None,
    buffer_cells: int = 12,
    ramp_periods: float = DEFAULT_HARMONIC_RAMP_PERIODS,
    settle_transit_multiplier: float = DEFAULT_HARMONIC_SETTLE_TRANSIT_MULTIPLIER,
    extraction_periods: float = DEFAULT_HARMONIC_EXTRACTION_PERIODS,
    transit_safety: float = DEFAULT_HARMONIC_TRANSIT_SAFETY,
) -> dict[str, Any]:
    """Build the one-frequency cache-key params for a harmonic (contsine) run.

    Cell size is sized the same way as the scaled Ricker mode (background
    wavelength / ``cells_per_wavelength``, capped by ``max_cell_size``); the
    center frequency is literally the target frequency (``contsine`` has no
    separate pulse-center concept); ``time_window`` comes from
    ``harmonic_time_window`` using that cell size's domain. Because
    ``time_window`` already depends on every one of ``ramp_periods`` /
    ``settle_transit_multiplier`` / ``extraction_periods`` / ``transit_safety``, changing
    any of those constants changes the cache key automatically -- no separate
    "harmonic settings" field is needed for correctness.
    """

    maximum_cell_size = float(params.get("cell_size", DEFAULT_CELL_SIZE) if max_cell_size is None else max_cell_size)
    frequency = float(frequency_hz)
    target_parameters = params.get("target_parameters")
    pml_cells = int(params.get("pml_cells", DEFAULT_PML_CELLS))
    sand_epsr = float(params["sand_epsr"])
    sand_sigma = float(params["sand_sigma"])
    eps0 = float(params["eps0"])
    mu0 = float(params["mu0"])
    cell_size = frequency_scaled_cell_size(
        frequency,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        eps0=eps0,
        mu0=mu0,
        cells_per_wavelength=cells_per_wavelength,
        max_cell_size=maximum_cell_size,
    )
    geometry = build_scene.build_geometry(
        target_shape=str(params["target_shape"]),
        target_size=float(params["target_size"]),
        target_parameters=target_parameters,
        standoff=float(params["standoff"]),
        tx_rx_offset=float(params["tx_rx_offset"]),
        cell_size=cell_size,
        pml_cells=pml_cells,
        buffer_cells=buffer_cells,
    )
    time_window = harmonic_time_window(
        frequency,
        domain_x=geometry.domain_x,
        domain_y=geometry.domain_y,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        eps0=eps0,
        mu0=mu0,
        ramp_periods=ramp_periods,
        settle_transit_multiplier=settle_transit_multiplier,
        extraction_periods=extraction_periods,
        transit_safety=transit_safety,
    )
    return build_params(
        target_shape=str(params["target_shape"]),
        target_size=float(params["target_size"]),
        target_parameters=target_parameters,
        standoff=float(params["standoff"]),
        tx_rx_offset=float(params["tx_rx_offset"]),
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        plastic_epsr=float(params["plastic_epsr"]),
        plastic_sigma=float(params["plastic_sigma"]),
        eps0=eps0,
        mu0=mu0,
        frequencies_hz=[frequency],
        cell_size=cell_size,
        waveform=DEFAULT_HARMONIC_WAVEFORM,
        center_frequency=frequency,
        time_window=time_window,
        pml_cells=pml_cells,
    )


def build_frequency_scaled_params_from_base(
    params: dict[str, Any],
    frequency_hz: float,
    *,
    cells_per_wavelength: float = DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
    max_cell_size: float | None = None,
    center_frequency_scale: float = 1.0,
) -> dict[str, Any]:
    """Build the one-frequency cache-key params for a scaled-grid run."""

    if center_frequency_scale <= 0.0:
        raise ValueError("center_frequency_scale must be positive.")
    maximum_cell_size = float(params.get("cell_size", DEFAULT_CELL_SIZE) if max_cell_size is None else max_cell_size)
    frequency = float(frequency_hz)
    target_parameters = params.get("target_parameters")
    return build_params(
        target_shape=str(params["target_shape"]),
        target_size=float(params["target_size"]),
        target_parameters=target_parameters,
        standoff=float(params["standoff"]),
        tx_rx_offset=float(params["tx_rx_offset"]),
        sand_epsr=float(params["sand_epsr"]),
        sand_sigma=float(params["sand_sigma"]),
        plastic_epsr=float(params["plastic_epsr"]),
        plastic_sigma=float(params["plastic_sigma"]),
        eps0=float(params["eps0"]),
        mu0=float(params["mu0"]),
        frequencies_hz=[frequency],
        cell_size=frequency_scaled_cell_size(
            frequency,
            sand_epsr=float(params["sand_epsr"]),
            sand_sigma=float(params["sand_sigma"]),
            eps0=float(params["eps0"]),
            mu0=float(params["mu0"]),
            cells_per_wavelength=cells_per_wavelength,
            max_cell_size=maximum_cell_size,
        ),
        waveform=str(params.get("waveform", DEFAULT_WAVEFORM)),
        center_frequency=frequency * float(center_frequency_scale),
        time_window=float(params.get("time_window", DEFAULT_TIME_WINDOW)),
        pml_cells=int(params.get("pml_cells", DEFAULT_PML_CELLS)),
    )


def build_frequency_scaled_params(
    *,
    target_shape: str,
    target_size: float,
    target_parameters: dict[str, Any] | None = None,
    standoff: float,
    tx_rx_offset: float,
    sand_epsr: float,
    sand_sigma: float,
    plastic_epsr: float,
    plastic_sigma: float,
    eps0: float,
    mu0: float,
    frequencies_hz: Iterable[float],
    max_cell_size: float = DEFAULT_CELL_SIZE,
    cells_per_wavelength: float = DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
    waveform: str = DEFAULT_WAVEFORM,
    center_frequency_scale: float = 1.0,
    time_window: float = DEFAULT_TIME_WINDOW,
    pml_cells: int = DEFAULT_PML_CELLS,
) -> list[dict[str, Any]]:
    """Return one cache-key parameter dict per requested frequency."""

    base = build_params(
        target_shape=target_shape,
        target_size=target_size,
        target_parameters=target_parameters,
        standoff=standoff,
        tx_rx_offset=tx_rx_offset,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        plastic_epsr=plastic_epsr,
        plastic_sigma=plastic_sigma,
        eps0=eps0,
        mu0=mu0,
        frequencies_hz=list(frequencies_hz),
        cell_size=max_cell_size,
        waveform=waveform,
        center_frequency=DEFAULT_CENTER_FREQUENCY,
        time_window=time_window,
        pml_cells=pml_cells,
    )
    return [
        build_frequency_scaled_params_from_base(
            base,
            frequency,
            cells_per_wavelength=cells_per_wavelength,
            max_cell_size=max_cell_size,
            center_frequency_scale=center_frequency_scale,
        )
        for frequency in sorted(base["frequencies_hz"])
    ]


def load_frequency_sweep(
    params: dict[str, Any],
    *,
    prefer_harmonic: bool = True,
    prefer_scaled: bool = True,
    cells_per_wavelength: float = DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
    max_cell_size: float | None = None,
    center_frequency_scale: float = 1.0,
) -> dict[str, Any] | None:
    """Load gprMax data for a sweep, preferring harmonic then scaled caches.

    Three cache formats can satisfy a lookup, tried in order:

    1. per-frequency harmonic (``contsine``) runs -- one exact frequency
       solved directly, no broadband pulse or post-hoc DFT extraction;
    2. per-frequency scaled Ricker runs -- the older broadband-pulse-per-
       frequency format;
    3. the legacy single whole-sweep blob.

    Each is tried only if every requested frequency has an entry in that
    format, so a partially regenerated cache falls back cleanly instead of
    mixing harmonic and Ricker frequencies in one row.
    """

    if prefer_harmonic:
        harmonic = load_harmonic_frequency_sweep(params)
        if harmonic is not None:
            return harmonic
    if prefer_scaled:
        scaled = load_scaled_frequency_sweep(
            params,
            cells_per_wavelength=cells_per_wavelength,
            max_cell_size=max_cell_size,
            center_frequency_scale=center_frequency_scale,
        )
        if scaled is not None:
            return scaled
    return load(params)


def load_harmonic_frequency_sweep(
    params: dict[str, Any],
    *,
    cells_per_wavelength: float = DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
    max_cell_size: float | None = None,
    buffer_cells: int = 12,
    ramp_periods: float = DEFAULT_HARMONIC_RAMP_PERIODS,
    settle_transit_multiplier: float = DEFAULT_HARMONIC_SETTLE_TRANSIT_MULTIPLIER,
    extraction_periods: float = DEFAULT_HARMONIC_EXTRACTION_PERIODS,
    transit_safety: float = DEFAULT_HARMONIC_TRANSIT_SAFETY,
) -> dict[str, Any] | None:
    entries: list[dict[str, Any]] = []
    frequency_params: list[dict[str, Any]] = []
    for frequency in sorted(params["frequencies_hz"]):
        one_frequency_params = build_harmonic_params_from_base(
            params,
            float(frequency),
            cells_per_wavelength=cells_per_wavelength,
            max_cell_size=max_cell_size,
            buffer_cells=buffer_cells,
            ramp_periods=ramp_periods,
            settle_transit_multiplier=settle_transit_multiplier,
            extraction_periods=extraction_periods,
            transit_safety=transit_safety,
        )
        cached = load(one_frequency_params)
        if cached is None:
            return None
        frequency_params.append(cached["params"])
        frequency_entries = list(iter_frequency_results(cached))
        if len(frequency_entries) != 1:
            raise ValueError("A harmonic cache entry must contain exactly one frequency.")
        entry = dict(frequency_entries[0])
        entry["cache_key"] = cached.get("key")
        entry["cell_size"] = float(cached["params"]["cell_size"])
        entry["center_frequency"] = float(cached["params"]["center_frequency"])
        entries.append(entry)

    combined_params = dict(params)
    combined_params["frequency_cache_mode"] = "per_frequency_harmonic"
    combined_params["harmonic_cells_per_wavelength"] = float(cells_per_wavelength)
    combined_params["harmonic_max_cell_size"] = float(
        params.get("cell_size", DEFAULT_CELL_SIZE) if max_cell_size is None else max_cell_size
    )
    combined_params["per_frequency_params"] = frequency_params
    result = {
        "cache_mode": "per_frequency_harmonic",
        "frequencies_hz": [entry["frequency_hz"] for entry in entries],
        "scattered_real": [entry["scattered_real"] for entry in entries],
        "scattered_imag": [entry["scattered_imag"] for entry in entries],
        "tx": entries[0]["tx"] if entries else None,
        "rx": entries[0]["rx"] if entries else None,
        "target_center": entries[0]["target_center"] if entries else None,
        "domain": entries[0]["domain"] if entries else None,
        "num_iterations": [entry["num_iterations"] for entry in entries],
        "dt": [entry["dt"] for entry in entries],
        "wall_clock_seconds": sum(float(entry["wall_clock_seconds"]) for entry in entries),
        "per_frequency": entries,
    }
    return {"key": case_key(combined_params), "params": combined_params, "result": result}


def load_scaled_frequency_sweep(
    params: dict[str, Any],
    *,
    cells_per_wavelength: float = DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
    max_cell_size: float | None = None,
    center_frequency_scale: float = 1.0,
) -> dict[str, Any] | None:
    entries: list[dict[str, Any]] = []
    frequency_params: list[dict[str, Any]] = []
    for frequency in sorted(params["frequencies_hz"]):
        one_frequency_params = build_frequency_scaled_params_from_base(
            params,
            float(frequency),
            cells_per_wavelength=cells_per_wavelength,
            max_cell_size=max_cell_size,
            center_frequency_scale=center_frequency_scale,
        )
        cached = load(one_frequency_params)
        if cached is None:
            return None
        frequency_params.append(cached["params"])
        frequency_entries = list(iter_frequency_results(cached))
        if len(frequency_entries) != 1:
            raise ValueError("A frequency-scaled cache entry must contain exactly one frequency.")
        entry = dict(frequency_entries[0])
        entry["cache_key"] = cached.get("key")
        entry["cell_size"] = float(cached["params"]["cell_size"])
        entry["center_frequency"] = float(cached["params"]["center_frequency"])
        entries.append(entry)

    combined_params = dict(params)
    combined_params["frequency_cache_mode"] = "per_frequency_scaled"
    combined_params["frequency_scaled_cells_per_wavelength"] = float(cells_per_wavelength)
    combined_params["frequency_scaled_max_cell_size"] = float(
        params.get("cell_size", DEFAULT_CELL_SIZE) if max_cell_size is None else max_cell_size
    )
    combined_params["frequency_scaled_center_frequency_scale"] = float(center_frequency_scale)
    combined_params["per_frequency_params"] = frequency_params
    result = {
        "cache_mode": "per_frequency_scaled",
        "frequencies_hz": [entry["frequency_hz"] for entry in entries],
        "scattered_real": [entry["scattered_real"] for entry in entries],
        "scattered_imag": [entry["scattered_imag"] for entry in entries],
        "tx": entries[0]["tx"] if entries else None,
        "rx": entries[0]["rx"] if entries else None,
        "target_center": entries[0]["target_center"] if entries else None,
        "domain": entries[0]["domain"] if entries else None,
        "num_iterations": [entry["num_iterations"] for entry in entries],
        "dt": [entry["dt"] for entry in entries],
        "wall_clock_seconds": sum(float(entry["wall_clock_seconds"]) for entry in entries),
        "per_frequency": entries,
    }
    return {"key": case_key(combined_params), "params": combined_params, "result": result}


def iter_frequency_results(cached: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield one normalised result record per cached frequency."""

    result = cached["result"]
    if "per_frequency" in result:
        for entry in result["per_frequency"]:
            yield dict(entry)
        return

    common_fields = {
        "tx": result.get("tx"),
        "rx": result.get("rx"),
        "target_center": result.get("target_center"),
        "domain": result.get("domain"),
        "num_iterations": result.get("num_iterations"),
        "dt": result.get("dt"),
        "wall_clock_seconds": result.get("wall_clock_seconds", 0.0),
    }
    params = cached.get("params", {})
    if "cell_size" in params:
        common_fields["cell_size"] = params["cell_size"]
    if "center_frequency" in params:
        common_fields["center_frequency"] = params["center_frequency"]
    for frequency, real, imag in zip(
        result["frequencies_hz"],
        result["scattered_real"],
        result["scattered_imag"],
    ):
        entry = dict(common_fields)
        entry["frequency_hz"] = float(frequency)
        entry["scattered_real"] = float(real)
        entry["scattered_imag"] = float(imag)
        yield entry


def cell_size_label(cached: dict[str, Any]) -> str:
    """Short display label for one or more gprMax cell sizes."""

    cell_sizes = [float(entry["cell_size"]) for entry in iter_frequency_results(cached) if "cell_size" in entry]
    if not cell_sizes and "cell_size" in cached.get("params", {}):
        cell_sizes = [float(cached["params"]["cell_size"])]
    if not cell_sizes:
        return "unknown"
    min_mm = min(cell_sizes) * 1.0e3
    max_mm = max(cell_sizes) * 1.0e3
    if math.isclose(min_mm, max_mm, rel_tol=1.0e-12, abs_tol=1.0e-12):
        return f"{max_mm:.2g}mm"
    return f"{min_mm:.2g}-{max_mm:.2g}mm"


def wall_clock_seconds(cached: dict[str, Any]) -> float:
    """Total gprMax wall-clock seconds represented by a cache payload."""

    result = cached["result"]
    if "wall_clock_seconds" in result:
        return float(result["wall_clock_seconds"])
    return sum(float(entry.get("wall_clock_seconds", 0.0)) for entry in iter_frequency_results(cached))
