"""One frozen TG-002 circle, relative permittivity four, for preparation only."""
import json
from pathlib import Path
import numpy as np
from scipy.io import savemat
from shapely import contains_xy
from shapely.geometry import Polygon
from experiments.benchmark import scenes as S

REPO=Path(__file__).resolve().parents[3]


def prepare(scene,out):
    out.mkdir(parents=True,exist_ok=False)
    curve=S.truth_fixture(scene);boundary=S.LENGTH*curve.values(8192)
    truth=Polygon(np.column_stack([boundary.real,boundary.imag]))
    x=np.arange(-166,166)*.000625;xx,yy=np.meshgrid(x,x,indexing='ij')
    eps=1+3*contains_xy(truth,xx,yy)
    savemat(out/'geometry.mat',dict(eps_true=eps.astype(float),x_m=x,y_m=x,boundary=boundary,
        forward_cell_m=.000625,inverse_cell_m=.00125,half_width_m=.10375),do_compression=True)
    record=dict(scene=scene,relative_permittivity=4,susceptibility=3,
        source=f'experiments.benchmark.scenes.truth_fixture({scene}); frozen shape and placement',
        coordinate_translation='TG-002 acquisition centre to Fresnel origin; no change to relative placement',
        forward_grid=[332,332],forward_cell_m=.000625,inverse_grid=[166,166],inverse_cell_m=.00125,
        half_width_m=.10375,true_area_mm2=truth.area*1e6,
        true_centroid_mm=[truth.centroid.x*1000,truth.centroid.y*1000],
        boundary_sample_count=len(boundary),positive_grid_nodes=int(np.count_nonzero(eps>1)),
        rasterization='point membership at native TM primary nodes; no truth is supplied to inversion')
    (out/'geometry.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


def main():
    prepare('circle',REPO/'results/csi/preparation/2026-11-17_geometry')


if __name__=='__main__':main()
