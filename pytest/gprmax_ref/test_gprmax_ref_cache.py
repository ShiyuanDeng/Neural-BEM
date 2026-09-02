from __future__ import annotations

import math

import pytest

from gprmax_ref import cache_io
from gprmax_ref.build_scene import build_geometry, render_scene


def _base_params(frequencies_hz: list[float]) -> dict:
    return cache_io.build_params(
        target_shape="circle",
        target_size=0.05,
        standoff=0.30,
        tx_rx_offset=0.06,
        sand_epsr=6.0,
        sand_sigma=0.0,
        plastic_epsr=3.0,
        plastic_sigma=0.0,
        eps0=8.854187817e-12,
        mu0=4.0 * math.pi * 1.0e-7,
        frequencies_hz=frequencies_hz,
    )


def _result(frequency_hz: float, real: float, imag: float, *, wall_clock_seconds: float = 1.0) -> dict:
    return {
        "frequencies_hz": [float(frequency_hz)],
        "scattered_real": [float(real)],
        "scattered_imag": [float(imag)],
        "tx": [0.3, 0.0],
        "rx": [0.294, 0.06],
        "target_center": [0.0, 0.0],
        "domain": [0.4, 0.16],
        "num_iterations": 100,
        "dt": 1.0e-12,
        "wall_clock_seconds": float(wall_clock_seconds),
    }


def test_frequency_scaled_cell_size_keeps_low_frequencies_and_refines_high() -> None:
    sizes = [
        cache_io.frequency_scaled_cell_size(
            frequency,
            sand_epsr=6.0,
            sand_sigma=0.0,
            eps0=8.854187817e-12,
            mu0=4.0 * math.pi * 1.0e-7,
        )
        for frequency in (0.5e9, 1.5e9, 2.5e9, 4.0e9, 6.0e9, 8.0e9)
    ]

    assert sizes[:4] == pytest.approx([1.0e-3, 1.0e-3, 1.0e-3, 1.0e-3])
    assert sizes[4] == pytest.approx(0.00068)
    assert sizes[5] == pytest.approx(0.00051)
    assert sizes == sorted(sizes, reverse=True)


def test_build_frequency_scaled_params_from_base_is_one_frequency_and_centered() -> None:
    base = _base_params([0.5e9, 8.0e9])
    scaled = cache_io.build_frequency_scaled_params_from_base(base, 8.0e9)

    assert scaled["frequencies_hz"] == [8.0e9]
    assert scaled["center_frequency"] == pytest.approx(8.0e9)
    assert scaled["cell_size"] < base["cell_size"]
    assert scaled["target_shape"] == base["target_shape"]
    assert scaled["target_size"] == base["target_size"]


def test_harmonic_time_window_uses_transit_scaled_settle() -> None:
    frequency = 8.0e9
    kwargs = {
        "domain_x": 0.4,
        "domain_y": 0.16,
        "sand_epsr": 6.0,
        "sand_sigma": 0.0,
        "eps0": 8.854187817e-12,
        "mu0": 4.0 * math.pi * 1.0e-7,
        "ramp_periods": 4.0,
        "extraction_periods": 6.0,
        "transit_safety": 1.15,
    }
    without_settle = cache_io.harmonic_time_window(
        frequency, settle_transit_multiplier=0.0, **kwargs
    )
    with_settle = cache_io.harmonic_time_window(
        frequency, settle_transit_multiplier=1.0, **kwargs
    )

    wavelength = cache_io.sand_phase_wavelength(
        frequency,
        sand_epsr=kwargs["sand_epsr"],
        sand_sigma=kwargs["sand_sigma"],
        eps0=kwargs["eps0"],
        mu0=kwargs["mu0"],
    )
    transit_time = math.hypot(kwargs["domain_x"], kwargs["domain_y"]) * kwargs["transit_safety"] / (
        wavelength * frequency
    )
    assert with_settle - without_settle == pytest.approx(transit_time, abs=1.0e-15)
    assert with_settle == pytest.approx(2.0 * transit_time + 10.0 / frequency, abs=1.0e-15)


def test_build_harmonic_params_is_single_frequency_contsine_and_settings_change_key() -> None:
    base = _base_params([0.5e9, 8.0e9])
    harmonic = cache_io.build_harmonic_params_from_base(base, 8.0e9)
    longer_settle = cache_io.build_harmonic_params_from_base(
        base, 8.0e9, settle_transit_multiplier=2.0
    )

    assert harmonic["frequencies_hz"] == [8.0e9]
    assert harmonic["center_frequency"] == pytest.approx(8.0e9)
    assert harmonic["waveform"] == cache_io.DEFAULT_HARMONIC_WAVEFORM
    assert harmonic["time_window"] > cache_io.harmonic_extraction_seconds(8.0e9)
    assert longer_settle["time_window"] > harmonic["time_window"]
    assert cache_io.case_key(longer_settle) != cache_io.case_key(harmonic)


def test_load_frequency_sweep_prefers_complete_harmonic_entries(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cache_io, "CACHE_DIR", tmp_path)
    frequencies = [1.5e9, 8.0e9]
    base = _base_params(frequencies)

    for frequency in frequencies:
        scaled = cache_io.build_frequency_scaled_params_from_base(base, frequency)
        cache_io.save(scaled, _result(frequency, 10.0, -10.0))
        harmonic = cache_io.build_harmonic_params_from_base(base, frequency)
        cache_io.save(harmonic, _result(frequency, 20.0, -20.0))

    cached = cache_io.load_frequency_sweep(base)
    assert cached is not None
    assert cached["result"]["cache_mode"] == "per_frequency_harmonic"
    entries = list(cache_io.iter_frequency_results(cached))
    assert [entry["scattered_real"] for entry in entries] == pytest.approx([20.0, 20.0])
    assert cache_io.wall_clock_seconds(cached) == pytest.approx(2.0)


def test_load_frequency_sweep_prefers_complete_scaled_entries(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cache_io, "CACHE_DIR", tmp_path)
    frequencies = [1.5e9, 8.0e9]
    base = _base_params(frequencies)
    legacy_result = {
        "frequencies_hz": frequencies,
        "scattered_real": [100.0, 200.0],
        "scattered_imag": [0.0, 0.0],
        "tx": [0.3, 0.0],
        "rx": [0.294, 0.06],
        "target_center": [0.0, 0.0],
        "domain": [0.4, 0.16],
        "num_iterations": 100,
        "dt": 1.0e-12,
        "wall_clock_seconds": 99.0,
    }
    cache_io.save(base, legacy_result)

    for frequency in frequencies:
        params = cache_io.build_frequency_scaled_params_from_base(base, frequency)
        cache_io.save(params, _result(frequency, frequency / 1.0e9, -frequency / 1.0e9, wall_clock_seconds=2.0))

    cached = cache_io.load_frequency_sweep(base)
    assert cached is not None
    assert cached["result"]["cache_mode"] == "per_frequency_scaled"
    entries = list(cache_io.iter_frequency_results(cached))
    assert [entry["frequency_hz"] for entry in entries] == frequencies
    assert [entry["scattered_real"] for entry in entries] == pytest.approx([1.5, 8.0])
    assert [entry["scattered_imag"] for entry in entries] == pytest.approx([-1.5, -8.0])
    assert cache_io.wall_clock_seconds(cached) == pytest.approx(4.0)
    assert cache_io.cell_size_label(cached) == "0.51-1mm"


def test_load_frequency_sweep_falls_back_to_legacy_blob(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cache_io, "CACHE_DIR", tmp_path)
    frequencies = [1.5e9, 8.0e9]
    base = _base_params(frequencies)
    cache_io.save(
        base,
        {
            "frequencies_hz": frequencies,
            "scattered_real": [100.0, 200.0],
            "scattered_imag": [0.0, 0.0],
            "tx": [0.3, 0.0],
            "rx": [0.294, 0.06],
            "target_center": [0.0, 0.0],
            "domain": [0.4, 0.16],
            "num_iterations": 100,
            "dt": 1.0e-12,
            "wall_clock_seconds": 99.0,
        },
    )

    cached = cache_io.load_frequency_sweep(base)
    assert cached is not None
    assert "cache_mode" not in cached["result"]
    assert [entry["scattered_real"] for entry in cache_io.iter_frequency_results(cached)] == [100.0, 200.0]
    assert cache_io.wall_clock_seconds(cached) == pytest.approx(99.0)
    assert cache_io.cell_size_label(cached) == "1mm"


def test_two_circles_scene_renders_two_non_touching_cylinders() -> None:
    geometry = build_geometry(
        target_shape="two_circles",
        target_size=0.105,
        target_parameters={
            "circle_centers": [[-0.07, 0.0], [0.07, 0.0]],
            "circle_radii": [0.035, 0.035],
        },
        standoff=0.30,
        tx_rx_offset=0.06,
        cell_size=1.0e-3,
    )

    scene = render_scene(
        geometry,
        sand_epsr=6.0,
        sand_sigma=0.0,
        plastic_epsr=3.0,
        plastic_sigma=0.0,
        waveform="ricker",
        center_frequency=1.5e9,
        time_window=15e-9,
        title="two circles",
        include_target=True,
    )

    assert geometry.target_parameters["circle_centers"] == [[-0.07, 0.0], [0.07, 0.0]]
    assert scene.count("#cylinder:") == 2
    assert "0.035000 plastic" in scene
