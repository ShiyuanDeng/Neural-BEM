"""Build the SPD-014 closeout from completed saved evidence, without field solves."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT/'results/validation/speedup/SPD-014-20260927-geometry'
CASES = ('wrong_circle','circle_to_star','circle_to_c','kite','peanut','hook')
NAMES = dict(zip(CASES, ('Circle','Star','C','Kite','Peanut','Hook')))


def read(path):
    return json.loads(Path(path).read_text())


geometry, batches, inverse, video = [read(BUNDLE/name/'result.json')
                                     for name in ('geometry','batches','inverse','video')]
assert all(r['passed'] for r in (geometry,batches,inverse,video))
summary = dict(passed=True, baseline_commit='e3bc5e5d',
               geometry_median_speedup=geometry['median_speedup'],
               geometry_cases=len(geometry['rows']), batch_cases=len(batches['rows']),
               batch_seconds=batches['sums_seconds'], batch_time_reduction=batches['reduction'],
               tests=read(BUNDLE/'tests.json'), harness_test=read(BUNDLE/'source_amendment.json')['harness_test'],
               extreme_scale_check=read(BUNDLE/'extreme_scale_check.json')['comparisons'],
               final_integrity=read(BUNDLE/'final_integrity.json')['passed'])
tables = {}
for name,data in (('inverse',inverse),('video',video)):
    rows=[]
    for case in CASES:
        comp=read(BUNDLE/name/case/'comparison.json')
        assert comp['passed']
        pair={r['arm']:r for r in data['rows'] if r['case']==case}
        ref,new=pair['reference'],pair['both']
        assert ref['units']==new['units']
        rows.append(dict(case=case,reference_seconds=ref['seconds'],combined_seconds=new['seconds'],
            reduction=1-new['seconds']/ref['seconds'],speedup=ref['seconds']/new['seconds'],
            units_per_arm=ref['units'],exact_non_timing_agreement=True,
            reference_dense_checks=ref['checks']['_dense_self_intersection_count']['calls'],
            combined_spatial_checks=new['checks']['spatial_self_intersection_count']['calls'],
            combined_dense_fallbacks=new['checks']['_dense_self_intersection_count']['calls']))
    reference=sum(r['reference_seconds'] for r in rows)
    combined=sum(r['combined_seconds'] for r in rows)
    summary[name]=dict(rows=rows,reference_seconds=reference,combined_seconds=combined,
        reduction=1-combined/reference,speedup=reference/combined,
        units_per_arm=sum(r['units_per_arm'] for r in rows),campaign_seconds=data['seconds'],
        reference_dense_checks=sum(r['reference_dense_checks'] for r in rows),
        combined_spatial_checks=sum(r['combined_spatial_checks'] for r in rows),
        combined_dense_fallbacks=sum(r['combined_dense_fallbacks'] for r in rows))
    lines=['| Scene | CUDA reference | Combined geometry | Time reduction | Physical units per arm |',
           '|---|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {NAMES[row['case']]} | {row['reference_seconds']:.2f} s | {row['combined_seconds']:.2f} s | {100*row['reduction']:.1f}% | {row['units_per_arm']} |")
    lines.append(f"| **Sum** | **{reference:.2f} s** | **{combined:.2f} s** | **{100*(1-combined/reference):.1f}%** | **{summary[name]['units_per_arm']}** |")
    tables[name]='\n'.join(lines)
(BUNDLE/'summary.json').write_text(json.dumps(summary,indent=1)+'\n')

seconds=batches['sums_seconds']
batch_table='\n'.join([
    '| Arm | Summed diagnostic time | Time reduction | Executed intersection checks |',
    '|---|---:|---:|---:|',
    *[f"| {arm} | {seconds[arm]:.3f} s | {100*(1-seconds[arm]/seconds['reference']):.1f}% | {sum(r['checks']['spatial_self_intersection_count' if arm in ('spatial','both') else '_dense_self_intersection_count']['calls'] for r in batches['rows'] if r['arm']==arm)} |"
      for arm in ('reference','cache','spatial','both')]])
inv,vid=summary['inverse'],summary['video']
dense_seconds=sum(r['checks']['_dense_self_intersection_count']['seconds'] for r in batches['rows'] if r['arm']=='reference')

text=f'''# SPD-014: exact geometry acceleration

**COMPLETE / PASS; qualified opt-in.** The user approved this bounded follow-up
with "you have my approval". Owner: Codex; no independent reviewer claimed.
The [contract](approved_plan.md) preserves geometry sampling, tolerances,
physics, optimizer decisions, work accounting and independent endpoint audits.

Against the completed SPD-012/013 CUDA baseline, the six SC-043 continuation workers take
**{100*inv['reduction']:.1f}% less time** and video preparation takes
**{100*vid['reduction']:.1f}% less time ({vid['speedup']:.2f}x faster)**.
Every paired non-timing inverse and video field agrees exactly. The broad
regression suite passed 369 tests; a subsequent replay-harness test also passed.

## What changed

- The shared sampled-polygon check can use a KD tree to select candidate
  segment pairs, followed by the original crossing, touching and adjacency
  rules. This extends the mechanism already present in the hybrid geometry
  code to Kress validation. It retains all polygon samples and resolved tolerances.
- Candidate pairs are counted before allocation. A candidate budget of
  `min(262144, max(4096, 16*N))`, extreme-coordinate guards and dense fallback
  bound the new allocation. The dense predicate's body is unchanged.
- Backend selection is context-local and copied to frequency workers. Cache
  keys include the backend as well as full points and resolved tolerances, so
  switching arms cannot mask a comparison with an old cache hit.
- Direct audit and complete renderer diagnostic calls use an independent,
  active exact cache. `geometry_validation('cache')` only selects future fits;
  it does not activate caching for direct objective calls. Existing fit caches
  and an explicitly active reference cache keep their original policies.
- Historical SC-042/043 drivers and `latest_vs_hybrid/render.py` are unchanged.
  The replay harness wraps their audit/diagnostic callables and writes fresh
  outputs. Source signatures and all original renderer assertions are preserved.

The normal intersection backend remains `reference`. See
[usage](../../../../experiments/spd014_geometry/README.md) for
`intersection_validation('spatial')`, or `geometry_acceleration('both')` with
`cache_diagnostic` for combined diagnostic acceleration.

## Qualification and attribution

The [geometry screen](geometry/result.json) compares all six SC-043 start/end
curves at 512, 1024 and 2048 nodes: **36 exact count matches**, with a median
**{geometry['median_speedup']:.1f}x** uncached-check speedup. The 256-node grid is
not valid for their K192 storage and is skipped explicitly. Unit tests add
crossings, tolerated touches, collinearity, repeated/zero-length segments,
translations/scales, nonuniform samples, invalid inputs, dense fallback,
cache lifetime, thread sharing and unchanged multicomponent clearance refusals.

The [four-arm screen](batches/result.json) uses six endpoint curves, actual
production/refined grids (512/1024, or 768/1536 for kite), all 19 frequencies,
and two repeats in reversed arm order. All **96 complete diagnostic outputs**
have identical hashes, including Jacobian blocks and frontiers. Each timed
batch performs 19 forwards and 19 reciprocal solves. The 24 warmup units are
recorded separately; total screen work is {batches['units']} units.

{batch_table}

The dense check consumes {dense_seconds:.3f} of {seconds['reference']:.3f} s
({100*dense_seconds/seconds['reference']:.1f}%) in these serial reference batches.
Caching reduces 38 computations per batch to one; spatial pruning makes each
computation much cheaper. Their gains overlap and must not be multiplied.
The combined screen exceeds the declared 20% diagnostic-saving gate.

## Complete SC-043 continuation workers

These workers begin at saved intermediate shapes and execute the complete
SC-043 suffix. They exclude the original circle-start prefix and earlier
releases; their times are not full circle-to-target reconstruction times.

Six SC-043 fixed-policy controls and six combined workers run sequentially,
alternating arm order by scene, with four frequency threads and one BLAS thread.
All 54 paired JSON files match after removing only fields named `seconds`:
decisions, accepted states, three blocks, checkpoints, audits, results and progress.
All endpoint audits pass. Physical units include each worker's 114-unit audit.
These preserve baseline reconstruction quality; they are not a new recovery or
optimizer-policy claim.

{tables['inverse']}

[Inverse receipt](inverse/result.json). Fits already share geometry checks,
so their marginal gain is smaller than for uncached diagnostics. Reference
workers execute {inv['reference_dense_checks']} dense checks; combined workers
execute {inv['combined_spatial_checks']} spatial checks, including independent
audit cache scopes, with {inv['combined_dense_fallbacks']} dense fallbacks on
these six trajectories.

## Fresh video preparation

Both arms run the unchanged renderer with new output/display-cache folders and
the same saved upstream raw field shots. Every non-timing prepared field,
source/cache signature, work counter, curve/RMS and frontier is identical.
Original saved-loss and refinement assertions pass in both arms. No inverse is
rerun here, and the identical displayed content does not need video re-encoding.

{tables['video']}

[Video receipt](video/result.json). Executed intersection checks fall from
**{vid['reference_dense_checks']} dense computations to {vid['combined_spatial_checks']}
spatial computations**, with {vid['combined_dense_fallbacks']} dense fallbacks.
Field and reciprocal work is unchanged.

## Timing scope and provenance

- Same RTX 5090 host; explicit `SC_FORWARD_BACKEND=cuda`, four frequency threads
  for inverse objectives, one BLAS/OpenMP thread, and one process worker at a
  time. The renderer's frequency loop stays serial. No other numerical campaign
  was running. Process/load/GPU observations accompany the saved commands.
- One full pair per scene, two diagnostic repeats. Reported ratios are observed
  shared-host timings, not statistically established population speedups.
  Tables use worker time, including inverse endpoint/scoring or video preparation;
  they exclude harness imports and repeated provenance hashing. The harness
  verifies roughly 21.5 GB of frozen inputs. Its full stage elapsed times are
  {inv['campaign_seconds']:.1f} s for inverse and {vid['campaign_seconds']:.1f} s for video,
  which include that extra verification/startup overhead.
- Earlier SPD-011/013 timings used different concurrency and are not the matched
  timing controls here. The measured baseline is completed commit `e3bc5e5d`
  plus the reference-preserving SPD-014 dispatch, pinned by source hashes.
- [Current manifest](manifest.json), [source archive](sources.tar.gz),
  [preflight source receipt](preflight_source_record/manifest.json), and
  [harness amendment](source_amendment.json) preserve exact provenance. Pre-dispatch
  review found a missing SC-043 output-manifest staging step; that harness-only
  fix and its test were recorded before any inverse run. Numerical sources,
  inputs, thresholds and schedules did not change after the successful screens.
- Geometry validation stays a sampled-polygon guard, not a continuous-curve
  simplicity proof. Dense/pathological shapes can fall back and need not gain
  speed. No multicomponent performance, noisy-data or all-topology-scene claim
  follows from these six single-object development cases.

Tests: [geometry/CPU](geometry-tests.log), [broad regression](regression-tests.log),
[replay harness](harness-tests.log). Post-timing validation adds
[54 exact extreme-scale count/error comparisons](extreme_scale_check.json),
including norm-underflow scales. The [final integrity check](final_integrity.json)
verifies all frozen sources, inputs, the approval snapshot and source archive.
Machine-readable closeout: [summary](summary.json).
Reproduction commands and scoped APIs are in the
[experiment README](../../../../experiments/spd014_geometry/README.md).
'''
(BUNDLE/'README.md').write_text(text)
print(json.dumps({k:summary[k] for k in ('geometry_median_speedup','batch_time_reduction')},indent=1))
for name in ('inverse','video'):
    print(name,{k:summary[name][k] for k in ('reference_seconds','combined_seconds','reduction','reference_dense_checks','combined_spatial_checks')})
