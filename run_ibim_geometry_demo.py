from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

import sys
from pathlib import Path

# Pick the solver before importing it: `gpr_bem` below is whichever package
# --solver selects out of solvers/. Defaults to the frozen reference.
sys.path.insert(0, str(Path(__file__).resolve().parent / "solvers"))
import solver_select

SELECTED_SOLVER = solver_select.resolve_from_argv()
SELECTED_SOLVER_PACKAGE = solver_select.alias_as_gpr_bem(SELECTED_SOLVER)

from config import simulation_config as cfg
from gpr_bem.ibim_geometry import build_implicit_boundary_band
from gpr_bem.neural_sdf import circle_signed_distance, circles_union_signed_distance


THREE_CIRCLE_CENTERS = np.array(
    [
        [0.3, 0.5],
        [0.5, 0.5],
        [0.7, 0.5],
    ],
    dtype=float,
)


def _plot_band(ax: plt.Axes, band, *, title: str, colorbar_label: str = "Quadrature weight") -> None:
    scatter = ax.scatter(
        band.points[:, 0].detach().cpu().numpy(),
        band.points[:, 1].detach().cpu().numpy(),
        c=band.quadrature_weights[:, 0].detach().cpu().numpy(),
        s=6.0,
        cmap="magma",
    )
    projected = band.projected_points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    stride = max(projected.shape[0] // 120, 1)
    ax.scatter(projected[:, 0], projected[:, 1], s=2.0, c="cyan", alpha=0.45)
    ax.quiver(
        projected[::stride, 0],
        projected[::stride, 1],
        normals[::stride, 0],
        normals[::stride, 1],
        angles="xy",
        scale_units="xy",
        scale=35.0,
        width=0.0022,
        color="white",
        alpha=0.8,
    )
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04, label=colorbar_label)


def main() -> None:
    output_dir = Path("results/ibim_geometry_demo")
    output_dir.mkdir(parents=True, exist_ok=True)

    circle_center = (0.5, 0.5)
    circle_radius = float(cfg.TARGET_RADIUS)
    bounds = ((0.0, 0.0), (cfg.DOMAIN_WIDTH, cfg.DOMAIN_HEIGHT))

    single_circle_band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=circle_center, radius=circle_radius),
        bounds,
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    three_circle_band = build_implicit_boundary_band(
        lambda points: circles_union_signed_distance(
            points,
            centers=THREE_CIRCLE_CENTERS,
            radii=np.full(3, circle_radius, dtype=float),
        ),
        bounds,
        grid_shape=(385, 385),
        dtype=torch.float64,
    )

    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.8), constrained_layout=True)
    _plot_band(
        axes[0],
        single_circle_band,
        title=(
            f"Single-circle implicit band\n"
            f"measure={single_circle_band.boundary_measure().item():.4f} m, "
            f"target={2.0 * np.pi * circle_radius:.4f} m"
        ),
    )
    _plot_band(
        axes[1],
        three_circle_band,
        title=(
            f"Three-circle implicit band\n"
            f"measure={three_circle_band.boundary_measure().item():.4f} m, "
            f"target={3.0 * 2.0 * np.pi * circle_radius:.4f} m"
        ),
    )
    figure.suptitle("IBIM Geometry Phase-A Demo", fontsize=15)

    output_path = output_dir / "ibim_geometry_demo.png"
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)

    print(f"Saved geometry demo to {output_path}")
    print(
        "Single-circle samples="
        f"{single_circle_band.num_samples}, "
        f"boundary_measure={single_circle_band.boundary_measure().item():.6f}"
    )
    print(
        "Three-circle samples="
        f"{three_circle_band.num_samples}, "
        f"boundary_measure={three_circle_band.boundary_measure().item():.6f}"
    )


if __name__ == "__main__":
    main()
