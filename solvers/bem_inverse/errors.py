"""Stable fitting exceptions and returned status names."""
NORMAL_RETURN = "NORMAL_OPTIMIZER_RETURN"
STAGE_QUOTA = "STAGE_QUOTA_REACHED"


class UpdateRefused(ValueError):
    """A geometry trial cannot be built; reason is a stable recorded label."""

    def __init__(self, reason, detail):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def refusal_from_value_error(exc):
    """Compatibility translation for older curve operations raising ValueError."""
    text = str(exc)
    if "self-intersects" in text:
        return UpdateRefused("self_intersection", text)
    if "projection unresolved" in text:
        return UpdateRefused("unresolved_projection", text)
    return UpdateRefused("irregular_parameterization", text)

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

