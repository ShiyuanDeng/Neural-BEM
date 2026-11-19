# Workspace

- Ask the user before creating any Git branch or worktree, even in
  full-access mode. Approving a task or experiment does not cover it.
- Codex and Claude may share this checkout at once. Check `git status` first
  and stage only your own files, by path.
- `/home/drdeng/Neural_SDF_BEM_AD` is the legacy workspace: removed docs,
  results and retired scene sets. Use it for history only.

# Commits

- `cp` (or `cp?`) means commit and push to the current branch's remote.
  Do it without asking again.
- After each experiment run, commit and push its code, docs and results,
  failed runs included.
- A clean tree means everything committed, never discarded.
- Before committing, run only the minimum relevant checks and reuse earlier
  ones; docs need none. Then confirm the push and `git status`.

# Terminal answers

For every agent, in progress updates and final answers:

- At most three terminal lines per paragraph. Short sentences, plain words:
  "check", "test run", "limit" rather than "audit", "gate", "pilot".
- Code and "where" questions: at most three lines. Explain roles in words,
  without equations or LaTeX.
- Inverse-solver explanations: place the function in the A1–C12 chain of
  `docs/reference/inverse_information_chain.md`, in its terms. Read that
  section and the code first, link the code, and say if it is on the
  default path.
- Present a named agent's findings in its required format.

# Experiments

- Use only the TG-002 benchmark (`experiments/benchmark/README.md`): one
  centred start, no grid search.
- Default method: `modal_muller` + `slider`, real data only, recovered
  contrast, band-1 warm-up on the lowest frequency, localization `none`.
- Runtime first: reuse saved evidence and keep tests to what the question
  needs. Validate rigorously only when asked.

# Iterations

When asked to start or continue an iteration, record it in `docs/iterations/`:

```text
docs/iterations/
  evaluate_our_method/                     investigation
    01_measure_clean_and_noisy_recovery/   activity
      plan.md
      results.md
      figures/
```

- Name both folder levels with verbs describing the work. Number activities
  within each investigation; keep names and numbers stable. Refer to runs by
  date and purpose, not letter codes.
- Before running, write `plan.md`: the questions, settings, comparisons,
  success criteria, run budget, commands, output locations, and which
  choices the user made.
- After running, write `results.md`: run dates, actual settings,
  measurements, failures, conclusions and links to evidence. Raw outputs
  stay in `results/`; report figures go in `figures/`.
- Changing course: if the activity has `results.md`, start the next numbered
  activity. If not, edit its `plan.md`.
- The investigation the user starts covers its follow-up activities: open
  them without asking. Ask before leaving its topic or exceeding the user's
  limits. Stop once the question is answered.

# Code and evidence

- `solvers/bem_inverse/` is the maintained inverse (see its README). It must
  not import `experiments/`, root `run_*.py`, `results/` or
  `development_results/`; truth-based scoring belongs in `experiments/`.
- `results/` holds runs from 17 November 2026 on; `development_results/`
  holds kept development evidence.
- Keep reference solvers, frozen inputs, source snapshots and failed runs.
  Dated plans are history; they do not choose the current code.

# Cleanup

Read `docs/cleanup/user_decisions.md` before proposing cleanup, and record
each new user decision there with the user's words and the rule it implies.
Keep each cleanup's plan and status in `docs/cleanup/`.
