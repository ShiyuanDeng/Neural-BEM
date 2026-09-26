"""Post-fit geometry diagnostics. No decisions, PDE solves or truth-based selection."""
import importlib.util
from pathlib import Path
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial import cKDTree
from experiments.shape_continuation.geometry import arclength_angles

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc042_regularity',HERE/'run.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def measure(curve,target,count=16384):
    nodes=curve.nodes(count)
    s,_=arclength_angles(nodes)
    uniform=2*np.pi*np.arange(count)/count
    curvature=CubicSpline(np.r_[s,2*np.pi],np.r_[nodes.curvatures,nodes.curvatures[0]],bc_type='periodic')(uniform)
    coefficients=np.fft.fft(curvature)/count
    orders=np.abs(np.fft.fftfreq(count)*count)
    power=np.abs(coefficients)**2
    by_order=np.bincount(np.rint(orders).astype(int),weights=power)
    tail=lambda m: float(power[orders>m].sum()/max(power.sum(),1e-30))
    stored_orders=np.arange(-curve.band,curve.band+1)
    stored=np.abs(curve.coefficients)**2*stored_orders**4
    sharpest=int(np.argmax(np.abs(nodes.curvatures)))
    true=target.nodes(count)
    distance,j=cKDTree(true.points).query(nodes.points[sharpest])
    return dict(minimum_radius_mm=float(50/max(abs(nodes.curvatures))),
        speed_max_over_min=float(max(nodes.speeds)/min(nodes.speeds)),
        curvature_arclength_tail_above_64=tail(64),
        curvature_arclength_order_for_95pct_energy=int(np.searchsorted(np.cumsum(by_order),.95*by_order.sum())),
        stored_second_derivative_energy_above_64=float(stored[abs(stored_orders)>64].sum()/max(stored.sum(),1e-30)),
        sharpest_point_mm=(50*nodes.points[sharpest]).tolist(),
        sharpest_point_to_truth_mm=float(50*distance),
        truth_radius_near_sharpest_mm=float(50/max(abs(true.curvatures[j]),1e-30)))


def main():
    r.verify()
    rows=[]
    for case in r.CASES:
        target=r.ast.curve_from(r.sc.read(r.ast.source_folder(case)/'truth.json'))
        for name,curve in (('truth',target),('start',r.start_record(case)[0])):
            rows.append(dict(case=case,arm=name,**measure(curve,target)))
        for arm in r.ARMS:
            path=HERE/'runs'/case/arm/'result.json'
            if path.exists():
                result=r.sc.read(path)
                rows.append(dict(case=case,arm=arm,**measure(r.ast.curve_from(result['curve']),target)))
    r.write(HERE/'regularity.json',dict(rows=rows,count=16384,
        interpretation='Curvature spectrum is evaluated in uniform arclength. Stored-coefficient energy depends on the curve parameterization. Neither statistic is an observability test. Nearest-truth feature localization is sampled, not a certified distance.'))
    print({'rows':len(rows)})


if __name__=='__main__':main()
