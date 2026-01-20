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

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.optimize import brentq

from scite.core import BMCSModel, ui_field
from scite.cs_design.cross_section import CrossSection
from scite.cs_design.cs_stress_strain_profile import StressStrainProfile


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
    
    n_kappa: int = ui_field(
        100,
        label=r"$n_\kappa$",
        unit="-",
        range=(10, 500),
        step=10,
        description="Number of curvature points",
        ge=10,
        le=500
    )
    
    # Tolerance for equilibrium solver
    N_tol: float = ui_field(
        0.01,
        label=r"$N_{tol}$",
        unit="kN",
        range=(0.001, 1.0),
        description="Axial force tolerance for equilibrium"
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
        eps_cu = abs(self.cs.concrete.eps_cu1)  # Ultimate compressive strain (negative)
        
        # Get maximum tensile strain from reinforcement
        eps_su = 0.010  # Default steel ultimate strain
        if self.cs.reinforcement.layers:
            # Get from first layer's material
            layer = self.cs.reinforcement.layers[0]
            if hasattr(layer.material, 'eps_ud'):
                eps_su = layer.material.eps_ud
            elif hasattr(layer.material, 'eps_u'):
                eps_su = layer.material.eps_u
        
        # Maximum curvature: full strain range over section height
        # When top concrete crushes and bottom steel yields
        kappa_max = (eps_cu + eps_su) / h
        
        # Start from small positive curvature (slightly above zero)
        kappa_min = kappa_max * 0.001
        
        return kappa_min, kappa_max
    
    def solve_equilibrium_at_kappa(self, kappa: float) -> Tuple[float, float, float, bool]:
        """
        Solve for ε_bot that gives N ≈ 0 at specified curvature.
        
        Uses Brent's method to find root of N(ε_bot) = 0.
        
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
            return N_total / 1000.0  # Convert to kN
        
        # Search bounds for eps_bot
        # Concrete can be in compression (negative) or tension (positive)
        # Steel in tension (positive)
        eps_bot_min = -0.010  # Compression at bottom
        eps_bot_max = 0.020   # Tension at bottom
        
        # Check if residual has opposite signs at bounds (required for brentq)
        r_min = residual(eps_bot_min)
        r_max = residual(eps_bot_max)
        
        if r_min * r_max > 0:
            # No sign change - no solution in range
            # Section has likely failed, return with converged=False
            profile.set_state(kappa=kappa, eps_bot=0.0)
            F_c, F_s, N_total, M_total = profile.get_force_resultants()
            return 0.0, float(N_total / 1000.0), float(M_total / 1e6), False
        
        try:
            # Solve for zero axial force with full output
            eps_bot_sol, result_info = brentq(residual, eps_bot_min, eps_bot_max, 
                                               xtol=1e-6, full_output=True)
            
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
        Compute the complete M-κ relationship.
        
        For each curvature in the range, solves equilibrium and stores results.
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
                    print(f"Stopping at κ = {kappa*1000:.4f} ‰/mm (equilibrium lost, section failed)")
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
    
    def plot_mk(
        self, 
        ax: Optional[plt.Axes] = None,
        show_grid: bool = True,
        color: str = '#1f77b4',
        linewidth: float = 2.0
    ) -> plt.Axes:
        """
        Plot moment-curvature relationship.
        
        Args:
            ax: Matplotlib axes (creates new if None)
            show_grid: Whether to show grid
            color: Line color
            linewidth: Line width
            
        Returns:
            Matplotlib axes with plot
        """
        if self.M_values is None:
            raise ValueError("No solution available. Call solve() first.")
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        # Convert curvature to ‰/mm for display
        kappa_permille_mm = self.kappa_values * 1000.0
        
        ax.plot(kappa_permille_mm, self.M_values, 
                color=color, linewidth=linewidth, label='M-κ')
        
        ax.set_xlabel('Curvature [1/m]', fontsize=12)
        ax.set_ylabel('Moment M [kN·m]', fontsize=12)
        ax.set_title('Moment-Curvature Relationship', fontsize=14, fontweight='bold')
        
        if show_grid:
            ax.grid(True, alpha=0.3, linestyle='--')
        
        ax.legend(fontsize=11)
        
        return ax
    
    def plot_state_at_kappa(
        self,
        kappa: float,
        ax_strain: Optional[plt.Axes] = None,
        ax_stress: Optional[plt.Axes] = None,
        show_resultants: bool = True
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
            fig.suptitle(f'State at κ = {kappa_actual*1000:.3f} ‰/mm, M = {M:.2f} kN·m', 
                         fontsize=14, fontweight='bold')
        
        profile.plot_stress_strain_profile(ax_strain, ax_stress, show_resultants)
        
        return ax_strain, ax_stress


def create_default_mkappa() -> MKappaAnalysis:
    """
    Create a default MKappa analysis for testing.
    
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
    concrete = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=1.0, gamma_c=1.5)
    
    # Steel reinforcement: 4Ø20 at bottom (z=50mm), 2Ø16 at top (z=450mm)
    steel_mat = SteelReinforcement(f_sy=500.0)
    
    layer_bottom = ReinforcementLayer(
        z=50.0,
        A_s=1256.6,  # 4Ø20 = 4×π×10²
        material=steel_mat
    )
    
    layer_top = ReinforcementLayer(
        z=450.0,
        A_s=402.1,   # 2Ø16 = 2×π×8²
        material=steel_mat
    )
    
    reinforcement = ReinforcementLayout(layers=[layer_bottom, layer_top])
    
    # Assemble cross-section
    cs = CrossSection(
        shape=shape,
        concrete=concrete,
        reinforcement=reinforcement
    )
    
    # Create analysis
    return MKappaAnalysis(cs=cs, n_kappa=100)

