"""Plot predetermined saved endpoints; geometry sampling only, no forward calls."""
from pathlib import Path
import hashlib
import json
import os
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('MPLCONFIGDIR','/tmp/top018-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run_top017 as m


def main():
    sources={}
    def read(path):
        sources[str(path.relative_to(ROOT))]=m.p.digest(path)
        return m.read(path)
    campaign=read(HERE/'campaign.json')
    if campaign['status']=='IN_PROGRESS':raise ValueError('wait for fixed campaign endpoints')
    spec=read(HERE/'scene_spec.json')
    scene=next(s for s in spec['scenes'] if s['id']=='far-two-stars')
    common=read(HERE/'inputs/far-two-stars/state.json')
    audit=read(HERE/'phase_a/audit.json')
    catalog=[dict(label='COMMON',state=common,score=audit.get('common_score'))]
    for arm in ('S','F'):
        path=HERE/'runs'/f'{arm}-far-two-stars/metrics.json'
        if path.exists():
            result=read(path)
            label=f'{arm}: prescribed stage 4' if result['schedule_complete'] else f'{arm}: stopped retained state'
            catalog.append(dict(label=label,state=result['final_state'],
                score=result.get('final',result.get('reporting_score')),status=result['status']))
        else:catalog.append(dict(label=f'{arm}: NOT RUN',state=None,score=None))
    truth=[curve.discretize(1024).points for curve in m.p.benchmark.truth_curves(scene)]
    shapes=[]
    for row in catalog:
        row['state_sha256']=None if row['state'] is None else m.state_hash(row['state'])
        shapes.append([] if row['state'] is None else m.p.boundary_points(m.p.driver.deserialize_state(row['state']),1024))
    points=np.concatenate(truth+[xy for curves in shapes for xy in curves])
    lower=points.min(axis=0)-.012;upper=points.max(axis=0)+.012
    fig,axes=plt.subplots(1,3,figsize=(12,5.5),constrained_layout=True)
    for ax,row,curves in zip(axes,catalog,shapes):
        for i,xy in enumerate(truth):
            ax.plot(*np.vstack((xy,xy[0])).T,'--',color='#303640',lw=1.5,label='Target' if i==0 else None)
        for i,xy in enumerate(curves):
            ax.plot(*np.vstack((xy,xy[0])).T,color='#087f8c',lw=1.7,label='Saved reconstruction' if i==0 else None)
        ax.set(xlim=(lower[0],upper[0]),ylim=(lower[1],upper[1]),aspect='equal',xlabel='x (m)',ylabel='y (m)')
        ax.grid(alpha=.15)
        score=row['score']
        if score:
            detail=f"Boundary: {1000*score['geometry']['maximum_matched_hausdorff_m']:.4g} mm | IoU: {score['geometry']['union_iou']:.4f}"
            detail+=f"\nWorst evaluation: {score['maximum_evaluation_error']:.4g} | Numerics: {'pass' if score['numerically_qualified'] else 'fail'}"
        else:detail='No available endpoint score'
        ax.set_title(row['label']+'\n'+detail,fontsize=10)
    axes[0].legend(fontsize=8,loc='center',bbox_to_anchor=(.5,.5))
    fig.suptitle('TOP-018: common start and fixed terminal states\nTwo-star S/F pair at 256/512; no best-stage selection',fontsize=14)
    fig.savefig(HERE/'endpoints.svg')
    svg=HERE/'endpoints.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    fig.savefig('/tmp/top018_endpoints.png',dpi=160)
    plt.close(fig)
    m.write(HERE/'figure_manifest.json',dict(source_sha256=sources,
        renderer_sha256=m.p.digest(Path(__file__)),figure_sha256=m.p.digest(HERE/'endpoints.svg'),
        states=catalog,no_physical_solves=True,no_coefficient_interpolation=True))
    readme=HERE/'README.md';text=readme.read_text()
    section='\n## Saved geometry\n\n[Common start and prescribed terminal states](endpoints.svg).\nThe figure uses only saved coefficients; [state/source associations](figure_manifest.json).\n'
    if '## Saved geometry' not in text:readme.write_text(text+section)
    text=readme.read_text()
    if '## Final closeout' not in text:
        readme.write_text(text+'\n## Final closeout\n\n[Owner review](closeout_review.md) · [Verification](closeout_verification.json) · [Commands](commands.md) · [89 final tests](final_tests.log).\n')
    m.write(HERE/'artifact_manifest.json',{str(x.relative_to(HERE)):m.p.digest(x) for x in sorted(HERE.rglob('*'))
            if x.is_file() and x.name!='artifact_manifest.json'})


if __name__=='__main__':main()
