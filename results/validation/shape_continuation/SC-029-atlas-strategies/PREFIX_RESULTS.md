# First milestone — all twelve four-stage paths complete

All six fresh baseline endpoints are **bitwise identical** to SC-025's
ladder, with identical work units. The wrong-circle detailed replay also
matches accepted history and stopping reasons. All twelve paths complete
normally. The [machine-readable prefix summary](prefix_summary.json)
records scores, work, mechanism measures and the frozen decision gate.

| Case | Original M=3 first stage, RMS mm | M=2 first stage, RMS mm |
|---|---:|---:|
| Circle | 0.002594 | 0.001382 |
| Star | 0.522234 | 0.543738 |
| C | 3.201993 | 0.353737 |
| Kite | 2.982577 | 5.536634 |
| Peanut | 2.944275 | 0.129188 |
| Hook | 0.525391 | 4.994014 |

**S1 does not qualify as a general policy.** It improves C and peanut
substantially but worsens kite by 1.86x and hook by 9.51x, exceeding the
predeclared 1.5x worst-case guardrail. These are meaningful case-specific
gains alongside a clear robustness failure; neither should be hidden by
the average.

The mechanism is not universal either. On peanut, M=2 keeps the tightest
radius above 18.37 mm and has no projection refusals, versus a 1.27-mm
radius and 531 refusals for the baseline. On hook it does the opposite:
radius 1.73 versus 7.88 mm, and 495 versus 2 refusals. Both settings keep
large first-stage steps. A smaller initial band is not itself a regularity
guarantee.

The frozen next phase tests both completed paths with (a) additional
optimization on the same four frequencies and (b) continuation to 2.5 GHz.
Those outcomes are not yet available at this checkpoint. No parameters or
case selections changed after seeing the first-stage results.
