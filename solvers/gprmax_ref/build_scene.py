"""Generate gprMax .in scenes for penetrable 2D target scattering cases.

Run only with the ``gprMax`` conda environment's Python -- this module has no
dependency on that environment beyond stdlib, so it also imports cleanly from
the main ``EMNerf`` environment for cache-key computation.

Coordinates are local to the scene, not the app's ``config.simulation_config``
frame: the physics only depends on the Tx/target/Rx *relative* geometry, and by
the circle's rotational symmetry a single representative bistatic pair stands
in for the whole ring (see ``docs/gprmax_reference_study.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


TARGET_SHAPES = ("circle", "square", "ellipse", "star", "two_circles")


@dataclass(frozen=True)
class SceneGeometry:
    domain_x: float
    domain_y: float
    cell_size: float
    pml_cells: int
    target_center: tuple[float, float]
    target_shape: str
    target_size: float
    target_parameters: dict[str, Any]
    tx: tuple[float, float]
    rx: tuple[float, float]


def build_geometry(
    *,
    target_shape: str,
    target_size: float,
    target_parameters: dict[str, Any] | None = None,
    standoff: float,
    tx_rx_offset: float,
    cell_size: float,
    pml_cells: int = 12,
    buffer_cells: int = 12,
) -> SceneGeometry:
    """Size a domain that snugly fits the target, both antennas, and PML.

    ``target_size`` is the target's bounding half-extent: radius for a circle,
    half-side for an axis-aligned square, semi-major axis for an ellipse, outer
    radius for a star, and the maximum component-center offset plus radius for
    two circles.

    The representative pair sits at angle 0 (Tx) and ``sep`` (Rx) on the
    standoff ring, ``sep = tx_rx_offset / standoff``, matching
    ``pytest/test_circle_comparison.py`` and ``pytest/test_square_comparison.py``'s
    ``_ring_scan``.
    """

    if target_shape not in TARGET_SHAPES:
        raise ValueError(f"target_shape must be one of {TARGET_SHAPES}, got {target_shape!r}.")
    target_parameters = _normalise_target_parameters(
        target_shape,
        target_size=target_size,
        target_parameters=target_parameters,
    )
    if target_shape == "square":
        # Snap to a whole number of cells so the box target sits exactly on
        # cell faces -- zero staircasing, unlike the circle. That is the
        # entire point of using a square as an independent gprMax oracle: see
        # docs/gprmax_reference_study.md, where staircasing was the circle's
        # dominant error source.
        target_size = round(target_size / cell_size) * cell_size

    sep = tx_rx_offset / standoff
    margin = (pml_cells + buffer_cells) * cell_size
    target_extent = _target_extent(target_shape, target_size, target_parameters)
    target_extent = math.ceil(target_extent / cell_size) * cell_size
    target_center = (target_extent + margin, target_extent + margin)

    tx = (target_center[0] + standoff, target_center[1])
    rx = (
        target_center[0] + standoff * math.cos(sep),
        target_center[1] + standoff * math.sin(sep),
    )

    domain_x = max(tx[0], rx[0]) + margin
    domain_y = max(tx[1], rx[1], target_center[1] + target_extent) + margin
    return SceneGeometry(
        domain_x,
        domain_y,
        cell_size,
        pml_cells,
        target_center,
        target_shape,
        target_size,
        target_parameters,
        tx,
        rx,
    )


def _normalise_target_parameters(
    target_shape: str,
    *,
    target_size: float,
    target_parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    params = {} if target_parameters is None else dict(target_parameters)
    if target_shape == "ellipse":
        semi_major = float(params.get("semi_major", target_size))
        semi_minor = float(params.get("semi_minor", target_size))
        if semi_major <= 0.0 or semi_minor <= 0.0:
            raise ValueError("ellipse semi-axes must be positive.")
        return {"semi_major": semi_major, "semi_minor": semi_minor}
    if target_shape == "star":
        mean_radius = float(params.get("mean_radius", target_size))
        amplitude = float(params.get("amplitude", 0.25))
        lobes = int(params.get("lobes", 5))
        if mean_radius <= 0.0:
            raise ValueError("star mean radius must be positive.")
        if abs(amplitude) >= 1.0:
            raise ValueError("star amplitude magnitude must be less than 1.")
        if lobes < 2:
            raise ValueError("star lobes must be at least 2.")
        return {"mean_radius": mean_radius, "amplitude": amplitude, "lobes": lobes}
    if target_shape == "two_circles":
        centers = params.get("circle_centers")
        radii = params.get("circle_radii")
        if centers is None or radii is None:
            raise ValueError("two_circles requires circle_centers and circle_radii target parameters.")
        centers = [tuple(float(value) for value in center) for center in centers]
        radii = [float(radius) for radius in radii]
        if len(centers) != len(radii) or len(centers) < 2:
            raise ValueError("two_circles requires at least two centers and the same number of radii.")
        if any(len(center) != 2 for center in centers):
            raise ValueError("two_circles circle_centers must be 2D coordinates.")
        if any(radius <= 0.0 for radius in radii):
            raise ValueError("two_circles radii must be positive.")
        for first in range(len(centers)):
            for second in range(first + 1, len(centers)):
                distance = math.dist(centers[first], centers[second])
                if distance <= radii[first] + radii[second]:
                    raise ValueError("two_circles components must be non-touching.")
        return {
            "circle_centers": [[center[0], center[1]] for center in centers],
            "circle_radii": radii,
        }
    return {}


def _target_extent(target_shape: str, target_size: float, target_parameters: dict[str, Any]) -> float:
    if target_shape == "ellipse":
        return max(float(target_parameters["semi_major"]), float(target_parameters["semi_minor"]))
    if target_shape == "star":
        return float(target_parameters["mean_radius"]) * (1.0 + abs(float(target_parameters["amplitude"])))
    if target_shape == "two_circles":
        centers = target_parameters["circle_centers"]
        radii = target_parameters["circle_radii"]
        return max(
            max(abs(float(center[0])) + float(radius), abs(float(center[1])) + float(radius))
            for center, radius in zip(centers, radii)
        )
    return float(target_size)


def _inside_voxelized_target(geometry: SceneGeometry, x: float, y: float) -> bool:
    cx, cy = geometry.target_center
    dx, dy = x - cx, y - cy
    if geometry.target_shape == "ellipse":
        semi_major = float(geometry.target_parameters["semi_major"])
        semi_minor = float(geometry.target_parameters["semi_minor"])
        return (dx / semi_major) ** 2 + (dy / semi_minor) ** 2 <= 1.0
    if geometry.target_shape == "star":
        mean_radius = float(geometry.target_parameters["mean_radius"])
        amplitude = float(geometry.target_parameters["amplitude"])
        lobes = int(geometry.target_parameters["lobes"])
        theta = math.atan2(dy, dx)
        boundary_radius = mean_radius * (1.0 + amplitude * math.cos(lobes * theta))
        return math.hypot(dx, dy) <= boundary_radius
    if geometry.target_shape == "two_circles":
        centers = geometry.target_parameters["circle_centers"]
        radii = geometry.target_parameters["circle_radii"]
        return any(
            math.hypot(dx - float(center[0]), dy - float(center[1])) <= float(radius)
            for center, radius in zip(centers, radii)
        )
    raise ValueError(f"target_shape={geometry.target_shape!r} is not voxelized.")


def _voxelized_target_boxes(geometry: SceneGeometry, material: str) -> list[str]:
    """Emit row-wise boxes for cell centers inside a smooth target."""

    cell_size = geometry.cell_size
    cx, cy = geometry.target_center
    extent = _target_extent(geometry.target_shape, geometry.target_size, geometry.target_parameters)
    i_min = max(0, math.floor((cx - extent) / cell_size))
    i_max = min(math.ceil((cx + extent) / cell_size), math.ceil(geometry.domain_x / cell_size))
    j_min = max(0, math.floor((cy - extent) / cell_size))
    j_max = min(math.ceil((cy + extent) / cell_size), math.ceil(geometry.domain_y / cell_size))

    boxes: list[str] = []
    for j in range(j_min, j_max):
        y_center = (j + 0.5) * cell_size
        run_start: int | None = None
        for i in range(i_min, i_max):
            x_center = (i + 0.5) * cell_size
            inside = _inside_voxelized_target(geometry, x_center, y_center)
            if inside and run_start is None:
                run_start = i
            elif not inside and run_start is not None:
                boxes.append(_box_line(run_start, i, j, cell_size, material))
                run_start = None
        if run_start is not None:
            boxes.append(_box_line(run_start, i_max, j, cell_size, material))
    if not boxes:
        raise ValueError(f"voxelized {geometry.target_shape} target produced no boxes.")
    return boxes


def _box_line(i_start: int, i_stop: int, j: int, cell_size: float, material: str) -> str:
    x1, x2 = i_start * cell_size, i_stop * cell_size
    y1, y2 = j * cell_size, (j + 1) * cell_size
    return f"#box: {x1:.6f} {y1:.6f} 0 {x2:.6f} {y2:.6f} {cell_size:.6f} {material}"


def render_scene(
    geometry: SceneGeometry,
    *,
    sand_epsr: float,
    sand_sigma: float,
    plastic_epsr: float,
    plastic_sigma: float,
    waveform: str,
    center_frequency: float,
    time_window: float,
    title: str,
    include_target: bool,
) -> str:
    """Render a gprMax ``.in`` file. ``include_target=False`` gives the
    homogeneous-sand calibration run: same source, same domain, no target."""

    g = geometry
    lines = [
        f"#title: {title}",
        f"#domain: {g.domain_x:.6f} {g.domain_y:.6f} {g.cell_size:.6f}",
        f"#dx_dy_dz: {g.cell_size:.6f} {g.cell_size:.6f} {g.cell_size:.6f}",
        f"#time_window: {time_window:.6e}",
        f"#pml_cells: {g.pml_cells} {g.pml_cells} 0 {g.pml_cells} {g.pml_cells} 0",  # no PML in z: domain is 1 cell thick there
        "",
        f"#material: {sand_epsr:g} {sand_sigma:g} 1 0 sand",
        f"#material: {plastic_epsr:g} {plastic_sigma:g} 1 0 plastic",
        "",
        f"#box: 0 0 0 {g.domain_x:.6f} {g.domain_y:.6f} {g.cell_size:.6f} sand",
    ]
    if include_target:
        cx, cy = g.target_center
        if g.target_shape == "circle":
            lines.append(
                f"#cylinder: {cx:.6f} {cy:.6f} 0 {cx:.6f} {cy:.6f} {g.cell_size:.6f} "
                f"{g.target_size:.6f} plastic"
            )
        elif g.target_shape == "square":
            x1, y1 = cx - g.target_size, cy - g.target_size
            x2, y2 = cx + g.target_size, cy + g.target_size
            lines.append(f"#box: {x1:.6f} {y1:.6f} 0 {x2:.6f} {y2:.6f} {g.cell_size:.6f} plastic")
        elif g.target_shape == "two_circles":
            centers = g.target_parameters["circle_centers"]
            radii = g.target_parameters["circle_radii"]
            for center_offset, radius in zip(centers, radii):
                circle_x = cx + float(center_offset[0])
                circle_y = cy + float(center_offset[1])
                lines.append(
                    f"#cylinder: {circle_x:.6f} {circle_y:.6f} 0 "
                    f"{circle_x:.6f} {circle_y:.6f} {g.cell_size:.6f} "
                    f"{float(radius):.6f} plastic"
                )
        else:  # smooth non-circular targets are staircased onto the Yee grid
            lines.extend(_voxelized_target_boxes(g, "plastic"))
    lines += [
        "",
        f"#waveform: {waveform} 1 {center_frequency:.6e} my_wave",
        f"#hertzian_dipole: z {g.tx[0]:.6f} {g.tx[1]:.6f} 0 my_wave",
        f"#rx: {g.rx[0]:.6f} {g.rx[1]:.6f} 0",
        "",
    ]
    return "\n".join(lines)
