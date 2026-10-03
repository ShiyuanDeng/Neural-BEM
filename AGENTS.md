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
- When asked to make the working tree clean, preserve the work by committing
  it. Do not discard changes to achieve a clean status.
- Run appropriate validation before committing, then verify the push and the
  final working-tree status.

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
