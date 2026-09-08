"""Bounds certify spectral changes without repeating any forward solve."""

import csv
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audit_star_observability_spectra import audit_bundle, main, rank_intervals


def test_rank_bounds_include_uncertainty_in_the_threshold_singular_value():
    intervals, ranks = rank_intervals([10.0, .2005, .02], .1, 3, 3, thresholds=(.01,))
    rank = ranks[0]
    assert intervals[1]["coarse_lower_bound"] > .01 * 10
    # This is still uncertain because the leading singular value can be 10.1.
    assert rank["certainly_above_indices"] == [0]
    assert rank["unresolved_indices"] == [1, 2]
    assert rank["guaranteed_minimum_rank"] == 1
    assert rank["guaranteed_maximum_rank"] == 3


def test_dimension_forced_zeros_cannot_become_uncertain():
    intervals, ranks = rank_intervals([1.0] * 16 + [0.0] * 5, .9, 16, 21)
    for rank in ranks:
        assert rank["guaranteed_maximum_rank"] == 16
        assert rank["certainly_at_or_below_indices"] == list(range(16, 21))
    assert all(v["coarse_upper_bound"] == 0 for v in intervals[16:])


def test_bounds_contain_actual_coarse_matrix_ranks():
    rng = np.random.default_rng(203)
    fine = rng.normal(size=(8, 12)) + 1j * rng.normal(size=(8, 12))
    change = .2 * (rng.normal(size=fine.shape) + 1j * rng.normal(size=fine.shape))
    fine_s = np.linalg.svd(np.vstack([fine.real, fine.imag]), compute_uv=False)
    coarse_s = np.linalg.svd(np.vstack([(fine + change).real, (fine + change).imag]), compute_uv=False)
    delta = np.linalg.norm(change)
    intervals, ranks = rank_intervals(fine_s, delta, 16, 12, thresholds=(.1, .3, .5))
    for value, interval in zip(coarse_s, intervals):
        assert interval["coarse_lower_bound"] <= value <= interval["coarse_upper_bound"]
    for rank in ranks:
        actual = np.sum(coarse_s > rank["relative_threshold"] * coarse_s[0])
        assert rank["guaranteed_minimum_rank"] <= actual <= rank["guaranteed_maximum_rank"]


def _write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _bundle(path):
    path.mkdir()
    changes, sensitivities = [], []
    for frequency in (.5, 1.5):
        for direction, norm, error in (("center_x", 3., .1), ("center_y", 4., .2)):
            metadata = dict(location="target", acquisition="paired-8", frequency_ghz=frequency, direction=direction)
            changes.append(dict(**metadata, relative_change=error))
            sensitivities.append(dict(**metadata, sensitivity_norm_1mm=norm, relative_sensitivity_1mm=norm / 5))
    _write_csv(path / "resolution_validation.csv", changes)
    _write_csv(path / "physical_jacobian.csv", sensitivities)
    _write_csv(path / "modal_jacobian.csv", [dict(sensitivities[0], direction="mode_0")])
    spectra = [dict(
        location="target", acquisition="paired-8", frequencies_ghz="0.5+1.5",
        family="physical", weighting=weighting,
        singular_values=[4.0, 2.0], real_rows=32, columns=2,
    ) for weighting in ("absolute", "target_relative")]
    metrics = dict(configuration=dict(num_nodes=256, refined_nodes=512), spectra=spectra)
    (path / "metrics.json").write_text(json.dumps(metrics))


def test_bundle_bound_uses_frequency_stacking_and_fixed_target_scaling(tmp_path):
    folder = tmp_path / "input"
    _bundle(folder)
    result, rows = audit_bundle(folder)
    absolute, relative = result["spectra"]
    expected = np.sqrt(2 * ((.1 * 3) ** 2 + (.2 * 4) ** 2))
    assert absolute["coarse_fine_frobenius_bound"] == pytest.approx(expected)
    assert relative["coarse_fine_frobenius_bound"] == pytest.approx(expected / 5)
    assert len(rows) == 6
    assert result["fine_nodes"] == 512


def test_cli_preserves_original_bundle_and_refuses_to_overwrite_audit(tmp_path):
    folder = tmp_path / "input"
    _bundle(folder)
    before = {path.name: path.read_bytes() for path in folder.iterdir()}
    assert main(["--input-dir", str(folder)]) == 0
    for name, content in before.items():
        assert (folder / name).read_bytes() == content
    assert (folder / "spectrum_refinement.csv").exists()
    assert (folder / "spectrum_refinement.json").exists()
    with pytest.raises(FileExistsError, match="Refusing"):
        main(["--input-dir", str(folder)])


def test_incomplete_or_inconsistent_inputs_do_not_silently_certify(tmp_path):
    folder = tmp_path / "input"
    _bundle(folder)
    changes = list(csv.DictReader((folder / "resolution_validation.csv").open()))
    _write_csv(folder / "resolution_validation.csv", changes[:-1])
    with pytest.raises(ValueError, match="Missing refinement"):
        audit_bundle(folder)
    with pytest.raises(ValueError, match="Dimension-forced"):
        rank_intervals([1, 1], .1, 1, 2)
    with pytest.raises(ValueError, match="finite"):
        rank_intervals([1, float("nan")], .1, 2, 2)
