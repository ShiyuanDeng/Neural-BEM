"""Explicit geometry selection: each name gives one update object and its geometry_update function."""
from functools import partial

GEOMETRY_UPDATES = ('spline', 'spectral', 'certified_spectral', 'analytic_spectral', 'gaussian_lipschitz', 'similarity',
                    'uncentred_spectral', 'n_update', 'slider')


def make_update(name, length_unit_m, execution):
    """(update, geometry_update): the method's settings object and its trial-curve function.

    ``geometry_update(normal_update, *, prepared)`` builds and checks one trial curve.
    ``None`` selects the spline update of a bare ``fit``.
    """
    device = None if execution.device == 'auto' else execution.device
    if name == 'spline' or name is None:
        from .geometry_update_methods import spline
        update = spline.ProjectedUpdate(length_unit_m)
        return update, partial(spline.geometry_update, settings=update)
    if name == 'spectral':
        from .geometry_update_methods import spectral
        update = spectral.SpectralProjectedUpdate(length_unit_m, device=device, batched=True)
        return update, partial(spectral.geometry_update, settings=update)
    if name == 'uncentred_spectral':
        from .geometry_update_methods import uncentred_spectral
        update = uncentred_spectral.UncentredSpectralUpdate(length_unit_m, device=device)
        return update, partial(uncentred_spectral.geometry_update, settings=update)
    if name == 'n_update':
        from .geometry_update_methods import n_update
        update = n_update.NUpdate(length_unit_m)
        return update, partial(n_update.geometry_update, settings=update)
    if name == 'slider':
        from .geometry_update_methods import slider
        update = slider.SliderUpdate(length_unit_m)
        return update, partial(slider.geometry_update, settings=update)
    if name == 'certified_spectral':
        from .geometry_update_methods import certified_spectral
        order = getattr(execution, 'validity_order', 'certificate_first')
        update = certified_spectral.CertifiedSpectralUpdate(length_unit_m, device=device, batched=True, order=order)
        if update.device == 'cuda':
            update = certified_spectral.CertifiedSpectralUpdate(length_unit_m, device=update.device, batched=True,
                                                                certificate_device=True, order=order)
        return update, partial(certified_spectral.geometry_update, settings=update)
    if name == 'gaussian_lipschitz':
        from .geometry_update_methods import gaussian_lipschitz
        update = gaussian_lipschitz.GaussianDisplacement(length_unit_m, device=device)
        return update, partial(gaussian_lipschitz.geometry_update, settings=update)
    if name == 'analytic_spectral':
        # Analytic preparation; the trial curve is the sampled spectral construction.
        from .geometry_update_methods import analytic_spectral, spectral
        update = analytic_spectral.AnalyticSpectralUpdate(length_unit_m)
        return update, partial(spectral.geometry_update, settings=update)
    if name == 'similarity':
        from .geometry_update_methods import similarity
        update = similarity.SimilarityUpdate(length_unit_m)
        return update, partial(similarity.geometry_update, settings=update)
    raise ValueError(f'Unknown geometry update {name!r}; choose from {GEOMETRY_UPDATES}.')


def operation_record(operation, settings):
    row = operation.record()
    if operation.fit_geometry_update is None and 'geometry_update' in row and 'construction' in settings:
        row['geometry_update'] = settings['construction']
    return row


def describe_plan(plan, settings, *, override_operations=True):
    """Use the selected implementation's description in every fit operation."""
    plan = dict(plan, geometry=settings)
    plan['operations'] = [dict(op, geometry_update=settings['construction'])
                          if override_operations and 'geometry_update' in op and op.get('fit_geometry_update') is None
                          and 'construction' in settings else op
                          for op in plan['operations']]
    return plan
