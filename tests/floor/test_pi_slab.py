"""CRC Pi slab (scite.beam.floor) — concept crc_pi_slab_bimaterial_section, M2.

Section composition, SLS/ULS pair, self-weight and resources, and the
verification cases §7.3/§7.4 (vanishing / mass-only ballast) and §2.1
(inverted T vs T rib).
"""
import contextlib
import io

import numpy as np
import pytest

from scite.beam.floor import (BALLAST_PRESETS, BallastSpec, CRCPiSlab, CRCRibbedSlab,
                              FloorAnalysisPair, FloorSectionCRCPiRib, LoadModel,
                              TopPlateSpec)
from scite.shared.units import UnitContext, UnitSystem

GEO = dict(H_rib=250.0, H_bay=50.0, B_rib=90.0, L_rib=6000.0, L_bay=800.0)


def _M_R(pair_member):
    with contextlib.redirect_stdout(io.StringIO()):
        return float(np.max(pair_member.bda.mk.M_values))


# ── Section composition (FloorSectionCRCPiRib) ────────────────────────────────

def _sec(**kw):
    return FloorSectionCRCPiRib(b_w=90.0, h_w=200.0, b_f=800.0, h_f=50.0, **kw)


def test_plain_section_and_reinforcement_layers():
    cs = _sec(A_s=150.0, z_s=30.0, A_grid=60.0, z_grid=20.0).build_cs()
    assert cs.regions == []
    assert cs.h_total == pytest.approx(250.0)
    names = [l.name for l in cs.reinforcement.layers]
    assert names == ['rib bars', 'plate grid']             # concentrated bars first
    assert [l.A_s for l in cs.reinforcement.layers] == [150.0, 60.0]
    assert [l.name for l in _sec(A_s=0.0, A_grid=60.0).build_cs().reinforcement.layers] \
        == ['plate grid']
    with pytest.raises(ValueError):
        _sec(A_s=0.0, A_grid=0.0).build_cs()


@pytest.mark.parametrize("h_fill, n_bands, y_top", [(120.0, 1, 170.0), (200.0, 1, 250.0),
                                                    (260.0, 2, 310.0)])
def test_ballast_bands(h_fill, n_bands, y_top):
    cs = _sec(ballast=BallastSpec(h_fill=h_fill)).build_cs()
    fill = [r for r in cs.regions if r.label == 'ballast']
    assert len(fill) == n_bands
    between = fill[0].shape
    assert (between.y0, between.b, between.gap) == (50.0, 710.0, 90.0)
    if n_bands == 2:
        assert (fill[1].shape.y0, fill[1].shape.b) == (250.0, 800.0)
    assert cs.h_total == pytest.approx(max(250.0, y_top))


def test_top_plate_rests_on_fill_or_webs():
    tp = TopPlateSpec(h_top=40.0)
    on_fill = _sec(ballast=BallastSpec(h_fill=260.0), top_plate=tp).build_cs()
    on_webs = _sec(ballast=BallastSpec(h_fill=120.0), top_plate=tp).build_cs()
    no_fill = _sec(top_plate=tp).build_cs()
    for cs, y0 in ((on_fill, 310.0), (on_webs, 250.0), (no_fill, 250.0)):
        plate = next(r for r in cs.regions if r.label == 'top plate')
        assert plate.shape.y0 == pytest.approx(y0)
        assert cs.h_total == pytest.approx(y0 + 40.0)


def test_mass_only_ballast_adds_no_region():
    spec = BallastSpec.from_preset('glass-foam gravel', h_fill=200.0)
    assert not spec.structural
    assert _sec(ballast=spec).build_cs().regions == []


def test_presets():
    assert {'FC400', 'FC600', 'FC800', 'FC1000'} <= set(BALLAST_PRESETS)
    fc = BallastSpec.from_preset('FC800', h_fill=150.0)
    assert (fc.rho, fc.f_c, fc.h_fill, fc.name) == (800.0, 4.0, 150.0, 'FC800')
    assert BALLAST_PRESETS['FC800'].h_fill == 200.0           # preset itself untouched
    with pytest.raises(KeyError):
        BallastSpec.from_preset('FC5000')


def test_pair_uses_ballast_gamma_at_uls():
    pair = FloorAnalysisPair.for_crc_pi_rib(
        b_w=90.0, h_w=200.0, b_f=800.0, h_f=50.0, f_ck=30.0, A_s=150.0, z_s=30.0,
        E_f=210_000.0, f_fk=3000.0, L_mm=6000.0,
        ballast=BallastSpec(h_fill=200.0, gamma=1.4), top_plate=TopPlateSpec(h_top=40.0))
    foam_sls = pair.sls.cs.regions[0].material
    foam_uls = pair.uls.cs.regions[0].material
    assert (foam_sls.gamma, foam_uls.gamma) == (1.0, 1.4)
    plate_uls = pair.uls.cs.regions[-1].material
    assert (plate_uls.gamma_c, plate_uls.alpha_cc) == (1.5, 0.85)   # EC2 design concrete
    assert pair.sls.bda.F_R > pair.uls.bda.F_R > 0.0


# ── Floor system (CRCPiSlab) ──────────────────────────────────────────────────

def test_plain_pi_slab_resources_equal_ribbed_slab():
    """Concrete and CFRP accounting are orientation independent."""
    pi, rib = CRCPiSlab(**GEO), CRCRibbedSlab(**GEO)
    assert pi.g_k == pytest.approx(rib.g_k)
    v_pi, v_rib = pi.volumes(), rib.volumes()
    for key, val in v_rib.items():
        assert v_pi[key] == pytest.approx(val), key
    assert v_pi['V_agg'] == 0.0 and v_pi['V_top'] == 0.0


def test_grid_reinforcement_area():
    pi = CRCPiSlab(**GEO, A_f_bay=150.0, r_long=0.5)
    assert pi.A_grid == pytest.approx(0.5 * 150.0 * pi.b_eff / 1000.0)
    layers = pi.rib_beam.sls.cs.reinforcement.layers
    assert layers[1].A_s == pytest.approx(pi.A_grid)
    assert layers[1].z == pi.z_f_bay


def test_g_k_and_volumes_with_fill_above_webs_and_top_plate():
    b = BallastSpec.from_preset('FC600', h_fill=260.0)
    tp = TopPlateSpec(h_top=40.0, e_co2=0.12, p_eur=180.0)
    pi = CRCPiSlab(**GEO, ballast=b, top_plate=tp)
    # per m² floor: (L_bay - B_rib)·h_w + L_bay·(h_fill - h_w), over L_bay
    V_agg_m2 = (0.71 * 0.200 + 0.80 * 0.060) / 0.80
    V_top_m2 = 0.040
    g_conc = 25.0 * (0.09 * 0.20 + 0.80 * 0.05) / 0.80
    assert pi.g_k == pytest.approx(g_conc + 6.0 * V_agg_m2 + 25.0 * V_top_m2)
    v = pi.volumes()
    A = v['A_bay']
    assert v['V_agg'] / A == pytest.approx(V_agg_m2)
    assert v['V_top'] / A == pytest.approx(V_top_m2)
    # composition-based: GWP of the fill = V_fill · Σ m_i·e_i of the FC600 mix
    from scite.cs_components.layup_materials import get_layup_material
    assert v['gwp_agg'] == pytest.approx(v['V_agg'] * get_layup_material('FC600').gwp_m3)
    assert v['gwp_top'] == pytest.approx(v['V_top'] * 2500.0 * 0.12)
    assert v['cost_top'] == pytest.approx(v['V_top'] * 180.0)
    assert v['gwp_total'] == pytest.approx(v['gwp_conc'] + v['gwp_cfrp']
                                           + v['gwp_agg'] + v['gwp_top'])
    assert v['gwp_per_m2'] == pytest.approx(v['gwp_total'] / A)
    assert v['cost_per_m2'] == pytest.approx(v['cost_total'] / A)
    assert pi.H_total == pytest.approx(350.0)


def test_mass_only_ballast_changes_weight_not_capacity():
    """§7.4: unbound granulate → M_R unchanged, g_k up by ρ·V/A."""
    plain = CRCPiSlab(**GEO)
    gravel = CRCPiSlab(**GEO, ballast=BallastSpec.from_preset('glass-foam gravel', h_fill=200.0))
    assert _M_R(gravel.rib_beam.sls) == pytest.approx(_M_R(plain.rib_beam.sls), rel=1e-12)
    dg = 1.75 * (0.71 * 0.200) / 0.80
    assert gravel.g_k - plain.g_k == pytest.approx(dg)


def test_structural_fill_raises_rib_capacity():
    plain = CRCPiSlab(**GEO)
    filled = CRCPiSlab(**GEO, ballast=BallastSpec.from_preset('FC600', h_fill=200.0))
    assert _M_R(filled.rib_beam.sls) > 1.1 * _M_R(plain.rib_beam.sls)
    # the transverse bay strip is unaffected (fill is mass only there, D-PI6)
    assert _M_R(filled.bay_beam.sls) == pytest.approx(_M_R(plain.bay_beam.sls))


def test_inverted_t_vs_t_rib():
    """§2.1: same b_w, h_w, b_f, h_f and bars (no grid) — the inverted T has the
    larger cracking moment, the T rib (flange in compression) the larger M_R."""
    pi = CRCPiSlab(**GEO, r_long=0.0)
    t = CRCRibbedSlab(**GEO)
    with contextlib.redirect_stdout(io.StringIO()):
        mk_pi, mk_t = pi.rib_beam.sls.bda.mk, t.rib_beam.sls.bda.mk
        assert mk_pi.M_cr_pos > mk_t.M_cr_pos
        assert np.max(mk_pi.M_values) < np.max(mk_t.M_values)


def test_assess_and_report():
    pi = CRCPiSlab(**GEO, ballast=BallastSpec(h_fill=200.0))
    with contextlib.redirect_stdout(io.StringIO()) as out:
        a = pi.assess(LoadModel())
        pi.report(LoadModel())
    assert set(a) == {'Bay slab', 'CRC Π rib'}
    assert all(d['p_R_sls'] > 0 for d in a.values())
    assert 'Ballast' in out.getvalue()


def test_unit_context_passes_specs_through():
    ctx = UnitContext(UnitSystem.CUSTOMARY_STRUCTURAL)
    b, tp = BallastSpec(h_fill=200.0), TopPlateSpec(h_top=40.0)
    pi = ctx.adapt(CRCPiSlab, H_rib=250.0, H_bay=50.0, B_rib=90.0, L_rib=6.0, L_bay=0.8,
                   A_f_rib=1.5, A_f_bay=1.5, ballast=b, top_plate=tp)
    assert (pi.L_rib, pi.A_f_rib, pi.A_f_bay) == (6000.0, 150.0, 150.0)
    assert pi.ballast is b and pi.top_plate is tp
