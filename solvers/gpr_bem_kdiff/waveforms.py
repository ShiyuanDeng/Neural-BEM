"""Waveform helpers matching the gprMax Gaussian source definition."""

from __future__ import annotations

import numpy as np


def gprmax_gaussian_time_signal(
    time: np.ndarray,
    center_frequency: float,
    amplitude: float = 1.0,
) -> np.ndarray:
    """Return the gprMax Gaussian waveform sampled in time.

    gprMax defines the Gaussian waveform as

        exp(-zeta * (t - chi)^2)

    with chi = 1 / f and zeta = 2 * pi^2 * f^2.
    """

    chi = 1.0 / center_frequency
    zeta = 2.0 * np.pi**2 * center_frequency**2
    return amplitude * np.exp(-zeta * (time - chi) ** 2)


def gprmax_gaussian_spectrum(
    angular_frequency: np.ndarray,
    center_frequency: float,
    amplitude: float = 1.0,
) -> np.ndarray:
    """Return the continuous Fourier spectrum of the gprMax Gaussian waveform.

    The transform convention is

        F(w) = integral f(t) * exp(+i w t) dt
        f(t) = (1 / 2pi) integral F(w) * exp(-i w t) dw

    The closed-form spectrum follows from the Gaussian waveform used in gprMax.
    """

    zeta = 2.0 * np.pi**2 * center_frequency**2
    chi = 1.0 / center_frequency
    return (
        amplitude
        * np.sqrt(np.pi / zeta)
        * np.exp(-(angular_frequency**2) / (4.0 * zeta))
        * np.exp(1j * angular_frequency * chi)
    )
