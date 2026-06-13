"""
scite.beam.floor.ribbed_slab
=============================

_RibbedSlabBase  -- Shared geometry, concrete-volume helpers, and plotting methods.
SRCRibbedSlab    -- One-way ribbed slab with steel reinforcement.
CRCRibbedSlab    -- One-way ribbed slab with CFRP reinforcement in the rib.

Both concrete classes are pure Python dataclasses -- no CFrame, usable directly
in notebooks.  All shared geometry, self-weight, beam-element, and plotting logic
lives in _RibbedSlabBase; the subclasses only add their material-specific fields
and implement __post_init__ / volumes() / report().

Geometry convention
-------------------
All lengths in mm.  Coordinate origin at the bottom of the rib web.

  b_f = b_eff (EC2 effective flange width)
  |<---------------------- b_f --------------------->|
  +--------------------------------------------------+  -- h_f = H_bay (flange)
  |                                                  |
  |             |<-- b_w = B_rib -->|                |
  |             |                   |                |  -- h_w = H_rib - H_bay (web)
  |             |     o z_s (reinf) |                |
  +-------------+-------------------+----------------+  -- y = 0

b_f (effective flange width) is computed from EC2 para 5.3.2.1 via ec2_beff_rib().
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from scite.shared.units import UnitLevel, field_mm

from .flat_slab import (
    _E_CFRP_CO2,
    _E_CONC_CO2,
    _E_STEEL_CO2,
    _P_CFRP,
    _P_CONC,
    _P_REINF,
    _RHO_CFRP_KG,
    _RHO_CONCRETE_KN,
    _RHO_STEEL_KG,
    _plot_pw_demands,
)
from .floor_analysis import FloorAnalysisPair, ec2_beff_rib
from .floor_system_base import FloorSystemBase
from .load_model import BLUE, RED, LoadModel

# ---- Shared base class -------------------------------------------------------

@dataclass
class _RibbedSlabBase(FloorSystemBase):
    """Shared geometry, concrete volumes, and plotting logic for ribbed slabs.

    Subclasses (SRCRibbedSlab, CRCRibbedSlab) add their material-specific fields
    and implement __post_init__, volumes(), and report().
    """

    # ---- Shared geometry fields (all required — no default) ------------------
    H_rib:     float = field_mm(UnitLevel.CS_DIM)
    H_bay:     float = field_mm(UnitLevel.CS_DIM)
    B_rib:     float = field_mm(UnitLevel.CS_DIM)
    L_rib:     float = field_mm(UnitLevel.STRUCTURAL)
    L_bay:     float = field_mm(UnitLevel.STRUCTURAL)
    l0_factor: float = 1.0

    # ---- Shared safety / resource parameters (with defaults) -----------------
    rho_conc: float = _RHO_CONCRETE_KN
    gamma_c:  float = 1.50
    r_long:   float = 0.50
    e_conc:   float = _E_CONC_CO2
    p_conc:   float = _P_CONC

    # ---- Computed fields (initialised by subclass __post_init__) -------------
    b_eff:    float             = field(init=False, repr=False)
    rib_beam: FloorAnalysisPair = field(init=False, repr=False)
    bay_beam: FloorAnalysisPair = field(init=False, repr=False)

    # ---- Class-level label used in _beam_elements and plot_pw ----------------
    _rib_element_label: str = field(init=False, repr=False, default='Rib')

    # ---- Helpers called from subclass __post_init__ --------------------------

    def _init_b_eff(self) -> None:
        """Compute EC2 effective flange width and store in self.b_eff."""
        self.b_eff = ec2_beff_rib(
            b_w_mm=self.B_rib,
            L_bay_mm=self.L_bay,
            L_rib_mm=self.L_rib,
            l0_factor=self.l0_factor,
        )

    def _concrete_volumes(self) -> dict:
        """Concrete geometry and mass/GWP/cost — identical for SRC and CRC."""
        L_rib_m = self.L_rib * 1e-3
        L_bay_m = self.L_bay * 1e-3
        B_rib_m = self.B_rib * 1e-3
        h_w_m   = self.h_w   * 1e-3
        H_bay_m = self.H_bay * 1e-3

        V_c_rib = B_rib_m * h_w_m * L_rib_m
        V_c_bay = (L_bay_m - B_rib_m) * H_bay_m * L_rib_m
        V_c     = V_c_rib + V_c_bay
        A_bay   = L_rib_m * L_bay_m

        rho_c_kg = self.rho_conc * 100.0   # kN/m3 -> kg/m3
        m_c      = V_c * rho_c_kg
        gwp_conc = m_c * self.e_conc
        cost_conc = V_c * self.p_conc

        return dict(
            A_bay=A_bay,
            V_c=V_c, V_c_rib=V_c_rib, V_c_bay=V_c_bay,
            V_c_per_m2=V_c / A_bay,
            m_c_kg=m_c,
            gwp_conc=gwp_conc,
            cost_conc=cost_conc,
        )

    # ---- Derived geometry ----------------------------------------------------

    @property
    def h_w(self) -> float:
        """Rib web height [mm]."""
        return self.H_rib - self.H_bay

    @property
    def s_m(self) -> float:
        """Rib spacing / tributary width [m]."""
        return self.L_bay / 1000.0

    # ---- Self-weight ---------------------------------------------------------

    @property
    def g_k(self) -> float:
        """Structural self-weight per m2 floor area [kN/m2]."""
        L_rib_m = self.L_rib * 1e-3
        L_bay_m = self.L_bay * 1e-3
        B_rib_m = self.B_rib * 1e-3
        h_w_m   = self.h_w   * 1e-3
        H_bay_m = self.H_bay * 1e-3
        V_web   = B_rib_m * h_w_m * L_rib_m
        V_fla   = (L_bay_m - B_rib_m) * H_bay_m * L_rib_m
        A_bay   = L_rib_m * L_bay_m
        return self.rho_conc * (V_web + V_fla) / A_bay

    # ---- FloorSystemBase hook ------------------------------------------------

    def _beam_elements(self) -> list:
        return [
            (self.bay_beam, 1.0,      'Bay slab'),
            (self.rib_beam, self.s_m, self._rib_element_label),
        ]

    # ---- Plotting ------------------------------------------------------------

    def plot_pw(self, ax,
                load_model: LoadModel | None = None,
                *,
                element: str = 'rib',
                title: str = '') -> None:
        """p-w capacity curve for the rib or bay slab with demand lines."""
        if element == 'rib':
            beam   = self.rib_beam
            w_trib = self.s_m
            L_mm   = self.L_rib
            auto   = (
                f'{self._rib_element_label}  '
                f'$b_w$={self.B_rib:.0f},  $h_w$={self.h_w:.0f},  '
                f'$b_f$={self.b_eff:.0f},  $h_f$={self.H_bay:.0f} mm\n'
                f'$L_{{rib}}$ = {self.L_rib/1e3:.2f} m,  '
                f'trib. = {self.s_m:.3f} m'
            )
        elif element == 'bay':
            beam   = self.bay_beam
            w_trib = 1.0
            L_mm   = self.L_bay
            auto   = (
                f'Bay slab  $h$={self.H_bay:.0f} mm,  '
                f'$L_{{bay}}$={self.L_bay:.0f} mm'
            )
        else:
            raise ValueError(f"element must be 'rib' or 'bay', got {element!r}")

        s = load_model.surface_loads(self.g_k) if load_model else None
        _plot_pw_demands(
            ax, beam,
            w_trib_m=w_trib,
            L_mm=L_mm,
            s=s,
            title=title or auto,
        )

    def plot_floor_assessment(self, axes,
                              load_model: LoadModel | None = None) -> None:
        """Three-panel assessment: load breakdown, bay p-w, rib p-w."""
        ax_load, ax_bay, ax_rib = axes
        if load_model:
            load_model.plot_breakdown(ax_load, self.g_k)
        else:
            ax_load.text(0.5, 0.5, 'no load model', ha='center', va='center',
                         transform=ax_load.transAxes)
        self.plot_pw(ax_bay, load_model, element='bay')
        self.plot_pw(ax_rib, load_model, element='rib')


# ---- SRC ribbed slab ---------------------------------------------------------

@dataclass
class SRCRibbedSlab(_RibbedSlabBase):
    """One-way ribbed slab with conventional steel reinforcement.

    Inherits all geometry fields, self-weight, plotting and concrete-volume
    logic from _RibbedSlabBase.  Only the steel-specific fields and the
    reinforcement portion of volumes() are defined here.

    Rib cross-section
    -----------------
    A_s_rib  : tensile steel in rib [mm2]
    z_s_rib  : cover from bottom of rib web to steel centroid [mm]
    f_ck     : concrete strength [MPa]
    f_yk     : steel yield strength [MPa]

    Bay slab cross-section
    ----------------------
    f_ck_bay : concrete strength of bay slab (None → use f_ck)
    f_yk_bay : steel yield strength of bay slab (None → use f_yk)
    A_s_bay  : tensile steel in bay slab [mm2/m]
    z_s_bay  : cover from bay slab bottom to steel centroid [mm]

    Safety / resource parameters
    ----------------------------
    gamma_s   : steel partial safety factor
    rho_steel : steel density [kg/m3]
    e_steel   : steel embodied CO2 [kgCO2/kg]
    p_reinf   : reinforcement unit cost [EUR/kg]
    """

    # ---- Rib steel section ---------------------------------------------------
    A_s_rib: float = field_mm(UnitLevel.REINF_AREA, 226.0)
    z_s_rib: float = field_mm(UnitLevel.CS_DIM,      35.0)
    f_ck:    float = 30.0
    f_yk:    float = 500.0

    # ---- Bay slab (optional separate grade) ----------------------------------
    f_ck_bay: float | None = None
    f_yk_bay: float | None = None
    A_s_bay: float = field_mm(UnitLevel.REINF_AREA, 150.0)
    z_s_bay: float = field_mm(UnitLevel.CS_DIM,      20.0)

    # ---- Steel safety / resource parameters ----------------------------------
    gamma_s:   float = 1.15
    rho_steel: float = _RHO_STEEL_KG
    e_steel:   float = _E_STEEL_CO2
    p_reinf:   float = _P_REINF

    def __post_init__(self) -> None:
        self._init_b_eff()
        # Resolve optional slab-specific grades (default to rib grades)
        if self.f_ck_bay is None:
            self.f_ck_bay = self.f_ck
        if self.f_yk_bay is None:
            self.f_yk_bay = self.f_yk
        # Rib: T-section (web + effective flange)
        self.rib_beam = FloorAnalysisPair.for_rc_rib(
            b_w=self.B_rib, h_w=self.h_w,
            b_f=self.b_eff, h_f=self.H_bay,
            f_ck=self.f_ck, A_s=self.A_s_rib, z_s=self.z_s_rib, f_yk=self.f_yk,
            L_mm=self.L_rib, gamma_c=self.gamma_c, gamma_s=self.gamma_s,
        )
        # Bay slab: rectangular (1 m wide strip over the bay span)
        self.bay_beam = FloorAnalysisPair.for_rc(
            b=1000.0, h=self.H_bay,
            f_ck=self.f_ck_bay, A_s=self.A_s_bay, z_s=self.z_s_bay, f_yk=self.f_yk_bay,
            L_mm=self.L_bay, gamma_c=self.gamma_c, gamma_s=self.gamma_s,
        )

    # ---- Resources -----------------------------------------------------------

    def volumes(self) -> dict:
        """Concrete and steel volumes, masses, GWP and cost per rib bay.

        Bay slab reinforcement includes transverse (A_s_bay) and longitudinal
        (r_long fraction) steel, spanning the full area L_rib × L_bay.

        Returns
        -------
        dict with keys:
          A_bay                               -- floor area per bay [m2]
          V_c, V_c_rib, V_c_bay, V_c_per_m2  -- concrete [m3]
          V_s_rib, V_s_bay, V_s              -- steel [m3/bay]
          m_c_kg, m_s_rib_kg, m_s_bay_kg, m_s_kg  -- masses [kg/bay]
          gwp_conc, gwp_s_rib, gwp_s_bay, gwp_steel, gwp_total, gwp_per_m2
          cost_conc, cost_s_rib, cost_s_bay, cost_steel, cost_total, cost_per_m2
        """
        cv = self._concrete_volumes()
        A_bay   = cv['A_bay']
        L_rib_m = self.L_rib * 1e-3
        L_bay_m = self.L_bay * 1e-3

        A_s_rib_m2 = self.A_s_rib * 1e-6   # mm2 -> m2
        A_s_bay_m2 = self.A_s_bay * 1e-6   # mm2/m -> m2/m

        # Steel volumes [m3 per bay]
        V_s_rib = A_s_rib_m2 * L_rib_m
        V_s_bay = A_s_bay_m2 * (1.0 + self.r_long) * L_bay_m * L_rib_m
        V_s     = V_s_rib + V_s_bay

        # Masses [kg]
        m_s_rib = V_s_rib * self.rho_steel
        m_s_bay = V_s_bay * self.rho_steel
        m_s     = m_s_rib + m_s_bay

        # GWP [kgCO2eq]
        gwp_s_rib = m_s_rib * self.e_steel
        gwp_s_bay = m_s_bay * self.e_steel
        gwp_steel = gwp_s_rib + gwp_s_bay
        gwp_total = cv['gwp_conc'] + gwp_steel

        # Cost [EUR]
        cost_s_rib = m_s_rib * self.p_reinf
        cost_s_bay = m_s_bay * self.p_reinf
        cost_steel = cost_s_rib + cost_s_bay
        cost_total = cv['cost_conc'] + cost_steel

        return dict(
            **cv,
            # Steel
            V_s_rib=V_s_rib, V_s_bay=V_s_bay, V_s=V_s,
            # Masses
            m_s_rib_kg=m_s_rib, m_s_bay_kg=m_s_bay, m_s_kg=m_s,
            # GWP
            gwp_s_rib=gwp_s_rib, gwp_s_bay=gwp_s_bay,
            gwp_steel=gwp_steel,
            gwp_total=gwp_total, gwp_per_m2=gwp_total / A_bay,
            # Cost
            cost_s_rib=cost_s_rib, cost_s_bay=cost_s_bay,
            cost_steel=cost_steel,
            cost_total=cost_total, cost_per_m2=cost_total / A_bay,
        )

    # ---- Summary -------------------------------------------------------------

    def report(self, load_model: LoadModel | None = None) -> None:
        """Print a formatted summary."""
        print('SRCRibbedSlab')
        print(f'  Geometry  : H_rib={self.H_rib:.0f}  H_bay={self.H_bay:.0f}  '
              f'B_rib={self.B_rib:.0f}  '
              f'L_rib={self.L_rib/1e3:.2f} m  L_bay={self.L_bay:.0f} mm')
        print(f'  T-section : b_w={self.B_rib:.0f}  h_w={self.h_w:.0f}  '
              f'b_f={self.b_eff:.0f}  h_f={self.H_bay:.0f}  [mm]  (EC2 b_eff)')
        print(f'  g_k       = {self.g_k:.2f} kN/m2  (self-weight, incl. web + bay slab)')
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


# ---- CRC ribbed slab ---------------------------------------------------------

@dataclass
class CRCRibbedSlab(_RibbedSlabBase):
    """One-way ribbed slab with CFRP reinforcement in rib and bay slab.

    Inherits all geometry fields, self-weight, plotting and concrete-volume
    logic from _RibbedSlabBase.  Only the CFRP-specific fields and the
    reinforcement portion of volumes() are defined here.

    Rib CFRP reinforcement
    ----------------------
    A_f_rib  : CFRP area in rib [mm2]
    z_f_rib  : cover from bottom of rib web to CFRP centroid [mm]
    f_ck     : concrete strength [MPa]
    E_f      : CFRP elastic modulus [MPa]
    f_fk     : CFRP characteristic tensile strength [MPa]

    Bay slab (CFRP — may use different grade)
    -----------------------------------------
    f_ck_bay : concrete strength of bay slab (None → use f_ck)
    f_fk_bay : CFRP tensile strength for bay slab (None → use f_fk)
    E_f_bay  : CFRP elastic modulus for bay slab (None → use E_f)
    A_f_bay  : CFRP area in bay slab [mm2/m]
    z_f_bay  : cover from bay slab bottom to CFRP centroid [mm]

    Safety / resource parameters
    ----------------------------
    gamma_f  : CFRP partial safety factor
    rho_cfrp : CFRP density [kg/m3]
    e_cfrp   : CFRP embodied CO2 [kgCO2/kg]
    p_cfrp   : CFRP unit cost [EUR/kg]
    """

    # ---- Rib CFRP section ----------------------------------------------------
    A_f_rib: float = field_mm(UnitLevel.REINF_AREA, 150.0)
    z_f_rib: float = field_mm(UnitLevel.CS_DIM,      30.0)
    f_ck:    float = 30.0
    E_f:     float = 210_000.0
    f_fk:    float = 3000.0

    # ---- Bay slab (CFRP, may use different material) -------------------------
    f_ck_bay:  float | None = None   # defaults to f_ck if not set
    f_fk_bay:  float | None = None   # defaults to f_fk if not set
    E_f_bay:   float | None = None   # defaults to E_f  if not set
    A_f_bay: float = field_mm(UnitLevel.REINF_AREA, 150.0)
    z_f_bay: float = field_mm(UnitLevel.CS_DIM,      20.0)

    # ---- CFRP safety / resource parameters -----------------------------------
    gamma_f:  float = 1.25
    rho_cfrp: float = _RHO_CFRP_KG
    e_cfrp:   float = _E_CFRP_CO2
    p_cfrp:   float = _P_CFRP

    def __post_init__(self) -> None:
        self._rib_element_label = 'CRC rib'
        self._init_b_eff()
        # Resolve optional slab-specific grades (default to rib grades)
        if self.f_ck_bay is None:
            self.f_ck_bay = self.f_ck
        if self.f_fk_bay is None:
            self.f_fk_bay = self.f_fk
        if self.E_f_bay is None:
            self.E_f_bay = self.E_f
        self.rib_beam = FloorAnalysisPair.for_crc_rib(
            b_w=self.B_rib, h_w=self.h_w,
            b_f=self.b_eff, h_f=self.H_bay,
            f_ck=self.f_ck, A_s=self.A_f_rib, z_s=self.z_f_rib,
            E_f=self.E_f, f_fk=self.f_fk,
            L_mm=self.L_rib, gamma_c=self.gamma_c, gamma_f=self.gamma_f,
        )
        # Bay slab: rectangular CRC strip (uses slab-specific material)
        self.bay_beam = FloorAnalysisPair.for_crc(
            b=1000.0, h=self.H_bay,
            f_ck=self.f_ck_bay, A_s=self.A_f_bay, z_s=self.z_f_bay,
            E_f=self.E_f_bay, f_fk=self.f_fk_bay,
            L_mm=self.L_bay, gamma_c=self.gamma_c, gamma_f=self.gamma_f,
        )

    # ---- Resources -----------------------------------------------------------

    def volumes(self) -> dict:
        """Concrete and CFRP volumes, masses, GWP and cost per rib bay.

        Both rib and bay slab reinforcement are accounted as CFRP for GWP/cost.
        Bay slab volume includes transverse (main) + longitudinal (r_long fraction).

        Returns
        -------
        dict with keys:
          A_bay                                     -- floor area per bay [m2]
          V_c, V_c_rib, V_c_bay, V_c_per_m2        -- concrete [m3]
          V_f_rib, V_f_bay, V_f                    -- CFRP [m3/bay]
          m_c_kg, m_f_rib_kg, m_f_bay_kg, m_f_kg  -- masses [kg/bay]
          gwp_conc, gwp_f_rib, gwp_f_bay, gwp_cfrp, gwp_total, gwp_per_m2
          cost_conc, cost_f_rib, cost_f_bay, cost_cfrp, cost_total, cost_per_m2
        """
        cv = self._concrete_volumes()
        A_bay   = cv['A_bay']
        L_rib_m = self.L_rib * 1e-3
        L_bay_m = self.L_bay * 1e-3

        A_f_rib_m2 = self.A_f_rib * 1e-6   # mm2 -> m2
        A_f_bay_m2 = self.A_f_bay * 1e-6   # mm2/m -> m2/m

        # CFRP volumes [m3 per bay]
        V_f_rib = A_f_rib_m2 * L_rib_m
        V_f_bay = A_f_bay_m2 * (1.0 + self.r_long) * L_bay_m * L_rib_m
        V_f     = V_f_rib + V_f_bay

        # Masses [kg]
        m_f_rib = V_f_rib * self.rho_cfrp
        m_f_bay = V_f_bay * self.rho_cfrp
        m_f     = m_f_rib + m_f_bay

        # GWP [kgCO2eq]
        gwp_f_rib = m_f_rib * self.e_cfrp
        gwp_f_bay = m_f_bay * self.e_cfrp
        gwp_cfrp  = gwp_f_rib + gwp_f_bay
        gwp_total = cv['gwp_conc'] + gwp_cfrp

        # Cost [EUR]
        cost_f_rib = m_f_rib * self.p_cfrp
        cost_f_bay = m_f_bay * self.p_cfrp
        cost_cfrp  = cost_f_rib + cost_f_bay
        cost_total = cv['cost_conc'] + cost_cfrp

        return dict(
            **cv,
            # CFRP
            V_f_rib=V_f_rib, V_f_bay=V_f_bay, V_f=V_f,
            # Masses
            m_f_rib_kg=m_f_rib, m_f_bay_kg=m_f_bay, m_f_kg=m_f,
            # GWP
            gwp_f_rib=gwp_f_rib, gwp_f_bay=gwp_f_bay,
            gwp_cfrp=gwp_cfrp,
            gwp_total=gwp_total, gwp_per_m2=gwp_total / A_bay,
            # Cost
            cost_f_rib=cost_f_rib, cost_f_bay=cost_f_bay,
            cost_cfrp=cost_cfrp,
            cost_total=cost_total, cost_per_m2=cost_total / A_bay,
        )

    # ---- Summary -------------------------------------------------------------

    def report(self, load_model: LoadModel | None = None) -> None:
        """Print a formatted summary."""
        print('CRCRibbedSlab')
        print(f'  Geometry  : H_rib={self.H_rib:.0f}  H_bay={self.H_bay:.0f}  '
              f'B_rib={self.B_rib:.0f}  '
              f'L_rib={self.L_rib/1e3:.2f} m  L_bay={self.L_bay:.0f} mm')
        print(f'  T-section : b_w={self.B_rib:.0f}  h_w={self.h_w:.0f}  '
              f'b_f={self.b_eff:.0f}  h_f={self.H_bay:.0f}  [mm]  (EC2 b_eff)')
        print(f'  CFRP rib  : A_f={self.A_f_rib:.1f} mm2  '
              f'E_f={self.E_f:.0f} MPa  f_fk={self.f_fk:.0f} MPa')
        print(f'  g_k       = {self.g_k:.2f} kN/m2')
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
