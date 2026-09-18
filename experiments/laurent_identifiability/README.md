# Calibration uncertainty and neighbour-assisted identifiability

LAU-005. The [neighbour experiment](../laurent_neighbour/README.md) compared two
extremes of antenna calibration: gains exactly known, or gains completely free.
It attributed its coupled-versus-additive gain to *scattering-assisted separation
of shape and calibration*. This experiment makes calibration uncertainty
**continuous** and asks where that explanation actually holds.

One Gaussian log-gain prior of scale `tau`, multiplying the neighbour study's own
truth gain scale `(0.15 nepers, 0.25 rad)`, spans both extremes:

| `tau` | meaning |
|---|---|
| `0` | exact calibration; the gain parameters are removed |
| `1` | the gain errors the neighbour study actually simulated (1.30 dB, 14.3 deg) |
| `inf` | the study's free-gain arm; an improper flat prior |

The same `tau` enters the Fisher analysis (a Schur complement carrying the prior)
and the nonlinear inverse (penalty rows on the gain coordinates), so the bound and
the recovery describe the same estimator.

- **Stage A** sweeps every one of the 63 configurations in the recorded screen and
  all three prior shape pairs, and solves for the crossover `tau*` at which
  coupling stops paying. Both endpoints are checked against the recorded screen
  values; monotonicity in `tau` is checked on every curve.
- **Stage B** runs matched nonlinear recoveries at five calibration scales, plus a
  bridge arm that is literally the recorded study's free-gain inverse — a test
  compares its residual and Jacobian against the study's own object.

Nothing here edits the neighbour, calibration, `modal_muller_research` or solver
packages; they are imported read-only so their recorded source hashes keep
validating. No production default changes and no speed claim is made.

See the [measured closeout](../../results/validation/laurent/LAU-005-20260918-closeout/README.md).
