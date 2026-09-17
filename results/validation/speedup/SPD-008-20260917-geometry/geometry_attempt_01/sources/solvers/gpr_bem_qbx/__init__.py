"""Archived full-row QBX ``T`` diagnostics for the shared kdiff solver.

This package deliberately does not carry a second copy of the boundary,
system, solve, or receiver code. It is not a production solver or a normal
solver-selector option. To reproduce a controlled diagnostic, pass
:class:`FullRowQBX` to the public ``gpr_bem_kdiff`` solve function::

    gpr_bem_kdiff.solve_ibim_tmz_total_field_batch(
        ...,
        t_assembly=FullRowQBX(source=...),
    )

The older near-band/four-block implementation remains reproducible in Git
history and documented validation results, but is not a live solver API. See
``docs/qbx_closure.md`` for the measured negative result, limitations, and
reopening criteria.
"""

from .full_row_t import (
    ComponentParameterizedFourierSources,
    FourierComponent,
    FullRowQBX,
    IDWProlongation,
    ParameterizedFourierSources,
    RawSDFBandSources,
    SameNodeSources,
)
__all__ = [
    "ComponentParameterizedFourierSources",
    "FourierComponent",
    "FullRowQBX",
    "IDWProlongation",
    "ParameterizedFourierSources",
    "RawSDFBandSources",
    "SameNodeSources",
]
