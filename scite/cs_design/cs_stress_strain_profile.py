"""
Cross-Section Stress-Strain Profile Analysis
============================================

Calculate and visualize strain and stress distributions across the cross-section
based on plane section assumption.

Integrates with CrossSection objects to compute:
- Strain profiles from curvature and reference strain
- Stress profiles in concrete and reinforcement
- Force resultants (N, M) with visualization
"""

from typing import TYPE_CHECKING, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.patches import FancyArrow, Rectangle

if TYPE_CHECKING:
    from scite.cs_design.cross_section import CrossSection


def to_scalar(val):
    """Convert numpy array or scalar to Python float (numpy 2.x compatible)."""
    if hasattr(val, 'item'):
        return float(val.item())
    return float(val)


class StressStrainProfile:
    """
    Stress and strain profile calculator for cross-sections.
    
    Computes distributions based on plane section assumption:
    ε(z) = eps_bot - κ × z
    
    Internal state: (kappa, eps_bottom) at z=0.
    Use set_state() to configure state with different control parameters:
    - (kappa, eps_bot) → M-κ analysis
    - (kappa, eps_top) → Alternative control
    - (eps_top, eps_bot) → Unbalanced model
    - (eps_top, eps_s, layer_index) → Textbook RC design
    
    Attributes:
        cs: CrossSection object with shape, concrete, and reinforcement
        kappa: Curvature [1/mm]
        eps_bottom: Strain at bottom reference point z=0 [-]
    """
    
    def __init__(self, cs: 'CrossSection', kappa: float = 0.0, eps_bottom: float = 0.0):
        """
        Initialize stress-strain profile.
        
        Internal state: (kappa, eps_bottom) at z=0.
        Use set_state() to update with different control parameters.
        
        Args:
            cs: CrossSection object
            kappa: Curvature [1/mm]
            eps_bottom: Strain at z=0 [-]
        """
        self.cs = cs
        self.kappa = kappa
        self.eps_bottom = eps_bottom
    
    def set_state(
        self, 
        kappa: Optional[float] = None,
        eps_bot: Optional[float] = None,
        eps_top: Optional[float] = None,
        eps_s1: Optional[float] = None,
        layer_index: int = 0
    ) -> None:
        """
        Set profile state from various control parameter combinations.
        
        Plane section kinematics: ε(z) = eps_bot - κ×z
        
        Supported combinations (provide exactly one):
        1. (kappa, eps_bot) → M-κ analysis mode
        2. (kappa, eps_top) → Alternative M-κ mode
        3. (eps_top, eps_bot) → Unbalanced/teaching mode
        4. (eps_top, eps_s1, layer_index) → Textbook RC design mode
        
        Args:
            kappa: Curvature [1/mm]
            eps_bot: Strain at bottom z=0 [-]
            eps_top: Strain at top z=h [-]
            eps_s1: Strain at reinforcement layer (EC2 notation) [-]
            layer_index: Reinforcement layer index (for eps_s1 mode)
            
        Examples:
            # M-κ analysis
            profile.set_state(kappa=-0.00001, eps_bot=0.002)
            
            # Textbook RC design
            profile.set_state(eps_top=-0.0035, eps_s1=0.005, layer_index=0)
            
            # Unbalanced model
            profile.set_state(eps_top=-0.0035, eps_bot=0.0078)
        """
        h = self.cs.h_total
        
        # Mode 1: (kappa, eps_bot) - Direct assignment
        if kappa is not None and eps_bot is not None:
            self.kappa = kappa
            self.eps_bottom = eps_bot
            
        # Mode 2: (kappa, eps_top) - Calculate eps_bot
        elif kappa is not None and eps_top is not None:
            self.kappa = kappa
            self.eps_bottom = eps_top + kappa * h
            
        # Mode 3: (eps_top, eps_bot) - Calculate kappa
        elif eps_top is not None and eps_bot is not None:
            self.kappa = (eps_bot - eps_top) / h
            self.eps_bottom = eps_bot
            
        # Mode 4: (eps_top, eps_s1, layer_index) - RC design mode
        elif eps_top is not None and eps_s1 is not None:
            if layer_index >= len(self.cs.reinforcement.layers):
                raise ValueError(f"Layer {layer_index} out of range")
            
            # layer.z is distance from BOTTOM; kappa = (eps_s1 - eps_top) / (h - z_s)
            z_s = self.cs.reinforcement.layers[layer_index].z
            self.kappa = (eps_s1 - eps_top) / (h - z_s)
            self.eps_bottom = eps_top + self.kappa * h
            
        else:
            raise ValueError(
                "Must provide one of: "
                "(kappa, eps_bot), (kappa, eps_top), (eps_top, eps_bot), or (eps_top, eps_s1)"
            )
    
    @property
    def eps_top(self) -> float:
        """Convenience property: strain at top (z=0)."""
        return self.eps_bottom - self.kappa * self.cs.h_total
    
    def get_strain_at_z(self, z: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Calculate strain at height z using plane section assumption.
        
        Standard coordinate system:
        - z = 0 at bottom of section
        - z = h at top of section
        - ε(z) = ε_bottom - κ×z (strain decreases with height for positive curvature)
        
        Args:
            z: Height coordinate(s) [mm]
            
        Returns:
            Strain value(s) [-]
        """
        return self.eps_bottom - self.kappa * z
    
    def get_strain_profile(self, n_points: int = 100) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Get strain distribution along cross-section height.
        
        Args:
            n_points: Number of points for profile
            
        Returns:
            (z_coords, strain_values): Height coordinates and strains
        """
        z_coords = np.linspace(0, self.cs.h_total, n_points)
        strain_values = np.asarray(self.get_strain_at_z(z_coords))
        return z_coords, strain_values
    
    def get_concrete_stress_profile(self, n_points: int = 100) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Get concrete stress distribution along cross-section height.
        
        Args:
            n_points: Number of points for profile
            
        Returns:
            (z_coords, stress_values): Height coordinates and stresses [MPa]
        """
        z_coords, strains = self.get_strain_profile(n_points)
        stress_values = self.cs.concrete.get_sig(strains)
        return z_coords, stress_values
    
    def get_reinforcement_strains_stresses(self) -> Tuple[list, list, list]:
        """
        Get strain and stress values at reinforcement layers.
        
        Returns:
            (z_positions, strains, stresses): Lists of z-coordinates, strains, and stresses
        """
        z_positions = []
        strains = []
        stresses = []
        
        for layer in self.cs.reinforcement.layers:
            z = layer.z
            eps = self.get_strain_at_z(z)
            sig = layer.get_sig(eps)
            
            z_positions.append(z)
            strains.append(eps)
            stresses.append(sig)
        
        return z_positions, strains, stresses
    
    def get_force_resultants(self) -> Tuple[float, float, float, float]:
        """
        Calculate force resultants from stress distributions.
        
        This calculation is independent of how the state (kappa, eps_bottom) was set.
        For kappa=0, eps_bot=0: uniform zero strain → zero stresses → N=0, M=0 (correct)
        
        Returns:
            (F_c, F_s, N_total, M_total): Concrete force, steel force, total axial force, total moment
        """
        # Concrete force (integrate stress over area)
        # Use simplified integration - rectangular stress block approximation
        z_coords, sigma_c = self.get_concrete_stress_profile(100)
        
        # Calculate concrete force by numerical integration
        F_c = 0.0
        dz = self.cs.h_total / 100
        for i, (z, sig) in enumerate(zip(z_coords, sigma_c)):
            # Get width at this height from shape
            width = self._get_width_at_z(z)
            dF = sig * width * dz
            F_c += dF
        
        # Steel forces from reinforcement
        F_s_total = 0.0
        z_s_list, eps_s_list, sig_s_list = self.get_reinforcement_strains_stresses()
        
        for layer, eps in zip(self.cs.reinforcement.layers, eps_s_list):
            F_s_total += layer.get_force(eps)
        
        # Total axial force
        N_total = F_c + F_s_total
        
        # Moment about reference point (z=0, bottom)
        # Sign convention: positive curvature (sagging) → positive moment
        M_c = 0.0
        for i, (z, sig) in enumerate(zip(z_coords, sigma_c)):
            width = self._get_width_at_z(z)
            dF = sig * width * dz
            M_c += dF * z
        
        M_s = 0.0
        for layer, eps in zip(self.cs.reinforcement.layers, eps_s_list):
            M_s += layer.get_moment(eps, y_ref=0.0)
        
        # Negate moment to follow standard sign convention:
        # positive curvature (sagging) → positive moment
        M_total = -(M_c + M_s)
        
        return F_c, F_s_total, N_total, M_total
    
    def get_concrete_force_centroid(self) -> float:
        """
        Calculate the centroid of the concrete compression/tension zone.
        
        Returns:
            z_centroid: Height coordinate of concrete force centroid [mm]
                        Clamped to valid range [0, h_total]
        """
        z_coords, sigma_c = self.get_concrete_stress_profile(100)
        
        F_c = 0.0
        M_c = 0.0
        dz = self.cs.h_total / 100
        
        for z, sig in zip(z_coords, sigma_c):
            width = self._get_width_at_z(z)
            dF = sig * width * dz
            F_c += dF
            M_c += dF * z
        
        # Centroid: z_c = M_c / F_c
        # Use higher threshold (100 N = 0.1 kN) to avoid numerical issues at low forces
        if abs(F_c) > 100.0:
            z_centroid = M_c / F_c
            # Clamp to valid range [0, h_total] to prevent arrows outside section
            z_centroid = max(0.0, min(z_centroid, self.cs.h_total))
            return z_centroid
        else:
            # If concrete force is too small, return mid-height
            return self.cs.h_total / 2
    
    def _get_width_at_z(self, z: float) -> float:
        """Get cross-section width at height z."""
        # For rectangular sections, width is constant
        if hasattr(self.cs.shape, 'b'):
            return self.cs.shape.b
        # For T or I sections, need to check flanges
        # Simplified - assume rectangular for now
        return self.cs.shape.b if hasattr(self.cs.shape, 'b') else 300.0
    
    def _plot_curvature_indicator(self, ax_strain, strains_permille):
        """Plot curvature visualization triangle in strain plot.
        
        Args:
            ax_strain: Matplotlib axes for strain plot
            strains_permille: Strain values in permille for positioning
        """
        from matplotlib.patches import Polygon

        # Triangle dimensions
        y_mid = self.cs.h_total / 2
        unit_length = 0.10 * self.cs.h_total  # Vertical side: 10% of height
        strain_change = self.kappa * unit_length * 1000  # Horizontal side: κ × unit_length [‰]
        
        # Triangle vertices
        y_base = y_mid - unit_length / 2
        y_top = y_base + unit_length
        eps_base = self.get_strain_at_z(y_base) * 1000
        
        # Position triangle with offset from strain profile
        strain_range = strains_permille.max() - strains_permille.min()
        # Ensure minimum strain range for positioning (avoid zero/tiny values)
        strain_range = max(strain_range, 0.1)  # At least 0.1 ‰
        offset_x = strain_range * 0.05
        
        # Right triangle: vertical right side, horizontal and diagonal on left
        triangle_vertices = [
            (eps_base + offset_x, y_base),           # Bottom right
            (eps_base + offset_x, y_top),            # Top right (vertical side)
            (eps_base + offset_x - strain_change, y_top)  # Top left (horizontal side)
        ]
        
        # Draw triangle outline only (no fill)
        triangle = Polygon(triangle_vertices, closed=True, 
                          facecolor='none', edgecolor='black', 
                          linewidth=1.5, zorder=3)
        ax_strain.add_patch(triangle)
        
        # Curvature label above horizontal side (left-aligned with left corner, then shifted right)
        # Approximate shift by one character width (roughly 5% of strain range for typical fonts)
        char_shift = strain_range * 0.03
        x_pos_kappa = eps_base + offset_x - strain_change + char_shift
        y_pos_kappa = y_top + self.cs.h_total * 0.02
        
        # κ text in ‰/mm (permille per mm) - no box
        kappa_text = f'κ = {self.kappa*1000:.3f} ‰/mm'
        ax_strain.text(x_pos_kappa, y_pos_kappa, kappa_text,
                      ha='left', va='bottom', fontsize=11, color='black')
        
        # "1 mm" label to the right of vertical side (centered vertically)
        x_pos_length = eps_base + offset_x + strain_range * 0.02
        y_pos_length = (y_base + y_top) / 2
        ax_strain.text(x_pos_length, y_pos_length, '1 mm',
                      ha='left', va='center', fontsize=11, color='black')
    
    def plot_stress_strain_profile(
        self, 
        ax_strain=None, 
        ax_stress=None,
        show_resultants: bool = True,
        eps_lim: tuple = None,
        z_lim: tuple = None,
        concrete_label: str = 'F_c',
        steel_label: str = 'F_s',
        N_Ed: Optional[float] = None,
        M_Ed: Optional[float] = None,
        show_assessment: bool = False
    ) -> Tuple:
        """
        Plot strain and stress distributions side by side.
        Based on StressStrainProfileSubWidget from rc_bending_widget_mn.py
        
        Args:
            ax_strain: Matplotlib axes for strain plot (creates if None)
            ax_stress: Matplotlib axes for stress plot (creates if None)
            show_resultants: Whether to show force arrows and values
            eps_lim: Fixed (min, max) strain limits for x-axis (if None, auto-calculated)
            z_lim: Fixed (min, max) height limits for y-axis (if None, auto-calculated)
            concrete_label: Label prefix for concrete force (e.g., 'F_c', 'F_cd')
            steel_label: Label prefix for steel force (e.g., 'F_s', 'F_sd')
            N_Ed: External axial force to display [kN] (optional)
            M_Ed: Design moment for assessment [kNm] (optional)
            show_assessment: Whether to show M_Rd ≥ M_Ed assessment box
            
        Returns:
            (ax_strain, ax_stress): The matplotlib axes objects
        """
        # Create figure if axes not provided
        if ax_strain is None or ax_stress is None:
            fig, (ax_strain, ax_stress) = plt.subplots(
                1, 2, figsize=(14, 6), 
                gridspec_kw={'width_ratios': [1, 2], 'wspace': 0},
                sharey=True
            )
        
        # Get profiles
        z_coords, strains = self.get_strain_profile(n_points=100)
        z_stress, stresses_c = self.get_concrete_stress_profile(n_points=100)
        z_reinf, eps_reinf, sig_reinf = self.get_reinforcement_strains_stresses()
        
        # Calculate forces
        F_c, F_s, N_total, M_total = self.get_force_resultants()
        F_c_val = to_scalar(F_c) / 1000  # Convert to kN
        F_s_val = to_scalar(F_s) / 1000  # Convert to kN
        
        # Find neutral axis (where strain = 0)
        neutral_axis_z = None
        for i, eps in enumerate(strains):
            if i > 0 and strains[i-1] * eps < 0:  # Sign change
                neutral_axis_z = z_coords[i]
                break
        if neutral_axis_z is None:
            neutral_axis_z = self.cs.h_total / 2
        
        # === STRAIN PROFILE ===
        strains_permille = strains * 1000
        
        # Separate compression and tension zones
        compression_mask = strains <= 0
        tension_mask = strains >= 0
        
        # Compression zone (negative strain, blue)
        if np.any(compression_mask):
            z_c = z_coords[compression_mask]
            eps_c = strains_permille[compression_mask]
            ax_strain.fill_betweenx(z_c, 0, eps_c, alpha=0.15, color='steelblue')
            ax_strain.plot(eps_c, z_c, 'b-', linewidth=3)
        
        # Tension zone (positive strain, coral to match force arrows)
        if np.any(tension_mask):
            z_t = z_coords[tension_mask]
            eps_t = strains_permille[tension_mask]
            ax_strain.fill_betweenx(z_t, 0, eps_t, alpha=0.15, color='lightcoral')
            ax_strain.plot(eps_t, z_t, '-', color='coral', linewidth=3)
        
        # Reinforcement strains
        for z, eps in zip(z_reinf, eps_reinf):
            color = 'red' if eps > 0 else 'blue'
            ax_strain.plot(eps * 1000, z, 'o', markersize=10, 
                          markerfacecolor=color, markeredgecolor='black', markeredgewidth=2)
        
        # Zero strain line
        ax_strain.axvline(x=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Horizontal reference lines
        ax_strain.axhline(y=neutral_axis_z, color='darkgreen', linestyle='--', alpha=0.7, linewidth=1.5)
        for z in z_reinf:
            ax_strain.axhline(y=z, color='black', linestyle='--', alpha=0.7, linewidth=1.5)
        
        # Formatting strain
        ax_strain.set_ylabel('Height [mm]', fontsize=11)
        ax_strain.set_xlabel('Strain [‰]', fontsize=11)
        ax_strain.set_title('Strain Distribution', fontsize=11)
        ax_strain.grid(True, alpha=0.3)
        ax_strain.tick_params(labelsize=11)
        
        # Set y-limits (height)
        if z_lim is not None:
            ax_strain.set_ylim(z_lim[0], z_lim[1])
        else:
            ax_strain.set_ylim(0, self.cs.h_total)
        
        # Set x-limits (strain)
        if eps_lim is not None:
            # Use provided fixed limits (already in ‰)
            ax_strain.set_xlim(eps_lim[0] * 1000, eps_lim[1] * 1000)
        else:
            # Auto-calculate based on actual strain range with margin
            min_strain = strains_permille.min()
            max_strain = strains_permille.max()
            strain_range = max_strain - min_strain
            margin = strain_range * 0.2
            ax_strain.set_xlim(min_strain - margin, max_strain + margin)
        
        # Add curvature visualization triangle
        self._plot_curvature_indicator(ax_strain, strains_permille)
        
        # === STRESS PROFILE WITH TWIN AXES ===
        # Base stress scale on concrete strength
        f_c = abs(self.cs.concrete.f_ck) if hasattr(self.cs.concrete, 'f_ck') else 30.0
        max_stress = f_c * 2.5  # Use 2.5x compressive strength for scale
        
        # Force range - primary axis
        max_force = max(abs(F_c_val), abs(F_s_val)) if (abs(F_c_val) > 0 or abs(F_s_val) > 0) else 100.0
        
        # Scale factor: map stress to force axis
        stress_to_force_scale = max_force / max_stress if max_stress > 0 else 1.0
        
        # Concrete stress (plot scaled to force axis)
        if len(stresses_c) > 0:
            stresses_c_scaled = stresses_c * stress_to_force_scale
            ax_stress.fill_betweenx(z_stress, 0, stresses_c_scaled, alpha=0.15, color='steelblue')
            ax_stress.plot(stresses_c_scaled, z_stress, 'b-', linewidth=3)
            max_idx = np.argmax(np.abs(stresses_c))
        
        # Zero line
        ax_stress.axvline(x=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Horizontal reference lines
        ax_stress.axhline(y=neutral_axis_z, color='darkgreen', linestyle='--', alpha=0.7, linewidth=1.5, zorder=1)
        
        # Set up twin x-axis for stress and store it
        ax_stress_twin = ax_stress.twiny()
        
        # Label offset from arrow
        label_offset = self.cs.h_total * 0.028
        
        # Show force resultants as arrows
        if show_resultants:
            # External force N_Ed (at mid-height) if provided
            if N_Ed is not None and abs(N_Ed) > 0.1:
                mid_height = self.cs.h_total / 2
                arrow_len = N_Ed  # kN (negative=compression=left, positive=tension=right)
                head_width = self.cs.h_total * 0.04
                head_length = max_force * 0.02
                ax_stress.arrow(0, mid_height, arrow_len, 0, 
                              head_width=head_width, head_length=head_length,
                              fc='dimgray', ec='black', linewidth=4, 
                              length_includes_head=True, zorder=2)
                
                # N_Ed label
                ax_stress.text(arrow_len, mid_height + label_offset, 
                             f'N_Ed = {N_Ed:.1f} kN',
                             ha='right' if N_Ed > 0 else 'left', va='bottom', 
                             fontsize=11, color='black',
                             bbox=dict(boxstyle='round', facecolor='lightgray', 
                                     alpha=0.15, edgecolor='black', linewidth=1.0))
                
                # Reference line for N_Ed
                ax_stress.axhline(y=mid_height, color='gray', linestyle='-', 
                                alpha=0.5, linewidth=1.0, zorder=0)
            
            # Calculate actual compression zone centroid
            z_c_centroid = self.get_concrete_force_centroid()
            
            # Reinforcement levels - sort by z for bottom-to-top numbering
            layer_indices = sorted(range(len(z_reinf)), key=lambda i: z_reinf[i])
            
            for z in z_reinf:
                ax_stress.axhline(y=z, color='black', linestyle='--', alpha=0.7, linewidth=1.5, zorder=1)
            
            # Compression force
            if abs(F_c_val) > 0.1:
                ax_stress.axhline(y=z_c_centroid, color='black', linestyle='--', alpha=0.7, linewidth=1.5, zorder=1)
                arrow_len = F_c_val  # F_c_val is negative for compression, so arrow points left
                head_width = self.cs.h_total * 0.04
                head_length = max_force * 0.02
                ax_stress.arrow(0, z_c_centroid, arrow_len, 0, 
                              head_width=head_width, head_length=head_length,
                              fc='cornflowerblue', ec='royalblue', linewidth=4, 
                              length_includes_head=True, zorder=2)
                
                # Combined label for concrete force and stress (show absolute value for compression)
                if len(stresses_c) > 0:
                    combined_text = f'{concrete_label} = {F_c_val:.1f} kN\nσ_c = {stresses_c[max_idx]:.1f} MPa'
                else:
                    combined_text = f'{concrete_label} = {F_c_val:.1f} kN'
                ax_stress.text(arrow_len, z_c_centroid - label_offset, 
                             combined_text,
                             ha='left', va='top', fontsize=11, color='black',
                             bbox=dict(boxstyle='round', facecolor='steelblue', alpha=0.15, 
                                     edgecolor='black', linewidth=1.0))
            
            # Tension forces (at steel levels) - numbered from bottom to top
            for idx, i in enumerate(layer_indices):
                z = z_reinf[i]
                eps = eps_reinf[i]
                sig = sig_reinf[i]
                layer_number = idx + 1  # 1-based numbering from bottom
                
                F_s_layer_raw = self.cs.reinforcement.layers[i].get_force(eps)
                F_s_layer = float(F_s_layer_raw.item() if hasattr(F_s_layer_raw, 'item') else F_s_layer_raw) / 1000  # kN
                if abs(F_s_layer) > 0.1:
                    arrow_len = F_s_layer
                    head_width = self.cs.h_total * 0.04
                    head_length = max_force * 0.02
                    ax_stress.arrow(0, z, arrow_len, 0, 
                                  head_width=head_width, head_length=head_length,
                                  fc='coral', ec='firebrick', linewidth=4, 
                                  length_includes_head=True, zorder=2)
                    
                    # Combined label for steel force and stress with layer number
                    combined_text = f'{steel_label}{layer_number} = {F_s_layer:.1f} kN\nσ_s = {float(sig):.1f} MPa'
                    ax_stress.text(arrow_len, z + label_offset, 
                                 combined_text,
                                 ha='right', va='bottom', fontsize=11, color='black',
                                 bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.15, 
                                         edgecolor='black', linewidth=1.0))
        
        # Configure axes - force is primary (bottom), stress is twin (top)
        ax_stress.set_ylabel('')  # Remove duplicate y-label (shared with strain plot)
        ax_stress.set_xlabel('force [kN]', fontsize=11, color='black')
        ax_stress_twin.set_xlabel('(compression ← stress [MPa] → tension)', fontsize=11, color='black')
        ax_stress_twin.tick_params(axis='x', labelcolor='black', labelsize=11)
        ax_stress.tick_params(labelsize=11)
        
        ax_stress.set_title('stress distribution & force resultants', fontsize=11)
        
        # Set y-limits
        ax_stress.set_ylim(0, self.cs.h_total)
        
        # Set x-limits - force axis controls visual range
        ax_stress.set_xlim(-max_force * 1.35, max_force * 1.35)
        ax_stress_twin.set_xlim(-max_stress * 1.35, max_stress * 1.35)
        
        # Add assessment or summary text box in bottom-left area
        N_val = to_scalar(N_total)
        M_val = to_scalar(M_total)
        
        # Position box in bottom-left area
        x_pos = -max_force * 1.35 / 2
        y_pos = self.cs.h_total * 0.2
        
        if show_assessment and M_Ed is not None:
            # Show M_Rd ≥ M_Ed assessment
            M_Rd = M_val / 1e6  # Convert to kNm
            delta_M = M_Rd - M_Ed
            
            # Determine box color based on safety
            box_bg_color = 'lightgreen' if delta_M >= 0 else 'lightcoral'
            
            assessment_text = f'M_Rd ≥ M_Ed\n{M_Rd:.2f} ≥ {M_Ed:.2f} [kNm]\nΔM = {delta_M:.2f} kNm'
            ax_stress.text(x_pos, y_pos, assessment_text,
                          ha='center', va='center', fontsize=11, color='black',
                          bbox=dict(boxstyle='round', facecolor=box_bg_color, 
                                  alpha=0.6, edgecolor='black', linewidth=1.0))
        else:
            # Show resultants only
            summary_text = f'N = {N_val/1000:.1f} kN\nM = {M_val/1e6:.2f} kNm'
            ax_stress.text(x_pos, y_pos, summary_text,
                          ha='center', va='center', fontsize=11, color='black',
                          bbox=dict(boxstyle='round', facecolor='lightyellow', 
                                  alpha=0.6, edgecolor='black', linewidth=1.0))
        
        # NOTE: N_total is the sum of all internal forces (F_c + F_s)
        # Equilibrium condition:
        #   - If N_Ed is provided (external axial load): N_internal = N_Ed, so N_err = N_internal - N_Ed
        #   - If N_Ed is None (pure bending): N_internal = 0, so N_err = N_internal
        
        # Show unbalanced force indicator if imbalance > threshold
        # Use absolute threshold of 0.1 kN rather than relative (more meaningful for equilibrium)
        threshold_kN = 0.1  # 0.1 kN = 100 N threshold
        
        # Calculate equilibrium error
        if N_Ed is not None:
            # With external axial load: error = internal - external
            N_imbalance_kN = (N_val / 1000) - N_Ed
        else:
            # Pure bending: error = internal forces (should sum to zero)
            N_imbalance_kN = N_val / 1000
        
        if abs(N_imbalance_kN) > threshold_kN:
            # Draw thick warning bar exactly on x-axis showing unbalanced force
            y_imbalance = 0  # Exactly on axis - global resultant
            
            # Draw thick bar from origin to imbalance value (distinct magenta color)
            ax_stress.plot([0, N_imbalance_kN], [y_imbalance, y_imbalance], 
                          color='magenta', linewidth=8, solid_capstyle='butt', zorder=5)
            
            # Simple text just above the tip - magenta, no box
            text_y_offset = self.cs.h_total * 0.03
            imbalance_text = f'N_err = {N_imbalance_kN:.1f} kN'
            ax_stress.text(N_imbalance_kN, y_imbalance + text_y_offset, imbalance_text,
                          ha='center', va='bottom', fontsize=11, color='magenta', fontweight='bold')
        
        return ax_strain, ax_stress


def plot_stress_strain_profile(
    cs,
    kappa: float,
    eps_bottom: float = 0.0,
    figsize: Tuple[int, int] = (14, 8),
    show_resultants: bool = True
) -> Tuple:
    """
    Convenience function to plot stress-strain profile.
    
    Args:
        cs: CrossSection object
        kappa: Curvature [1/mm]
        eps_bottom: Strain at bottom [-]
        figsize: Figure size (width, height)
        show_resultants: Whether to show force arrows
        
    Returns:
        (fig, ax_strain, ax_stress): Figure and axes objects
    """
    profile = StressStrainProfile(cs, kappa, eps_bottom)
    fig, (ax_strain, ax_stress) = plt.subplots(1, 2, figsize=figsize)
    profile.plot_stress_strain_profile(ax_strain, ax_stress, show_resultants)
    plt.tight_layout()
    return fig, ax_strain, ax_stress
