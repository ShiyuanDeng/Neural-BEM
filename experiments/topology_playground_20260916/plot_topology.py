"""Refresh a compact experimental geometry gallery, with partial runs labelled."""
from pathlib import Path
import json
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .run import p, read


def main():
    root=Path('results/experiments/meeting_20260916')
    configs=sorted(root.glob('*/config.json'))
    if not configs:return
    fig,axes=plt.subplots(math.ceil(len(configs)/3),3,figsize=(13,4*math.ceil(len(configs)/3)),squeeze=False)
    summary=[]
    for ax,path in zip(axes.flat,configs):
        folder=path.parent;config=read(path)
        spec=read(p.ROOT/'config/topology_scenes_v1.json')
        scene=next(s for s in spec['scenes'] if s['id']==config['scene'])
        for curve in p.benchmark.truth_curves(scene):
            points=curve.discretize(512).points
            ax.fill(points[:,0],points[:,1],color='#d7e9f3',alpha=.7)
            ax.plot(*points.T,color='#267ca7',lw=2)
        checkpoint=folder/'topology/checkpoint.json'
        if not checkpoint.exists():continue
        saved=read(checkpoint)
        state=p.driver.deserialize_state(saved['state'])
        if state:
            for component in state.components:
                points=component.parameterization().discretize(512).points
                ax.plot(*points.T,color='#cf613b',ls='--',lw=1.6)
        result=read(folder/'result.json') if (folder/'result.json').exists() else {}
        metrics=result.get('geometry',{})
        title=f'{folder.name}\n{result.get("status","RUNNING")}; objects={0 if state is None else len(state.components)}'
        title+=f'; loss={saved["loss"]:.3g}'
        if metrics:title+=f'\nIoU={metrics["union_iou"]:.3f}; boundary={1000*metrics["maximum_matched_hausdorff_m"]:.2f} mm'
        ax.set(title=title,xlim=(.28,.72),ylim=(.28,.72),aspect='equal')
        ax.grid(alpha=.2)
        summary.append(dict(run=folder.name,status=result.get('status','RUNNING'),
                            loss=saved['loss'],geometry=metrics))
    for ax in list(axes.flat)[len(configs):]:ax.axis('off')
    fig.suptitle('Topology experiments — blue truth, orange retained estimate')
    fig.tight_layout();fig.savefig(root/'topology_gallery.png',dpi=140)
    (root/'topology_summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
