# TA-001 continuation answer

**Question 1:** The saved-step benefit does not produce a recovering
trajectory in any of the four fresh default-policy TG-002 fits.
Recovery stays at 0/4, as in NR-001.

**Question 2:** All four stop on modal numerical refusals. Chart RMS errors
are 7.874, 5.940, 5.975 and 6.193 mm. NR-001's were 3.953, 5.266, 4.283 and
8.281 mm. Hook improves RMS but fails the final numerical check.

The failed chart candidates all have off-diagonal divided-difference
minima, with minimum speed / mean from 0.231 to 0.726. Their distant gaps
are 0.118, 0.245, 1.127 and 6.799 mm. Positive speed does not control these
nonlocal approaches or guarantee a successful coefficient certificate.

Keep the chart experimental. A future design should address nonlocal
separation and the hook's visible high-frequency geometry. No further
fit or maintained-solver change was made.

[Numbers, figures, settings, failures and limitations](../../../../results/validation/cleaned_interfaces/TA-001/continuation/README.md).
