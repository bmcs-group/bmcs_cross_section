"""
M-κ Analysis State Visualization
=================================

Interactive visualization combining M-κ curve with stress-strain profile state.

Shows the relationship between a point on the M-κ curve and the corresponding
strain and stress distributions in the cross-section.
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Optional
from matplotlib.gridspec import GridSpec

from bmcs_cross_section.mkappa.mkappa import MKappaAnalysis
from bmcs_cross_section.cs_design.cs_stress_strain_profile import StressStrainProfile


class MKappaStateProfiles:
    """
    Combined visualization of M-κ curve and stress-strain profile state.
    
    Creates an interactive figure showing:
    - Left: Strain and stress distributions (from StressStrainProfile)
    - Right: M-κ curve with current state marker
    
    The current state is controlled by the kappa parameter, which can be
    updated to explore different points on the M-κ curve.
    
    Attributes:
        mkappa: MKappaAnalysis instance with solved M-κ curve
        kappa: Current curvature for state visualization [1/mm]
        profile: StressStrainProfile instance at current kappa
    """
    
    def __init__(self, mkappa: MKappaAnalysis, kappa: Optional[float] = None):
        """
        Initialize M-κ state visualization.
        
        Args:
            mkappa: MKappaAnalysis instance (should be solved first)
            kappa: Initial curvature for visualization [1/mm].
                   If None, uses mid-point of solved curve.
        """
        self.mkappa = mkappa
        
        # Check if mkappa has been solved
        if not hasattr(self.mkappa, 'kappa_values') or len(self.mkappa.kappa_values) == 0:
            raise ValueError("MKappaAnalysis must be solved before creating state profiles. Call mkappa.solve() first.")
        
        # Store fixed z-range for consistent visualization
        self.z_min = 0.0
        self.z_max = self.mkappa.cs.h_total
        
        # Calculate global strain range across all states for consistent x-axis
        self._calculate_global_strain_range()
        
        # Set initial kappa
        if kappa is None:
            # Default to mid-point of the curve
            mid_idx = len(self.mkappa.kappa_values) // 2
            self.kappa = self.mkappa.kappa_values[mid_idx]
        else:
            self.kappa = kappa
        
        # Create stress-strain profile at current kappa
        self._update_profile()
    
    def _calculate_global_strain_range(self):
        """Calculate the global min/max strain range across all M-κ states."""
        eps_min_global = 0.0
        eps_max_global = 0.0
        
        # Sample several points along the M-κ curve to find strain extrema
        for i in range(len(self.mkappa.kappa_values)):
            kappa = self.mkappa.kappa_values[i]
            eps_bot = self.mkappa.eps_bot_values[i]
            
            # Strain at bottom
            eps_min_global = min(eps_min_global, eps_bot)
            eps_max_global = max(eps_max_global, eps_bot)
            
            # Strain at top (eps_top = eps_bot - kappa * h)
            eps_top = eps_bot - kappa * self.mkappa.cs.h_total
            eps_min_global = min(eps_min_global, eps_top)
            eps_max_global = max(eps_max_global, eps_top)
        
        # Add 10% margin for better visualization
        strain_range = eps_max_global - eps_min_global
        # Ensure minimum range to avoid plotting issues
        strain_range = max(strain_range, 0.001)  # At least 0.001 (1‰) range
        margin = 0.1 * strain_range
        
        self.eps_min = eps_min_global - margin
        self.eps_max = eps_max_global + margin
        
        # Safety check: ensure eps_max > eps_min
        if self.eps_max <= self.eps_min:
            self.eps_min = -0.005
            self.eps_max = 0.005
    
    def _update_profile(self):
        """Update the stress-strain profile for the current kappa."""
        # Find the equilibrium solution at this kappa
        # (kappa might not exactly match a point in kappa_values, so interpolate)
        eps_bot = self._get_eps_bot_at_kappa(self.kappa)
        
        # Create profile
        self.profile = StressStrainProfile(
            cs=self.mkappa.cs,
            kappa=self.kappa,
            eps_bottom=eps_bot
        )
    
    def _get_eps_bot_at_kappa(self, kappa: float) -> float:
        """
        Get the equilibrium eps_bot value at the given kappa.
        
        Args:
            kappa: Curvature [1/mm]
            
        Returns:
            eps_bot: Strain at bottom for equilibrium [-]
        """
        # Interpolate from solved values
        if kappa <= self.mkappa.kappa_values[0]:
            return self.mkappa.eps_bot_values[0]
        elif kappa >= self.mkappa.kappa_values[-1]:
            return self.mkappa.eps_bot_values[-1]
        else:
            return float(np.interp(kappa, self.mkappa.kappa_values, self.mkappa.eps_bot_values))
    
    def _get_M_at_kappa(self, kappa: float) -> float:
        """
        Get the moment value at the given kappa.
        
        Args:
            kappa: Curvature [1/mm]
            
        Returns:
            M: Moment [kN·m]
        """
        # Interpolate from solved values
        if kappa <= self.mkappa.kappa_values[0]:
            return self.mkappa.M_values[0]
        elif kappa >= self.mkappa.kappa_values[-1]:
            return self.mkappa.M_values[-1]
        else:
            return float(np.interp(kappa, self.mkappa.kappa_values, self.mkappa.M_values))
    
    def set_kappa(self, kappa: float):
        """
        Update the current curvature for visualization.
        
        Args:
            kappa: New curvature value [1/mm]
        """
        kappa_min = self.mkappa.kappa_values[0]
        kappa_max = self.mkappa.kappa_values[-1]
        
        if kappa < kappa_min or kappa > kappa_max:
            print(f"Warning: kappa = {kappa:.6f} is outside solved range "
                  f"[{kappa_min:.6f}, {kappa_max:.6f}]")
        
        self.kappa = kappa
        self._update_profile()
    
    def plot_mkappa_state(
        self,
        figsize: tuple = (18, 6),
        show_resultants: bool = True
    ) -> tuple:
        """
        Create combined visualization of M-κ curve and stress-strain profile.
        
        Layout:
        - Left: Strain distribution
        - Center: Stress distribution with force resultants
        - Right: M-κ curve with current state marker
        
        Args:
            figsize: Figure size (width, height) in inches
            show_resultants: Whether to show force arrows in stress plot
            
        Returns:
            (fig, ax_strain, ax_stress, ax_mk): Figure and axes objects
        """
        # Create figure with custom layout
        fig = plt.figure(figsize=figsize)
        
        # Use GridSpec for layout: [strain+stress (unified) | M-κ]
        # Create two main columns: profiles (3 parts) and M-κ curve (1.5 parts)
        gs_main = GridSpec(1, 2, figure=fig, width_ratios=[3, 1.5], wspace=0.15)
        
        # Subdivide first column into strain (1 part) and stress (2 parts) with no spacing
        gs_profiles = gs_main[0, 0].subgridspec(1, 2, width_ratios=[1, 2], wspace=0)
        
        ax_strain = fig.add_subplot(gs_profiles[0, 0])
        ax_stress = fig.add_subplot(gs_profiles[0, 1], sharey=ax_strain)
        ax_mk = fig.add_subplot(gs_main[0, 1])
        
        # Plot stress-strain profile using existing method with fixed axis limits
        self.profile.plot_stress_strain_profile(
            ax_strain=ax_strain,
            ax_stress=ax_stress,
            show_resultants=show_resultants,
            eps_lim=(self.eps_min, self.eps_max),
            z_lim=(self.z_min, self.z_max)
        )
        
        # Plot M-κ curve using existing method
        self.mkappa.plot_mk(ax=ax_mk)
        
        # Add marker for current state on M-κ curve
        M_current = self._get_M_at_kappa(self.kappa)
        kappa_display = self.kappa * 1000  # Convert to 1/m
        
        ax_mk.plot(kappa_display, M_current, 'ro', 
                  markersize=10, markeredgewidth=2, 
                  markerfacecolor='red', markeredgecolor='darkred',
                  zorder=10, label=f'Current: {kappa_display:.4f} 1/m')
        
        # Add vertical line from marker to x-axis
        ax_mk.plot([kappa_display, kappa_display], [0, M_current], 
                  'r--', linewidth=1.5, alpha=0.7, zorder=9)
        
        # Update legend to include current state
        ax_mk.legend(fontsize=11, loc='best')
        
        # Add overall title
        section_info = f'{self.mkappa.cs.shape.b:.0f}×{self.mkappa.cs.h_total:.0f} mm'
        concrete_info = f'f_ck = {self.mkappa.cs.concrete.f_ck:.0f} MPa'
        fig.suptitle(f'M-κ Analysis with State Profiles | {section_info}, {concrete_info}', 
                    fontsize=14, fontweight='bold', y=0.98)
        
        # Adjust layout manually for subgridspec compatibility
        gs_main.tight_layout(fig, rect=[0, 0, 1, 0.96])
        
        return fig, ax_strain, ax_stress, ax_mk
    
    def plot_at_kappa_values(
        self,
        kappa_values: list,
        figsize: tuple = (18, 6),
        show_resultants: bool = True
    ):
        """
        Create multiple figures showing states at different curvature values.
        
        Args:
            kappa_values: List of curvature values to visualize [1/mm]
            figsize: Figure size for each plot
            show_resultants: Whether to show force arrows
        """
        for kappa in kappa_values:
            self.set_kappa(kappa)
            self.plot_mkappa_state(figsize=figsize, show_resultants=show_resultants)
            plt.show()
    
    def plot_at_percentages(
        self,
        percentages: list = [0.25, 0.50, 0.75, 1.0],
        figsize: tuple = (18, 6),
        show_resultants: bool = True
    ):
        """
        Create multiple figures showing states at percentage points of the M-κ curve.
        
        Args:
            percentages: List of percentages (0.0 to 1.0) of the maximum curvature
            figsize: Figure size for each plot
            show_resultants: Whether to show force arrows
        """
        kappa_max = self.mkappa.kappa_values[-1]
        
        for pct in percentages:
            kappa = kappa_max * pct
            self.set_kappa(kappa)
            self.plot_mkappa_state(figsize=figsize, show_resultants=show_resultants)
            plt.show()


def create_mkappa_state_visualization(
    mkappa: MKappaAnalysis,
    kappa: Optional[float] = None,
    figsize: tuple = (18, 6),
    show_resultants: bool = True
) -> tuple:
    """
    Convenience function to create M-κ state visualization.
    
    Args:
        mkappa: Solved MKappaAnalysis instance
        kappa: Curvature for visualization [1/mm]. If None, uses mid-point.
        figsize: Figure size (width, height)
        show_resultants: Whether to show force arrows
        
    Returns:
        (mkappa_state, fig, ax_strain, ax_stress, ax_mk): 
            MKappaStateProfiles instance and axes objects
    """
    mkappa_state = MKappaStateProfiles(mkappa=mkappa, kappa=kappa)
    fig, ax_strain, ax_stress, ax_mk = mkappa_state.plot_mkappa_state(
        figsize=figsize,
        show_resultants=show_resultants
    )
    return mkappa_state, fig, ax_strain, ax_stress, ax_mk
