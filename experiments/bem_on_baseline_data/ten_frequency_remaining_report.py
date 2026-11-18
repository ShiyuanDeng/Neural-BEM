"""Report activity 10 from saved results only; no forward solve."""
from csi_runtime import ROOT, provenance
import hashlib
import json
from pathlib import Path
import numpy as np
from bem_inverse.io import curve_from
import csi_fit as F

OUT=ROOT/'results/bem/baseline_data/csi_ten_frequency/2026-11-18'
OLD=ROOT/'results/bem/baseline_data/csi_five_frequency/2026-11-18'
DOC=ROOT/'docs/iterations/adapt_bem_to_baseline_data/10_fit_remaining_csi_tables_at_ten_frequencies'
FIRST=('circle','star','kite','hook')
NEW=('peanut','asymmetric','c_shape','cross','cog','aphex_twin')
ALL=FIRST+NEW

def load(p): return json.loads(p.read_text())
def folder(root,s): return root/(s+'__c4')/'cuda/attempt_01'
def collect(root,s):
    p=folder(root,s)
    return dict(metrics=load(p/'metrics.json'),manifest=load(p/'manifest.json'),
                fit=load(p/'fit.json') if (p/'fit.json').exists() else None)

def main():
    old={s:collect(OLD,s) for s in ALL}
    new={s:collect(OUT,s) for s in ALL if (folder(OUT,s)/'metrics.json').exists()}
    done=[s for s in NEW if s in new]
    score_path=OUT/'remaining_stage_scores.json'
    record=load(score_path) if score_path.exists() else dict(rule='curve_from(stages[i][curve]); csi_fit.score(case, curve, contrast); no solve',cases={})
    record['provenance']=provenance()
    for s in done:
        if s in record['cases']: continue
        d=new[s]; stages=[]
        for stage in d['fit']['stages'] if d['fit'] else []:
            stages.append(dict(stage=stage['stage'],M=stage['M'],outcome=stage['outcome'],contrast=stage['contrast'],
                score=F.score(s+'__c4',curve_from(stage['curve']),stage['contrast'])))
        fit_path=folder(OUT,s)/'fit.json'
        record['cases'][s]=dict(fit_path=str(fit_path.relative_to(ROOT)),
            fit_sha256=hashlib.sha256(fit_path.read_bytes()).hexdigest() if fit_path.exists() else None,
            run_provenance=d['manifest']['provenance'],stages=stages)
    score_path.write_text(json.dumps(record,indent=2)+'\n')
    gains=[s for s,d in new.items() if d['metrics'].get('outcome')=='COMPLETED_SCHEDULE'
           and d['metrics'].get('score',{}).get('area_error',float('inf'))<=old[s]['metrics']['score']['area_error']/2]
    misses=[s for s,d in new.items() if d['metrics'].get('score',{}).get('area_error',0)>.05]
    failures=[s for s in done if new[s]['metrics']['outcome']!='COMPLETED_SCHEDULE']
    lines=['# Fit the remaining ten-frequency CSI cases: results','',
        '18 November 2026. Runner: bem-ten. [Plan](plan.md).',
        f'State: {len(done)}/6 new GPU fits recorded; {len(new)}/10 ten-frequency results available.','',
        '## Settings and evidence','',
        'Same frozen ten-frequency CSI tables and passing checks as activity 08.',
        'Frequencies: 0.25 to 2.5 GHz in 0.25 GHz steps. All tables have 17640 rows.',
        'Unchanged csi_ten_frequency.py runner and csi_fit.py wrapper; no code change.',
        'Default modal_muller + slider, centred 65 mm circle, real data only,',
        'recovered contrast, no localization, warm-up or declared noise. Series limit 1e-9.',
        'Ten-stage ladder quotas: 1000, eight times 375, 4000; total fit limit 13412 work units.','',
        'Each new shape is fitted once on the GPU. Fits run detached, one at a time here.',
        'The machine is shared with other sessions, so times are indicative.',
        'There is no elapsed-time stop, tuning or rerun. Existing checks are reused.','',
        'The first four ten-frequency rows are copied from activity 08. They were not rerun.',
        'Five-frequency rows are read from activity 07, without fitting or solving again.','',
        '## All ten shapes beside the five-frequency pass','',
        'Area error is symmetric difference divided by true area, in percent.',
        'A clear gain halves the five-frequency area error. A score above 5% is a miss.','',
        '| Shape | Frequencies | Outcome | Last stage | Work units | Fit seconds | Contrast | Area error (%) |',
        '|---|---|---|---|---:|---:|---:|---:|']
    for s in ALL:
        for label,rows in (('five',old),('ten',new)):
            if s not in rows:
                lines.append(f'| {s} | {label} | pending | — | — | — | — | — |');continue
            m=rows[s]['metrics']
            area=f"{100*m['score']['area_error']:.6f}" if 'score' in m else 'unavailable'
            sec=f"{m['fit_seconds']:.3f}" if 'fit_seconds' in m else 'unavailable'
            contrast=f"{m['contrast']:.9f}" if 'contrast' in m else 'unavailable'
            lines.append(f"| {s} | {label} | {m['outcome']} | {m.get('last_stage','unavailable')} | {m.get('work_units','unavailable')} | {sec} | {contrast} | {area} |")
    lines+=['','## Area error of every saved stage: the six new fits','',
        'Each curve comes from fit.json stages[i]["curve"], decoded with bem_inverse.io.curve_from,',
        'then scored with csi_fit.score(case, curve, contrast). No solve is needed or run.',
        'Saved scores are reused when this report is updated.','',
        '| Shape | Stage | Shape band | Outcome | Area error (%) |','|---|---|---:|---|---:|']
    for s in done:
        for t in record['cases'][s]['stages']:
            lines.append(f"| {s} | {t['stage']} | {t['M']} | {t['outcome']} | {100*t['score']['area_error']:.6f} |")
    lines+=['','## Run records for the six new fits','',
        '| Shape | Start UTC | Commit | Solver dirty | Start GiB | Peak host / GPU GiB |','|---|---|---|---|---:|---:|']
    for s in done:
        d=new[s]; p=d['manifest']['provenance']; m=d['metrics']
        lines.append(f"| {s} | {p['utc']} | `{p['commit'][:9]}` | {p['solver_used_dirty']} | {p['memory_available_gib']:.3f} | {m['peak_memory_gib']:.3f} / {m['gpu_peak_allocated_gib']:.3f} |")
    lines+=['','Evidence: [ten-frequency fits](../../../../results/bem/baseline_data/csi_ten_frequency/2026-11-18/).',
        'Each attempt has manifest.json, fit.json, metrics.json and bulk_manifest.json; logs are in logs/.',
        '[Saved stage scores](../../../../results/bem/baseline_data/csi_ten_frequency/2026-11-18/remaining_stage_scores.json)',
        'include fit-file SHA-256 and run provenance. Fit-local histories stay ignored with their hashes.','']
    if len(done)==6:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,3,figsize=(13,9),constrained_layout=True)
        for ax,s in zip(axes.flat,NEW):
            truth=F.truth_for(s+'__c4')[0].values(4096)*50
            a=curve_from(old[s]['fit']['final_curve']).values(4096)*50
            b=curve_from(new[s]['fit']['final_curve']).values(4096)*50 if new[s]['fit'] else None
            ax.fill(truth.real,truth.imag,color='#e8edf1',zorder=0)
            for z,label,color,style,width in ((truth,'Truth','#202c38','-',2.),(a,'Five frequencies','#dc7b22','-',1.4),(b,'Ten frequencies','#1564aa','--',1.4)):
                if z is not None:
                    z=np.r_[z,z[0]];ax.plot(z.real,z.imag,label=label,color=color,ls=style,lw=width)
            m=new[s]['metrics'];n=old[s]['metrics']
            area=f"{100*m['score']['area_error']:.2f}%" if 'score' in m else 'failed'
            title={'c_shape':'C-shape','aphex_twin':'Aphex Twin'}.get(s,s.capitalize())
            ax.set_title(f"{title}\nTen {area}; five {100*n['score']['area_error']:.2f}%",fontsize=11)
            ax.set(xlabel='x (mm)',ylabel='y (mm)',aspect='equal');ax.grid(alpha=.2);ax.margins(.1)
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False)
        fig.suptitle('Remaining six CSI cases: ten frequencies versus five\nTen: 0.25–2.5 GHz; five: 0.5–2.5 GHz',fontsize=14)
        (DOC/'figures').mkdir(exist_ok=True)
        fig.savefig(DOC/'figures/outlines.png',dpi=170);plt.close(fig)
        lines+=['## Outlines','','![Six new fits over truth and five-frequency fits](figures/outlines.png)','',
            '## Conclusion','',f'All-ten clear-gain count: {len(gains)}/10 ('+', '.join(gains)+').',
            f'Ten-frequency misses above 5%: {len(misses)}/10'+(' ('+', '.join(misses)+').' if misses else '.'),
            'The six new fits complete the BEM side of the paired ten-frequency table.','']
    else:
        lines+=['## Progress','',f'Clear gains among the {len(new)} recorded ten-frequency results: {len(gains)}.',
            'Final all-ten count and figure wait for the remaining fits.','']
    lines+=['## Failures','', 'Fit failures: '+(', '.join(failures)+'.' if failures else 'none recorded.'),
        'No fit or data check was rerun. Activity 08 retains its earlier pending-input launch receipt.','',
        '```text','Activity: adapt_bem_to_baseline_data/10_fit_remaining_csi_tables_at_ten_frequencies',
        f'Runs: {len(done)}/6 new GPU fits; four activity 08 fits copied; no new forward checks',
        f'Result: {len(new)}/10 results available; {len(gains)} clear gains; {len(misses)} misses above 5%',
        'Failures: '+(', '.join(failures) if failures else 'none'), 'Upstream patches: none',
        'Changes to our code: none; unchanged activity 08 runner and settings',
        'New unknowns: paired MF-CC-CSI results on the ten-frequency tables',
        'Proposed next activity: '+('coordinator hands the completed BEM table to the baseline side' if len(done)==6 else 'finish the remaining authorized fits'),
        '```','']
    (DOC/'results.md').write_text('\n'.join(lines))
    print(json.dumps({s:dict(outcome=new[s]['metrics']['outcome'],area_percent=100*new[s]['metrics']['score']['area_error'] if 'score' in new[s]['metrics'] else None) for s in done},indent=2))

if __name__=='__main__':main()
