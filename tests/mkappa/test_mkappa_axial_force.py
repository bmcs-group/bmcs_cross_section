"""
M-κ under a constant axial force N_Ed.

Regression for the sweep acceptance test: the solver used to compare the total
axial force with zero instead of with N_Ed, so every step with N_Ed ≠ 0 was
discarded and the curve consisted of the two injected points only (found while
building the GdT node of scite_apps, 2026-10-14).
"""
import numpy as np
import pytest

from scite.cs_design import (CrossSection, RectangularShape, ReinforcementLayer,
                             ReinforcementLayout)
from scite.matmod import EC2ParabolaRectangle, SteelReinforcement
from scite.mkappa import MKappaAnalysis


def _section():
    steel = SteelReinforcement(f_yk=500.0, gamma_s=1.15)
    layers = [ReinforcementLayer(z=50.0, A_s=4 * np.pi * 8.0 ** 2, material=steel)]
    return CrossSection(
        shape=RectangularShape(b=200.0, h=500.0),
        concrete=EC2ParabolaRectangle(f_ck=30.0, alpha_cc=0.85, gamma_c=1.5),
        reinforcement=ReinforcementLayout(layers=layers),
    )


def _solve(N_Ed):
    mk = MKappaAnalysis(cs=_section(), N_Ed=N_Ed, n_kappa=60)
    mk.solve()
    return mk


@pytest.mark.parametrize("N_Ed", [-100.0, -300.0, 100.0])
def test_sweep_continues_under_axial_force(N_Ed):
    mk = _solve(N_Ed)
    assert len(mk.kappa_values) > 10, "sweep stopped at the injected points"
    # every accepted step is in equilibrium with the applied axial force
    sampled = mk.N_values[2:]
    assert np.allclose(sampled, N_Ed, atol=mk.N_tol * 100.0)


@pytest.mark.xfail(strict=True,
                   reason="F12 (cscp-arch concept 08): the κ grid does not follow the "
                          "failure curvature, so a heavily compressed section yields only "
                          "2–4 points. Remove the marker when _build_kappa_array adapts.")
def test_heavy_compression_is_resolved():
    mk = _solve(-500.0)
    assert len(mk.kappa_values) > 10


def test_compression_raises_capacity_and_reduces_ductility():
    mk0 = _solve(0.0)
    mkc = _solve(-500.0)
    assert mkc.M_values.max() > mk0.M_values.max()
    assert mkc.kappa_values.max() < mk0.kappa_values.max()


def test_pure_bending_unchanged():
    mk = _solve(0.0)
    assert len(mk.kappa_values) > 10
    assert 120.0 < mk.M_values.max() < 160.0   # 4⌀16 B500, 200×500, C30/37: ≈ 140 kNm
