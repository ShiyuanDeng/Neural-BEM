# Central circle → ellipse + star: saved-state video

[Watch the 53-second MP4](central_circle_to_ellipse_star.mp4) · [Final comparison frame](final_frame.png) · [Source/state manifest](video_manifest.json) · [Exact timeline](timeline.json)

The central reconstruction now succeeds in the resumed fixed-topology experiment: final F boundary error **0.0623345 mm**, IoU **0.999426**, worst evaluation error **0.00123772**, with all original gates passed. The matched S control ends at 6.12516 mm and fails the shape/prediction gates.

This does **not** establish that a fresh automatic run from the central circle is now fully fixed. TOP-017 started from two components already found by the historical topology run. The video joins actual saved histories with explicit run boundaries; it is not a fresh end-to-end rerun or a claim of general pipeline reliability.

| Time | Evidence shown |
|---|---|
| 0–15 s | Archived TOP-008 H: original central circle, automatic split/birth/merge, retained two-object endpoint |
| 15–24 s | Archived common TOP-016 stage 1; geometry-preserving zero-padding and low-frequency refinement |
| 24–46 s | TOP-017 S/F comparison through the three predetermined stages; fixed two-component topology |
| 46–53 s | Final stage-4 coefficients and their saved scores; F passes all original gates |

Dashed black curves are analytic targets. Orange is S, blue is F. Every reconstruction shown is sampled directly from an archived state; no intermediate coefficients were interpolated. Stage playback is aligned for viewing, not matched in iterations, solves or wall time. Endpoint scores appear only with their matching saved endpoint states. Final stage 4 is shown even though stage 3 had slightly smaller boundary/evaluation errors.

Rendering used **zero new forward or inverse solves**. All 148 saved state records match the repository's boundary sampler to at most 2.22e-16 m. The historical TOP-008 and TOP-016 seams were checked, including exact physical zero-padding and coefficient-identical TOP-017 paired starts. All media source hashes and the 146 sealed TOP-017 artifacts remained unchanged.

The H.264 MP4 was decoded fully without errors and checked at 1280×800, 15 fps, 795 frames, 53 seconds. The initial and decoded final frames were visually inspected. [Validation record](validation.json).

Rebuild from the experiment worktree (reads coefficients/JSON only):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/topology/TOP-017-20260914-central-video/render_video.py
```

[TOP-017 numerical closeout](../TOP-017-20260914-staged-continuation/README.md). No numerical result, optimizer, configuration or promotion decision changed to create this video.
