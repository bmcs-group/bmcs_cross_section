"""
scite.beam.floor.pi_slab
========================

CRCPiSlab -- one-way CRC Pi slab: a continuous plate at the bottom with ribs
pointing upward (inverted-T rib), optionally with a ballast / insulation fill
between (and above) the ribs and a concrete top cover plate.

Pure Python dataclass -- no CFrame, usable directly in notebooks.

Geometry convention (as all ribbed slabs, ``_RibbedSlabBase``)
-------------------------------------------------------------
All lengths in mm.  ``H_rib`` is the TOTAL depth of the inverted T, ``H_bay``
the plate thickness, ``h_w = H_rib - H_bay`` the web height above the plate,
``b_eff`` the EC2 5.3.2.1 effective width of the (tension) plate.

          |<----------------- b_f = b_eff ----------------->|
          +--------------------------------------------------+  top plate (opt.)
          |  ballast fill above the web (opt., full width)   |
          +-------------------+---------+--------------------+  -- y = H_rib
          |  ballast fill     |   web   |   ballast fill     |
          |  (b_eff - b_w)    |  B_rib  |                    |
          +-------------------+---------+--------------------+  -- y = H_bay
          |     o grid (z_f_bay)    o bars (z_f_rib)         |  plate
          +--------------------------------------------------+  -- y = 0

Rib tension reinforcement (concept D-PI2): the concentrated bars ``A_f_rib``
plus the longitudinal plate grid inside b_eff, ``r_long * A_f_bay * b_eff``.
Ballast and top plate act in the rib direction only; for the transverse bay
strip (the plate spanning between the webs) they are mass only (D-PI6).
"""
from __future__ import annotations

from dataclasses import dataclass

from .floor_analysis import FloorAnalysisPair
from .load_model import LoadModel
from .ribbed_slab import CRCRibbedSlab
from .section_crc import BallastSpec, TopPlateSpec


@dataclass
class CRCPiSlab(CRCRibbedSlab):
    """One-way CRC Pi slab (inverted-T ribs) with optional ballast and top plate.

    Inherits all CFRP fields of ``CRCRibbedSlab`` (rib bars ``A_f_rib`` at
    ``z_f_rib``, plate grid ``A_f_bay`` [mm²/m] at ``z_f_bay`` with ``r_long``,
    materials and resource parameters) and adds:

    ballast   : BallastSpec | None  -- fill; ``h_fill`` from the plate top
    top_plate : TopPlateSpec | None -- cover plate on max(fill top, web top)
    """

    ballast:   BallastSpec | None = None
    top_plate: TopPlateSpec | None = None

    def __post_init__(self) -> None:
        self._rib_element_label = 'CRC Π rib'
        self._init_b_eff()
        if self.f_ck_bay is None:
            self.f_ck_bay = self.f_ck
        if self.f_fk_bay is None:
            self.f_fk_bay = self.f_fk
        if self.E_f_bay is None:
            self.E_f_bay = self.E_f
        # Rib: inverted T (plate in tension) + optional fill / top plate
        self.rib_beam = FloorAnalysisPair.for_crc_pi_rib(
            b_w=self.B_rib, h_w=self.h_w,
            b_f=self.b_eff, h_f=self.H_bay,
            f_ck=self.f_ck, A_s=self.A_f_rib, z_s=self.z_f_rib,
            E_f=self.E_f, f_fk=self.f_fk,
            A_grid=self.A_grid, z_grid=self.z_f_bay,
            E_grid=self.E_f_bay, f_grid=self.f_fk_bay,
            ballast=self.ballast, top_plate=self.top_plate,
            L_mm=self.L_rib, gamma_c=self.gamma_c, gamma_f=self.gamma_f,
        )
        # Bay: the plate as a 1 m strip spanning between the webs
        self.bay_beam = FloorAnalysisPair.for_crc(
            b=1000.0, h=self.H_bay,
            f_ck=self.f_ck_bay, A_s=self.A_f_bay, z_s=self.z_f_bay,
            E_f=self.E_f_bay, f_fk=self.f_fk_bay,
            L_mm=self.L_bay, gamma_c=self.gamma_c, gamma_f=self.gamma_f,
        )

    # ---- Derived geometry ----------------------------------------------------

    @property
    def A_grid(self) -> float:
        """Longitudinal plate grid inside b_eff acting as rib reinforcement [mm²]."""
        return self.r_long * self.A_f_bay * self.b_eff / 1000.0

    @property
    def h_fill(self) -> float:
        """Fill height above the plate [mm] (0 without ballast)."""
        return self.ballast.h_fill if self.ballast is not None else 0.0

    @property
    def h_top(self) -> float:
        """Top-plate thickness [mm] (0 without top plate)."""
        return self.top_plate.h_top if self.top_plate is not None else 0.0

    @property
    def H_total(self) -> float:
        """Overall floor depth incl. fill above the webs and top plate [mm]."""
        return max(self.H_rib, self.H_bay + self.h_fill) + self.h_top

    def _fill_top_volumes(self) -> tuple[float, float]:
        """(V_agg, V_top) per rib bay [m³] -- fill between/above the webs, top plate."""
        L_rib_m = self.L_rib * 1e-3
        L_bay_m = self.L_bay * 1e-3
        B_rib_m = self.B_rib * 1e-3
        h_w_m = self.h_w * 1e-3
        h_fill_m = self.h_fill * 1e-3
        V_agg = ((L_bay_m - B_rib_m) * min(h_fill_m, h_w_m)
                 + L_bay_m * max(h_fill_m - h_w_m, 0.0)) * L_rib_m
        V_top = L_bay_m * self.h_top * 1e-3 * L_rib_m
        return V_agg, V_top

    # ---- Self-weight ---------------------------------------------------------

    @property
    def g_k(self) -> float:
        """Structural self-weight [kN/m²]: inverted T + fill + top plate."""
        V_agg, V_top = self._fill_top_volumes()
        A_bay = self.L_rib * 1e-3 * self.L_bay * 1e-3
        rho_agg_kN = self.ballast.rho / 100.0 if self.ballast is not None else 0.0
        return super().g_k + (rho_agg_kN * V_agg + self.rho_conc * V_top) / A_bay

    # ---- Resources -----------------------------------------------------------

    def volumes(self) -> dict:
        """CRC ribbed-slab volumes (concrete, CFRP) plus fill and top plate.

        Additional keys:
          V_agg, m_agg_kg, gwp_agg, cost_agg   -- ballast fill
          V_top, m_top_kg, gwp_top, cost_top   -- top plate
        Totals and per-m² values include both.
        """
        v = super().volumes()
        V_agg, V_top = self._fill_top_volumes()
        b, tp = self.ballast, self.top_plate

        m_agg = V_agg * b.rho if b is not None else 0.0
        gwp_agg = m_agg * b.e_co2 if b is not None else 0.0
        cost_agg = V_agg * b.p_eur if b is not None else 0.0

        m_top = V_top * self.rho_conc * 100.0          # kN/m3 -> kg/m3
        e_top = tp.e_co2 if tp is not None and tp.e_co2 is not None else self.e_conc
        p_top = tp.p_eur if tp is not None and tp.p_eur is not None else self.p_conc
        gwp_top = m_top * e_top
        cost_top = V_top * p_top

        gwp_total = v['gwp_total'] + gwp_agg + gwp_top
        cost_total = v['cost_total'] + cost_agg + cost_top
        v.update(
            V_agg=V_agg, m_agg_kg=m_agg, gwp_agg=gwp_agg, cost_agg=cost_agg,
            V_top=V_top, m_top_kg=m_top, gwp_top=gwp_top, cost_top=cost_top,
            gwp_total=gwp_total, gwp_per_m2=gwp_total / v['A_bay'],
            cost_total=cost_total, cost_per_m2=cost_total / v['A_bay'],
        )
        return v

    # ---- Summary -------------------------------------------------------------

    def report(self, load_model: LoadModel | None = None) -> None:
        """Print a formatted summary."""
        print('CRCPiSlab')
        print(f'  Geometry  : H_rib={self.H_rib:.0f} (total)  H_bay={self.H_bay:.0f} (plate)  '
              f'B_rib={self.B_rib:.0f}  L_rib={self.L_rib/1e3:.2f} m  L_bay={self.L_bay:.0f} mm')
        print(f'  Inv. T    : b_w={self.B_rib:.0f}  h_w={self.h_w:.0f}  '
              f'b_f={self.b_eff:.0f}  h_f={self.H_bay:.0f}  [mm]  (EC2 b_eff)')
        print(f'  CFRP rib  : bars A_f={self.A_f_rib:.1f} mm2 @ {self.z_f_rib:.0f}  '
              f'grid A={self.A_grid:.1f} mm2 @ {self.z_f_bay:.0f}')
        if self.ballast is not None:
            b = self.ballast
            kind = 'structural' if b.structural else 'mass only'
            print(f'  Ballast   : {b.name}  h_fill={b.h_fill:.0f} mm  rho={b.rho:.0f} kg/m3  '
                  f'f_c={b.f_c:.2f}  E={b.E:.0f} MPa  ({kind})')
        if self.top_plate is not None:
            print(f'  Top plate : h_top={self.top_plate.h_top:.0f} mm  '
                  f'f_ck={self.top_plate.f_ck:.0f} MPa  ({self.top_plate.law})')
        print(f'  H_total   = {self.H_total:.0f} mm   g_k = {self.g_k:.2f} kN/m2')
        p_R_sls = self.rib_beam.sls.bda.F_R / self.s_m
        p_R_uls = self.rib_beam.uls.bda.F_R / self.s_m
        print(f'  Rib p_R   = {p_R_sls:.2f} kN/m2  (SLS)   {p_R_uls:.2f} kN/m2  (ULS)')
        if load_model:
            s = load_model.surface_loads(self.g_k)
            load_model.print_summary(self.g_k)
            if p_R_uls > 0:
                print(f'  eta_SLS = {s["p_Ed_qp"]/p_R_sls:.2f}   '
                      f'eta_ULS = {s["p_Ed_u"]/p_R_uls:.2f}')
        v = self.volumes()
        print(f'  V_c/m2 = {v["V_c_per_m2"]:.3f} m3/m2   '
              f'GWP = {v["gwp_per_m2"]:.1f} kgCO2/m2   '
              f'cost = {v["cost_per_m2"]:.1f} EUR/m2')
