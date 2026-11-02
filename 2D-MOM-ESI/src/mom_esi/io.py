"""Save a forward simulation in a compact, documented format."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .solver import SimulationResult


def save_result(result: SimulationResult, output: str | Path) -> Path:
    """Save all fields to a new or empty directory; never overwrite a result."""
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"Output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output / "fields.npz",
        epsilon_r=result.epsilon_r,
        x_grid=result.x_grid,
        y_grid=result.y_grid,
        tx_xy=result.tx_xy,
        rx_xy=result.rx_xy,
        E_inc=result.E_inc,
        E_total=result.E_total,
        J=result.J,
        E_scattered=result.E_scattered,
    )
    metadata = {
        "frequency_ghz": result.frequency_ghz,
        "grid_size": result.epsilon_r.shape[0],
        "n_tx": len(result.tx_xy),
        "n_rx": len(result.rx_xy),
        "n_active": int(np.count_nonzero(np.abs(result.epsilon_r - 1) > 1e-12)),
        "field_shape": "(n_cells, n_tx); x-first then y cell order",
        "scattered_shape": "(n_rx, n_tx)",
        "model": "2-D scalar TM, pulse-basis point-matched volume integral equation",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return output / "fields.npz"

