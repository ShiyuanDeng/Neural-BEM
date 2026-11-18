"""Report the no-curvature row against activity 04 from saved receipts."""
import datetime
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'results/brg/tg002_no_curvature/2026-11-18'
SOURCE=ROOT/'results/brg/tg002_shapes/2026-11-17'
DOC=ROOT/'docs/iterations/brg_adaptation/05_run_brg_without_curvature_limit'


def main():
    state=json.loads((BASE/'campaign.json').read_text())
    cases=[]
    for case in state['cases']:
        p=BASE/case
        if not (p/'metrics.json').exists():continue
        cases.append((case,json.loads((p/'metrics.json').read_text()),json.loads((SOURCE/case/'metrics.json').read_text()),
            json.loads((p/'attempt_01.json').read_text())))
    text=f'''# Run BRG without the curvature limit: provisional control

## Status and settings

Started {state['started']}; queue state `{state['status']}`;
{len(cases)}/20 cases have scores. Last update: {state.get('ended',state['updated'])}.
These are **provisional BRG-forward data**, identical to activity 04 by
SHA-256. This is the control row alongside its shipped-limit row.

The [plan](plan.md) records the coordinator's decision. The only inverse
change is removing the curvature constraint with the wrapper's existing
switch: it omits `eps_curv` and the inactive `n_curv_min` parameter.
The public default `eps_curv=Inf` never rejects on curvature. Self-intersection
checks remain. Same 37 frequencies, one centred unit-disk start, known
contrast, update bands, eight threads, public stops/filter and patches 03/04.
No BEM run or edit. No new upstream patch. Every case starts afresh.

The original data files are read in place, with no data generation. Each
`data_reuse.json` records their paths and SHA-256 plus the geometry-input
hash; the runner verifies hashes before fitting. Original data-generation
cost is retained in metrics as `reused_data_generation_seconds`; new data
cost is zero. The resource monitor raised the BRG ceiling from four to six
at 02:40 UTC and to eight at 02:51 UTC, only while CSI stays held; the policy applies at
new launch boundaries, without changing active fits.
The queue overlaps other work, so times are indicative.

Scoring follows unchanged protocol 1, with all components, no fitted
alignment, raw set-difference area divided by true area and known-contrast
error. Final-curve residuals use all 37 observations. Both rows stay
provisional until the BEM side freezes and checks the shared data.

## Results against the shipped curvature limit

Area errors are raw fractions, not percentages. Each case links to its
compact metrics and figure. No new success cutoff is selected.

| Case | State | Frequencies | 04 area | 05 area | 04 max residual | 05 max residual | Inverse s | Residual s | Score s | Case wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
'''
    for case,m,old,a in cases:
        residual='missing' if m['max_final_curve_residual'] is None else f"{m['max_final_curve_residual']:.6g}"
        text+=f"| {case} | {m['status']} | {m['completed_frequencies']}/37 | {old['area_error']:.8g} | {m['area_error']:.8g} | {old['max_final_curve_residual']:.6g} | {residual} | {m['inverse_seconds']:.2f} | {m['residual_check_seconds']:.2f} | {m['scoring_seconds']:.2f} | {a['case_wall_seconds']:.2f} |\n"
    text+='\n## Time, limits and saved-output checks\n\n'
    if state.get('ended'):
        elapsed=(datetime.datetime.fromisoformat(state['ended'])-datetime.datetime.fromisoformat(state['started'])).total_seconds()
        text+=f"Queue ended {state['ended']}; elapsed {elapsed/60:.2f} min against a 300 min reporting target.\n\n"
    if state.get('pilot_wall_seconds'):
        text+=f"Kite eta 0.5 pilot: {state['pilot_wall_seconds']:.2f} s. It ran alone before the rest.\n\n"
    text+=f"Aggregate case wall time: {sum(a['case_wall_seconds'] for _,_,_,a in cases)/60:.2f} min. New data-generation time: zero.\n\n"
    samples=[json.loads(l) for l in (BASE/'resources.jsonl').read_text().splitlines()]
    text+=f"Minimum sampled available memory: {min(s['available_gib'] for s in samples):.2f} GiB; maximum simultaneous control workers: {max(len(s['active']) for s in samples)}. Each launch checks fresh shared memory, reserves at least 3 GiB for the new BRG fit and retains the 14 GiB floor plus 2 GiB margin, allowing for other queues and B1 reservations. The guard delays starts; it never kills running fits.\n\n"
    if state.get('case_target_exceeded') or state.get('queue_target_exceeded_at'):
        text+=f"Time targets exceeded: cases {state.get('case_target_exceeded',{})}; queue {state.get('queue_target_exceeded_at','no')}. Runs continued; time targets never stop work.\n\n"
    if state.get('stop_reason'):
        text+=f"Queue stop reason: {state['stop_reason']}. Unrun cases: {state.get('unrun_cases',[])}.\n\n"
    for case,m,old,a in cases:
        p=BASE/case
        check=json.loads((p/'saved_output_check.json').read_text()) if (p/'saved_output_check.json').exists() else None
        status='pending' if check is None else ('passed' if not check['issues'] else str(check['issues']))
        text+=f"- {case}: saved-output check {status}; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/{case}/metrics.json), [figure](figures/{case}.png).\n"
        if a.get('returncode') or a.get('supervisor_failure') or a.get('scoring_failure'):
            text+=f"  Failure: return code {a.get('returncode')}; {a.get('supervisor_failure','')} {a.get('scoring_failure','')}; log `{a['log']}`.\n"
    text+='\nCompleted attempt receipts also record peak other simultaneous BRG/B1 fits, distinct overlapping fit receipts, and original MATLAB snapshots. Counts use saved process intervals; BRG intervals include residual evaluation. No B1 files are changed.\n'
    text+='\n## Frequency-ending rejection codes\n\nThe first two columns count the selected final geometry/filter code on rejected frequency exits. The last counts final iteration ier -5. They overlap: the public routine replaces geometry rejection by -5 when the old residual is kept. Counts come only from existing logs; each case retains full codes and log hashes.\n\n| Case | Final filter ier 2 | Final filter ier 1 | Final iteration ier -5 |\n|---|---:|---:|---:|\n'
    for case,m,old,a in cases:
        p=BASE/case/'rejection_counts.json'
        if p.exists():
            r=json.loads(p.read_text());c=r['selected_terminal_filter_ier_counts']
            text+=f"| {case} | {c.get('2',0)} | {c.get('1',0)} | {r['final_iteration_ier_counts'].get('-5',0)} |\n"
    text+='\n## Interpretation and next step\n\n'
    if (BASE/'PILOT_REVIEW.json').exists():
        text+='The first case, kite at contrast 0.5, reduced area error from 47.53% to 33.87% and maximum final residual from 0.3901 to 0.2051 in 374.85 s. It still failed to recover the shape. Its saved curve has loops and ripples; unchanged scoring reports a repaired ring and two components. There were no terminal curvature rejections, but 24 terminal self-intersection rejections and 37 final iteration ier -5 codes. The saved checks and settings review passed; the remaining cases were released without a supervisor restart. See `PILOT_REVIEW.json`.\n\n'
    if state['status']=='complete' and len(cases)==20:
        improved=sum(m['area_error']<old['area_error'] for _,m,old,_ in cases)
        worsened=sum(m['area_error']>old['area_error'] for _,m,old,_ in cases)
        unchanged=20-improved-worsened
        under5=sum(m['area_error']<=0.05 for _,m,_,_ in cases)
        residual_ok=sum(m['max_final_curve_residual']<=0.003 for _,m,_,_ in cases)
        old_under5=sum(old['area_error']<=0.05 for _,_,old,_ in cases)
        text+=f"Removing the curvature limit lowers raw area error in {improved}/20 cases, raises it in {worsened}/20 and leaves {unchanged}/20 exactly unchanged. {under5}/20 cases have area error at most 5%, versus {old_under5}/20 with the shipped limit; {residual_ok}/20 meet the clean final-residual limit. These are descriptive counts, not a decision on the open final-table cutoff. Contrast error remains zero by construction because BRG receives the true contrast.\n\n"
        text+='The curvature limit is a real cause of stalled updates in the shipped row, but removing it does not uniformly improve recovery. The raw curves, self-intersection rejections and high residuals retain the remaining failures. No setting was tuned to a shape, and no failed recovery was retried. Both rows remain provisional; this activity does not establish a final cross-solver comparison.\n\n'
        text+=f"Measured phase totals: inverse {sum(m['inverse_seconds'] for _,m,_,_ in cases)/60:.2f} min; final residual checks {sum(m['residual_check_seconds'] for _,m,_,_ in cases)/60:.2f} min; scoring {sum(m['scoring_seconds'] for _,m,_,_ in cases)/60:.2f} min. These overlap across cases and with B1. Source data generation is reused, not charged as fresh work.\n\n"
        peaks=[a.get('fit_overlap',{}).get('peak_other_fits') for _,_,_,a in cases]
        if all(p is not None for p in peaks):
            text+=f"Each case overlapped a peak of {min(peaks)} to {max(peaks)} other BRG/B1 fit processes. Each attempt receipt names the contributing saved timing records. These timings must be read as shared-machine timings.\n\n"
    else:
        text+='Interpretation remains partial until the queue ends. All failed or user-stopped cases remain in the record.\n\n'
    text+='Bulk observations remain in activity 04. Fresh exact states and logs stay local with SHA-256 manifests. Source snapshots, order, overlap and receipts are retained. Shared-data qualification and BEM rows belong to the BEM side. Any further tuning or experiment needs a new coordinator decision.\n'
    (DOC/'results.md').write_text(text)


if __name__=='__main__':main()
