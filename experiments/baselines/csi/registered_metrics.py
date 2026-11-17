"""Protocol-1 region summaries in the fixed exported numerical frame."""
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from experiments.comparison import scoring as G


def score_field(values,shape,gx,gy,truth,fractions=(.5,.3,.7)):
    n=G.PROTOCOL['grid_cells'];h=G.PROTOCOL['grid_half_width_m']
    x=np.linspace(-h,h,n);y=x[::-1];xx,yy=np.meshgrid(x,y)
    native=np.asarray(values).real.reshape(shape,order='F')
    sampler=RegularGridInterpolator((gx,gy),native,bounds_error=False,fill_value=0.)
    image=sampler(np.column_stack([xx.ravel(),yy.ravel()])).reshape(n,n)
    results=[]
    for fraction in fractions:
        rings,peak=G.support_rings(image,fraction);found,repaired=G.region(rings)
        inside=np.sign(peak)*image>=fraction*abs(peak) if peak else np.zeros_like(image,dtype=bool)
        mean=float(image[inside].mean()) if inside.any() else None
        results.append(dict(fraction=fraction,image_peak=peak,**G.region_scores(found,truth),
            centroid_xy_mm=None if found.is_empty else [1000*found.centroid.x,1000*found.centroid.y],
            mean_susceptibility=mean,mean_relative_permittivity=None if mean is None else 1+mean,ring_repaired=repaired))
    return results,image
