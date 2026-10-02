"""Fourier sign and physical-unit tests, without invoking gprMax."""
import numpy as np

from experiments.time_domain.compare_bie import positive_transform, synthesize


def test_inverse_positive_transform_recovers_a_delayed_pulse():
    count, df = 4096, 2e7
    times = np.arange(count) / (count * df)
    delay, width = 3.4e-9, .3e-9
    frequencies = np.arange(count // 2 + 1) * df
    spectrum = np.sqrt(2 * np.pi) * width * np.exp(-.5 * (2 * np.pi * frequencies * width) ** 2)
    spectrum = spectrum * np.exp(2j * np.pi * frequencies * delay)
    recovered_times, signal = synthesize(spectrum, df, nfft=count)
    expected = np.exp(-.5 * ((times - delay) / width) ** 2)
    np.testing.assert_allclose(recovered_times, times)
    np.testing.assert_allclose(signal, expected, atol=2e-14)
    assert abs(times[np.argmax(signal)] - delay) < times[1]


def test_sampled_ricker_transform_and_source_time_offset():
    f0, dt = 1e9, 2e-12
    times = np.arange(3000) * dt
    delay = np.sqrt(2) / f0
    a = np.pi ** 2 * f0 ** 2
    values = (1 - 2 * a * (times - delay) ** 2) * np.exp(-a * (times - delay) ** 2)
    frequencies = np.array([.4e9, .8e9, 1.2e9, 2e9])
    expected = 2 / np.sqrt(np.pi) * frequencies ** 2 / f0 ** 3 * np.exp(-(frequencies / f0) ** 2)
    expected = expected * np.exp(2j * np.pi * frequencies * (delay + dt / 2))
    actual = positive_transform(values, dt, frequencies, time_offset=dt / 2)
    np.testing.assert_allclose(actual, expected, rtol=2e-7, atol=1e-17)
