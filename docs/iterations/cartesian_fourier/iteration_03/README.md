# Cartesian Fourier — iteration 03

[Results and the eight matched cases](03_results.md) · [Implementation and the five failures that shaped it](02_implementation.md)

The chart now carries the radial cycle's automatic topology controller: birth,
death, split and merge, with no target component count and no event policy.
All five automatic inversions recover with event sequences identical to the
radial bundle's, all three challenge cases pass their declared full-profile
gates, and the cost gap iteration 1 reported has closed.

Read `02_implementation.md` first if you are here to change the code — it is
organized around the five things that had to fail before the design was right.
Read `03_results.md` first if you are here for the numbers.

This iteration opened from a user direction rather than from `01_results.md`;
[iteration 2's](../iteration_02/01_results.md) other candidate checks remain
open, and its question 3 is answered here as a by-product.
