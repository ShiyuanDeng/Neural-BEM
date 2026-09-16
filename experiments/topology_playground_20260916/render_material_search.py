"""Animate recorded shortlisted-birth optimization states, without interpolation."""
from pathlib import Path
import argparse
import json
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(args):
    root=Path('results/experiments/meeting_20260916')
    source=root/args.source
    result=json.loads((source/'result.json').read_text())
    frames=root/(args.name+'_frames');frames.mkdir(exist_ok=True)
    states=[dict(parameters=[],kinds=[],loss=.5,label='Empty initial scene',duration=2.)]
    for event in result['events']:
        selected=event['selected'];kinds=selected['kinds'];new_kind=kinds[-1]
        for step in selected['history']:
            states.append(dict(parameters=step['parameters'],kinds=kinds,loss=step['loss'],
                label=f'Proposed {new_kind} birth — joint fit, step {step["iteration"]}',duration=.55))
        states.append(dict(parameters=selected['parameters'],kinds=kinds,loss=selected['loss'],
            label=f'Birth accepted: {len(kinds)} object'+('s' if len(kinds)>1 else ''),duration=1.4))
    states[-1]['duration']=3.
    theta=np.linspace(0,2*np.pi,401);records=[]
    for index,state in enumerate(states):
        fig,(ax,lossax)=plt.subplots(1,2,figsize=(10,4.8),gridspec_kw={'width_ratios':[1.25,1]})
        for q,kind in zip(result['truth'],result['truth_kinds']):
            x=q[0]+q[2]*np.cos(theta);y=q[1]+q[2]*np.sin(theta)
            ax.fill(x,y,color='#c9d9e6' if kind=='plastic' else '#c3c5c8',alpha=.65)
            ax.plot(x,y,':',color='#4d5964',lw=1.3)
        for q,kind in zip(state['parameters'],state['kinds']):
            ax.plot(q[0]+q[2]*np.cos(theta),q[1]+q[2]*np.sin(theta),
                    color='#087f9b' if kind=='plastic' else '#793ea0',lw=2.8,label=f'Estimated {kind}')
        ax.set(xlim=(.31,.69),ylim=(.33,.67),aspect='equal',xlabel='x (m)',ylabel='y (m)',title=state['label'])
        if state['kinds']:ax.legend(loc='upper left',fontsize=9)
        ax.grid(alpha=.18)
        errors=[max(1e-12,np.sqrt(2*s['loss'])) for s in states[:index+1]]
        lossax.semilogy(range(index+1),errors,'-o',color='#007f65',markersize=4)
        if result['noise']:
            lossax.axhline(result['noise'],color='#8b6b47',ls=':',label=f'{100*result["noise"]:g}% noise level')
            lossax.legend(loc='upper right',fontsize=9)
        lossax.set(xlim=(-.5,len(states)-.5),ylim=(max(1e-11,result['noise']*.05),2),xlabel='Recorded proposal / accepted state',
                   ylabel='Relative data misfit',title=f'{len(state["kinds"])} objects; misfit {errors[-1]:.2g}')
        lossax.grid(alpha=.2)
        fig.suptitle(f'Plastic + ideal metal in sand — empty start, {100*result["noise"]:g}% noise',fontsize=14)
        fig.text(.5,.015,'Count and material labels inferred. Circular shapes; BEM-generated data; analytic coupled Jacobian.\nDotted boundaries / shading: truth. Proposed-birth frames show the selected candidate trial.',
                 ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.08,1,.94))
        path=frames/f'{index:03d}.png';fig.savefig(path,dpi=120);plt.close(fig)
        records.append((path.resolve(),state['duration']))
    listing=frames/'frames.txt'
    listing.write_text(''.join(f"file '{path}'\nduration {duration}\n" for path,duration in records)
                       +f"file '{records[-1][0]}'\n")
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(listing),
                    '-vf','fps=20','-c:v','libx264','-crf','20','-pix_fmt','yuv420p',
                    str(root/(args.name+'.mp4'))],check=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='mixed_empty_start_clean')
    parser.add_argument('--name',default='plastic_metal_empty_start')
    main(parser.parse_args())
