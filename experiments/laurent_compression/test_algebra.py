"""Algebra checks required by the LAU-001 plan, section 10."""
import numpy as np
import pytest

from experiments.bie002_modal_diagnostic.fixtures import inputs
from experiments.modal_muller_research.coefficient_operator import (
    CoefficientGeometry, LaurentGeometry, ModalMomentFamily, kernel_matrix,
    kernel_matrix_reference)
from experiments.modal_muller_research.coefficient_derivative import ShapeOperator
from experiments.modal_muller_research.modal import ModalSystem
from experiments.modal_muller_research.scattering_library import parameterization

from . import masks as mask_rules
from .adapters import (BLOCK_NAMES, NativeCase, nodal_reference, relative, split_operator, waves)
from .metrics import paired
from .run_screen import equivalent_radius, fixture_set

FREQUENCY = 1.0669086261672807e9  # k_out * a_ref(star) = 2


def case_for(name, cutoff=16, bandwidth=96, terms=28):
    acq, _ = inputs()
    return NativeCase(fixture_set()[name], acq, FREQUENCY, cutoff, bandwidth, terms), acq


@pytest.mark.parametrize('name', ['circle', 'ellipse', 'star'])
def test_split_reconstructs_the_assembled_operator(name):
    case, _ = case_for(name)
    assert case.reconstruction_error < 1e-14
    for label in ('IDENTITY_ONLY', 'VERIFIED_SINGULAR_SPLIT'):
        protected, remainder = case.parts(label)
        assert relative(protected + remainder, case.a) < 1e-14


@pytest.mark.parametrize('name', ['circle', 'ellipse', 'star'])
def test_blockwise_split_sums_to_each_block(name):
    case, _ = case_for(name)
    blocks = case.remainder_blocks('IDENTITY_ONLY')
    for block_name in BLOCK_NAMES:
        total = case.log_blocks[block_name] + case.smooth_blocks[block_name]
        assert relative(blocks[block_name], total) < 1e-14


def test_fast_log_symbol_matches_the_retained_literal_contraction():
    """kernel_matrix versus the independent kernel_matrix_reference sum."""
    rng = np.random.default_rng(20260917)
    bandwidth, cutoff = 12, 6
    p = rng.normal(size=(2 * bandwidth + 1,) * 2) + 1j * rng.normal(size=(2 * bandwidth + 1,) * 2)
    s = rng.normal(size=p.shape) + 1j * rng.normal(size=p.shape)
    assert relative(kernel_matrix(p, s, cutoff),
                    kernel_matrix_reference(p, s, cutoff)) < 1e-13


@pytest.mark.parametrize('name', ['circle', 'ellipse', 'star'])
def test_three_assemblers_agree(name):
    """assemble (the reference) versus ModalMomentFamily and ShapeOperator."""
    geometry = fixture_set()[name]
    acq, _ = inputs()
    ko, ki = waves(FREQUENCY, acq)
    prepared = CoefficientGeometry(geometry, 64)
    reference, _ = prepared.assemble(ko, ki, 24, 28)
    family, _ = ModalMomentFamily(prepared, cutoff=24, terms=28).assemble(ko, ki)
    shape = ShapeOperator(prepared, ko, ki, 24, 28).a
    assert relative(family, reference) < 1e-13
    assert relative(shape, reference) < 1e-13


@pytest.mark.parametrize('name', ['circle', 'ellipse'])
def test_full_dft_projection_of_the_nodal_system_reproduces_nodal_receivers(name):
    """The A_M^proj control: a square coordinate change, not compression."""
    acq, _ = inputs()
    curve = parameterization(fixture_set()[name], component_id=name)
    reference = nodal_reference([curve], FREQUENCY, acq, 128)
    modal = ModalSystem.from_nodal(reference['a'], reference['b'], reference['c'],
                                   reference['curves'])
    solved = modal.solve(cutoff=63)  # exactly N distinct DFT modes, no Nyquist double count
    assert relative(paired(solved['y']), paired(reference['y'])) < 1e-10
    assert solved['residual'] < 1e-10


@pytest.mark.parametrize('name', ['ellipse', 'star'])
def test_mask_accounting_is_consistent(name):
    case, _ = case_for(name)
    directions = [{2: 1e-3}, {-1: 1e-3}]
    derivatives = [case.derivative(dz) for dz in directions]
    size = 2 * case.cutoff + 1
    for fraction in (0.1, 0.3, 0.5):
        mask = mask_rules.derivative_aware(case, 'VERIFIED_SINGULAR_SPLIT', fraction,
                                           derivatives=derivatives, floor=1e-12)
        report = mask_rules.retention(mask, case, 'VERIFIED_SINGULAR_SPLIT')
        assert report['candidate_count'] == 4 * size * size
        # each block rounds independently, so the total lands within one entry
        assert abs(report['retained_total'] - fraction) < 2 / (size * size)
        for block_name in BLOCK_NAMES:
            assert abs(report[f'retained_{block_name}'] - fraction) < 2 / (size * size)
        union = mask_rules.derivative_support_union(mask, case, derivatives,
                                                    'VERIFIED_SINGULAR_SPLIT', 1e-12)
        assert union >= report['retained_total'] - 1e-12


def test_masks_are_deterministic_under_ties():
    case, _ = case_for('ellipse')
    kwargs = dict(derivatives=[case.derivative({2: 1e-3})], floor=1e-12)
    first = mask_rules.derivative_aware(case, 'VERIFIED_SINGULAR_SPLIT', 0.3, **kwargs)
    second = mask_rules.derivative_aware(case, 'VERIFIED_SINGULAR_SPLIT', 0.3, **kwargs)
    assert np.array_equal(first, second)


class _SyntheticCase:
    """R(eta) = eta*H at eta = 0: zero forward remainder, nonzero derivative."""

    def __init__(self, size):
        self.cutoff = (size - 1) // 2
        rng = np.random.default_rng(7)
        self._zero = {n: np.zeros((size, size), complex) for n in BLOCK_NAMES}
        self._h = {n: rng.normal(size=(size, size)) + 0j for n in BLOCK_NAMES}
        for n in BLOCK_NAMES:          # concentrate the sensitivity in one corner
            keep = np.zeros((size, size), bool)
            keep[:3, :3] = True
            self._h[n] = np.where(keep, self._h[n], 0)

    def remainder_blocks(self, label):
        return dict(self._zero)

    def derivative_remainder_blocks(self, derivative, label):
        return dict(self._h)


def test_derivative_aware_keeps_sensitivity_when_the_forward_remainder_vanishes():
    """The plan's required R(eta)=eta*H control."""
    synthetic = _SyntheticCase(9)
    mask = mask_rules.derivative_aware(synthetic, 'VERIFIED_SINGULAR_SPLIT', 0.2,
                                       derivatives=[None], floor=1e-12)
    forward_mask = mask_rules.forward(synthetic, 'VERIFIED_SINGULAR_SPLIT', 0.2)
    size = 9
    needed = np.zeros((size, size), bool)
    needed[:3, :3] = True
    stacked = mask_rules.stack({n: needed for n in BLOCK_NAMES})
    assert np.all(mask[stacked]), 'derivative-aware selection discarded all sensitivity'
    assert not np.all(forward_mask[stacked]), 'forward-only control should miss it'
