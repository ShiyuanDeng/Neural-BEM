"""Animate recorded controller states; no interpolated or manufactured shapes."""
from pathlib import Path
import json
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from .run import p, SOURCE, read


def main():
    root=Path('results/experiments/meeting_20260916')
    frames=root/'topology_compare_frames';frames.mkdir(exist_ok=True)
    runs=['empty_f500','empty_two_frequency_ellipse_seeds']
    histories=[[json.loads(line) for line in (root/run/'topology/trajectory.jsonl').read_text().splitlines()]
               for run in runs]
    scene=next(s for s in read(SOURCE/'scene_spec.json')['scenes'] if s['id']=='empty-ellipse-star')
    titles=['500 MHz; original circle seeds', '500 + 750 MHz; deformable seeds + handoff guard']
    count=max(len(h) for h in histories)
    records=[]
    for index in range(count):
        fig,axes=plt.subplots(1,2,figsize=(11,5.2))
        for ax,history,title in zip(axes,histories,titles):
            row=history[round(index*(len(history)-1)/(count-1))]
            state=p.driver.deserialize_state(row['state'])
            for curve in p.benchmark.truth_curves(scene):
                points=curve.discretize(512).points
                ax.fill(*points.T,color='#dbe5ed',alpha=.8)
                ax.plot(*points.T,color='#425666',ls=':',lw=1.3)
            if state is not None:
                for component in state.components:
                    points=component.parameterization().discretize(512).points
                    points=np.vstack((points,points[:1]))
                    ax.plot(*points.T,color='#00856e',lw=2)
            objects=0 if state is None else len(state.components)
            ax.set(xlim=(.33,.71),ylim=(.30,.69),aspect='equal',xlabel='x (m)',ylabel='y (m)',
                   title=f'{title}\n{objects} objects; {row["label"]}')
            ax.grid(alpha=.18)
        fig.suptitle('Empty-start topology search — ellipse and star',fontsize=15)
        fig.text(.5,.015,'Dotted / shaded: truth. Green: recorded estimate.\nTimelines aligned by progress, not wall time. These are topology endpoints, before final frequency refinement.',
                 ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.07,1,.95))
        path=frames/f'{index:03d}.png';fig.savefig(path,dpi=110);plt.close(fig)
        records.append((path.resolve(),2. if index==0 else (4. if index==count-1 else .18)))
    listing=frames/'frames.txt'
    listing.write_text(''.join(f"file '{path}'\nduration {duration}\n" for path,duration in records)
                      +f"file '{records[-1][0]}'\n")
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(listing),
                    '-vf','fps=20','-c:v','libx264','-crf','20','-pix_fmt','yuv420p',
                    str(root/'topology_before_after.mp4')],check=True)


if __name__=='__main__':main()
