"""One meeting figure and a small result table; no experiment documentation tree."""
from pathlib import Path
import csv
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from .run import p,SOURCE,read,write

ROOT=Path('results/experiments/meeting_20260916')
CASES=[
    ('empty-ellipse-star','empty_two_frequency_ellipse_seeds','empty_six_frequency_polish'),
    ('far-ellipse-star','uniform_far_ellipse_star/topology','uniform_far_ellipse_star/refinement'),
    ('enclosing-ellipse-star','enclosing_two_frequency_ellipse_seeds','enclosing_six_frequency_polish'),
    ('far-three-shapes','three_shapes_two_frequency_ellipse_seeds','three_shapes_six_frequency_polish'),
    ('far-two-stars','uniform_far_two_stars/topology','uniform_far_two_stars/refinement'),
]
CONTROLS=[
    ('death','control_death_new_policy'),
    ('split','control_split_new_policy'),
    ('repeated-birth','control_repeated-birth_new_policy'),
    ('far-two-circles','control_far-two-circles_new_policy'),
    ('mixed','control_mixed_new_policy'),
    ('merge','control_merge_six_frequency_polish'),
    ('central-ellipse-star','control_central_six_frequency_polish'),
]


def endpoint(folder):
    path=folder/'result.json'
    if not path.exists():return None,None
    result=read(path)
    score=result.get('score',result.get('schedule',{}).get('final'))
    if not score:return None,None
    state=result.get('schedule',{}).get('final_state')
    if state is None and (folder/'retained_state.json').exists():state=read(folder/'retained_state.json')
    return p.driver.deserialize_state(state),score


def old_state(scene):
    folder=SOURCE/'runs'/scene
    if (folder/'F/metrics.json').exists():return p.driver.deserialize_state(read(folder/'F/metrics.json')['final_state'])
    return p.driver.deserialize_state(read(folder/'topology/checkpoint.json')['state'])


def draw_state(ax,state,**kwargs):
    if state is None:return
    for component in state.components:
        points=component.parameterization().discretize(1024).points
        points=np.vstack((points,points[:1]))
        ax.plot(*points.T,**kwargs)


def main():
    spec=read(SOURCE/'scene_spec.json')
    baseline={r['scene']:r for r in csv.DictReader((SOURCE/'comparison.csv').open())}
    fig,axes=plt.subplots(2,3,figsize=(15,9))
    rows=[]
    for ax,(name,topology,continuation) in zip(axes.flat,CASES):
        scene=next(s for s in spec['scenes'] if s['id']==name)
        for curve in p.benchmark.truth_curves(scene):
            points=curve.discretize(1024).points
            ax.fill(*points.T,color='#d9e3ed',alpha=.8)
            ax.plot(*points.T,color='#293e55',lw=2)
        draw_state(ax,old_state(name),color='#d67c35',ls='--',lw=1.2,alpha=.8)
        state,score=endpoint(ROOT/continuation)
        old=baseline[name]
        row=dict(scene=name,before_recovered=old['recovered']=='True',before_count=int(old['count']),before_boundary_mm=float(old['boundary_mm']),
            before_iou=float(old['iou']),after_count=None,after_boundary_mm=None,after_iou=None,
            holdout_1_5_relative=None,holdout_2_5_relative=None,numerically_qualified=False,
            original_gates_pass=False,fresh_original_geometry_start=True,
            topology_run=topology,fit_run=continuation,status='RUNNING')
        if score:
            geometry=score['geometry'];draw_state(ax,state,color='#007f65',lw=1.8)
            row.update(after_count=geometry['component_count'],
                after_boundary_mm=1000*geometry['maximum_matched_hausdorff_m'],after_iou=geometry['union_iou'],
                holdout_1_5_relative=score['evaluation_errors'][0],holdout_2_5_relative=score['evaluation_errors'][1],
                numerically_qualified=score['numerically_qualified'],original_gates_pass=score['original_gates_pass'],
                status='PASS' if score['numerically_qualified'] and score['original_gates_pass'] else 'NOT_RECOVERED')
            title=f'{name}: {row["status"]}\n{row["before_count"]} → {row["after_count"]} objects; {row["before_boundary_mm"]:.2f} → {row["after_boundary_mm"]:.3f} mm'
        else:
            if (ROOT/topology/'retained_state.json').exists():
                draw_state(ax,p.driver.deserialize_state(read(ROOT/topology/'retained_state.json')),color='#007f65',lw=1.8)
            title=f'{name}\nFinal frequency refinement running'
        ax.set(title=title,xlim=(.28,.75),ylim=(.27,.73),aspect='equal',xlabel='x (m)',ylabel='y (m)')
        ax.grid(alpha=.2);rows.append(row)
    ax=axes.flat[-1]
    material=read(ROOT/'mixed_empty_project_acquisition/result.json')
    theta=np.linspace(0,2*np.pi,501)
    for q,kind in zip(material['truth'],material['truth_kinds']):
        q=np.array(q);color='#2b78b8' if kind=='plastic' else '#555555'
        ax.fill(q[0]+q[2]*np.cos(theta),q[1]+q[2]*np.sin(theta),color=color,alpha=.15)
        ax.plot(q[0]+q[2]*np.cos(theta),q[1]+q[2]*np.sin(theta),color=color,lw=2,label=f'True {kind}')
    for q,kind in zip(material['parameters'],material['kinds']):
        ax.plot(q[0]+q[2]*np.cos(theta),q[1]+q[2]*np.sin(theta),'--',color='#007f65',lw=1.8,label=f'Found {kind}')
    ax.set(title='Plastic + ideal metal in sand\nEmpty start; count and labels inferred; 1% noise',
           xlim=(.32,.68),ylim=(.34,.66),aspect='equal',xlabel='x (m)',ylabel='y (m)')
    ax.grid(alpha=.2);ax.legend(fontsize=8,loc='upper left')
    fig.suptitle('Topology recovery experiments — truth: navy / previous failure: orange / new estimate: green',fontsize=14)
    fig.text(.5,.012,'Topology: 500 + 750 MHz. Shape fit: 0.5, 0.75, 1, 1.25, 1.75, 2 GHz. Evaluation only: 1.5 and 2.5 GHz.\nSynthetic data; original endpoint gates and 256/512-node numerical checks retained. Material panel uses the project acquisition geometry.',
             ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.045,1,.96));fig.savefig(ROOT/'meeting_results.png',dpi=180)
    write(ROOT/'meeting_results.json',rows)
    with (ROOT/'meeting_results.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    controls=[]
    for scene,run in CONTROLS:
        folder=ROOT/run
        score=(read(folder/'score.json')['score'] if (folder/'score.json').exists()
               else read(folder/'result.json').get('score'))
        old=baseline[scene]
        geometry=score['geometry']
        controls.append(dict(scene=scene,before_recovered=old['recovered']=='True',before_count=int(old['count']),
            before_boundary_mm=float(old['boundary_mm']),before_iou=float(old['iou']),
            after_count=geometry['component_count'],
            after_boundary_mm=1000*geometry['maximum_matched_hausdorff_m'],
            after_iou=geometry['union_iou'],holdout_1_5_relative=score['evaluation_errors'][0],
            holdout_2_5_relative=score['evaluation_errors'][1],
            numerically_qualified=score['numerically_qualified'],
            original_gates_pass=score['original_gates_pass'],fresh_original_geometry_start=True,
            topology_run=(f'control_{scene}_new_policy'),fit_run=run,
            status='PASS' if score['numerically_qualified'] and score['original_gates_pass'] else 'NOT_RECOVERED'))
    write(ROOT/'all_scenes.json',rows+controls)
    with (ROOT/'all_scenes.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows+controls)
    print(json.dumps([{k:r[k] for k in ('scene','status','after_boundary_mm','holdout_2_5_relative')} for r in rows],indent=2))


if __name__=='__main__':main()
