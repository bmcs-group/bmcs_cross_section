"""
scite.beam.floor.flat_slab
===========================

FlatSlab    -- Simply supported SRC flat slab (rectangular section, 1 m wide strip).
CRCFlatSlab -- Simply supported CRC flat slab (CFRP reinforcement, 1 m wide strip).

Pure Python dataclasses -- no CFrame, usable directly in notebooks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from scite.shared.units import UnitLevel, field_mm

from .floor_analysis import FloorAnalysisPair
from .floor_system_base import FloorSystemBase
from .load_model import BLUE, RED, LoadModel

# ---- Default material constants (used as field defaults) ---------------------
_RHO_CONCRETE_KN = 25.0     # kN/m3 (= 2500 kg/m3 at g = 10 m/s2)
_RHO_STEEL_KG    = 7850.0   # kg/m3
_RHO_CFRP_KG     = 1600.0   # kg/m3
_E_CONC_CO2      = 0.17     # kgCO2/kg -- concrete
_E_STEEL_CO2     = 1.50     # kgCO2/kg -- reinforcing steel
_E_CFRP_CO2      = 19.0     # kgCO2/kg -- CFRP (icc_app default)
_P_CONC          = 150.0    # EUR/m3  -- concrete (placement incl. formwork)
_P_REINF         = 1.20     # EUR/kg  -- reinforcing steel
_P_CFRP          = 100.0    # EUR/kg  -- CFRP


# ---- p-w demand plot (shared helper) ----------------------------------------

def _plot_pw_demands(ax, beam_pair: FloorAnalysisPair,
                     w_trib_m: float, L_mm: float,
                     s: dict | None,
                     label_prefix: str = '',
                     title: str = '') -> None:
    """Draw SLS/ULS capacity curves with EC0 demand lines on *ax*.

    Visual convention (matches icc_app _draw_Fw_panel):
    - Blue solid  -- SLS capacity (mean strengths)
    - Red  solid  -- ULS capacity (design strengths)
    - Blue dashed -- L/250 limit  +  pale blue fill to the left
    - Blue horiz. -- p_Ed,qp demand (SLS)
    - Red  horiz. -- p_Ed,u  demand (ULS)
    - Pale red fill from 0 to p_Ed,u
    - Blue dot at SLS-curve intersection with p_Ed,qp
    - Red  dot at end of ULS curve (capacity reached)
    """
    p_sls, w_sls = beam_pair.sls.get_pw(w_trib_m)
    p_uls, w_uls = beam_pair.uls.get_pw(w_trib_m)

    sfx = f'  ({label_prefix})' if label_prefix else ''
    ax.plot(w_sls, p_sls, color=BLUE, lw=2.0,
            label=f'SLS capacity (mean){sfx}')
    ax.plot(w_uls, p_uls, color=RED,  lw=2.0,
            label=f'ULS capacity (design){sfx}')

    # L/250 serviceability limit
    w_lim = L_mm / 250.0
    ax.axvspan(0, w_lim, color=BLUE, alpha=0.08, zorder=0)
    ax.axvline(w_lim, color=BLUE, ls='--', lw=1.5,
               label=f'$L$/250 = {w_lim:.0f} mm')

    # Demand lines
    if s is not None:
        p_qp = s['p_Ed_qp']
        p_u  = s['p_Ed_u']

        ax.axhspan(0, p_u, color=RED, alpha=0.08, zorder=0)
        ax.axhline(p_qp, color=BLUE, lw=1.6,
                   label=fr"$p_{{Ed,qp}}$ = {p_qp:.2f} kN/m$^2$  (SLS)")
        ax.axhline(p_u,  color=RED,  lw=1.6,
                   label=fr"$p_{{Ed,u}}$  = {p_u:.2f} kN/m$^2$  (ULS)")

        # Blue dot at SLS curve intersection with p_Ed,qp
        sc = np.where(np.diff(np.sign(p_sls - p_qp)))[0]
        if len(sc):
            i = sc[0]
            dp = p_sls[i + 1] - p_sls[i]
            t  = (p_qp - p_sls[i]) / dp if dp != 0 else 0.0
            w_x = w_sls[i] + t * (w_sls[i + 1] - w_sls[i])
            ax.plot(w_x, p_qp, 'o', color=BLUE, ms=8, zorder=5)

        # Red dot at end of ULS curve
        ax.plot(w_uls[-1], p_uls[-1], 'o', color=RED, ms=8, zorder=5)

    ax.set_xlabel(r'$w_\mathrm{max}$ [mm]')
    ax.set_ylabel(r'$p$ [kN/m$^2$]')
    if title:
        ax.set_title(title, fontsize=9)
    ax.legend(fontsize=7, loc='lower right')
    ax.grid(True, linestyle='--', alpha=0.4)


# ---- FlatSlab ----------------------------------------------------------------

@dataclass
class FlatSlab(FloorSystemBase):
    """Simply supported SRC flat slab strip (steel reinforcement).

    Parameters (all lengths in mm, strengths in MPa)
    -------------------------------------------------
    h            : slab depth [mm]
    A_s          : tensile reinforcement per unit width [mm2/m = mm2 for b=1000]
    z_s          : distance from bottom fibre to steel centroid [mm]
    f_ck         : concrete cylinder strength [MPa]
    f_yk         : steel yield strength [MPa]
    L            : span [mm]
    b            : strip width [mm]  (default 1000 mm)

    Safety factors
    --------------
    rho_conc : concrete unit weight [kN/m3]
    gamma_c  : concrete partial safety factor
    gamma_s  : steel partial safety factor

    Resource parameters (used by volumes())
    ----------------------------------------
    r_transverse : transverse-to-main reinforcement ratio  (default 0.20)
    rho_steel    : steel density [kg/m3]
    e_conc       : concrete embodied CO2 [kgCO2/kg]
    e_steel      : steel embodied CO2 [kgCO2/kg]
    p_conc       : concrete unit cost [EUR/m3]
    p_reinf      : reinforcement unit cost [EUR/kg]
    """

    h:        float = field_mm(UnitLevel.CS_DIM)
    A_s:      float = field_mm(UnitLevel.REINF_AREA)
    z_s:      float = field_mm(UnitLevel.CS_DIM)
    f_ck:     float = 30.0
    f_yk:     float = 500.0
    L:        float = field_mm(UnitLevel.STRUCTURAL, 5000.0)
    b:        float = field_mm(UnitLevel.CS_DIM,     1000.0)
    # Safety
    rho_conc:     float = _RHO_CONCRETE_KN
    gamma_c:      float = 1.50
    gamma_s:      float = 1.15
    # Resources
    r_transverse: float = 0.20
    rho_steel:    float = _RHO_STEEL_KG
    e_conc:       float = _E_CONC_CO2
    e_steel:      float = _E_STEEL_CO2
    p_conc:       float = _P_CONC
    p_reinf:      float = _P_REINF

    # Built in __post_init__ -- excluded from constructor
    beam: FloorAnalysisPair = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.beam = FloorAnalysisPair.for_rc(
            b=self.b, h=self.h,
            f_ck=self.f_ck, A_s=self.A_s, z_s=self.z_s, f_yk=self.f_yk,
            L_mm=self.L, gamma_c=self.gamma_c, gamma_s=self.gamma_s,
        )

    # ---- Derived quantities --------------------------------------------------

    @property
    def g_k(self) -> float:
        """Structural self-weight [kN/m2]."""
        return self.rho_conc * self.h * 1e-3   # h [mm] -> [m]

    # ---- FloorSystemBase hook ------------------------------------------------

    def _beam_elements(self) -> list:
        return [(self.beam, self.b / 1000.0, 'Slab strip')]

    # ---- Plotting ------------------------------------------------------------

    def plot_pw(self, ax,
                load_model: LoadModel | None = None,
                *,
                title: str = '',
                label_prefix: str = '') -> None:
        """p-w capacity curves with optional demand lines."""
        s = load_model.surface_loads(self.g_k) if load_model else None
        if not title:
            title = (
                f'Flat slab  '
                f'$h$ = {self.h:.0f} mm,  '
                f'$A_s$ = {self.A_s:.0f} mm$^2$,  '
                f'$L$ = {self.L/1e3:.2f} m'
            )
        _plot_pw_demands(
            ax, self.beam,
            w_trib_m=self.b / 1000.0,
            L_mm=self.L,
            s=s,
            label_prefix=label_prefix,
            title=title,
        )

    def plot_floor_assessment(self, axes,
                              load_model: LoadModel | None = None) -> None:
        """Two-panel assessment: load breakdown + p-w curve.

        Parameters
        ----------
        axes : sequence of two matplotlib Axes  [ax_load, ax_pw]
               OR a single Axes (only the p-w panel is drawn)
        """
        if hasattr(axes, '__len__') and len(axes) >= 2:
            ax_load, ax_pw = axes[0], axes[1]
            if load_model:
                load_model.plot_breakdown(ax_load, self.g_k)
            else:
                ax_load.text(0.5, 0.5, 'no load model',
                             ha='center', va='center',
                             transform=ax_load.transAxes)
        else:
            ax_pw = axes if not hasattr(axes, '__len__') else axes[0]
        self.plot_pw(ax_pw, load_model)

    # ---- Resources -----------------------------------------------------------

    def volumes(self) -> dict:
        """Material volumes, masses, GWP and cost per strip and per m2.

        Reference area: A_ref = b x L  (e.g. 1 m x 5 m = 5 m2 for defaults)

        Returns
        -------
        dict with keys:
          A_ref              -- strip floor area [m2]
          V_c, V_c_per_m2   -- concrete [m3]
          V_s, V_s_per_m2   -- steel (main + transverse) [m3]
          m_c_kg, m_s_kg    -- masses [kg]
          gwp_conc, gwp_steel, gwp_total, gwp_per_m2  -- GWP [kgCO2eq]
          cost_conc, cost_steel, cost_total, cost_per_m2  -- cost [EUR]
        """
        b_m   = self.b * 1e-3
        L_m   = self.L * 1e-3
        A_ref = b_m * L_m

        # Volumes [m3 per strip]
        V_c      = self.h * 1e-3 * A_ref
        V_s_main = self.A_s * 1e-6 * L_m               # main steel per b_m=1 m
        V_s      = V_s_main * (1.0 + self.r_transverse) # incl. transverse

        # Masses [kg]
        rho_c_kg = self.rho_conc * 100.0   # kN/m3 -> kg/m3
        m_c = V_c * rho_c_kg
        m_s = V_s * self.rho_steel

        # GWP [kgCO2eq]
        gwp_conc  = m_c * self.e_conc
        gwp_steel = m_s * self.e_steel
        gwp_total = gwp_conc + gwp_steel

        # Cost [EUR]
        cost_conc  = V_c * self.p_conc
        cost_steel = m_s * self.p_reinf
        cost_total = cost_conc + cost_steel

        return dict(
            A_ref=A_ref,
            V_c=V_c,        V_c_per_m2=V_c / A_ref,
            V_s=V_s,        V_s_per_m2=V_s / A_ref,
            m_c_kg=m_c,     m_s_kg=m_s,
            gwp_conc=gwp_conc, gwp_steel=gwp_steel,
            gwp_total=gwp_total, gwp_per_m2=gwp_total / A_ref,
            cost_conc=cost_conc, cost_steel=cost_steel,
            cost_total=cost_total, cost_per_m2=cost_total / A_ref,
        )

    # ---- Summary -------------------------------------------------------------

    def report(self, load_model: LoadModel | None = None) -> None:
        """Print a formatted summary report."""
        print(f'FlatSlab:  h = {self.h:.0f} mm   b = {self.b:.0f} mm   '
              f'L = {self.L/1e3:.2f} m')
        print(f'  f_ck = {self.f_ck:.0f} MPa   f_yk = {self.f_yk:.0f} MPa')
        print(f'  A_s  = {self.A_s:.1f} mm2   z_s = {self.z_s:.0f} mm')
        print(f'  g_k  = {self.g_k:.2f} kN/m2  (self-weight)')
        p_R_sls = self.beam.sls.bda.F_R / (self.b / 1e3)
        p_R_uls = self.beam.uls.bda.F_R / (self.b / 1e3)
        print(f'  p_R  = {p_R_sls:.2f} kN/m2  (SLS)   '
              f'{p_R_uls:.2f} kN/m2  (ULS)')
        if load_model:
            s = load_model.surface_loads(self.g_k)
            print(f'  p_Ed,qp = {s["p_Ed_qp"]:.2f} kN/m2   '
                  f'p_Ed,u = {s["p_Ed_u"]:.2f} kN/m2')
            if p_R_sls > 0:
                print(f'  eta_SLS = {s["p_Ed_qp"]/p_R_sls:.2f}   '
                      f'eta_ULS = {s["p_Ed_u"]/p_R_uls:.2f}')
        v = self.volumes()
        m_s_per_m2 = v["m_s_kg"] / v["A_ref"]
        print(f'  V_c  = {v["V_c_per_m2"]:.3f} m3/m2   '
              f'm_s = {m_s_per_m2:.1f} kg/m2   '
              f'GWP = {v["gwp_per_m2"]:.1f} kgCO2/m2   '
              f'cost = {v["cost_per_m2"]:.1f} EUR/m2')


# ---- CRCFlatSlab -------------------------------------------------------------

@dataclass
class CRCFlatSlab(FloorSystemBase):
    """Simply supported CRC flat slab strip (CFRP reinforcement).

    Parameters (all lengths in mm, strengths in MPa)
    -------------------------------------------------
    h        : slab depth [mm]
    A_f      : CFRP reinforcement area [mm2/m = mm2 for b=1000]
    z_f      : distance from bottom fibre to CFRP centroid [mm]
    f_ck     : concrete cylinder strength [MPa]
    E_f      : CFRP elastic modulus [MPa]
    f_fk     : CFRP characteristic tensile strength [MPa]
    L        : span [mm]
    b        : strip width [mm]  (default 1000 mm)

    Safety factors
    --------------
    rho_conc : concrete unit weight [kN/m3]
    gamma_c  : concrete partial safety factor
    gamma_f  : CFRP partial safety factor

    Resource parameters
    -------------------
    r_transverse : transverse-to-main CFRP ratio  (default 0.20)
    rho_cfrp     : CFRP density [kg/m3]
    e_conc       : concrete embodied CO2 [kgCO2/kg]
    e_cfrp       : CFRP embodied CO2 [kgCO2/kg]
    p_conc       : concrete unit cost [EUR/m3]
    p_cfrp       : CFRP unit cost [EUR/kg]
    """

    h:    float = field_mm(UnitLevel.CS_DIM)
    A_f:  float = field_mm(UnitLevel.REINF_AREA)
    z_f:  float = field_mm(UnitLevel.CS_DIM)
    f_ck: float = 30.0
    E_f:  float = 210_000.0
    f_fk: float = 3000.0
    L:    float = field_mm(UnitLevel.STRUCTURAL, 5000.0)
    b:    float = field_mm(UnitLevel.CS_DIM,     1000.0)
    # Safety
    rho_conc:     float = _RHO_CONCRETE_KN
    gamma_c:      float = 1.50
    gamma_f:      float = 1.25
    # Resources
    r_transverse: float = 0.20
    rho_cfrp:     float = _RHO_CFRP_KG
    e_conc:       float = _E_CONC_CO2
    e_cfrp:       float = _E_CFRP_CO2
    p_conc:       float = _P_CONC
    p_cfrp:       float = _P_CFRP

    # Built in __post_init__ -- excluded from constructor
    beam: FloorAnalysisPair = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.beam = FloorAnalysisPair.for_crc(
            b=self.b, h=self.h,
            f_ck=self.f_ck, A_s=self.A_f, z_s=self.z_f,
            E_f=self.E_f, f_fk=self.f_fk,
            L_mm=self.L, gamma_c=self.gamma_c, gamma_f=self.gamma_f,
        )

    # ---- Derived quantities --------------------------------------------------

    @property
    def g_k(self) -> float:
        """Structural self-weight [kN/m2]."""
        return self.rho_conc * self.h * 1e-3

    # ---- FloorSystemBase hook ------------------------------------------------

    def _beam_elements(self) -> list:
        return [(self.beam, self.b / 1000.0, 'CRC slab strip')]

    # ---- Plotting ------------------------------------------------------------

    def plot_pw(self, ax,
                load_model: LoadModel | None = None,
                *,
                title: str = '',
                label_prefix: str = '') -> None:
        """p-w capacity curves with optional demand lines."""
        s = load_model.surface_loads(self.g_k) if load_model else None
        if not title:
            title = (
                f'CRC flat slab  '
                f'$h$ = {self.h:.0f} mm,  '
                f'$A_f$ = {self.A_f:.0f} mm$^2$,  '
                f'$L$ = {self.L/1e3:.2f} m'
            )
        _plot_pw_demands(
            ax, self.beam,
            w_trib_m=self.b / 1000.0,
            L_mm=self.L,
            s=s,
            label_prefix=label_prefix,
            title=title,
        )

    def plot_floor_assessment(self, axes,
                              load_model: LoadModel | None = None) -> None:
        """Two-panel assessment: load breakdown + p-w curve."""
        if hasattr(axes, '__len__') and len(axes) >= 2:
            ax_load, ax_pw = axes[0], axes[1]
            if load_model:
                load_model.plot_breakdown(ax_load, self.g_k)
            else:
                ax_load.text(0.5, 0.5, 'no load model',
                             ha='center', va='center',
                             transform=ax_load.transAxes)
        else:
            ax_pw = axes if not hasattr(axes, '__len__') else axes[0]
        self.plot_pw(ax_pw, load_model)

    # ---- Resources -----------------------------------------------------------

    def volumes(self) -> dict:
        """Material volumes, masses, GWP and cost per strip and per m2.

        Reference area: A_ref = b x L

        Returns
        -------
        dict with keys:
          A_ref              -- strip floor area [m2]
          V_c, V_c_per_m2   -- concrete [m3]
          V_f, V_f_per_m2   -- CFRP (main + transverse) [m3]
          m_c_kg, m_f_kg    -- masses [kg]
          gwp_conc, gwp_cfrp, gwp_total, gwp_per_m2  -- GWP [kgCO2eq]
          cost_conc, cost_cfrp, cost_total, cost_per_m2  -- cost [EUR]
        """
        b_m   = self.b * 1e-3
        L_m   = self.L * 1e-3
        A_ref = b_m * L_m

        V_c      = self.h * 1e-3 * A_ref
        V_f_main = self.A_f * 1e-6 * L_m
        V_f      = V_f_main * (1.0 + self.r_transverse)

        rho_c_kg = self.rho_conc * 100.0   # kN/m3 -> kg/m3
        m_c = V_c * rho_c_kg
        m_f = V_f * self.rho_cfrp

        gwp_conc = m_c * self.e_conc
        gwp_cfrp = m_f * self.e_cfrp
        gwp_total = gwp_conc + gwp_cfrp

        cost_conc  = V_c * self.p_conc
        cost_cfrp  = m_f * self.p_cfrp
        cost_total = cost_conc + cost_cfrp

        return dict(
            A_ref=A_ref,
            V_c=V_c,        V_c_per_m2=V_c / A_ref,
            V_f=V_f,        V_f_per_m2=V_f / A_ref,
            m_c_kg=m_c,     m_f_kg=m_f,
            gwp_conc=gwp_conc, gwp_cfrp=gwp_cfrp,
            gwp_total=gwp_total, gwp_per_m2=gwp_total / A_ref,
            cost_conc=cost_conc, cost_cfrp=cost_cfrp,
            cost_total=cost_total, cost_per_m2=cost_total / A_ref,
        )

    # ---- Summary -------------------------------------------------------------

    def report(self, load_model: LoadModel | None = None) -> None:
        """Print a formatted summary report."""
        print(f'CRCFlatSlab:  h = {self.h:.0f} mm   b = {self.b:.0f} mm   '
              f'L = {self.L/1e3:.2f} m')
        print(f'  f_ck = {self.f_ck:.0f} MPa')
        print(f'  A_f  = {self.A_f:.1f} mm2   z_f = {self.z_f:.0f} mm   '
              f'E_f = {self.E_f:.0f} MPa   f_fk = {self.f_fk:.0f} MPa')
        print(f'  g_k  = {self.g_k:.2f} kN/m2  (self-weight)')
        p_R_sls = self.beam.sls.bda.F_R / (self.b / 1e3)
        p_R_uls = self.beam.uls.bda.F_R / (self.b / 1e3)
        print(f'  p_R  = {p_R_sls:.2f} kN/m2  (SLS)   '
              f'{p_R_uls:.2f} kN/m2  (ULS)')
        if load_model:
            s = load_model.surface_loads(self.g_k)
            print(f'  p_Ed,qp = {s["p_Ed_qp"]:.2f} kN/m2   '
                  f'p_Ed,u = {s["p_Ed_u"]:.2f} kN/m2')
            if p_R_sls > 0:
                print(f'  eta_SLS = {s["p_Ed_qp"]/p_R_sls:.2f}   '
                      f'eta_ULS = {s["p_Ed_u"]/p_R_uls:.2f}')
        v = self.volumes()
        m_f_per_m2 = v["m_f_kg"] / v["A_ref"]
        print(f'  V_c  = {v["V_c_per_m2"]:.3f} m3/m2   '
              f'm_f = {m_f_per_m2:.1f} kg/m2   '
              f'GWP = {v["gwp_per_m2"]:.1f} kgCO2/m2   '
              f'cost = {v["cost_per_m2"]:.1f} EUR/m2')
