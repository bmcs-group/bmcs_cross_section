"""
scite.beam.floor.floor_analysis
================================

FloorAnalysis    — single BeamDeflectionAnalysis (dist load) with tributary-
                   width conversion from F [N/mm=kN/m] → p [kN/m²].

FloorAnalysisPair — SLS + ULS pair; drop-in replacement for the legacy
                    ``(dp_sls, dp_uls)`` tuple produced by
                    ``FloorSystem._build_dp_pair[_cfrp]``.

These classes are intentionally lightweight (plain Python dataclasses) because
they are constructed fresh on every ``update_plot`` call — no Pydantic overhead
is needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from scite.beam.bending.beam_deflection import BeamDeflectionAnalysis
from scite.cs_design import CrossSection


def ec2_beff_rib(
    b_w_mm: float,
    L_bay_mm: float,
    L_rib_mm: float,
    l0_factor: float = 1.0,
) -> float:
    """EC2 5.3.2.1 — effective flange width for a T-section rib.

    For a rib uniformly spaced at *L_bay_mm* centre-to-centre, the flange
    overhangs on each side are:

    .. math::
        b_i = (L_{\\mathrm{bay}} - b_w) / 2

    The effective contribution of each overhang (EC2 Eq. 5.7a / 5.7b):

    .. math::
        b_{\\mathrm{eff},i} = \\min\\!
            \\bigl(0.2\\,b_i + 0.1\\,l_0,\\; 0.2\\,l_0,\\; b_i\\bigr)

    And the total effective flange width (EC2 Eq. 5.7):

    .. math::
        b_{\\mathrm{eff}} = 2\\,b_{\\mathrm{eff},i} + b_w

    Parameters
    ----------
    b_w_mm    : rib web width [mm]
    L_bay_mm  : rib spacing, centre-to-centre [mm]
    L_rib_mm  : rib span [mm]
    l0_factor : fraction of *L_rib_mm* used as the zero-moment distance l₀.
                Default 1.0 (simply supported, zero moment at both ends).
                Use 0.85 for an end span or 0.70 for an interior span of a
                continuous beam (EC2 Fig. 5.2).

    Returns
    -------
    beff : float
        Effective flange width *including* the web [mm].
        Bounded above by *L_bay_mm* (cannot exceed the rib spacing).
    """
    l0 = l0_factor * L_rib_mm
    b_i = max((L_bay_mm - b_w_mm) / 2.0, 0.0)   # overhang each side
    beff_i = min(0.2 * b_i + 0.1 * l0, 0.2 * l0, b_i)
    beff = 2.0 * beff_i + b_w_mm
    return beff


@dataclass
class FloorAnalysis:
    """Single nonlinear distributed-load analysis for a floor section.

    Wraps ``BeamDeflectionAnalysis`` and converts the internal force
    F [N/mm = kN/m] to surface pressure p [kN/m²] via a tributary width.

    Parameters
    ----------
    cs       : cross-section (Pydantic model)
    L_mm     : beam span [mm]
    n_load_steps : load increments for the F-w curve (default 41)
    n_kappa  : curvature steps for the M-κ solver (default 150)
    """

    cs: CrossSection
    L_mm: float
    n_load_steps: int = 41
    n_kappa: int = 150

    # Lazily built
    _bda: Optional[BeamDeflectionAnalysis] = field(default=None, init=False, repr=False)

    @property
    def bda(self) -> BeamDeflectionAnalysis:
        """Return (and cache) the underlying BeamDeflectionAnalysis."""
        if self._bda is None:
            self._bda = BeamDeflectionAnalysis(
                cs=self.cs,
                L=self.L_mm,
                load_type='dist',
                n_load_steps=self.n_load_steps,
                n_kappa=self.n_kappa,
            )
        return self._bda

    def get_Fw(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return (F_arr [N/mm], w_arr [mm]) load-deflection curve."""
        return self.bda.get_Fw()

    def get_pw(self, w_trib_m: float) -> Tuple[np.ndarray, np.ndarray]:
        """Return (p_arr [kN/m²], w_arr [mm]) at tributary width *w_trib_m* [m]."""
        F_arr, w_arr = self.get_Fw()
        # F [N/mm] = [kN/m] → p [kN/m²] = F [kN/m] / w_trib [m]
        p_arr = F_arr / w_trib_m
        return p_arr, w_arr

    def get_w_x(self, F: float) -> np.ndarray:
        """Deflection profile [mm] (positive downward) at load F [N/mm]."""
        return self.bda.get_w_x(F)

    def get_kappa_x(self, F: float) -> np.ndarray:
        """Curvature profile [1/mm] at load F [N/mm]."""
        return self.bda.get_kappa_x(F)

    @property
    def x(self) -> np.ndarray:
        """Spatial coordinate array [mm] from 0 to L."""
        return self.bda.x


@dataclass
class FloorAnalysisPair:
    """SLS / ULS pair of FloorAnalysis objects.

    Drop-in replacement for the ``(dp_sls, dp_uls)`` tuple produced by the
    legacy ``FloorSystem._build_dp_pair[_cfrp]`` helpers.

    Parameters
    ----------
    sls, uls : FloorAnalysis built with appropriate partial-safety factors.
    """

    sls: FloorAnalysis
    uls: FloorAnalysis

    @classmethod
    def for_rc(
        cls,
        b: float, h: float, f_ck: float,
        A_s: float, z_s: float, f_yk: float,
        L_mm: float,
        gamma_c: float = 1.5, gamma_s: float = 1.15, alpha_cc: float = 0.85,
        n_load_steps: int = 41,
    ) -> "FloorAnalysisPair":
        """Build SLS + ULS pair for a rectangular RC section.

        SLS: characteristic concrete (f_ck, no safety factors),
             characteristic steel (f_yk).
        ULS: EC2 design values (alpha_cc=0.85, gamma_c=1.5, gamma_s=1.15).
        """
        from scite.beam.floor.section_rc import FloorSectionRC

        sec = FloorSectionRC(b=b, h=h, f_ck=f_ck, f_yk=f_yk, A_s=A_s, z_s=z_s)
        cs_sls = sec.build_cs(gamma_c=1.0, gamma_s=1.0, alpha_cc=1.0)
        cs_uls = sec.build_cs(gamma_c=gamma_c, gamma_s=gamma_s, alpha_cc=alpha_cc)
        return cls(
            sls=FloorAnalysis(cs=cs_sls, L_mm=L_mm, n_load_steps=n_load_steps),
            uls=FloorAnalysis(cs=cs_uls, L_mm=L_mm, n_load_steps=n_load_steps),
        )

    @classmethod
    def for_crc(
        cls,
        b: float, h: float, f_ck: float,
        A_s: float, z_s: float,
        E_f: float, f_fk: float,
        L_mm: float,
        gamma_c: float = 1.5, gamma_f: float = 1.25, alpha_cc: float = 0.85,
        n_load_steps: int = 41,
    ) -> "FloorAnalysisPair":
        """Build SLS + ULS pair for a rectangular CRC section.

        SLS: characteristic concrete (no safety factors), CFRP factor = 1.0.
        ULS: EC2 design concrete + CFRP factor = 1/gamma_f.
        """
        from scite.beam.floor.section_crc import FloorSectionCRC

        sec = FloorSectionCRC(b=b, h=h, f_ck=f_ck, A_s=A_s, z_s=z_s,
                              E_f=E_f, f_fk=f_fk)
        cs_sls = sec.build_cs(gamma_c=1.0, gamma_f=1.0, alpha_cc=1.0)
        cs_uls = sec.build_cs(gamma_c=gamma_c, gamma_f=gamma_f, alpha_cc=alpha_cc)
        return cls(
            sls=FloorAnalysis(cs=cs_sls, L_mm=L_mm, n_load_steps=n_load_steps),
            uls=FloorAnalysis(cs=cs_uls, L_mm=L_mm, n_load_steps=n_load_steps),
        )

    @classmethod
    def for_rc_rib(
        cls,
        b_w: float, h_w: float, b_f: float, h_f: float,
        f_ck: float, A_s: float, z_s: float, f_yk: float,
        L_mm: float,
        gamma_c: float = 1.5, gamma_s: float = 1.15, alpha_cc: float = 0.85,
        n_load_steps: int = 41,
    ) -> "FloorAnalysisPair":
        """Build SLS + ULS pair for a T-section RC rib.

        Parameters
        ----------
        b_w, h_w : web (rib) width and height below the flange [mm]
        b_f, h_f : flange (bay-slab) width and thickness [mm]
                   b_f is typically the rib spacing; h_f the slab thickness.
        z_s      : distance from the bottom of the web to the steel centroid [mm]
        """
        from scite.beam.floor.section_rc import FloorSectionRCRib

        sec = FloorSectionRCRib(b_w=b_w, h_w=h_w, b_f=b_f, h_f=h_f,
                                f_ck=f_ck, f_yk=f_yk, A_s=A_s, z_s=z_s)
        cs_sls = sec.build_cs(gamma_c=1.0, gamma_s=1.0, alpha_cc=1.0)
        cs_uls = sec.build_cs(gamma_c=gamma_c, gamma_s=gamma_s, alpha_cc=alpha_cc)
        return cls(
            sls=FloorAnalysis(cs=cs_sls, L_mm=L_mm, n_load_steps=n_load_steps),
            uls=FloorAnalysis(cs=cs_uls, L_mm=L_mm, n_load_steps=n_load_steps),
        )

    @classmethod
    def for_crc_rib(
        cls,
        b_w: float, h_w: float, b_f: float, h_f: float,
        f_ck: float, A_s: float, z_s: float,
        E_f: float, f_fk: float,
        L_mm: float,
        gamma_c: float = 1.5, gamma_f: float = 1.25, alpha_cc: float = 0.85,
        n_load_steps: int = 41,
    ) -> "FloorAnalysisPair":
        """Build SLS + ULS pair for a T-section CRC rib with CFRP reinforcement.

        Parameters
        ----------
        b_w, h_w : web (rib) width and height below the flange [mm]
        b_f, h_f : flange (bay-slab) width and thickness [mm]
        z_s      : distance from the bottom of the web to the CFRP centroid [mm]
        """
        from scite.beam.floor.section_crc import FloorSectionCRCRib

        sec = FloorSectionCRCRib(b_w=b_w, h_w=h_w, b_f=b_f, h_f=h_f,
                                 f_ck=f_ck, A_s=A_s, z_s=z_s, E_f=E_f, f_fk=f_fk)
        cs_sls = sec.build_cs(gamma_c=1.0, gamma_f=1.0, alpha_cc=1.0)
        cs_uls = sec.build_cs(gamma_c=gamma_c, gamma_f=gamma_f, alpha_cc=alpha_cc)
        return cls(
            sls=FloorAnalysis(cs=cs_sls, L_mm=L_mm, n_load_steps=n_load_steps),
            uls=FloorAnalysis(cs=cs_uls, L_mm=L_mm, n_load_steps=n_load_steps),
        )
