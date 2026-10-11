"""Analytic trainable SDF for a fixed collection of circles.

This module is deliberately independent of the active inverse models.  It is
an integration fixture for multi-component geometry today and can later be
wired into a solver-neutral dispatcher once that dispatcher accepts an
``OrderedBoundary2D`` with multiple components.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import torch
from torch import nn


def _real_floating_dtype(dtype: torch.dtype) -> torch.dtype:
    if dtype not in {
        torch.float16,
        torch.bfloat16,
        torch.float32,
        torch.float64,
    }:
        raise TypeError("dtype must be a real floating-point torch dtype.")
    return dtype


class CircleUnionSDF2D(nn.Module):
    """Trainable minimum of component-circle signed-distance functions.

    For disjoint circles, ``min_i(||x - c_i|| - r_i)`` is the negative-inside
    signed distance to their union in a neighbourhood of every boundary
    component.  The minimum is intentionally evaluated directly: it gives an
    exact analytic extraction target without coupling this test model to the
    marching-squares or ordered-boundary implementations.

    Centres and logarithmic radii are parameters, which makes the model ready
    for a future low-dimensional inverse controller.  Geometry feasibility
    (component count, intersections, and clearance) belongs to the boundary
    builder rather than this unconstrained parameter container.
    """

    def __init__(
        self,
        *,
        centers: Sequence[Sequence[float]],
        radii: Sequence[float],
        dtype: torch.dtype = torch.float64,
        device: torch.device | str | None = None,
    ) -> None:
        super().__init__()
        resolved_dtype = _real_floating_dtype(dtype)
        if np.iscomplexobj(centers) or np.iscomplexobj(radii):
            raise ValueError("centers and radii must be real-valued.")
        try:
            center_values = np.array(centers, dtype=np.float64, copy=True)
            radius_values = np.array(radii, dtype=np.float64, copy=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("centers and radii must be real numeric values.") from exc
        if (
            center_values.ndim != 2
            or center_values.shape[1:] != (2,)
            or center_values.shape[0] < 1
            or not np.all(np.isfinite(center_values))
        ):
            raise ValueError(
                "centers must have shape (num_components, 2) and contain "
                "finite coordinates."
            )
        if (
            radius_values.shape != (center_values.shape[0],)
            or not np.all(np.isfinite(radius_values))
            or np.any(radius_values <= 0.0)
        ):
            raise ValueError(
                "radii must contain one finite positive value per component."
            )

        self.centers = nn.Parameter(
            torch.as_tensor(center_values, dtype=resolved_dtype, device=device)
        )
        self.log_radii = nn.Parameter(
            torch.as_tensor(
                np.log(radius_values),
                dtype=resolved_dtype,
                device=device,
            )
        )

    @property
    def num_components(self) -> int:
        """Number of circle primitives in the union."""

        return int(self.centers.shape[0])

    @property
    def radii(self) -> torch.Tensor:
        """Positive differentiable radius of every component."""

        return torch.exp(self.log_radii)

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        if not isinstance(points, torch.Tensor):
            raise TypeError("points must be a torch.Tensor.")
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must have shape (num_points, 2).")
        if not points.is_floating_point():
            raise TypeError("points must have a floating-point dtype.")
        if points.device != self.centers.device:
            raise ValueError(
                "points and CircleUnionSDF2D parameters must be on the same device."
            )

        centers = self.centers.to(dtype=points.dtype)
        radii = self.radii.to(dtype=points.dtype)
        component_values = torch.linalg.norm(
            points[:, None, :] - centers[None, :, :],
            dim=2,
        ) - radii[None, :]
        return torch.amin(component_values, dim=1, keepdim=True)

    def physical_geometry(self) -> dict[str, float]:
        """Return detached parameters keyed by input-order primitive identity.

        ``primitive_XXX`` deliberately does not claim to be an extracted
        boundary component ID.  The frontend assigns its own deterministic
        spatial ordering, which can differ when primitives are supplied out of
        order or move past one another.
        """

        centers = self.centers.detach().cpu().to(dtype=torch.float64).numpy()
        radii = self.radii.detach().cpu().to(dtype=torch.float64).numpy()
        geometry: dict[str, float] = {}
        for index, (center, radius) in enumerate(zip(centers, radii)):
            prefix = f"primitive_{index:03d}"
            geometry[f"{prefix}.center_x"] = float(center[0])
            geometry[f"{prefix}.center_y"] = float(center[1])
            geometry[f"{prefix}.radius"] = float(radius)
        return geometry

    @property
    def geometry_dict(self) -> dict[str, float]:
        """Property alias for experiment logging."""

        return self.physical_geometry()


__all__ = ["CircleUnionSDF2D"]
