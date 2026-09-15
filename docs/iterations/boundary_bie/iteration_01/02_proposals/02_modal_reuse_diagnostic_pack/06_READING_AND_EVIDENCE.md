# Focused reading and evidence boundaries

These references motivate mechanisms and controls. None proves a speedup, inverse-recovery improvement, or first-ever GPR contribution for the proposed code. External publication pages/abstracts were checked on 2026-09-15. No paper's full numerical experiment has been reproduced here.

## S1 — a strong existing transmission baseline

Y. Boubendir, V. Domínguez and C. Turc, **High-order Nyström discretizations for the solution of integral equation formulations of two-dimensional Helmholtz transmission problems**. Preprint 2014; check the publication record for the journal citation.

Source: `https://arxiv.org/abs/1404.1331`

Why it matters: directly relevant high-order Nyström transmission formulations. It prevents treating Kress as a low-order baseline or assuming modal notation alone creates spectral convergence. Read the formulation/discretization assumptions before borrowing a convergence claim. It is not an accuracy certificate for the repository's particular implementation.

## S2 — structured Fourier–Galerkin assembly, not a coordinate relabeling

Y. Jiang, B. Wang and D. Yu, **A fast Fourier-Galerkin method solving boundary integral equations for the Helmholtz equation with exponential convergence**, Numerical Algorithms 88, 1457–1491 (2021). DOI: `10.1007/s11075-021-01082-0`.

Source: `https://link.springer.com/article/10.1007/s11075-021-01082-0`

The publisher's abstract describes convolution/compact splitting and sparse coefficient truncation with stability/convergence results for Helmholtz Dirichlet BIEs. That is the mechanism to understand. A coupled multi-interface transmission operator and its geometry derivatives are not automatically covered. Only the publicly accessible abstract/metadata and displayed material were checked for this packet; a full paper implementation is not claimed.

## S3 — singular operators as coefficient-space building blocks

R. M. Slevinsky and S. Olver, **A fast and well-conditioned spectral method for singular integral equations** (preprint 2015; published 2017).

Source: `https://arxiv.org/abs/1507.00596`

This is a structured spectral singular-integral reference using polynomial/coefficient operators rather than this project's periodic Fourier transmission setup. Read for separation of known singular actions from variable/smooth coefficients. It does not justify copying a Chebyshev/ultraspherical construction unchanged into Müller.

## S4 — analytic geometry dependence

J. Dölz and F. Henríquez, **Parametric Shape Holomorphy of Boundary Integral Operators with Applications** (preprint 2023; revised 2024).

Source: `https://arxiv.org/abs/2305.19853`

The abstract establishes analytic/holomorphic parameter dependence of operators and solutions and discusses sound-soft Helmholtz scattering, reduced models and Bayesian shape inversion. Use it to understand why shape-parametric approximation may exist. It does not supply the useful local radius, inexpensive online evaluation, or derivative error guarantees needed by this proposed diagnostic.

## S5 — reusable solves require identifiable update structure

Y. Zhang and A. Gillman, **A fast direct solver for boundary value problems on locally perturbed geometries**, Journal of Computational Physics 356, 356–371 (2018); preprint 2017.

Source: `https://arxiv.org/abs/1706.01414`

The paper exploits low-rank updates for spatially local boundary modifications. The relevant lesson is to identify the update structure and its construction cost before using a matrix-update formula. Global Fourier deformation is a different regime. Do not import the paper's speed ratios as forecasts.

## S6 — adaptive surrogate optimization is already an established comparison area

T. Keil, L. Mechelli, M. Ohlberger, F. Schindler and S. Volkwein, **A non-conforming dual approach for adaptive Trust-Region Reduced Basis approximation of PDE-constrained optimization** (preprint 2020).

Source: `https://arxiv.org/abs/2006.09297`

Use this as a comparator for later model validity, enrichment and optimization claims, not an instruction to implement a trust-region framework now. An eventual “approximate operator plus periodic rebuild” contribution needs to distinguish itself from this wider literature.

## Repository evidence

The packet's placement/approval/checkout instructions rely on these freshly inspected repository documents:

| Path | Blob SHA inspected |
|---|---|
| `docs/iterations/README.md` | `f8b63f04377cf5e6bf49667c75e30e751a3050b7` |
| `docs/iterations/boundary_bie/README.md` | `196025ed6fe0b7a9d8a9fb17a2d908a08a105d21` |
| `docs/iterations/boundary_bie/iteration_01/02_proposals/01_boundary_bie_research_brief.md` | `f655313efccf4b45bf7dea4719510c1a85049c42` |

The proposal-directory listing contained only the existing `01_boundary_bie_research_brief.md` when checked. Recheck before installing if the branch has advanced.

Earlier conversation inspections additionally established the single-interface derivative versus multi-component FD distinction, separate Fourier/gauge optimizer paths, and TOP-018's 256/512-node qualified case. Revalidate current APIs and saved data locally; this package does not claim to have rerun those experiments or exhaustively audited the latest source tree.

## Reading output expected from the implementation agent

No broad literature review is needed to execute BIE-002. Write at most one short note mapping the chosen projection/structure diagnostic to S1–S3 and stating the transfer limitations. Reading S4–S6 does not release idea 3. Missing paywalled details are a reason not to claim a paper implementation, not a reason to invent a formula.

All equations in the experimental contract that follow by unitary transformation, differentiation or dimensional scaling are supplied as elementary derivations for the discrete diagnostic. The compression thresholds, scene choices, budgets and promotion criteria are proposed experimental design choices, not theorems from these sources.
