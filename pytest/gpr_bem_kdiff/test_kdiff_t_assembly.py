"""Contract tests for the shared kdiff solve and pluggable T assembly."""

from __future__ import annotations

import numpy as np
import pytest
import torch

import gpr_bem_kdiff
from gpr_bem_kdiff.t_assembly import TAssemblyReport, TAssemblyResult
from gpr_bem_qbx import (
    ComponentParameterizedFourierSources,
    FourierComponent,
    FullRowQBX,
    IDWProlongation,
    ParameterizedFourierSources,
    RawSDFBandSources,
    SameNodeSources,
)
from nystrom_ref import build_curve, circle_parameterization
from nystrom_ref import nystrom_tmz


BOUNDS = ((-0.1, -0.1), (0.1, 0.1))
CENTER = (0.0, 0.0)
RADIUS = 0.05
K_EXT = 12.0 + 0.1j
K_INT = 20.0 + 0.2j


def _perfect_boundary(num_samples: int = 16):
    return gpr_bem_kdiff.perfect_circle_boundary_samples(
        CENTER,
        RADIUS,
        num_samples=num_samples,
        bounds=BOUNDS,
        dtype=torch.float64,
    )


def _assert_regular_blocks_identical(left, right) -> None:
    for name in (
        "single_layer_matrix",
        "double_layer_matrix",
        "adjoint_double_layer_matrix",
    ):
        assert np.array_equal(getattr(left, name), getattr(right, name)), name


def test_explicit_legacy_t_is_exactly_the_default() -> None:
    boundary = _perfect_boundary()
    implicit = gpr_bem_kdiff.build_kdiff_operator_blocks(boundary, K_EXT, K_INT)
    explicit = gpr_bem_kdiff.build_kdiff_operator_blocks(
        boundary,
        K_EXT,
        K_INT,
        t_assembly=gpr_bem_kdiff.LegacyLocalT(),
    )
    _assert_regular_blocks_identical(implicit, explicit)
    assert np.array_equal(implicit.hypersingular_matrix, explicit.hypersingular_matrix)
    assert explicit.t_assembly_report.method == "legacy_local"


def test_parameterized_full_row_qbx_changes_only_t() -> None:
    boundary = _perfect_boundary()
    baseline = gpr_bem_kdiff.build_kdiff_operator_blocks(boundary, K_EXT, K_INT)
    qbx = gpr_bem_kdiff.build_kdiff_operator_blocks(
        boundary,
        K_EXT,
        K_INT,
        t_assembly=FullRowQBX(
            source=ParameterizedFourierSources(
                parameterization=circle_parameterization(CENTER, RADIUS),
                oversampling_factor=2,
            ),
            expansion_order=4,
            source_chunk_size=16,
        ),
    )
    _assert_regular_blocks_identical(baseline, qbx)
    assert not np.array_equal(baseline.hypersingular_matrix, qbx.hypersingular_matrix)
    assert np.all(np.isfinite(qbx.hypersingular_matrix))
    report = qbx.t_assembly_report
    assert report.method == "full_row_qbx"
    assert report.parameters["source_mode"] == "parameterized_fourier"
    assert report.diagnostics["num_sources"] == 2 * boundary.num_samples
    assert report.diagnostics["constant_prolongation_error"] < 1.0e-12
    assert report.diagnostics["invalid_clearance_count"] == 0


def test_same_node_full_row_qbx_is_the_plain_one_x_variant() -> None:
    boundary = _perfect_boundary()
    strategy = FullRowQBX(source=SameNodeSources(), expansion_order=4, source_chunk_size=16)
    baseline = gpr_bem_kdiff.build_kdiff_operator_blocks(boundary, K_EXT, K_INT)
    qbx = gpr_bem_kdiff.build_kdiff_operator_blocks(
        boundary, K_EXT, K_INT, t_assembly=strategy
    )
    second_frequency = gpr_bem_kdiff.build_kdiff_operator_blocks(
        boundary, 1.1 * K_EXT, 1.1 * K_INT, t_assembly=strategy
    )
    _assert_regular_blocks_identical(baseline, qbx)
    assert np.all(np.isfinite(qbx.hypersingular_matrix))
    assert qbx.t_assembly_report.parameters["source_mode"] == "same_node"
    assert qbx.t_assembly_report.diagnostics["actual_source_ratio"] == 1.0
    assert qbx.t_assembly_report.diagnostics["constant_prolongation_error"] == 0.0
    assert second_frequency.t_assembly_report.diagnostics["source_cache_hit"] is True


def test_component_fourier_prolongation_keeps_components_separate() -> None:
    nodes_per_component = 8
    target_t = 2.0 * np.pi * np.arange(nodes_per_component) / nodes_per_component
    centers = ((-0.06, 0.0), (0.06, 0.0))
    radius = 0.025
    point_parts = []
    normal_parts = []
    weight_parts = []
    parameterizations = []
    for center in centers:
        parameterization = circle_parameterization(center, radius)
        points, tangents = parameterization(target_t)
        speeds = np.linalg.norm(tangents, axis=1)
        point_parts.append(points)
        normal_parts.append(np.stack((tangents[:, 1], -tangents[:, 0]), axis=1) / speeds[:, None])
        weight_parts.append(speeds * (2.0 * np.pi / nodes_per_component))
        parameterizations.append(parameterization)
    points = np.concatenate(point_parts)
    normals = np.concatenate(normal_parts)
    weights = np.concatenate(weight_parts)
    boundary = gpr_bem_kdiff.ImplicitBoundarySamples2D(
        points=torch.as_tensor(points, dtype=torch.float64),
        normals=torch.as_tensor(normals, dtype=torch.float64),
        quadrature_weights=torch.as_tensor(weights, dtype=torch.float64),
        strict_quadrature_weights=torch.as_tensor(weights, dtype=torch.float64),
        merge_distance=0.01,
        source_num_samples=2 * nodes_per_component,
        bounds=((-0.1, -0.05), (0.1, 0.05)),
        level=0.0,
    )
    first = np.arange(nodes_per_component)
    second = np.arange(nodes_per_component, 2 * nodes_per_component)
    source = ComponentParameterizedFourierSources(
        components=(
            FourierComponent(parameterizations[0], first, target_t),
            FourierComponent(parameterizations[1], second, target_t),
        ),
        oversampling_factor=2,
    )
    qbx = gpr_bem_kdiff.build_kdiff_operator_blocks(
        boundary,
        K_EXT,
        K_INT,
        t_assembly=FullRowQBX(source=source, expansion_order=4, source_chunk_size=16),
    )
    report = qbx.t_assembly_report
    assert report.parameters["source_mode"] == "component_parameterized_fourier"
    assert report.diagnostics["num_components"] == 2
    assert report.diagnostics["component_target_counts"] == [8, 8]
    assert report.diagnostics["component_source_counts"] == [16, 16]
    assert report.diagnostics["target_parameterization_mismatch"] < 1.0e-14
    assert report.diagnostics["constant_prolongation_error"] < 1.0e-12


def test_eight_x_parameterized_qbx_matches_nystrom_t_action() -> None:
    num_samples = 32
    parameterization = circle_parameterization(CENTER, RADIUS)
    curve = build_curve(parameterization, num_samples, "circle")
    boundary = _perfect_boundary(num_samples)
    qbx = gpr_bem_kdiff.build_kdiff_operator_blocks(
        boundary,
        K_EXT,
        K_INT,
        t_assembly=FullRowQBX(
            source=ParameterizedFourierSources(parameterization, oversampling_factor=8),
            expansion_order=16,
            source_chunk_size=128,
        ),
    )
    reference = nystrom_tmz._operator_matrices(curve, K_EXT, K_INT, epsilon=1.0e-3)["hyper"]
    density = np.cos(curve.t)
    expected = reference @ density
    actual = qbx.hypersingular_matrix @ density
    relative_error = np.linalg.norm(actual - expected) / np.linalg.norm(expected)
    assert relative_error < 1.0e-6


def test_raw_sdf_band_full_row_qbx_changes_only_t() -> None:
    def sdf(points: torch.Tensor) -> torch.Tensor:
        return gpr_bem_kdiff.circle_signed_distance(points, center=CENTER, radius=RADIUS)

    band = gpr_bem_kdiff.build_implicit_boundary_band(
        sdf,
        BOUNDS,
        grid_shape=(33, 33),
        dtype=torch.float64,
    )
    with pytest.warns(RuntimeWarning, match="reduced merge_distance"):
        boundary = gpr_bem_kdiff.compress_implicit_boundary_band(band)
    baseline = gpr_bem_kdiff.build_kdiff_operator_blocks(boundary, K_EXT, K_INT, sdf_fn=sdf)
    raw_sources = RawSDFBandSources(
        grid_refinement_factor=1,
        base_grid_shape=(33, 33),
        prolongation=IDWProlongation(neighbours=4, power=2.0),
    )
    with pytest.raises(ValueError, match="QBX expansion geometry is inadmissible"):
        gpr_bem_kdiff.build_kdiff_operator_blocks(
            boundary,
            K_EXT,
            K_INT,
            sdf_fn=sdf,
            t_assembly=FullRowQBX(
                source=raw_sources,
                expansion_order=4,
                radius_spacing_factor=0.5,
                source_chunk_size=32,
            ),
        )
    qbx = gpr_bem_kdiff.build_kdiff_operator_blocks(
        boundary,
        K_EXT,
        K_INT,
        sdf_fn=sdf,
        t_assembly=FullRowQBX(
            source=raw_sources,
            expansion_order=4,
            radius_spacing_factor=0.5,
            source_chunk_size=32,
            allow_invalid_clearance=True,
        ),
    )
    _assert_regular_blocks_identical(baseline, qbx)
    assert np.all(np.isfinite(qbx.hypersingular_matrix))
    report = qbx.t_assembly_report
    assert report.parameters["source_mode"] == "raw_sdf_band_idw"
    assert report.parameters["allow_invalid_clearance"] is True
    assert report.diagnostics["num_sources"] > boundary.num_samples
    assert report.diagnostics["invalid_clearance_count"] > 0
    assert report.diagnostics["constant_prolongation_error"] < 1.0e-12


class _ZeroT:
    name = "zero_test_t"

    def assemble(self, context):
        return TAssemblyResult(
            matrix=np.zeros((context.points.shape[0], context.points.shape[0]), dtype=complex),
            report=TAssemblyReport(method=self.name),
        )


def test_system_composition_changes_only_the_lower_left_quadrant() -> None:
    boundary = _perfect_boundary()
    exterior = gpr_bem_kdiff.Material(epsr=6.0, sigma=0.0)
    interior = gpr_bem_kdiff.Material(epsr=3.0, sigma=0.0)
    common = dict(
        exterior=exterior,
        interior=interior,
        eps0=8.854187817e-12,
        mu0=4.0 * np.pi * 1.0e-7,
    )
    baseline = gpr_bem_kdiff.build_ibim_tmz_frequency_system(boundary, 2.0 * np.pi * 0.5e9, **common)
    modified = gpr_bem_kdiff.build_ibim_tmz_frequency_system(
        boundary,
        2.0 * np.pi * 0.5e9,
        t_assembly=_ZeroT(),
        **common,
    )
    num_nodes = boundary.num_samples
    baseline_matrix = baseline.system_matrix[0]
    modified_matrix = modified.system_matrix[0]
    assert np.array_equal(baseline_matrix[:num_nodes], modified_matrix[:num_nodes])
    assert np.array_equal(baseline_matrix[num_nodes:, num_nodes:], modified_matrix[num_nodes:, num_nodes:])
    assert not np.array_equal(baseline_matrix[num_nodes:, :num_nodes], modified_matrix[num_nodes:, :num_nodes])
    assert np.count_nonzero(modified_matrix[num_nodes:, :num_nodes]) == 0
    assert modified.t_assembly_report.method == "zero_test_t"
