"""Fitting inputs only. No target, scene ID, result path or historical winner."""
from dataclasses import dataclass
import numpy as np

from experiments.shape_continuation.forward import same_acquisition
from experiments.shape_continuation.geometry import FourierCurve


@dataclass(frozen=True)
class Observation:
    wavenumber: complex
    acquisition: object
    scattered: np.ndarray
    frequency_hz: float
    sigma_real_imag: float = 0.0

    def __post_init__(self):
        k = complex(self.wavenumber)
        if not np.isfinite(k) or k.real <= 0 or k.imag < 0:
            raise ValueError('Wavenumbers require finite positive real and nonnegative imaginary parts.')
        data = np.array(self.scattered, complex, copy=True)
        if data.shape != self.acquisition.data_shape or not np.isfinite(data).all():
            raise ValueError('Finite data matching the acquisition are required.')
        if not np.isfinite(self.frequency_hz) or self.frequency_hz <= 0:
            raise ValueError('Positive frequency_hz required.')
        if not np.isfinite(self.sigma_real_imag) or self.sigma_real_imag < 0:
            raise ValueError('Noise standard deviation must be finite and nonnegative.')
        if np.linalg.norm(data) == 0:
            raise ValueError('Relative objectives require a nonzero observation.')
        data.setflags(write=False)
        object.__setattr__(self, 'scattered', data)
        object.__setattr__(self, 'wavenumber', k.real if k.imag == 0 else k)


@dataclass(frozen=True)
class Problem:
    initial: FourierCurve
    real: tuple
    damped: tuple
    contrast: float
    length_unit_m: float = .05
    origin_m: complex = .5 + .5j
    bounds_m: tuple = ((.2, .2), (.8, .8))
    material: str = 'equal_density_homogeneous'

    def __post_init__(self):
        if not np.isfinite(self.contrast) or self.contrast <= 0:
            raise ValueError('Positive finite contrast required.')
        if not np.isfinite(self.length_unit_m) or self.length_unit_m <= 0:
            raise ValueError('Positive finite length unit required.')
        if not np.isfinite(self.origin_m):
            raise ValueError('Finite origin required.')
        if not self.real or len(self.real) != len(self.damped):
            raise ValueError('CI-001 requires matched real AND damped observations. Generate missing '
                             'synthetic data explicitly with the benchmark augment command.')
        for catalog in (self.real, self.damped):
            if any(b.frequency_hz <= a.frequency_hz for a, b in zip(catalog, catalog[1:])):
                raise ValueError('Observation catalogs must be strictly increasing.')
            if not all(same_acquisition(catalog[0].acquisition, o.acquisition) for o in catalog):
                raise ValueError('The cumulative policy requires one acquisition across frequencies.')
            sigma = [o.sigma_real_imag > 0 for o in catalog]
            if any(sigma) and not all(sigma):
                raise ValueError('Noise metadata must cover every frequency, or all be noiseless.')
        for real, damped in zip(self.real, self.damped):
            if (complex(real.wavenumber).imag != 0 or
                    not np.isclose(damped.wavenumber, real.wavenumber * (1 + .25j), rtol=1e-13, atol=0) or
                    real.frequency_hz != damped.frequency_hz or
                    not same_acquisition(real.acquisition, damped.acquisition)):
                raise ValueError('Damped catalog must match the real acquisition at k*(1+0.25i).')
        bounds = np.asarray(self.bounds_m)
        if bounds.shape != (2, 2) or not np.isfinite(bounds).all() or np.any(bounds[1] <= bounds[0]):
            raise ValueError('Expected finite ordered physical bounds.')

    @property
    def domain_box(self):
        origin = np.array([self.origin_m.real, self.origin_m.imag])
        return tuple(tuple((np.asarray(p) - origin) / self.length_unit_m) for p in self.bounds_m)
