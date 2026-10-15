"""CrossSection.integrate — the single integration kernel and matrix regions.

Identities (concept crc_pi_slab_bimaterial_section §7):
  * filled inverted T  ≡  rectangle  (same concrete law in web, flange and fill)
  * vanishing region   ≡  no region
  * legacy quadrature  ≡  the former StressStrainProfile rule
"""
import numpy as np
import pytest

from scite.cs_design import (BandShape, CrossSection, InvTShape, MatrixRegion,
                             RectangularShape, ReinforcementLayer, ReinforcementLayout,
                             StressStrainProfile)
from scite.matmod import (CarbonReinforcement, EC2Concrete, EC2ParabolaRectangle,
                          FoamConcrete, SteelReinforcement)

B_F, H_F, B_W, H_W = 800.0, 50.0, 90.0, 200.0
H_T = H_F + H_W


def _layout():
    return ReinforcementLayout(layers=[
        ReinforcementLayer(z=20.0, A_s=150.0, material=CarbonReinforcement(E=210_000.0, f_t=3000.0))])


def _states(h, n=12, seed=0):
    """Random sagging states: top fibre in [-3.5, -0.2] ‰, bottom in [-1, 12] ‰."""
    rng = np.random.default_rng(seed)
    for _ in range(n):
        eps_top = rng.uniform(-0.0035, -0.0002)
        eps_bot = rng.uniform(-0.001, 0.012)
        yield (eps_bot - eps_top) / h, eps_bot


def _filled_invt(concrete, extra_top=0.0, plate=0.0):
    regions = [MatrixRegion(shape=BandShape(y0=H_F, y1=H_T, b=B_F - B_W, gap=B_W),
                            material=concrete, label='fill')]
    if extra_top > 0:
        regions.append(MatrixRegion(shape=BandShape(y0=H_T, y1=H_T + extra_top, b=B_F),
                                    material=concrete, label='fill'))
    if plate > 0:
        y0 = H_T + extra_top
        regions.append(MatrixRegion(shape=BandShape(y0=y0, y1=y0 + plate, b=B_F),
                                    material=concrete, label='top plate'))
    return CrossSection(shape=InvTShape(b_f=B_F, h_f=H_F, b_w=B_W, h_w=H_W),
                        concrete=concrete, reinforcement=_layout(), regions=regions)


def _rect(concrete, h):
    return CrossSection(shape=RectangularShape(b=B_F, h=h), concrete=concrete,
                        reinforcement=_layout())


@pytest.mark.parametrize("extra_top, plate", [(0.0, 0.0), (60.0, 40.0)])
def test_filled_invt_equals_rectangle_parabola(extra_top, plate):
    """Piecewise-polynomial law → both integrals exact → equal to round-off."""
    conc = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=1.0, gamma_c=1.0)
    comp = _filled_invt(conc, extra_top, plate)
    h = H_T + extra_top + plate
    rect = _rect(conc, h)
    assert comp.h_total == pytest.approx(h)
    assert comp.y_top_primary == pytest.approx(H_T)
    for kappa, eps_bot in _states(h):
        a, b = comp.integrate(kappa, eps_bot), rect.integrate(kappa, eps_bot)
        assert a.N == pytest.approx(b.N, rel=1e-10, abs=1e-6)
        assert a.M == pytest.approx(b.M, rel=1e-10, abs=1e-3)


def test_filled_invt_equals_rectangle_sargin():
    """Rational (Sargin) law with a tension branch → close, not exact."""
    conc = EC2Concrete(f_ck=30.0)
    comp, rect = _filled_invt(conc), _rect(conc, H_T)
    for kappa, eps_bot in _states(H_T):
        a, b = comp.integrate(kappa, eps_bot), rect.integrate(kappa, eps_bot)
        assert a.N == pytest.approx(b.N, rel=1e-5, abs=1.0)
        assert a.M == pytest.approx(b.M, rel=1e-5, abs=1e3)


def test_transformed_properties_filled_invt_equals_rectangle():
    conc = EC2ParabolaRectangle(f_ck=30.0)
    comp, rect = _filled_invt(conc, 60.0, 40.0), _rect(conc, H_T + 100.0)
    np.testing.assert_allclose(comp.transformed_properties(), rect.transformed_properties())


def test_transformed_properties_weight_regions_by_modulus():
    conc = EC2ParabolaRectangle(f_ck=30.0)
    foam = FoamConcrete(f_c=2.0, E=1250.0)
    cs = CrossSection(shape=InvTShape(b_f=B_F, h_f=H_F, b_w=B_W, h_w=H_W), concrete=conc,
                      reinforcement=_layout(),
                      regions=[MatrixRegion(shape=BandShape(y0=H_F, y1=H_T, b=B_F - B_W),
                                            material=foam)])
    A, S, I = cs.transformed_properties()
    n = 1250.0 / conc.E_ct_computed
    shp = cs.shape
    assert A == pytest.approx(shp.area + n * (B_F - B_W) * H_W)
    assert S == pytest.approx(shp.first_moment_of_area_bottom
                              + n * (B_F - B_W) * (H_T ** 2 - H_F ** 2) / 2)


def test_vanishing_region_equals_plain_section():
    conc = EC2ParabolaRectangle(f_ck=30.0)
    shape = InvTShape(b_f=B_F, h_f=H_F, b_w=B_W, h_w=H_W)
    void = FoamConcrete(f_c=1e-7, E=1e-4, gamma=1.0)
    with_void = CrossSection(shape=shape, concrete=conc, reinforcement=_layout(),
                             regions=[MatrixRegion(shape=BandShape(y0=H_F, y1=H_T, b=B_F - B_W),
                                                   material=void)])
    plain = CrossSection(shape=shape, concrete=conc, reinforcement=_layout())
    for kappa, eps_bot in _states(H_T):
        a, b = with_void.integrate(kappa, eps_bot), plain.integrate(kappa, eps_bot)
        F_max = void.f_cd * (B_F - B_W) * H_W                  # ≈ 0.014 N
        assert abs(a.components[1].N) <= F_max
        assert a.N == pytest.approx(b.N, abs=F_max)
        assert a.M == pytest.approx(b.M, abs=F_max * H_T)


def test_region_components_and_centroid():
    conc = EC2ParabolaRectangle(f_ck=30.0)
    foam = FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0)
    cs = CrossSection(shape=InvTShape(b_f=B_F, h_f=H_F, b_w=B_W, h_w=H_W), concrete=conc,
                      reinforcement=_layout(),
                      regions=[MatrixRegion(shape=BandShape(y0=H_F, y1=H_T, b=B_F - B_W),
                                            material=foam, label='ballast')])
    kappa, eps_bot = 0.01 / H_T, 0.007                        # top at -3 ‰
    res = cs.integrate(kappa, eps_bot)
    assert [c.label for c in res.components] == ['concrete', 'ballast']
    fill = res.components[1]
    assert fill.N < 0.0                                        # foam in compression
    y_na = eps_bot / kappa
    assert y_na < fill.y_centroid < H_T
    # only the compressed part of the fill acts: |N| < full-depth plateau force
    assert abs(fill.N) < foam.f_cd * (B_F - B_W) * (H_T - y_na)
    assert res.N == pytest.approx(res.N_matrix + res.N_reinf)


def test_grouped_merges_bands_with_the_same_label():
    conc = EC2ParabolaRectangle(f_ck=30.0)
    cs = _filled_invt(conc, extra_top=60.0, plate=40.0)       # fill = 2 bands
    res = cs.integrate(4e-5, 0.006)
    g = res.grouped()
    assert [c.label for c in g] == ['concrete', 'fill', 'top plate']
    assert g[1].N == pytest.approx(res.components[1].N + res.components[2].N)
    assert (g[1].y_bot, g[1].y_top) == (H_F, H_T + 60.0)
    assert sum(c.N for c in g) == pytest.approx(res.N_matrix)


def test_get_N_M_and_profile_delegate_to_kernel():
    conc = EC2ParabolaRectangle(f_ck=30.0)
    cs = _filled_invt(conc, 60.0)
    kappa, eps_bot = 4e-5, 0.006
    res = cs.integrate(kappa, eps_bot)
    assert cs.get_N_M(kappa, eps_bot) == pytest.approx((res.N, res.M))
    F_c, F_s, N, M = StressStrainProfile(cs, kappa, eps_bot).get_force_resultants()
    assert (F_c, F_s, N, M) == pytest.approx((res.N_matrix, res.N_reinf, res.N, -res.M))


def test_legacy_quadrature_reproduces_former_rule():
    """quadrature='legacy' == the pre-kernel StressStrainProfile loop (no regions)."""
    conc = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=0.85, gamma_c=1.5)
    shape = InvTShape(b_f=B_F, h_f=H_F, b_w=B_W, h_w=H_W)
    cs = CrossSection(shape=shape, concrete=conc, reinforcement=_layout(), quadrature='legacy')
    for kappa, eps_bot in _states(H_T, n=5):
        z = np.linspace(0, H_T, 100)
        dz = H_T / 100
        sig = conc.get_sig(eps_bot - kappa * z)
        F_c = sum(s * float(shape.get_width_at_y(np.array([zz]))[0]) * dz for zz, s in zip(z, sig))
        M_c = sum(s * float(shape.get_width_at_y(np.array([zz]))[0]) * dz * zz
                  for zz, s in zip(z, sig))
        res = cs.integrate(kappa, eps_bot)
        assert res.components[0].N == pytest.approx(F_c, rel=1e-12)
        assert res.components[0].M == pytest.approx(M_c, rel=1e-12)


def test_sketch_draws_regions_on_the_envelope():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    conc = EC2ParabolaRectangle(f_ck=30.0)
    cs = _filled_invt(conc, extra_top=60.0, plate=40.0)
    fig, ax = plt.subplots()
    n0 = len(ax.patches)
    cs.plot_cross_section(ax=ax)
    # primary polygon + fill (2 halves + 1 band) + top plate + 1 layer circle
    assert len(ax.patches) - n0 == 6
    assert ax.get_ylim()[1] > cs.h_total
    assert any(t.get_text() == f'h={cs.h_total:.0f}' for t in ax.texts)
    plt.close(fig)


def test_steel_band_region_smoke():
    """A steel plate glued under a rectangle (compound section capability)."""
    conc = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=1.0, gamma_c=1.0)
    steel = SteelReinforcement(f_yk=355.0, gamma_s=1.0)
    plate = MatrixRegion(shape=BandShape(y0=-10.0, y1=0.0, b=200.0), material=steel,
                         label='steel plate', color='#555555')
    cs = CrossSection(shape=RectangularShape(b=300.0, h=400.0), concrete=conc,
                      reinforcement=_layout(), regions=[plate])
    res = cs.integrate(1e-5, 0.0015)
    assert res.components[1].N > 0.0                           # plate in tension
    assert res.components[1].N <= steel.f_td * 2000.0 + 1e-6
    assert plate.y_bot == -10.0 and cs.h_total == 400.0
