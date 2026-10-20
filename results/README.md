# Results

Only the evidence the current pipeline needs is kept on this branch:

- `validation/cleaned_interfaces/TG-002/`: the sealed TG-002 inputs (truths, start,
  real and damped catalogs, source snapshot). Check them with
  `python -m experiments.benchmark verify`.
- `validation/cleaned_interfaces/PC-001/M1/`: the default `modal_fixed` method on all 30
  cases, 26 recovered. Use it as the reference when checking the rewrite.

All other recorded results remain on `feature/shape-frequency-continuation`. Put new run
directories under `validation/cleaned_interfaces/<ID>/`.
