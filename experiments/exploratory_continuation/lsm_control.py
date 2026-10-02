"""Full-aperture synthetic LSM control, distinct from the paired benchmark."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
os.environ['SC_FORWARD_BACKEND']='cpu'
from pathlib import Path
from time import perf_counter
import numpy as np
from scipy.special import hankel1

from experiments.shape_continuation.forward import PointSourceAcquisition, Work, solve
from experiments.shape_continuation.geometry import FourierCurve
from .indicators import tikhonov_sampling
from .run import write, OUTPUT


def main():
    started = perf_counter()
    count, radius, k, contrast = 32, 3., 2., .5
    angle = np.arange(count)*2*np.pi/count
    sources = radius*np.column_stack((np.cos(angle),np.sin(angle)))
    receivers = radius*np.column_stack((np.cos(angle+.03),np.sin(angle+.03)))
    acquisition = PointSourceAcquisition(sources,receivers,strength=1.,paired=False)
    center, object_radius = .25+.1j, .35
    truth = FourierCurve.circle(object_radius,center)
    work = Work(max_forwards=3)
    fields = [solve(truth,k,contrast,acquisition,n,work=work).prediction for n in (64,128)]
    matrix = fields[1].T * 2*np.pi*radius/count
    x,y = np.meshgrid(np.linspace(-1.,1.,81),np.linspace(-1.,1.,81))
    points = np.column_stack((x.ravel(),y.ravel()))
    probes = .25j*hankel1(0,k*np.linalg.norm(receivers[:,None,:]-points[None,:,:],axis=-1))
    result = tikhonov_sampling(matrix,probes,relative_discrepancy=.01)
    distance = abs(points[:,0]+1j*points[:,1]-center)
    inside,outside=distance<object_radius*.7,distance>object_radius*1.5
    peak=points[np.argmax(result['indicator'])]
    record = dict(acquisition='separate synthetic full 32-by-32 matrix, full ring',
        kernel='i H0^(1)(k r)/4', receiver_source_quadrature_weight=2*np.pi*radius/count,
        discrepancy='1% right-hand-side residual target; NOT measured operator noise',
        relative_forward_refinement=float(np.linalg.norm(fields[0]-fields[1])/np.linalg.norm(fields[1])),
        peak=peak,peak_center_error=float(abs(peak[0]+1j*peak[1]-center)),
        median_inside_to_outside=float(np.median(result['indicator'][inside])/np.median(result['indicator'][outside])),
        attained_fraction=float(np.mean(result['discrepancy_attained'])),
        work=work.summary(),wall_seconds=perf_counter()-started,
        not_a_frozen_topology_benchmark_arm=True)
    output=OUTPUT/'lsm_control'
    write(output/'metrics.json',record)
    np.savez_compressed(output/'image.npz',points=points,**result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(6,5),constrained_layout=True)
    image=ax.imshow(result['indicator'].reshape(x.shape),origin='lower',extent=(-1,1,-1,1),cmap='magma')
    t=np.linspace(0,2*np.pi,200)
    ax.plot(center.real+object_radius*np.cos(t),center.imag+object_radius*np.sin(t),'c-',label='True disk')
    ax.scatter(*peak,c='white',marker='+',label='Indicator peak')
    ax.set_title('LSM numerical control: full matrix, 1% probe discrepancy')
    ax.legend()
    fig.colorbar(image,ax=ax,label='1 / ||g||')
    fig.savefig(output/'image.png',dpi=150)
    print(record)


if __name__=='__main__':
    main()
