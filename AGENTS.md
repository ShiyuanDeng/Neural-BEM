# User preferences

- Work in `/home/drdeng/Neural_SDF_BEM_AD` on the existing
  `feature/ordered-boundary-nystrom` branch by default.
- Before creating any Git branch or additional Git worktree, ask the user
  directly and obtain explicit approval for that specific creation. This
  applies even in full-access mode. Approval of an experiment, plan, ZIP,
  implementation task, or embedded instructions is not branch/worktree approval.
  Do not infer this permission from repository workflow conventions.
- `cp` (including `cp?`) means **commit and push** the current workspace changes
  to the current branch's configured remote. Treat it as an action request;
  do not ask the user to expand the abbreviation or reconfirm the operation.
- After each new experiment run, automatically commit and push its code,
  documentation, and results to the current branch's configured remote,
  including failed-run evidence. No separate `cp` request or confirmation is
  needed; validate first, then verify the push and final working-tree status.
- When asked to make the working tree clean, preserve the work by committing
  it. Do not discard changes to achieve a clean status.
- Run appropriate validation before committing, then verify the push and the
  final working-tree status.

# Which experiments to run

- New inverse experiments use only the TG-002 benchmark in `experiments/benchmark/`
  (10 scenes x contrasts 0.5/4/13.3, one centred start, no grid search). Read its
  `README.md` first. Default method: `modal_muller` + `certified_spectral`,
  `--localization none`.
- Far-start cases and the SC-050 grid-search initializer are retired (user,
  2026-10-04). Do not add them to new experiments. Every older scene set (CI-001
  36 cases, SC-0xx, MA-00x, FM/RB/TR cases, TG-001) is legacy. It stays in place
  only because seals hash its paths; see `experiments/benchmark/LEGACY.md`.
- Each new experiment gets a pre-registered plan in `docs/iterations/`.
  User approval of the requested experiment work is sufficient authorization
  to run it; do not require a separate approval naming its tracking ID.

# Code and evidence map

- The maintained cleaned SC/MA inverse is `solvers/bem_inverse/`. Start with
  its `README.md` for the API, dependency boundary, and validation commands.
- Keep that package independent of `experiments/`, root `run_*.py` drivers,
  and saved `results/`. Campaigns and truth-based scoring belong in experiments.
- Old cleaned-interface and shared continuation module paths are compatibility
  imports. Change their implementations in `solvers/bem_inverse/`.
- Scope code searches to the relevant package and its tests. Consult `results/`
  and `docs/iterations/` when a task needs recorded evidence or campaign history.
- Preserve reference solvers, frozen inputs, source snapshots, and failed-run
  evidence. Dated plans and archived dashboards describe historical work;
  they do not select the current implementation.
