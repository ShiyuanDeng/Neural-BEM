"""Continuation decisions taken from the measured atlas, not from a formula.

The established baseline prescribes both halves of a continuation step: the
next frequency comes from a fixed ladder, and the admissible shape bandwidth
from a rule such as `floor(3 max(k, ki))`. This policy replaces both with
quantities measured at the current boundary.

The band rule is the one the measurements support. A shape harmonic is worth
admitting at frequency `k` only if there is an amplitude at which it is both

* detectable - its whitened column norm puts an RMS normal displacement
  `eps_min(k, p)` above one noise unit - and
* linearly predictable - that amplitude is still inside the linearization
  horizon `eps*(k)`, beyond which `J h` stops describing the measured change
  in the data.

The admissible band is therefore where those two curves cross,
`eps_min(k, p) <= gamma eps*(k)`, rather than a multiple of the wavenumber.
The horizon is measured online by a short bracket of finite steps, using the
residual-free criterion, so it is a property of the geometry and frequency
rather than of the optimizer's current progress.

Frequencies are chosen by the same evidence: the largest admissible jump whose
Gauss-Newton model still delivers a declared fraction of its own promised
misfit decrease. Every probe is charged to the same `Work` budget as the
inversion, so an arm that measures more has fewer solves left to optimize
with. The policy sees geometry, contrast, acquisition and data; it never sees
truth or held-out data.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .atlas import (Whitening, cell_at, harmonic_index, to_solver_coefficients)
from .continuation import Decision
from .forward import BudgetExceeded, solve
from .geometry import displaced, grid_size, integer
from .horizon import gauss_newton_direction, perturbed
from .inverse import FitConfig
from .schedule import Stage


def even_at_least(value):
    return 2 * int(np.ceil(value / 2))


def harmonic_sensitivity(cell):
    """Whitened column norms with each harmonic's cosine and sine combined."""
    band = (len(cell.sensitivity) - 1) // 2
    combined = np.zeros(band + 1)
    np.add.at(combined, harmonic_index(band), cell.sensitivity ** 2)
    return np.sqrt(combined)


def detection_thresholds(sensitivity, perimeter):
    """Smallest RMS normal displacement each harmonic moves above one sigma.

    Columns are unit `L^2(ds)`, so a coefficient `a` is an RMS displacement
    `a / sqrt(L)` and the whitened column norm is the signal-to-noise ratio of
    a unit-coefficient displacement. Its reciprocal, rescaled, is the
    detection threshold in the same length unit as the geometry.
    """
    sensitivity = np.asarray(sensitivity, float)
    with np.errstate(divide="ignore"):
        return np.where(sensitivity > 0,
                        1.0 / (np.sqrt(perimeter) * sensitivity), np.inf)


def harmonic_horizons(sensitivity, ceiling, saturation):
    """Per-harmonic horizon predicted from the free atlas diagonal.

    Measuring a horizon for every cell is unaffordable. What the measurements
    support instead is that the second-order remainder of a normal
    displacement is nearly harmonic-independent, while the first-order term is
    proportional to the column norm, so the horizon rises linearly with
    relative sensitivity until it meets the frequency's own ceiling:

        eps*(k, p) = eps*(k) min(1, c s(k, p) / max_q s(k, q)).

    One probe per frequency therefore calibrates `eps*(k)` and the diagonal
    supplies the rest. This is an empirical law and it is not universal: it
    holds closely at low contrast and breaks down at high contrast, where the
    second-order response acquires its own harmonic structure.
    """
    sensitivity = np.asarray(sensitivity, float)
    peak = float(sensitivity.max()) if sensitivity.size else 0.0
    if not np.isfinite(ceiling) or ceiling <= 0 or peak <= 0:
        return np.zeros_like(sensitivity)
    return ceiling * np.minimum(1.0, saturation * sensitivity / peak)


def window_band(sensitivity, perimeter, ceiling, *, safety=1.0, saturation=2.0):
    """Highest harmonic that is detectable at an amplitude the model still predicts.

    A harmonic earns its place only if its detection threshold lies inside its
    own horizon: below that amplitude it is invisible, above it the derivative
    that justifies admitting it no longer describes the data. Contiguity is
    enforced, because a contiguous band is what the optimizer applies.
    """
    sensitivity = np.asarray(sensitivity, float)
    admissible = (detection_thresholds(sensitivity, perimeter)
                  <= safety * harmonic_horizons(sensitivity, ceiling, saturation))
    band = 0
    for harmonic in range(1, len(sensitivity)):
        if not admissible[harmonic]:
            break
        band = harmonic
    return max(1, band)


def measure_horizon(shape, state, jacobian, direction, storage_band, *,
                    brackets, tolerance, work, wavenumber, contrast, acquisition,
                    nodes):
    """Largest RMS step along `direction` where `J h` still predicts the data.

    Residual-free: it compares the measured change in the scattered field with
    the Jacobian's prediction, so a frequency whose residual happens to be
    small does not report a small horizon. The bracket is walked from the
    largest candidate down, and the first rung inside tolerance is returned
    together with every rung tried.
    """
    perimeter = float(state.curve.perimeter)
    unit = direction / max(np.linalg.norm(direction), np.finfo(float).tiny)
    rungs, horizon = [], float("nan")
    for amplitude in brackets:
        coefficients = unit * amplitude * np.sqrt(perimeter)
        rung = dict(amplitude=float(amplitude))
        rungs.append(rung)
        try:
            moved = perturbed(shape, coefficients, storage_band, tolerance=1e-3)
            prediction = solve(moved.shape, wavenumber, contrast, acquisition,
                               nodes, work=work).prediction
        except BudgetExceeded:
            raise
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            rung["failure"] = str(exc)
            continue
        linear = jacobian @ coefficients
        scale = float(np.linalg.norm(linear))
        if scale <= 0:
            rung["failure"] = "the Jacobian predicts no change along this direction"
            continue
        error = float(np.linalg.norm(prediction - state.prediction - linear) / scale)
        rung.update(relative_error=error, achieved=moved.rms_displacement)
        if error <= tolerance:
            horizon = moved.rms_displacement
            break
    return horizon, rungs


@dataclass(frozen=True)
class ProbeReport:
    """What one probed frequency reported at the current geometry."""
    wavenumber: float
    probe_band: int
    nodes: int
    relative_residual: float
    sensitivity: list
    horizon: float
    horizon_rungs: list
    band: int
    model_ratio: float
    predicted_decrease: float
    actual_decrease: float
    step: float
    step_rms: float
    effective_rank: int
    forwards: int

    @property
    def usable(self):
        return np.isfinite(self.horizon) and self.horizon > 0

    def as_record(self):
        return dict(wavenumber=self.wavenumber, probe_band=self.probe_band,
                    nodes=self.nodes, relative_residual=self.relative_residual,
                    horizon=self.horizon, band=self.band,
                    model_ratio=self.model_ratio, step=self.step,
                    step_rms=self.step_rms, effective_rank=self.effective_rank,
                    predicted_decrease=self.predicted_decrease,
                    actual_decrease=self.actual_decrease, forwards=self.forwards,
                    horizon_rungs=self.horizon_rungs,
                    harmonic_sensitivity=self.sensitivity)


def probe(shape, observation, contrast, *, probe_band, storage_band, nodes,
          whitening, work, radius, safety, horizon_tolerance, brackets,
          saturation=2.0, horizon_band=3, steps=(1.0, 0.5, 0.25)):
    """Measure one frequency's horizon, admissible band and model quality.

    Costs one solve and one Jacobian for the cell, up to `len(brackets)` solves
    for the horizon, and up to `len(steps)` solves for the model check.
    """
    before = work.attempted
    cell, state, jacobian = cell_at(shape, observation, contrast, probe_band, nodes,
                                    whitening=whitening, work=work, dense=True)
    perimeter = float(shape.nodes(grid_size(shape.band)).perimeter)
    sensitivity = harmonic_sensitivity(cell)
    # The direction used to measure the horizon must itself lie inside the
    # window, or the measurement destroys its own premise: a Gauss-Newton step
    # over a provisional band amplifies exactly the harmonics whose horizon has
    # already collapsed, and reports their failure as the frequency's. A low,
    # always-admissible band is safe because the horizon is nearly independent
    # of harmonic index inside the window.
    horizon, rungs = measure_horizon(
        shape, state, jacobian, gauss_newton_direction(cell, band_limit=horizon_band),
        storage_band, brackets=[radius * factor for factor in brackets],
        tolerance=horizon_tolerance, work=work, wavenumber=observation.wavenumber,
        contrast=contrast, acquisition=observation.acquisition, nodes=nodes)
    ceiling = horizon if np.isfinite(horizon) else radius * min(brackets)
    band = window_band(sensitivity, perimeter, ceiling, safety=safety,
                       saturation=saturation)
    direction = gauss_newton_direction(cell, band_limit=band)
    raw = to_solver_coefficients(direction, perimeter)
    slope = float(cell.gradient @ direction)
    curvature = float(direction @ cell.gauss_newton @ direction)
    ratio, predicted, actual = float("nan"), float("nan"), float("nan")
    used, rms = float("nan"), float("nan")
    for step in steps:
        predicted = -(step * slope - 0.5 * step ** 2 * curvature)
        try:
            moved = displaced(shape, raw, storage_band, step=step)
            prediction = solve(moved.shape, observation.wavenumber, contrast,
                               observation.acquisition, nodes, work=work).prediction
        except BudgetExceeded:
            raise
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            continue
        residual = (prediction - observation.scattered) / cell.sigma
        actual = cell.whitened_misfit - float(0.5 * np.sum(np.abs(residual) ** 2))
        ratio = actual / predicted if predicted > 0 else float("nan")
        used, rms = float(step), moved.rms_displacement
        break
    return ProbeReport(float(observation.wavenumber), probe_band, nodes,
                       cell.relative_residual, sensitivity.tolist(), horizon, rungs,
                       band, ratio, predicted, actual, used, rms,
                       cell.effective_rank(), work.attempted - before)


@dataclass
class AtlasPolicy:
    """Choose the next frequency and update band from probed atlas cells.

    `mode` selects how much of the atlas is used, so arms of a comparison
    differ in one declared ingredient at a time:

    * `fixed`     - the baseline: uniform ladder, prescribed band, no probes;
    * `band`      - the same ladder, with the band from the measured window;
    * `frequency` - the prescribed band, with the frequency chosen by probe;
    * `full`      - both measured.
    """
    observations: tuple
    contrast: float
    work: object
    mode: str = "full"
    ratio_floor: float = 0.25
    safety: float = 1.0
    horizon_tolerance: float = 0.1
    brackets: tuple = (2.0, 1.0, 0.5, 0.25)
    horizon_anchor: float = 0.12
    horizon_band: int = 3
    saturation: float = 2.0
    trust_radius: float = 0.05
    trust_minimum: float = 1e-4
    trust_maximum: float = 0.5
    maximum_jump: float = 2.0
    refine_at_top: bool = True
    probe_band_factor: float = 4.0
    probe_band_cap: int = 80
    maximum_probes: int = 3
    points_per_wavelength: float = 30.0
    minimum_nodes: int = 96
    curvature_minimum: int = 20
    band_rule: str = "paper"
    config: FitConfig = field(default_factory=FitConfig)
    whitening: Whitening = field(default_factory=lambda: Whitening("relative", 1e-3))
    k_stop: Optional[float] = None
    probes: list = field(default_factory=list)
    decisions: list = field(default_factory=list)

    def __post_init__(self):
        if self.mode not in ("band", "frequency", "full", "fixed"):
            raise ValueError("mode must be fixed, band, frequency or full.")
        if self.band_rule not in ("paper", "driver", "scaled"):
            raise ValueError("band_rule must be paper, driver or scaled.")
        self.catalog = {float(o.wavenumber): o for o in self.observations}
        self.grid = np.array(sorted(self.catalog))
        if self.k_stop is None:
            self.k_stop = float(self.grid[-1])
        integer(self.maximum_probes, "maximum_probes", minimum=1)

    @property
    def probing(self):
        return self.mode != "fixed"

    # -- resolution and band rules --------------------------------------------------

    def prescribed_band(self, wavenumber, perimeter):
        largest = wavenumber * max(1.0, np.sqrt(self.contrast))
        if self.band_rule == "paper":
            return max(1, int(np.floor(3 * largest)))
        scale = wavenumber if self.band_rule == "driver" else largest
        return max(1, int(np.floor(2 * scale * perimeter / (2 * np.pi))))

    def storage_for(self, wavenumber, perimeter, band, previous_curve_modes):
        return max(previous_curve_modes, band,
                   int(np.ceil(self.points_per_wavelength * perimeter * wavenumber / (2 * np.pi))))

    def nodes_for(self, wavenumber, perimeter, storage):
        largest = wavenumber * max(1.0, np.sqrt(self.contrast))
        return even_at_least(max(self.minimum_nodes, 2 * (storage + 1) + 2,
                                 self.points_per_wavelength * perimeter * largest / (2 * np.pi)))

    def stage_for(self, wavenumber, perimeter, band, previous_curve_modes):
        storage = self.storage_for(wavenumber, perimeter, band, previous_curve_modes)
        return Stage(float(wavenumber), band, storage,
                     self.nodes_for(wavenumber, perimeter, storage),
                     max(self.curvature_minimum, band))

    def probe_band_for(self, wavenumber):
        largest = wavenumber * max(1.0, np.sqrt(self.contrast))
        return int(min(self.probe_band_cap, max(8, self.probe_band_factor * largest + 8)))

    def bracket_radius(self, wavenumber):
        """Where to centre this frequency's horizon bracket.

        Anchoring on the measured `eps* ~ anchor / k` scaling rather than on
        the previous frequency's answer keeps the estimate from sticking at
        whichever rung happened to pass first, while the rungs themselves are
        still decided by measurement.
        """
        return float(np.clip(self.horizon_anchor / wavenumber,
                             self.trust_minimum, self.trust_maximum))

    def probe_at(self, shape, perimeter, wavenumber, stored):
        band = self.probe_band_for(wavenumber)
        storage = self.storage_for(wavenumber, perimeter, band, stored)
        report = probe(shape, self.catalog[wavenumber], self.contrast, probe_band=band,
                       storage_band=storage, nodes=self.nodes_for(wavenumber, perimeter, storage),
                       whitening=self.whitening, work=self.work,
                       radius=self.bracket_radius(wavenumber),
                       safety=self.safety, horizon_tolerance=self.horizon_tolerance,
                       brackets=self.brackets, horizon_band=self.horizon_band,
                       saturation=self.saturation)
        if report.usable:
            self.trust_radius = float(np.clip(report.horizon, self.trust_minimum,
                                              self.trust_maximum))
        else:
            self.trust_radius = float(np.clip(self.trust_radius * min(self.brackets),
                                              self.trust_minimum, self.trust_maximum))
        self.probes.append(dict(report.as_record(), trust_radius=self.trust_radius))
        return report

    # -- the decision ----------------------------------------------------------------

    def __call__(self, context):
        shape = context.shape
        perimeter = float(shape.nodes(grid_size(shape.band)).perimeter)
        previous = context.history[-1].decision.stage if context.history else None
        stored = max(shape.band, previous.curve_modes if previous else 1)
        candidates = self.candidates(previous.wavenumber if previous else None, context)
        if len(candidates) == 0:
            return None
        report = None
        if not self.probing:
            chosen = float(candidates[0])
        elif self.mode == "band" or len(candidates) == 1:
            chosen = float(candidates[0])
            report = self.probe_at(shape, perimeter, chosen, stored)
        else:
            chosen, report = self.search(shape, perimeter, candidates, stored)
        band = (report.band if (self.mode in ("band", "full") and report is not None)
                else min(self.prescribed_band(chosen, perimeter), self.probe_band_cap))
        stage = self.stage_for(chosen, perimeter, band, stored)
        self.decisions.append(dict(
            wavenumber=chosen, band=band, nodes=stage.nodes, curve_modes=stage.curve_modes,
            mode=self.mode, trust_radius=self.trust_radius,
            horizon=None if report is None else report.horizon,
            model_ratio=None if report is None else report.model_ratio,
            forwards=self.work.attempted))
        reason = (f"{self.mode}: k={chosen:g}, band={band}, horizon={self.trust_radius:.4g}"
                  + (f", model ratio={report.model_ratio:.3g}" if report is not None else ""))
        return Decision(stage, self.config, reason)

    def candidates(self, last, context):
        """Frequencies this decision may choose from.

        Every arm may keep working at the top of the ladder once it is reached,
        so an arm that jumps early does not simply stop with budget unspent.
        Refinement continues only while the previous decision still accepted an
        update, which is evidence the fixed ladder has too.
        """
        if last is None:
            return self.grid[self.grid <= self.k_stop][:1]
        ceiling = min(self.k_stop, last * self.maximum_jump)
        higher = self.grid[(self.grid > last) & (self.grid <= ceiling)]
        if len(higher):
            return higher
        # A sparse measured catalog may contain no point within the preferred
        # jump. Advance to its next available point rather than declaring the
        # inverse finished below k_stop; no missing-frequency data is invented.
        remaining = self.grid[(self.grid > last) & (self.grid <= self.k_stop)]
        if len(remaining):
            return remaining[:1]
        if last >= self.k_stop and self.refine_at_top and self.progressed(context):
            return np.array([self.k_stop])
        return np.array([])

    @staticmethod
    def progressed(context):
        if not context.history:
            return False
        record = context.history[-1]
        return record.committed and any("direction" in entry for entry in record.result.history)

    def search(self, shape, perimeter, candidates, stored):
        """Largest candidate whose model delivers a declared share of its promise.

        Probes walk down from the most ambitious admissible jump, so a
        well-behaved problem pays for one probe and a badly-behaved one pays
        for at most `maximum_probes` before falling back to the next grid
        point - which is what the fixed ladder would have chosen anyway.
        """
        last = None
        for wavenumber in self.candidate_order(candidates)[:self.maximum_probes]:
            report = self.probe_at(shape, perimeter, wavenumber, stored)
            last = report
            if np.isfinite(report.model_ratio) and report.model_ratio >= self.ratio_floor:
                return float(wavenumber), report
        return float(candidates[0]), last

    def candidate_order(self, candidates):
        """Most ambitious jump first, then halves of it, then the next grid point."""
        if len(candidates) == 1:
            return [candidates[0]]
        picks, index = [], len(candidates) - 1
        while index > 0 and len(picks) < self.maximum_probes - 1:
            picks.append(candidates[index])
            index //= 2
        picks.append(candidates[0])
        ordered, seen = [], set()
        for value in picks:
            if float(value) not in seen:
                seen.add(float(value))
                ordered.append(value)
        return ordered
