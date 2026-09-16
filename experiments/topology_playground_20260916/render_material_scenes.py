"""Render every saved empty-start material search, streaming frames to ffmpeg."""
from pathlib import Path
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .render_all import BUNDLE,ROOT,read,write,digest,old,FPS


def collect(result):
    states=[dict(parameters=[],kinds=[],loss=.5,label='Empty initial scene',trial=False,duration=2.)]
    for event in result['events']:
        selected=event['selected']
        for step in selected['history']:
            if 'parameters' not in step:
                # The first noisy runs saved scalar iteration logs only. Their
                # accepted birth states are available; do not invent snapshots.
                continue
            states.append(dict(parameters=step['parameters'],kinds=selected['kinds'],loss=step['loss'],
                label=f"Proposed {selected['kinds'][-1]} birth | joint fit, step {step['iteration']}",trial=True,duration=.6))
        states.append(dict(parameters=selected['parameters'],kinds=selected['kinds'],loss=selected['loss'],
            label=f"Birth accepted: {len(selected['kinds'])} object(s)",trial=False,duration=1.3))
    assert states[-1]['parameters']==result['parameters'] and states[-1]['kinds']==result['kinds']
    states[-1]['duration']=5.
    timeline=[index for index,state in enumerate(states) for _ in range(round(FPS*state['duration']))]
    return states,timeline


def title(result):
    return {'two':'Plastic + ideal metal in sand','one-metal':'One metal circle in sand',
            'three':'Two plastic circles + metal in sand','swapped':'Plastic/metal circles with positions swapped'}[result.get('scene','two')]


def circles(ax,parameters,kinds,truth=False):
    theta=np.linspace(0,2*np.pi,401)
    for q,kind in zip(parameters,kinds):
        x=q[0]+q[2]*np.cos(theta);y=q[1]+q[2]*np.sin(theta)
        if truth:
            ax.fill(x,y,color='#c9d9e6' if kind=='plastic' else '#c3c5c8',alpha=.65)
            ax.plot(x,y,':',color='#4d5964',lw=1.3)
        else:
            ax.plot(x,y,color='#087f9b' if kind=='plastic' else '#793ea0',lw=2.7,label=f'Estimated {kind}')


def render_one(name,result,output):
    states,timeline=collect(result)
    missing=sum('parameters' not in step for event in result['events'] for step in event['selected']['history'])
    fig,(ax,lossax)=plt.subplots(1,2,figsize=(12,6),dpi=100,gridspec_kw={'width_ratios':[1.2,1]})
    fig.subplots_adjust(left=.07,right=.97,bottom=.22,top=.76,wspace=.30)
    fig.suptitle(title(result)+f" | empty start, {100*result['noise']:g}% noise",fontsize=16,y=.965)
    label=fig.text(.5,.875,'',ha='center',fontsize=12)
    acquisition='Project transmitter/receiver geometry' if result.get('project_acquisition') else '24-pair circular acquisition (0.12 rad offset)'
    fig.text(.5,.825,acquisition,ha='center',fontsize=10,color='#475569')
    foot=fig.text(.5,.105,'',ha='center',fontsize=10)
    provenance=('Only retained birth states were saved for this run.' if missing
                else 'Recorded selected-candidate trials shown.')
    fig.text(.5,.025,'Circular family; known material library; PEC metal; independently BEM-generated synthetic data.\nCount and labels inferred. '+provenance+' No shape interpolation.',ha='center',fontsize=9)
    def draw(index):
        state=states[index];ax.clear();lossax.clear()
        circles(ax,result['truth'],result['truth_kinds'],True)
        circles(ax,state['parameters'],state['kinds'])
        ax.set(xlim=(.31,.69),ylim=(.33,.67),aspect='equal',xlabel='x (m)',ylabel='y (m)')
        if state['kinds']:
            handles,labels=ax.get_legend_handles_labels();unique=dict(zip(labels,handles))
            ax.legend(unique.values(),unique.keys(),loc='lower left',fontsize=9)
        ax.grid(alpha=.18)
        errors=[max(1e-12,np.sqrt(2*s['loss'])) for s in states[:index+1]]
        lossax.semilogy(range(index+1),errors,'-o',color='#007f65',markersize=4)
        if result['noise']:
            lossax.axhline(result['noise'],color='#8b6b47',ls=':',label=f"{100*result['noise']:g}% noise level")
            lossax.legend(loc='upper right',fontsize=9)
        lossax.set(xlim=(-.5,len(states)-.5),ylim=(max(1e-11,result['noise']*.05),2),
                   xlabel='Recorded proposal / accepted state',ylabel='Relative data misfit')
        lossax.grid(alpha=.2)
        label.set_text(state['label']);label.set_color('#ad6b17' if state['trial'] else '#166534')
        final=index==len(states)-1
        foot.set_text((f"Final: {len(state['kinds'])} correctly labelled object(s) | fit error {100*result['relative_error']:.4g}%\n"
                       f"Held-out field errors at 1.5 / 2.5 GHz: {100*result['holdout_relative_errors'][0]:.4g}% / {100*result['holdout_relative_errors'][1]:.4g}%")
                      if final else f"{len(state['kinds'])} object(s) in the {'proposed' if state['trial'] else 'retained'} scene")
    encoding=old.encode(fig,output/f'{name}.mp4',timeline,draw)
    draw(timeline[-1]);fig.savefig(output/f'{name}_final.png',dpi=100);plt.close(fig)
    source=BUNDLE/name/'result.json'
    return dict(encoding=encoding,source=str(source.relative_to(ROOT)),source_sha256=digest(source),
                states=states,timeline=timeline,coefficient_interpolation=False,missing_optimizer_snapshots=missing)


def overview(results,output):
    names=['mixed_empty_one_metal','mixed_empty_project_acquisition','mixed_empty_three_objects','mixed_empty_swapped']
    records={name:collect(results[name]) for name in names}
    fig,axes=plt.subplots(2,2,figsize=(12,10),dpi=100,facecolor='#f7f9fc')
    fig.subplots_adjust(left=.06,right=.97,bottom=.14,top=.88,wspace=.17,hspace=.38)
    fig.suptitle('Empty-start material searches | count and material labels inferred',fontsize=16,y=.97)
    fig.text(.5,.025,'Dotted / shaded: truth. Blue: plastic. Purple: ideal PEC metal. Selected-candidate trial frames are labelled.\nKnown circular family and material library; 1% noise; independent BEM data. Timelines aligned by progress.',ha='center',fontsize=9)
    frames=list(range(22*FPS))+[22*FPS-1]*(5*FPS)
    def draw(frame):
        for ax,name in zip(axes.flat,names):
            ax.clear();result=results[name];states,timeline=records[name]
            state=states[timeline[round(frame/(22*FPS-1)*(len(timeline)-1))]]
            circles(ax,result['truth'],result['truth_kinds'],True)
            circles(ax,state['parameters'],state['kinds'])
            ax.set(xlim=(.31,.69),ylim=(.33,.67),aspect='equal',xlabel='x (m)',ylabel='y (m)',
                   title=title(result)+'\n'+state['label'])
            ax.title.set_fontsize(10);ax.title.set_color('#ad6b17' if state['trial'] else '#166534');ax.grid(alpha=.15)
    encoding=old.encode(fig,output/'all_material_scenes.mp4',frames,draw)
    draw(frames[-1]);fig.savefig(output/'all_material_scenes_final.png',dpi=110);plt.close(fig)
    return encoding


def main(args):
    output=BUNDLE/'videos/materials';output.mkdir(parents=True,exist_ok=True)
    rows=read(BUNDLE/'material_results.json');results={row['run']:read(BUNDLE/row['run']/'result.json') for row in rows}
    manifest=(read(output/'video_manifest.json')['outputs'] if args.overview_only else {})
    if not args.overview_only:
        for name,result in results.items():
            manifest[name]=render_one(name,result,output);print('Rendered',name,flush=True)
    manifest['all_material_scenes']=overview(results,output)
    write(output/'video_manifest.json',dict(new_physical_solves=0,renderer_sha256=digest(Path(__file__)),outputs=manifest))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overview-only',action='store_true')
    main(parser.parse_args())
