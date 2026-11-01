"""Generate a dielectric disk and save its 2-D TM scattering fields."""

import argparse
import numpy as np

from mom_esi import make_domain, save_result, simulate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="outputs/circle", help="New or empty output directory")
    args = parser.parse_args()

    x, y = make_domain(32, extent=1.0)
    epsilon = np.ones_like(x)
    epsilon[x * x + y * y <= 0.48**2] = 2.0

    result = simulate(epsilon, frequency_ghz=0.4)
    saved = save_result(result, args.output)
    print(f"Saved {saved}")
    print(f"E_scattered shape: {result.E_scattered.shape}")
    print(f"E_scattered norm: {np.linalg.norm(result.E_scattered):.6f}")


if __name__ == "__main__":
    main()
