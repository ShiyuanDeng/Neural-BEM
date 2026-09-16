"""Noise-whitened information after quotienting calibration and other nuisance.

All compared plans are connected regular bipartite graphs. They therefore have
the SAME cycle dimension, per-antenna counts, and total measurement count.
Design swaps also preserve a predeclared physical-offset histogram.
"""
import numpy as np

from .model import TARGET, NUISANCE, incidence, realify


def project_out(jac, nuisance, rtol=1e-11):
    if nuisance.shape[1] == 0:
        return jac.copy(), 0
    u, s, _ = np.linalg.svd(nuisance, full_matrices=False)
    rank = int(np.count_nonzero(s > rtol*s[0])) if s.size and s[0] else 0
    u = u[:, :rank]
    return jac-u@(u.conj().T@jac), rank


def shape_information(y, jac, mask, sigma, calibrate=True):
    """Profile arbitrary complex gains at each frequency, then real geometry/material.

    sigma is the standard deviation of EACH real/imaginary noise component.
    No damping/prior enters the projection. Returned Fisher matrix is local.
    """
    edges = np.argwhere(mask)
    b = incidence(edges, mask.shape[0])
    projected, ranks = [], []
    for f in range(len(y)):
        j = jac[f][mask]/sigma[f]
        if calibrate:
            # Complex span equals the real span of both amplitude and phase.
            n = y[f][mask, None]*b/sigma[f]
            j, rank = project_out(j, n)
        else:
            rank = 0
        projected.append(realify(j))
        ranks.append(rank)
    j = np.concatenate(projected)
    target, nuisance_rank = project_out(j[:, TARGET], j[:, NUISANCE])
    gram = target.T@target
    eig = np.maximum(np.linalg.eigvalsh(gram), 0.)
    return dict(gram=gram, eigenvalues=eig, jacobian=target,
                calibration_complex_ranks=ranks, other_nuisance_rank=nuisance_rank)


def graph_record(mask, offset_bins=None):
    n, m = mask.shape
    unseen = set(range(n+m))
    components = 0
    while unseen:
        components += 1
        frontier = [unseen.pop()]
        while frontier:
            v = frontier.pop()
            neighbors = (np.flatnonzero(mask[v])+n if v < n else np.flatnonzero(mask[:, v-n]))
            for neighbor in neighbors:
                if int(neighbor) in unseen:
                    unseen.remove(int(neighbor))
                    frontier.append(int(neighbor))
    record = dict(edges=int(mask.sum()), components=components,
                  cycle_dimension=int(mask.sum()-n-m+components),
                  receiver_counts=mask.sum(axis=1).tolist(), transmitter_counts=mask.sum(axis=0).tolist())
    if offset_bins is not None:
        record["offset_histogram"] = np.bincount(offset_bins[mask], minlength=int(offset_bins.max())+1).tolist()
    return record


def uniform_plan(n=12):
    mask = np.zeros((n, n), bool)
    for shift in (0, 2, 5, 8):
        mask[np.arange(n), (np.arange(n)+shift)%n] = True
    return mask


def offset_categories(fixture):
    offsets = np.abs(fixture.receivers[:, None, 0]-fixture.sources[None, :, 0])
    return np.digitize(offsets, [.06, .14, .26])


def swap_proposal(mask, bins, rng):
    edges = np.argwhere(mask)
    r1, s1 = edges[rng.integers(len(edges))]
    r2, s2 = edges[rng.integers(len(edges))]
    if r1 == r2 or s1 == s2 or mask[r1, s2] or mask[r2, s1]:
        return None
    if sorted((bins[r1, s1], bins[r2, s2])) != sorted((bins[r1, s2], bins[r2, s1])):
        return None
    candidate = mask.copy()
    candidate[r1, s1] = candidate[r2, s2] = False
    candidate[r1, s2] = candidate[r2, s1] = True
    if graph_record(candidate)["components"] != 1:
        return None
    return candidate


def random_plan(base, bins, seed, accepted_swaps=300):
    rng = np.random.default_rng(seed)
    mask = base.copy()
    accepted = 0
    for _ in range(accepted_swaps*100):
        proposal = swap_proposal(mask, bins, rng)
        if proposal is not None:
            mask = proposal
            accepted += 1
            if accepted == accepted_swaps:
                return mask
    raise RuntimeError("Insufficient valid degree/offset-preserving random swaps")


def score_plan(mask, prior, calibrate):
    # Mean log determinant over declared prior scenarios. The tiny floor avoids
    # log(0); it is NOT used in the information projection or reported CRLB.
    scores = []
    for y, jac, sigma in prior:
        eig = shape_information(y, jac, mask, sigma, calibrate)["eigenvalues"]
        scores.append(np.log(np.maximum(eig, 1e-20)).sum())
    return float(np.mean(scores))


def optimize_plan(starts, bins, prior, calibrate, seed, proposals=1800):
    """Matched-budget local search; both design criteria see the same starts."""
    rng = np.random.default_rng(seed)
    records, winners = [], []
    for start in starts:
        mask = start.copy()
        score = score_plan(mask, prior, calibrate)
        initial = score
        valid, accepted = 0, 0
        for _ in range(proposals):
            candidate = swap_proposal(mask, bins, rng)
            if candidate is None:
                continue
            valid += 1
            next_score = score_plan(candidate, prior, calibrate)
            if next_score > score+1e-10:
                mask, score = candidate, next_score
                accepted += 1
        winners.append((score, mask))
        records.append(dict(initial_score=initial, final_score=score,
                            attempted=proposals, valid=valid, accepted=accepted))
    score, mask = max(winners, key=lambda pair: pair[0])
    return mask, dict(score=score, starts=records, criterion="profiled_logdet" if calibrate else "known_gain_logdet")
