"""Command-line entry point for a single permittivity image."""

import argparse
from pathlib import Path

import numpy as np

from .io import save_result
from .solver import simulate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mom-esi",
        description="Simulate 2-D TM fields from a relative-permittivity .npy image.",
    )
    parser.add_argument("epsilon", type=Path, help="Square 2-D .npy array of relative permittivity")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory")
    parser.add_argument("--frequency-ghz", type=float, default=0.4)
    parser.add_argument("--extent", type=float, default=1.0, help="Half-width of grid centre coordinates, in metres")
    parser.add_argument("--x-grid", type=Path, help="Optional x-coordinate .npy array")
    parser.add_argument("--y-grid", type=Path, help="Optional y-coordinate .npy array")
    parser.add_argument("--tx-xy", type=Path, help="Optional transmitter (N, 2) .npy array")
    parser.add_argument("--rx-xy", type=Path, help="Optional receiver (N, 2) .npy array")
    parser.add_argument("--tx-count", type=int, default=16)
    parser.add_argument("--rx-count", type=int, default=32)
    parser.add_argument("--sensor-radius", type=float, default=3.0)
    return parser


def _load(path: Path | None) -> np.ndarray | None:
    return None if path is None else np.load(path, allow_pickle=False)


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
            raise ValueError(f"Output directory must be absent or empty: {args.output}")
        result = simulate(
            _load(args.epsilon),
            frequency_ghz=args.frequency_ghz,
            extent=args.extent,
            x_grid=_load(args.x_grid),
            y_grid=_load(args.y_grid),
            tx_xy=_load(args.tx_xy),
            rx_xy=_load(args.rx_xy),
            tx_count=args.tx_count,
            rx_count=args.rx_count,
            sensor_radius=args.sensor_radius,
        )
        saved = save_result(result, args.output)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"mom-esi: {exc}\n")
    print(f"Saved {saved}")


if __name__ == "__main__":
    main()
