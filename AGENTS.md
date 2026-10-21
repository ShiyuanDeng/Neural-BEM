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
  Do not validate documentation when asked to `cp`: no documentation tests,
  linting, link checks, or separate review pass. Write documentation carefully
  when creating or editing it instead.
- After each new experiment run, automatically commit and push its code,
  documentation, and results to the current branch's configured remote,
  including failed-run evidence. No separate `cp` request or confirmation is
  needed; apply the minimum relevant code/result validation below, then verify
  the push and final working-tree status.
- When asked to make the working tree clean, preserve the work by committing
  it. Do not discard changes to achieve a clean status.
- Before committing code or experimental results, use only the minimum
  relevant validation. Reuse checks already completed for the unchanged code;
  a `cp` request is not a reason to rerun them. Documentation does not require
  validation. Verify the push and final working-tree status.

# Terminal answers

- These rules apply to every agent, including agents assigned part of a task,
  and to both progress updates and final answers.
- Keep every paragraph to at most three terminal lines. Use short sentences
  and split longer explanations into separate paragraphs or short bullets.
- Use plain, direct language. Do not use words such as "audit", "gate", or
  "pilot", or similar fancy process language. Describe what happens in ordinary
  words; use necessary technical terms only when they help explain the work.
- For code questions, especially "where" questions, answer in at most three
  lines. Keep explanations as short as possible and never exceed one page.
  Explain roles intuitively in words; avoid equations and raw LaTeX in replies.
- For inverse-solver explanations, use the user's A1–C12 information chain and
  fixed terminology in [the canonical code map](docs/reference/inverse_information_chain.md).
  Place the requested function in that chain and link its actual implementation.
  Read the relevant section and code before explaining; distinguish the default
  pipeline from optional research variants.

# Implementation plans, test scope, and runtime

- Start every implementation plan with one or a few explicit questions the
  work aims to answer. Tie the proposed work and experiments to those questions.
- Unless the user explicitly asks for rigorous implementation/validation,
  keep test numbers to a minimum. Omit tests unrelated to the stated aims;
  do not add tests merely to make a plan appear comprehensive.
- For long tasks, runtime is the first priority. Choose the shortest practical
  route that answers the questions, reuse existing evidence, and avoid
  unnecessary setup, repeated runs, and extra computation for recording.
- Use the established working pipeline and its existing checks. Do not add
  extra tests or repeat checks of working components unless a relevant change
  or observed failure requires it. Preserve the agreed experiment scope and
  run count.
- Record the necessary evidence during the requested runs and analyze saved
  results where possible. If those results cannot answer a question, report
  the limitation; an unresolved answer does not authorize extra experiments.

# Which experiments to run

- New inverse experiments use only the TG-002 benchmark in `experiments/benchmark/`
  (10 scenes x contrasts 0.5/4/13.3, one centred start, no grid search). Read its
  `README.md` first. Default method: `modal_muller` + `spectral` (sampled checks, batched preparation),
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
