# Stage A xi/k_star=1

Exact outgoing circle moments, complete near quadrature, complex128/float64.
The far radial quadrature 256/512 agrees to max 3.62e-15 in multiplier units.
Independent flat symbol error is <=4.53e-17. The complete-near refinement
absolute max is 2.36e-8 over V/K/T; its single-layer curvature correction
improves the relative operator-scale error from 2.25e-5 to <=4.06e-9.

| Grid | Trace cutoff | Worst V error / scale | Worst K error / scale | Worst T error / scale |
|---|---:|---:|---:|---:|
|128|64|1.66e-3|9.66e-3|4.81e-1|
|128|128|2.53e-3|9.66e-3|8.94e-1|
|256|64|6.42e-6|8.94e-4|1.54e-2|
|256|128|6.42e-6|8.94e-4|4.32e-2|

These are necessary diagonal screens, not full block-action or field passes.
The refined grid still fails the predeclared 1e-7 circle operator-scale
control. T's worst refined mode is -128, contrast 0.5, 0.25 GHz real.
The exact-near control removes a local-model approximation as the explanation;
radial quadrature is resolved. Continue only the other three declared split
scales; no larger grid or shifted pole is authorized.

Total process: 19.92 s, single-thread CPU. This measures controls, not the
complete 24-pair forward service, and is not a speed comparison.
