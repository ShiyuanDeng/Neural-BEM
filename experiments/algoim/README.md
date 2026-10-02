# Optional Algoim experiment

Run `python experiments/algoim/run_comparison.py` from the repository root in an
environment with NumPy, SciPy, Matplotlib, PyTorch, scikit-image and the existing
solver dependencies. A C++17 `g++` compiler is required.

`build.py` downloads only the nine required files from the official, SHA-pinned
Algoim revision into `/tmp/neural_bem_algoim`, verifies all hashes, and compiles
`quadrature.cpp`. It does not modify the system or vendor the library. The
upstream license is fetched and preserved with the headers. Delete the temporary
cache only if you intentionally want to force another download/build.

The experiment loads the safe JSON snapshot of a real saved checkpoint from
`results/algoim/input/siren_circle.json`, exports its SIREN layers to the temporary directory, performs analytic and
neural surface quadrature, compares production Method B at three bandwidths,
and checks continuum shape derivatives against recomputed quadrature.

Results, limitations and the mathematical derivative are documented in
[the results report](../../results/algoim/README.md).
