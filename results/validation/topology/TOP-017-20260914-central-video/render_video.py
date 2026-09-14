"""Visualize immutable saved coefficients; no BIE or inverse calls.

The timeline joins explicitly labelled historical runs and shows every saved
accepted TOP-017 state, including checkpoints saved before an interrupted FD.
No intermediate coefficients are interpolated. Stage playback is not cost/time matched.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from matplotlib.lines import Line2D

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=ROOT/'results/validation/topology'
B8=BASE/'TOP-008-20260912-feasible-fd'
B16=BASE/'TOP-016-20260914-fixed-topology'
B17=BASE/'TOP-017-20260914-staged-continuation'
SCENE='central-ellipse-star'
FPS=15
sources={}
catalog=[]


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    sources[str(p.relative_to(ROOT))]=digest(p)
    return json.loads(p.read_text())
def jsonlines(p):
    sources[str(p.relative_to(ROOT))]=digest(p)
    return [json.loads(s) for s in p.read_text().splitlines()]
def state_hash(state):return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def points(state,count=1024):
    t=np.arange(count)*2*np.pi/count
    result=[]
    for c in state:
        assert c['chart']=='cartesian'
        k=c['maximum_mode'];v=np.array(c['parameters']);n=2*(k+1)
        cosine=v[:n].reshape(-1,2);sine=np.vstack((np.zeros(2),v[n:].reshape(-1,2)))
        phase=t[:,None]*np.arange(k+1)[None,:]
        xy=np.cos(phase)@cosine+np.sin(phase)@sine
        result.append(np.vstack((xy,xy[0])))
    return result

def add(state,path,selector,label,score=None):
    if score is not None:assert score['numerically_qualified']
    frame=dict(state=state,state_sha256=state_hash(state),source=str(path.relative_to(ROOT)),
               selector=selector,label=label,score=score)
    catalog.append(frame)
    return len(catalog)-1

def inverse_frames(root,number):
    p=root/f'stage_{number}'
    rows=jsonlines(p/'trajectory.jsonl')
    ids=[add(r['state'],p/'trajectory.jsonl',f'line {i+1}',f"Accepted update {r['iteration']}") for i,r in enumerate(rows)]
    checkpoint=read(p/'accepted_state.json')
    if catalog[ids[-1]]['state_sha256']!=state_hash(checkpoint['state']):
        ids.append(add(checkpoint['state'],p/'accepted_state.json','state',f"Accepted update {checkpoint['iteration']}"))
    terminal=read(p/'terminal.json')
    assert catalog[ids[-1]]['state_sha256']==state_hash(terminal['final_state'])
    return ids


def build():
    spec=read(B17/'scene_spec.json');scene=next(s for s in spec['scenes'] if s['id']==SCENE)
    prefix=B8/'runs/H'/SCENE
    initial=read(prefix/'manifest.json')
    rows=read(prefix/'trajectory.json');old=read(prefix/'metrics.json')
    assert rows[0]['state']==initial['initial_state'] and rows[-1]['state']==old['final_state']
    assert not any(initial[k] for k in ('supplied_target_count','supplied_truth_shape','supplied_event_policy'))
    historical=[add(r['state'],prefix/'trajectory.json',f'index {i}',r['label']) for i,r in enumerate(rows)]
    common=B16/'runs'/f'S-{SCENE}'
    common_ids=inverse_frames(common,1);common_metrics=read(common/'metrics.json')
    assert catalog[common_ids[-1]]['state_sha256']==state_hash(common_metrics['final_state'])
    for a,b in zip(points(old['final_state']),points(catalog[common_ids[0]]['state'])):
        assert np.max(np.linalg.norm(a-b,axis=1))<1e-10  # exact zero-padding seam
    stages={};metrics={}
    for arm in ('S','F'):
        path=B17/'runs'/f'{arm}-{SCENE}'
        metrics[arm]=read(path/'metrics.json')
        assert metrics[arm]['initial_state']==common_metrics['final_state']
        stages[arm]={n:inverse_frames(path,n) for n in (2,3,4)}
        for n in (2,3,4):
            stage=metrics[arm]['stages'][n-2]
            assert catalog[stages[arm][n][-1]]['state_sha256']==stage['score_state_sha256']
            assert catalog[stages[arm][n][0]]['state_sha256']==stage['start_state_sha256']
            if n>2:assert catalog[stages[arm][n-1][-1]]['state_sha256']==catalog[stages[arm][n][0]]['state_sha256']
    timeline=[]
    def hold(seconds,left,right,chapter,subtitle,left_title,right_title,scores=None,phase='history'):
        timeline.append(dict(frames=round(seconds*FPS),left=left,right=right,chapter=chapter,subtitle=subtitle,
            left_title=left_title,right_title=right_title,scores=scores,phase=phase))
    def sequence(left,right,seconds,chapter,subtitle,left_title,right_title,phase='history'):
        count=max(len(left),len(right));total=round(seconds*FPS)
        cuts=np.linspace(0,total,count+1).round().astype(int)
        for i in range(count):
            a=left[round(i*(len(left)-1)/max(1,count-1))]
            b=right[round(i*(len(right)-1)/max(1,count-1))]
            hold((cuts[i+1]-cuts[i])/FPS,a,b,chapter,subtitle,left_title,right_title,phase=phase)
    hold(3,historical[0],historical[0],'Central circle to ellipse + star',
         'Historical starting circle. Dashed black outlines are the target.', 'Original circle', 'Original circle')
    sequence(historical,historical,10,'1 / Archived TOP-008 topology run',
         'Saved history: automatic split, birth and merge. This run was not repeated.', 'Shared historical run','Shared historical run')
    hold(2,historical[-1],historical[-1],'TOP-008 endpoint: two objects found',
         'Correct object count; boundary error 9.223 mm. Shape recovery still failed.', 'Same archived endpoint','Same archived endpoint')
    hold(2,common_ids[0],common_ids[0],'2 / TOP-016 common low-frequency continuation',
         'Explicit run boundary: zero-pad to K=9 without changing the curves.', 'Shared 0.5-GHz fitting','Shared 0.5-GHz fitting')
    sequence(common_ids,common_ids,4,'2 / Archived TOP-016 stage 1',
         'Same accepted low-frequency history for both later arms.', 'Shared 0.5-GHz fitting','Shared 0.5-GHz fitting')
    hold(3,common_ids[-1],common_ids[-1],'TOP-017 starts here: identical two-object states',
         'Fixed topology from this point. Boundary error 8.815 mm; both counts already correct.',
         'S / single frequency','F / cumulative frequencies',scores=[common_metrics['final']]*2,phase='shared')
    for n in (2,3,4):
        freqs=', '.join(f'{x/1e9:g}' for x in metrics['F']['stages'][n-2]['active_frequencies_hz'])
        subtitle=f'Training GHz: S = 0.5    |    F = {freqs}. Only saved accepted coefficients are shown.'
        sequence(stages['S'][n],stages['F'][n],6,f'3 / TOP-017 stage {n}',subtitle,
                 'S / single frequency','F / cumulative frequencies',phase=f'stage_{n}')
        score=[metrics[a]['stages'][n-2]['score'] for a in ('S','F')]
        hold(2 if n<4 else 7,stages['S'][n][-1],stages['F'][n][-1],
             f'TOP-017 stage {n} endpoint' if n<4 else 'Final predetermined endpoint: F passes all original gates',
             'Saved endpoint scores. Later stages were not chosen using these scores.' if n<4 else
             'Accurate fixed-topology recovery demonstrated. A fresh circle-start full pipeline was not rerun.',
             'S / single frequency','F / cumulative frequencies',scores=score,phase=f'stage_{n}_endpoint')
    return scene,timeline,metrics


def main():
    scene,timeline,metrics=build()
    theta=np.arange(2048)*2*np.pi/2048
    truth=[]
    for item in scene['truth']:
        if item['kind']=='ellipse':local=np.column_stack((item['semi_major']*np.cos(theta),item['semi_minor']*np.sin(theta)))
        else:
            radius=item['mean_radius']*(1+item['amplitude']*np.cos(item['lobes']*theta))
            local=radius[:,None]*np.column_stack((np.cos(theta),np.sin(theta)))
        a=item['rotation'];rotation=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
        xy=local@rotation.T+np.array(item['center']);truth.append(np.vstack((xy,xy[0])))
    fig=plt.figure(figsize=(12.8,8),dpi=100,facecolor='#f7f9fc')
    axes=[fig.add_axes([.06,.245,.42,.57]),fig.add_axes([.55,.245,.42,.57])]
    colors=['#b56b19','#086ea4']
    curves=[];titles=[];captions=[]
    for ax,color in zip(axes,colors):
        ax.set_aspect('equal');ax.set_xlim(.385,.615);ax.set_ylim(.385,.615)
        ax.set_xlabel('x (m)',fontsize=10);ax.set_ylabel('y (m)',fontsize=10)
        ax.grid(alpha=.2);ax.tick_params(labelsize=9)
        for xy in truth:ax.plot(xy[:,0],xy[:,1],color='#20232a',lw=1.7,ls=(0,(4,3)),zorder=4)
        curves.append([ax.plot([],[],color=color,lw=2.4,zorder=3)[0] for _ in range(4)])
        titles.append(ax.set_title('',fontsize=13,pad=12,fontweight='bold'))
        ax.legend(handles=[Line2D([],[],color='#20232a',lw=1.7,ls='--',label='Target'),
                           Line2D([],[],color=color,lw=2.4,label='Saved reconstruction')],loc='upper left',fontsize=9)
    chapter=fig.text(.5,.963,'',ha='center',fontsize=19,fontweight='bold',color='#182334')
    subtitle=fig.text(.5,.907,'',ha='center',fontsize=11,color='#344256')
    captions=[fig.text(x,.165,'',ha='center',va='top',fontsize=12,linespacing=1.55,color='#182334') for x in (.27,.76)]
    fig.text(.5,.048,'Playback aligns stages, not iterations, solve counts or wall time. No inverse or forward solves were rerun.',ha='center',fontsize=10,color='#4a5769')
    cache={i:points(r['state']) for i,r in enumerate(catalog)}
    snapshots=[]
    writer=FFMpegWriter(fps=FPS,codec='libx264',extra_args=['-preset','medium','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart','-threads','2'],metadata={'title':'TOP-017 central case — saved-state evidence'})
    counter=0
    with writer.saving(fig,str(HERE/'central_circle_to_ellipse_star.mp4'),dpi=100):
        for index,row in enumerate(timeline):
            chapter.set_text(row['chapter']);subtitle.set_text(row['subtitle'])
            for side,key in enumerate(('left','right')):
                frame=catalog[row[key]];xy=cache[row[key]]
                titles[side].set_text(row['left_title' if side==0 else 'right_title'])
                for line,data in zip(curves[side],xy+[np.empty((0,2))]*(4-len(xy))):line.set_data(data[:,0],data[:,1])
                if row['scores'] is None:
                    captions[side].set_text(f"{len(frame['state'])} component(s)  |  {frame['label']}\nActual saved state; no between-state morphing")
                else:
                    score=row['scores'][side];g=score['geometry'];passed=score['original_gates_pass']
                    captions[side].set_text(f"Boundary {1000*g['maximum_matched_hausdorff_m']:.4f} mm  |  IoU {g['union_iou']:.6f}\nWorst evaluation error {score['maximum_evaluation_error']:.6g}  |  Gates {'PASS' if passed else 'FAIL'}")
            if index in (0,len(timeline)-1):
                name='initial_frame.png' if index==0 else 'final_frame.png'
                fig.savefig(HERE/name,dpi=140,facecolor=fig.get_facecolor());snapshots.append(name)
            for _ in range(row['frames']):writer.grab_frame(facecolor=fig.get_facecolor());counter+=1
            row['end_frame_exclusive']=counter
            if index%20==0:print('rendered segments',index,'frames',counter,flush=True)
    plt.close(fig)
    for path,sha in sources.items():assert digest(ROOT/path)==sha
    serial_catalog=[{k:v for k,v in r.items() if k not in ('state','score')} for r in catalog]
    (HERE/'timeline.json').write_text(json.dumps(dict(fps=FPS,frame_count=counter,duration_seconds=counter/FPS,
        segments=timeline,state_catalog=serial_catalog),indent=2)+'\n')
    summary=dict(kind='saved-state visualization, not a new experiment',scene=SCENE,
        no_forward_or_inverse_reruns=True,coefficient_interpolation=False,playback_cost_matched=False,
        original_circle_history='TOP-008 H; autonomous split/birth/merge from the benchmark central circle',
        common_prefix='TOP-016 shared0.5-GHz stage; exact geometry-preserving K9 padding',
        new_recovery='TOP-017 fixed-topology continuation from two already found components',
        fresh_end_to_end_circle_pipeline_tested=False,source_sha256=sources,
        all_original_final_F_gates_pass=metrics['F']['final']['original_gates_pass'],
        final_F=metrics['F']['final'],final_S=metrics['S']['final'],frame_count=counter,fps=FPS,
        source_state_count=len(catalog),duration_seconds=counter/FPS,
        renderer_sha256=digest(Path(__file__)),outputs_sha256={n:digest(HERE/n) for n in
            ['central_circle_to_ellipse_star.mp4','timeline.json',*snapshots]})
    (HERE/'video_manifest.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print('COMPLETE',counter,'frames,',counter/FPS,'seconds;',len(catalog),'saved states; zero numerical solves',flush=True)

if __name__=='__main__':main()
