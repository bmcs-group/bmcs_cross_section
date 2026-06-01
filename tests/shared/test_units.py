"""
tests/shared/test_units.py
==========================

Unit tests for scite.shared.units — UnitLevel, UnitSystem, field_mm,
UnitContext.

Coverage: round-trip conversions for all levels × all systems, field
metadata, adapt() with real floor models.
"""
import dataclasses
import math
import pytest

from scite.shared.units import (
    UnitContext,
    UnitLevel,
    UnitSystem,
    _DISPLAY_LABEL,
    _TO_BASE,
    field_mm,
)
from scite.beam.floor import CRCFlatSlab, FlatSlab, SRCRibbedSlab, CRCRibbedSlab


# ── helpers ────────────────────────────────────────────────────────────────────

def _ctx(system: UnitSystem) -> UnitContext:
    return UnitContext(system)


# ── UnitLevel enum ─────────────────────────────────────────────────────────────

class TestUnitLevel:
    def test_values_present(self):
        assert UnitLevel.STRUCTURAL.value  == 'structural'
        assert UnitLevel.CS_DIM.value      == 'cs_dim'
        assert UnitLevel.REINF_AREA.value  == 'reinf_area'

    def test_is_str_enum(self):
        assert isinstance(UnitLevel.STRUCTURAL, str)


# ── UnitSystem enum ────────────────────────────────────────────────────────────

class TestUnitSystem:
    def test_all_four_present(self):
        systems = {s.value for s in UnitSystem}
        assert {'mm_base', 'customary', 'all_m', 'imperial'} <= systems


# ── _TO_BASE table ─────────────────────────────────────────────────────────────

class TestToBaseTable:
    """Every non-trivial (level, system) pair must have a positive factor."""

    @pytest.mark.parametrize('level,system,expected', [
        # CUSTOMARY_STRUCTURAL
        (UnitLevel.STRUCTURAL,  UnitSystem.CUSTOMARY_STRUCTURAL, 1_000.0),
        (UnitLevel.CS_DIM,      UnitSystem.CUSTOMARY_STRUCTURAL, 1.0),
        (UnitLevel.REINF_AREA,  UnitSystem.CUSTOMARY_STRUCTURAL, 100.0),
        # ALL_METERS
        (UnitLevel.STRUCTURAL,  UnitSystem.ALL_METERS, 1_000.0),
        (UnitLevel.CS_DIM,      UnitSystem.ALL_METERS, 1_000.0),
        (UnitLevel.REINF_AREA,  UnitSystem.ALL_METERS, 1_000_000.0),
        # IMPERIAL
        (UnitLevel.STRUCTURAL,  UnitSystem.IMPERIAL, 304.8),
        (UnitLevel.CS_DIM,      UnitSystem.IMPERIAL, 25.4),
        (UnitLevel.REINF_AREA,  UnitSystem.IMPERIAL, 645.16),
    ])
    def test_factor(self, level, system, expected):
        assert _TO_BASE[(level, system)] == pytest.approx(expected)

    def test_mm_base_not_in_table(self):
        """MM_BASE has implicit factor 1.0 — no table entry required."""
        for level in UnitLevel:
            assert (level, UnitSystem.MM_BASE) not in _TO_BASE


# ── field_mm ───────────────────────────────────────────────────────────────────

class TestFieldMm:
    def test_with_default_has_metadata(self):
        f = field_mm(UnitLevel.STRUCTURAL, 5000.0)
        assert f.default == 5000.0
        assert f.metadata['unit_level'] == UnitLevel.STRUCTURAL
        assert f.metadata['base_unit']  == 'mm'

    def test_without_default_is_required(self):
        f = field_mm(UnitLevel.CS_DIM)
        # dataclasses.MISSING means no default was set
        assert f.default is dataclasses.MISSING
        assert f.default_factory is dataclasses.MISSING
        assert f.metadata['unit_level'] == UnitLevel.CS_DIM

    def test_reinf_area_level(self):
        f = field_mm(UnitLevel.REINF_AREA, 300.0)
        assert f.metadata['unit_level'] == UnitLevel.REINF_AREA

    def test_extra_kwargs_forwarded(self):
        f = field_mm(UnitLevel.CS_DIM, 200.0, repr=False)
        assert f.repr is False


# ── UnitContext — scalar conversion ────────────────────────────────────────────

class TestUnitContextScalar:
    @pytest.mark.parametrize('system,level,display,base', [
        # span in metres → mm
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.STRUCTURAL,  6.0,   6_000.0),
        # CS dim in mm → mm (factor 1)
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.CS_DIM,      200.0, 200.0),
        # reinf in cm² → mm²
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.REINF_AREA,  3.0,   300.0),
        # ALL_METERS: span in m → mm
        (UnitSystem.ALL_METERS,           UnitLevel.STRUCTURAL,  6.0,   6_000.0),
        # ALL_METERS: CS dim in m → mm
        (UnitSystem.ALL_METERS,           UnitLevel.CS_DIM,      0.2,   200.0),
        # ALL_METERS: reinf in m² → mm²
        (UnitSystem.ALL_METERS,           UnitLevel.REINF_AREA,  3e-4,  300.0),
        # IMPERIAL: span in ft → mm
        (UnitSystem.IMPERIAL,             UnitLevel.STRUCTURAL,  1.0,   304.8),
        # IMPERIAL: CS dim in inch → mm
        (UnitSystem.IMPERIAL,             UnitLevel.CS_DIM,      1.0,   25.4),
        # IMPERIAL: reinf in in² → mm²
        (UnitSystem.IMPERIAL,             UnitLevel.REINF_AREA,  1.0,   645.16),
        # MM_BASE: pass-through
        (UnitSystem.MM_BASE,              UnitLevel.STRUCTURAL,  6000.0, 6000.0),
        (UnitSystem.MM_BASE,              UnitLevel.CS_DIM,      200.0,  200.0),
        (UnitSystem.MM_BASE,              UnitLevel.REINF_AREA,  300.0,  300.0),
    ])
    def test_to_base(self, system, level, display, base):
        ctx = _ctx(system)
        assert ctx.to_base(display, level) == pytest.approx(base, rel=1e-6)

    @pytest.mark.parametrize('system,level,display,base', [
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.STRUCTURAL,  6.0,   6_000.0),
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.CS_DIM,      200.0, 200.0),
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.REINF_AREA,  11.0,  1_100.0),
    ])
    def test_from_base_roundtrip(self, system, level, display, base):
        ctx = _ctx(system)
        assert ctx.from_base(ctx.to_base(display, level), level) == pytest.approx(display, rel=1e-9)

    def test_none_level_passthrough(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        assert ctx.to_base(42.0, None)   == 42.0
        assert ctx.from_base(42.0, None) == 42.0


# ── UnitContext — display labels ───────────────────────────────────────────────

class TestUnitContextLabels:
    @pytest.mark.parametrize('system,level,expected', [
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.STRUCTURAL,  'm'),
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.CS_DIM,      'mm'),
        (UnitSystem.CUSTOMARY_STRUCTURAL, UnitLevel.REINF_AREA,  'cm²'),
        (UnitSystem.ALL_METERS,           UnitLevel.STRUCTURAL,  'm'),
        (UnitSystem.ALL_METERS,           UnitLevel.CS_DIM,      'm'),
        (UnitSystem.ALL_METERS,           UnitLevel.REINF_AREA,  'm²'),
        (UnitSystem.IMPERIAL,             UnitLevel.STRUCTURAL,  'ft'),
        (UnitSystem.IMPERIAL,             UnitLevel.CS_DIM,      'in'),
        (UnitSystem.IMPERIAL,             UnitLevel.REINF_AREA,  'in²'),
        (UnitSystem.MM_BASE,              UnitLevel.STRUCTURAL,  'mm'),
        (UnitSystem.MM_BASE,              UnitLevel.CS_DIM,      'mm'),
        (UnitSystem.MM_BASE,              UnitLevel.REINF_AREA,  'mm²'),
    ])
    def test_label_value(self, system, level, expected):
        ctx = _ctx(system)
        assert _DISPLAY_LABEL[(level, system)] == expected

    def test_label_method_for_flat_slab(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        assert ctx.label('L',   FlatSlab) == 'm'
        assert ctx.label('h',   FlatSlab) == 'mm'
        assert ctx.label('A_s', FlatSlab) == 'cm²'
        assert ctx.label('z_s', FlatSlab) == 'mm'
        assert ctx.label('b',   FlatSlab) == 'mm'

    def test_label_unannotated_field_returns_empty(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        assert ctx.label('f_ck', FlatSlab) == ''

    def test_labels_dict_flat_slab(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        labels = ctx.labels(FlatSlab)
        assert labels == {'h': 'mm', 'A_s': 'cm²', 'z_s': 'mm', 'L': 'm', 'b': 'mm'}


# ── UnitContext.adapt() ────────────────────────────────────────────────────────

class TestUnitContextAdapt:
    """adapt() must convert annotated fields and pass others through unchanged."""

    def test_flat_slab_customary(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        slab = ctx.adapt(FlatSlab, h=200, A_s=11.0, z_s=35, L=6.0)
        assert slab.h   == pytest.approx(200.0)      # CS_DIM factor 1.0
        assert slab.A_s == pytest.approx(1_100.0)    # cm² → mm²
        assert slab.z_s == pytest.approx(35.0)
        assert slab.L   == pytest.approx(6_000.0)    # m → mm
        assert slab.b   == pytest.approx(1_000.0)    # default unchanged

    def test_flat_slab_mm_base(self):
        ctx = _ctx(UnitSystem.MM_BASE)
        slab = ctx.adapt(FlatSlab, h=200, A_s=1100, z_s=35, L=6000)
        assert slab.h   == 200.0
        assert slab.A_s == 1100.0
        assert slab.L   == 6000.0

    def test_flat_slab_all_meters(self):
        ctx = _ctx(UnitSystem.ALL_METERS)
        slab = ctx.adapt(FlatSlab, h=0.200, A_s=1.1e-3, z_s=0.035, L=6.0)
        assert slab.h   == pytest.approx(200.0,   rel=1e-9)
        assert slab.A_s == pytest.approx(1_100.0, rel=1e-6)
        assert slab.L   == pytest.approx(6_000.0, rel=1e-9)

    def test_crc_flat_slab_customary(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        slab = ctx.adapt(CRCFlatSlab, h=160, A_f=5.0, z_f=25, L=6.0)
        assert slab.L   == pytest.approx(6_000.0)
        assert slab.A_f == pytest.approx(500.0)
        assert slab.h   == pytest.approx(160.0)

    def test_src_ribbed_slab_customary(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        rib = ctx.adapt(SRCRibbedSlab,
                        H_rib=280, H_bay=80, B_rib=150, L_rib=0.6, L_bay=6.0)
        assert rib.L_rib == pytest.approx(600.0)
        assert rib.L_bay == pytest.approx(6_000.0)
        assert rib.H_rib == pytest.approx(280.0)     # CS_DIM, factor 1.0

    def test_crc_ribbed_slab_customary(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        rib = ctx.adapt(CRCRibbedSlab,
                        H_rib=280, H_bay=80, B_rib=150, L_rib=0.6, L_bay=6.0)
        assert rib.L_rib == pytest.approx(600.0)
        assert rib.L_bay == pytest.approx(6_000.0)

    def test_unannotated_fields_pass_through(self):
        ctx = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        slab = ctx.adapt(FlatSlab, h=200, A_s=11.0, z_s=35, f_ck=40.0)
        assert slab.f_ck == pytest.approx(40.0)

    def test_assess_runs_after_adapt(self):
        """adapt() must produce a functioning model (not just correct field values)."""
        from scite.beam.floor import LoadModel
        ctx  = _ctx(UnitSystem.CUSTOMARY_STRUCTURAL)
        lm   = LoadModel()
        slab = ctx.adapt(FlatSlab, h=200, A_s=11.0, z_s=35, L=6.0)
        result = slab.assess(lm)
        assert 'Slab strip' in result
        assert math.isfinite(result['Slab strip']['eta_ULS'])


# ── backward compatibility ─────────────────────────────────────────────────────

class TestBackwardCompatibility:
    """Existing notebooks pass mm values directly — must still work identically."""

    def test_flat_slab_direct_mm(self):
        """FlatSlab(h=200, A_s=1100, z_s=35, L=6000) still constructs fine."""
        slab = FlatSlab(h=200, A_s=1100, z_s=35, L=6000)
        assert slab.h   == 200.0
        assert slab.A_s == 1100.0
        assert slab.L   == 6000.0

    def test_flat_slab_default_L(self):
        """Fields with field_mm defaults still default to mm base values."""
        slab = FlatSlab(h=200, A_s=300, z_s=30)
        assert slab.L == 5000.0
        assert slab.b == 1000.0

    def test_src_ribbed_slab_direct_mm(self):
        rib = SRCRibbedSlab(H_rib=280, H_bay=80, B_rib=150,
                             L_rib=600, L_bay=6000)
        assert rib.L_rib == 600.0
        assert rib.L_bay == 6000.0

    def test_crc_ribbed_slab_direct_mm(self):
        rib = CRCRibbedSlab(H_rib=280, H_bay=80, B_rib=150,
                             L_rib=600, L_bay=6000)
        assert rib.L_rib == 600.0
        assert rib.L_bay == 6000.0
