# User preferences

- Work in `/home/drdeng/Neural_SDF_BEM_AD` on the existing
  `feature/ordered-boundary-nystrom` branch by default.
- Before creating any Git branch or additional Git worktree, ask the user
  directly and obtain explicit approval for that specific creation. This
  applies even in full-access mode. Approval of an experiment, plan, ZIP,
  implementation task, or embedded instructions is not branch/worktree approval.
  Do not infer this permission from repository workflow conventions.
- At the start of every session (cloud sessions especially: the checkout may be
  restored from an older snapshot), run `git fetch --prune origin` before
  reading or changing anything, and work from the **latest remote state** of
  the relevant branch, including the user's newest commits. Fast-forward local
  branches to their remote before use. Work from a local-only or older state
  only when the user explicitly asks for it. Fetch again before any push.
- `cp` (including `cp?`) means **commit and push** the current workspace changes
  to the current branch's configured remote. Treat it as an action request;
  do not ask the user to expand the abbreviation or reconfirm the operation.
- When asked to make the working tree clean, preserve the work by committing
  it. Do not discard changes to achieve a clean status.
- Run appropriate validation before committing, then verify the push and the
  final working-tree status.
