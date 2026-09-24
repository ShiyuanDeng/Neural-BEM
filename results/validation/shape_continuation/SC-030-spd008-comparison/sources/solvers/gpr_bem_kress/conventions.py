"""Frozen convention record for the Kress/Nyström solver."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class MullerConvention:
    """Human- and machine-readable meanings of every visible operator block."""

    green_function: str
    time_dependence: str
    orientation: str
    normal: str
    single_layer: str
    double_layer: str
    adjoint_double_layer: str
    hypersingular_t: str
    hypersingular_w: str
    jumps: str
    unknowns: str
    neumann_trace: str
    difference: str
    system: str
    right_hand_side: str
    exterior_representation: str
    weight_ownership: str

    def as_mapping(self) -> Mapping[str, str]:
        return MappingProxyType(asdict(self))


PROJECT_MULLER_CONVENTION = MullerConvention(
    green_function="G_k(x,y) = (i/4) H_0^(1)(k |x-y|)",
    time_dependence="exp(-i omega t)",
    orientation="one counterclockwise inclusion boundary",
    normal="unit normal points from the inclusion into the exterior for both media",
    single_layer="V phi = integral_Gamma G_k(x,y) phi(y) ds_y",
    double_layer="K phi = p.v. integral_Gamma dG_k(x,y)/dn_y phi(y) ds_y",
    adjoint_double_layer="Kp phi = p.v. integral_Gamma dG_k(x,y)/dn_x phi(y) ds_y",
    hypersingular_t="T phi = f.p. integral_Gamma d2G_k(x,y)/(dn_x dn_y) phi(y) ds_y",
    hypersingular_w="W = -T in gpr_bem_mod vocabulary",
    jumps="V, K, Kp, and T are principal operators; no trace jump is included",
    unknowns="[u_D, u_N], total Dirichlet trace then ordinary outward normal derivative",
    neumann_trace="u_N is unscaled because the supported TMz media are nonmagnetic",
    difference="Delta X = X_exterior - X_interior",
    system="[[I-Delta K, Delta V], [-Delta T, I+Delta Kp]]",
    right_hand_side="positive incident Dirichlet and outward-normal traces",
    exterior_representation="u_sc = D_exterior u_D - S_exterior u_N",
    weight_ownership="nodal unknowns are unweighted; each matrix includes source ds exactly once",
)


__all__ = ["MullerConvention", "PROJECT_MULLER_CONVENTION"]
