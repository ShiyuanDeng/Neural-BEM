"""Select a standalone forward function, preserving external solver adapters."""
from functools import partial


def bind_forward_solve(physics):
    """Bind execution/cache state once; the returned function runs one frequency."""
    from . import modal_muller, nodal_kress
    if type(physics) is modal_muller.ModalMuller and 'evaluate' not in vars(physics):
        return partial(modal_muller.forward_solve, context=physics)
    if type(physics) is nodal_kress.NodalKress and 'evaluate' not in vars(physics):
        return partial(nodal_kress.forward_solve, context=physics)
    if physics is not None:
        return physics.evaluate  # Research services and external/test implementations.
    from ..continuation.forward import solve

    def forward_solve(curve, observation, contrast, resolution):
        return solve(curve, observation.wavenumber, contrast, observation.acquisition, resolution)

    return forward_solve
