# Development results

These are development inputs, comparisons and numerical checks, not final results
for the revised baseline study. New runs belong in `results/`, which was emptied on
2026-11-17. The sealed TG-002 inputs remain the benchmark for new runs.

| Component | Why it was run | What is retained |
|---|---|---|
| [TG-002](TG-002/README.md) | Define the fixed 30-case benchmark and accurate observations | Complete sealed inputs, qualifications, source snapshot and scene gallery |
| MR-001 | Compare supplied and recovered contrast | The 60 selected BEM endpoints, settings and final checks; reported diagnostic failures and timeout evidence |
| GGB-002 | Compare GauGal with BEM on TG-002 | All 30 final images and result records, tuning choices, timing and execution records |
| FW-001 | Measure MoM/GauGal forward error against the reference | Existing field-error records and logs; this was an incomplete forward study |
| [GU-001](GU-001/README.md), [GU-002](GU-002/README.md) | Compare curve updates and CPU/CUDA slider preparation | Summary tables, timing and agreement records |
| [PC-001](PC-001/README.md), [PC-002](PC-002/README.md) | Compare modal and nodal BEM and investigate nodal cost | Summary tables and links to the full historical runs |
| [NR-001](NR-001/README.md) | Measure removal of finer re-evaluations | Summary, settings and comparison records |
| Numerical and policy checks | Explain earlier implementation choices | Compact evidence cited by [docs/evidence.md](../docs/evidence.md) |
| [GauGal native scenes](GauGal-native/README.md) | Preserve the original seconds-per-scene timing context | Compact table and a link to the original GGB-001 evidence |

The [current comparison report](../docs/iterations/gaugal_comparison/iteration_01/report.md)
and its CSV/JSON stay under `docs/`. Their source links now point here. The
[revised Stage 1 actions](../docs/iterations/gaugal_comparison/iteration_01/02_proposals/01_stage_one_actions_verified.md)
define the next study; no new comparison runs were made for this reorganisation.

## Complete historical runs

The complete old `results/` tree is preserved at commit
`af68817f7917cfa927355862dad4e3929c098321`. The [archive index](archive_index.json) lists every original
file, its Git blob, and its retained path where applicable.

Open the [full archived results](https://github.com/ShiyuanDeng/Neural-BEM/tree/af68817f7917cfa927355862dad4e3929c098321/results).
To retrieve a file without repopulating the new `results/` directory:

```bash
git show af68817f7917cfa927355862dad4e3929c098321:results/path/to/file > /tmp/saved-result
```

Earlier legacy runs also remain in `/home/drdeng/Neural_SDF_BEM_AD` at commit
`5cc25845e51b5cec4e16b4e1b3602555a023b832`. Its experiment names are not interchangeable: that branch's
GGB-002 is a different experiment.

Raw records retain their original embedded paths and settings as provenance.
Some old campaign scripts require their full run tree to be restored before use.
For new benchmark runs, give the benchmark CLI a fresh `--run-dir` under `results/`.

Git does not store empty directories. `results/` exists locally and is empty;
the benchmark creates a requested run directory when needed after a fresh checkout.
