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

from typing import Optional, Tuple

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

    # Tolerance for equilibrium solver
    N_tol: float = ui_field(
        0.01,
        label=r"$N_{tol}$",
        unit="kN",
        range=(0.001, 1.0),
        description="Axial force tolerance for equilibrium",
    )

    # Solution arrays (computed)
    kappa_values: Optional[npt.NDArray[np.float64]] = None
    eps_bot_values: Optional[npt.NDArray[np.float64]] = None
    M_values: Optional[npt.NDArray[np.float64]] = None
    N_values: Optional[npt.NDArray[np.float64]] = None

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
        h = self.cs.h_total

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

        h = self.cs.h_total
        eps_cu = abs(self.cs.concrete.eps_cu2_computed)

        # Lower bound: top fiber at concrete failure strain (NA at top of section).
        # ε_top = eps_bot - κ·h = -eps_cu  →  eps_bot = -eps_cu + κ·h
        #
        # Using a fixed -0.020 is wrong: for small κ it lands the entire section
        # past concrete failure AND past FRP compression limit → Fc=Fs=0 → N=0
        # trivially (degenerate root).  brentq picks it immediately, giving M≡0.
        eps_bot_min = -eps_cu + kappa * h
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

    def solve(self) -> None:
        """
        Compute the complete M-κ relationship under constant axial force N_Ed.

        For each curvature in the range, solves equilibrium (N = N_Ed) and stores results.
        Stops when equilibrium tolerance is violated (indicates section failure).
        """
        kappa_min, kappa_max = self.get_kappa_range()

        # Create curvature array
        kappa_array = np.linspace(kappa_min, kappa_max, self.n_kappa)

        # Initialize result arrays
        eps_bot_list = []
        M_list = []
        N_list = []
        kappa_list = []

        # Solve for each curvature until equilibrium tolerance is violated
        n_failed = 0
        failure_threshold = 3  # Allow a few tolerance violations before stopping
        tolerance_multiplier = 100.0  # Allow up to 100x normal tolerance
        M_max_so_far = 0.0
        M_peak_reached = False

        for i, kappa in enumerate(kappa_array):
            eps_bot, N, M, converged = self.solve_equilibrium_at_kappa(kappa)

            # Check if equilibrium is satisfied (this is the key criterion)
            if abs(N) > self.N_tol * tolerance_multiplier:
                # Equilibrium badly violated - count as failure
                n_failed += 1
                if n_failed >= failure_threshold:
                    # Stop here - section has failed
                    print(
                        f"Stopping at κ = {kappa*1000:.4f} ‰/mm (equilibrium lost, section failed)"
                    )
                    break
                # Don't store this point - equilibrium not satisfied
                continue
            else:
                # Equilibrium satisfied - reset failure counter
                n_failed = 0

            # Store results (only if equilibrium is satisfied)
            kappa_list.append(kappa)
            eps_bot_list.append(eps_bot)
            N_list.append(N)
            M_list.append(M)

            # Track peak moment
            if M > M_max_so_far:
                M_max_so_far = M
                M_peak_reached = True

            # Check if moment has dropped below 20% of peak (post-peak softening cutoff)
            if M_peak_reached and M < 0.2 * M_max_so_far:
                print(f"Stopping at κ = {kappa*1000:.4f} ‰/mm (M dropped below 20% of peak)")
                break

        # Convert to arrays
        self.kappa_values = np.array(kappa_list)
        self.eps_bot_values = np.array(eps_bot_list)
        self.M_values = np.array(M_list)
        self.N_values = np.array(N_list)

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
        eps_tops = eps_bots - kappas * self.cs.h_total  # negative = compression

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

    def plot_mk(
        self,
        ax: Optional[plt.Axes] = None,
        show_grid: bool = True,
        color: str = "#1f77b4",
        linewidth: float = 2.0,
        label: str = "M-κ",
        show_failure_marker: bool = False,
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

        if show_failure_marker:
            self._add_failure_marker(ax, color=color)

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
    from scite.cs_design.reinforcement import ReinforcementLayer, ReinforcementLayout
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
