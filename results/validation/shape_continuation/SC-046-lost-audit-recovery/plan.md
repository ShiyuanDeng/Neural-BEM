# SC-046 — recover one lost audit result

2026-09-26. One additional qualification, with no fitting or changed tolerance.
SC-045's first audit called the numerical routine, then its output write
failed because audits/ did not exist. Neither its numerical result nor ledger
survived. SC-045/audits/1.json retains that execution failure, with up to 130
unrecorded work units. No numerical pass or failure is inferred from it.

Create and check the output directory before this separate attempt. Freeze
all inherited sources and original inputs, the execution-failure record,
this plan and this runner before calling a PDE solver. Wait for SC-045's
remaining four serial audits. Then perform exactly one audit of the original
SC-042 kite/boundary endpoint, using the original final stage and config,
the unchanged c.audit implementation, 42001 FD seed, 1e-7 m FD step,
130-unit cap and 900-second ceiling. No refit, new resolution or tolerance
relaxation. Print the portable numerical result to the captured log before
writing the result file, so a later file-write failure does not lose both.

Maximum new work: 130 units, additional to SC-045 and its unrecorded first
attempt. Original SC-042 and SC-045 failure flags remain unchanged. This
one-time recovery supplies separate evidence, never retroactive success of
the original runs. No further retry is part of this contract.

SC-043 waits for this record, then starts its unchanged frozen policies.
Its scheduling allows only one kite path at a time after observing more
than 17 GiB resident memory in the serial audit; up to six PDE workers total
remain permitted with lower-resolution cases and SC-044.
