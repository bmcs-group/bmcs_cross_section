"""Layup-material register: composition-based GWP and the fill presets built on it."""
import pytest

from scite.beam.floor import BALLAST_PRESETS, BallastSpec
from scite.cs_components.layup_materials import (CONSTITUENTS, LAYUP_MATERIALS,
                                                 get_layup_material, layup_materials)


def test_gwp_is_the_sum_over_the_composition():
    m = get_layup_material('FC600')
    expected = sum(kg * CONSTITUENTS[c].gwp for c, kg in m.composition.items())
    assert m.gwp_m3 == pytest.approx(expected)
    assert m.gwp_kg == pytest.approx(expected / 600.0)
    assert sum(r[3] for r in m.breakdown()) == pytest.approx(expected)
    assert m.breakdown()[0][0] == 'CEM I'                    # cement dominates
    assert m.binder == 350.0


def test_flat_reference_entries_keep_the_app_defaults():
    conc = get_layup_material('icc reference (flat)')
    cfrp = get_layup_material('icc reference CFRP (flat)')
    assert (conc.gwp_kg, conc.rho, conc.cost_m3) == (0.17, 2500.0, 150.0)
    assert (cfrp.gwp_kg, cfrp.cost_kg) == (19.0, 100.0)
    assert conc.composition_text() == 'flat 0.17 kgCO₂e/kg'


def test_binder_drives_the_fill_carbon():
    cem1 = get_layup_material('FC600').gwp_m3
    assert get_layup_material('FC600 CEM III/B').gwp_m3 < 0.4 * cem1
    assert get_layup_material('FC600 50% fly ash').gwp_m3 < 0.6 * cem1
    # a CEM I foam concrete needs about as much cement per m³ as normal concrete
    assert cem1 == pytest.approx(get_layup_material('C30/37 CEM I').gwp_m3, rel=0.05)
    assert get_layup_material('glass-foam gravel').gwp_m3 < 0.1 * cem1


def test_categories_and_constituent_keys():
    assert set(layup_materials('fill')) == set(BALLAST_PRESETS)
    assert all(m.category in ('concrete', 'fill', 'frp') for m in LAYUP_MATERIALS.values())
    for m in LAYUP_MATERIALS.values():
        assert set(m.composition) <= set(CONSTITUENTS), m.key
        assert (m.gwp_flat is None) != (not m.composition), m.key   # exactly one source
    with pytest.raises(KeyError):
        get_layup_material('unobtainium')


def test_fill_presets_follow_the_register():
    for key, spec in BALLAST_PRESETS.items():
        m = get_layup_material(key)
        assert spec.e_co2 == pytest.approx(m.gwp_kg)
        assert (spec.rho, spec.p_eur, spec.structural, spec.name) == \
            (m.rho, m.cost_m3, m.structural, key)
    with pytest.raises(ValueError):
        BallastSpec.from_material('C30/37 CEM I')                # not a fill
