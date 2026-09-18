# LAU-002 — reproduce published Fourier compression before judging transfer

- **Approval status:** APPROVED. The user's 2026-09-17 instruction, "yep,
  lemme know when we catch up with literature progress", authorizes the preceding
  recommendation: reproduce published compression, then test transmission and
  derivatives. This direct instruction supersedes the generic named-ID approval
  wording for this bounded work. No branch or worktree creation is authorized.
- **Execution status:** COMPLETE, 2026-09-17. [Closeout](../iteration_04/01_results.md):
  scalar construction/convergence reproduced with unresolved table discrepancies;
  conditional numerical transmission transfer, without a speed claim.
- **Question:** can we reproduce a published compression construction, and where
  does its transfer to our qualified Muller operator cease to work?
- **Primary source:** Jiang, Wang and Yu (2021), Numerical Algorithms 88,
  1457–1491, DOI 10.1007/s11075-021-01082-0, Sections 2–6; full PDF obtained from
  the publisher. Cai (2012), DOI 10.1007/s10543-012-0380-6, is a supporting
  predecessor, not an interchangeable algorithm.
- **Baseline:** full Fourier scalar single-layer discretization and independently
  evaluated physical kernels; qualified LAU-001-R1 native transmission and Kress
  controls. Existing numerical sources and bundles remain unchanged.
- **Intervention:** reproduce the 2021 diagonal-convolution split and exact index
  set, translating double-kernel Fourier indices into matrix row/input indices.
  First reproduce mask counts and ellipse manufactured-density convergence.
  Record discrepancies with printed tables instead of tuning them away.
- **Controls:** explicit Fourier normalization, independent quadrature/window
  refinements, analytic circle eigenvalues, exact manufactured-density Fourier
  coefficients when available, independent physical field/derivative references.
  Published convergence, our accuracy gates and measured cost stay distinct.
- **Conditional transfer:** after scalar accuracy and mask-index tests pass,
  apply the published index geometry to all four transmission blocks. This is
  labelled a numerical extension; the scalar theorem does not prove it valid.
  Use circle, ellipse, star, asymmetric star at ka=2/5; test the six existing
  shape directions and physical gates. Keep the original masks as historical
  controls. Any changed split or scaling must be explicit.
- **File/API map:** new isolated `experiments/laurent_literature/` owns scalar
  reference assembly, masks, tests and drivers; imports existing Laurent/Kress
  helpers read-only. No production API/default or old evidence changes.
- **Validation before campaigns:** exact circle single-layer symbols, split
  reconstruction, independent smooth-kernel Fourier signs and index counts;
  scalar RHS from a larger reference space, including unresolved density tail.
  Transfer derivatives must differentiate the actual frozen compressed model.
- **Budget:** per campaign at most 30 minutes, 6 GiB peak RSS, 160 physical
  assemblies and 600 factorizations. Pilot first; fresh output directories;
  preserve failures and source/config/environment hashes. No inverse campaign.
- **Completion:** a source-to-code map and reproducible convergence/count
  evidence, followed by an explicitly scoped transmission-transfer verdict.
  Do not claim the entire literature or its fast-assembly complexity reproduced
  merely because dense-then-masked matrices give accurate answers.
- **Pilot amendment, before the transfer campaign:** all eight pilot full
  controls and 24 compressed-model finite differences qualify; literal masks
  at the small trace dimensions fail. The campaign additionally restricts the
  same published mask from n*=2n,4n,8n,16n to the existing qualified trace space,
  with mu=1.1. This isolates aggressive mask resolution from trace resolution.
  It is explicitly an extension, not a reproduction of the paper's coupled
  n/trace choice. Original gates and resource ceilings are unchanged.
- **Artifacts:** `results/validation/laurent/LAU-002-<timestamp>/`; closeout opens
  iteration 04. Owner: Codex. Independent reviewer: unassigned.
