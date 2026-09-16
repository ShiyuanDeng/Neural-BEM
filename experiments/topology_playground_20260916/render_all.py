"""Render the successful meeting runs from saved states without new solves."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiments.top025 import render as old

ROOT=Path(__file__).resolve().parents[2]
BUNDLE=ROOT/'results/experiments/meeting_20260916'
SOURCE=ROOT/'results/validation/topology/TOP-025-20260915-210356-all-scenes-current'
read,write,digest,state_hash=old.read,old.write,old.digest,old.state_hash
FPS=old.FPS


def collect(row):
    topology=BUNDLE/row['topology_run']/'topology'
    refinement=BUNDLE/row['fit_run']/'fit'
    catalog=[];sources={};phases=[]
    def add(state,path,selector,label,trial=False):
        source=str(path.relative_to(ROOT));sources[source]=digest(path)
        catalog.append(dict(state=state,state_sha256=state_hash(state),source=source,
                            selector=selector,label=label,promotion_trial=trial))
        return len(catalog)-1
    initial=topology/'initial_state.json'
    phases.append(('Initial geometry',[add(read(initial),initial,'root','Original starting geometry')],2))
    # Zero padding may change coefficients, but must preserve the original shape.
    before=old.curves(read(SOURCE/'inputs'/row['scene']/'initial_state.json'))
    after=old.curves(read(initial))
    assert len(before)==len(after)
    for a,b in zip(before,after):np.testing.assert_allclose(a,b,atol=1e-12,rtol=0)
    def phase(directory,title,seconds,topology_phase=False):
        path=directory/'trajectory.jsonl';items=[]
        for number,line in enumerate(path.read_text().splitlines(),1):
            item=json.loads(line)
            trial=topology_phase and item['label'].startswith('promote ')
            if trial:label=f"Cycle {item['cycle']}: shape-capacity trial, step {item['label'].split()[-1]}"
            elif topology_phase:label=f"Cycle {item['cycle']}: {item['label']}"
            else:label=f"Accepted shape update {item['iteration']}"
            items.append(add(item['state'],path,f'line {number}',label,trial))
        terminal=directory/'terminal.json';item=read(terminal)
        if not items or catalog[items[-1]]['state_sha256']!=state_hash(item['final_state']):
            items.append(add(item['final_state'],terminal,'final_state','Retained phase endpoint'))
        phases.append((title,items,seconds))
    phase(topology,'Topology search | 500 + 750 MHz',12,True)
    if refinement.exists():phase(refinement,'Shape refinement | 0.5, 0.75, 1, 1.25, 1.75, 2 GHz',7)
    folder=BUNDLE/row['fit_run']
    score=(read(folder/'score.json')['score'] if (folder/'score.json').exists()
           else read(folder/'result.json')['score'])
    endpoint=folder/'retained_state.json';retained=read(endpoint)
    assert state_hash(retained)==score['state_sha256']
    assert catalog[-1]['state_sha256']==state_hash(retained)
    final=add(retained,endpoint,'root','Scored final reconstruction')
    timeline=[]
    for title,items,seconds in phases:
        count=max(seconds*FPS,len(items))
        timeline.extend((items[round(i*(len(items)-1)/max(1,count-1))],title) for i in range(count))
    timeline.extend([(final,'Final reconstruction')]*(5*FPS))
    assert set(range(len(catalog)))<={index for index,_ in timeline}
    return dict(catalog=catalog,timeline=timeline,sources_sha256=sources,score=score)


def bounds(scene,data):
    curves=old.curves(data['catalog'][0]['state'])
    curves.extend(np.array(old.report.old.truth_points(item)) for item in scene['truth'])
    points=np.concatenate(curves)
    low=np.minimum(points.min(axis=0)-.025,[.29,.29])
    high=np.maximum(points.max(axis=0)+.025,[.72,.73])
    return (low[0],high[0]),(low[1],high[1])


def draw_truth(ax,scene):
    for i,item in enumerate(scene['truth']):
        points=np.array(old.report.old.truth_points(item))
        ax.fill(*points.T,color='#dbe5ed',alpha=.65)
        ax.plot(*points.T,'--',color='#475569',lw=1.3,label='Target' if i==0 else None)


def render_scene(scene,row,data,output):
    fig,ax=plt.subplots(figsize=(10,7.6),dpi=100,facecolor='#f7f9fc')
    fig.subplots_adjust(left=.10,right=.94,bottom=.25,top=.80)
    draw_truth(ax,scene)
    cache=[old.curves(item['state']) for item in data['catalog']]
    lines=[ax.plot([],[],color='#0d9488',lw=2,label='Recorded estimate' if i==0 else None)[0]
           for i in range(max(map(len,cache),default=0))]
    xlim,ylim=bounds(scene,data)
    ax.set(xlim=xlim,ylim=ylim,aspect='equal',xlabel='x (m)',ylabel='y (m)')
    ax.grid(alpha=.2);ax.legend(fontsize=9,loc='upper left')
    fig.text(.5,.96,scene['title'],ha='center',fontsize=16,weight='bold')
    phase_text=fig.text(.5,.89,'',ha='center',fontsize=12)
    label=fig.text(.5,.835,'',ha='center',fontsize=10)
    metrics=fig.text(.5,.18,'',ha='center',va='top',fontsize=11)
    fig.text(.5,.035,'Saved states; orange indicates a promotion trial. No shape interpolation.\nPlayback speed does not represent solve time. Evaluation frequencies: 1.5 and 2.5 GHz.',
             ha='center',fontsize=9,color='#475569')
    def draw(frame):
        index,phase=frame;item=data['catalog'][index];polygons=cache[index]
        color='#c87920' if item['promotion_trial'] else '#0d9488'
        for i,line in enumerate(lines):
            line.set_color(color)
            line.set_data((polygons[i][:,0],polygons[i][:,1]) if i<len(polygons) else ([],[]))
        phase_text.set_text(phase);label.set_text(item['label']);label.set_color(color)
        final=phase=='Final reconstruction'
        if final:
            worst=100*max(row['holdout_1_5_relative'],row['holdout_2_5_relative'])
            metrics.set_text(f"PASS: all original endpoint gates\n{row['after_count']} components | Boundary error {row['after_boundary_mm']:.4g} mm | IoU {row['after_iou']:.4f}\nWorst held-out relative field error: {worst:.4g}%")
        else:
            metrics.set_text(f"{len(polygons)} component(s) in this {'trial' if item['promotion_trial'] else 'recorded state'}\nFinal recovery scores are shown at the end.")
        metrics.set_color('#166534' if final else '#334155')
    result=old.encode(fig,output/f"{scene['id']}.mp4",data['timeline'],draw)
    draw(data['timeline'][0]);fig.savefig(output/f"{scene['id']}_initial.png",dpi=100)
    draw(data['timeline'][-1]);fig.savefig(output/f"{scene['id']}_final.png",dpi=100)
    plt.close(fig);return result


def render_overview(scenes,rows,all_data,output):
    fig,axes=plt.subplots(3,4,figsize=(18,13.2),dpi=100,facecolor='#f7f9fc')
    fig.subplots_adjust(left=.035,right=.985,bottom=.10,top=.90,wspace=.18,hspace=.35)
    handles=[]
    for ax,scene in zip(axes.flat,scenes):
        row=rows[scene['id']];data=all_data[scene['id']]
        cache=[old.curves(item['state']) for item in data['catalog']]
        draw_truth(ax,scene)
        lines=[ax.plot([],[],color='#0d9488',lw=1.6)[0] for _ in range(max(map(len,cache),default=0))]
        xlim,ylim=bounds(scene,data)
        ax.set(xlim=xlim,ylim=ylim,aspect='equal');ax.tick_params(labelsize=7);ax.grid(alpha=.15)
        label=ax.set_title('',fontsize=10)
        handles.append((lines,label,cache,data,row))
    fig.suptitle('Updated topology reconstruction | all twelve scenes',fontsize=20,weight='bold',y=.975)
    fig.text(.5,.017,'Dashed: target. Teal: recorded estimate. Orange: promotion trial. Timelines aligned by progress, not wall time.\nOriginal endpoint gates retained; 1.5 and 2.5 GHz evaluation-only. No shape interpolation.',
             ha='center',fontsize=10)
    # Each catalog record appears at least once, including the longest trajectory.
    frames=list(range(28*FPS))+[28*FPS-1]*(5*FPS)
    for data in all_data.values():
        shown={data['timeline'][round(frame/(28*FPS-1)*(len(data['timeline'])-1))][0] for frame in frames}
        assert set(range(len(data['catalog'])))<=shown
    def draw(frame):
        fraction=frame/(28*FPS-1)
        for lines,label,cache,data,row in handles:
            index,phase=data['timeline'][round(fraction*(len(data['timeline'])-1))]
            item=data['catalog'][index];polygons=cache[index]
            color='#c87920' if item['promotion_trial'] else '#0d9488'
            for i,line in enumerate(lines):
                line.set_color(color)
                line.set_data((polygons[i][:,0],polygons[i][:,1]) if i<len(polygons) else ([],[]))
            final=phase=='Final reconstruction'
            status=(f"PASS | {row['after_count']} objects | {row['after_boundary_mm']:.3g} mm" if final
                    else 'Promotion trial' if item['promotion_trial'] else phase.split('|')[0].strip())
            label.set_text(row['scene']+'\n'+status)
            label.set_color('#166534' if final else color if item['promotion_trial'] else '#0f172a')
    result=old.encode(fig,output/'all_scenes.mp4',frames,draw)
    draw(frames[-1]);fig.savefig(output/'all_scenes_final.png',dpi=120)
    plt.close(fig);return result


def main(args):
    rows={row['scene']:row for row in read(BUNDLE/'all_scenes.json')}
    assert len(rows)==12 and all(row['status']=='PASS' for row in rows.values())
    scenes=read(SOURCE/'scene_spec.json')['scenes']
    all_data={scene['id']:collect(rows[scene['id']]) for scene in scenes}
    output=BUNDLE/'videos';output.mkdir(exist_ok=True)
    if args.scene:
        scene=next(s for s in scenes if s['id']==args.scene)
        result=render_scene(scene,rows[args.scene],all_data[args.scene],output)
        write(output/f'{args.scene}_manifest.json',dict(encoding=result,**all_data[args.scene]))
        print('Rendered',args.scene,flush=True);return
    if args.overview:
        result=render_overview(scenes,rows,all_data,output)
        write(output/'overview_manifest.json',result);return
    for scene in scenes:
        result=render_scene(scene,rows[scene['id']],all_data[scene['id']],output)
        write(output/f"{scene['id']}_manifest.json",dict(encoding=result,**all_data[scene['id']]))
        print('Rendered',scene['id'],flush=True)
    result=render_overview(scenes,rows,all_data,output)
    write(output/'overview_manifest.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene');parser.add_argument('--overview',action='store_true')
    main(parser.parse_args())
