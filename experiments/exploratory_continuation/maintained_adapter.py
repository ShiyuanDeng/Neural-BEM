"""Coupled inputs for the maintained cumulative-policy interpreter.

No new optimizer or continuation schedule lives here. Componentwise complete
ProjectedUpdate trials feed runner.fit, whose actual CumulativePolicy operations
own all quotas, iterations, cleanup, release and frontier decisions.
"""
from dataclasses import replace
from time import perf_counter
import numpy as np
from scipy.linalg import block_diag

from experiments.cleaned_interface.geometry import ProjectedUpdate, resize, cleanup
from experiments.cleaned_interface.io import curve_record, curve_from
from experiments.cleaned_interface.physics import NodalKress
from experiments.cleaned_interface.policy import CumulativePolicy
from experiments.shape_continuation import forward as F
from experiments.shape_continuation.atlas import orthonormal_normal_basis
from experiments.shape_continuation.multi_object import MultiCurve, MultiUpdate


class CoupledProjectedUpdate(MultiUpdate):
    def __init__(self, length_unit_m):
        super().__init__(ProjectedUpdate(length_unit_m))

    @property
    def counts(self):
        return self.base.counts

    def settings(self):
        return dict(self.base.settings(), component_composition='independent projected trials; coupled physics',
                    metric='sum of per-component squared RMS normal displacements')


class CoupledGeometry:
    update = CoupledProjectedUpdate

    @staticmethod
    def resize(curve, band):
        return MultiCurve(tuple(resize(c, band) for c in curve.components), curve.ids)

    @staticmethod
    def cleanup(curve, retained_band, storage_band):
        return MultiCurve(tuple(cleanup(c, retained_band, storage_band) for c in curve.components), curve.ids)

    @staticmethod
    def record(curve):
        return dict(components=[curve_record(c) for c in curve.components], ids=curve.ids,
                    storage_band=curve.band)

    @staticmethod
    def restore(record):
        return MultiCurve(tuple(curve_from(c) for c in record['components']), tuple(record['ids']))


def preserve_td_start(problem, physics, rule, ledger, progress):
    """TD initialization is a common experimental input, not circle relocalization."""
    ledger.reserve(0)
    record = dict(reason='preserve common data-only TD seed configuration after initial numerical audit',
                  component_count=len(problem.initial.components), additional_localization_solves=0,
                  initializer='archived topological derivative; no truth or heldout access',
                  single_circle_mie_localization_replaced=True)
    progress([record])
    return problem.initial, record


class CoupledNodalKress(NodalKress):
    name = 'coupled_nodal_kress'

    def validate(self, problem):
        if not isinstance(problem.initial, MultiCurve):
            raise ValueError('Coupled backend requires MultiCurve input.')
        # Reuse all material/acquisition/device checks from the maintained service.
        super().validate(replace(problem, initial=problem.initial.components[0]))
        problem.initial.validate()

    def observable_frontier(self, curve, observation, contrast, top, threshold):
        state = self.evaluate(curve, observation, contrast,
                              self.resolution_profile(curve.band)['refined'])._handle
        started = perf_counter()
        self._record('derivative_attempts')
        try:
            basis = block_diag(*(orthonormal_normal_basis(c, top) for c in state.curve.components))
            jacobian = F.shape_jacobian(state, basis)
            norms = np.linalg.norm(jacobian, axis=0).reshape(len(curve.components), 2*top+1)
            paired = np.column_stack((norms[:, 0], np.hypot(norms[:, 1::2], norms[:, 2::2])))
            if not np.isfinite(paired).all() or paired.max() <= 0:
                raise FloatingPointError('No finite nonzero observable frontier')
            active = paired >= threshold*paired.max()
            frontier = int(np.flatnonzero(np.any(active, axis=0)).max())
        except Exception:
            self._record('failed_derivatives', perf_counter()-started)
            raise
        self._record('derivatives', perf_counter()-started)
        return dict(frontier=frontier, column_profile=paired, threshold=threshold, top=top, work_units=2,
                    component_ids=curve.ids,
                    extension='common band: maximum harmonic above threshold times global paired-column maximum; '
                              'direct sum of per-component L2(ds)-orthonormal normal bases')

    def receipt(self):
        return dict(super().receipt(), localization_model='prescribed common TD circles; Mie search replaced',
                    geometry='coupled disjoint Cartesian Fourier curves',
                    physics_extension='inherited maintained real/complex nodal service on OrderedBoundary2D')


class CoupledCumulativePolicy(CumulativePolicy):
    """Only input-prefix/localization descriptions differ from maintained policy."""
    def operations(self, problem, physics):
        if self.gamma != problem.damping_ratio:
            raise ValueError('Policy gamma and observation contract must agree.')
        operations = list(super().operations(problem, physics))
        operations[1] = replace(operations[1], label='prescribed_td_initialization',
            purpose='Retain the common qualified TD seed configuration',
            transition='same fixed-count seeds enter warmup; no single-circle localization',
            details=dict(original_localization='single-circle Mie search', replacement='common archived TD seeds',
                         reason='paired comparison requires identical data-only starts and component counts'))
        if self.gamma == 0:
            operations = [replace(op, purpose=op.purpose.replace('Damped', 'Real-catalog alias').replace('damped', 'real-catalog alias'),
                                  details=dict(op.details or {}, catalog_alias=True)) for op in operations]
        return tuple(operations)

    def plan(self, problem, physics):
        return dict(super().plan(problem, physics), adaptations=dict(
            maintained_policy_source='experiments.cleaned_interface.policy.CumulativePolicy',
            maintained_interpreter_source='experiments.cleaned_interface.runner.fit',
            geometry='componentwise complete ProjectedUpdate with coupled forward/reciprocal physics',
            initialization='common TD seeds replace inapplicable single-circle Mie localization',
            prefix_frequencies_hz=self.prefix_frequencies_hz, damping_ratio=self.gamma,
            information='same five real observations' if self.gamma == 0 else 'five real plus five explicitly qualified synthetic damped observations',
            frontier='direct-sum component bases; global threshold; common released band',
            frozen_default_reproduction=False))
