"""
Moment-Curvature Analysis
=========================

Clean implementation using StressStrainProfile for force calculations.

Approach:
1. For each curvature κ, solve for ε_bot that gives N = 0
2. Compute corresponding moment M
3. Build M-κ relationship

Uses conventions from cs_design and cs_components modules.
"""

from typing import Literal, Optional, Tuple

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.optimize import brentq

from scite.core import BMCSModel, ui_field
from scite.cs_design.cross_section import CrossSection
from scite.cs_design.cs_stress_strain_profile import StressStrainProfile

# ── Failure-mode marker styles ──────────────────────────────────────────────
# Used by plot_mk(show_failure_marker=True) and add_failure_mode_legend().
_FAILURE_MODE_MARKERS: dict[str, tuple[str, int, str]] = {
    'concrete':      ('D', 12, 'Concrete crushing (η_c > η_f)'),
    'reinforcement': ('x', 14, 'CFRP/steel rupture (η_f > η_c)'),
    'balanced':      ('o', 12, 'Balanced / simultaneous'),
}
# Marker cycle for additional matrix regions in plot_mk(show_component_markers=True)
_REGION_MARKERS: tuple[str, ...] = ('s', '^', 'v', 'P', 'h')


class MKappaAnalysis(BMCSModel):
    """
    Moment-curvature relationship calculator.

    Given a cross-section, computes the M-κ curve by:
    1. Defining a range of curvatures based on material strain limits
    2. For each κ, solving for ε_bot that satisfies equilibrium (N = 0)
    3. Computing the corresponding moment M

    The analysis uses StressStrainProfile to compute forces at each state.

    Attributes:
        cs: CrossSection with geometry, concrete, and reinforcement
        n_kappa: Number of curvature points for analysis
        kappa_range: Computed range of curvatures [1/mm]
        kappa_values: Array of curvature values
        eps_bot_values: Corresponding bottom strains
        M_values: Corresponding moments [kN·m]
        N_values: Corresponding axial forces (should be ≈0) [kN]
    """

    cs: CrossSection

    N_Ed: float = ui_field(
        0.0,
        label=r"$N_{Ed}$",
        unit="kN",
        range=(-5000.0, 5000.0),
        description="Design axial force (positive = tension, negative = compression)",
    )

    n_kappa: int = ui_field(
        100,
        label=r"$n_\kappa$",
        unit="-",
        range=(10, 500),
        step=10,
        description="Number of curvature points",
        ge=10,
        le=500,
    )

    solve_mode: Literal['positive', 'negative', 'both'] = ui_field(
        'both',
        label="Solve mode",
        description=(
            "'positive' = positive-κ branch only (tension at bottom); "
            "'negative' = negative-κ branch only (tension at top); "
            "'both' = full positive + negative"
        ),
    )

    # Tolerance for equilibrium solver
    N_tol: float = ui_field(
        0.01,
        label=r"$N_{tol}$",
        unit="kN",
        range=(0.001, 1.0),
        description="Axial force tolerance for equilibrium",
    )

    non_descending: bool = ui_field(
        True,
        label="Non-descending M-κ",
        description=(
            "Apply running maximum/minimum to M_values after solve(), "
            "eliminating the post-cracking dip. Equivalent to ACK mean-stress "
            "tension stiffening: M never drops below the cracking moment."
        ),
    )

    # Solution arrays (computed) — positive-κ branch (tension at bottom)
    # kappa_values / M_values / eps_bot_values reflect the selected post-processing
    # step (raw when non_descending=False, crack-plateau+truncated when True).
    kappa_values: Optional[npt.NDArray[np.float64]] = None
    eps_bot_values: Optional[npt.NDArray[np.float64]] = None
    M_values: Optional[npt.NDArray[np.float64]] = None
    N_values: Optional[npt.NDArray[np.float64]] = None

    # Step 0 — raw solver output (always stored after solve())
    kappa_raw_values: Optional[npt.NDArray[np.float64]] = None
    M_raw_values: Optional[npt.NDArray[np.float64]] = None
    eps_bot_raw_values: Optional[npt.NDArray[np.float64]] = None

    # Step 1 — crack-plateau: max.accumulate up to peak, raw post-peak preserved
    M_plateau_values: Optional[npt.NDArray[np.float64]] = None

    # Negative-κ solution arrays (tension at top, computed in solve())
    kappa_neg_values: Optional[npt.NDArray[np.float64]] = None
    eps_bot_neg_values: Optional[npt.NDArray[np.float64]] = None
    M_neg_values: Optional[npt.NDArray[np.float64]] = None
    N_neg_values: Optional[npt.NDArray[np.float64]] = None

    # Step 0 / 1 — negative branch raw and plateau
    kappa_neg_raw_values: Optional[npt.NDArray[np.float64]] = None
    M_neg_raw_values: Optional[npt.NDArray[np.float64]] = None
    eps_bot_neg_raw_values: Optional[npt.NDArray[np.float64]] = None
    M_neg_plateau_values: Optional[npt.NDArray[np.float64]] = None

    # Cracking curvatures and moments (stored after solve(), computed analytically)
    kappa_cr_pos: Optional[float] = None
    kappa_cr_neg: Optional[float] = None
    M_cr_pos: Optional[float] = None   # cracking moment, positive branch [kN·m]
    M_cr_neg: Optional[float] = None   # cracking moment, negative branch [kN·m] (negative sign)

    def get_kappa_range(self) -> Tuple[float, float]:
        """
        Determine reasonable curvature range based on material limits.

        Strategy:
        1. Get maximum compressive strain from concrete (ε_cu)
        2. Get maximum tensile strain from steel (ε_su)
        3. Compute κ_max from these limits and cross-section height

        Returns:
            (kappa_min, kappa_max): Curvature range [1/mm]
        """
        # Height of the PRIMARY concrete: additional regions above it (fill,
        # top plate) must not shorten the sweep before the primary fails.
        h = self.cs.y_top_primary

        # Get material strain limits
        eps_cu = abs(self.cs.concrete.eps_cu2_computed)  # Ultimate compressive strain (negative)

        # Get maximum tensile strain from reinforcement
        eps_su = 0.010  # Default steel ultimate strain
        if self.cs.reinforcement.layers:
            # Get from first layer's material
            layer = self.cs.reinforcement.layers[0]
            if hasattr(layer.material, "eps_ud"):
                eps_su = layer.material.eps_ud
            elif hasattr(layer.material, "eps_u"):
                eps_su = layer.material.eps_u

        # Maximum curvature: full strain range over section height
        # When top concrete crushes and bottom steel yields
        kappa_max = (eps_cu + eps_su) / h

        # Start from small positive curvature (slightly above zero)
        kappa_min = kappa_max * 0.001

        return kappa_min, kappa_max

    def get_kappa_range_neg(self) -> Tuple[float, float]:
        """
        Determine curvature range for the negative-κ branch (tension at top).

        For negative κ the tensile fibre is at the *top*, so the kappa limit is
        governed by the top reinforcement layer's strain limit (eps_ud_top)
        combined with the concrete compressive limit at the bottom fibre.

            |κ_max_neg| = (eps_cu + eps_ud_top) / h

        Returns:
            (kappa_min, kappa_max): Magnitudes [1/mm], both positive.
                Caller uses them as  np.linspace(-kappa_min, -kappa_max, n).
        """
        h = self.cs.h_total
        eps_cu = abs(self.cs.concrete.eps_cu2_computed)

        eps_su_top = 0.010  # default
        if self.cs.reinforcement.layers:
            # Top reinforcement layer has the largest z coordinate
            top_layer = max(self.cs.reinforcement.layers, key=lambda lay: lay.z)
            if hasattr(top_layer.material, "eps_ud"):
                eps_su_top = top_layer.material.eps_ud
            elif hasattr(top_layer.material, "eps_u"):
                eps_su_top = top_layer.material.eps_u

        kappa_max_hog = (eps_cu + eps_su_top) / h
        kappa_min_hog = kappa_max_hog * 0.001
        return kappa_min_hog, kappa_max_hog

    def solve_equilibrium_at_kappa(self, kappa: float) -> Tuple[float, float, float, bool]:
        """
        Solve for ε_bot that gives N ≈ N_Ed at specified curvature.

        Uses Brent's method to find root of N(ε_bot) - N_Ed = 0.

        Args:
            kappa: Curvature [1/mm]

        Returns:
            (eps_bot, N, M, converged): Bottom strain, axial force [kN], moment [kN·m], convergence flag
        """
        profile = StressStrainProfile(self.cs)

        # Define function to find root of
        def residual(eps_bot: float) -> float:
            profile.set_state(kappa=kappa, eps_bot=eps_bot)
            F_c, F_s, N_total, M_total = profile.get_force_resultants()
            return (N_total / 1000.0) - self.N_Ed  # N_total - N_Ed = 0

        # Bound on the PRIMARY concrete's own top fibre; region fibres above it
        # may pass their own limits (their laws handle it, markers report it).
        h = self.cs.y_top_primary
        eps_cu = abs(self.cs.concrete.eps_cu2_computed)

        # Lower bound: compressed fiber at concrete failure strain.
        # For sagging (κ≥0): top fiber compressed → ε_top = -eps_cu
        #   ε_top = eps_bot - κ·h = -eps_cu  →  eps_bot_min = -eps_cu + κ·h
        # For hogging (κ<0): bottom fiber compressed → ε_bot = -eps_cu
        #   ε_bot = eps_bot = -eps_cu  →  eps_bot_min = -eps_cu
        if kappa >= 0:
            eps_bot_min = -eps_cu + kappa * h
        else:
            eps_bot_min = -eps_cu
        # For significant axial compression allow going somewhat below that limit
        if self.N_Ed < -100:
            eps_bot_min -= 0.005

        # Upper bound: for each layer, eps_bot must not push that layer past failure.
        # ε(z) = eps_bot - κ·z  →  eps_bot ≤ 0.99·eps_ud + κ·z
        # Take the MIN over all layers so the most-constraining layer wins.
        eps_bot_max = 0.100   # start high; reduced by layer constraints below
        for layer in self.cs.reinforcement.layers:
            eps_ud_layer = getattr(layer.material, 'eps_ud', 0.025)
            eps_bot_max = min(eps_bot_max, 0.99 * eps_ud_layer + kappa * layer.z)

        # Check if residual has opposite signs at bounds (required for brentq)
        r_min = residual(eps_bot_min)
        r_max = residual(eps_bot_max)

        if r_min * r_max > 0:
            # No sign change - no solution in range
            # Try to evaluate at a reasonable point and return with converged=False
            # Use the bound that gives smaller absolute residual
            eps_bot_trial = eps_bot_min if abs(r_min) < abs(r_max) else eps_bot_max
            profile.set_state(kappa=kappa, eps_bot=eps_bot_trial)
            F_c, F_s, N_total, M_total = profile.get_force_resultants()
            return float(eps_bot_trial), float(N_total / 1000.0), float(M_total / 1e6), False

        try:
            # Solve for zero axial force with full output
            eps_bot_sol, result_info = brentq(
                residual, eps_bot_min, eps_bot_max, xtol=1e-6, full_output=True
            )

            # Check convergence
            converged = result_info.converged

            # Compute final state
            profile.set_state(kappa=kappa, eps_bot=float(eps_bot_sol))
            F_c, F_s, N_total, M_total = profile.get_force_resultants()

            # Additional check: if residual is still large, mark as not converged
            N_kN = float(N_total / 1000.0)
            if abs(N_kN) > self.N_tol * 10:  # 10x tolerance threshold
                converged = False

            return float(eps_bot_sol), N_kN, float(M_total / 1e6), converged

        except ValueError as e:
            # Solver failed completely
            profile.set_state(kappa=kappa, eps_bot=0.0)
            F_c, F_s, N_total, M_total = profile.get_force_resultants()
            return 0.0, float(N_total / 1000.0), float(M_total / 1e6), False

    # ── Cracking curvature helpers ────────────────────────────────────────────

    def _modular_ratio(self) -> float:
        """Modular ratio n = E_s / E_c."""
        E_c = self.cs.concrete.E_ct_computed
        E_s = 200_000.0
        if self.cs.reinforcement.layers:
            mat = self.cs.reinforcement.layers[0].material
            if hasattr(mat, 'E_s'):
                E_s = float(mat.E_s)
        return E_s / E_c

    def _transformed_section_centroid(self) -> float:
        """Neutral-axis position y_c from bottom [mm] of the uncracked transformed section.

        Matrix regions enter with n_r = E_r / E_c (``CrossSection.transformed_properties``).
        """
        n = self._modular_ratio()
        A_c, S_c, _ = self.cs.transformed_properties()
        A_tr = sum((n - 1) * lay.A_s for lay in self.cs.reinforcement.layers)
        S_tr = sum((n - 1) * lay.A_s * lay.z for lay in self.cs.reinforcement.layers)
        return (S_c + S_tr) / (A_c + A_tr)

    def _transformed_section_I(self, y_c: float) -> float:
        """Second moment of area I_g [mm⁴] of the transformed section about y_c."""
        n = self._modular_ratio()
        A_c, S_c, I_0 = self.cs.transformed_properties()
        # I about y_c via expansion: ∫b(z)(z-y_c)² dz = I_0 - 2·y_c·S_c + y_c²·A_c
        I_c_yc = I_0 - 2.0 * y_c * S_c + y_c ** 2 * A_c
        I_tr = sum((n - 1) * lay.A_s * (y_c - lay.z) ** 2
                   for lay in self.cs.reinforcement.layers)
        return I_c_yc + I_tr

    def _kappa_cr(self, branch: str) -> Optional[float]:
        """Cracking curvature magnitude [1/mm] for 'positive' (tension at bottom) or 'negative' (tension at top).

        Returns None if the concrete model does not expose f_ctm / E_ct_computed.
        Returns 0.0 if N_Ed is so large that the section is already pre-cracked.
        """
        f_ctm = getattr(self.cs.concrete, 'f_ctm', None)
        E_c = getattr(self.cs.concrete, 'E_ct_computed', None)
        if f_ctm is None or E_c is None:
            return None

        A_g = self.cs.transformed_properties()[0]
        sig_N = self.N_Ed * 1000.0 / A_g   # kN → N → MPa
        f_ctm_eff = f_ctm - sig_N           # tension N_Ed reduces cracking resistance
        if f_ctm_eff <= 0.0:
            return 0.0                      # section pre-cracked under axial tension

        eps_cr_eff = f_ctm_eff / E_c
        y_c = self._transformed_section_centroid()

        if branch == 'positive':
            return eps_cr_eff / y_c                     # positive-κ: bottom fibre in tension
        else:
            return eps_cr_eff / (self.cs.h_total - y_c) # negative-κ: top fibre in tension

    def _M_cr_analytical(self, kappa_cr: float) -> float:
        """Cracking moment [kN·m] from elastic uncracked section: M_cr = E_c · I_g · κ_cr.

        This is model-agnostic: it uses the uncracked transformed section stiffness
        regardless of whether the concrete model includes a tensile branch.
        Compression-only models (EC2ParabolaRectangle) return near-zero M from the
        solver at κ_cr — the analytical formula is the correct value.
        """
        E_c = self.cs.concrete.E_ct_computed
        y_c = self._transformed_section_centroid()
        I_g = self._transformed_section_I(y_c)
        return E_c * I_g * kappa_cr / 1e6   # N/mm² · mm⁴ · 1/mm → N·mm → /1e6 → kN·m

    def _build_kappa_array(self, branch: str) -> np.ndarray:
        """Curvature sample points for one branch, with κ_cr pinned explicitly.

        When κ_cr is available:
          Returns n_kappa + 1 points: [κ_cr, …, κ_max].
          post[0] = κ_cr is injected analytically by solve(); the caller skips it
          (post[1:]) so the solver loop covers exactly n_kappa post-cracking steps.

        Falls back to linspace(κ_min, κ_max, n_kappa) if κ_cr is unavailable.
        """
        if branch == 'positive':
            kappa_min, kappa_max = self.get_kappa_range()
        else:
            kappa_min, kappa_max = self.get_kappa_range_neg()

        kappa_cr = self._kappa_cr(branch)

        if kappa_cr is None or kappa_cr <= 0.0 or kappa_cr >= kappa_max:
            return np.linspace(kappa_min, kappa_max, self.n_kappa)

        # n_kappa+1 points so caller can skip first (= kappa_cr, injected analytically)
        # and still iterate over exactly n_kappa post-cracking solver steps
        return np.linspace(kappa_cr, kappa_max, self.n_kappa + 1)

    def solve(self) -> None:
        """
        Compute the complete M-κ relationship under constant axial force N_Ed.

        For each curvature in the range, solves equilibrium (N = N_Ed) and stores results.
        Stops when equilibrium tolerance is violated (indicates section failure).
        """
        failure_threshold = 3
        tolerance_multiplier = 100.0

        # ── Positive-κ sweep (tension at bottom) ─────────────────────────────
        if self.solve_mode == 'negative':
            self.kappa_values = np.array([])
            self.eps_bot_values = np.array([])
            self.M_values = np.array([])
            self.N_values = np.array([])
        else:
            kappa_cr_pos = self._kappa_cr('positive')
            self.kappa_cr_pos = kappa_cr_pos if (kappa_cr_pos is not None and kappa_cr_pos > 0) else None
            self.M_cr_pos = (self._M_cr_analytical(kappa_cr_pos)
                             if self.kappa_cr_pos is not None else None)
            kappa_array = self._build_kappa_array('positive')

            # Inject origin (0, 0) analytically (solver is degenerate at κ=0)
            kappa_list: list = [0.0]
            eps_bot_list: list = [0.0]
            M_list: list = [0.0]
            N_list: list = [0.0]

            # Inject cracking point (κ_cr, M_cr) analytically — model-agnostic.
            # EC2ParabolaRectangle has no tensile concrete, so the solver would return
            # M ≈ 0 at κ_cr.  The analytical M_cr = E_c·I_g·κ_cr is always correct.
            if self.kappa_cr_pos is not None and self.M_cr_pos is not None:
                eps_cr = getattr(self.cs.concrete, 'eps_cr_computed',
                                 self.kappa_cr_pos * self._transformed_section_centroid())
                kappa_list.append(self.kappa_cr_pos)
                eps_bot_list.append(float(eps_cr))   # bottom fibre at cracking = ε_cr
                M_list.append(self.M_cr_pos)
                N_list.append(0.0)
                kappa_array = kappa_array[1:]        # kappa_cr already injected; skip it

            n_failed = 0
            M_max_so_far = 0.0
            M_peak_reached = False

            for i, kappa in enumerate(kappa_array):
                eps_bot, N, M, converged = self.solve_equilibrium_at_kappa(kappa)

                if abs(N) > self.N_tol * tolerance_multiplier:
                    n_failed += 1
                    if n_failed >= failure_threshold and M_peak_reached:
                        print(
                            f"Stopping at κ = {kappa*1000:.4f} ‰/mm (equilibrium lost, section failed)"
                        )
                        break
                    continue
                else:
                    n_failed = 0

                kappa_list.append(kappa)
                eps_bot_list.append(eps_bot)
                N_list.append(N)
                M_list.append(M)

                if M > M_max_so_far:
                    M_max_so_far = M
                    M_peak_reached = True

                if M_peak_reached and M < 0.2 * M_max_so_far:
                    print(f"Stopping at κ = {kappa*1000:.4f} ‰/mm (M dropped below 20% of peak)")
                    break

            kappa_arr   = np.array(kappa_list)
            eps_bot_arr = np.array(eps_bot_list)
            M_arr       = np.array(M_list)
            N_arr       = np.array(N_list)

            # Step 0 — raw: store verbatim solver output for inspection
            self.kappa_raw_values   = kappa_arr
            self.M_raw_values       = M_arr
            self.eps_bot_raw_values = eps_bot_arr

            # Step 1 — crack plateau: maximum.accumulate up to peak only,
            # then append the raw post-peak values unchanged.
            # This removes the post-crack dip without masking the softening branch.
            idx_peak = int(np.argmax(M_arr))
            M_asc = np.maximum.accumulate(M_arr[:idx_peak + 1])
            self.M_plateau_values = np.concatenate([M_asc, M_arr[idx_peak + 1:]])

            # Step 2 — non-descending: crack plateau + truncate at peak.
            # Gives a strictly monotone curve that can be cleanly inverted κ(M).
            if self.non_descending:
                self.kappa_values   = kappa_arr[:idx_peak + 1]
                self.eps_bot_values = eps_bot_arr[:idx_peak + 1]
                self.M_values       = M_asc
                self.N_values       = N_arr[:idx_peak + 1]
            else:
                self.kappa_values   = kappa_arr
                self.eps_bot_values = eps_bot_arr
                self.M_values       = M_arr
                self.N_values       = N_arr

        # ── Negative-κ sweep (tension at top) ────────────────────────────────
        if self.solve_mode == 'positive':
            self.kappa_neg_values = np.array([])
            self.eps_bot_neg_values = np.array([])
            self.M_neg_values = np.array([])
            self.N_neg_values = np.array([])
            return

        kappa_cr_neg = self._kappa_cr('negative')
        self.kappa_cr_neg = kappa_cr_neg if (kappa_cr_neg is not None and kappa_cr_neg > 0) else None
        self.M_cr_neg = (-self._M_cr_analytical(kappa_cr_neg)
                         if self.kappa_cr_neg is not None else None)
        kappa_neg_array = -self._build_kappa_array('negative')  # signed negative

        # Inject origin (0, 0) analytically
        kappa_neg_list: list = [0.0]
        eps_bot_neg_list: list = [0.0]
        M_neg_list: list = [0.0]
        N_neg_list: list = [0.0]

        # Inject cracking point (−κ_cr, M_cr_neg) analytically
        if self.kappa_cr_neg is not None and self.M_cr_neg is not None:
            eps_cr = getattr(self.cs.concrete, 'eps_cr_computed',
                             self.kappa_cr_neg * (self.cs.h_total
                                                  - self._transformed_section_centroid()))
            # For negative κ: top fibre cracks → ε_bot = ε_cr − κ_cr_neg·h (negative, compression)
            eps_bot_cr_neg = float(eps_cr) - self.kappa_cr_neg * self.cs.h_total
            kappa_neg_list.append(-self.kappa_cr_neg)
            eps_bot_neg_list.append(eps_bot_cr_neg)
            M_neg_list.append(self.M_cr_neg)
            N_neg_list.append(0.0)
            kappa_neg_array = kappa_neg_array[1:]   # kappa_cr already injected; skip it

        n_failed_neg = 0
        M_min_so_far = 0.0   # tracks most-negative peak moment
        M_peak_neg_reached = False

        for kappa in kappa_neg_array:
            eps_bot, N, M, converged = self.solve_equilibrium_at_kappa(kappa)

            if abs(N) > self.N_tol * tolerance_multiplier:
                n_failed_neg += 1
                if n_failed_neg >= failure_threshold and M_peak_neg_reached:
                    print(
                        f"Stopping negative-κ sweep at κ = {kappa*1000:.4f} ‰/mm "
                        f"(equilibrium lost, section failed)"
                    )
                    break
                continue
            else:
                n_failed_neg = 0

            kappa_neg_list.append(kappa)
            eps_bot_neg_list.append(eps_bot)
            N_neg_list.append(N)
            M_neg_list.append(M)

            # Track most-negative peak
            if M < M_min_so_far:
                M_min_so_far = M
                M_peak_neg_reached = True

            # Stop if moment has recovered past 20 % of negative peak
            if M_peak_neg_reached and M > 0.2 * M_min_so_far:
                print(
                    f"Stopping negative-κ sweep at κ = {kappa*1000:.4f} ‰/mm "
                    f"(M recovered past 20 % of negative-κ peak)"
                )
                break

        kappa_neg_arr   = np.array(kappa_neg_list)
        eps_bot_neg_arr = np.array(eps_bot_neg_list)
        M_neg_arr       = np.array(M_neg_list)
        N_neg_arr       = np.array(N_neg_list)

        # Step 0 — raw
        self.kappa_neg_raw_values   = kappa_neg_arr
        self.M_neg_raw_values       = M_neg_arr
        self.eps_bot_neg_raw_values = eps_bot_neg_arr

        # Step 1 — crack plateau (minimum.accumulate for negative branch)
        idx_peak_neg = int(np.argmin(M_neg_arr))
        M_neg_asc = np.minimum.accumulate(M_neg_arr[:idx_peak_neg + 1])
        self.M_neg_plateau_values = np.concatenate([M_neg_asc, M_neg_arr[idx_peak_neg + 1:]])

        # Step 2 — non-descending: crack plateau + truncate at peak
        if self.non_descending:
            self.kappa_neg_values   = kappa_neg_arr[:idx_peak_neg + 1]
            self.eps_bot_neg_values = eps_bot_neg_arr[:idx_peak_neg + 1]
            self.M_neg_values       = M_neg_asc
            self.N_neg_values       = N_neg_arr[:idx_peak_neg + 1]
        else:
            self.kappa_neg_values   = kappa_neg_arr
            self.eps_bot_neg_values = eps_bot_neg_arr
            self.M_neg_values       = M_neg_arr
            self.N_neg_values       = N_neg_arr

    @property
    def xd_pos(self) -> float:
        """x/d at the peak positive-κ moment — from actual M-κ strain state."""
        if self.M_values is None or len(self.M_values) == 0:
            raise RuntimeError("MKappaAnalysis not solved yet — call .solve() first.")
        idx = int(np.argmax(self.M_values))
        p = StressStrainProfile(self.cs, kappa=float(self.kappa_values[idx]),
                                eps_bottom=float(self.eps_bot_values[idx]))
        _, _, xd = p.xd
        return xd

    @property
    def xd_neg(self) -> float:
        """x/d at the peak negative-κ moment — from actual M-κ strain state.

        Requires solve_mode='both'.
        """
        if self.kappa_neg_values is None or len(self.kappa_neg_values) == 0:
            raise ValueError("Negative-κ branch not solved — use solve_mode='both'.")
        idx = int(np.argmin(self.M_neg_values))
        p = StressStrainProfile(self.cs, kappa=float(self.kappa_neg_values[idx]),
                                eps_bottom=float(self.eps_bot_neg_values[idx]))
        _, _, xd = p.xd
        return xd

    # ── M-κ interpolation helpers ─────────────────────────────────────────────

    @staticmethod
    def _ascending_envelope(
        kappa_abs: np.ndarray, M_abs: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Keep only points where |M| is strictly ascending.

        Removes the cracking-dip instability and post-peak softening so the
        resulting table is suitable for monotone np.interp in both directions
        (M→κ inversion and κ→M forward map), regardless of n_kappa.
        """
        mask = np.zeros(len(M_abs), dtype=bool)
        M_max = -np.inf
        for i, m in enumerate(M_abs):
            if m > M_max:
                M_max = m
                mask[i] = True
        return kappa_abs[mask], M_abs[mask]

    def kappa_from_M(self, M_arr: np.ndarray) -> np.ndarray:
        """Invert M-κ: M [N·mm] → κ [1/mm], signed (+ positive branch, – negative branch).

        Uses the strictly ascending envelope of each branch so the result is
        unique and n_kappa-independent (the cracking dip is bridged).
        Moments are clipped to the respective branch capacity.

        Respects solve_mode: if only one branch was solved, the other falls
        back to a symmetric mirror or returns zero.
        """
        M_arr = np.asarray(M_arr, dtype=float)
        M_abs = np.abs(M_arr)

        # ── Positive-κ branch ────────────────────────────────────────────────
        has_pos = self.kappa_values is not None and len(self.kappa_values) > 0
        if has_pos:
            k_env, M_env = self._ascending_envelope(
                self.kappa_values, self.M_values * 1e6
            )
            k_env = np.concatenate([[0.0], k_env])
            M_env = np.concatenate([[0.0], M_env])
            kappa_sag = np.interp(np.clip(M_abs, 0.0, M_env[-1]), M_env, k_env)
        else:
            kappa_sag = np.zeros_like(M_abs)

        # ── Negative-κ branch ────────────────────────────────────────────────
        has_neg = self.kappa_neg_values is not None and len(self.kappa_neg_values) > 0
        if has_neg:
            k_env, M_env = self._ascending_envelope(
                np.abs(self.kappa_neg_values), np.abs(self.M_neg_values) * 1e6
            )
            k_env = np.concatenate([[0.0], k_env])
            M_env = np.concatenate([[0.0], M_env])
            kappa_neg = np.interp(np.clip(M_abs, 0.0, M_env[-1]), M_env, k_env)
        elif has_pos:
            kappa_neg = kappa_sag   # symmetric fallback
        else:
            kappa_neg = np.zeros_like(M_abs)

        return np.where(M_arr >= 0.0, kappa_sag, -kappa_neg)

    def M_from_kappa(self, kappa_arr: np.ndarray) -> np.ndarray:
        """Forward map κ [1/mm] → M [N·mm], signed (+ positive-κ branch, – negative-κ branch).

        Uses the ascending-κ segment up to the peak for each branch, with the
        origin prepended.  This is the centralised version of ``_forward_map``
        in ContinuousBeamAnalysis.
        """
        kappa_arr = np.asarray(kappa_arr, dtype=float)
        kappa_abs = np.abs(kappa_arr)

        # Positive-κ branch
        has_pos = self.kappa_values is not None and len(self.kappa_values) > 0
        if has_pos:
            idx_pk = int(np.argmax(self.M_values))
            k_pos = np.concatenate([[0.0], self.kappa_values[:idx_pk + 1]])
            M_pos = np.concatenate([[0.0], self.M_values[:idx_pk + 1] * 1e6])
            M_pos_interp = np.interp(np.clip(kappa_abs, 0.0, k_pos[-1]), k_pos, M_pos)
        else:
            M_pos_interp = np.zeros_like(kappa_abs)

        # Negative-κ branch
        has_neg = self.kappa_neg_values is not None and len(self.kappa_neg_values) > 0
        if has_neg:
            idx_pk = int(np.argmin(self.M_neg_values))
            k_neg = np.concatenate([[0.0], np.abs(self.kappa_neg_values[:idx_pk + 1])])
            M_neg = np.concatenate([[0.0], np.abs(self.M_neg_values[:idx_pk + 1]) * 1e6])
            M_neg_interp = np.interp(np.clip(kappa_abs, 0.0, k_neg[-1]), k_neg, M_neg)
        elif has_pos:
            M_neg_interp = M_pos_interp   # symmetric fallback
        else:
            M_neg_interp = np.zeros_like(kappa_abs)

        return np.where(kappa_arr >= 0.0, M_pos_interp, -M_neg_interp)

    def plot_kappa_from_M(
        self,
        ax: Optional[plt.Axes] = None,
        color: str = '#1f77b4',
        linewidth: float = 2.0,
        label_suffix: str = '',
    ) -> plt.Axes:
        """Plot the inverted κ(M) curve using the strictly ascending envelope.

        Useful for verifying that the inversion is smooth and monotone after
        removing the cracking dip.  Positive-κ (M > 0, κ > 0) is solid; negative-κ
        (M < 0, κ < 0) is dashed.  Both branches share one colour so the call
        can be looped with MKappaModes.iter_modes().
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(8, 5))

        has_pos = self.kappa_values is not None and len(self.kappa_values) > 0
        has_neg = self.kappa_neg_values is not None and len(self.kappa_neg_values) > 0

        if has_pos:
            k_env, M_env = self._ascending_envelope(
                self.kappa_values * 1e3,    # ‰/mm
                self.M_values,              # kN·m
            )
            k_env = np.concatenate([[0.0], k_env])
            M_env = np.concatenate([[0.0], M_env])
            ax.plot(M_env, k_env, color=color, lw=linewidth,
                    label=f'pos{label_suffix}')

        if has_neg:
            k_env, M_env = self._ascending_envelope(
                np.abs(self.kappa_neg_values) * 1e3,
                np.abs(self.M_neg_values),
            )
            k_env = np.concatenate([[0.0], k_env])
            M_env = np.concatenate([[0.0], M_env])
            ax.plot(-M_env, -k_env, color=color, lw=linewidth, ls='--',
                    label=f'neg{label_suffix}')

        ax.axhline(0, color='k', lw=0.5)
        ax.axvline(0, color='k', lw=0.5)
        ax.set_xlabel('Moment $M$  [kN·m]', fontsize=11)
        ax.set_ylabel('Curvature $\\kappa$  [‰/mm]', fontsize=11)
        ax.set_title('Inverted M-κ: κ(M) — ascending envelope',
                     fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, ls='--')
        ax.legend()
        return ax

    def get_failure_mode(self) -> dict:
        """
        Identify the governing failure mode at the peak moment.

        Compares strain utilisation for each material at the M-peak state:

            eta_c = |eps_top| / |eps_cu|      (concrete compression fibre)
            eta_f = eps_bot  /  eps_ud        (main reinforcement tensile fibre)

        The material whose strain is closer to its limit at M-peak is the
        governing component. This criterion is independent of the constitutive
        law shape and remains valid for EC2 parabola-rectangle, nonlinear, and
        bilinear models.

        Returns:
            dict with keys:
              'mode'    : 'concrete' | 'reinforcement' | 'balanced'
              'eta_c'   : concrete strain utilisation (0 … 1+)
              'eta_f'   : reinforcement strain utilisation (0 … 1+)
              'eps_top' : top-fibre strain at M-peak [–]  (negative = compression)
              'eps_bot' : bottom-fibre strain at M-peak [–]
        """
        if self.M_values is None or len(self.M_values) == 0:
            return {'mode': 'unknown', 'eta_c': float('nan'), 'eta_f': float('nan'),
                    'eps_top': float('nan'), 'eps_bot': float('nan')}

        eps_cu = abs(self.cs.concrete.eps_cu2_computed)

        # eps_ud: ultimate tensile strain — works for both steel (eps_ud) and
        # CFRP (eps_cr alias eps_ud) via the common property interface.
        main_layer = self.cs.reinforcement.layers[0]
        eps_ud = getattr(main_layer.material, 'eps_ud', None)
        if eps_ud is None:
            eps_ud = getattr(main_layer.material, 'eps_cr', 0.025)

        # Identify the failure onset index: last point before either material
        # limit is first crossed.  Using the last sub-limit point avoids the
        # artefact where the post-peak softening tail (CFRP) or the argmax
        # heuristic pushes η above 1 due to solver step size.
        kappas  = self.kappa_values
        eps_bots = self.eps_bot_values
        # top fibre of the PRIMARY concrete (regions report via get_component_limits)
        eps_tops = eps_bots - kappas * self.cs.y_top_primary  # negative = compression

        within = (eps_bots <= eps_ud) & (np.abs(eps_tops) <= eps_cu)
        if within.any():
            idx = int(np.where(within)[0][-1])
        else:
            # All points past both limits (very coarse κ grid): fall back to argmax
            idx = int(np.argmax(self.M_values))

        kappa   = kappas[idx]
        eps_bot = eps_bots[idx]
        eps_top = eps_tops[idx]

        eta_c = abs(eps_top) / eps_cu  if eps_cu  > 0 else float('nan')
        eta_f = eps_bot       / eps_ud if eps_ud  > 0 else float('nan')

        tol = 0.05  # within 5 % → "balanced"
        if abs(eta_c - eta_f) < tol:
            mode = 'balanced'
        elif eta_c > eta_f:
            mode = 'concrete'
        else:
            mode = 'reinforcement'

        return {
            'mode'   : mode,
            'eta_c'  : float(eta_c),
            'eta_f'  : float(eta_f),
            'eps_top': float(eps_top),
            'eps_bot': float(eps_bot),
        }

    def get_component_limits(self) -> list[dict]:
        """Limit-strain crossings of every component on the positive-κ branch.

        Each component — primary concrete, every matrix region (grouped by
        label) and every reinforcement layer — has its own limit strain at its
        critical fibre.  The sweep continues past a secondary component's limit
        (its law softens / drops); this method reports where each limit is
        first reached along the raw solver path.

        Critical fibres (sagging): compression at the component's top fibre
        (concrete: ``eps_cu2_computed``; steel: −eps_ud), tension at its bottom
        fibre (materials with ``eps_ud``), reinforcement at the layer.

        Returns:
            list of dicts, sorted with the reached limits first (by κ):
              'label', 'kind' ('compression' | 'tension'), 'y' [mm], 'eps_lim',
              'reached' (bool), 'kappa_lim' [1/mm] (NaN if not reached),
              'M_lim' [kN·m] (on the raw path), 'eta_peak' (|ε|/|ε_lim| at M-peak).
            The first reached entry is the governing component.
        """
        kap, eb, M_raw = self.kappa_raw_values, self.eps_bot_raw_values, self.M_raw_values
        if kap is None or len(kap) < 2:
            return []
        i_pk = int(np.argmax(M_raw))

        checks = [('concrete', 'compression', self.cs.y_top_primary,
                   float(self.cs.concrete.eps_cu2_computed))]
        seen = set()
        for reg in self.cs.regions:
            if reg.label in seen:
                continue
            seen.add(reg.label)
            group = [r for r in self.cs.regions if r.label == reg.label]
            mat = reg.material
            y_top = max(r.y_top for r in group)
            y_bot = min(r.y_bot for r in group)
            eps_ud = getattr(mat, 'eps_ud', None)
            eps_cu = getattr(mat, 'eps_cu2_computed', None)
            if eps_cu is None and eps_ud is not None:
                eps_cu = -eps_ud
            if eps_cu is not None:
                checks.append((reg.label, 'compression', y_top, float(eps_cu)))
            if eps_ud is not None:
                checks.append((reg.label, 'tension', y_bot, float(eps_ud)))
        layers = self.cs.reinforcement.layers
        for i, lay in enumerate(layers):
            eps_ud = getattr(lay.material, 'eps_ud', None)
            if eps_ud is None:
                eps_ud = getattr(lay.material, 'eps_cr', 0.025)
            label = lay.name or ('reinforcement' if len(layers) == 1 else f'reinforcement {i + 1}')
            checks.append((label, 'tension', float(lay.z), float(eps_ud)))

        # The sweep ends when equilibrium is lost — typically because the next
        # κ step would push the primary concrete past the solver bound.  A limit
        # crossed within that one extrapolated step therefore counts as reached
        # at the end of the path.
        kap_x = np.append(kap, 2 * kap[-1] - kap[-2])
        M_x = np.append(M_raw, M_raw[-1])
        out = []
        for label, kind, y, lim in checks:
            eps = eb - kap * y
            eps_x = np.append(eps, 2 * eps[-1] - eps[-2])
            hit = eps_x <= lim if kind == 'compression' else eps_x >= lim
            reached = bool(hit.any())
            kappa_lim = M_lim = float('nan')
            if reached:
                j = int(np.argmax(hit))
                if j == 0:
                    kappa_lim, M_lim = float(kap_x[0]), float(M_x[0])
                elif M_x[j] < 0.9 * M_x[j - 1]:
                    # cliff (the component's law drops within the step): the limit
                    # is the last state before the drop
                    kappa_lim, M_lim = float(kap_x[j - 1]), float(M_x[j - 1])
                else:
                    t = (lim - eps_x[j - 1]) / (eps_x[j] - eps_x[j - 1])
                    kappa_lim = float(kap_x[j - 1] + t * (kap_x[j] - kap_x[j - 1]))
                    M_lim = float(M_x[j - 1] + t * (M_x[j] - M_x[j - 1]))
            out.append(dict(label=label, kind=kind, y=float(y), eps_lim=lim, reached=reached,
                            kappa_lim=kappa_lim, M_lim=M_lim,
                            eta_peak=float(abs(eps[i_pk]) / abs(lim)) if lim else float('nan')))
        out.sort(key=lambda d: (not d['reached'], d['kappa_lim'] if d['reached'] else 0.0))
        return out

    def plot_mk(
        self,
        ax: Optional[plt.Axes] = None,
        show_grid: bool = True,
        color: str = "#1f77b4",
        linewidth: float = 2.0,
        label: str = "M-κ",
        show_failure_marker: bool = False,
        show_full_range: bool = False,
        show_cracking_marker: bool = False,
        show_component_markers: bool = False,
    ) -> plt.Axes:
        """
        Plot moment-curvature relationship.

        Args:
            ax: Matplotlib axes (creates new if None)
            show_grid: Whether to show grid
            color: Line color
            linewidth: Line width
            label: Legend label for this curve
            show_failure_marker: If True, place a ◆/×/○ marker at the peak
                point indicating the governing failure mode (concrete crushing,
                reinforcement rupture, or balanced).  Use
                ``add_failure_mode_legend(ax)`` afterwards to add the three
                marker legend entries to the axes.
            show_full_range: If True, also plot the negative-κ branch alongside
                the positive-κ branch.  The two branches are drawn with the
                same color and linewidth; only the positive-κ branch carries
                the legend label.
            show_component_markers: If True, mark where each component
                (concrete, regions, reinforcement) first reaches its limit
                strain — one labelled marker per component within the plotted
                κ-range (see ``get_component_limits``).

        Returns:
            Matplotlib axes with plot
        """
        if self.M_values is None:
            raise ValueError("No solution available. Call solve() first.")

        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        # Convert curvature to ‰/mm for display
        kappa_permille_mm = self.kappa_values * 1000.0

        ax.plot(kappa_permille_mm, self.M_values, color=color, linewidth=linewidth, label=label)

        # Negative-κ branch
        if show_full_range and self.kappa_neg_values is not None and len(self.kappa_neg_values) > 0:
            kappa_neg_mm = self.kappa_neg_values * 1000.0
            ax.plot(kappa_neg_mm, self.M_neg_values, color=color, linewidth=linewidth)

        if show_failure_marker:
            self._add_failure_marker(ax, color=color)
            if show_full_range and self.kappa_neg_values is not None and len(self.kappa_neg_values) > 0:
                self._add_failure_marker_neg(ax, color=color)

        if show_component_markers:
            self._add_component_markers(ax, color=color)

        if show_cracking_marker:
            # Use analytically computed M_cr (= E_c·I_g·κ_cr), not solver interpolation.
            # Solver gives near-zero M for compression-only models (EC2ParabolaRectangle)
            # because they carry no tensile concrete — the elastic formula is always correct.
            if self.kappa_cr_pos is not None and self.M_cr_pos is not None:
                ax.axvline(self.kappa_cr_pos * 1e3, color=color, lw=0.8, ls=':', alpha=0.6)
                ax.plot(self.kappa_cr_pos * 1e3, self.M_cr_pos, 'o', color=color,
                        markersize=6, markerfacecolor='white', markeredgewidth=1.5, zorder=4)
            if show_full_range and self.kappa_cr_neg is not None and self.M_cr_neg is not None:
                ax.axvline(-self.kappa_cr_neg * 1e3, color=color, lw=0.8, ls=':', alpha=0.6)
                ax.plot(-self.kappa_cr_neg * 1e3, self.M_cr_neg, 'o', color=color,
                        markersize=6, markerfacecolor='white', markeredgewidth=1.5, zorder=4)

        ax.set_xlabel("Curvature [1/m]", fontsize=12)
        ax.set_ylabel("Moment M [kN·m]", fontsize=12)
        ax.set_title("Moment-Curvature Relationship", fontsize=14, fontweight="bold")

        if show_grid:
            ax.grid(True, alpha=0.3, linestyle="--")

        ax.legend(fontsize=11)

        return ax

    def _add_failure_marker(
        self,
        ax: plt.Axes,
        color: str = "#1f77b4",
    ) -> None:
        """Place a ◆/×/○ failure-mode marker at the peak point on *ax*.

        The marker style is determined by ``get_failure_mode()``.  This method
        is called automatically when ``plot_mk(show_failure_marker=True)`` is
        used, or can be invoked directly for fine-grained control.
        """
        fm = self.get_failure_mode()
        idx_pk = int(np.argmax(self.M_values))
        mstyle, msize, _ = _FAILURE_MODE_MARKERS[fm['mode']]
        ax.plot(
            self.kappa_values[idx_pk] * 1000.0,
            self.M_values[idx_pk],
            marker=mstyle,
            markersize=msize,
            color=color,
            markeredgewidth=2.0,
            markerfacecolor='white',
            linestyle='none',
            zorder=5,
        )

    def _add_component_markers(self, ax: plt.Axes, color: str = "#1f77b4") -> None:
        """One labelled marker per component limit reached on the positive branch.

        Limits beyond the plotted (non-descending, peak-truncated) curve sit on
        the raw post-peak path, which is drawn as a thin dashed continuation.
        """
        if self.kappa_values is None or len(self.kappa_values) == 0:
            return
        k_end = float(self.kappa_values[-1])
        kap_raw, M_raw = self.kappa_raw_values, self.M_raw_values
        if kap_raw is not None and len(kap_raw) and float(kap_raw[-1]) > k_end:
            tail = kap_raw >= k_end
            ax.plot(kap_raw[tail] * 1000.0, M_raw[tail], color=color, lw=1.0, ls='--',
                    alpha=0.7, zorder=2)
        region_styles = iter(_REGION_MARKERS * 3)
        for lim in self.get_component_limits():
            if not lim['reached']:
                continue
            if lim['label'] == 'concrete':
                mstyle = _FAILURE_MODE_MARKERS['concrete'][0]
            elif lim['label'].startswith('reinforcement'):
                mstyle = _FAILURE_MODE_MARKERS['reinforcement'][0]
            else:
                mstyle = next(region_styles)
            k = lim['kappa_lim']
            if k <= k_end:
                M = float(np.interp(k, self.kappa_values, self.M_values))
            elif kap_raw is not None and k <= float(kap_raw[-1]):
                M = lim['M_lim']
            else:                      # within the extrapolated last step → path end
                k, M = float(kap_raw[-1]), float(M_raw[-1])
            ax.plot(k * 1000.0, M, marker=mstyle, markersize=10, color=color,
                    markeredgewidth=2.0, markerfacecolor='white', linestyle='none', zorder=5,
                    label=f"{lim['label']} limit ({lim['kind']})")

    def _add_failure_marker_neg(
        self,
        ax: plt.Axes,
        color: str = "#1f77b4",
    ) -> None:
        """Place a failure-mode marker at the peak of the negative-κ branch.

        For negative κ the bottom fibre is in compression (concrete governs) and the
        top fibre is in tension (top reinforcement governs).  The utilisation
        ratios are therefore:
            η_c = |ε_bot| / ε_cu   (concrete at bottom compression fibre)
            η_f = ε_top / ε_ud_top  (top reinforcement at tension fibre)
        """
        if self.kappa_neg_values is None or len(self.kappa_neg_values) == 0:
            return

        idx_pk    = int(np.argmin(self.M_neg_values))
        kappa_pk  = self.kappa_neg_values[idx_pk]       # negative [1/mm]
        eps_bot_pk = self.eps_bot_neg_values[idx_pk]    # bottom (compression at negative κ)
        eps_top_pk = eps_bot_pk - kappa_pk * self.cs.h_total  # top (tension at negative κ)

        eps_cu = abs(self.cs.concrete.eps_cu2_computed)
        if self.cs.reinforcement.layers:
            top_layer = max(self.cs.reinforcement.layers, key=lambda lay: lay.z)
            eps_ud_top = getattr(top_layer.material, 'eps_ud', None)
            if eps_ud_top is None:
                eps_ud_top = getattr(top_layer.material, 'eps_cr', 0.025)
        else:
            eps_ud_top = 0.025

        eta_c = abs(eps_bot_pk) / eps_cu    if eps_cu    > 0 else float('nan')
        eta_f = eps_top_pk      / eps_ud_top if eps_ud_top > 0 else float('nan')

        tol = 0.05
        if abs(eta_c - eta_f) < tol:
            mode = 'balanced'
        elif eta_c > eta_f:
            mode = 'concrete'
        else:
            mode = 'reinforcement'

        mstyle, msize, _ = _FAILURE_MODE_MARKERS[mode]
        ax.plot(
            kappa_pk * 1000.0,
            self.M_neg_values[idx_pk],
            marker=mstyle,
            markersize=msize,
            color=color,
            markeredgewidth=2.0,
            markerfacecolor='white',
            linestyle='none',
            zorder=5,
        )

    @staticmethod
    def add_failure_mode_legend(
        ax: plt.Axes,
        fontsize: int = 9,
        **legend_kwargs,
    ) -> None:
        """Append the three failure-mode marker entries to the axes legend.

        Call this once after all ``plot_mk(show_failure_marker=True)`` calls
        to add ◆/×/○ legend entries without duplicating them per curve.

        Example::

            for b_f, color in zip(b_f_values, colors):
                mk.plot_mk(ax=ax, color=color, show_failure_marker=True, label=...)
            MKappaAnalysis.add_failure_mode_legend(ax)
        """
        handles, labels = ax.get_legend_handles_labels()
        for mode, (mstyle, msize, mlabel) in _FAILURE_MODE_MARKERS.items():
            handles.append(
                mlines.Line2D(
                    [], [],
                    marker=mstyle, linestyle='none', color='#555555',
                    markersize=msize, markeredgewidth=2.0, markerfacecolor='white',
                    label=mlabel,
                )
            )
            labels.append(mlabel)
        ax.legend(handles=handles, labels=labels, fontsize=fontsize, **legend_kwargs)

    def plot_state_at_kappa(
        self,
        kappa: float,
        ax_strain: Optional[plt.Axes] = None,
        ax_stress: Optional[plt.Axes] = None,
        show_resultants: bool = True,
    ) -> Tuple[plt.Axes, plt.Axes]:
        """
        Plot strain and stress profiles at a specific curvature.

        Args:
            kappa: Curvature value [1/mm]
            ax_strain: Axes for strain plot
            ax_stress: Axes for stress plot
            show_resultants: Whether to show force arrows

        Returns:
            (ax_strain, ax_stress): Tuple of axes
        """
        if self.kappa_values is None:
            raise ValueError("No solution available. Call solve() first.")

        # Find closest kappa in solution
        idx = np.argmin(np.abs(self.kappa_values - kappa))
        kappa_actual = self.kappa_values[idx]
        eps_bot = self.eps_bot_values[idx]

        # Create profile and plot
        profile = StressStrainProfile(self.cs, kappa=kappa_actual, eps_bottom=eps_bot)

        # Ensure axes are created if not provided
        if ax_strain is None or ax_stress is None:
            fig, (ax_strain_created, ax_stress_created) = plt.subplots(1, 2, figsize=(14, 8))
            ax_strain = ax_strain_created
            ax_stress = ax_stress_created
            # Add title with curvature info
            M = self.M_values[idx]
            fig.suptitle(
                f"State at κ = {kappa_actual*1000:.3f} ‰/mm, M = {M:.2f} kN·m",
                fontsize=14,
                fontweight="bold",
            )

        profile.plot_stress_strain_profile(ax_strain, ax_stress, show_resultants)

        return ax_strain, ax_stress

    def plot_summary(
        self,
        title: str = "",
        figsize: Tuple[float, float] = (16, 8),
    ) -> plt.Figure:
        """
        4-panel summary figure: cross-section | M-κ curve | strain profile | stress profile.

        All panels are drawn by delegating to the existing model-level plot methods
        (``cs.plot_cross_section``, ``plot_mk``, ``plot_state_at_kappa``).

        Args:
            title: Figure suptitle (defaults to class name + key parameters).
            figsize: Figure size in inches.

        Returns:
            The matplotlib Figure.
        """
        import matplotlib.gridspec as gridspec

        if self.M_values is None or len(self.M_values) == 0:
            raise ValueError("No solution available. Call solve() first.")

        idx_peak = int(np.argmax(self.M_values))
        kappa_peak = self.kappa_values[idx_peak]

        fig = plt.figure(figsize=figsize, layout="constrained")
        fig.suptitle(
            title or f"M-κ Summary  (M_peak = {self.M_values[idx_peak]:.1f} kN·m)",
            fontsize=13,
            fontweight="bold",
        )
        gs = gridspec.GridSpec(1, 4, figure=fig)

        self.cs.plot_cross_section(ax=fig.add_subplot(gs[0]))
        self.plot_mk(ax=fig.add_subplot(gs[1]))
        self.plot_state_at_kappa(
            kappa_peak,
            ax_strain=fig.add_subplot(gs[2]),
            ax_stress=fig.add_subplot(gs[3]),
        )

        # Render exactly once in any environment:
        # - IPython/Jupyter: display() shows it, plt.close() stops flush_figures()
        #   from rendering it a second time, and returning None suppresses _repr_png_()
        # - Script / non-IPython: fall back to returning the figure for the caller
        try:
            from IPython.display import display as ipy_display
            ipy_display(fig)
            plt.close(fig)
            return None
        except ImportError:
            return fig


def create_default_mkappa(N_Ed: float = 0.0) -> MKappaAnalysis:
    """
    Create a default MKappa analysis for testing.

    Args:
        N_Ed: Design axial force [kN] (default: 0.0 = pure bending)

    Returns:
        MKappaAnalysis with rectangular section and standard reinforcement
    """
    from scite.cs_design.reinforcement import (ReinforcementLayer,
                                               ReinforcementLayout)
    from scite.cs_design.shapes import RectangularShape
    from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
    from scite.matmod.steel_reinforcement import SteelReinforcement

    # Create rectangular section 300x500 mm
    shape = RectangularShape(b=300.0, h=500.0)

    # C30/37 concrete (design values)
    concrete = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=0.85, gamma_c=1.5)

    # Steel reinforcement: 4Ø20 at bottom (z=50mm), 2Ø16 at top (z=450mm)
    steel_mat = SteelReinforcement(f_yk=500.0)

    layer_bottom = ReinforcementLayer(z=50.0, A_s=1256.6, material=steel_mat)  # 4Ø20 = 4×π×10²

    layer_top = ReinforcementLayer(z=450.0, A_s=402.1, material=steel_mat)  # 2Ø16 = 2×π×8²

    reinforcement = ReinforcementLayout(layers=[layer_bottom, layer_top])

    # Assemble cross-section
    cs = CrossSection(shape=shape, concrete=concrete, reinforcement=reinforcement)

    # Create analysis
    return MKappaAnalysis(cs=cs, n_kappa=100, N_Ed=N_Ed)
