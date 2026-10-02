"""Check the predicted incident/receiver phase cancellation with physical units.

For an outward receiver displacement dR, calibration of the near-origin
incident field adds exp(-ik dR); receiver propagation adds exp(+ik dR).
The leading phase cancels. This full-BIE test keeps both legs consistent.
It uses only incident samples and two fixed analytic controls, no target data.
"""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import hashlib
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.constants import c
from ordered_boundary import circle
from solvers.io.fresnel2001 import load_fresnel2001
from .multipole_sources import multipole_basis,fit_multipoles
from .multipole_forward import solve_multipole_forward
from .qualify_sources import ROOT,OUTPUT,relative,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fourth-frequency',action='store_true')
    args=parser.parse_args()
    qualification=json.loads((OUTPUT/'qualification.json').read_text())
    higher=json.loads((OUTPUT/'higher_order_audit.json').read_text()) if args.fourth_frequency else None
    report=dict(contract='Incident calibration and receiver propagation perturbed consistently; no scattered measurements used',
        maximum_allowed_relative_change=.05,
        synthetic_controls=[dict(center_m=[0.,0.],radius_m=.02),dict(center_m=[.03,-.025],radius_m=.02)],
        cases={},work=dict(control_frequency_solves=0,underlying_dense_factorizations=0),
        qualification_sha256=hashlib.sha256((OUTPUT/'qualification.json').read_bytes()).hexdigest())
    window=(np.arange(49)>=12)&(np.arange(49)<=36)
    for label,filename in [('single','dielTM_dec8f.exp'),('twin','twodielTM_8f.exp')]:
        data=load_fresnel2001(ROOT/'data/fresnel'/filename)
        rows=[]
        for fi in ([3] if args.fourth_frequency else range(3)):
            q=qualification['local_aperture_cases'][label]['frequencies'][fi]
            if args.fourth_frequency:
                ceiling=higher['cases'][label]['frequencies'][0]
                order=ceiling['selected_full_rank_order']
                if order is None:raise ValueError('No full-rank4GHz incident candidate qualifies.')
                selected=next(r for r in ceiling['candidates'] if r['order']==order)
            else:
                order=q['selected_order'];selected=q['candidates'][order]
            coeff=np.array(selected['coefficients_real'])+1j*np.array(selected['coefficients_imag'])
            k=2*np.pi*data.frequencies_hz[fi]/c;incident=data.incident[fi].mean(axis=0)
            perturbations=[]
            for control in report['synthetic_controls']:
                curve=circle(tuple(control['center_m']),control['radius_m']).discretize(64)
                base=solve_multipole_forward(curve,data.source_points,data.receiver_points,k,coeff)
                report['work']['control_frequency_solves']+=1
                base_values=data.select_receiver_pairs(base.scattered_receiver)
                for ds,dr in [(-.003,0),(.003,0),(0,-.003),(0,.003)]:
                    sources=data.source_points*(1+ds/.72)
                    receivers=data.receiver_points*(1+dr/.76)
                    paired=receivers[data.receiver_labels[0]-1]
                    a=multipole_basis(paired,sources[0],k,order)[0]
                    fit=fit_multipoles(a[window],incident[window])
                    perturbed=solve_multipole_forward(curve,sources,receivers,k,fit.coefficients)
                    report['work']['control_frequency_solves']+=1
                    change=relative(data.select_receiver_pairs(perturbed.scattered_receiver),base_values)
                    perturbations.append(dict(control=control,source_radius_delta_m=ds,receiver_radius_delta_m=dr,
                        relative_scattered_prediction_change=change))
            maximum=max(p['relative_scattered_prediction_change'] for p in perturbations)
            nominal_gates=({'full_rank':selected['rank']==2*order+1,'incident_ceiling_eligible':selected['nominal_eligible']}
                if args.fourth_frequency else {key:value for key,value in q['gates'].items() if key!='target_position'})
            passed=all(nominal_gates.values()) and maximum<report['maximum_allowed_relative_change']
            rows.append(dict(frequency_hz=data.frequencies_hz[fi],source_order=order,
                original_target_position_gate=q['gates']['target_position'],other_source_gates=nominal_gates,
                maximum_joint_prediction_change=maximum,joint_operator_qualified=passed,perturbations=perturbations))
            print(label,fi+1,maximum,passed,flush=True)
        report['cases'][label]=rows
    # The isolated adapter constructs one production reference and one new RHS
    # solution, hence two dense factorizations per control call.
    report['work']['underlying_dense_factorizations']=2*report['work']['control_frequency_solves']
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path(__file__),ROOT/'experiments/fresnel/multipole_forward.py',ROOT/'experiments/fresnel/multipole_sources.py')}
    if args.fourth_frequency:
        report['higher_order_audit_sha256']=hashlib.sha256((OUTPUT/'higher_order_audit.json').read_bytes()).hexdigest()
    save(OUTPUT/('position_pair_4ghz.json' if args.fourth_frequency else 'position_pair_qualification.json'),report)


if __name__=='__main__':main()
