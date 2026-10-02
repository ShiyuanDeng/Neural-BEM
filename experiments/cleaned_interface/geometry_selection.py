"""Explicit geometry selection without process-global experiment substitution."""
GEOMETRY_UPDATES = ('spline', 'spectral', 'certified_spectral', 'analytic_spectral')


def make_update(name, length_unit_m, execution, *, default=None):
    if name is None and default is not None:
        return default(length_unit_m)  # preserve existing experiment wrappers
    if name == 'spline' or name is None:
        from .geometry import ProjectedUpdate
        return ProjectedUpdate(length_unit_m)
    if name == 'spectral':
        from .nu003 import SpectralProjectedUpdate
        return SpectralProjectedUpdate(length_unit_m)
    if name == 'certified_spectral':
        from .nu006 import BatchedCertifiedUpdate
        return BatchedCertifiedUpdate(length_unit_m, device=None if execution.device == 'auto' else execution.device)
    if name == 'analytic_spectral':
        from .analytic_projection import AnalyticSpectralUpdate
        return AnalyticSpectralUpdate(length_unit_m)
    raise ValueError(f'Unknown geometry update {name!r}; choose from {GEOMETRY_UPDATES}.')


def operation_record(operation, settings):
    row = operation.record()
    if 'geometry_update' in row and 'construction' in settings:
        row['geometry_update'] = settings['construction']
    return row


def describe_plan(plan, settings, *, override_operations=True):
    """Use the selected implementation's description in every fit operation."""
    plan = dict(plan, geometry=settings)
    plan['operations'] = [dict(op, geometry_update=settings['construction'])
                          if override_operations and 'geometry_update' in op and 'construction' in settings else op
                          for op in plan['operations']]
    return plan
