"""Experimental coupled dielectric/PEC boundary integral forward check.

Plastic and PEC boundaries in sand; TMz, nonmagnetic, disjoint curves.
Plastic rows use the existing Muller differences. Metal has u_D=0, and its
exterior Dirichlet equation solves for q_N. This single-layer PEC formulation
must avoid interior Dirichlet resonances; it is a bounded experiment, not a
general production replacement or a finite-conductivity metal model.
"""
from __future__ import annotations
import numpy as np
from scipy.special import hankel1,jv
from gpr_bem_kress.operators import build_muller_difference_blocks
from gpr_bem_kress.multicomponent import (
    build_exterior_cross_blocks, multicomponent_incident_trace_on_boundary,
    build_multicomponent_exterior_receiver_operator,
)
from ordered_boundary import OrderedBoundary2D,circle
from periodic_kress import kress_log_weight_matrix
from .mixed_circles import wave


def self_single_layer(curve,k):
    n=curve.num_nodes;h=2*np.pi/n
    speed=curve.arc_length_weights/h
    distance=np.linalg.norm(curve.points[:,None,:]-curve.points[None,:,:],axis=-1)
    diagonal=np.eye(n,dtype=bool)
    safe=distance.copy();safe[diagonal]=1.
    kernel=.25j*hankel1(0,k*safe)
    logarithm=-jv(0,k*safe)/(4*np.pi)
    logarithm[diagonal]=-1/(4*np.pi)
    offsets=(np.arange(n)[:,None]-np.arange(n)[None,:])%n
    periodic_log=np.zeros((n,n));periodic_log[~diagonal]=np.log(4*np.sin(np.pi*offsets[~diagonal]/n)**2)
    smooth=kernel-logarithm*periodic_log
    smooth[diagonal]=.25j-(np.euler_gamma+np.log(k*speed/2))/(2*np.pi)
    return (kress_log_weight_matrix(n)*logarithm+h*smooth)*speed[None,:]


def predict_components(curves,kinds,sources,receivers,frequencies,*,return_details=False):
    curves=tuple(curves);kinds=tuple(kinds)
    if len(curves)!=len(kinds) or any(k not in ('plastic','metal') for k in kinds):
        raise ValueError('Each component requires a plastic/metal label')
    boundary=OrderedBoundary2D(curves)
    total=boundary.num_nodes
    dielectric_slices={};dielectric_nodes=0
    for index,(curve,kind) in enumerate(zip(curves,kinds)):
        if kind=='plastic':
            dielectric_slices[index]=slice(dielectric_nodes,dielectric_nodes+curve.num_nodes)
            dielectric_nodes+=curve.num_nodes
    slices=boundary.component_slices
    values=[];details=[]
    for frequency in frequencies:
        ke,ki=wave(frequency,6),wave(frequency,3)
        matrix=np.zeros((total+dielectric_nodes,total+dielectric_nodes),complex)
        # Rows: all Dirichlet equations, then dielectric Neumann equations.
        # Columns: dielectric Dirichlet traces, then all Neumann traces.
        for i,(curve,kind) in enumerate(zip(curves,kinds)):
            rd=slices[i]
            cq=slice(dielectric_nodes+rd.start,dielectric_nodes+rd.stop)
            if kind=='plastic':
                cu=dielectric_slices[i]
                rn=slice(total+cu.start,total+cu.stop)
                self_blocks=build_muller_difference_blocks(curve,ke,ki)
                matrix[rd,cu]=np.eye(curve.num_nodes)-self_blocks.delta_k
                matrix[rd,cq]=self_blocks.delta_v
                matrix[rn,cu]=-self_blocks.delta_t
                matrix[rn,cq]=np.eye(curve.num_nodes)+self_blocks.delta_kp
            else:
                matrix[rd,cq]=self_single_layer(curve,ke)
            for j,source in enumerate(curves):
                if i==j:continue
                cross=build_exterior_cross_blocks(curve,source,ke)
                sj=slices[j];qj=slice(dielectric_nodes+sj.start,dielectric_nodes+sj.stop)
                matrix[rd,qj]=cross.v
                if j in dielectric_slices:matrix[rd,dielectric_slices[j]]=-cross.k
                if kind=='plastic':
                    matrix[rn,qj]=cross.kp
                    if j in dielectric_slices:matrix[rn,dielectric_slices[j]]=-cross.t
        uinc,qinc=multicomponent_incident_trace_on_boundary(boundary,sources,ke,1.)
        rhs=np.concatenate((uinc,*[qinc[:,slices[i]] for i in dielectric_slices]),axis=1).T
        state=np.linalg.solve(matrix,rhs)
        u=np.zeros((total,len(sources)),complex)
        for i,sl in dielectric_slices.items():u[slices[i]]=state[sl]
        q=state[dielectric_nodes:]
        operator=build_multicomponent_exterior_receiver_operator(boundary,receivers,ke)
        values.append(np.diag(operator.evaluate(u.T,q.T).scattered))
        details.append(dict(relative_residual=float(np.linalg.norm(matrix@state-rhs)/np.linalg.norm(rhs))))
    prediction=np.stack(values,axis=1)
    return (prediction,details) if return_details else prediction


def predict_boundary(plastic,metal,sources,receivers,frequencies,*,return_details=False):
    return predict_components((plastic,metal),('plastic','metal'),sources,receivers,frequencies,
                              return_details=return_details)


def predict(parameters,sources,receivers,frequencies,*,nodes=64,kinds=('plastic','metal'),return_details=False):
    q=np.asarray(parameters).reshape(-1,3)
    curves=[circle(tuple(row[:2]),row[2],component_id=label).discretize(nodes)
            for row,label in zip(q,[f'component_{i}' for i in range(len(q))])]
    return predict_components(curves,kinds,sources,receivers,frequencies,return_details=return_details)
