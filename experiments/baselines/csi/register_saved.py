"""Rescore accepted measured images using the read, fixed signed frame map."""
import json
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from shapely.geometry import Point
from experiments.baselines.csi.registered_metrics import score_field

REPO=Path(__file__).resolve().parents[3]


def main():
    source=REPO/'results/csi/fresnel/2026-11-17_diel_tm/final_contrast.mat'
    data=loadmat(source,simplify_cells=True)
    out=REPO/'results/csi/preparation/2026-11-17_frame';out.mkdir(parents=True,exist_ok=True)
    truth=Point(0,.03).buffer(.015,quad_segs=4096)
    rows=[]
    for index,method in enumerate(['MF-CC-CSI','MF-MR-CSI','CSI'],1):
        scores,_=score_field(data[f'chi{index}'][-1],tuple(int(x) for x in data['csi_pars']['Ninv'][:2]),
            data['grid_x_primary_m'],data['grid_y_primary_m'],truth)
        rows.append(dict(method=method,scores=scores))
    record=dict(source=str(source.relative_to(REPO)),truth=dict(radius_mm=15,centre_numerical_mm=[0,30],
        relative_permittivity=3,nominal_offset='about 30 mm, not exact metrology'),
        drawing_to_numerical_matrix=[[0,1],[-1,0]],
        basis='right-handed signed clockwise quarter-turn of the unlabelled sketch; angle zero is numerical +x and positive sine is +y',
        sources=['https://doi.org/10.1088/0266-5611/17/6/301',
                 'https://www.fresnel.fr/perso/belkebir/Articles/Ip01_Belkebir.pdf'],
        sign_check='Database first author Belkebir with Tijhuis, same dielTM_dec8f file: section 4.2.1 and Figure 6 of their 2001 inversion paper place it at positive y; the search domain is centred at y=2.8 cm.',
        no_fitted_alignment=True,methods=rows)
    (out/'registered_scores.json').write_text(json.dumps(record,indent=2)+'\n')
    for row in rows:print(row['method'],json.dumps(row['scores'][0]))


if __name__=='__main__':main()
