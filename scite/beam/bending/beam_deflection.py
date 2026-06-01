"""
BeamDeflectionAnalysis
======================

Pydantic BMCSModel for nonlinear beam deflection by integration of the M-κ curve.

Computation chain
-----------------
  CrossSection  →  MKappaAnalysis  (M-κ relationship)
                        ↓
              Analytical M(x, F)    (3PB or distributed load)
                        ↓
              κ(x, F) = interp M-κ   (curvature profile)
                        ↓
              φ(x) = ∫ κ dx   (rotation, with symmetry BC)
                        ↓
              w(x) = ∫ φ dx   (deflection, with support BC)
                        ↓
              w_max(F)  →  F-w curve

Supported systems
-----------------
  '3pb'   — simply supported beam, point load F [N] at midspan
             M(x) = F/2 · min(x, L−x)
             F_R  = 4 M_R / L

  'dist'  — simply supported beam, uniform distributed load q [N/mm]
             M(x) = q/2 · x · (L − x)
             q_R  = 8 M_R / L²  (max q)

Architecture note
-----------------
This class is the beam-level equivalent of MKappaAnalysis: a self-contained
Pydantic BMCSModel that can be used directly in Jupyter notebooks without any
UI framework.  The CNode wrapper (NonlinearBeamModel in icc_app) delegates its
actual computation here and provides only the UI adaptation layer.
"""

from __future__ import annotations

from functools import cached_property
from typing import Literal, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from pydantic import Field
from scipy.integrate import cumulative_trapezoid as cumtrapz

from scite.core import BMCSModel, ui_field
from scite.cs_design.cross_section import CrossSection
from scite.mkappa.mkappa import MKappaAnalysis


class BeamDeflectionAnalysis(BMCSModel):
    """
    Nonlinear load-deflection analysis for a simply supported beam.

    Uses the moment-curvature (M-κ) relationship of the supplied cross-section
    to compute nonlinear deflection profiles and the load-deflection (F-w) curve.

    Parameters
    ----------
    cs : CrossSection
        Cross-section model (Pydantic BMCSModel).
    L : float
        Span length [mm].
    load_type : '3pb' | 'dist'
        Structural system.  '3pb' = point load at midspan (3-point bending);
        'dist' = uniform distributed load.
    n_x : int
        Number of spatial integration points along the span.
    n_kappa : int
        Number of curvature steps for the M-κ solver.
    n_load_steps : int
        Number of load increments for the F-w curve.
    N_Ed : float
        Axial force [kN] passed to the M-κ solver (default 0).

    Usage
    -----
    >>> from scite.beam.bending.beam_deflection import BeamDeflectionAnalysis
    >>> bda = BeamDeflectionAnalysis(cs=cs, L=6000.0, load_type='3pb')
    >>> F_arr, w_arr = bda.get_Fw()
    >>> bda.plot_summary("My RC beam")
    """

    cs: CrossSection
    L: float = ui_field(6000.0, label="L", unit="mm", range=(500, 20_000))
    load_type: Literal['3pb', 'dist'] = ui_field(
        '3pb', label="Load type", description="'3pb'=point at midspan, 'dist'=uniform"
    )
    n_x: int = ui_field(200, label="n_x", unit="-", range=(20, 500))
    n_kappa: int = ui_field(150, label="n_κ", unit="-", range=(30, 500))
    n_load_steps: int = ui_field(41, label="n steps", unit="-", range=(11, 101))
    N_Ed: float = ui_field(0.0, label="N_Ed", unit="kN")

    # Experimental F-w data for overlay (list of (w_arr, F_arr) pairs)
    exp_data: list = Field(default_factory=list)

    # ── M-κ relationship (cached) ─────────────────────────────────────────────

    @cached_property
    def mk(self) -> MKappaAnalysis:
        """Solved MKappaAnalysis for the cross-section."""
        mk = MKappaAnalysis(cs=self.cs, n_kappa=self.n_kappa, N_Ed=self.N_Ed)
        mk.solve()
        return mk

    @cached_property
    def M_R(self) -> float:
        """Peak moment capacity [kN·m] from the M-κ curve."""
        if self.mk.M_values is None or len(self.mk.M_values) == 0:
            raise RuntimeError("M-κ solver returned no results.")
        return float(np.max(self.mk.M_values))

    @cached_property
    def F_R(self) -> float:
        """
        Force at ultimate limit state [N] (or [N/mm] for 'dist').

        3pb : F_R [N]     = 4 · M_R [kN·m] · 1000 / L [mm]
        dist: q_R [N/mm]  = 8 · M_R [kN·m] · 1e6  / L² [mm²]
        """
        M_R_Nmm = self.M_R * 1e6  # kN·m → N·mm
        if self.load_type == '3pb':
            return 4.0 * M_R_Nmm / self.L
        else:  # 'dist'
            return 8.0 * M_R_Nmm / self.L ** 2

    @cached_property
    def x(self) -> np.ndarray:
        """Spatial coordinate array [mm], from 0 to L."""
        return np.linspace(0.0, self.L, self.n_x)

    # ── Analytical moment distribution ───────────────────────────────────────

    def get_M_x(
        self,
        F: float,
        M_end_left: float = 0.0,
        M_end_right: float = 0.0,
    ) -> np.ndarray:
        """
        Moment distribution M(x) [N·mm] at load F.

        Optional end moments allow the SSB to carry imposed end moments (e.g.
        from continuous-beam compatibility analysis).  Both default to 0, so
        existing call sites are unaffected.

        Parameters
        ----------
        F : float
            Applied force: [N] for '3pb', [N/mm] for 'dist'.
        M_end_left : float
            Moment [N·mm] at x = 0 (positive = sagging convention).
        M_end_right : float
            Moment [N·mm] at x = L (positive = sagging convention).
        """
        x = self.x
        L = self.L
        if self.load_type == '3pb':
            M_load = F * 0.5 * np.minimum(x, L - x)
        else:  # 'dist'
            M_load = F * 0.5 * x * (L - x)
        # Linear superposition of end moments (SSB: zero reactions at supports)
        M_linear = M_end_left * (1.0 - x / L) + M_end_right * (x / L)
        return M_load + M_linear

    # ── κ(x) from M-κ interpolation ──────────────────────────────────────────

    def get_kappa_x_from_M(self, M_x: np.ndarray) -> np.ndarray:
        """
        Curvature profile κ(x) [1/mm] for a given moment array M_x [N·mm].

        Inverts the ascending branch of the M-κ curve.  Moments beyond M_R
        are clipped.  Negative (hogging) moments are mapped via the symmetric-
        section approximation: κ = −κ(|M|).
        """
        mk = self.mk
        idx_peak = int(np.argmax(mk.M_values))
        M_ref     = mk.M_values[:idx_peak + 1] * 1e6   # kN·m → N·mm
        kappa_ref = mk.kappa_values[:idx_peak + 1]       # 1/mm
        M_abs  = np.abs(M_x)
        M_clip = np.clip(M_abs, 0.0, float(np.max(M_ref)))
        kappa  = np.interp(M_clip, M_ref, kappa_ref)
        return np.where(M_x >= 0.0, kappa, -kappa)

    def get_kappa_x(self, F: float) -> np.ndarray:
        """
        Curvature profile κ(x) [1/mm] at load F by inverting the M-κ curve.

        Delegates to get_kappa_x_from_M after computing the moment distribution.
        """
        return self.get_kappa_x_from_M(self.get_M_x(F))

    # ── Integration: κ → φ → w ───────────────────────────────────────────────

    def get_phi_x(self, F: float) -> np.ndarray:
        """
        Rotation profile φ(x) [rad] at load F.

        BC: w(0) = w(L) = 0 (simply supported beam, no assumption of symmetry).
        The integration constant C1 is chosen so that ∫₀ᴸ φ dx = 0, which is
        equivalent to the zero-displacement condition at both supports.  For
        symmetric loading this gives the same result as φ(L/2) = 0.
        """
        kappa_x = self.get_kappa_x(F)
        x = self.x
        phi_int = cumtrapz(kappa_x, x, initial=0.0)
        # SSB displacement BC: w(L) = -∫₀ᴸ φ dx = 0  ⟹  C1 = -⟨φ_int⟩
        C1 = -np.trapezoid(phi_int, x) / (x[-1] - x[0])
        return phi_int + C1

    def get_w_x(self, F: float) -> np.ndarray:
        """
        Deflection profile w(x) [mm] at load F (downward positive).

        BC: w(0) = 0 (pinned support).
        """
        phi_x = self.get_phi_x(F)
        x = self.x
        w_int = cumtrapz(phi_x, x, initial=0.0)
        # Enforce w(0) = 0
        return -(w_int - w_int[0])

    # ── Load-deflection curve ─────────────────────────────────────────────────

    def get_Fw(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Nonlinear load-deflection curve (F, w_max).

        Returns
        -------
        F_arr : np.ndarray
            Applied force array [N] or [N/mm] for 'dist'.
        w_arr : np.ndarray
            Maximum deflection array [mm] (midspan for symmetric loading).
        """
        F_R = self.F_R
        # Denser spacing in the lower 20 % to capture cracking accurately
        n = self.n_load_steps
        n1 = max(2, int(0.4 * n))
        n2 = n - n1
        F_arr = np.concatenate([
            np.linspace(0.0, 0.2 * F_R, n1, endpoint=False),
            np.linspace(0.2 * F_R, F_R, n2),
        ])
        w_arr = np.array([
            float(np.max(self.get_w_x(F))) if F > 0.0 else 0.0
            for F in F_arr
        ])
        return F_arr, w_arr

    # ── Section geometry helpers ──────────────────────────────────────────────

    @cached_property
    def E_cm(self) -> float:
        """
        EC2 mean secant modulus of concrete [MPa].

        E_cm = 22·(f_cm/10)^0.3  [GPa]  (EC2 Table 3.1)
        """
        f_cm = self.cs.concrete.f_cm
        return 22_000.0 * (f_cm / 10.0) ** 0.3

    @cached_property
    def I_g(self) -> float:
        """
        Gross (uncracked) moment of inertia of the cross-section [mm⁴].

        Computed by integrating b(y)·y² over the section height,
        where y is measured from the centroid of the gross section.
        """
        n_pts = max(self.n_x, 200)
        h     = self.cs.h_total
        y_arr = np.linspace(0.0, h, n_pts)
        b_arr = np.array([float(self.cs.shape.get_width_at_y(np.array([y]))[0])
                          for y in y_arr], dtype=float)
        A_g   = float(np.trapezoid(b_arr, y_arr))
        y_c   = float(np.trapezoid(b_arr * y_arr, y_arr)) / A_g
        I_g   = float(np.trapezoid(b_arr * (y_arr - y_c) ** 2, y_arr))
        return I_g

    # ── Plotting ──────────────────────────────────────────────────────────────
    #
    # Structural engineering sign convention:
    #   - Deflection w and curvature κ are POSITIVE DOWNWARD.
    #   - Profile plots: y-axis INVERTED so the beam "sags" below the baseline.
    #   - F-w plots: w on x-axis (rightward), F on y-axis (upward) — standard.

    @property
    def _F_scale(self) -> float:
        """Convert internal force units to display units."""
        return 1e-3 if self.load_type == '3pb' else 1.0   # N→kN  or  N/mm=kN/m

    @property
    def _F_unit(self) -> str:
        return 'kN' if self.load_type == '3pb' else 'kN/m'

    @property
    def _F_sym(self) -> str:
        return 'F' if self.load_type == '3pb' else 'q'

    @property
    def _F_label(self) -> str:
        return f'${self._F_sym}$ [{self._F_unit}]'

    # ── F-w load-deflection plot ──────────────────────────────────────────────

    def plot_Fw(
        self,
        ax: Optional[plt.Axes] = None,
        color: str = '#1f77b4',
        linewidth: float = 2.0,
        label: str = '',
        show_sls: bool = True,
    ) -> plt.Axes:
        """
        Plot the nonlinear load-deflection curve w_max – F.

        Convention: w on x-axis (rightward), F on y-axis (upward).
        The SLS limit w = L/250 is shown as a dashed red vertical line.
        Overlays any experimental data added via add_exp_Fw().
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(7, 5))
        F_arr, w_arr = self.get_Fw()
        lbl = label or f'{self._F_sym}_R={self._F_scale * self.F_R:.1f} {self._F_unit}'
        ax.plot(w_arr, self._F_scale * F_arr, color=color, linewidth=linewidth, label=lbl)
        if show_sls:
            w_sls = self.L / 250.0
            ax.axvline(w_sls, color='red', linestyle='--', linewidth=1.2, alpha=0.8,
                       label=f'$w_{{SLS}}$ = L/250 = {w_sls:.0f} mm')
        if self.exp_data:
            self.plot_exp_Fw(ax)
        ax.set_xlabel(r'$w_\mathrm{max}$ [mm]', fontsize=11)
        ax.set_ylabel(self._F_label, fontsize=11)
        ax.set_title('Load–deflection', fontsize=11)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(fontsize=9)
        return ax

    def add_exp_Fw(self, w_arr: np.ndarray, F_arr: np.ndarray) -> None:
        """Add an experimental F-w dataset for overlay in plot_Fw().

        Parameters
        ----------
        w_arr : deflection values [mm]
        F_arr : force values in the same units as the model output
                (kN for '3pb', kN/m for 'dist')
        """
        self.exp_data.append((list(w_arr), list(F_arr)))

    def plot_exp_Fw(
        self,
        ax: plt.Axes,
        color: str = 'gray',
        label_prefix: str = 'exp',
    ) -> None:
        """Overlay all experimental datasets on *ax*.

        Datasets were added via add_exp_Fw().  Each is shown as a dotted
        line with small circle markers.
        """
        for i, (w, F) in enumerate(self.exp_data):
            lbl = (f'{label_prefix} {i + 1}' if len(self.exp_data) > 1
                   else label_prefix)
            ax.plot(w, F, color=color, lw=1.5, linestyle=':', marker='o',
                    ms=3, label=lbl)



    def plot_Fw_vs_elastic(
        self,
        ax: Optional[plt.Axes] = None,
        show_sls: bool = True,
        show_cracked: bool = True,
    ) -> plt.Axes:
        """
        Plot the nonlinear F-w curve together with linear-elastic references.

        Two elastic reference curves are added:
        - **Gross section** I_g with E_cm (upper bound stiffness, uncracked).
        - **Cracked section** I_cr (simplified transformed section, n = E_s / E_cm)
          when the first reinforcement layer is steel and show_cracked=True.

        E_cm and I_g are derived automatically from the concrete model and geometry.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(8, 5))

        # nonlinear F-w (model)
        self.plot_Fw(ax=ax, show_sls=show_sls, label='Nonlinear (M-κ)', color='#1f77b4')

        F_arr, _ = self.get_Fw()
        E_c  = self.E_cm
        I_g  = self.I_g
        L    = self.L

        if self.load_type == '3pb':
            w_el_g = F_arr * L ** 3 / (48.0 * E_c * I_g)
        else:
            w_el_g = 5.0 * F_arr * L ** 4 / (384.0 * E_c * I_g)
        ax.plot(w_el_g, self._F_scale * F_arr, color='gray', linewidth=1.5,
                linestyle='--', label=r'Elastic (gross $I_g$)')

        if show_cracked:
            layers = self.cs.reinforcement.layers
            if layers:
                mat  = layers[0].material
                E_s  = getattr(mat, 'E_s', getattr(mat, 'E', None))
                A_s  = layers[0].A_s
                z_s  = layers[0].z          # distance from bottom
                d    = self.cs.h_total - z_s  # effective depth from top
                b    = float(self.cs.shape.get_width_at_y(
                               np.array([self.cs.h_total]))[0])  # top width
                if E_s is not None and b > 0 and d > 0:
                    n     = E_s / E_c
                    # NA from top: b·x²/2 = n·A_s·(d−x)
                    A_q   = 0.5 * b
                    B_q   = n * A_s
                    C_q   = -n * A_s * d
                    x_na  = (-B_q + np.sqrt(B_q**2 - 4*A_q*C_q)) / (2*A_q)
                    I_cr  = b * x_na**3 / 3.0 + n * A_s * (d - x_na)**2
                    if self.load_type == '3pb':
                        w_el_cr = F_arr * L**3 / (48.0 * E_c * I_cr)
                    else:
                        w_el_cr = 5.0 * F_arr * L**4 / (384.0 * E_c * I_cr)
                    ax.plot(w_el_cr, self._F_scale * F_arr, color='black',
                            linewidth=1.5, linestyle=':', label=r'Elastic (cracked $I_{cr}$)')

        ax.legend(fontsize=9)
        return ax

    # ── Deformation profile plots ─────────────────────────────────────────────

    def plot_profile(
        self,
        F: float,
        ax_w: plt.Axes,
        ax_k: plt.Axes,
        color: str = '#1f77b4',
        label: str = '',
        elastic_E_c: Optional[float] = None,
    ) -> None:
        """
        Add one deflection + curvature profile at load F onto existing axes.

        Caller must call ``ax_w.invert_yaxis()`` and ``ax_k.invert_yaxis()``
        once after all curves are added (done automatically by plot_profiles).
        """
        x    = self.x
        w_x  = self.get_w_x(F)
        k_x  = self.get_kappa_x(F)
        lbl  = label or f'{self._F_sym}={self._F_scale*F:.1f} {self._F_unit}'

        ax_w.plot(x, w_x,       color=color, lw=1.8, label=lbl)
        ax_k.plot(x, k_x * 1e3, color=color, lw=1.8, linestyle='--')

        if elastic_E_c is not None:
            I_g = self.I_g
            L   = self.L
            if self.load_type == '3pb':
                w_el = np.where(
                    x <= L / 2,
                    F * x * (3*L**2 - 4*x**2) / (48*elastic_E_c*I_g),
                    F * (L-x) * (3*L**2 - 4*(L-x)**2) / (48*elastic_E_c*I_g),
                )
                k_el = F * np.minimum(x, L - x) / (2 * elastic_E_c * I_g)
            else:
                w_el = F * x * (L**3 - 2*L*x**2 + x**3) / (24*elastic_E_c*I_g*L)
                k_el = F * x * (L - x) / (2 * elastic_E_c * I_g)
            ax_w.plot(x, w_el,       color=color, lw=1.2, linestyle=':', label='elastic ref.')
            ax_k.plot(x, k_el * 1e3, color=color, lw=1.2, linestyle=':')

    def plot_profiles(
        self,
        ax_w: Optional[plt.Axes] = None,
        ax_k: Optional[plt.Axes] = None,
        fractions: Tuple[float, ...] = (0.05, 0.30, 0.60, 1.00),
        colors: Optional[list] = None,
        show_elastic_ref: bool = True,
        show_sls: bool = True,
    ) -> Tuple[plt.Axes, plt.Axes]:
        """
        Plot deflection w(x) and curvature κ(x) at several load levels.

        Structural convention: y-axis is inverted so the beam sags downward,
        matching standard design drawings (positive w and κ point downward).

        Parameters
        ----------
        fractions : F/F_R load fractions to display
        show_elastic_ref : overlay dotted elastic reference at the first fraction
        show_sls : mark the L/250 serviceability deflection limit
        """
        if ax_w is None or ax_k is None:
            fig, (ax_w, ax_k) = plt.subplots(1, 2, figsize=(14, 4))

        if colors is None:
            import matplotlib.cm as cm
            colors = [cm.viridis(v) for v in np.linspace(0.1, 0.9, len(fractions))]

        E_el = self.E_cm if show_elastic_ref else None
        for i, (frac, color) in enumerate(zip(fractions, colors)):
            F   = frac * self.F_R
            lbl = f'{int(round(frac*100))} % {self._F_sym}_R'
            self.plot_profile(F, ax_w, ax_k, color=color, label=lbl,
                              elastic_E_c=E_el if i == 0 else None)

        if show_sls:
            w_sls = self.L / 250.0
            ax_w.axhline(w_sls, color='red', linestyle='--', lw=1.2,
                         label=f'$w_{{SLS}}$ = L/250 = {w_sls:.0f} mm')

        # Structural convention: downward is positive
        ax_w.invert_yaxis()
        ax_k.invert_yaxis()

        ax_w.axhline(0, color='black', lw=0.8)   # beam reference axis
        ax_w.set_xlabel(r'$x$ [mm]', fontsize=11)
        ax_w.set_ylabel(r'$w$ [mm]  $\downarrow$', fontsize=11)
        ax_w.set_title('Deflection profiles', fontsize=10)
        ax_w.legend(fontsize=8); ax_w.grid(True, alpha=0.3)

        ax_k.set_xlabel(r'$x$ [mm]', fontsize=11)
        ax_k.set_ylabel(r'$\kappa$ [‰/mm]  $\downarrow$', fontsize=11)
        ax_k.set_title('Curvature profiles (dashed, same colors)', fontsize=10)
        ax_k.grid(True, alpha=0.3)

        return ax_w, ax_k

    # ── Combined summary ──────────────────────────────────────────────────────

    def plot_summary(
        self,
        title: str = '',
        fractions: Tuple[float, ...] = (0.05, 0.30, 0.60, 1.00),
        figsize: Tuple[float, float] = (18, 5),
    ) -> None:
        """
        4-panel summary: M-κ | F-w vs elastic | deflection profiles | κ profiles.
        """
        import matplotlib.gridspec as gridspec

        fig = plt.figure(figsize=figsize, layout='constrained')
        fig.suptitle(
            title or (
                f'Beam deflection — L={self.L/1000:.1f} m, {self.load_type.upper()}, '
                f'M_R={self.M_R:.1f} kN·m'
            ),
            fontsize=12, fontweight='bold',
        )
        gs = gridspec.GridSpec(1, 4, figure=fig)
        ax_mk = fig.add_subplot(gs[0, 0])
        ax_Fw = fig.add_subplot(gs[0, 1])
        ax_w  = fig.add_subplot(gs[0, 2])
        ax_k  = fig.add_subplot(gs[0, 3])

        # M-κ panel
        mk = self.mk
        if mk.M_values is not None and len(mk.M_values) > 0:
            idx_pk = int(np.argmax(mk.M_values))
            ax_mk.plot(mk.kappa_values[:idx_pk + 1] * 1e3,
                       mk.M_values[:idx_pk + 1],
                       color='#2ca02c', linewidth=2.0)
            mk._add_failure_marker(ax_mk, color='#2ca02c')
        ax_mk.set_xlabel(r'$\kappa$ [1/m]', fontsize=10)
        ax_mk.set_ylabel(r'$M$ [kN·m]', fontsize=10)
        ax_mk.set_title('M–κ', fontsize=10)
        ax_mk.grid(True, alpha=0.3, linestyle='--')

        # F-w panel (with elastic references)
        self.plot_Fw_vs_elastic(ax=ax_Fw)

        # Deformation profile panels
        self.plot_profiles(ax_w=ax_w, ax_k=ax_k, fractions=fractions)

        try:
            from IPython.display import display as ipy_display
            ipy_display(fig)
            plt.close(fig)
        except ImportError:
            return fig


# ── Utility helpers ───────────────────────────────────────────────────────────

def _align_yaxis_to_zero(ax1: plt.Axes, ax2: plt.Axes) -> None:
    """Align the zero lines of two twinx axes."""
    lo1, hi1 = ax1.get_ylim()
    lo2, hi2 = ax2.get_ylim()
    if (hi1 - lo1) == 0 or (hi2 - lo2) == 0:
        return
    f1 = -lo1 / (hi1 - lo1)
    f2 = -lo2 / (hi2 - lo2)
    if f1 < f2:
        ax1.set_ylim(lo1, hi1 + (hi1 - lo1) * (f2 - f1) / max(1 - f2, 1e-9))
    else:
        ax2.set_ylim(lo2, hi2 + (hi2 - lo2) * (f1 - f2) / max(1 - f1, 1e-9))


def _merge_twin_legends(ax1: plt.Axes, ax2: plt.Axes) -> None:
    """Combine handles from two twinx axes into a single legend on ax1."""
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=8)
    leg2 = ax2.get_legend()
    if leg2:
        leg2.remove()
