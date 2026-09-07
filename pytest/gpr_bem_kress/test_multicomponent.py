"""Opt-in multi-component Kress assembly and forward-solve tests."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from scipy.special import hankel1

from gpr_bem_kress import Material, build_muller_system
import gpr_bem_kress.multicomponent as multicomponent_module
from gpr_bem_kress.multicomponent import (
    ExteriorCrossBlocks,
    MultiComponentAssemblyConfig,
    MultiComponentCurveGeometryError,
    MultiComponentFieldPointError,
    MultiComponentKressGeometryError,
    MultiComponentKressSolveConfig,
    MultiComponentTopologyError,
    adapt_multicomponent_boundary,
    build_exterior_cross_blocks,
    build_multicomponent_exterior_receiver_operator,
    build_multicomponent_muller_blocks,
    build_multicomponent_muller_system,
    solve_multicomponent_kress_tmz_total_field_batch,
)
from ordered_boundary import OrderedBoundary2D, circle


K_EXTERIOR = 13.0 - 0.1j
K_INTERIOR = 21.0 - 0.2j
EPS0 = 8.8541878128e-12
MU0 = 1.25663706212e-6


def _two_circle_boundary(*, reverse: bool = False) -> OrderedBoundary2D:
    left = circle(
        (-0.12, 0.01),
        0.04,
        component_id="left",
    ).discretize(24, require_even=True)
    right = circle(
        (0.11, -0.015),
        0.055,
        component_id="right",
    ).discretize(32, require_even=True)
    return OrderedBoundary2D((right, left) if reverse else (left, right))


def _direct_exterior_blocks(target, source, wave: complex):
    displacement = target.points[:, None, :] - source.points[None, :, :]
    distance = np.linalg.norm(displacement, axis=-1)
    target_projection = np.einsum("mnd,md->mn", displacement, target.normals)
    source_projection = np.einsum("mnd,nd->mn", displacement, source.normals)
    normal_dot = target.normals @ source.normals.T
    green = 0.25j * hankel1(0, wave * distance)
    radial_first = -0.25j * wave * hankel1(1, wave * distance) / distance
    radial_anisotropy = 0.25j * wave**2 * hankel1(2, wave * distance)
    weights = source.arc_length_weights[None, :]
    return {
        "delta_v": green * weights,
        "delta_k": -radial_first * source_projection * weights,
        "delta_kp": radial_first * target_projection * weights,
        "delta_t": (
            -radial_first * normal_dot
            - radial_anisotropy
            * target_projection
            * source_projection
            / distance**2
        )
        * weights,
    }


def test_self_blocks_are_exact_existing_assemblies_on_unequal_local_grids() -> None:
    boundary = _two_circle_boundary()
    blocks = build_multicomponent_muller_blocks(
        boundary,
        K_EXTERIOR,
        K_INTERIOR,
    )

    assert blocks.geometry is boundary
    assert blocks.diagnostics["component_node_counts"] == (24, 32)
    assert blocks.diagnostics["operator_formula"] == (
        "X_exterior_global - blockdiag(X_interior_components)"
    )
    assert dict(blocks.diagnostics["component_orientations"]) == {
        "left": "counterclockwise",
        "right": "counterclockwise",
    }
    assert blocks.diagnostics["normal_convention"] == "outward_from_each_inclusion"
    assert blocks.diagnostics["topology"] == "disjoint_non_nested_components"
    assert len(blocks.self_blocks) == 2
    for component_slice, self_block in zip(
        boundary.component_slices,
        blocks.self_blocks,
    ):
        for name in ("delta_v", "delta_k", "delta_kp", "delta_t"):
            np.testing.assert_array_equal(
                getattr(blocks, name)[component_slice, component_slice],
                getattr(self_block, name),
            )
    interaction_kinds = tuple(
        record["kind"] for record in blocks.diagnostics["interactions"]
    )
    assert interaction_kinds.count("self_kress_exterior_minus_interior") == 2
    assert interaction_kinds.count("cross_exterior_trapezoid") == 2
    global_block_bytes = sum(
        getattr(blocks, name).nbytes
        for name in ("delta_v", "delta_k", "delta_kp", "delta_t")
    )
    retained_self_arrays = {}
    for self_block in blocks.self_blocks:
        arrays = (
            self_block.delta_v,
            self_block.delta_k,
            self_block.delta_kp,
            self_block.delta_t,
            *self_block.diagonal_log_coefficients.values(),
            *self_block.diagonal_smooth_remainders.values(),
        )
        retained_self_arrays.update((id(array), array) for array in arrays)
    self_block_bytes = sum(array.nbytes for array in retained_self_arrays.values())
    delta_only_bytes = sum(
        getattr(self_block, name).nbytes
        for self_block in blocks.self_blocks
        for name in ("delta_v", "delta_k", "delta_kp", "delta_t")
    )
    assert self_block_bytes > delta_only_bytes
    assert blocks.diagnostics["retained_global_block_bytes"] == global_block_bytes
    assert blocks.diagnostics["retained_self_block_bytes"] == self_block_bytes
    assert blocks.diagnostics["retained_block_bytes"] == (
        global_block_bytes + self_block_bytes
    )


def test_cross_blocks_are_weighted_exterior_only_kernels() -> None:
    boundary = _two_circle_boundary()
    blocks = build_multicomponent_muller_blocks(
        boundary,
        K_EXTERIOR,
        K_INTERIOR,
    )
    changed_interior = build_multicomponent_muller_blocks(
        boundary,
        K_EXTERIOR,
        37.0 - 0.4j,
    )

    for target_index, source_index in ((0, 1), (1, 0)):
        target = boundary.components[target_index]
        source = boundary.components[source_index]
        target_slice = boundary.component_slices[target_index]
        source_slice = boundary.component_slices[source_index]
        expected = _direct_exterior_blocks(target, source, K_EXTERIOR)
        for name, values in expected.items():
            observed = getattr(blocks, name)[target_slice, source_slice]
            np.testing.assert_allclose(observed, values, rtol=2.0e-14, atol=2.0e-14)
            np.testing.assert_array_equal(
                observed,
                getattr(changed_interior, name)[target_slice, source_slice],
            )
            assert np.linalg.norm(observed) > 0.0


def test_cross_blocks_obey_weighted_reciprocity_relations() -> None:
    boundary = _two_circle_boundary()
    blocks = build_multicomponent_muller_blocks(
        boundary,
        K_EXTERIOR,
        K_INTERIOR,
    )
    first, second = boundary.component_slices
    first_weights = boundary.components[0].arc_length_weights
    second_weights = boundary.components[1].arc_length_weights

    # Stored Nyström matrices include source ds in their columns.  Removing
    # the target weights after transposition and restoring the source weights
    # makes the continuous reciprocal kernel identities explicit.
    def weighted_transpose(values: np.ndarray) -> np.ndarray:
        return (
            values.T
            * second_weights[None, :]
            / first_weights[:, None]
        )

    np.testing.assert_allclose(
        blocks.delta_v[first, second],
        weighted_transpose(blocks.delta_v[second, first]),
        rtol=2.0e-14,
        atol=2.0e-14,
    )
    np.testing.assert_allclose(
        blocks.delta_k[first, second],
        weighted_transpose(blocks.delta_kp[second, first]),
        rtol=2.0e-14,
        atol=2.0e-14,
    )
    np.testing.assert_allclose(
        blocks.delta_kp[first, second],
        weighted_transpose(blocks.delta_k[second, first]),
        rtol=2.0e-14,
        atol=2.0e-14,
    )
    np.testing.assert_allclose(
        blocks.delta_t[first, second],
        weighted_transpose(blocks.delta_t[second, first]),
        rtol=2.0e-14,
        atol=2.0e-14,
    )


def test_one_component_ordered_boundary_reproduces_existing_system_exactly() -> None:
    curve = circle(
        (0.03, -0.02),
        0.06,
        component_id="compatibility-circle",
    ).discretize(32, require_even=True)
    expected = build_muller_system(curve, K_EXTERIOR, K_INTERIOR)
    observed = build_multicomponent_muller_system(
        OrderedBoundary2D((curve,)),
        K_EXTERIOR,
        K_INTERIOR,
    )

    np.testing.assert_array_equal(observed.system_matrix, expected.system_matrix)
    for name in ("delta_v", "delta_k", "delta_kp", "delta_t"):
        np.testing.assert_array_equal(
            getattr(observed.difference_blocks, name),
            getattr(expected.difference_blocks, name),
        )


def test_three_components_create_every_ordered_interaction_block() -> None:
    boundary = OrderedBoundary2D(
        tuple(
            circle(center, 0.025, component_id=component_id).discretize(
                16,
                require_even=True,
            )
            for center, component_id in (
                ((-0.15, 0.0), "left"),
                ((0.15, 0.0), "right"),
                ((0.0, 0.18), "top"),
            )
        )
    )
    blocks = build_multicomponent_muller_blocks(
        boundary,
        K_EXTERIOR,
        K_INTERIOR,
    )

    assert blocks.delta_v.shape == (48, 48)
    assert len(blocks.self_blocks) == 3
    assert len(blocks.geometry_adapter.component_pair_reports) == 3
    interactions = blocks.diagnostics["interactions"]
    assert len(interactions) == 9
    assert sum(item["kind"].startswith("self_") for item in interactions) == 3
    assert sum(item["kind"].startswith("cross_") for item in interactions) == 6


def test_component_permutation_is_a_matrix_similarity_and_field_invariant() -> None:
    boundary = _two_circle_boundary()
    reversed_boundary = _two_circle_boundary(reverse=True)
    system = build_multicomponent_muller_system(
        boundary,
        K_EXTERIOR,
        K_INTERIOR,
    )
    reversed_system = build_multicomponent_muller_system(
        reversed_boundary,
        K_EXTERIOR,
        K_INTERIOR,
    )
    first_count = boundary.components[0].num_nodes
    node_permutation = np.concatenate(
        (
            np.arange(first_count, boundary.num_nodes),
            np.arange(first_count),
        )
    )
    state_permutation = np.concatenate(
        (node_permutation, boundary.num_nodes + node_permutation)
    )
    np.testing.assert_allclose(
        reversed_system.system_matrix,
        system.system_matrix[np.ix_(state_permutation, state_permutation)],
        rtol=2.0e-14,
        atol=2.0e-14,
    )

    sources = np.asarray(((-0.31, 0.12), (0.31, 0.13)))
    receivers = np.asarray(((-0.30, -0.14), (0.30, -0.13), (0.0, 0.24)))
    exterior = Material(epsr=3.1)
    interior = Material(epsr=2.2)
    forward = solve_multicomponent_kress_tmz_total_field_batch(
        boundary,
        sources,
        receivers,
        2.0 * np.pi * 1.2e9,
        exterior=exterior,
        interior=interior,
        eps0=EPS0,
        mu0=MU0,
    )
    reversed_forward = solve_multicomponent_kress_tmz_total_field_batch(
        reversed_boundary,
        sources,
        receivers,
        2.0 * np.pi * 1.2e9,
        exterior=exterior,
        interior=interior,
        eps0=EPS0,
        mu0=MU0,
    )
    np.testing.assert_allclose(
        reversed_forward.total_receiver,
        forward.total_receiver,
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    np.testing.assert_allclose(
        reversed_forward.scattered_receiver,
        forward.scattered_receiver,
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    receiver_dual = np.asarray(
        (
            (0.4 + 0.2j, -0.3 + 0.7j, 0.1 - 0.5j),
            (-0.2 + 0.8j, 0.6 - 0.1j, -0.9 + 0.3j),
        )
    )
    mapped = forward.receiver_operator.apply_state(forward.solution)
    state_dual = forward.receiver_operator.apply_adjoint(receiver_dual)
    np.testing.assert_allclose(
        np.vdot(mapped, receiver_dual),
        np.vdot(forward.solution, state_dual),
        rtol=5.0e-13,
        atol=5.0e-13,
    )


def test_zero_contrast_has_identity_traces_and_zero_exterior_scattering() -> None:
    boundary = _two_circle_boundary()
    sources = np.asarray(((-0.31, 0.12), (0.31, 0.13)))
    receivers = np.asarray(((-0.30, -0.14), (0.30, -0.13), (0.0, 0.24)))
    material = Material(epsr=3.1)
    forward = solve_multicomponent_kress_tmz_total_field_batch(
        boundary,
        sources,
        receivers,
        2.0 * np.pi * 1.2e9,
        exterior=material,
        interior=material,
        eps0=EPS0,
        mu0=MU0,
    )

    # Cross-component exterior blocks remain nonzero at zero contrast.  Their
    # action on analytic incident Cauchy data cancels by Green's identity.
    left, right = boundary.component_slices
    assert np.linalg.norm(forward.system.difference_blocks.delta_v[left, right]) > 0.0
    np.testing.assert_allclose(
        forward.dirichlet_total,
        forward.dirichlet_incident,
        rtol=2.0e-11,
        atol=2.0e-11,
    )
    np.testing.assert_allclose(
        forward.neumann_total,
        forward.neumann_incident,
        rtol=2.0e-11,
        atol=2.0e-11,
    )
    assert (
        np.linalg.norm(forward.scattered_receiver)
        / np.linalg.norm(forward.incident_receiver)
        < 1.0e-10
    )
    assert forward.linear_system_relative_residual < 1.0e-12
    assert np.max(forward.per_source_relative_residual) < 1.0e-12
    assert forward.incident_representation_leak < 1.0e-10


def test_topology_and_resolution_guards_fail_before_assembly() -> None:
    overlapping = OrderedBoundary2D(
        (
            circle((-0.02, 0.0), 0.05, component_id="overlap-a").discretize(
                24, require_even=True
            ),
            circle((0.02, 0.0), 0.05, component_id="overlap-b").discretize(
                24, require_even=True
            ),
        )
    )
    with pytest.raises(MultiComponentTopologyError, match="intersect or touch"):
        build_multicomponent_muller_blocks(overlapping, K_EXTERIOR, K_INTERIOR)
    with pytest.raises(MultiComponentTopologyError, match="intersect or touch"):
        build_exterior_cross_blocks(
            overlapping.components[0],
            overlapping.components[1],
            K_EXTERIOR,
        )

    nested = OrderedBoundary2D(
        (
            circle((0.0, 0.0), 0.12, component_id="outer").discretize(
                32, require_even=True
            ),
            circle((0.0, 0.0), 0.025, component_id="inner").discretize(
                16, require_even=True
            ),
        )
    )
    with pytest.raises(MultiComponentTopologyError, match="nested"):
        build_multicomponent_muller_blocks(nested, K_EXTERIOR, K_INTERIOR)
    with pytest.raises(MultiComponentTopologyError, match="nested"):
        build_exterior_cross_blocks(
            nested.components[0],
            nested.components[1],
            K_EXTERIOR,
        )

    close = OrderedBoundary2D(
        (
            circle((-0.045, 0.0), 0.04, component_id="close-a").discretize(
                16, require_even=True
            ),
            circle((0.045, 0.0), 0.04, component_id="close-b").discretize(
                16, require_even=True
            ),
        )
    )
    with pytest.raises(MultiComponentTopologyError, match="too close"):
        build_multicomponent_muller_blocks(close, K_EXTERIOR, K_INTERIOR)
    with pytest.raises(MultiComponentTopologyError, match="too close"):
        build_exterior_cross_blocks(
            close.components[0],
            close.components[1],
            K_EXTERIOR,
        )
    permissive = MultiComponentAssemblyConfig(minimum_clearance_in_weights=0.0)
    built = build_multicomponent_muller_blocks(
        close,
        K_EXTERIOR,
        K_INTERIOR,
        config=permissive,
    )
    assert built.geometry is close
    cross = build_exterior_cross_blocks(
        close.components[0],
        close.components[1],
        K_EXTERIOR,
        config=permissive,
    )
    assert cross.v.shape == (16, 16)

    odd = OrderedBoundary2D(
        (
            circle((-0.1, 0.0), 0.03, component_id="even").discretize(
                16, require_even=True
            ),
            circle((0.1, 0.0), 0.03, component_id="odd").discretize(15),
        )
    )
    with pytest.raises(MultiComponentCurveGeometryError, match="even number") as caught:
        build_multicomponent_muller_blocks(odd, K_EXTERIOR, K_INTERIOR)
    assert isinstance(caught.value, MultiComponentKressGeometryError)
    assert isinstance(caught.value.__cause__, ValueError)


def test_component_grid_failures_use_the_public_geometry_error_hierarchy() -> None:
    too_short = circle(
        (0.0, 0.0),
        0.03,
        component_id="too-short",
    ).discretize(6, require_even=True)

    malformed = circle(
        (0.0, 0.0),
        0.03,
        component_id="malformed",
    ).discretize(16, require_even=True)
    object.__setattr__(
        malformed,
        "arc_length_weights",
        1.5 * malformed.arc_length_weights,
    )

    self_intersecting = circle(
        (0.0, 0.0),
        0.03,
        component_id="self-intersecting",
    ).discretize(16, require_even=True)
    crossing_order = np.asarray(
        (0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15)
    )
    object.__setattr__(
        self_intersecting,
        "points",
        self_intersecting.points[crossing_order],
    )

    for component, message in (
        (too_short, "at least 8 nodes"),
        (malformed, "arc-length weights are inconsistent"),
        (self_intersecting, "self-intersection"),
    ):
        boundary = OrderedBoundary2D((component,))
        with pytest.raises(
            MultiComponentCurveGeometryError,
            match=message,
        ) as caught:
            adapt_multicomponent_boundary(boundary)
        assert isinstance(caught.value, MultiComponentKressGeometryError)
        assert isinstance(caught.value.__cause__, ValueError)
        assert component.component_id in str(caught.value)

    valid = circle(
        (0.2, 0.0),
        0.03,
        component_id="valid-source",
    ).discretize(16, require_even=True)
    with pytest.raises(
        MultiComponentCurveGeometryError,
        match="target component.*even number",
    ):
        build_exterior_cross_blocks(
            circle(
                (-0.2, 0.0),
                0.03,
                component_id="odd-target",
            ).discretize(15),
            valid,
            K_EXTERIOR,
        )


def test_nonzero_contrast_receiver_field_converges_under_local_refinement() -> None:
    source = np.asarray(((-0.31, 0.12),))
    receiver = np.asarray(((0.30, -0.13),))
    exterior = Material(epsr=3.1)
    interior = Material(epsr=2.2)
    fields = []
    for num_nodes in (32, 48, 64):
        boundary = OrderedBoundary2D(
            (
                circle((-0.12, 0.01), 0.04, component_id="left").discretize(
                    num_nodes,
                    require_even=True,
                ),
                circle((0.11, -0.015), 0.055, component_id="right").discretize(
                    num_nodes,
                    require_even=True,
                ),
            )
        )
        forward = solve_multicomponent_kress_tmz_total_field_batch(
            boundary,
            source,
            receiver,
            2.0 * np.pi * 8.0e9,
            exterior=exterior,
            interior=interior,
            eps0=EPS0,
            mu0=MU0,
        )
        assert forward.linear_system_relative_residual < 1.0e-10
        fields.append(complex(forward.scattered_receiver[0, 0]))

    coarse_change = abs(fields[1] - fields[0])
    fine_change = abs(fields[2] - fields[1])
    assert fine_change < 0.05 * coarse_change
    assert fine_change / abs(fields[2]) < 2.0e-3


def test_sources_and_receivers_are_rejected_inside_any_component() -> None:
    boundary = _two_circle_boundary()
    left_center = np.asarray((-0.12, 0.01))
    right_center = np.asarray((0.11, -0.015))
    outside_source = np.asarray(((-0.31, 0.12),))
    outside_receiver = np.asarray(((0.31, -0.13),))
    material = Material(epsr=3.1)

    assert issubclass(
        MultiComponentCurveGeometryError,
        MultiComponentKressGeometryError,
    )
    assert issubclass(MultiComponentTopologyError, MultiComponentKressGeometryError)
    assert issubclass(MultiComponentFieldPointError, MultiComponentKressGeometryError)

    with pytest.raises(MultiComponentFieldPointError, match="homogeneous exterior"):
        build_multicomponent_exterior_receiver_operator(
            boundary,
            right_center,
            K_EXTERIOR,
        )
    with pytest.raises(MultiComponentFieldPointError, match="homogeneous exterior"):
        solve_multicomponent_kress_tmz_total_field_batch(
            boundary,
            left_center,
            outside_receiver,
            2.0 * np.pi * 1.2e9,
            exterior=material,
            interior=Material(epsr=2.2),
            eps0=EPS0,
            mu0=MU0,
        )
    near_left_boundary = np.asarray(((-0.079, 0.01),))
    with pytest.raises(MultiComponentFieldPointError, match="too close"):
        build_multicomponent_exterior_receiver_operator(
            boundary,
            near_left_boundary,
            K_EXTERIOR,
            minimum_clearance=2.0e-3,
        )
    with pytest.raises(MultiComponentFieldPointError, match="must be distinct"):
        solve_multicomponent_kress_tmz_total_field_batch(
            boundary,
            outside_source,
            outside_source,
            2.0 * np.pi * 1.2e9,
            exterior=material,
            interior=Material(epsr=2.2),
            eps0=EPS0,
            mu0=MU0,
        )
    # The corresponding all-exterior call remains valid.
    solve_config = MultiComponentKressSolveConfig(
        minimum_field_point_clearance_in_weights=1.5
    )
    forward = solve_multicomponent_kress_tmz_total_field_batch(
        boundary,
        outside_source,
        outside_receiver,
        2.0 * np.pi * 1.2e9,
        exterior=material,
        interior=Material(epsr=2.2),
        eps0=EPS0,
        mu0=MU0,
        config=solve_config,
    )
    assert np.all(np.isfinite(forward.total_receiver))
    assert (
        forward.solve_config.minimum_field_point_clearance_in_weights
        == 1.5
    )
    assert forward.diagnostics["minimum_field_point_clearance_required"] == (
        1.5 * np.max(boundary.arc_length_weights)
    )
    assert "minimum_clearance_required" not in forward.diagnostics


def test_public_results_defensively_freeze_arrays_and_validate_shapes() -> None:
    mutable_block = np.ones((2, 3), dtype=np.complex128)
    cross = ExteriorCrossBlocks(
        target_component_id="target",
        source_component_id="source",
        k_exterior=K_EXTERIOR,
        v=mutable_block,
        k=2.0 * mutable_block,
        kp=3.0 * mutable_block,
        t=4.0 * mutable_block,
        minimum_pair_distance=0.1,
        build_seconds=0.0,
    )
    mutable_block[0, 0] = 99.0
    assert cross.v[0, 0] == 1.0
    for values in (cross.v, cross.k, cross.kp, cross.t):
        assert not values.flags.writeable
    with pytest.raises(ValueError, match="same shape"):
        replace(cross, t=np.zeros((3, 2), dtype=np.complex128))

    boundary = _two_circle_boundary()
    forward = solve_multicomponent_kress_tmz_total_field_batch(
        boundary,
        np.asarray(((-0.31, 0.12),)),
        np.asarray(((0.30, -0.13),)),
        2.0 * np.pi * 1.2e9,
        exterior=Material(epsr=3.1),
        interior=Material(epsr=2.2),
        eps0=EPS0,
        mu0=MU0,
    )
    mutable_total = np.array(forward.total_receiver, copy=True)
    hardened = replace(
        forward,
        total_receiver=mutable_total,
        diagnostics={"nested": {"sequence": [1, 2]}},
    )
    expected_total = np.array(hardened.total_receiver, copy=True)
    mutable_total[:] = 0.0
    np.testing.assert_array_equal(hardened.total_receiver, expected_total)
    assert not hardened.total_receiver.flags.writeable
    assert hardened.diagnostics["nested"]["sequence"] == (1, 2)
    with pytest.raises(TypeError):
        hardened.diagnostics["new"] = "not allowed"
    with pytest.raises(ValueError, match="total_receiver must have shape"):
        replace(forward, total_receiver=np.zeros((2, 2), dtype=np.complex128))
    invalid_solution = np.array(forward.solution, copy=True)
    invalid_solution[0, 0] = np.nan
    with pytest.raises(ValueError, match="solution must contain only finite"):
        replace(forward, solution=invalid_solution)


def test_nonfinite_direct_solve_output_fails_explicitly(monkeypatch) -> None:
    def nonfinite_solve(matrix: np.ndarray, right_hand_side: np.ndarray) -> np.ndarray:
        del matrix
        return np.full(right_hand_side.shape, np.nan + 0.0j)

    monkeypatch.setattr(multicomponent_module.np.linalg, "solve", nonfinite_solve)
    with pytest.raises(FloatingPointError, match="non-finite solution"):
        solve_multicomponent_kress_tmz_total_field_batch(
            _two_circle_boundary(),
            np.asarray(((-0.31, 0.12),)),
            np.asarray(((0.30, -0.13),)),
            2.0 * np.pi * 1.2e9,
            exterior=Material(epsr=3.1),
            interior=Material(epsr=2.2),
            eps0=EPS0,
            mu0=MU0,
        )
