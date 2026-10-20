"""Directed acceptance of a finite coefficient update, without sample fallback.

Construction/refinement accuracy is the caller's separate responsibility.
The three roles are checked in order, stopping at the first unproved role.
"""
from .interval_geometry import IntervalGeometry


def certify_pair(accepted, candidate, moved_coarse, moved_fine, base, *, verifier=None):
    verifier=IntervalGeometry() if verifier is None else verifier
    if base.get('curve_sha256')!=verifier.curve_key(accepted):
        raise ValueError('Base certificate does not belong to the accepted curve.')
    checks=[]
    reference_proof,reference_curve=base,accepted
    for role,curve in [('moved_coarse',moved_coarse),('moved_fine',moved_fine),('candidate',candidate)]:
        if role=='candidate':
            reference_proof,reference_curve=base,accepted
        cheap=verifier.increment(reference_proof,reference_curve,curve)
        if cheap['outcome']=='valid':
            proof=dict(cheap,tier='direct_increment',role=role)
        else:
            full=verifier.certify(curve)
            proof=dict(full,tier='arc_range_cover',role=role,increment_attempt=cheap,
                       total_seconds=cheap['seconds']+full['seconds'])
        checks.append(proof)
        if proof['outcome']!='valid':
            return dict(accepted=False,reason='unproved_'+role,checks=checks)
        reference_proof,reference_curve=proof,curve
    return dict(accepted=True,reason='all_three_roles_proved',checks=checks)
