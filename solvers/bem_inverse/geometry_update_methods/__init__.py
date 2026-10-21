"""Selectable geometry methods; numerical construction lives in each method file."""
import numpy as np


def bind_geometry_update(update):
    """Use the new entry point, retaining external adapters with the old API."""
    method = getattr(update, 'geometry_update', None)
    if method is not None:
        return method

    def geometry_update(normal_update, *, prepared):
        return update.trial(prepared, normal_update)

    return geometry_update


def control_step(proposed, space, update, config):
    """Apply the configured step control before backtracking."""
    if config.step_control == 'coefficient':
        bound = config.bounds(space.orders)
        return np.clip(proposed, -bound, bound)
    if config.step_control == 'physical':
        size = update.measure(space, proposed)['maximum_normal_m']
        return proposed * min(1., config.physical_step_bound_m / size) if size > 0 else proposed
    raise ValueError(f'Unknown step control {config.step_control!r}.')
