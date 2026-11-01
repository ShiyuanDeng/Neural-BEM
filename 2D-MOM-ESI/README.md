# MOM-ESI

A small forward simulator for **two-dimensional (2-D) TM electromagnetic
scattering**. Given a relative-permittivity map `epsilon_r[y, x]`, it computes
the incident field, total field, equivalent current, and scattered field at
the receivers. It does not perform inverse reconstruction.

## Model

The background is free space (`epsilon_r = 1`). The model assumes real,
positive relative permittivity and **zero electrical conductivity**
(`sigma = 0`). It does not support lossy materials or complex permittivity.
This is a scalar 2-D TM model with line sources, **not** a full 3-D Maxwell
solver.

The solver discretizes the volume-integral equation on a square grid using
pulse basis functions and point matching (a method-of-moments formulation).
For each cell, the contrast is `chi = epsilon_r - 1`. With cell area `A`,
angular frequency `omega`, and free-space permittivity `epsilon_0`, it uses

```text
xi = -i * omega * epsilon_0 * A * chi
J = xi * E_total
E_total = E_inc + Phi * J
E_scattered = R * J
```

`Phi` couples the grid cells through a 2-D Hankel-function Green kernel; its
diagonal uses an equal-area disk self term. `R` maps the equivalent current
to the receiver positions. Only cells with nonzero contrast enter the dense
linear solve.

## Run an example

```bash
cd MOM-ESI
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/circle.py
```

The example places a disk with `epsilon_r = 2` in free space and simulates
0.4 GHz measurements with 16 transmitters and 32 receivers. It writes
`outputs/circle/fields.npz` and `outputs/circle/metadata.json`. To run it
again, choose a new directory with `--output`.

For your own square, real-valued permittivity map saved as `epsilon.npy`:

```bash
mom-esi epsilon.npy --output outputs/my_case
```

`fields.npz` contains `epsilon_r`, grid and sensor coordinates, `E_inc`,
`E_total`, `J`, and `E_scattered`. `E_inc`, `E_total`, and `J` have shape
`(n_cells, n_transmitters)`; `E_scattered` has shape
`(n_receivers, n_transmitters)`. Image rows run from top to bottom, while
field vectors use `image.T.reshape(-1)` cell ordering. The output directory
must be new or empty.

The defaults are a grid spanning `[-1, 1]` m in both axes, sensors on a 3 m
circle, and 0.4 GHz. Run `mom-esi --help` to change frequency, geometry, or
sensor coordinates. The direct solve can become slow for large dense objects.

## Validation

The 0.4 GHz implementation was compared with the clean
[SingleTX-EISP](https://github.com/gomenei/SingleTX-EISP) MNIST and Cylinder
test fields; representative scattered fields agree to about `2e-6` relative
L2 error. The source datasets are not included. To run the optional external
data checks, install `.[test]`, set `MOM_ESI_SINGLETX_TEST_ROOT` to the
official `test/data/test` directory, and run `pytest -q`. Only load pickle
files from a source you trust.
