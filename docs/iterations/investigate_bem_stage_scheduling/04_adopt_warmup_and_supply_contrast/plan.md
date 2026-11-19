# Adopt the warm-up as the default; supply the contrast at 13.3

19 November 2026, 13:46 UTC. Coordinator: Claude, Herdr pane `w4:p1`. Follows the [joint results](../03_compare_schedule_effects/results.md).

## The user's words

In this pane, after reading the joint results: "yes default with warm up. also have you tested to supply material contrast in the 10 c13.3 cases".

- **First sentence:** a decision. It answers point 1 of the joint results: the band-1 warm-up at the lowest frequency becomes part of the default method.
- **Second sentence:** a question. The answer is no. The saved known-contrast run (`bem/default_clean_kc_fc`, 17 November, default without warm-up) covers contrasts 0.5 and 4 only: 9/10 and 2/10 recovered.
- **Coordinator's choice:** run the test now. It is ten fits, inside this investigation's topic, and it is the matched test that the eight unexplained 13.3 misses lack.

## Part 1: the default

**Question.** Does the default, with the warm-up built into the solver's schedule, repeat last night's warm-up fits?

**Change, in the solver.** [`RealOnlyPolicy`](../../../../solvers/bem_inverse/real_only_policy.py) gains `warmup` (on by default). In the `continuation` schedule one stage runs before the ladder: the lowest real frequency of the catalog alone, update band 1, storage band 4, 600 work units, 44 steps. These are the numbers tested last night and those of the older damped warm-up. The whole-fit limits stay 13,412 units and 120 s.

**Place in the chain.** A policy change only: it adds one stage to the list that C12 walks through. A1 to C11 are untouched. The stage's update coordinates (B6) are the slider's `a0, a1, b1`, which on a circle are radius and the two shifts.

**What is general about it.** The rule names no dataset and no frequency: the lowest frequency of whatever catalog is given.

**What is left unchanged, by the coordinator's choice.**

- The `simultaneous` and `single` schedules get no warm-up. Neither was tested with one.
- With `fixed_band` the warm-up stage is kept at the fixed band, so that variant still differs from the default by the band only.
- The wrappers for other groups' data, `CsiPolicy` and `B1Policy`, set `warmup=False`. Their saved fits had none. On the measured cylinder a warm-up on the lowest frequency alone gave 95% against 68%. Whether they follow the default is the user's call (point 2 of the joint results).
- Last night's experiment schedules set `warmup=False`, so each still rebuilds its saved fit. They add their own warm-up where they need one.

**Checks.**

1. `pytest pytest/bem_inverse/test_real_only.py`: the default's stage list is the old one with the warm-up in front; `warmup=False` is the old one.
2. Two fits through the default policy, `kite__c4` and `circle__c13.3`, compared with the saved warm-up fits. Pass: same stage count, bands and accepted steps in every stage, and outlines equal to 1e-9 relative.

**Not done here.** The saved tables under `results/bem/default_*` come from the default without warm-up and stay as dated evidence. Last night's warm-up fits stand in for the new default: 20/30 clean, 20/30 on noise draw 0. Running the named default runs again is the user's call.

## Part 2: supplied contrast at 13.3

**Question.** With the true contrast supplied and held, do the ten contrast-13.3 cases recover under the new default?

**Why it matters.** Nine of ten miss with recovered contrast. In six the contrast estimate starts below the background and goes to zero; in three it starts on the right side and the warm-up stalls. Supplying the contrast removes the size–material valley and leaves place, size and shape. If the cases then recover, contrast recovery is the cause. If they do not, the shape path at high contrast is.

**Matched pair.** Reference: last night's warm-up fits, recovered contrast (`clean_tg002/warmup`). One change: contrast 13.3 supplied and not fitted, exactly as a `kc` run does it (`material=None`). Everything else is the default: sealed clean real data, the centred 65 mm start, `modal_muller`, `slider`, no localization, 13,412 units, 120 s nominal wall.

**Success.** A case is recovered at area error of 5% or less. The count out of ten is the answer; no threshold on the count is set in advance.

**Budget.** Ten fits, one at a time, alone on the GPU. Each is limited by the 120 s nominal wall, which is checked when a trial returns; one fit last night ran 586 s. No fit is stopped for time.

## Commands and outputs

```bash
cd /home/drdeng/Neural_SDF_BEM_AD_organised
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$P -m pytest pytest/bem_inverse/test_real_only.py -q
$P -m experiments.comparison.compare_clean_default_contrasts recovered kite__c4
$P -m experiments.comparison.compare_clean_default_contrasts recovered circle__c13.3
for shape in circle kite peanut star asymmetric c_shape hook cross cog aphex_twin; do
  $P -m experiments.comparison.compare_clean_default_contrasts known ${shape}__c13.3
done
```

The ten `known` fits run from a detached launcher, `results/bem/stage_scheduling/2026-11-19/clean_tg002/logs/batch_10_known_contrast.sh`, with a state file beside it. Do not relaunch it while that file exists.

Outputs: `results/bem/stage_scheduling/2026-11-19/clean_tg002/default_recovered/` and `.../default_known/`, one JSON per case. Driver: [`compare_clean_default_contrasts.py`](../../../../experiments/comparison/compare_clean_default_contrasts.py).
