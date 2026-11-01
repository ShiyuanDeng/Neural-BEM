"""Pulse-basis, point-matched 2-D TM volume-integral forward solver.

The numerical conventions match the original EISP data generator. Array rows
are image y-coordinates (top to bottom); columns are x-coordinates. Physics
vectors order cells by x first, then y, i.e. ``grid.T.reshape(-1)``.
"""

from dataclasses import dataclass

import numpy as np
from scipy.special import hankel1


# Retained from the validated EISP implementation for numerical compatibility.
ETA_0 = 120.0 * np.pi
C_0 = 3.0e8
EPSILON_0 = 8.85e-12


@dataclass(frozen=True)
class SimulationResult:
    """Fields in physics-vector order: (n_cells, n_tx), except E_scattered."""

    epsilon_r: np.ndarray
    x_grid: np.ndarray
    y_grid: np.ndarray
    tx_xy: np.ndarray
    rx_xy: np.ndarray
    frequency_ghz: float
    E_inc: np.ndarray
    E_total: np.ndarray
    J: np.ndarray
    E_scattered: np.ndarray  # (n_rx, n_tx)

    def field_image(self, field: str, tx_index: int = 0) -> np.ndarray:
        """Return one transmitter's E_inc, E_total, or J as a 2-D image."""
        if field not in {"E_inc", "E_total", "J"}:
            raise ValueError("field must be E_inc, E_total, or J")
        values = getattr(self, field)
        if not 0 <= tx_index < values.shape[1]:
            raise IndexError("tx_index is outside the transmitter range")
        n = self.epsilon_r.shape[0]
        return values[:, tx_index].reshape(n, n).T


def make_domain(grid_size: int, extent: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Make an n-by-n cell-centre grid on [-extent, extent] in each axis."""
    if grid_size < 2 or not np.isfinite(extent) or extent <= 0:
        raise ValueError("grid_size must be >= 2 and extent must be positive")
    axis = np.linspace(-extent, extent, grid_size, dtype=np.float64)
    return np.meshgrid(axis, -axis)


def points_on_circle(count: int, radius: float = 3.0) -> np.ndarray:
    """Equally spaced transmitters or receivers, starting at (radius, 0)."""
    if count < 1 or not np.isfinite(radius) or radius <= 0:
        raise ValueError("count and radius must be positive")
    theta = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    return np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))


def _flatten(grid: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(grid.T).reshape(-1)


def _green(source_xy: np.ndarray, x: np.ndarray, y: np.ndarray, k0: float) -> np.ndarray:
    rho = np.hypot(source_xy[:, 0, None] - x[None, :], source_xy[:, 1, None] - y[None, :])
    if np.any(rho == 0):
        raise ValueError("A transmitter or receiver coincides with a grid cell")
    return ((1j * k0 * ETA_0) * (1j / 4.0) * hankel1(0, k0 * rho)).astype(np.complex128)


def _phi_kernel(n: int, k0: float, step: float) -> np.ndarray:
    offsets = np.arange(1 - n, n, dtype=np.float64)
    dx, dy = np.meshgrid(offsets, offsets, indexing="ij")
    distance = step * np.hypot(dx, dy)
    argument = k0 * np.where(distance == 0, 1.0, distance)
    kernel = (1j * k0 * ETA_0) * (1j / 4.0) * hankel1(0, argument)

    # Equal-area disk integration removes the singular centre-cell value.
    area = step * step
    radius = np.sqrt(area / np.pi)
    kernel[n - 1, n - 1] = (1j * k0 * ETA_0) * (1j / 4.0) * (
        2.0 * hankel1(1, k0 * radius) / (k0 * radius)
        + 4.0j / (k0 * k0 * area)
    )
    return kernel


def _phi_block(
    kernel: np.ndarray, rows: np.ndarray, columns: np.ndarray, n: int
) -> np.ndarray:
    ix = np.repeat(np.arange(n), n)
    iy = np.tile(np.arange(n), n)
    dx = ix[rows, None] - ix[columns][None, :] + n - 1
    dy = iy[rows, None] - iy[columns][None, :] + n - 1
    return kernel[dx, dy]


def _check_xy(values: np.ndarray, name: str) -> np.ndarray:
    xy = np.asarray(values, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1] != 2 or xy.shape[0] < 1 or not np.all(np.isfinite(xy)):
        raise ValueError(f"{name} must be a finite array of shape (N, 2)")
    return xy


def _check_grid(x_grid: np.ndarray, y_grid: np.ndarray, n: int) -> float:
    if x_grid.shape != (n, n) or y_grid.shape != (n, n):
        raise ValueError("x_grid and y_grid must match epsilon_r")
    if not np.all(np.isfinite(x_grid)) or not np.all(np.isfinite(y_grid)):
        raise ValueError("Grid coordinates must be finite")
    step = float(x_grid[0, 1] - x_grid[0, 0])
    if step <= 0 or not np.allclose(x_grid, x_grid[0:1, :], rtol=1e-5, atol=1e-8):
        raise ValueError("x_grid must have uniformly increasing x coordinates")
    if not np.allclose(np.diff(x_grid[0, :]), step, rtol=1e-5, atol=1e-8):
        raise ValueError("x_grid must have uniformly spaced x coordinates")
    if not np.allclose(y_grid, y_grid[:, 0:1], rtol=1e-5, atol=1e-8):
        raise ValueError("y_grid must have constant y along each row")
    if not np.allclose(np.diff(y_grid[:, 0]), -step, rtol=1e-5, atol=1e-8):
        raise ValueError("y_grid must have the same spacing as x_grid")
    return step


def simulate(
    epsilon_r: np.ndarray,
    *,
    frequency_ghz: float = 0.4,
    extent: float = 1.0,
    x_grid: np.ndarray | None = None,
    y_grid: np.ndarray | None = None,
    tx_xy: np.ndarray | None = None,
    rx_xy: np.ndarray | None = None,
    tx_count: int = 16,
    rx_count: int = 32,
    sensor_radius: float = 3.0,
    block_rows: int = 256,
) -> SimulationResult:
    """Simulate a real relative-permittivity image in homogeneous free space.

    Returns incident/total electric fields and equivalent current at all cell
    centres, plus scattered electric field at each receiver for every source.
    The direct solve scales cubically with the number of non-background cells.
    """
    if np.iscomplexobj(epsilon_r):
        raise ValueError("epsilon_r must be real; complex material parameters are not supported")
    epsilon = np.asarray(epsilon_r, dtype=np.float64)
    if epsilon.ndim != 2 or epsilon.shape[0] != epsilon.shape[1] or epsilon.shape[0] < 2:
        raise ValueError("epsilon_r must be a square 2-D array with side >= 2")
    if not np.all(np.isfinite(epsilon)) or np.any(epsilon <= 0):
        raise ValueError("epsilon_r must contain finite, positive real values")
    if not np.isfinite(frequency_ghz) or frequency_ghz <= 0:
        raise ValueError("frequency_ghz must be positive")
    if block_rows < 1:
        raise ValueError("block_rows must be positive")

    n = epsilon.shape[0]
    if (x_grid is None) != (y_grid is None):
        raise ValueError("Supply both x_grid and y_grid, or neither")
    if x_grid is None:
        x_grid, y_grid = make_domain(n, extent)
    else:
        x_grid = np.asarray(x_grid, dtype=np.float64)
        y_grid = np.asarray(y_grid, dtype=np.float64)
    step = _check_grid(x_grid, y_grid, n)
    tx = _check_xy(points_on_circle(tx_count, sensor_radius) if tx_xy is None else tx_xy, "tx_xy")
    rx = _check_xy(points_on_circle(rx_count, sensor_radius) if rx_xy is None else rx_xy, "rx_xy")

    frequency_hz = frequency_ghz * 1e9
    k0 = 2.0 * np.pi * frequency_hz / C_0
    omega = 2.0 * np.pi * frequency_hz
    x_flat, y_flat = _flatten(x_grid), _flatten(y_grid)
    E_inc = _green(tx, x_flat, y_flat, k0).T
    R = _green(rx, x_flat, y_flat, k0)

    contrast = _flatten(epsilon) - 1.0
    active = np.flatnonzero(np.abs(contrast) > 1e-12)
    J = np.zeros_like(E_inc)
    if active.size == 0:
        return SimulationResult(epsilon, x_grid, y_grid, tx, rx, frequency_ghz,
                                E_inc, E_inc.copy(), J, np.zeros((len(rx), len(tx)), dtype=np.complex128))

    xi = (-1j * omega * EPSILON_0 * step * step * contrast)[active]
    kernel = _phi_kernel(n, k0, step)
    system = np.empty((active.size, active.size), dtype=np.complex128)
    for start in range(0, active.size, block_rows):
        stop = min(start + block_rows, active.size)
        system[start:stop] = -_phi_block(kernel, active[start:stop], active, n) * xi[None, :]
    system[np.diag_indices(active.size)] += 1.0

    E_active = np.linalg.solve(system, E_inc[active])
    J_active = xi[:, None] * E_active
    J[active] = J_active
    E_scattered = R[:, active] @ J_active
    E_total = np.empty_like(E_inc)
    for start in range(0, n * n, block_rows):
        stop = min(start + block_rows, n * n)
        rows = np.arange(start, stop)
        E_total[start:stop] = E_inc[start:stop] + _phi_block(kernel, rows, active, n) @ J_active

    return SimulationResult(epsilon, x_grid, y_grid, tx, rx, frequency_ghz,
                            E_inc, E_total, J, E_scattered)
