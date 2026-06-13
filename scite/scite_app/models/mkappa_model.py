"""
scite_app/models/mkappa_model.py — M-κ analysis CNode with predefined cross-section.

Interactive moment-curvature analysis for a predefined rectangular RC cross-section:
  • Dimensions: 200 mm (width) × 500 mm (height)
  • Concrete: C30/35 (f_ck = 30 MPa, α_cc = 0.85, γ_c = 1.5)
  • Reinforcement: 4×D16 bottom layer (A_s = 804.2 mm²)
  • z = 50 mm from top (450 mm from bottom)

User can vary:
  • N_Ed (axial force)
  • κ step (to explore state at different curvature levels)
"""
from __future__ import annotations

import numpy as np
from cframe import CField, CNode


class MKappaInteractive(CNode):
    """
    Moment-curvature (M-κ) analysis for a predefined rectangular
    RC cross-section (EC2 parabola-rectangle concrete).
    
    Wraps scite.mkappa.MKappaAnalysis with fixed geometry and materials.
    """
    name = "M-κ Analysis (Predefined Section)"
    
    # User-controllable process fields
    N_Ed      = CField(
        0.0, 
        label="N_Ed", 
        unit="kN", 
        latex=r"N_{Ed}",
        kind="number", 
        min=-2000, 
        max=2000,
    )
    
    kappa_idx = CField(
        50, 
        label="κ step", 
        unit="-", 
        latex=r"\kappa_\mathrm{idx}",
        kind="slider", 
        min=0, 
        max=99, 
        step=1,
    )

    # ── Layout ──────────────────────────────────────────────────────────────

    def subplots(self, fig):
        """Create 3-column layout for M-κ curve, strain, and stress."""
        fig.set_size_inches(12, 4)
        return fig.subplots(1, 3)

    # ── Computation + drawing ────────────────────────────────────────────────

    def update_plot(self, axes) -> None:
        """
        Build predefined cross-section, run M-κ analysis, and plot results.
        """
        from scite.cs_design import (CrossSection, RectangularShape,
                                     ReinforcementLayer, ReinforcementLayout)
        from scite.matmod import EC2ParabolaRectangle, SteelReinforcement
        from scite.mkappa import MKappaAnalysis

        ax_mk, ax_strain, ax_stress = axes

        # ── Predefined cross-section parameters ──────────────────────────────
        # Geometry
        b = 200.0   # mm (width)
        h = 500.0   # mm (height)
        
        # Concrete C30/35
        f_ck = 30.0      # MPa
        alpha_cc = 0.85  # EC2 coefficient for long-term effects
        gamma_c = 1.5    # Safety factor for concrete
        
        # Steel reinforcement B500B
        f_yk = 500.0     # MPa (characteristic yield strength)
        gamma_s = 1.15   # Safety factor for steel
        
        # 4×D16 bars at bottom
        d_bar = 16.0     # mm (bar diameter)
        A_s_bot = 4 * np.pi * (d_bar / 2.0) ** 2  # 804.2 mm²
        z_bot = 50.0     # mm from top (or h - 50 = 450 mm from bottom)

        # ── Build cross-section ──────────────────────────────────────────────
        steel_mat = SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s)
        
        layers = [
            ReinforcementLayer(
                z=z_bot, 
                A_s=A_s_bot,
                material=steel_mat,
            ),
        ]

        cs = CrossSection(
            shape=RectangularShape(b=b, h=h),
            concrete=EC2ParabolaRectangle(
                f_ck=f_ck,
                alpha_cc=alpha_cc, 
                gamma_c=gamma_c,
            ),
            reinforcement=ReinforcementLayout(layers=layers),
        )

        # ── Run M-κ analysis ─────────────────────────────────────────────────
        mk = MKappaAnalysis(cs=cs, N_Ed=float(self.N_Ed), n_kappa=100)
        mk.solve()

        # ── Plot M-κ curve ───────────────────────────────────────────────────
        mk.plot_mk(ax_mk)

        # Marker for selected κ
        idx = min(int(self.kappa_idx), len(mk.kappa_values) - 1)
        kappa     = mk.kappa_values[idx]          # [1/mm]
        kappa_x   = kappa * 1000.0                 # [1/m] — same as plot_mk x axis
        M_at_idx  = mk.M_values[idx]
        
        ax_mk.axvline(kappa_x, color="red", ls="--", lw=1.5, alpha=0.8)
        ax_mk.plot(kappa_x, M_at_idx, "ro", ms=6,
                   label=f"κ={kappa_x:.3f} 1/m\nM={M_at_idx:.1f} kNm")
        ax_mk.legend(fontsize=8, loc="best")
        ax_mk.set_title("M-κ Diagram")

        # ── Plot strain / stress state ───────────────────────────────────────
        mk.plot_state_at_kappa(
            kappa, 
            ax_strain=ax_strain, 
            ax_stress=ax_stress,
            show_resultants=True,
        )
        
        ax_strain.set_title(f"Strain at κ={kappa_x:.3f} 1/m")
        ax_stress.set_title(f"Stress at κ={kappa_x:.3f} 1/m")

        # ── Add cross-section info to plot ───────────────────────────────────
        info_text = (
            f"Cross-section: {b:.0f}×{h:.0f} mm\n"
            f"Concrete: C30/35 (f_ck={f_ck:.0f} MPa)\n"
            f"Steel: 4×D{d_bar:.0f} @ z={z_bot:.0f} mm\n"
            f"A_s = {A_s_bot:.1f} mm²"
        )
        ax_mk.text(
            0.02, 0.98, info_text,
            transform=ax_mk.transAxes,
            fontsize=8,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3),
        )
