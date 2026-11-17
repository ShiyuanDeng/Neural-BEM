# Shipped example I: failed on MATLAB R2026a

Run 17 November 2026, 19:23:22 UTC; 8.286 s wall time, eight MATLAB threads.
The unmodified driver completed input construction, then `show_InitGuess.m`
called `plottools('on')`, removed in R2026a. No inversion iteration ran.
See `failure.txt`, `matlab.log`, `launch.json` and the identical driver copies.

Next: remove only that obsolete display-tool call, save its upstream patch,
and repeat in a distinct directory. No algorithm, input or setting changes.
