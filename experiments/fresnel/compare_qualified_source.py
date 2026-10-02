"""Matched single-cylinder low-frequency inverse after incident-model qualification.

Both arms use the original K=2 Cartesian parameterization, initialization,
regularization, bounds and35-evaluation cap. Incident coefficients are frozen.
"""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import hashlib
import argparse
import json
from pathlib import Path
import time
import numpy as np
from scipy.constants import c
from scipy.optimize import least_squares
from solvers.io.fresnel2001 import load_fresnel2001,calibrate_line_sources
from .run_fresnel2001 import (ContinuationObjective,coefficient_slots,curve_from_parameters,
    coefficient_directions,geometry_metrics,forward,relative_error)
from .multipole_forward import solve_multipole_forward,linearize_multipole_forward
from .qualify_sources import ROOT,OUTPUT,save


class MultipoleObjective(ContinuationObjective):
    def __init__(self,data,coefficients,indices):
        super().__init__(data,None,indices,2,64,.1)
        self.coefficients=coefficients

    def evaluate(self,parameters):
        if self.cached is not None and np.array_equal(parameters,self.cached[0]):return self.cached
        curve=curve_from_parameters(parameters,self.mode,self.nodes)
        residuals=[];jacobians=[];errors=[]
        for fi in self.indices:
            k=2*np.pi*self.data.frequencies_hz[fi]/c
            base=solve_multipole_forward(curve,self.data.source_points,self.data.receiver_points,k,self.coefficients[fi])
            measured=self.data.scattered[fi];scale=np.linalg.norm(measured)*np.sqrt(len(self.indices))
            predicted=self.data.select_receiver_pairs(base.scattered_receiver)
            residual=(predicted-measured).ravel()/scale
            jac=np.column_stack([self.data.select_receiver_pairs(linearize_multipole_forward(base,d)).ravel()/scale
                for d in coefficient_directions(curve,self.mode)])
            residuals.extend((residual.real,residual.imag));jacobians.extend((jac.real,jac.imag))
            errors.append(relative_error(predicted,measured))
        residuals.append(self.reg*parameters);jacobians.append(np.diag(self.reg))
        self.evaluations+=1
        self.cached=(parameters.copy(),np.concatenate(residuals),np.vstack(jacobians),errors)
        return self.cached


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--maximum-frequency',type=int,choices=(1,3,4),default=4)
    args=parser.parse_args()
    maximum=args.maximum_frequency
    started=time.perf_counter()
    qualification=json.loads((OUTPUT/'qualification.json').read_text())
    entries=qualification['local_aperture_cases']['single']['frequencies'][:min(maximum,3)]
    if maximum==4:
        higher=json.loads((OUTPUT/'higher_order_audit.json').read_text())
        extra=json.loads((OUTPUT/'position_pair_4ghz.json').read_text())
        if not extra['cases']['single'][0]['joint_operator_qualified']:
            raise ValueError('4GHz joint operator gate failed.')
        if extra['higher_order_audit_sha256']!=hashlib.sha256((OUTPUT/'higher_order_audit.json').read_bytes()).hexdigest():
            raise ValueError('4GHz joint audit used different calibration coefficients.')
        row=higher['cases']['single']['frequencies'][0]
        order=row['selected_full_rank_order']
        selected=next(r for r in row['candidates'] if r['order']==order)
        entries.append(dict(selected_order=order,candidates={order:selected},gates=extra['cases']['single'][0]['other_source_gates']))
    if maximum==1:
        if not entries[0]['numerically_qualified']:raise ValueError('1GHz incident gates failed.')
    else:
        joint=json.loads((OUTPUT/'position_pair_qualification.json').read_text())
        if joint['qualification_sha256']!=hashlib.sha256((OUTPUT/'qualification.json').read_bytes()).hexdigest():
            raise ValueError('Joint position audit used different incident qualification.')
        if not all(r['joint_operator_qualified'] for r in joint['cases']['single'][:maximum]):
            raise ValueError('Joint incident/receiver operator gates have not passed.')
    coefficients=[]
    for entry in entries:
        source=entry['candidates'][entry['selected_order']]
        coefficients.append(np.array(source['coefficients_real'])+1j*np.array(source['coefficients_imag']))
    data=load_fresnel2001(ROOT/'data/fresnel/dielTM_dec8f.exp')
    if data.source_sha256!=qualification['local_aperture_cases']['single']['data_sha256']:
        raise ValueError('Incident qualification used different data bytes.')
    calibration=calibrate_line_sources(data)
    slots=coefficient_slots(2);initial=np.zeros(len(slots))
    low,high=np.full(len(slots),-1.),np.full(len(slots),1.)
    for j,(kind,m,d) in enumerate(slots):
        if m==0:low[j],high[j]=-60.,60.
        elif (kind,m,d) in [('cos',1,0),('sin',1,1)]:initial[j],low[j],high[j]=25.,8.,40.
        elif m==1:low[j],high[j]=-4.,4.
    report=dict(maximum_frequency_ghz=maximum,scope='conditional single-cylinder source-model comparison; full1–8GHz continuation remains unqualified',
        data_sha256=data.source_sha256,qualification_sha256=hashlib.sha256((OUTPUT/'qualification.json').read_bytes()).hexdigest(),
        source_order=[entry['selected_order'] for entry in entries],source_calibration_uses='incident-only coefficients frozen before geometry fitting',
        source_gates=[entry['gates'] for entry in entries],position_treatment='incident and receiver Green operators varied consistently for1–3GHz qualification',common_settings=dict(nodes=64,mode=2,regularization=.1,max_nfev=35,
        initial_parameters_mm=initial,bounds_mm=[low,high],epsr=3.),arms={})
    arrays={}
    for name in ('opposite_line','local_multipole'):
        local_started=time.perf_counter()
        parameters=initial.copy();stages=[]
        start_frequency=0
        if maximum==4:
            prefix_path=OUTPUT/'inverse_3ghz.json'
            prefix=json.loads(prefix_path.read_text())
            if prefix['data_sha256']!=data.source_sha256 or prefix['qualification_sha256']!=report['qualification_sha256']:
                raise ValueError('Reusable1–3GHz prefix used different data or incident coefficients.')
            for path,digest in prefix['source_sha256'].items():
                if path!=str(Path(__file__).relative_to(ROOT)) and hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:
                    raise ValueError(f'Reusable prefix core source changed:{path}')
            prior=prefix['arms'][name]
            parameters=np.array(prior['parameters_mm']);stages=prior['stages'].copy();start_frequency=3
            report['reused_prefix']=dict(path=str(prefix_path.relative_to(ROOT)),sha256=hashlib.sha256(prefix_path.read_bytes()).hexdigest(),
                rationale='Same incident coefficients, geometry, core operators and objective through3GHz; only4GHz stage newly evaluated')
        for stop in range(start_frequency,maximum):
            indices=list(range(stop+1))
            objective=(ContinuationObjective(data,calibration,indices,2,64,.1) if name=='opposite_line'
                       else MultipoleObjective(data,coefficients,indices))
            fit=least_squares(objective.fun,parameters,jac=objective.jac,bounds=(low,high),x_scale='jac',
                max_nfev=35,ftol=1e-7,xtol=1e-7,gtol=1e-7)
            parameters=fit.x.copy()
            stages.append(dict(maximum_frequency_ghz=stop+1,parameters_mm=fit.x,status=int(fit.status),
                nfev=fit.nfev,objective_evaluations=objective.evaluations,
                relative_scattered_error=objective.evaluate(fit.x)[3]))
        curve=curve_from_parameters(fit.x,2,64)
        fine=curve_from_parameters(fit.x,2,128)
        errors=[];changes=[];predictions=[]
        for fi in range(maximum):
            if name=='opposite_line':
                coarse_result=forward(data,calibration,curve,fi)
                fine_result=forward(data,calibration,fine,fi)
            else:
                k=2*np.pi*data.frequencies_hz[fi]/c
                coarse_result=solve_multipole_forward(curve,data.source_points,data.receiver_points,k,coefficients[fi])
                fine_result=solve_multipole_forward(fine,data.source_points,data.receiver_points,k,coefficients[fi])
            coarse=data.select_receiver_pairs(coarse_result.scattered_receiver)
            refined=data.select_receiver_pairs(fine_result.scattered_receiver)
            errors.append(relative_error(refined,data.scattered[fi]))
            changes.append(relative_error(coarse,refined));predictions.append(refined)
        row=dict(parameters_mm=fit.x,geometry=geometry_metrics(fine),status=int(fit.status),message=fit.message,
            nfev=fit.nfev,objective_evaluations=objective.evaluations,stages=stages,relative_scattered_error=errors,
            newly_evaluated_stage_count=maximum-start_frequency,
            coarse_to_refined_change=changes,seconds=time.perf_counter()-local_started,
            active_bounds=[slots[i] for i in np.flatnonzero(np.isclose(fit.x,low,atol=1e-3)|np.isclose(fit.x,high,atol=1e-3))])
        report['arms'][name]=row
        arrays[name+'_boundary_m']=fine.points;arrays[name+'_prediction']=np.array(predictions)
        print(json.dumps(row,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x)),flush=True)
    report['elapsed_seconds']=time.perf_counter()-started
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__),ROOT/'experiments/fresnel/multipole_forward.py',ROOT/'experiments/fresnel/multipole_sources.py',
        ROOT/'experiments/fresnel/run_fresnel2001.py',ROOT/'solvers/gpr_bem_kress/shape_derivative.py')}
    save(OUTPUT/f'inverse_{maximum}ghz.json',report)
    np.savez_compressed(OUTPUT/f'inverse_{maximum}ghz.npz',**arrays)


if __name__=='__main__':main()
