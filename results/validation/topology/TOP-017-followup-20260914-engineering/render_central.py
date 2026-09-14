"""Render only saved accepted states from the fresh integration validation."""
from pathlib import Path
import hashlib
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0,str(ROOT))
import run_top017 as m

RUN = HERE/'central-validated'
FPS = 15
sources = {}


def read(path):
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())


def lines(path):
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return [json.loads(row) for row in path.read_text().splitlines()]


def main():
    result=read(RUN/'result.json')
    spec=read(RUN/'inputs/scene_spec.json')
    scene=next(s for s in spec['scenes'] if s['id']=='central-ellipse-star')
    initial=read(RUN/'inputs/initial_state.json')
    catalog=[]
    def add(state,path,selector,label,score=None):
        catalog.append(dict(state=state,state_sha256=m.state_hash(state),
            source=str(path.relative_to(ROOT)),selector=selector,label=label,score=score))
        return len(catalog)-1
    first=add(initial,RUN/'inputs/initial_state.json','root','Original central circle')
    phases=[]
    top=[]
    path=RUN/'topology/trajectory.jsonl'
    for i,row in enumerate(lines(path)):
        top.append(add(row['state'],path,f'line {i+1}',f"Topology cycle {row['cycle']}: {row['label']}"))
    terminal=read(RUN/'topology/terminal.json')
    if catalog[top[-1]]['state_sha256']!=m.state_hash(terminal['final_state']):
        top.append(add(terminal['final_state'],RUN/'topology/terminal.json','final_state','Topology endpoint'))
    phases.append(('Automatic topology at 0.5 GHz',top,10))
    schedule=result.get('schedule',{})
    for stage in schedule.get('stages',[]):
        n=stage['stage'];folder=RUN/f'continuation/stage_{n}';items=[]
        initial_stage=read(folder/'initial_state.json')
        path=folder/'trajectory.jsonl'
        if path.exists():
            for i,row in enumerate(lines(path)):
                items.append(add(row['state'],path,f'line {i+1}',f"Stage {n}: accepted update {row['iteration']}"))
        else:
            items.append(add(initial_stage,folder/'initial_state.json','root',f'Stage {n}: initial state'))
        saved=read(folder/'accepted_state.json')
        if catalog[items[-1]]['state_sha256']!=saved['state_sha256']:
            items.append(add(saved['state'],folder/'accepted_state.json','state',f"Stage {n}: accepted update {saved['iteration']}"))
        assert catalog[items[-1]]['state_sha256']==stage['terminal']['state_sha256']
        if stage.get('score') is not None:
            assert catalog[items[-1]]['state_sha256']==stage['score_state_sha256']
            catalog[items[-1]]['score']=stage['score']
        freq=', '.join(f'{v/1e9:g}' for v in stage['active_frequencies_hz'])
        phases.append((f'Continuation stage {n} | training: {freq} GHz',items,5))
    timeline=[dict(index=first,chapter='Fresh circle-start validation',frames=2*FPS)]
    for title,items,seconds in phases:
        total=seconds*FPS
        # Duplicate saved frames to fit playback; never interpolate coefficients.
        for i in range(total):
            timeline.append(dict(index=items[round(i*(len(items)-1)/max(1,total-1))],chapter=title,frames=1))
    last=phases[-1][1][-1]
    final_title='Fresh run: all reconstruction gates pass' if result.get('fresh_recovery_pass') else 'Fresh run: recovery not established'
    timeline.append(dict(index=last,chapter=final_title,frames=5*FPS))
    cache={}
    for i,row in enumerate(catalog):
        state=m.p.driver.deserialize_state(row['state'])
        cache[i]=[] if state is None else m.p.boundary_points(state,count=1024)
    fig,ax=plt.subplots(figsize=(9.6,7.2),dpi=100,facecolor='#f7f9fc')
    fig.subplots_adjust(left=.12,right=.90,bottom=.25,top=.80)
    for curve in m.p.benchmark.truth_curves(scene):
        xy=curve.discretize(1024).points
        ax.plot(*np.vstack((xy,xy[0])).T,color='#222',linestyle='--',linewidth=1.7)
    count=max(len(value) for value in cache.values())
    curves=[ax.plot([],[],color='#087ba5',linewidth=2.4)[0] for _ in range(count)]
    ax.set(xlim=(.38,.62),ylim=(.38,.62),xlabel='x (m)',ylabel='y (m)',aspect='equal')
    ax.grid(alpha=.2)
    title=fig.text(.5,.95,'',ha='center',fontsize=16,weight='bold')
    subtitle=fig.text(.5,.88,'',ha='center',fontsize=11)
    score_text=fig.text(.5,.16,'',ha='center',va='top',fontsize=12)
    fig.text(.5,.045,'Blue: saved reconstruction. Dashed: target. No coefficient interpolation.\nPlayback timing does not represent computational work.',ha='center',fontsize=9,color='#455')
    writer=FFMpegWriter(fps=FPS,codec='libx264',extra_args=['-crf','21','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart'])
    frames=0
    with writer.saving(fig,str(HERE/'fresh_circle_to_ellipse_star.mp4'),dpi=100):
        for index,row in enumerate(timeline):
            saved=catalog[row['index']];polygons=cache[row['index']]
            title.set_text(row['chapter']);subtitle.set_text(saved['label'])
            for line,xy in zip(curves,polygons+[np.empty((0,2))]*(count-len(polygons))):
                closed=np.vstack((xy,xy[0])) if len(xy) else xy
                line.set_data(closed[:,0],closed[:,1])
            score=saved['score']
            if score is None:
                score_text.set_text(f'{len(polygons)} component(s)\nActual saved state from the fresh automatic run')
            else:
                geometry=score['geometry']
                score_text.set_text(f"Boundary {1000*geometry['maximum_matched_hausdorff_m']:.4f} mm | IoU {geometry['union_iou']:.6f}\nWorst evaluation error {score['maximum_evaluation_error']:.6g} | Numerically qualified: {score['numerically_qualified']}")
            if index==len(timeline)-1:
                fig.savefig(HERE/'fresh_final.svg',facecolor=fig.get_facecolor())
                svg=HERE/'fresh_final.svg'
                svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
                fig.savefig(HERE/'fresh_final.png',facecolor=fig.get_facecolor())
            for _ in range(row['frames']):
                writer.grab_frame(facecolor=fig.get_facecolor());frames+=1
    plt.close(fig)
    for path,digest in sources.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    m.write(HERE/'video_manifest.json',dict(fresh_run=True,no_new_numerical_solves=True,
        coefficient_interpolation=False,frame_count=frames,fps=FPS,duration_seconds=frames/FPS,
        sources_sha256=sources,state_catalog=catalog,timeline=timeline,
        renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        outputs_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
            for name in ('fresh_circle_to_ellipse_star.mp4','fresh_final.svg','fresh_final.png')}))
    print('Rendered',frames,'frames;',frames/FPS,'seconds;',len(catalog),'saved states',flush=True)


if __name__=='__main__':
    main()
