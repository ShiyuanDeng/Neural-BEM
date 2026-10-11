"""Kernel-differenced Muller quadrature on IBIM's boundary object -- a scoped
diagnostic, not an oracle. See ``kernel_diff_tmz`` for what this is and is not.

Sibling of ``nystrom_ref``, ``gpr_bem_ref``/``gpr_bem_mod``, deliberately: its
whole point is testing whether the kernel-differencing trick can be hosted
against IBIM's own boundary data shape, so it must not import the machinery
it is trying to validate.
"""

from .kernel_diff_tmz import KernelDiffSolution, solve_transmission_on_circle

__all__ = ["KernelDiffSolution", "solve_transmission_on_circle"]
