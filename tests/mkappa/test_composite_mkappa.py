"""M-κ of composite (multi-component) sections — concept §7 cases 2, 5, 6.

Pi-slab rib: inverted T (plate 800×50, web 90×200) with a CFRP layer in the
plate, optionally a foam fill between / above the web and a concrete top plate.
"""
import contextlib
import io

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from scite.cs_design import (BandShape, CrossSection, InvTShape, MatrixRegion,  # noqa: E402
                             RectangularShape, ReinforcementLayer, ReinforcementLayout)
from scite.matmod import CarbonReinforcement, EC2ParabolaRectangle, FoamConcrete  # noqa: E402
from scite.mkappa.mkappa import MKappaAnalysis  # noqa: E402

B_F, H_F, B_W, H_W = 800.0, 50.0, 90.0, 200.0
H_T = H_F + H_W
CONC = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=1.0, gamma_c=1.0)


def _layout():
    return ReinforcementLayout(layers=[
        ReinforcementLayer(z=20.0, A_s=150.0, material=CarbonReinforcement(E=210_000.0, f_t=3000.0))])


def _pi(foam=None, above=0.0, plate=0.0, fill_material=None):
    regs = []
    mat = fill_material or foam
    if mat is not None:
        regs.append(MatrixRegion(shape=BandShape(y0=H_F, y1=H_T, b=B_F - B_W, gap=B_W),
                                 material=mat, label='ballast'))
        if above > 0:
            regs.append(MatrixRegion(shape=BandShape(y0=H_T, y1=H_T + above, b=B_F),
                                     material=mat, label='ballast'))
    if plate > 0:
        y0 = H_T + above
        regs.append(MatrixRegion(shape=BandShape(y0=y0, y1=y0 + plate, b=B_F),
                                 material=EC2ParabolaRectangle(f_ck=25.0, alpha_cc=1.0, gamma_c=1.0),
                                 label='top plate'))
    return CrossSection(shape=InvTShape(b_f=B_F, h_f=H_F, b_w=B_W, h_w=H_W),
                        concrete=CONC, reinforcement=_layout(), regions=regs)


def _solve(cs, **kw):
    mk = MKappaAnalysis(cs=cs, solve_mode='positive', n_kappa=120, **kw)
    with contextlib.redirect_stdout(io.StringIO()):
        mk.solve()
    return mk


def _by_label(limits):
    return {(d['label'], d['kind']): d for d in limits}


def test_filled_invt_mkappa_equals_rectangle():
    """§7.2 at M-κ level: same concrete in the fill → same κ_cr, M_cr, M_R."""
    comp = _solve(_pi(fill_material=CONC))
    rect = _solve(CrossSection(shape=RectangularShape(b=B_F, h=H_T), concrete=CONC,
                               reinforcement=_layout()))
    assert comp.kappa_cr_pos == pytest.approx(rect.kappa_cr_pos, rel=1e-9)
    assert comp.M_cr_pos == pytest.approx(rect.M_cr_pos, rel=1e-9)
    assert np.max(comp.M_values) == pytest.approx(np.max(rect.M_values), rel=1e-6)


def test_plain_section_concrete_limit_reached_at_end():
    mk = _solve(_pi())
    lims = _by_label(mk.get_component_limits())
    conc = lims[('concrete', 'compression')]
    # the last converged point lies within one κ-step (Δη ≈ 0.02) of the limit
    assert conc['reached'] and 0.97 < conc['eta_peak'] <= 1.0 + 1e-6
    assert not lims[('reinforcement', 'tension')]['reached']
    assert mk.get_component_limits()[0]['label'] == 'concrete'      # governing


def test_fill_raises_capacity_and_stiffness():
    plain = _solve(_pi())
    filled = _solve(_pi(FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0), above=100.0))
    assert np.max(filled.M_values) > 1.3 * np.max(plain.M_values)
    assert filled.M_cr_pos > plain.M_cr_pos


def test_soft_foam_reaches_its_limit_first_and_sweep_continues():
    """§7.5: a soft fill above the web is marked first; the sweep goes on."""
    foam = FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0, eps_cu=-0.002)
    mk = _solve(_pi(foam, above=60.0))
    limits = mk.get_component_limits()
    assert limits[0]['label'] == 'ballast' and limits[0]['kind'] == 'compression'
    k_fill = limits[0]['kappa_lim']
    assert mk.kappa_raw_values[-1] > 1.5 * k_fill
    conc = _by_label(limits)[('concrete', 'compression')]
    assert conc['reached'] and conc['kappa_lim'] > k_fill
    # the curve keeps rising after the fill's limit (concrete takes over)
    assert np.max(mk.M_values) > float(np.interp(k_fill, mk.kappa_values, mk.M_values))


def test_top_plate_envelope_bound_and_path_following():
    """§7.6: the envelope grows, the solver bound stays on the primary top fibre.

    A strong top plate keeps the neutral axis high; the reinforcement governs.
    Regression: N(ε_bot) has a second root once the plate could be crushed
    (plate crushed + CFRP unloaded) — the sweep must not jump to it when the
    CFRP reaches its limit, but stop there (rupture), as a plain section does.
    """
    cs = _pi(FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0), above=60.0, plate=40.0)
    assert cs.h_total == pytest.approx(H_T + 100.0)
    assert cs.y_top_primary == pytest.approx(H_T)
    mk = _solve(cs)
    eps_top_primary = mk.eps_bot_raw_values - mk.kappa_raw_values * H_T
    assert np.min(eps_top_primary) >= CONC.eps_cu2_computed - 1e-6
    M = mk.M_raw_values
    assert np.all(np.diff(M[2:]) > 0.0), "no jump to the crushed-plate / unloaded-CFRP root"
    limits = mk.get_component_limits()
    assert limits[0]['label'] == 'reinforcement' and limits[0]['reached']
    assert limits[0]['M_lim'] == pytest.approx(np.max(mk.M_values))
    plate = _by_label(limits)[('top plate', 'compression')]
    assert not plate['reached'] and plate['eta_peak'] < 0.6


def test_genuine_top_plate_crushing_is_followed():
    """A thin weak plate over heavy reinforcement crushes first: the limit is the
    peak (cliff of the parabola-rectangle law) and the sweep continues on the
    crushed branch to the concrete limit of the inverted T."""
    lay = ReinforcementLayout(layers=[ReinforcementLayer(
        z=20.0, A_s=600.0, material=CarbonReinforcement(E=210_000.0, f_t=3000.0))])
    foam = FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0)
    regs = [MatrixRegion(shape=BandShape(y0=H_F, y1=H_T, b=B_F - B_W, gap=B_W),
                         material=foam, label='ballast'),
            MatrixRegion(shape=BandShape(y0=H_T, y1=H_T + 60.0, b=B_F),
                         material=foam, label='ballast'),
            MatrixRegion(shape=BandShape(y0=H_T + 60.0, y1=H_T + 80.0, b=B_F),
                         material=EC2ParabolaRectangle(f_ck=12.0, alpha_cc=1.0, gamma_c=1.0),
                         label='top plate')]
    mk = _solve(CrossSection(shape=InvTShape(b_f=B_F, h_f=H_F, b_w=B_W, h_w=H_W),
                             concrete=CONC, reinforcement=lay, regions=regs))
    limits = mk.get_component_limits()
    assert [d['label'] for d in limits if d['reached']] == ['top plate', 'concrete']
    plate = limits[0]
    assert plate['M_lim'] == pytest.approx(np.max(mk.M_values))
    assert mk.kappa_raw_values[-1] > 1.2 * plate['kappa_lim']


def test_component_markers_are_plotted():
    import matplotlib.pyplot as plt
    mk = _solve(_pi(FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0, eps_cu=-0.002), above=60.0))
    fig, ax = plt.subplots()
    mk.plot_mk(ax=ax, show_component_markers=True)
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert 'ballast limit (compression)' in labels
    assert 'concrete limit (compression)' in labels
    plt.close(fig)
