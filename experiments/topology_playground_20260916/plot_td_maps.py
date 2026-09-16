"""View 500/750 MHz topology sensitivities at the same two retained geometries."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from .run import p,suite,SOURCE,read,write
from sdf_inverse.topology_controller import build_topology_workspace,component_parameterization
from sdf_inverse.runtime import inverse_execution


@inverse_execution
def main():
    root=Path('results/experiments/meeting_20260916')
    _,observed,_,scene,spec=suite.load_scene(SOURCE,'empty-ellipse-star')
    control=p.benchmark.controller_config(spec,'H');solve=p.driver.baseline.iteration01_solve_config()
    geometry=p.driver.baseline._geometry_config(64)
    failed=p.driver.deserialize_state(read(root/'empty_f500/retained_state.json'))
    fig,axes=plt.subplots(2,3,figsize=(12,8),constrained_layout=True)
    saved={}
    for row,(label,state) in enumerate([('Empty start',None),('500 MHz failed endpoint',failed)]):
        fields=[]
        for index in (0,1):
            data=p.training_data([p.TRAIN[index]],observed[:,index:index+1])
            workspace=build_topology_workspace(state,data,geometry,solve,control)
            fields.append(np.where(workspace.material,workspace.removal,workspace.addition))
        fields.append((fields[0]+fields[1])/2)
        scale=np.nanpercentile(np.abs(np.stack(fields)),98)
        for col,(frequency,field) in enumerate(zip(['500 MHz','750 MHz','Equal-weight combination'],fields)):
            ax=axes[row,col]
            im=ax.pcolormesh(workspace.axis_x,workspace.axis_y,field,cmap='RdBu',vmin=-scale,vmax=scale,shading='auto')
            for curve in p.benchmark.truth_curves(scene):
                points=curve.discretize(512).points;ax.plot(*points.T,color='black',lw=1.1)
            if state:
                for component in state.components:
                    points=component_parameterization(component).discretize(512).points
                    ax.plot(*points.T,color='#e7af24',lw=1.6,ls='--')
            ax.set(title=f'{label}\n{frequency}',aspect='equal',xlabel='x (m)',ylabel='y (m)')
            saved[f'row{row}_col{col}']=field
        fig.colorbar(im,ax=axes[row,:],label='TD score (same scale across this row)',shrink=.8)
    fig.suptitle('Negative sensitivity favours insertion outside / removal inside\nBlack: truth; gold dashed: current estimate; white: excluded boundary buffer')
    fig.savefig(root/'td_frequency_maps.png',dpi=180)
    np.savez(root/'td_frequency_maps.npz',x=workspace.axis_x,y=workspace.axis_y,**saved)


if __name__=='__main__':main()
