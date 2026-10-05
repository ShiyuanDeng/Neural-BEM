# ON-002 interrupted launch record

The original user-authorized run started at 2026-10-05 01:39:26 UTC and was
interrupted at 01:48:40 UTC. Status: **INTERRUPTED, adapter-unqualified**.
The unchanged source and receipts were preserved in `7d50e3f8`.

The completed 128-pixel / 112-centre batch tested all three contrasts at the
lowest and highest real and damped frequencies. **0/12** systems reached the
required 1e-6 true residual in 200 BiCGSTAB iterations; residuals ranged from
0.910115 to 1.000000. All 12 field checks failed and derivatives were
refused because forward systems did not converge. The original batch took
10.256 seconds and verified unchanged source hashes.

These are adapter-failure receipts, not a qualified physical comparison. No
inverse screen, hybrid, 30-case comparison or timing ratio was released.
The original receipt and native arrays stay in
`results/validation/cleaned_interfaces/ON-002/adapter128/`.

The user requested `go on ON-002` on 2026-10-05. Resumption remains ON-002;
it does not launch the separately proposed GP-001. Its new receipt and
bounded repair decision will be recorded separately before numerical work.
