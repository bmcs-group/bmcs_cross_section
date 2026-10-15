"""
scite.beam.floor.section_rc
============================

FloorSectionRC — lightweight container for a rectangular RC cross-section
that can build a Pydantic ``CrossSection`` at SLS or ULS material levels.
"""
from __future__ import annotations

from dataclasses import dataclass

from scite.cs_design import (
    CrossSection,
    RectangularShape,
    ReinforcementLayer,
    ReinforcementLayout,
)
from scite.cs_design.shapes import TShape
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.matmod.steel_reinforcement import SteelReinforcement


@dataclass
class FloorSectionRC:
    """Geometric and material parameters for a rectangular RC section.

    Parameters
    ----------
    b     : section width [mm]
    h     : section height [mm]
    f_ck  : concrete characteristic compressive strength [MPa]
    f_yk  : steel characteristic yield strength [MPa]
    A_s   : tensile reinforcement area [mm²]
    z_s   : distance from bottom fibre to steel centroid [mm]

    Usage
    -----
    SLS  (mean/characteristic strengths):
        cs = FloorSectionRC(...).build_cs(gamma_c=1.0, gamma_s=1.0)
    ULS  (design strengths, EC2 default):
        cs = FloorSectionRC(...).build_cs(gamma_c=1.5, gamma_s=1.15,
                                          alpha_cc=0.85)
    """

    b: float
    h: float
    f_ck: float = 30.0
    f_yk: float = 500.0
    A_s: float = 100.0
    z_s: float = 50.0

    def build_cs(
        self,
        gamma_c: float = 1.0,
        gamma_s: float = 1.0,
        alpha_cc: float = 1.0,
    ) -> CrossSection:
        """Build a ``CrossSection`` with the requested partial-safety levels.

        For SLS use ``gamma_c=1.0, gamma_s=1.0, alpha_cc=1.0``.
        For ULS use ``gamma_c=1.5, gamma_s=1.15, alpha_cc=0.85``.
        """
        concrete = EC2ParabolaRectangle(
            f_ck=self.f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c
        )
        steel = SteelReinforcement(f_yk=self.f_yk, gamma_s=gamma_s)
        layer = ReinforcementLayer(z=self.z_s, A_s=self.A_s, material=steel)
        return CrossSection(
            shape=RectangularShape(b=self.b, h=self.h),
            concrete=concrete,
            reinforcement=ReinforcementLayout(layers=[layer]),
        )


@dataclass
class FloorSectionRCRib:
    """T-section RC rib for ribbed-slab analysis.

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
    f_yk  : steel characteristic yield strength [MPa]
    A_s   : tensile reinforcement area in the rib [mm²]
    z_s   : distance from bottom of web to steel centroid [mm]
    """

    b_w: float
    h_w: float
    b_f: float
    h_f: float
    f_ck: float = 30.0
    f_yk: float = 500.0
    A_s: float = 100.0
    z_s: float = 50.0

    def build_cs(
        self,
        gamma_c: float = 1.0,
        gamma_s: float = 1.0,
        alpha_cc: float = 1.0,
    ) -> CrossSection:
        """Build a T-section ``CrossSection`` at the requested safety levels."""
        concrete = EC2ParabolaRectangle(
            f_ck=self.f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c
        )
        steel = SteelReinforcement(f_yk=self.f_yk, gamma_s=gamma_s)
        layer = ReinforcementLayer(z=self.z_s, A_s=self.A_s, material=steel)
        return CrossSection(
            shape=TShape(b_w=self.b_w, h_w=self.h_w, b_f=self.b_f, h_f=self.h_f),
            concrete=concrete,
            reinforcement=ReinforcementLayout(layers=[layer]),
        )
