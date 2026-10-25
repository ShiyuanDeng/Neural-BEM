"""Stable stage inputs, numerical state and restart/result records.

M, K_geometry and physics-resolution tokens retain their public field names.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
import hashlib
import pickle
import numpy as np
from .continuation.geometry import FourierCurve, integer

@dataclass(frozen=True)
class FitStage:
    """One policy decision: the objective, the shape space and the work allowed."""
    label: str
    observations: tuple  # inverse.Observation, one per active frequency (F)
    weights: tuple  # objective weight per active frequency
    discrepancy_tolerances: tuple  # production/refined agreement per frequency
    update_modes: int  # M
    curve_modes: int  # K
    nodes: int  # N for the objective and Jacobian
    refined_nodes: int  # acceptance and numerical-regime check
    iterations: int  # LM iteration cap
    quota: Optional[int] = None  # work units for this stage
    resolution_kind: str = 'nodal'

    def __post_init__(self):
        count = len(self.observations)
        if not count or len(self.weights) != count or len(self.discrepancy_tolerances) != count:
            raise ValueError("One weight and tolerance is required per active observation.")
        if any(not np.isfinite(w) or w < 0 for w in self.weights) or not any(self.weights):
            raise ValueError("Weights must be finite, nonnegative and not all zero.")
        for name in ("curve_modes", "nodes", "refined_nodes"):
            integer(getattr(self, name), name)
        integer(self.update_modes, "update_modes", minimum=0)
        integer(self.iterations, "iterations", minimum=0)
        if self.resolution_kind not in ('nodal', 'modal'):
            raise ValueError('resolution_kind must be nodal or modal.')
        if self.refined_nodes <= self.nodes:
            raise ValueError('Resolution must refine strictly.')
        if self.resolution_kind == 'modal' and (self.nodes % 8 or self.refined_nodes % 8):
            raise ValueError('Modal resolution tokens must be positive multiples of eight.')
        if self.resolution_kind == 'nodal' and self.nodes <= 2 * self.curve_modes:
            raise ValueError("Nodes must resolve the curve band and refine strictly.")
        if self.quota is not None:
            integer(self.quota, "quota")



@dataclass(frozen=True)
class BackendConfig:
    """SPD continuation LM settings; bounds apply by harmonic order 0, 1, >=2."""
    initial_damping: float = 1e-3
    damping_increase: float = 10.0
    damping_decrease: float = 0.3
    max_damping_trials: int = 5
    max_backtracks: int = 7
    gradient_tolerance: float = 1e-7
    loss_tolerance: float = 1e-14
    relative_step_tolerance: float = 1e-7
    scaling_floor: float = 1.0
    step_bounds_m: tuple = (0.012, 0.018, 0.006)
    acceptance_absolute_margin: float = 1e-14
    acceptance_relative_margin: float = 1e-8
    cross_resolution_factor: float = 5.0
    residual_floor: float = 1e-12
    domain_box: Optional[tuple] = None  # ((xmin, ymin), (xmax, ymax)) in package units
    # "coefficient" clips each coordinate to `step_bounds_m` (SPD's rule, the
    # default). "physical" instead scales the whole proposal so its maximum
    # normal move is at most `physical_step_bound_m`, keeping its direction and
    # a bound that does not grow with the band M. A shared-backend option,
    # added after the 2026-09-24 review; runs before it used "coefficient".
    step_control: str = "coefficient"
    physical_step_bound_m: float = 0.006
    # SC-031 opt-in regularizing LM (defaults reproduce V2 bitwise).
    # damping_rule "schedule": first damping of an iteration carries over
    # (initial_damping, then x damping_decrease after success). "hanke": it
    # solves ||r + J d(lam)|| = hanke_ratio ||r|| each iteration (Hanke 1997),
    # falling back to a Gauss-Newton floor when unattainable. metric
    # "marquardt": max(diag G, scaling_floor); "mass"/"curvature": the
    # update's physical step metric, with smoothing length
    # 1 / (detectability_factor * exterior wavenumber of the stage's highest
    # frequency). log_model adds pred = -g.d - d.G.d/2 to every trial record.
    damping_rule: str = "schedule"
    hanke_ratio: float = 0.7
    metric: str = "marquardt"
    detectability_factor: float = 2.5
    log_model: bool = False
    # ON-001 opt-in; sampled reach is a proxy, never an admissibility certificate.
    reach_fraction: float = 0.0
    resolution_gate: str = "absolute"
    # CI-SPD feedback is opt-in until recovery retention is measured.
    damping_floor_relative: float = 1e-6
    geometry_proposal_cap: int = 2000
    progress_window: int = 5
    minimum_relative_progress: float = .01
    avoid_terminal_linearization: bool = False
    plain_progress_exit: bool = False

    def __post_init__(self):
        if self.resolution_gate not in ("absolute", "decision"):
            raise ValueError("resolution_gate must be 'absolute' or 'decision'")
        if not 0 <= self.reach_fraction <= 1:
            raise ValueError("reach_fraction must lie in [0, 1]")
        if self.damping_rule not in ("schedule", "hanke", "agreement"):
            raise ValueError(f"Unknown damping rule {self.damping_rule!r}.")
        if self.metric not in ("marquardt", "mass", "curvature"):
            raise ValueError(f"Unknown step metric {self.metric!r}.")
        if not 0 < self.hanke_ratio < 1 or not self.detectability_factor > 0:
            raise ValueError("hanke_ratio must lie in (0, 1) and detectability_factor must be positive.")
        if not np.isfinite(self.damping_floor_relative) or not 0 < self.damping_floor_relative < 1:
            raise ValueError('Damping floor must be a finite relative curvature in (0,1).')
        integer(self.geometry_proposal_cap, 'geometry_proposal_cap')
        integer(self.progress_window, 'progress_window')
        if not np.isfinite(self.minimum_relative_progress) or not 0 <= self.minimum_relative_progress < 1:
            raise ValueError('Minimum progress must lie in [0,1).')

    def bounds(self, orders):
        order = np.asarray(orders)
        return np.where(order == 0, self.step_bounds_m[0],
                        np.where(order == 1, self.step_bounds_m[1], self.step_bounds_m[2]))



@dataclass(frozen=True)
class Evaluation:
    curve: FourierCurve
    loss: float
    relative_l2: float
    residual: np.ndarray = field(repr=False)
    prediction: np.ndarray = field(repr=False)  # (pairs, frequencies)
    forwards: tuple = field(repr=False, default=())



@dataclass
class StageResult:
    stage_label: str
    curve: FourierCurve
    outcome: str
    stop_reason: Optional[str]
    converged: bool
    accepted_steps: int
    initial_loss: float
    final_loss: float
    history: list
    trials: list
    acceptance_checks: list
    detail: Optional[str] = None
    work: dict = field(default_factory=dict)
    seconds: float = 0.0
    checkpoint: object = field(default=None, repr=False)
    resolution_events: list = field(default_factory=list)
    final_nodes: Optional[int] = None
    final_refined_nodes: Optional[int] = None
    physics_failures: list = field(default_factory=list)
    geometry_proposals: int = 0
    final_entry: object = field(default=None, repr=False)
    entry_reused: bool = False



@dataclass(frozen=True, eq=False)
class StageEntry:
    """An evaluated stage endpoint offered to the next stage for exact reuse.

    The production prediction keeps its factorized forward states, so the next
    stage builds its own Jacobian without new solves. ``refined_prediction`` is
    present when the stage already validated this curve. Reuse requires the same
    curve bytes, active catalog (identical objects), contrast, physics service and
    both resolutions; the ledger is charged exactly as the replaced solves.
    """
    curve_bytes: bytes = field(repr=False)
    band: int
    nodes: int
    refined_nodes: int
    observations: tuple = field(repr=False)
    contrast: float
    physics: object = field(repr=False)
    prediction: np.ndarray = field(repr=False)
    forwards: tuple = field(repr=False)
    refined_prediction: object = field(default=None, repr=False)

    def matches(self, curve, stage, contrast, physics):
        return bool(curve.band == self.band and curve.coefficients.tobytes() == self.curve_bytes and
                    stage.nodes == self.nodes and stage.refined_nodes == self.refined_nodes and
                    len(stage.observations) == len(self.observations) and
                    all(a is b for a, b in zip(stage.observations, self.observations)) and
                    float(contrast) == self.contrast and physics is self.physics and
                    len(self.forwards) == len(self.observations))



@dataclass
class StageCheckpoint:
    """Accepted-state restart, retaining the exact linearization and next damping.

    No LU factors are needed until the next accepted candidate. Cached refined
    values are part of the state so pause/resume does not add solves or reset
    quotas. The caller must restore the matching ledger before resuming.
    """
    signature: str
    stage: FitStage
    current: Evaluation
    matrix: np.ndarray
    gradient: np.ndarray
    iteration: int
    damping: float
    initial_loss: float
    scale: float
    work: dict
    history: list
    trials: list
    checks: list
    refined_cache: dict



def checkpoint_signature(stage, contrast, config, update):
    # Hashing pickle bytes does not deserialize or execute any external input.
    return hashlib.sha256(pickle.dumps((stage, float(contrast), config, update.settings()),
                                      protocol=5)).hexdigest()



@dataclass(frozen=True)
class ResolutionResponse:
    """One opt-in promotion followed by ordinary backtracking at the upper pair.

    The caller supplies the same physics service at the finer execution profile
    (RB-001 uses one frequency worker). This mechanism is for ordinary losses.
    """
    production_nodes: int = 1024
    refined_nodes: int = 2048
    physics: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.production_nodes <= 0 or self.refined_nodes <= self.production_nodes:
            raise ValueError('Resolution response must refine strictly')



class _PromoteBase(Exception):
    pass





def stage_record(stage):
    """Portable description of a stage without observation arrays."""
    record = {k: v for k, v in asdict(stage).items() if k != "observations"}
    record["wavenumbers"] = [o.wavenumber for o in stage.observations]
    return record

