"""
scite.beam.continuous.continuous_beam
======================================

ContinuousBeamAnalysis — two-span nonlinear continuous beam solved by
rotation compatibility at the interior support.

Algorithm
---------
Each span is treated as an independent simply supported beam (SSB).  The
unknown hogging moment M_hog ≥ 0 at the interior support is determined by
requiring equal end-rotations from the two spans:

    φ_a(L_a; M_hog) = φ_b(0; M_hog)   →   residuum R = φ_L − φ_R = 0

End-rotations are computed via numerical integration of the M-κ curve with the
SSB displacement BC w(0) = w(L) = 0.  The brentq solver finds the root.

Sign convention (sagging positive)
-----------------------------------
- Positive M → sagging (tension at bottom).
- M_hog ≥ 0 is the *magnitude* of the interior support moment; it enters
  moment expressions as −M_hog.
- φ = −dw/dx with w downward positive → φ > 0 means slope points upward.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import cumulative_trapezoid as cumtrapz
from scipy.optimize import brentq

from scite.beam.bending.beam_deflection import BeamDeflectionAnalysis

# ── SSB rotation helper ───────────────────────────────────────────────────────

def _phi_ssb(kappa_x: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Rotation profile φ(x) for a SSB using w(0) = w(L) = 0 BC.

    The integration constant C1 is derived from ∫₀ᴸ φ dx = 0, which is
    equivalent to zero displacement at both supports.
    """
    phi_int = cumtrapz(kappa_x, x, initial=0.0)
    C1 = -np.trapezoid(phi_int, x) / (x[-1] - x[0])
    return phi_int + C1


# ── ContinuousBeamAnalysis ────────────────────────────────────────────────────

@dataclass
class ContinuousBeamAnalysis:
    """Two-span nonlinear continuous beam via rotation-compatibility.

    Parameters
    ----------
    span_left : BeamDeflectionAnalysis
        Left span — M-κ integration engine with span length L_a [mm].
    span_right : BeamDeflectionAnalysis
        Right span — M-κ integration engine with span length L_b [mm].
    q : float
        Uniform distributed load intensity [N/mm = kN/m].
    verbose : bool
        If True, print solver trace during residuum evaluations.
    """

    span_left:  BeamDeflectionAnalysis
    span_right: BeamDeflectionAnalysis
    q:          float
    verbose:    bool = False

    # ── end-rotation helpers ──────────────────────────────────────────────────

    def _end_phi(
        self,
        span: BeamDeflectionAnalysis,
        M_end_left: float,
        M_end_right: float,
        end: str,
    ) -> float:
        """Return the end rotation of *span* at 'left' (x=0) or 'right' (x=L).

        The moment distribution is the SSB under self.q plus the linear
        end-moment correction.  κ(x) is obtained from the M-κ inverse.
        """
        M_x     = span.get_M_x(self.q, M_end_left=M_end_left, M_end_right=M_end_right)
        kappa_x = span.get_kappa_x_from_M(M_x)
        phi_x   = _phi_ssb(kappa_x, span.x)
        return float(phi_x[0] if end == 'left' else phi_x[-1])

    # ── residuum ──────────────────────────────────────────────────────────────

    def residuum(self, M_hog: float) -> float:
        """R(M_hog) = φ_L(L_a) − φ_R(0); zero when rotation compatibility holds."""
        phi_L = self._end_phi(self.span_left,  0.0,    -M_hog, 'right')
        phi_R = self._end_phi(self.span_right, -M_hog,  0.0,   'left')
        if self.verbose:
            print(
                f"  M_hog={M_hog / 1e6:8.3f} kN·m  "
                f"φ_L={phi_L:+.6f}  φ_R={phi_R:+.6f}  R={phi_L - phi_R:+.2e}"
            )
        return phi_L - phi_R

    # ── elastic estimate (three-moment equation) ─────────────────────────────

    @property
    def M_hog_elastic(self) -> float:
        """M_hog [N·mm] from Clapeyron's three-moment equation (uniform EI).

        M_hog,el = q (L_a³ + L_b³) / [8 (L_a + L_b)]

        Reduces to q L² / 8 for equal spans.
        """
        La = self.span_left.L
        Lb = self.span_right.L
        return self.q * (La ** 3 + Lb ** 3) / (8.0 * (La + Lb))

    # ── solver ────────────────────────────────────────────────────────────────

    def solve(self, xtol: float = 1.0) -> float:
        """Return M_hog [N·mm] via brentq on the rotation-compatibility residuum.

        Bracket: [0, 1.5 · M_hog_el].  At M_hog = 0, R > 0 (φ_L > 0, φ_R < 0).
        At the upper end the over-large hogging reverses the imbalance, R < 0.
        """
        return brentq(self.residuum, 0.0, 1.5 * self.M_hog_elastic, xtol=xtol)

    def solve_over_load(self, q_arr: np.ndarray) -> np.ndarray:
        """Solve M_hog for each load level in *q_arr* [N/mm].

        Creates a lightweight copy with a different *q* for each step so the
        current instance is never mutated (safe for interactive / cached use).
        """
        from dataclasses import replace as _replace
        M_hog_arr = np.empty_like(q_arr)
        for i, q_i in enumerate(q_arr):
            cba_i = _replace(self, q=float(q_i))
            M_hog_arr[i] = cba_i.solve()
        return M_hog_arr

    # ── profile getters ───────────────────────────────────────────────────────

    def M_profiles(
        self, M_hog: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Moment profiles for the given M_hog.

        Returns
        -------
        x_a, M_a : coordinate and moment [N·mm] arrays for the left span
        x_b, M_b : coordinate and moment [N·mm] arrays for the right span
        """
        M_a = self.span_left.get_M_x(self.q,  M_end_right=-M_hog)
        M_b = self.span_right.get_M_x(self.q, M_end_left=-M_hog)
        return self.span_left.x, M_a, self.span_right.x, M_b

    def w_profiles(
        self, M_hog: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Deflection profiles [mm] for the given M_hog (downward positive).

        Uses the nonlinear M-κ table to obtain curvature at each section.

        Returns
        -------
        x_a, w_a, x_b, w_b : coordinate and deflection arrays per span
        """
        x_a, M_a, x_b, M_b = self.M_profiles(M_hog)

        def _w(span: BeamDeflectionAnalysis, M_x: np.ndarray, x: np.ndarray) -> np.ndarray:
            kappa_x = span.get_kappa_x_from_M(M_x)
            phi_x   = _phi_ssb(kappa_x, x)
            return -cumtrapz(phi_x, x, initial=0.0)   # w positive downward

        return (
            x_a, _w(self.span_left,  M_a, x_a),
            x_b, _w(self.span_right, M_b, x_b),
        )

    def elastic_w_profiles(
        self, M_hog: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """True linear-elastic deflection profiles using κ = M / EI.

        EI is estimated from a linear fit to the initial segment of the M-κ
        table.  This avoids the non-zero lower bound of the M-κ sweep
        (kappa_min = kappa_max × 0.001) that causes a step change in curvature
        at the moment zero-crossing when the nonlinear table is used.

        Returns
        -------
        x_a, w_a, x_b, w_b : coordinate and deflection arrays per span
        """
        x_a, M_a, x_b, M_b = self.M_profiles(M_hog)

        def _EI(span: BeamDeflectionAnalysis) -> float:
            # Use gross-section mean elastic stiffness — the same EI assumed by
            # the three-moment equation (where EI cancels).  The nonlinear M-κ
            # model treats the section as cracked from the first increment (no
            # tension stiffening), so comparing against E_cm·I_g clearly shows
            # the stiffness reduction due to cracking.
            return span.E_cm * span.I_g  # N·mm²

        def _w(span: BeamDeflectionAnalysis, M_x: np.ndarray, x: np.ndarray) -> np.ndarray:
            EI      = _EI(span)
            kappa_x = M_x / EI          # linear-elastic curvature
            phi_x   = _phi_ssb(kappa_x, x)
            return -cumtrapz(phi_x, x, initial=0.0)

        return (
            x_a, _w(self.span_left,  M_a, x_a),
            x_b, _w(self.span_right, M_b, x_b),
        )

    # ── Plotting ──────────────────────────────────────────────────────────────
    #
    # Structural sign convention (same as BeamDeflectionAnalysis):
    #   - y-axis INVERTED on profile plots so sagging / downward deflection
    #     appears below the beam reference axis.
    #   - Global x-axis: left span [0, L_a], right span [L_a, L_a + L_b].

    def plot_scheme(
        self,
        ax: Optional[plt.Axes] = None,
        load_label: Optional[str] = None,
    ) -> plt.Axes:
        """Structural schematic: beam axis, support triangles, UDL arrows.

        Parameters
        ----------
        load_label : str, optional
            Text shown above the UDL arrows.  Defaults to
            ``'$q$ = {self.q:.3g} N/mm'``.  Pass e.g.
            ``load_label='$p_{Ed,qp}$ = 11.9 kN/m'`` for the SLS context.

        No coordinate axes are shown — the panel is purely illustrative.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 2))

        La      = self.span_left.L
        Lb      = self.span_right.L
        L_total = La + Lb
        tri_h   = 0.06 * L_total
        q_level = 0.30 * L_total

        # Beam reference axis
        ax.plot([0, L_total], [0, 0], color='black', lw=2.0, solid_capstyle='round')

        # Distributed load: downward arrows + filled top bar
        for xi in np.linspace(0, L_total, 15):
            ax.annotate(
                '', xy=(xi, 0), xytext=(xi, q_level),
                arrowprops=dict(arrowstyle='->', color='steelblue', lw=1.1),
            )
        ax.fill_between(
            [0, L_total], [q_level] * 2, [q_level * 1.05] * 2,
            color='steelblue', alpha=0.25,
        )
        ax.text(
            L_total / 2, q_level * 1.12,
            load_label if load_label is not None else f'$q$ = {self.q:.3g} N/mm',
            ha='center', va='bottom', fontsize=9, color='steelblue',
        )

        # Support triangles at x = 0, L_a, L_a + L_b
        for xs in (0, La, L_total):
            ax.fill(
                [xs - tri_h * 0.55, xs + tri_h * 0.55, xs],
                [-tri_h, -tri_h, 0],
                color='#555555', zorder=3,
            )
            ax.text(xs, -tri_h * 1.55, f'{xs / 1000:.2f} m',
                    ha='center', va='top', fontsize=8, color='#555555')

        # Double-headed span dimension arrows
        arr_y = -tri_h * 3.0
        for x0, x1, label in (
            (0,  La,      f'$L_a$ = {La / 1000:.2f} m'),
            (La, L_total, f'$L_b$ = {Lb / 1000:.2f} m'),
        ):
            ax.annotate(
                '', xy=(x1, arr_y), xytext=(x0, arr_y),
                arrowprops=dict(arrowstyle='<->', color='black', lw=0.9),
            )
            ax.text((x0 + x1) / 2, arr_y - tri_h * 0.8, label,
                    ha='center', va='top', fontsize=9)

        ax.set_xlim(-0.05 * L_total, 1.05 * L_total)
        ax.set_ylim(-tri_h * 5.0, q_level * 1.3)
        ax.set_axis_off()
        return ax

    def plot_M(
        self,
        ax: Optional[plt.Axes] = None,
        show_elastic: bool = True,
        color_el: str = '#888888',
        color_nl: str = '#1f77b4',
        M_hog_nl: Optional[float] = None,
    ) -> plt.Axes:
        """Bending moment diagram: elastic estimate and nonlinear solution.

        Parameters
        ----------
        M_hog_nl : float, optional
            Pre-computed nonlinear hogging moment [N·mm].  When provided the
            internal ``solve()`` call is skipped (avoids duplicate solves when
            multiple plot methods are called in sequence).

        y-axis is inverted (sagging below the beam axis, structural convention).
        Circular markers show M_hog at the interior support for each case.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 4))

        La        = self.span_left.L
        M_hog_el  = self.M_hog_elastic
        if M_hog_nl is None:
            M_hog_nl  = self.solve()

        cases: list = []
        if show_elastic:
            cases.append((M_hog_el, color_el, '--',
                          f'elastic  $M_{{hog}}$ = {M_hog_el / 1e6:.2f} kN·m'))
        cases.append((M_hog_nl, color_nl, '-',
                      f'nonlinear  $M_{{hog}}$ = {M_hog_nl / 1e6:.2f} kN·m'))

        for M_hog, color, ls, label in cases:
            x_a, M_a, x_b, M_b = self.M_profiles(M_hog)
            ax.plot(x_a,       M_a / 1e6, color=color, lw=1.8, ls=ls, label=label)
            ax.plot(x_b + La,  M_b / 1e6, color=color, lw=1.8, ls=ls)
            # Interior support moment marker
            ax.plot(La, -M_hog / 1e6, marker='o', ms=6, color=color, zorder=5)

        # Support and interior-support guide lines
        for xs in (0, La, La + self.span_right.L):
            ax.axvline(xs, color='gray', lw=0.5, ls=':')
        ax.axhline(0, color='black', lw=0.8)

        ax.invert_yaxis()   # sagging below line
        ax.set_xlabel('$x$ [mm]', fontsize=11)
        ax.set_ylabel(r'$M$ [kN·m]  $\downarrow$ sagging', fontsize=11)
        ax.set_title('Bending moment diagram', fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, ls='--')
        return ax

    def plot_w(
        self,
        ax: Optional[plt.Axes] = None,
        show_elastic: bool = True,
        color_el: str = '#888888',
        color_nl: str = '#1f77b4',
        M_hog_nl: Optional[float] = None,
    ) -> plt.Axes:
        """Deflection profiles: elastic estimate and nonlinear solution.

        Parameters
        ----------
        M_hog_nl : float, optional
            Pre-computed nonlinear hogging moment [N·mm].  When provided the
            internal ``solve()`` call is skipped.

        y-axis is inverted (downward positive, structural convention).
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 4))

        La       = self.span_left.L
        Lb       = self.span_right.L
        M_hog_el = self.M_hog_elastic
        if M_hog_nl is None:
            M_hog_nl = self.solve()

        if show_elastic:
            x_a, w_a, x_b, w_b = self.elastic_w_profiles(M_hog_el)
            ax.plot(x_a,       w_a, color=color_el, lw=1.8, ls='--',
                    label=r'elastic ($E_{cm}\cdot I_g$, uncracked)')
            ax.plot(x_b + La,  w_b, color=color_el, lw=1.8, ls='--')

        x_a, w_a, x_b, w_b = self.w_profiles(M_hog_nl)
        ax.plot(x_a,       w_a, color=color_nl, lw=1.8, ls='-', label='nonlinear')
        ax.plot(x_b + La,  w_b, color=color_nl, lw=1.8, ls='-')

        for xs in (0, La, La + Lb):
            ax.axvline(xs, color='gray', lw=0.5, ls=':')
        ax.axhline(0, color='black', lw=0.8)

        ax.invert_yaxis()
        ax.set_xlabel('$x$ [mm]', fontsize=11)
        ax.set_ylabel(r'$w$ [mm]  $\downarrow$', fontsize=11)
        ax.set_title('Deflection profiles', fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, ls='--')
        return ax

    def plot_redistribution(
        self,
        q_arr: Optional[np.ndarray] = None,
        ax: Optional[plt.Axes] = None,
        color: str = '#d62728',
    ) -> plt.Axes:
        """Moment redistribution curve: M_hog / M_hog,el vs q.

        Shows how cracking (or material nonlinearity) shifts the interior
        support moment relative to the elastic reference.  Elastic behaviour
        yields a horizontal line at 1.0.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(7, 5))
        La, Lb = self.span_left.L, self.span_right.L
        if q_arr is None:
            q_arr = np.linspace(1e-3 * self.q, 2.0 * self.q, 40)

        M_hog_arr = self.solve_over_load(q_arr)
        M_el_arr  = q_arr * (La ** 3 + Lb ** 3) / (8.0 * (La + Lb))

        ax.plot(q_arr, M_hog_arr / M_el_arr, color=color, lw=2.0,
                label=r'$M_\mathrm{hog} / M_\mathrm{hog,el}$')
        ax.axhline(1.0, color='gray', lw=1.0, ls='--', label='elastic reference')
        ax.set_xlabel('$q$ [N/mm]', fontsize=11)
        ax.set_ylabel(r'$M_\mathrm{hog} / M_\mathrm{hog,el}$', fontsize=11)
        ax.set_title('Moment redistribution', fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, ls='--')
        return ax

    def plot_summary(self, title: str = '') -> None:
        """3-panel summary: beam scheme | M diagram | deflection profile.

        Analogous to BeamDeflectionAnalysis.plot_summary but for the two-span
        geometry.  Each profile panel overlays the elastic estimate (gray
        dashed) and the nonlinear solution (blue solid).

        ``solve()`` is called once and the result is shared between
        ``plot_M`` and ``plot_w`` to avoid redundant computation.
        """
        M_hog_nl = self.solve()
        fig, axes = plt.subplots(
            3, 1,
            figsize=(12, 10),
            gridspec_kw={'height_ratios': [1, 2, 2]},
        )
        self.plot_scheme(axes[0])
        self.plot_M(axes[1], M_hog_nl=M_hog_nl)
        self.plot_w(axes[2], M_hog_nl=M_hog_nl)

        La, Lb = self.span_left.L, self.span_right.L
        fig.suptitle(
            title or (
                f'Two-span continuous beam — '
                f'$L_a$ = {La / 1000:.2f} m,  '
                f'$L_b$ = {Lb / 1000:.2f} m,  '
                f'$q$ = {self.q:.3g} N/mm'
            ),
            fontsize=12, fontweight='bold',
        )
        fig.tight_layout()
        try:
            from IPython.display import display as ipy_display
            ipy_display(fig)
            plt.close(fig)
        except ImportError:
            return fig
