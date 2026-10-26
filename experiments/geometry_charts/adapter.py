"""Experimental TA-001 finite chart map with its exact local B6 tangent basis."""
from functools import partial
from time import perf_counter

import numpy as np

from bem_inverse import checks
from bem_inverse.continuation.geometry import FourierCurve, cleanup, grid_size, resize, speed_ratio
from bem_inverse.errors import UpdateRefused
from bem_inverse.geometry_update_methods.spectral import SpectralProjectedUpdate
from bem_inverse.io import curve_record
from .replay import TangentChart


class TangentAngleUpdate(SpectralProjectedUpdate):
    name='ta001_positive_speed_tangent_angle'

    def __init__(self,length_unit_m):
        if length_unit_m!=.05:
            raise ValueError('TA-001 chart diagnostics are qualified only for TG-002 length_unit_m=.05')
        super().__init__(length_unit_m,device='cpu',batched=True)
        self.counts.update(chart_constructions=0,chart_closure_refusals=0)

    def settings(self):
        settings=super().settings()
        settings.update(name=self.name,
            construction='positive log-speed/tangent-angle retraction of complete spectral B6 velocity; closure, integration, crop to K',
            gauge='retain B6 tangential gauge and original parameter at first order',
            derivative='exact first derivative is the precomputed complete spectral B6 coefficient basis',
            resampler='eq.9 quadrature only builds B6; finite chart uses tangent integration and Fourier crop',
            closure='two angle corrections; failure backtracks as UpdateRefused',
            positivity='before crop only; actual stored curve checked after crop',chart_grid_minimum=4096)
        return settings


def geometry_update(a,*,prepared,settings):
    started=perf_counter()
    settings.counts['trial_constructions']+=1
    a=settings._checked(prepared,a)
    settings.last_trial={}
    try:
        if not np.any(a):
            return prepared.curve,dict(maximum_normal_m=0.,rms_normal_m=0.,
                speed_ratio=speed_ratio(prepared.curve),finite_path=settings.name,
                refits=0,closure_residual_package=0.)
        velocity=FourierCurve(prepared.derivatives@a)
        settings.counts['chart_constructions']+=1
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            chart=TangentChart(prepared.curve,velocity)
            candidate,detail=chart.trial(1.)
            if not np.isfinite(detail['minimum_chart_speed_package']) or detail['minimum_chart_speed_package']<=0:
                raise ValueError('chart speed is non-finite or underflowed to zero')
        settings.last_trial=dict(closure_residual_package=detail['closure_residual_package'],
                                 minimum_chart_speed_package=detail['minimum_chart_speed_package'])
        checks.check_area(candidate.coefficients)
        nodes=candidate.nodes(grid_size(candidate.band))
        checks.check_speed(nodes.speeds)
        checks.check_intersection(nodes.points)
        return candidate,dict(**settings.measure(prepared,a),speed_ratio=speed_ratio(candidate),
                              finite_path=settings.name,refits=0,**detail)
    except UpdateRefused:
        settings.counts['refused_trials']+=1
        raise
    except (ValueError,FloatingPointError,np.linalg.LinAlgError) as exc:
        settings.counts['refused_trials']+=1
        settings.counts['chart_closure_refusals']+=1
        raise UpdateRefused('chart_closure',str(exc)) from exc
    finally:
        settings.counts['trial_seconds']+=perf_counter()-started


class GeometryAdapter:
    resize=staticmethod(resize)
    cleanup=staticmethod(cleanup)
    record=staticmethod(curve_record)

    def update(self,length_unit_m):
        settings=TangentAngleUpdate(length_unit_m)
        return settings,partial(geometry_update,settings=settings)
