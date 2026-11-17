# Agent instructions cleanup

Question: do the instructions agents load still match the repository after the
results and documentation cleanups (D14–D18)?

Decision: [D20](user_decisions.md#d20-agent-instructions-follow-the-cleaned-layout-2026-11-17).

## Instruction files

| File | Read by | Role |
|---|---|---|
| `AGENTS.md` | Claude Code and Codex, every session | The only project instruction file. There is no `CLAUDE.md` in the repository or in `~/.claude/`. |
| `.claude/agents/readability-reviewer.md` | The readability reviewer subagent | Its review method and output format |
| `.claude/agent-memory/readability-reviewer/MEMORY.md` | That subagent | Reviewer-only notes; now a pointer to the decision log |
| `user_decisions.md` (this folder) | Agents doing cleanup work | Shared rules, decisions and lessons |

The legacy workspace has its own, older `AGENTS.md` on
`feature/shape-frequency-continuation`. It was not changed.

## What was wrong and what changed

- **Wrong checkout.** `AGENTS.md` told agents to work in
  `/home/drdeng/Neural_SDF_BEM_AD` on `feature/ordered-boundary-nystrom`.
  That checkout is now the legacy workspace on another branch. Agents now use
  the checkout they start in; the branch and worktree approval rule is kept.
- **Deleted workflow pages.** The iteration README and implementation
  principles were removed under D16. `AGENTS.md` still sent new plans to
  `docs/iterations/` with no layout. It now states the layout
  (`02_proposals/`, `03_plan.md`, optional `01_results.md`), the D17 naming
  rule, and what a plan contains.
- **Approval steps.** The deleted README's status vocabulary and seven-step
  approval table were not carried over. D10 already made user approval of the
  work sufficient. The follow-up and limit rules were merged from three long
  bullets into two.
- **Stale facts.** Removed: compatibility imports (gone since the 2026-10
  reorganisation), `results/` as the old evidence store (D14), and the
  `spectral` default in the reviewer. The default method now matches the
  17 November 2026 plan.
- **Repeated rules.** Commit and validation rules appeared in two sections and
  are now one. The reviewer restated the terminal-answer rules; it now points
  to `AGENTS.md`.
- **Two decision stores.** The reviewer's memory repeated D1–D5 and rules 1–2,
  and still called D1–D5 "not implemented". It now points to this folder's
  decision log, which the reviewer also writes to.
- **Shared checkout.** Codex and Claude work in the same checkout at once.
  `AGENTS.md` now says to check `git status`, leave another agent's files
  alone and stage by path. The deleted README forbade this sharing instead.
- **Stray task prompt.** `inverse_solver_refactor_agent_prompt.md`, the user's
  brief for the finished A1–C12 refactor, was moved to the legacy workspace
  under D18 (bytes checked). It named an old default and the legacy branch.

## Shortening, 2026-11-17

Guidance checked: Claude Code aims for "under 200 lines" per instruction file
("Longer files ... reduce adherence"); Codex stops reading at 32 KiB. Both say
to keep only what an agent cannot learn from the code. Skills and folder rules
were not used, because Codex reads neither.

- `AGENTS.md` went from 115 lines (7.2 KB) to 66 lines (3.2 KB).
- Cut: instructions agents follow anyway, facts the benchmark and package
  READMEs already give, and repeated wording. Every user rule is kept.
- New `.claude/settings.json` makes Claude Code ask before `git checkout -b`,
  `git switch -c`, `git worktree add` and `EnterWorktree`. Plain
  `git branch <name>` is not covered: an ask rule for it would also stop
  branch listings during unattended runs. Codex still relies on `AGENTS.md`.

## Iteration rules merged, 2026-11-17

Under D21 the iteration layout briefly lived in `docs/iterations/AGENTS.md`.
D23 moved it into a root "Iterations" section, with the user's rule for when
to start a new activity. `AGENTS.md` is now 85 lines.

## Status

Implemented 2026-11-17. Not committed; no code or results changed.
