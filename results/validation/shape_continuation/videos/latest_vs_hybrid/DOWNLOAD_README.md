# Latest six scenes versus original hybrid

Selected policy: SC-043 fixed release with initial cleanup.

Each video shows the original hybrid above and the selected latest trajectory
below, with boundary visualisation, residual heatmap and shape harmonics.
All videos are 1800 x 1100 H.264, 12 fps, 498 frames (41.5 seconds).
Every saved state is included; geometry is not interpolated.

| Scene | Video | Final frame | Original RMS (mm) | Latest RMS (mm) |
|---|---|---|---:|---:|
| Circle | [1_circle.mp4](1_circle.mp4) | [PNG](frames/1_circle_final.png) | 0.0025943298 | 0.00024467411 |
| Star | [2_star.mp4](2_star.mp4) | [PNG](frames/2_star_final.png) | 0.52223398 | 0.011028463 |
| C | [3_c.mp4](3_c.mp4) | [PNG](frames/3_c_final.png) | 3.2019928 | 0.0040928956 |
| Kite | [4_kite.mp4](4_kite.mp4) | [PNG](frames/4_kite_final.png) | 2.9825765 | 0.034605879 |
| Peanut | [5_peanut.mp4](5_peanut.mp4) | [PNG](frames/5_peanut_final.png) | 2.9442745 | 0.0024277975 |
| Hook | [6_hook.mp4](6_hook.mp4) | [PNG](frames/6_hook_final.png) | 0.52539076 | 0.0020533132 |

The latest history includes the declared SC-040 prefix, the recorded SC-041
star/kite continuation, and the explicit SC-043 cleanup and fixed releases.
Original hybrid is the SC-029 baseline. The original holds its endpoint
through the later continuation stages. Playback time does not measure solve
time: the latest paths use more frequencies, stages and work. This is a
full-history visual comparison, not a matched-cost benchmark.

The dashed boundary and spectrum show the target for evaluation. Heatmaps
use the established capped QR residual score in ideal normal ripples. They
are descriptive scores, not predicted achieved loss reductions. The white
line is an assumed 0.01% sensitivity display threshold, not a recovery limit.
The Cartesian harmonic strip is parameter dependent on general curves.
The displayed band extends through order 48; upper bars cover orders 49-192.

All 743 verification checks passed, including complete state coverage,
source hashes, final endpoints and error-free decoding of each video. Final
RMS values match the recorded results exactly. Maximum heatmap change under
doubled sampling was 0.00253 dex, with no frontier changes. No inverse fitting
was performed to make these videos.

This viewing bundle contains six videos, six final-frame previews,
manifest.json, verification.json, and this README. The repository retains
render.py, verify.py, portable prepared records, and full preparation receipts.
The manifest includes original repository paths for provenance; those input
files are not required to play the videos.
