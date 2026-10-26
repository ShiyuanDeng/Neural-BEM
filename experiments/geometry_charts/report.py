"""Render TA-001 tables and figures from saved data, without new solves."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse import checks
from bem_inverse.io import curve_from, digest, read, write
from .replay import OUTPUT, ROWS, UNIT, at, inputs


def label(metrics, case):
    if case=='aphex_twin__c4':
        return 'near-cusp / tiny local loop'
    if metrics['separation_rad']<.01:
        return 'diagonal minimum; cusp-like'
    if metrics['separation_rad']<np.pi/4:
        return 'local fold; no distant near-touch'
    return 'distant near-touch'


def main():
    rows=[]
    details=[]
    for case,stage in ROWS:
        rebuild=read(OUTPUT/'rebuild'/f'{case}.json')
        classification=read(OUTPUT/'classification'/f'{case}.json')
        replay=read(OUTPUT/'replay'/f'{case}.json')
        original=classification['original']
        matched=next(t for t in replay['trials'] if t['backtrack']==rebuild['failed_backtrack'])
        improving=[t for t in replay['trials'] if t['lower_exact_loss']]
        best=min(improving,key=lambda t:t['physics']['loss']) if improving else matched
        _,_,_,config=inputs(case,stage)
        domain=[]
        for trial in replay['trials']:
            if 'curve' in trial:
                inside=checks.inside_box(curve_from(trial['curve']),config.domain_box)
                domain.append(dict(backtrack=trial['backtrack'],inside_recorded_domain=inside))
                if not inside and trial['lower_exact_loss']:
                    raise ValueError('An improving trial is outside the recorded domain')
        exact_loss=matched['physics']['loss']
        row=dict(case=case,refusal_type=label(original,case),
                 original_min_speed_over_mean=original['minimum_speed_over_mean'],
                 original_W_over_mean_speed=original['W_over_mean_speed'],
                 original_minimum_separation_rad=original['separation_rad'],
                 original_distant_approach_mm=original['distant_approach_mm'],
                 original_physics='refused; loss unavailable',accepted_loss=rebuild['current_loss'],
                 matched_fraction=matched['alpha'],matched_physics=matched['physics']['status'],
                 matched_loss=exact_loss,
                 matched_decrease_percent=None if exact_loss is None else 100*(1-exact_loss/rebuild['current_loss']),
                 matched_min_speed_over_mean=matched['metrics']['minimum_speed_over_mean'],
                 matched_distant_approach_mm=matched['metrics']['distant_approach_mm'],
                 best_fraction=best['alpha'],best_loss=best['physics']['loss'],
                 best_decrease_percent=None if best['physics']['loss'] is None else
                     100*(1-best['physics']['loss']/rebuild['current_loss']),
                 haibing_verdict=classification['haibing']['verdict'],
                 haibing_q_lower_bound=classification['haibing']['q_lower_bound'],
                 roundtrip_mm=replay['roundtrip_mm'],
                 reconstruction_error_mm=rebuild['coefficient_curve_error_mm'])
        rows.append(row)
        details.append(dict(case=case,domain_checks=domain,
                            first_order_checks=replay['first_order_checks'],
                            closure_failed_backtracks=[t['backtrack'] for t in replay['trials'] if 'construction_failed' in t],
                            successful_backtracks=[t['backtrack'] for t in improving]))

        curves=[curve_from(rebuild['accepted']),curve_from(rebuild['original']),curve_from(matched['curve'])]
        metrics=[classification['accepted'],original,matched['metrics']]
        colors=['#0068a8','#d43d28','#00a272']
        labels=['Last accepted',f'Original refused (fraction {matched["alpha"]:g})',
                f'Chart (fraction {matched["alpha"]:g})']
        figure,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
        for curve,metric,color,name in zip(curves,metrics,colors,labels):
            z=curve.values(max(8192,16*(2*curve.band+1)))*UNIT*1000
            z=np.r_[z,z[0]]
            pair=at(curve,metric['min_pair_theta'])*UNIT*1000
            for ax in axes:
                ax.plot(z.real,z.imag,color=color,lw=1.5,label=name)
                ax.plot(pair.real,pair.imag,'o',color=color,markersize=5)
        centre=np.mean(at(curves[1],original['min_pair_theta']))*UNIT*1000
        width=3. if case!='aphex_twin__c13.3' else 5.
        axes[1].set_xlim(centre.real-width,centre.real+width)
        axes[1].set_ylim(centre.imag-width,centre.imag+width)
        axes[0].legend(loc='best',fontsize=8)
        axes[0].set_title(case)
        axes[1].set_title('Original |W|² minimum, enlarged')
        for ax in axes:
            ax.set_aspect('equal',adjustable='box')
            ax.set_xlabel('x relative to scene centre (mm)')
            ax.set_ylabel('y relative to scene centre (mm)')
            ax.grid(alpha=.2)
        figure.savefig(OUTPUT/f'{case}.png',dpi=160)
        plt.close(figure)
    with (OUTPUT/'table.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines=['| Case | Original minimum | speed / mean | Distant gap mm | Accepted loss | Matched chart fraction | Chart status / loss | Loss decrease | Chart speed / mean | Chart gap mm |',
           '|---|---|---:|---:|---:|---:|---|---:|---:|---:|']
    for row in rows:
        status='refused' if row['matched_loss'] is None else f'{row["matched_loss"]:.9f}'
        decrease='—' if row['matched_decrease_percent'] is None else f'{row["matched_decrease_percent"]:.3f}%'
        lines.append(f'| {row["case"]} | {row["refusal_type"]} | {row["original_min_speed_over_mean"]:.6g} | '
                     f'{row["original_distant_approach_mm"]:.3f} | {row["accepted_loss"]:.9f} | '
                     f'{row["matched_fraction"]:g} | {status} | {decrease} | '
                     f'{row["matched_min_speed_over_mean"]:.6g} | {row["matched_distant_approach_mm"]:.3f} |')
    (OUTPUT/'table.md').write_text('\n'.join(lines)+'\n')
    write(OUTPUT/'summary.json',dict(rows=rows,checks=details,
                                   question_2_positive=sum(r['matched_loss'] is not None and r['matched_loss']<r['accepted_loss'] for r in rows),
                                   source_sha256={str(p.relative_to(Path(__file__).resolve().parents[2])):digest(p)
                                                  for p in Path(__file__).parent.glob('*.py')}))
    print('\n'.join(lines))


if __name__=='__main__':
    main()
