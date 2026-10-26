# HB-004 answers for items 1, 10 and 11

The circle formulas match the maintained physical solver. Circular ItI
propagation crosses a real DtN pole accurately. Neither result establishes
general-curve response propagation or faster inverse reconstruction.

## Items 1 and 10 — circle blocks and fields

All 12 combinations of endpoint frequencies, three contrasts and real/damped
copies passed the recorded 1e-8 relative comparison. The largest relative
block discrepancy was 4.083e-9; paired fields differed from independent Mie
predictions by at most 2.896e-10. The largest errors were at contrast 13.3,
2.5 GHz, damped. Small complex Bessel products involve cancellation there.

The maintained A2 already uses Maue and the index-reversed K transpose.
Comparing its assembled blocks with independent circle Bessel expressions
checks signs and normalization in this special case. This does not newly
validate extended-band Maue products on arbitrary noncircular curves.

The uniform-radius derivative of the single-layer spectrum, equation (60)
of the original proposal, matches centred differences to 3.365e-9 relative
error. Nonuniform near-circle directions and actual refit derivatives were
not tested here.

The existing Mie paired-field path took 3.66–4.83 ms per call, versus
40.8–88.2 ms for the modal forward calls. These are single observations,
with modal geometry reused within each contrast, on CPU under parallel
load. They support using the already-implemented exact disk special case
when the boundary is a disk; they do not establish whole-fit savings.
M=1 normal updates do not generally preserve a disk.

## Item 11 — circular ItI transport

Integrated modes 0–16 through radii 0.9–1.1 times the first real J0 pole.
The benchmark uses a 50 mm length unit; the pole radius is 5.138 mm.
The normal benchmark start is 65 mm. This smaller-radius calculation is
an analytic component test, not a new inverse start or benchmark run.

| Copy | ODE tolerance | Maximum response error | RHS calls |
|---|---:|---:|---:|
| Real | 1e-7 | 2.227e-7 | 59 |
| Real | 1e-10 | 2.675e-10 | 104 |
| Damped | 1e-7 | 1.515e-6 | 131 |
| Damped | 1e-10 | 1.197e-9 | 251 |

The direct ratio evaluates ItI without forming a divergent DtN. At the real
pole its mode-zero value differs from one by 1.65e-16. The exact lossless
unitarity defect is 1.34e-15; the damped defect is 60.35 with the proposal's
g-minus/g-plus convention and eta=1. Damped unitarity is therefore false,
not a numerical integration error. No claim of damped contractivity follows.

General-curve mode closure, tangential transport, exterior coupling and
cost remain untested. Keep this branch experimental. Its circular identity
and pole-removal claim pass; its proposed inverse acceleration remains open.

## Evidence and reproduction

Original proposal: sections 7 and 20–22; review: items 1, 10 and 11.
No literature novelty claim is made by these numerical tests.

[Driver](../../../../experiments/haibing_circle/study.py),
[numbers](../../../../results/validation/cleaned_interfaces/HB-004-circle/summary.json),
[run output](../../../../results/validation/cleaned_interfaces/HB-004-circle/run.log).

Command: `env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1 taskset -c 12-15 /home/drdeng/miniconda3/envs/EMNerf/bin/python
-u -m experiments.haibing_circle.study`.
