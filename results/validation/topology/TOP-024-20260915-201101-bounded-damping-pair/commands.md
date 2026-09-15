# TOP-024 execution commands

Working directory: `/home/drdeng/Neural_SDF_BEM_AD`.
Python: `/home/drdeng/miniconda3/envs/EMNerf/bin/python`.
`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, and `MKL_NUM_THREADS` were each `1`.

1. Source-bound tests: command and test/log/source hashes are in
   `pre_dispatch_validation.json`; stdout is in `pre_dispatch_tests.log`.
   Final result: 98 passed. Before that freeze, two test failures exposed an
   ndarray/dictionary equality error in the new configuration guard; it was
   corrected using canonical serialization before any numerical work.
2. Preparation ran `experiments.top024.run.prepare(output,
   Path("experiments/top024/validation.json").resolve())` in the stated Python,
   where `output` is this fresh directory. It returned `PREPARED` and zero new
   physical solves. Both arm configurations and the initial state were frozen.
3. Numerical pair:

   ```sh
   OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top024/dispatch.py --output results/validation/topology/TOP-024-20260915-201101-bounded-damping-pair
   ```

   Exact child commands, exit codes and timings are in `campaign.json`.
   Complete child stdout/stderr are in `A.log` and `B.log`.

The reporter `experiments/top024/summarize.py --output <this-directory>`
replays saved arrays and counters with zero new BIE solves.
