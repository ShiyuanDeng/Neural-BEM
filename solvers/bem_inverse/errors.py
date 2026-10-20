"""Stable fitting exceptions and returned status names."""
NORMAL_RETURN = "NORMAL_OPTIMIZER_RETURN"
STAGE_QUOTA = "STAGE_QUOTA_REACHED"

class Stop(RuntimeError):
    code = "IMPLEMENTATION_ERROR"



class StageQuota(Stop):
    code = STAGE_QUOTA



class TrialSolveCap(Stop):
    code = "TRIAL_SOLVE_CAP"



class TrialWallLimit(Stop):
    code = "TRIAL_WALL_LIMIT"



class NumericalFailure(Stop):
    code = "NUMERICAL_FAILURE"



class GeometryProposalCap(Stop):
    code = 'GEOMETRY_PROPOSAL_CAP'


for _type in (Stop, StageQuota, TrialSolveCap, TrialWallLimit, NumericalFailure, GeometryProposalCap,):
    _type.__module__ = "bem_inverse.continuation.lm_backend"
