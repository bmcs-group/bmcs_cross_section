"""
scite.beam.continuous.continuous_beam
======================================

ContinuousBeamAnalysis — two-span nonlinear continuous beam solved by
rotation compatibility at the interior support.

Algorithm
---------
Each span is treated as an independent simply supported beam (SSB).  The
unknown hogging moment M_hog ≤ 0 at the interior support is determined by
requiring equal end-rotations from the two spans:

    φ_a(L_a; M_hog) = φ_b(0; M_hog)   →   residuum R = φ_L − φ_R = 0

End-rotations are computed via numerical integration of the M-κ curve with the
SSB displacement BC w(0) = w(L) = 0.  The brentq solver finds the root.

Sign convention (sagging positive, hogging negative — consistent with M-κ)
---------------------------------------------------------------------------
- M > 0 → sagging (tension at bottom).   κ > 0 → sagging.
- M < 0 → hogging (tension at top).      κ < 0 → hogging.
- M_hog ≤ 0 is the *signed* interior support moment.
- κ_hog ≤ 0 is the *signed* support curvature.
- φ = −dw/dx with w downward positive → φ > 0 means slope points upward.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import cumulative_trapezoid as cumtrapz
from scipy.optimize import brentq

from scite.beam.bending.beam_deflection import BeamDeflectionAnalysis


def _M_sag_max(
    q_arr: np.ndarray,
    M_hog_kNm: np.ndarray,
    L: float,
) -> np.ndarray:
    """Max sagging moment [kN·m] for a SSB with end moment M_hog [kN·m] and UDL q [N/mm]."""
    M_Nmm  = np.asarray(M_hog_kNm) * 1e6   # signed, ≤ 0
    q_a    = np.asarray(q_arr)
    x_star = np.clip(L / 2 + M_Nmm / (q_a * L), 0.0, L)
    return (q_a * 0.5 * x_star * (L - x_star) + M_Nmm * (x_star / L)) / 1e6


class CompatibilityNoRoot(Exception):
    """Raised when no root exists in the admissible κ_hog domain.

    This occurs when q ≥ q_u (failure load): the rotation-compatibility
    equation has no solution with |κ_hog| ≤ κ_{R,hog}.  The outer q-loop
    should catch this and interpret it as failure.
    """

    def __init__(self, q: float) -> None:
        self.q = q
        super().__init__(
            f"No root in [κ_R_hog, 0] at q = {q:.4g} N/mm — capacity exceeded"
        )

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
        M_end_left and M_end_right are signed [N·mm].
        """
        M_x     = span.get_M_x(self.q, M_end_left=M_end_left, M_end_right=M_end_right)
        kappa_x = span.get_kappa_x_from_M(M_x)
        phi_x   = _phi_ssb(kappa_x, span.x)
        return float(phi_x[0] if end == 'left' else phi_x[-1])

    # ── residuum ──────────────────────────────────────────────────────────────

    def residuum(self, M_hog: float) -> float:
        """R(M_hog) = φ_L(L_a) − φ_R(0); zero when rotation compatibility holds.

        M_hog [N·mm] ≤ 0 (signed, hogging).  Passed directly as end-moment
        to the left span's right end and the right span's left end.
        """
        phi_L = self._end_phi(self.span_left,  0.0,   M_hog, 'right')
        phi_R = self._end_phi(self.span_right, M_hog,  0.0,  'left')
        if self.verbose:
            print(
                f"  M_hog={M_hog / 1e6:8.3f} kN·m  "
                f"φ_L={phi_L:+.6f}  φ_R={phi_R:+.6f}  R={phi_L - phi_R:+.2e}"
            )
        return phi_L - phi_R

    # ── elastic estimate (three-moment equation) ─────────────────────────────

    @property
    def M_hog_elastic(self) -> float:
        """Elastic hogging moment [N·mm] at interior support (≤ 0, signed).

        Clapeyron's three-moment equation (uniform EI):

            M_hog,el = − q (L_a³ + L_b³) / [8 (L_a + L_b)]

        Reduces to −q L² / 8 for equal spans.
        """
        La = self.span_left.L
        Lb = self.span_right.L
        return -self.q * (La ** 3 + Lb ** 3) / (8.0 * (La + Lb))

    # ── solver ────────────────────────────────────────────────────────────────

    def solve(self, xtol: float = 1.0) -> float:
        """Return M_hog [N·mm] ≤ 0 (signed) via brentq on the residuum.

        Bracket: [1.5·M_hog_el, 0].  M_hog_el < 0 so the bracket spans
        [large hogging, zero].  At M_hog = 0: R > 0 (UDL only, no support
        moment).  At the lower bound: large hogging reverses the imbalance,
        R < 0.
        """
        return brentq(self.residuum, 1.5 * self.M_hog_elastic, 0.0, xtol=xtol)

    def solve_over_load(self, q_arr: np.ndarray) -> np.ndarray:
        """Solve M_hog [N·mm] ≤ 0 for each load level in *q_arr* [N/mm].

        Creates a lightweight copy with a different *q* for each step so the
        current instance is never mutated (safe for interactive / cached use).
        """
        from dataclasses import replace as _replace
        M_hog_arr = np.empty_like(q_arr)
        for i, q_i in enumerate(q_arr):
            cba_i = _replace(self, q=float(q_i))
            M_hog_arr[i] = cba_i.solve()
        return M_hog_arr

    # ── κ-controlled solver (Strategy C) ─────────────────────────────────────

    @property
    def kappa_R_hog(self) -> float:
        """Signed curvature [1/mm] at peak hogging moment (≤ 0).

        Uses the independently solved hogging branch (kappa_neg_values) when
        available (solve_mode='both'); otherwise mirrors the sagging branch peak
        — valid for symmetric sections (equal top/bottom reinforcement).
        """
        mk = self.span_left.mk
        if mk.kappa_neg_values is not None and len(mk.kappa_neg_values) > 0:
            idx_peak = int(np.argmin(mk.M_neg_values))
            return float(mk.kappa_neg_values[idx_peak])    # already negative
        else:
            idx_peak = int(np.argmax(mk.M_values))
            return -float(mk.kappa_values[idx_peak])       # negate to make hogging negative

    def _forward_map(self, kappa_hog: float) -> float:
        """Map κ_hog [1/mm] (≤ 0, signed) → M_hog [N·mm] (≤ 0, signed).

        Uses the ascending sub-segment of the hogging branch (magnitudes for
        np.interp which requires ascending x); result is negated before return.
        For symmetric sections without a neg branch, the sagging mirror is used.
        """
        mk = self.span_left.mk
        if mk.kappa_neg_values is not None and len(mk.kappa_neg_values) > 0:
            idx_peak = int(np.argmin(mk.M_neg_values))
            kappa_ref = np.abs(mk.kappa_neg_values[:idx_peak + 1])   # magnitudes, ascending
            M_ref_Nmm = np.abs(mk.M_neg_values[:idx_peak + 1]) * 1e6  # magnitudes, ascending
        else:
            idx_peak = int(np.argmax(mk.M_values))
            kappa_ref = mk.kappa_values[:idx_peak + 1]
            M_ref_Nmm = mk.M_values[:idx_peak + 1] * 1e6
        # Ensure the map passes through (0, 0): the M-κ table starts at a
        # small non-zero kappa, so np.interp would clamp at the first entry
        # for kappa < kappa_ref[0] — prepending the origin fixes this.
        kappa_ref = np.concatenate([[0.0], kappa_ref])
        M_ref_Nmm = np.concatenate([[0.0], M_ref_Nmm])
        return -float(np.interp(abs(kappa_hog), kappa_ref, M_ref_Nmm))

    def residuum_kappa(self, kappa_hog: float) -> float:
        """R(κ_hog) = φ_L(La) − φ_R(0) for κ_hog [1/mm] ≤ 0 (signed).

        The hogging moment is obtained via the forward map M_hog = f(κ_hog),
        then delegated to residuum().  No M-κ inversion at the support.
        """
        return self.residuum(self._forward_map(kappa_hog))

    def solve_kappa_controlled(self, xtol: float = 1e-12) -> float:
        """Return κ_hog [1/mm] ≤ 0 (signed) via brentq on the residuum.

        Bracket: [κ_{R,hog}, κ_eps] where both are negative and κ_R < κ_eps.
        At κ_eps (near zero, tiny hogging): R > 0.
        At κ_R (full hogging): R < 0.

        Raises
        ------
        CompatibilityNoRoot
            When R_lo * R_hi ≥ 0 (same sign at both bracket ends), meaning no
            root exists and q ≥ q_u (failure load reached).
        """
        kappa_R   = self.kappa_R_hog               # negative, e.g. −0.049
        kappa_eps = 1e-8 * kappa_R                 # tiny negative, near zero

        R_at_kappa_R   = self.residuum_kappa(kappa_R)    # expected < 0
        R_at_kappa_eps = self.residuum_kappa(kappa_eps)  # expected > 0

        if R_at_kappa_R * R_at_kappa_eps >= 0:
            raise CompatibilityNoRoot(self.q)

        # brentq requires a < b: kappa_R < kappa_eps (both negative, kappa_R more negative)
        return brentq(self.residuum_kappa, kappa_R, kappa_eps, xtol=xtol)

    def solve_over_load_kappa_controlled(
        self, q_arr: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Solve κ_hog [1/mm] ≤ 0 for each load in q_arr [N/mm], stopping at failure.

        Returns
        -------
        q_valid     : loads for which a root was found (q < q_u)
        kappa_hog_arr : corresponding κ_hog values [1/mm], signed ≤ 0
        """
        from dataclasses import replace as _replace

        q_valid_list: list[float] = []
        kappa_list: list[float] = []
        for q_i in q_arr:
            cba_i = _replace(self, q=float(q_i))
            try:
                kappa_list.append(cba_i.solve_kappa_controlled())
                q_valid_list.append(float(q_i))
            except CompatibilityNoRoot:
                break
        return np.array(q_valid_list), np.array(kappa_list)

    # ── q-controlled solver (Strategy D) ─────────────────────────────────────
    #
    # κ_hog ≤ 0 is prescribed (stepped through the M-κ table); q is the inner
    # brentq unknown.  R(q=0) < 0 is analytically guaranteed for M_hog < 0,
    # so the bracket [0, q_hi] needs no pre-check sign test.

    def residuum_q(self, q: float, M_hog: float) -> float:
        """R(q; M_hog) = φ_L(L_a) − φ_R(0) with M_hog [N·mm] ≤ 0 prescribed.

        Uses a temporary instance with self.q replaced by *q* so that the
        existing residuum() implementation is reused without modification.
        """
        from dataclasses import replace as _replace
        return _replace(self, q=float(q)).residuum(M_hog)

    def solve_q_from_kappa(self, kappa_hog: float) -> float:
        """Return q [N/mm] satisfying rotation compatibility for prescribed κ_hog ≤ 0.

        Bracket: [0, q_hi] where q_hi starts at 4 × the elastic estimate and
        doubles up to 5 times if R(q_hi) is not yet positive.

        Raises
        ------
        CompatibilityNoRoot
            If the upper bracket cannot be established after 5 doublings.
        """
        M_hog = self._forward_map(kappa_hog)          # N·mm, negative
        La, Lb = self.span_left.L, self.span_right.L
        q_el = -8.0 * M_hog * (La + Lb) / (La ** 3 + Lb ** 3)   # positive (M_hog < 0)

        q_hi = 4.0 * q_el
        for _ in range(5):
            if self.residuum_q(q_hi, M_hog) > 0:
                break
            q_hi *= 2.0
        else:
            raise CompatibilityNoRoot(q_hi)

        xtol = max(1e-6 * q_el, 1e-8)
        return brentq(
            lambda q: self.residuum_q(q, M_hog),
            0.0,
            q_hi,
            xtol=xtol,
        )

    def solve_over_kappa_q_controlled(
        self,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Sweep κ_hog through the ascending hogging M-κ branch; find q for each.

        The outer parameter steps through `mk.kappa_neg_values` (signed, ≤ 0)
        or the sagging mirror for symmetric fallback.  The last entry corresponds
        to κ_hog = κ_{R,hog} and gives the ultimate load q_u directly.

        Parameters
        ----------
        progress_cb : callable(fraction, label), optional
            Called after each κ step with a progress fraction in [0, 1] and a
            human-readable label string.  Used by ComputeNode to update a live
            progress bar in the Streamlit UI.

        Returns
        -------
        kappa_arr : [1/mm]   signed hogging curvatures (≤ 0, ascending in magnitude)
        M_hog_arr : [kN·m]  signed hogging moments (≤ 0)
        q_arr     : [N/mm]  compatible distributed loads (both spans, > 0)
        """
        mk = self.span_left.mk
        if mk.kappa_neg_values is not None and len(mk.kappa_neg_values) > 0:
            idx_peak    = int(np.argmin(mk.M_neg_values))
            kappa_sweep = mk.kappa_neg_values[:idx_peak + 1]   # signed negative
        else:
            idx_peak    = int(np.argmax(mk.M_values))
            kappa_sweep = -mk.kappa_values[:idx_peak + 1]       # negate to make hogging negative

        n = len(kappa_sweep)
        kappa_list: list[float] = []
        M_hog_list: list[float] = []
        q_list:     list[float] = []
        for i, kappa_hog in enumerate(kappa_sweep):
            kappa_hog = float(kappa_hog)
            q         = self.solve_q_from_kappa(kappa_hog)
            kappa_list.append(kappa_hog)
            M_hog_list.append(self._forward_map(kappa_hog) / 1e6)   # kN·m, negative
            q_list.append(q)
            if progress_cb is not None:
                progress_cb((i + 1) / n, f"κ-sweep: step {i + 1} / {n}")

        return np.array(kappa_list), np.array(M_hog_list), np.array(q_list)

    # ── profile getters ───────────────────────────────────────────────────────

    def M_profiles(
        self, M_hog: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Moment profiles for the given M_hog [N·mm] ≤ 0 (signed, hogging).

        M_hog is passed directly as the end-moment to both spans; the sign
        convention is consistent with the M-κ curve (negative = hogging).

        Returns
        -------
        x_a, M_a : coordinate and moment [N·mm] arrays for the left span
        x_b, M_b : coordinate and moment [N·mm] arrays for the right span
        """
        M_a = self.span_left.get_M_x(self.q,  M_end_right=M_hog)
        M_b = self.span_right.get_M_x(self.q, M_end_left=M_hog)
        return self.span_left.x, M_a, self.span_right.x, M_b

    def w_profiles(
        self, M_hog: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Deflection profiles [mm] for the given M_hog [N·mm] ≤ 0 (downward positive).

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
            return span.E_cm * span.I_g  # N·mm²

        def _w(span: BeamDeflectionAnalysis, M_x: np.ndarray, x: np.ndarray) -> np.ndarray:
            EI      = _EI(span)
            kappa_x = M_x / EI          # linear-elastic curvature (signed)
            phi_x   = _phi_ssb(kappa_x, x)
            return -cumtrapz(phi_x, x, initial=0.0)

        return (
            x_a, _w(self.span_left,  M_a, x_a),
            x_b, _w(self.span_right, M_b, x_b),
        )

    # ── κ-controlled sweep cache and plot methods ─────────────────────────────

    def compute_sweep(
        self,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> dict:
        """Run Strategy D and return the sweep dict.

        This is the computation core, separated from the cached_property so
        that a progress callback can be supplied (e.g. by ComputeNode for live
        Streamlit progress bars).

        Parameters
        ----------
        progress_cb : callable(fraction, label), optional
            Passed through to ``solve_over_kappa_q_controlled``.  Called after
            each κ step with a progress fraction in [0, 1] and a label string.

        Returns a dict with keys:
          kappa_d      [1/mm]  signed hogging curvatures (≤ 0, ascending magnitude)
          M_hog_d      [kN·m] signed hogging moments (≤ 0)
          q_d          [N/mm] compatible distributed loads (> 0)
          M_hog_el_d   [kN·m] elastic M_hog at each sweep step (≤ 0)
          M_sag_a_d    [kN·m] max NL sagging moment in left span at each step
          M_sag_b_d    [kN·m] max NL sagging moment in right span at each step
          M_sag_a_el_d [kN·m] max elastic sagging in left span at each step
          M_sag_b_el_d [kN·m] max elastic sagging in right span at each step
          i_yield      int    first index where top reinforcement yields (len if no yield)
          eps_yd       float  top-bar design yield strain (None if unavailable)
        """
        kappa_d, M_hog_d, q_d = self.solve_over_kappa_q_controlled(progress_cb)
        La = self.span_left.L
        Lb = self.span_right.L
        mk = self.span_left.mk

        M_hog_el_d = -q_d * (La ** 3 + Lb ** 3) / (8.0 * (La + Lb)) / 1e6  # [kN·m]

        # Yield detection — top fibre of the hogging section
        n        = len(kappa_d)
        eps_yd   = None
        i_yield  = n  # default: no yield detected

        if (
            mk.eps_bot_neg_values is not None
            and len(mk.eps_bot_neg_values) >= n
            and mk.cs.reinforcement.layers
        ):
            top_layer = max(mk.cs.reinforcement.layers, key=lambda lay: lay.z)
            # eps_sy is the design yield strain on ReinforcementLayer
            eps_yd    = float(getattr(top_layer, 'eps_sy',
                              getattr(top_layer, 'eps_yd', None) or
                              getattr(top_layer.material, 'eps_yd', 0.002174)))
            h         = float(mk.cs.h_total)
            eps_bot   = mk.eps_bot_neg_values[:n]
            eps_top   = eps_bot - kappa_d * h   # top fibre (tension in hogging)
            yield_mask = eps_top >= eps_yd
            if yield_mask.any():
                i_yield = int(np.argmax(yield_mask))

        return dict(
            kappa_d      = kappa_d,
            M_hog_d      = M_hog_d,
            q_d          = q_d,
            M_hog_el_d   = M_hog_el_d,
            M_sag_a_d    = _M_sag_max(q_d, M_hog_d, La),
            M_sag_b_d    = _M_sag_max(q_d, M_hog_d, Lb),
            M_sag_a_el_d = _M_sag_max(q_d, M_hog_el_d, La),
            M_sag_b_el_d = _M_sag_max(q_d, M_hog_el_d, Lb),
            i_yield      = i_yield,
            eps_yd       = eps_yd,
        )

    @cached_property
    def sweep(self) -> dict:
        """Run Strategy D once and cache the result (no progress callback).

        For use in notebooks and scripts.  For Streamlit apps with a live
        progress bar, call ``compute_sweep(progress_cb=…)`` directly.
        """
        return self.compute_sweep()

    def _sweep_vlines(self, ax: plt.Axes) -> None:
        """Draw yield and failure vertical lines on a κ sweep axis."""
        s  = self.sweep
        kappa_abs = np.abs(s['kappa_d']) * 1e3   # ‰/mm
        i_yield   = s['i_yield']
        n         = len(kappa_abs)
        if i_yield < n:
            ax.axvline(kappa_abs[i_yield], color='#2ca02c', ls='--', lw=1.1, zorder=0)
        ax.axvline(kappa_abs[-1], color='#d62728', ls=':', lw=1.1, zorder=0)

    def plot_q_kappa(
        self,
        ax: Optional[plt.Axes] = None,
        kappa_idx: Optional[int] = None,
    ) -> plt.Axes:
        """Panel 1: distributed load q vs |κ_hog| along the Strategy D sweep.

        Parameters
        ----------
        kappa_idx : int, optional
            When given, draw a vertical marker at this sweep step.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 3))

        s             = self.sweep
        kappa_abs     = np.abs(s['kappa_d']) * 1e3   # ‰/mm
        q_d           = s['q_d']
        i_yield       = s['i_yield']
        q_u           = q_d[-1]
        n             = len(kappa_abs)
        C_FAIL        = '#d62728'
        C_YLD         = '#2ca02c'

        # pre-yield segment (always present)
        ax.plot(
            kappa_abs[:i_yield + 1], q_d[:i_yield + 1],
            '-', color='steelblue', lw=2.0, label='$q$  pre-yield',
        )
        # post-yield segment (if any)
        if i_yield < n - 1:
            ax.plot(
                kappa_abs[i_yield:], q_d[i_yield:],
                '-', color='#9467bd', lw=2.0, label='$q$  post-yield',
            )

        ax.axhline(q_u, color=C_FAIL, ls=':', lw=1.0,
                   label=f'$q_u$ = {q_u:.2f} N/mm')
        self._sweep_vlines(ax)

        # yield annotation
        if i_yield < n and s['eps_yd'] is not None:
            eps_yd = s['eps_yd']
            ax.annotate(
                f'top-bar yield\n$\\varepsilon_{{yd}}={eps_yd * 1e3:.2f}$‰',
                xy=(kappa_abs[i_yield], q_d[i_yield]),
                xytext=(kappa_abs[i_yield], 0.70 * q_u),
                arrowprops=dict(arrowstyle='->', color=C_YLD, lw=1.2),
                color=C_YLD, fontsize=8.5, ha='left', va='top',
            )
        # failure annotation
        mk      = self.span_left.mk
        idx_pk  = int(np.argmin(mk.M_neg_values)) if (
            mk.M_neg_values is not None and len(mk.M_neg_values) > 0
        ) else -1
        mode_label = ''
        try:
            from scite.cs_design.cs_stress_strain_profile import StressStrainProfile
            k_last  = float(s['kappa_d'][-1])
            eb_last = float(mk.eps_bot_neg_values[idx_pk]) if idx_pk >= 0 else 0.0
            p       = StressStrainProfile(mk.cs, kappa=k_last, eps_bottom=eb_last)
            mode_label = p.failure_mode
        except Exception:
            pass

        ax.annotate(
            f'$q_u$={q_u:.2f}' + (f'\n{mode_label}' if mode_label else ''),
            xy=(kappa_abs[-1], q_u),
            xytext=(kappa_abs[-1], 0.70 * q_u),
            arrowprops=dict(arrowstyle='->', color=C_FAIL, lw=1.2),
            color=C_FAIL, fontsize=8.5, ha='right', va='top',
        )

        # current-step marker
        if kappa_idx is not None:
            idx = int(np.clip(kappa_idx, 0, n - 1))
            ax.axvline(kappa_abs[idx], color='gray', lw=1.2, ls='-', alpha=0.7, zorder=3)
            ax.scatter([kappa_abs[idx]], [q_d[idx]],
                       color='steelblue', s=50, zorder=5)

        ax.set_ylabel('$q$  [N/mm]', fontsize=11)
        ax.legend(fontsize=11, loc='lower right')
        ax.grid(True, alpha=0.3, ls='--')
        return ax

    def plot_M_kappa(
        self,
        ax: Optional[plt.Axes] = None,
        kappa_idx: Optional[int] = None,
    ) -> plt.Axes:
        """Panel 2: |M_hog| and M_sag moments vs |κ_hog| along the sweep.

        Legend is split:
          - lower-left : line labels for the dynamic curves (M_hog, M_sag)
          - lower-right: text box with reference values (M_R, M_hog_el, δ_M)

        Parameters
        ----------
        kappa_idx : int, optional
            When given, add scatter markers and annotate the current step's values.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))

        s          = self.sweep
        kappa_abs  = np.abs(s['kappa_d']) * 1e3   # ‰/mm
        M_hog_abs  = np.abs(s['M_hog_d'])
        M_sag_a    = s['M_sag_a_d']
        M_sag_b    = s['M_sag_b_d']
        n          = len(kappa_abs)
        La         = self.span_left.L
        Lb         = self.span_right.L
        bda        = self.span_left
        C_HOG      = 'steelblue'   # redistributed hogging — blue
        C_SAG      = '#4488cc'     # NL sagging — lighter blue
        C_EL       = '#cc2222'     # elastic reference — red

        M_hog_el_at_qu = abs(s['M_hog_el_d'][-1])
        M_R_hog        = M_hog_abs[-1]
        delta_M        = M_R_hog / M_hog_el_at_qu

        sym = abs(La - Lb) < 1.0   # spans equal to within 1 mm

        # ── Curve lines — these go into the left legend ───────────────────────
        h_hog, = ax.plot(kappa_abs, M_hog_abs, '-', color=C_HOG, lw=2.0)
        if sym:
            h_sag_a, = ax.plot(kappa_abs, M_sag_a, '--', color=C_SAG, lw=2.0)
            curve_handles = [h_hog, h_sag_a]
            curve_labels  = ['$|M_{hog}|$', '$M_{sag,max}$']
        else:
            h_sag_a, = ax.plot(kappa_abs, M_sag_a, '--', color=C_SAG, lw=2.0)
            h_sag_b, = ax.plot(kappa_abs, M_sag_b, ':',  color=C_SAG, lw=2.0)
            curve_handles = [h_hog, h_sag_a, h_sag_b]
            curve_labels  = ['$|M_{hog}|$', '$M_{sag,a}$ (left)', '$M_{sag,b}$ (right)']

        # ── Reference axhlines — no legend labels ─────────────────────────────
        ax.axhline(bda.M_R,        color=C_HOG, ls=':', lw=1.2)   # M_R,sag — blue
        ax.axhline(M_R_hog,        color=C_HOG, ls=':', lw=1.2)   # M_R,hog — blue
        ax.axhline(M_hog_el_at_qu, color=C_EL,  ls='--', lw=1.2)  # elastic ref — red

        self._sweep_vlines(ax)
        ax.set_ylim(bottom=0, top=M_hog_el_at_qu * 1.12)

        # ── Current-step markers ──────────────────────────────────────────────
        if kappa_idx is not None:
            idx = int(np.clip(kappa_idx, 0, n - 1))
            ax.axvline(kappa_abs[idx], color='gray', lw=1.2, ls='-', alpha=0.7, zorder=3)
            ax.scatter([kappa_abs[idx]], [M_hog_abs[idx]], color='steelblue', s=50, zorder=5)
            ax.scatter([kappa_abs[idx]], [M_sag_a[idx]],  color='steelblue', s=50, zorder=5)
            if not sym:
                ax.scatter([kappa_abs[idx]], [M_sag_b[idx]],
                           color='steelblue', s=50, marker='s', zorder=5)

        # ── Left legend: curve line styles ────────────────────────────────────
        leg_left = ax.legend(
            curve_handles, curve_labels,
            fontsize=10, loc='lower left',
            framealpha=0.85,
        )
        ax.add_artist(leg_left)   # keep it when we add the second legend

        # ── Right text box: reference values ──────────────────────────────────
        ref_lines = [
            f'$M_R$ (sag) = {bda.M_R:.1f} kN·m',
            f'$M_R$ (hog) = {M_R_hog:.1f} kN·m',
            f'$|M_{{hog,el}}|(q_u)$ = {M_hog_el_at_qu:.1f} kN·m',
            f'$\\delta_M = {delta_M:.3f}$',
        ]
        ax.text(
            0.99, 0.02, '\n'.join(ref_lines),
            transform=ax.transAxes,
            ha='right', va='bottom', fontsize=9.5,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='#aaaaaa', alpha=0.9),
        )

        ax.set_xlabel(r'$|\kappa_{hog}|$  [‰/mm]', fontsize=11)
        ax.set_ylabel('Moment  [kN·m]', fontsize=11)
        ax.grid(True, alpha=0.3, ls='--')
        return ax

    def plot_moment_profile_at_step(
        self,
        ax: Optional[plt.Axes] = None,
        kappa_idx: int = -1,
    ) -> plt.Axes:
        """Two-bay bending moment diagram at a given sweep step.

        Shows both the nonlinear (blue, filled) and elastic (red) moment
        profiles.  Sagging-peak values appear in corner text boxes; hogging
        values are annotated directly at the interior support.

        Parameters
        ----------
        kappa_idx : int
            Sweep index (0 … n-1).  -1 means the last step (ultimate state).
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 3.5))

        s   = self.sweep
        n   = len(s['kappa_d'])
        idx = int(np.clip(kappa_idx if kappa_idx >= 0 else n - 1, 0, n - 1))
        La  = self.span_left.L
        Lb  = self.span_right.L

        q_step        = float(s['q_d'][idx])
        M_hog_Nmm     = float(s['M_hog_d'][idx]) * 1e6      # NL hogging, N·mm, signed ≤ 0
        M_hog_el_Nmm  = float(s['M_hog_el_d'][idx]) * 1e6   # elastic hogging at same q

        from dataclasses import replace as _replace
        cba_step = _replace(self, q=q_step)

        # Nonlinear and elastic moment profiles
        x_a,  M_a,  x_b,  M_b  = cba_step.M_profiles(M_hog_Nmm)
        x_a_,  M_a_el, x_b_,  M_b_el = cba_step.M_profiles(M_hog_el_Nmm)

        x_b_g = x_b + La   # global x for right span

        # ── Nonlinear: blue solid fill ────────────────────────────────────────
        ax.plot(x_a,  M_a    / 1e6, '-', color='steelblue', lw=2.0)
        ax.plot(x_b_g, M_b   / 1e6, '-', color='steelblue', lw=2.0)
        ax.fill_between(x_a,  0, M_a   / 1e6, color='steelblue', alpha=0.13)
        ax.fill_between(x_b_g, 0, M_b  / 1e6, color='steelblue', alpha=0.13)

        # ── Elastic: red solid, no fill ───────────────────────────────────────
        ax.plot(x_a,  M_a_el / 1e6, '-', color='#cc2222', lw=1.6, alpha=0.85)
        ax.plot(x_b_g, M_b_el / 1e6, '-', color='#cc2222', lw=1.6, alpha=0.85)

        ax.axhline(0, color='black', lw=0.8)
        for xs in (0, La, La + Lb):
            ax.axvline(xs, color='gray', lw=0.5, ls=':')

        # ── Sagging-peak markers ──────────────────────────────────────────────
        idx_sag_a    = int(np.argmax(M_a))
        idx_sag_b    = int(np.argmax(M_b))
        idx_sag_a_el = int(np.argmax(M_a_el))
        idx_sag_b_el = int(np.argmax(M_b_el))

        ax.scatter([x_a[idx_sag_a]],    [M_a[idx_sag_a]    / 1e6],
                   color='steelblue', s=55, zorder=6)
        ax.scatter([x_b_g[idx_sag_b]],  [M_b[idx_sag_b]    / 1e6],
                   color='steelblue', s=55, zorder=6)
        ax.scatter([x_a[idx_sag_a_el]], [M_a_el[idx_sag_a_el] / 1e6],
                   color='#cc2222', s=45, zorder=6, marker='D')
        ax.scatter([x_b_g[idx_sag_b_el]], [M_b_el[idx_sag_b_el] / 1e6],
                   color='#cc2222', s=45, zorder=6, marker='D')

        # ── Interior-support (hogging) markers ───────────────────────────────
        ax.scatter([La], [M_hog_Nmm    / 1e6], color='steelblue', s=65, zorder=7)
        ax.scatter([La], [M_hog_el_Nmm / 1e6], color='#cc2222',   s=50, zorder=7, marker='D')

        # ── Fixed y-limits from the ultimate state ────────────────────────────
        # Both NL and elastic values at the last sweep step define the fixed range
        y_min_ult = min(float(s['M_hog_d'][-1]), float(s['M_hog_el_d'][-1])) * 1.12
        y_max_ult = max(float(s['M_sag_a_d'][-1]),    float(s['M_sag_b_d'][-1]),
                        float(s['M_sag_a_el_d'][-1]),  float(s['M_sag_b_el_d'][-1])) * 1.12
        ax.set_ylim(y_min_ult, y_max_ult)

        ax.invert_yaxis()   # sagging below axis (structural convention)

        C_NL = 'steelblue'
        C_EL = '#cc2222'

        # ── Hogging box — split into NL (blue) and EL (red), stacked at interior support
        # Placed in the sagging zone (axes y≈0) which is free space at x=La.
        import matplotlib.transforms as _mtfm
        _blended = _mtfm.blended_transform_factory(ax.transData, ax.transAxes)
        ax.text(
            La, 0.03,
            f'$M_{{hog,nl}}$ = {M_hog_Nmm / 1e6:.1f} kN·m',
            transform=_blended, ha='center', va='bottom', fontsize=8.5, color=C_NL,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=C_NL, alpha=0.90),
        )
        ax.text(
            La, 0.17,
            f'$M_{{hog,el}}$  = {M_hog_el_Nmm / 1e6:.1f} kN·m',
            transform=_blended, ha='center', va='bottom', fontsize=8.5, color=C_EL,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=C_EL, alpha=0.90),
        )

        # ── Corner sagging boxes — NL (blue) and EL (red) stacked in the upper corners
        # (hogging zone corners at x=0 and x=La+Lb are free: moment is 0 at outer supports)
        sym = abs(La - Lb) < 1.0
        # Left span — NL
        ax.text(
            0.01, 0.97,
            f'Left span\n$M_{{sag,nl}}$ = {M_a[idx_sag_a] / 1e6:.1f} kN·m',
            transform=ax.transAxes, ha='left', va='top', fontsize=8.5, color=C_NL,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=C_NL, alpha=0.88),
        )
        # Left span — EL
        ax.text(
            0.01, 0.80,
            f'$M_{{sag,el}}$  = {M_a_el[idx_sag_a_el] / 1e6:.1f} kN·m',
            transform=ax.transAxes, ha='left', va='top', fontsize=8.5, color=C_EL,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=C_EL, alpha=0.88),
        )
        # Right span — NL
        ax.text(
            0.99, 0.97,
            ('Right span' if not sym else 'Right = Left') + '\n'
            f'$M_{{sag,nl}}$ = {M_b[idx_sag_b] / 1e6:.1f} kN·m',
            transform=ax.transAxes, ha='right', va='top', fontsize=8.5, color=C_NL,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=C_NL, alpha=0.88),
        )
        # Right span — EL
        ax.text(
            0.99, 0.80,
            f'$M_{{sag,el}}$  = {M_b_el[idx_sag_b_el] / 1e6:.1f} kN·m',
            transform=ax.transAxes, ha='right', va='top', fontsize=8.5, color=C_EL,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=C_EL, alpha=0.88),
        )

        ax.set_xlabel('$x$  [mm]', fontsize=11)
        ax.set_ylabel(r'$M$  [kN·m]', fontsize=11)
        ax.grid(True, alpha=0.3, ls='--')
        return ax

    # ── Plotting ──────────────────────────────────────────────────────────────
    #
    # Structural sign convention:
    #   - M > 0 (sagging) plotted BELOW the beam axis (invert_yaxis).
    #   - M < 0 (hogging) plotted ABOVE the beam axis.
    #   - Global x-axis: left span [0, L_a], right span [L_a, L_a + L_b].
    #   - Interior support is at x = L_a.

    def plot_scheme(
        self,
        ax: Optional[plt.Axes] = None,
        load_label: Optional[str] = None,
    ) -> plt.Axes:
        """Structural schematic: beam axis, support triangles, UDL arrows."""
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 2))

        La      = self.span_left.L
        Lb      = self.span_right.L
        L_total = La + Lb
        tri_h   = 0.06 * L_total
        q_level = 0.30 * L_total

        ax.plot([0, L_total], [0, 0], color='black', lw=2.0, solid_capstyle='round')

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

        for xs in (0, La, L_total):
            ax.fill(
                [xs - tri_h * 0.55, xs + tri_h * 0.55, xs],
                [-tri_h, -tri_h, 0],
                color='#555555', zorder=3,
            )
            ax.text(xs, -tri_h * 1.55, f'{xs / 1000:.2f} m',
                    ha='center', va='top', fontsize=8, color='#555555')

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
            Pre-computed nonlinear hogging moment [N·mm] ≤ 0 (signed).
            When provided the internal ``solve()`` call is skipped.

        Convention: y-axis inverted so sagging (M > 0) appears below the
        beam axis and hogging (M < 0) appears above — structural standard.
        Interior support is at x = L_a.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 4))

        La        = self.span_left.L
        M_hog_el  = self.M_hog_elastic    # negative
        if M_hog_nl is None:
            M_hog_nl  = self.solve()       # negative

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
            # Interior support marker at x = L_a (right end of left span)
            ax.plot(La, M_hog / 1e6, marker='o', ms=6, color=color, zorder=5)

        for xs in (0, La, La + self.span_right.L):
            ax.axvline(xs, color='gray', lw=0.5, ls=':')
        ax.axhline(0, color='black', lw=0.8)

        ax.invert_yaxis()   # sagging (M>0) below axis, hogging (M<0) above axis
        ax.set_xlabel('$x$ [mm]', fontsize=11)
        ax.set_ylabel(r'$M$ [kN·m]  ($+$ sagging $\downarrow$, $-$ hogging $\uparrow$)', fontsize=11)
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
            Pre-computed nonlinear hogging moment [N·mm] ≤ 0 (signed).

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

        Both M_hog and M_hog,el are ≤ 0 (signed); their ratio is positive
        (≤ 1 means redistribution has occurred).
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(7, 5))
        La, Lb = self.span_left.L, self.span_right.L
        if q_arr is None:
            q_arr = np.linspace(1e-3 * self.q, 2.0 * self.q, 40)

        M_hog_arr = self.solve_over_load(q_arr)
        M_el_arr  = -q_arr * (La ** 3 + Lb ** 3) / (8.0 * (La + Lb))   # negative

        ax.plot(q_arr, M_hog_arr / M_el_arr, color=color, lw=2.0,
                label=r'$M_\mathrm{hog} / M_\mathrm{hog,el}$')
        ax.axhline(1.0, color='gray', lw=1.0, ls='--', label='elastic reference')
        ax.set_xlabel('$q$ [N/mm]', fontsize=11)
        ax.set_ylabel(r'$M_\mathrm{hog} / M_\mathrm{hog,el}$', fontsize=11)
        ax.set_title('Moment redistribution', fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, ls='--')
        return ax

    def plot_summary(self, title: str = '', M_hog_nl: Optional[float] = None) -> None:
        """3-panel summary: beam scheme | M diagram | deflection profile."""
        if M_hog_nl is None:
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
