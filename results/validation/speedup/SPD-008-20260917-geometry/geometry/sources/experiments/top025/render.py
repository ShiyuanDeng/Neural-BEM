"""Render all scenes using only saved accepted states; no inverse/solver imports."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.top025 import summarize as report

read,write,digest,state_hash=report.read,report.write,report.digest,report.state_hash
FPS=12


def collect(bundle,scene_id):
    folder=bundle/'runs'/scene_id;sources={};catalog=[];phases=[]
    def add(state,path,selector,label):
        sources[str(path.relative_to(bundle))]=digest(path)
        catalog.append(dict(state=state,state_sha256=state_hash(state),source=str(path.relative_to(bundle)),selector=selector,label=label))
        return len(catalog)-1
    initial=bundle/'inputs'/scene_id/'initial_state.json'
    phases.append(('Original initialization',[add(read(initial),initial,'root','Original starting geometry')],2))
    def phase(directory,title,seconds,topology=False):
        items=[];path=directory/'trajectory.jsonl'
        if path.exists():
            for i,line in enumerate(path.read_text().splitlines()):
                row=json.loads(line);label=(f"Cycle {row['cycle']}: {row['label']}" if topology else f"Accepted update {row['iteration']}")
                items.append(add(row['state'],path,f'line {i+1}',label))
        checkpoint=directory/('checkpoint.json' if topology else 'accepted_state.json')
        if checkpoint.exists():
            row=read(checkpoint)
            if not items or catalog[items[-1]]['state_sha256']!=state_hash(row['state']):
                items.append(add(row['state'],checkpoint,'state','Last accepted checkpoint'))
        terminal=directory/'terminal.json'
        if terminal.exists():
            row=read(terminal)
            if not items or catalog[items[-1]]['state_sha256']!=state_hash(row['final_state']):
                items.append(add(row['final_state'],terminal,'final_state','Terminal accepted state'))
        if items: phases.append((title,items,seconds))
    phase(folder/'topology','Automatic topology | 0.5 GHz',10,True)
    for n in (1,2,3,4):
        frequencies=', '.join(f'{f/1e9:g}' for f in report.old.saved.TRAIN[:n])
        phase(folder/'F'/f'stage_{n}',f'Refinement stage {n} | {frequencies} GHz',4)
    result=folder/'F/result.json'
    if result.exists() and read(result).get('skipped_continuation'):
        schedule=read(result)['schedule']
        phases.append(('Training readiness | independent endpoint checks',
            [add(schedule['final_state'],result,'schedule.final_state','Ready without continuation')],2))
    retained=report.old.retained_state(bundle,scene_id,'F')
    assert catalog[-1]['state_sha256']==state_hash(retained),'video does not end at scored retained state'
    timeline=[]
    for title,items,seconds in phases:
        frames=max(seconds*FPS,len(items))
        for i in range(frames): timeline.append((items[round(i*(len(items)-1)/max(1,frames-1))],title))
    timeline += [(len(catalog)-1,'Final retained state')]*(6*FPS)
    assert set(range(len(catalog))).issubset({index for index,_ in timeline})
    return dict(catalog=catalog,timeline=timeline,sources_sha256=sources)


def curves(state):
    return [np.asarray(report.old.saved.curve_points(component,count=512)) for component in (state or [])]


def encode(fig,path,frames,draw):
    fig.canvas.draw();width,height=fig.canvas.get_width_height()
    command=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24',
        '-s',f'{width}x{height}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-crf','22',
        '-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(path)]
    with subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE) as process:
        last=None;pixels=None
        for frame in frames:
            if frame!=last:
                draw(frame);fig.canvas.draw()
                pixels=np.ascontiguousarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3]).tobytes();last=frame
            process.stdin.write(pixels)
        process.stdin.close();stderr=process.stderr.read().decode();code=process.wait()
        if code: raise RuntimeError(f'ffmpeg failed {code}: {stderr}')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height,nb_frames,duration','-of','json',str(path)],text=True))['streams'][0]
    assert int(probe['nb_frames'])==len(frames)
    return dict(command=command,probe=probe,sha256=digest(path),frames=len(frames),fps=FPS)


def metric_text(row):
    error='unmatched' if row['boundary_mm'] is None else f"{row['boundary_mm']:.3f} mm"
    prediction='unavailable' if row['prediction_errors'] is None else f"{max(row['prediction_errors'][4:]):.4g}"
    status='PASS: all recovery gates' if row['recovered'] else ('STOPPED / incomplete' if not row['schedule_complete'] else 'FAIL: recovery gates')
    return status+f"\nCount {row['count']}/{row['truth_count']} | Boundary {error} | IoU {row['iou']:.4f}\nWorst development error: {prediction}"


def render_scene(bundle,scene,row,data):
    fig,ax=plt.subplots(figsize=(10,7.6),dpi=100,facecolor='#f7f9fc')
    fig.subplots_adjust(left=.10,right=.94,bottom=.25,top=.80)
    for i,item in enumerate(scene['truth']):
        ax.plot(*zip(*report.old.truth_points(item)),'--',color='#475569',lw=1.7,label='Target' if i==0 else None)
    cache=[curves(record['state']) for record in data['catalog']]
    count=max((len(c) for c in cache),default=0)
    lines=[ax.plot([],[],color='#0d9488',lw=2,label='Accepted reconstruction' if i==0 else None)[0] for i in range(count)]
    ax.set(xlim=(.28,.73),ylim=(.28,.75),aspect='equal',xlabel='x (m)',ylabel='y (m)');ax.grid(alpha=.2);ax.legend(fontsize=9)
    fig.text(.5,.96,scene['title'],ha='center',fontsize=16,weight='bold')
    title=fig.text(.5,.89,'',ha='center',fontsize=12)
    label=fig.text(.5,.835,'',ha='center',fontsize=10)
    metrics=fig.text(.5,.18,'',ha='center',va='top',fontsize=11)
    fig.text(.5,.035,'Actual accepted states; no coefficient interpolation. Playback speed does not represent solve time.',ha='center',fontsize=9,color='#475569')
    def draw(frame):
        index,phase=frame;polygons=cache[index]
        for i,line in enumerate(lines):
            if i<len(polygons): line.set_data(polygons[i][:,0],polygons[i][:,1])
            else: line.set_data([],[])
        title.set_text(phase);label.set_text(data['catalog'][index]['label'])
        final=phase=='Final retained state'
        metrics.set_text(metric_text(row) if final else f'{len(polygons)} accepted component(s)\nFinal recovery scores are shown at the end.')
        metrics.set_color('#166534' if final and row['recovered'] else '#991b1b' if final else '#334155')
    result=encode(fig,bundle/'videos'/f"{scene['id']}.mp4",data['timeline'],draw)
    draw(data['timeline'][-1]);fig.savefig(bundle/'videos'/f"{scene['id']}_final.png",dpi=120)
    plt.close(fig)
    return result


def render_overview(bundle,spec,rows,all_data):
    fig,axes=plt.subplots(4,3,figsize=(15,17),dpi=100,facecolor='#f7f9fc')
    fig.subplots_adjust(left=.04,right=.98,bottom=.045,top=.94,wspace=.18,hspace=.36)
    handles=[]
    for ax,scene,row in zip(axes.flat,spec['scenes'],rows):
        data=all_data[scene['id']];cache=[curves(record['state']) for record in data['catalog']]
        for item in scene['truth']:ax.plot(*zip(*report.old.truth_points(item)),'--',color='#64748b',lw=1)
        lines=[ax.plot([],[],color='#0d9488',lw=1.5)[0] for _ in range(max(map(len,cache),default=0))]
        ax.set(xlim=(.28,.73),ylim=(.28,.75),aspect='equal');ax.tick_params(labelsize=7);ax.grid(alpha=.15)
        label=ax.set_title('',fontsize=10)
        handles.append((lines,label,cache,data,row))
    fig.suptitle('Latest integrated pipeline · all twelve original starts',fontsize=19,weight='bold',y=.985)
    fig.text(.5,.018,'Dashed: target. Teal: saved accepted reconstruction. Scenes use normalized playback progress; no coefficient interpolation.',ha='center',fontsize=10)
    frames=list(range(24*FPS))+[24*FPS-1]*(6*FPS)
    def draw(frame):
        fraction=frame/(24*FPS-1)
        for lines,label,cache,data,row in handles:
            index,phase=data['timeline'][round(fraction*(len(data['timeline'])-1))]
            polygons=cache[index]
            for i,line in enumerate(lines):
                if i<len(polygons):line.set_data(polygons[i][:,0],polygons[i][:,1])
                else:line.set_data([],[])
            final=phase=='Final retained state';outcome='PASS' if row['recovered'] else 'STOPPED' if not row['schedule_complete'] else 'FAIL'
            error='unmatched' if row['boundary_mm'] is None else f"{row['boundary_mm']:.2f} mm"
            label.set_text(row['scene']+'\n'+(f'{outcome} | {error} | IoU {row["iou"]:.3f}' if final else phase.split('|')[0].strip()))
            label.set_color('#166534' if final and row['recovered'] else '#991b1b' if final else '#0f172a')
    result=encode(fig,bundle/'videos/all_scenes.mp4',frames,draw)
    draw(24*FPS-1);fig.savefig(bundle/'all_scenes.png',dpi=140);fig.savefig(bundle/'all_scenes.svg',metadata={'Date':None})
    plt.close(fig);return result


def render(bundle):
    spec=read(bundle/'scene_spec.json');rows=read(bundle/'scorecard.json')['rows']
    (bundle/'videos').mkdir(exist_ok=True)
    all_data={scene['id']:collect(bundle,scene['id']) for scene in spec['scenes']}
    outputs={}
    for scene,row in zip(spec['scenes'],rows):
        outputs[scene['id']]=render_scene(bundle,scene,row,all_data[scene['id']])
        print('Rendered',scene['id'],flush=True)
    outputs['all_scenes']=render_overview(bundle,spec,rows,all_data)
    for data in all_data.values():
        for path,sha in data['sources_sha256'].items():assert digest(bundle/path)==sha
    write(bundle/'video_manifest.json',dict(new_physical_solves=0,coefficient_interpolation=False,
        all_saved_accepted_records_shown=True,renderer_sha256=digest(Path(__file__)),scenes=all_data,outputs=outputs))
    report.write_index(bundle)
    write(bundle/'artifact_manifest.json',{str(path.relative_to(bundle)):digest(path)
        for path in sorted(bundle.rglob('*')) if path.is_file() and path.name!='artifact_manifest.json'})
    return dict(videos=len(outputs),new_physical_solves=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    print(json.dumps(render(parser.parse_args().bundle.resolve())))
