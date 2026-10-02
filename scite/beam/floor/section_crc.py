"""
scite.beam.floor.section_crc
=============================

FloorSectionCRC — lightweight container for a rectangular CRC (Carbon-FRP
reinforced concrete) cross-section that can build a Pydantic ``CrossSection``
at SLS (characteristic) or ULS (design) material levels.

FloorSectionCRCPiRib — inverted-T rib of a CRC Pi slab (plate at the bottom,
web up) with an optional ballast fill and top cover plate (composite section).
BallastSpec / TopPlateSpec describe those two optional components.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from scite.cs_design import (
    BandShape,
    CrossSection,
    InvTShape,
    MatrixRegion,
    RectangularShape,
    ReinforcementLayer,
    ReinforcementLayout,
)
from scite.cs_components.layup_materials import (LayupMaterial, get_layup_material,
                                                 layup_materials)
from scite.cs_design.shapes import TShape
from scite.matmod.carbon_reinforcement import CarbonReinforcement
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.matmod.foam_concrete import FoamConcrete

# Sketch colour of a concrete top plate region (the ballast keeps the default ochre)
TOP_PLATE_COLOR = '#8c8c8c'


# ---- Optional components of a Pi-slab rib -----------------------------------

@dataclass
class BallastSpec:
    """Ballast / insulation fill between (and possibly above) the Pi-slab ribs.

    Geometry: ``h_fill`` is measured from the top of the plate; up to the web
    height it fills the space between the webs, above it the full width.

    ``structural=False`` makes the fill mass only (an unbound granulate): it
    adds self-weight and resources but no stiffness or strength.

    Parameters
    ----------
    h_fill : fill height above the plate [mm]
    rho    : dry density [kg/m³]
    f_c, E, eps_c1, eps_cu, sig_res, law : FoamConcrete parameters
    gamma  : partial safety factor of the fill (ULS)
    e_co2  : embodied carbon [kgCO₂/kg]
    p_eur  : unit cost [EUR/m³]
    """

    h_fill: float = 200.0
    rho: float = 600.0
    f_c: float = 2.0
    E: float = 1250.0
    eps_c1: float | None = None
    eps_cu: float | None = None
    sig_res: float = 0.0
    law: Literal['sargin', 'parabola'] = 'sargin'
    gamma: float = 1.5
    e_co2: float = 0.40
    p_eur: float = 105.0
    structural: bool = True
    name: str = 'FC600'

    def material(self, gamma: float = 1.0) -> FoamConcrete:
        """FoamConcrete law of the fill at partial factor *gamma*."""
        return FoamConcrete(rho=self.rho, f_c=self.f_c, E=self.E, eps_c1=self.eps_c1,
                            eps_cu=self.eps_cu, sig_res=self.sig_res, gamma=gamma,
                            law=self.law)

    @classmethod
    def from_material(cls, material: LayupMaterial | str, **overrides) -> 'BallastSpec':
        """Fill spec from a layup-material record (composition-based GWP and cost)."""
        m = get_layup_material(material) if isinstance(material, str) else material
        if m.category != 'fill':
            raise ValueError(f"{m.key!r} is a {m.category} material, not a fill")
        spec = cls(rho=m.rho, f_c=m.f_c if m.f_c is not None else 0.05,
                   E=m.E if m.E is not None else 5.0, eps_cu=m.eps_cu,
                   e_co2=m.gwp_kg, p_eur=m.cost_m3, structural=m.structural, name=m.key)
        return replace(spec, **overrides)

    @classmethod
    def from_preset(cls, name: str, **overrides) -> 'BallastSpec':
        """Indicative preset (see ``BALLAST_PRESETS``), fields overridable."""
        try:
            base = BALLAST_PRESETS[name]
        except KeyError:
            raise KeyError(f"unknown ballast preset {name!r}; "
                           f"choose from {sorted(BALLAST_PRESETS)}") from None
        return replace(base, **overrides)


# Indicative fill presets — derived from the composition-based layup-material
# register (scite.cs_components.layup_materials): GWP follows from the binder and
# constituents of each mix. Replace with the data of the intended product.
BALLAST_PRESETS: dict[str, BallastSpec] = {
    key: BallastSpec.from_material(m) for key, m in layup_materials('fill').items()
}


@dataclass
class TopPlateSpec:
    """Concrete top cover plate on the fill (or on the webs), rigidly connected.

    Parameters
    ----------
    h_top : plate thickness [mm]
    f_ck  : characteristic concrete strength [MPa]
    law   : 'parabola' (EC2 parabola-rectangle) or 'sargin' (EC2 Eq. 3.14 with
            softening, via FoamConcrete parametrised as normal concrete)
    e_co2, p_eur : embodied carbon [kgCO₂/kg] / cost [EUR/m³]; None → the
            slab concrete's values
    """

    h_top: float = 40.0
    f_ck: float = 25.0
    law: Literal['parabola', 'sargin'] = 'parabola'
    e_co2: float | None = None
    p_eur: float | None = None

    def material(self, gamma_c: float = 1.0, alpha_cc: float = 1.0):
        """Concrete law of the plate at the given partial-safety level."""
        if self.law == 'parabola':
            return EC2ParabolaRectangle(f_ck=self.f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c)
        f_cm = self.f_ck + 8.0
        E_cm = 22000.0 * (f_cm / 10.0) ** 0.3
        eps_c1 = -1e-3 * min(0.7 * f_cm ** 0.31, 2.8)
        return FoamConcrete(rho=2500.0, f_c=alpha_cc * self.f_ck, E=E_cm, eps_c1=eps_c1,
                            eps_cu=-0.0035, gamma=gamma_c, law='sargin')


@dataclass
class FloorSectionCRC:
    """Geometric and material parameters for a rectangular CRC section.

    Parameters
    ----------
    b     : section width [mm]
    h     : section height [mm]
    f_ck  : concrete characteristic compressive strength [MPa]
    A_s   : CFRP reinforcement area [mm²]
    z_s   : distance from bottom fibre to CFRP centroid [mm]
    E_f   : CFRP elastic modulus [MPa]
    f_fk  : CFRP characteristic tensile strength [MPa]

    Usage
    -----
    SLS  (characteristic strengths):
        cs = FloorSectionCRC(...).build_cs(gamma_c=1.0, gamma_f=1.0)
    ULS  (design strengths):
        cs = FloorSectionCRC(...).build_cs(gamma_c=1.5, gamma_f=1.25,
                                            alpha_cc=0.85)
    """

    b: float
    h: float
    f_ck: float = 30.0
    A_s: float = 100.0
    z_s: float = 50.0
    E_f: float = 210_000.0
    f_fk: float = 3000.0

    def build_cs(
        self,
        gamma_c: float = 1.0,
        gamma_f: float = 1.0,
        alpha_cc: float = 1.0,
    ) -> CrossSection:
        """Build a ``CrossSection`` with the requested partial-safety levels.

        For SLS use ``gamma_c=1.0, gamma_f=1.0, alpha_cc=1.0``.
        For ULS use ``gamma_c=1.5, gamma_f=1.25, alpha_cc=0.85``.
        """
        concrete = EC2ParabolaRectangle(
            f_ck=self.f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c
        )
        factor = 1.0 / gamma_f
        carbon = CarbonReinforcement(E=self.E_f, f_t=self.f_fk, factor=factor)
        layer = ReinforcementLayer(z=self.z_s, A_s=self.A_s, material=carbon)
        return CrossSection(
            shape=RectangularShape(b=self.b, h=self.h),
            concrete=concrete,
            reinforcement=ReinforcementLayout(layers=[layer]),
        )


@dataclass
class FloorSectionCRCRib:
    """T-section CRC rib for ribbed-slab analysis with CFRP reinforcement.

    The flange (top) represents the bay slab; the web (bottom) is the rib.

    Coordinate system (matches TShape):
        - y = 0  at the bottom of the web
        - y = h_w  at web/flange interface
        - y = h_w + h_f  at the top of the flange

    Parameters
    ----------
    b_w   : web (rib) width [mm]
    h_w   : web (rib) height below the flange [mm]
    b_f   : flange (bay-slab) width — typically = rib spacing [mm]
    h_f   : flange (bay-slab) thickness [mm]
    f_ck  : concrete characteristic compressive strength [MPa]
    A_s   : CFRP reinforcement area in the rib [mm²]
    z_s   : distance from bottom of web to CFRP centroid [mm]
    E_f   : CFRP elastic modulus [MPa]
    f_fk  : CFRP characteristic tensile strength [MPa]
    """

    b_w: float
    h_w: float
    b_f: float
    h_f: float
    f_ck: float = 30.0
    A_s: float = 100.0
    z_s: float = 50.0
    E_f: float = 210_000.0
    f_fk: float = 3000.0

    def build_cs(
        self,
        gamma_c: float = 1.0,
        gamma_f: float = 1.0,
        alpha_cc: float = 1.0,
    ) -> CrossSection:
        """Build a T-section ``CrossSection`` at the requested safety levels."""
        concrete = EC2ParabolaRectangle(
            f_ck=self.f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c
        )
        factor = 1.0 / gamma_f
        carbon = CarbonReinforcement(E=self.E_f, f_t=self.f_fk, factor=factor)
        layer = ReinforcementLayer(z=self.z_s, A_s=self.A_s, material=carbon)
        return CrossSection(
            shape=TShape(b_w=self.b_w, h_w=self.h_w, b_f=self.b_f, h_f=self.h_f),
            concrete=concrete,
            reinforcement=ReinforcementLayout(layers=[layer]),
        )


@dataclass
class FloorSectionCRCPiRib:
    """Inverted-T CRC rib of a Pi slab — plate (flange) at the bottom, web up.

    Coordinate system (matches InvTShape):
        - y = 0      at the plate soffit
        - y = h_f    plate top / web bottom
        - y = h_f + h_w   web top

    Tension reinforcement (D-PI2) — two CFRP layers in the plate:
        * ``A_s`` at ``z_s``: concentrated bars under the web (may be 0), and
        * ``A_grid`` at ``z_grid``: the longitudinal part of the plate grid
          within b_eff (``r_long·a_f·b_eff``), material ``E_grid / f_grid``.

    Optional composite components (``MatrixRegion``s of the section):
        * ``ballast`` — fill between the webs up to min(h_fill, h_w), above the
          web top over the full width b_f (label 'ballast');
        * ``top_plate`` — on max(fill top, web top) over b_f (label 'top plate').

    Parameters
    ----------
    b_w, h_w : web width / height above the plate [mm]
    b_f, h_f : plate effective width (b_eff) / thickness [mm]
    f_ck     : concrete strength of the inverted T [MPa]
    A_s, z_s, E_f, f_fk : concentrated rib bars [mm², mm, MPa, MPa]
    A_grid, z_grid, E_grid, f_grid : plate-grid layer (E/f None → E_f / f_fk)
    ballast, top_plate : optional components
    """

    b_w: float
    h_w: float
    b_f: float
    h_f: float
    f_ck: float = 30.0
    A_s: float = 150.0
    z_s: float = 25.0
    E_f: float = 210_000.0
    f_fk: float = 3000.0
    A_grid: float = 0.0
    z_grid: float = 15.0
    E_grid: float | None = None
    f_grid: float | None = None
    ballast: BallastSpec | None = None
    top_plate: TopPlateSpec | None = None

    @property
    def h_t(self) -> float:
        """Depth of the inverted T [mm]."""
        return self.h_f + self.h_w

    @property
    def y_top_plate(self) -> float:
        """Soffit of the top plate [mm]: on the fill or, if lower, on the webs."""
        h_fill = self.ballast.h_fill if self.ballast is not None else 0.0
        return max(self.h_t, self.h_f + h_fill)

    def layout(self, gamma_f: float = 1.0) -> ReinforcementLayout:
        """CFRP layers (zero areas skipped); the concentrated bars come first."""
        layers = []
        if self.A_s > 0.0:
            layers.append(ReinforcementLayer(
                z=self.z_s, A_s=self.A_s, name='rib bars',
                material=CarbonReinforcement(E=self.E_f, f_t=self.f_fk, factor=1.0 / gamma_f)))
        if self.A_grid > 0.0:
            E_g = self.E_grid if self.E_grid is not None else self.E_f
            f_g = self.f_grid if self.f_grid is not None else self.f_fk
            layers.append(ReinforcementLayer(
                z=self.z_grid, A_s=self.A_grid, name='plate grid',
                material=CarbonReinforcement(E=E_g, f_t=f_g, factor=1.0 / gamma_f)))
        if not layers:
            raise ValueError("Pi rib needs reinforcement: A_s and A_grid are both zero")
        return ReinforcementLayout(layers=layers)

    def regions(self, gamma_c: float = 1.0, alpha_cc: float = 1.0,
                gamma_agg: float = 1.0) -> list[MatrixRegion]:
        """Ballast band(s) and top plate as MatrixRegions (mass-only fill → none)."""
        regs = []
        b = self.ballast
        if b is not None and b.structural and b.h_fill > 0.0:
            foam = b.material(gamma_agg)
            y1 = self.h_f + min(b.h_fill, self.h_w)
            if self.b_f > self.b_w:
                regs.append(MatrixRegion(
                    shape=BandShape(y0=self.h_f, y1=y1, b=self.b_f - self.b_w, gap=self.b_w),
                    material=foam, label='ballast'))
            if b.h_fill > self.h_w:
                regs.append(MatrixRegion(
                    shape=BandShape(y0=self.h_t, y1=self.h_f + b.h_fill, b=self.b_f),
                    material=foam, label='ballast'))
        tp = self.top_plate
        if tp is not None and tp.h_top > 0.0:
            y0 = self.y_top_plate
            regs.append(MatrixRegion(
                shape=BandShape(y0=y0, y1=y0 + tp.h_top, b=self.b_f),
                material=tp.material(gamma_c, alpha_cc), label='top plate',
                color=TOP_PLATE_COLOR))
        return regs

    def build_cs(
        self,
        gamma_c: float = 1.0,
        gamma_f: float = 1.0,
        alpha_cc: float = 1.0,
        gamma_agg: float = 1.0,
    ) -> CrossSection:
        """Build the composite inverted-T ``CrossSection`` at the given safety levels.

        SLS: all factors 1.0.  ULS: ``gamma_c=1.5, gamma_f=1.25, alpha_cc=0.85``
        and ``gamma_agg = ballast.gamma`` for the fill.
        """
        concrete = EC2ParabolaRectangle(f_ck=self.f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c)
        return CrossSection(
            shape=InvTShape(b_w=self.b_w, h_w=self.h_w, b_f=self.b_f, h_f=self.h_f),
            concrete=concrete,
            reinforcement=self.layout(gamma_f),
            regions=self.regions(gamma_c, alpha_cc, gamma_agg),
        )
