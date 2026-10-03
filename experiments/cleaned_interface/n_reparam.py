"""NU-002 spectral arclength reparameterization (compass eq. 9) and its shape audit.

For a Laurent curve z(theta) with speed sigma=|z'| and normalized arclength
alpha(theta) = theta + eta(theta), alpha' = sigma/sigma_0, the arclength curve
z~(alpha) = z(theta(alpha)) has Fourier coefficients

    z~_k = <z(theta) alpha'(theta) e^{-i k alpha(theta)}>_0          (change of variables)

which is eq. 9 before its integration by parts (Koga 2021, eq. 3.6). The mean
is a trapezoid sum on a uniform theta grid used only as a quadrature engine:
no interpolation, no inversion theta(alpha), no composition. The integrand is
analytic, so the sum converges geometrically; the grid is doubled until two
successive results agree.

By Lemma 2 the arclength curve of a non-circle is not band-limited. Cropping
z~ to the storage band K therefore changes the SHAPE by the discarded tail.
``shape_distance`` measures that change exactly (Newton projection of the new
curve's samples onto the old curve), so a reset can be refused when the crop
would move the shape by more than a tolerance.
"""
import numpy as np

from experiments.shape_continuation.geometry import FourierCurve
from bem_inverse.n_reparam import (
    _evaluate, normalized_arclength, arclength_coefficients,
    reparameterize, speed_ratio, _point,
    shape_distance, mean_radius, reset,
)


# --------------------------------------------------------------------------- NU-002 replay

CAMPAIGNS = dict(nodal='CI-001', A='NU-001-A', B='NU-001-B')
CORE = ('core__wrong_circle', 'core__peanut', 'core__circle_to_c', 'core__hook', 'core__circle_to_star', 'core__kite')


def replay(root, output):
    """Reset the last accepted state of every stage of the six core runs of each arm; write replay.json."""
    import json
    from pathlib import Path
    rows = []
    for arm, campaign in CAMPAIGNS.items():
        for case in CORE:
            states = json.loads((Path(root)/campaign/'runs'/case/'accepted.json').read_text())['states']
            last = {s['stage']: s for s in states}
            for stage, state in last.items():
                z = np.asarray(state['curve']['real'])+1j*np.asarray(state['curve']['imag'])
                new, info = reparameterize(z)
                rows.append(dict(arm=arm, case=case, stage=stage, M=state['M'], K=len(z)//2,
                                 speed_ratio=speed_ratio(z), speed_ratio_after=speed_ratio(new),
                                 shape_relative=shape_distance(z, new)/mean_radius(z),
                                 quadrature_change=info['quadrature_change'], quadrature_nodes=info['count']))
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output)/'replay.json').write_text(json.dumps(dict(
        description='Last accepted state of every stage of the six core runs (nodal = CI-001, A/B = NU-001), '
                    'reset to arclength by n_reparam.reparameterize at its own storage band K. '
                    'shape_relative = max distance from the reset curve to the original curve over '
                    'sigma_0 = L/(2 pi); speed ratios on a uniform grid of max(1024, 32(K+1)) nodes.',
        rows=rows), indent=1))
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--root', default='results/validation/cleaned_interfaces')
    parser.add_argument('--output', default='results/validation/cleaned_interfaces/NU-002-reset-replay')
    args = parser.parse_args()
    replay(args.root, args.output)
