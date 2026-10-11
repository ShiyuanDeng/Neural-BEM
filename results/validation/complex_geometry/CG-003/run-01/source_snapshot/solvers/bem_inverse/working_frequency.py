"""ON-001 subset proposal model with unchanged full production/refined acceptance."""
from dataclasses import replace
import numpy as np
from .continuation.lm_backend import Objective, Evaluation, normalize


class WorkingSetChanged(Exception):
    """Rejected full-objective proposal expanded the model; rebuild before retry."""


class WorkingObjective(Objective):
    def __init__(self, *args, anchor_count=5, **kwargs):
        super().__init__(*args, **kwargs)
        if self.count != 19 or anchor_count not in (5, 9):
            raise ValueError("W requires the fixed 19-frequency stage and five/nine anchors")
        self.anchor_count = anchor_count
        self.anchors = (0, 4, 9, 14, 18) if anchor_count == 5 else tuple(np.rint(np.linspace(0, 18, 9)).astype(int))
        self.indices = ()
        self.events = []
        self.last_trial = {}

    def relative_residuals(self, evaluation):
        return np.linalg.norm(evaluation.prediction-self.observed, axis=0)/np.linalg.norm(self.observed, axis=0)

    def _subset(self, indices):
        weights = np.asarray(self.stage.weights)[list(indices)]
        stage = replace(self.stage, observations=tuple(self.stage.observations[i] for i in indices),
                        weights=tuple(weights/weights.sum()),
                        discrepancy_tolerances=tuple(self.stage.discrepancy_tolerances[i] for i in indices))
        return Objective(stage, self.contrast, self.config, self.ledger, physics=self.physics)

    def _normalize_subset(self, values, indices):
        # Preserve the full-data numerical residual floor as well as relative weights.
        shape = (values.shape[0], self.count)+values.shape[2:]
        padded = np.zeros(shape, complex)
        padded[:, list(indices)] = values
        full = normalize(padded, self.observed, self.stage.weights, self.config.residual_floor)
        tail = values.shape[2:]
        full = full.reshape((2, values.shape[0], self.count)+tail)
        return full[:, :, list(indices)].reshape((-1,)+tail)/np.sqrt(sum(self.stage.weights[i] for i in indices))

    def _choose(self, evaluation):
        residual = self.relative_residuals(evaluation)
        wanted = set(self.indices) | set(self.anchors)
        if residual.max() < .01:
            wanted = set(range(self.count))
        elif self.anchor_count == 5:
            excluded = [i for i in range(self.count) if i not in self.anchors]
            wanted.update(sorted(excluded, key=lambda i: (-residual[i], i))[:2])
        if len(wanted) > 9:
            wanted = set(range(self.count))
        indices = tuple(sorted(wanted))
        if indices != self.indices:
            self.events.append(dict(action="accepted_state_model", old=self.indices, new=indices,
                                    maximum_full_residual=float(residual.max())))
            self.indices = indices

    def model_residual(self, evaluation):
        difference = evaluation.prediction[:, self.indices]-self.observed[:, self.indices]
        return self._normalize_subset(difference, self.indices)

    def jacobian(self, evaluation, update, space):
        self._choose(evaluation)
        if len(self.indices) == self.count:
            return super().jacobian(evaluation, update, space)
        blocks = []
        forwards = tuple(evaluation.forwards[i] for i in self.indices)
        with self.ledger.calls(self.physics.ordered_calls,
                              lambda f: self.physics.derivative(f, update, space),
                              forwards, "reciprocal", "working_derivative") as calls:
            for call in calls:
                block = call()
                blocks.append(block.reshape(-1, block.shape[-1]))
        return self._normalize_subset(np.stack(blocks, axis=1), self.indices)

    def _expand(self, selected, indices):
        omitted = tuple(i for i in range(self.count) if i not in indices)
        remaining = self._subset(omitted).production(selected.curve, "candidate_expansion")
        if remaining is None:
            return None
        prediction = np.empty_like(self.observed)
        forwards = [None]*self.count
        for evaluation, subset in ((selected, indices), (remaining, omitted)):
            prediction[:, subset] = evaluation.prediction
            for i, forward in zip(subset, evaluation.forwards):
                forwards[i] = forward
        residual = normalize(prediction-self.observed, self.observed, self.stage.weights, self.config.residual_floor)
        return Evaluation(selected.curve, .5*float(residual@residual),
                          float(np.linalg.norm(prediction-self.observed)/np.linalg.norm(self.observed)),
                          residual, prediction, tuple(forwards))

    def reject(self, base, candidate):
        if len(self.indices) == self.count:
            return
        omitted = [i for i in range(self.count) if i not in self.indices]
        increase = self.relative_residuals(candidate)**2-self.relative_residuals(base)**2
        added = max(omitted, key=lambda i: (increase[i], -i))
        wanted = set(self.indices) | {added}
        if len(wanted) > 9:
            wanted = set(range(self.count))
        previous = self.indices
        self.indices = tuple(sorted(wanted))
        self.events.append(dict(action="full_rejection_expand", old=previous, new=self.indices,
                                added=added, squared_residual_increase=float(increase[added])))
        self.last_trial.update(working_set_changed=True, working_new_indices=self.indices)
        raise WorkingSetChanged()

    def candidate(self, base, curve):
        self.last_trial = dict(active_frequencies=self.indices, full_acceptance=True)
        if len(self.indices) == self.count:
            return self.production(curve, "candidate")
        selected = self._subset(self.indices).production(curve, "working_candidate")
        if selected is None:
            self.last_trial["working_status"] = "physics_failed"
            return None
        residual = self._normalize_subset(selected.prediction-self.observed[:, self.indices], self.indices)
        subset_loss = .5*float(residual@residual)
        model_residual = self.model_residual(base)
        base_loss = .5*float(model_residual@model_residual)
        self.last_trial.update(working_base_loss=base_loss, working_candidate_loss=subset_loss)
        if subset_loss >= base_loss:
            self.last_trial["working_status"] = "subset_nondecreasing"
            return None
        expanded = self._expand(selected, self.indices)
        if expanded is None:
            self.last_trial["working_status"] = "expansion_physics_failed"
            return None
        self.last_trial.update(full_candidate_loss=expanded.loss,
                               maximum_full_residual=float(self.relative_residuals(expanded).max()))
        if expanded.loss >= base.loss:
            self.last_trial["working_status"] = "full_nondecreasing"
            self.reject(base, expanded)
        return expanded
