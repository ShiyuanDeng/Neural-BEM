"""Joint Laurent deformation/pose inversion with exact checks of local T models."""
from time import perf_counter
import numpy as np
from .deformable_scattering import ShapePoseChart,DeformableEvaluator,LinearizedEvaluator
from .pose_inverse import PoseEvaluator,invert_pose
from .run_scattering_library import fixture
from .inverse import real_stack


def shape_fixture(count=4):
    acq,pose,pose_truth,_=fixture(count)
    directions=[]
    for i,g in enumerate(pose.geometries):
        physical=([{1:.002},{-1:.0015},{-2:.001+.0003j}] if i%2==0 else
                  [{1:.002},{4:.001,-2:.001},{-1:.0015+.0002j}])
        directions.append([{j:v/g.scale for j,v in d.items()} for d in physical])
    chart=ShapePoseChart(pose.geometries,directions,pose.anchors)
    shape_values=[[.6,-.5,.8],[-.5,.7,-.6],[.3,.6,-.7],[-.6,-.5,.5]]
    truth=np.concatenate([np.r_[p,shape_values[i%4]] for i,p in enumerate(pose_truth.reshape(-1,3))])
    return acq,chart,truth,np.zeros(chart.size)


class NodalDeformableEvaluator:
    """Independent full coupled Kress rebuild and reciprocal shape derivative."""
    def __init__(self,chart,acq,frequencies,nodes=64,paired=True):
        self.base=PoseEvaluator(chart,acq,frequencies,backend='nodal_rebuild',nodes=nodes,paired=paired)
        self.chart,self.acq=chart,acq;self.backend='nodal_rebuild';self.work=self.base.work
        self.x=None;self.jac=None

    def forward(self,x):
        return self.base.forward(x)

    def jacobian(self,x):
        self.forward(x)
        if self.x is not None and np.array_equal(self.x,x): return self.jac
        tick=perf_counter()
        from gpr_bem_kress.multicomponent import multicomponent_incident_trace_on_boundary
        from gpr_bem_kress.execution import execution
        centers,angles=self.chart.poses(x);weights=[]
        for curve,g,directions,center,angle in zip(self.base.boundary.components,self.chart.geometries,
                                                   self.chart.directions,centers,angles):
            theta=np.arange(len(curve.points))*2*np.pi/len(curve.points)
            z=curve.points[:,0]+1j*curve.points[:,1]
            delta=[np.full(len(z),.01),np.full(len(z),.01j),1j*(z-center)]
            delta.extend(g.scale*np.exp(1j*angle)*sum(v*np.exp(1j*j*theta) for j,v in d.items())
                         for d in directions)
            weights.append([(a.real*curve.normals[:,0]+a.imag*curve.normals[:,1])*curve.arc_length_weights for a in delta])
        jac=[]
        with execution(kernels='real_bessel'):
            for state in self.base.states:
                d,n=multicomponent_incident_trace_on_boundary(self.base.boundary,state.receivers,state.system.k_exterior,1.)
                ur=state.factors.solve(np.concatenate((d,n),axis=1).T);columns=[]
                contrast=state.system.k_interior**2-state.system.k_exterior**2
                for sl,row in zip(self.base.boundary.component_slices,weights):
                    for w in row:
                        columns.append(self.base.select(contrast*(ur[sl].T@(w[:,None]*state.U[sl]))))
                jac.append(np.stack(columns,axis=-1))
        self.jac=np.stack(jac);self.x=np.array(x,copy=True)
        self.work['jacobian_evaluations']+=1;self.work['jacobian_seconds']+=perf_counter()-tick
        return self.jac


def invert_relinearized(chart,acq,frequencies,observed,initial,*,backend='native',max_outer=15,**options):
    """Optimize a shape-linear scattering model; accept only exact improvements.

    Each outer iteration recompiles candidate shapes and checks the true loss.
    Pose/multiple-scattering nonlinearities remain exact inside each local model.
    Final convergence requires a small gradient from freshly compiled dT.
    """
    tick=perf_counter();exact=DeformableEvaluator(chart,acq,frequencies,backend=backend,**options)
    scale=np.linalg.norm(observed,axis=1)*np.sqrt(len(frequencies))
    def residual(e,x): return real_stack((e.forward(x)-observed)/scale[:,None])
    def gradient(e,x,r): return real_stack(e.jacobian(x)/scale[:,None,None]).T@r
    x=np.array(initial,copy=True);r=residual(exact,x);cost=.5*r@r
    radius=.8;history=[];success=False;inner_seconds=0.;inner_evaluations=0
    lower,upper=chart.bounds()
    for iteration in range(max_outer):
        grad=gradient(exact,x,r)
        # Projected gradient supports solutions on the global parameter bounds.
        feasible=grad.copy()
        feasible[(x<=lower+1e-9)&(grad>0)]=0
        feasible[(x>=upper-1e-9)&(grad<0)]=0
        if np.linalg.norm(feasible,np.inf)<1e-10:
            success=True;break
        model=LinearizedEvaluator(exact,x)
        lo,hi=lower.copy(),upper.copy()
        for sl in chart.slices:
            shape=slice(sl.start+3,sl.stop)
            lo[shape]=np.maximum(lo[shape],x[shape]-radius)
            hi[shape]=np.minimum(hi[shape],x[shape]+radius)
        # Temporary bounds constrain only deformation; global pose limits remain.
        class LocalBounds:
            def bounds(self): return lo,hi
        fitted=invert_pose(LocalBounds(),acq,frequencies,observed,np.clip(x,lo+1e-12,hi-1e-12),
                          evaluator=model,max_nfev=35)
        inner_seconds+=fitted['seconds'];inner_evaluations+=fitted['nfev']
        candidate=np.array(fitted['parameters']);predicted=residual(model,candidate)
        actual=residual(exact,candidate);candidate_cost=.5*actual@actual
        predicted_reduction=cost-.5*predicted@predicted
        ratio=(cost-candidate_cost)/max(predicted_reduction,1e-30)
        accepted=candidate_cost<cost and ratio>.1
        history.append(dict(iteration=iteration,parameters=candidate.tolist(),accepted=bool(accepted),
            actual_residual=float(np.linalg.norm(actual)),model_residual=float(np.linalg.norm(predicted)),
            model_data_discrepancy=float(np.linalg.norm(actual-predicted)),trust_radius=radius,
            reduction_ratio=float(ratio),gradient_inf=float(np.linalg.norm(feasible,np.inf)),
            inner_nfev=fitted['nfev'],elapsed_seconds=perf_counter()-tick))
        if accepted:
            x=candidate;r=actual;cost=candidate_cost
            if ratio>.75: radius=min(1.5,1.6*radius)
        else:
            radius*=.4
            # Exact evaluator's last state is rejected; reset to accepted x.
            r=residual(exact,x)
        if radius<1e-5: break
    final_grad=gradient(exact,x,r)
    return dict(parameters=x.tolist(),seconds=perf_counter()-tick,success=success,
        residual_norm=float(np.linalg.norm(r)),gradient_inf=float(np.linalg.norm(final_grad,np.inf)),
        history=history,outer_trials=len(history),inner_evaluations=inner_evaluations,inner_seconds=inner_seconds,
        work=dict(exact.work),backend='relinearized_'+backend)
