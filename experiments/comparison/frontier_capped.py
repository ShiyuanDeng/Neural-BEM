"""A schedule mixin: cap each stage's shape band at the frontier measured when the stage is entered.

The default sets every update band from the frequency alone. This mixin keeps the wrapped
policy's stages, order, data, quotas and iteration caps, and changes one thing: before each
fit stage after the first, the runner measures the observable frontier at the current outline
and contrast, at that stage's highest frequency (the solver's own measure and threshold), and
the stage runs with band ``max(1, min(default band, frontier))``. A stage whose default band is
at or below the frontier is the default stage, object for object.

Each measurement is one refined solve and one reciprocal batch, charged two work units by the
runner. With ``cap=False`` the measurements are made and recorded but no band changes.

Use as the first base of a frozen dataclass that also defines ``cap: bool`` and
``state: dict`` (``field(default_factory=dict, compare=False, repr=False)``).
"""
from dataclasses import replace

from bem_inverse.policy import Operation


class FrontierCapped:
    def operations(self, problem, physics):
        default = list(super().operations(problem, physics))
        first = next(i for i, op in enumerate(default) if op.kind == 'fit')
        head, rest = default[:first+1], default[first+1:]
        self.state.clear()
        self.state['remaining'] = rest
        following = next((op for op in rest if op.kind == 'fit'), None)
        if following is None:
            self.state['remaining'] = []
            return [*head, *rest]
        return [*head, self._measure_before(problem, following)]

    def _measure_before(self, problem, op):
        top = max(op.stage.observations, key=lambda o: o.frequency_hz)
        index = next(i for i, o in enumerate(problem.real) if o is top)
        return Operation('frontier', 'frontier_before_'+op.label,
            'Measure the paired-Jacobian frontier at the current curve and this stage\'s highest frequency',
            'previous stage returned', 'enter '+op.label+' with band min(default, frontier), at least 1',
            details=dict(observation_index=index, frequency_hz=top.frequency_hz,
                         threshold=self.frontier_threshold, top=self.frontier_top,
                         default_band=op.stage.update_modes, cap=self.cap))

    def _capped(self, problem, physics, op, frontier):
        default = op.stage.update_modes
        band = max(1, min(default, int(frontier))) if self.cap else default
        if band == default:
            return op
        storage = 2*band+2 if op.stage.curve_modes == 2*default+2 else op.stage.curve_modes
        capped = self._fit(problem, physics, op.label, op.stage.observations, band, storage,
                           op.stage.quota, op.stage.iterations,
                           purpose=f'{op.purpose}; band capped at the measured frontier {int(frontier)} (default {default})')
        return replace(capped, details=dict(capped.details, default_band=default, measured_frontier=int(frontier)))

    def tail(self, problem, physics, frontier):
        remaining = self.state.get('remaining')
        if not remaining:      # the wrapped policy's own frontier operation
            return super().tail(problem, physics, frontier)
        out = []
        while remaining[0].kind != 'fit':
            out.append(remaining.pop(0))
        out.append(self._capped(problem, physics, remaining.pop(0), frontier))
        following = next((op for op in remaining if op.kind == 'fit'), None)
        if following is None:
            out.extend(remaining)
            remaining.clear()
        else:
            out.append(self._measure_before(problem, following))
        return tuple(out)
