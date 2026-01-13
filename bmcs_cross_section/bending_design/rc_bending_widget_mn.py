"""
RC Bending and Normal Force - Interactive Widget Module

This module provides modular interactive widgets for visualizing reinforced
concrete cross-section analysis. Each aspect (geometry, materials, strains,
stresses, results) is handled by a separate subwidget for better performance.

The widgets are model-agnostic and work with both:
- RCBendingModelMN (balanced model with automatic equilibrium)
- RCBendingUnbalancedModel (trial-and-error model with manual strain control)

The StressStrainProfileSubWidget separates figure creation from plotting for
efficient updates when model parameters change.

Author: Rostislav Chudoba
Course: Grundlagen der Tragwerke (Fundamentals of Structural Design)
Institution: IMB Institute, RWTH Aachen University
"""

import ipywidgets as widgets
from IPython.display import display, clear_output
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, Union
from .rc_bending_model_mn import RCBendingModelMN
from .rc_bending_unbalanced_model import RCBendingUnbalancedModel

# Type alias for supported models
RCModel = Union[RCBendingModelMN, RCBendingUnbalancedModel]


class GeometrySubWidget:
    """Subwidget for cross-section geometry visualization."""
    
    def __init__(self, model: RCModel):
        self.model = model
        self.output = widgets.Output()
        
    def update(self):
        """Update geometry plot."""
        with self.output:
            clear_output(wait=True)
            fig, ax = plt.subplots(1, 1, figsize=(8, 6))
            self._plot_geometry(ax)
            plt.tight_layout()
            plt.show()
    
    def _plot_geometry(self, ax):
        """Plot cross-section geometry with dimensions."""
        d = self.model.d
        b = self.model.b
        h = self.model.h
        c_nom = self.model.c_nom
        d_s1 = self.model.d_s1
        
        # Draw concrete section
        rect = plt.Rectangle((0, 0), b, h, fill=True, facecolor='lightgray',
                            edgecolor='black', linewidth=2.5, alpha=0.3)
        ax.add_patch(rect)
        
        # Draw reinforcement bars (schematic)
        n_bars = 3
        bar_spacing = b / (n_bars + 1)
        for i in range(n_bars):
            x_bar = (i + 1) * bar_spacing
            ax.plot(x_bar, d_s1, 'ro', markersize=12, markeredgecolor='darkred',
                   markeredgewidth=2, label='Reinforcement' if i == 0 else '')
        
        # Dimensions
        # Effective depth d (from TOP to reinforcement)
        ax.annotate('', xy=(b + 0.05, h), xytext=(b + 0.05, c_nom),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
        ax.text(b + 0.09, h - d/2, f'd = {d:.2f} m\n(from TOP)', rotation=90, va='center',
               fontsize=11, fontweight='bold')
        
        # Width b
        ax.annotate('', xy=(0, -0.03), xytext=(b, -0.03),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
        ax.text(b/2, -0.06, f'b = {b:.2f} m', ha='center', fontsize=11,
               fontweight='bold')
        
        # Cover c_nom
        ax.annotate('', xy=(-0.03, 0), xytext=(-0.03, c_nom),
                   arrowprops=dict(arrowstyle='<->', color='gray', lw=1))
        ax.text(-0.06, c_nom/2, f'c_nom = {c_nom:.2f} m', rotation=90,
               va='center', fontsize=11, color='gray')
        
        # Loading info
        loading_text = f'M_Ed = {self.model.M_Ed:.2f} MN·m\nN_Ed = {self.model.N_Ed:.2f} MN'
        ax.text(0.02, h - 0.03, loading_text, fontsize=9,
               bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
        
        ax.set_xlim(-0.2, b + 0.2)
        ax.set_ylim(-0.1, h + 0.05)
        ax.set_aspect('equal')
        ax.set_xlabel('Width [m]', fontsize=11)
        ax.set_ylabel('Height [m]', fontsize=11)
        ax.set_title('Cross-Section Geometry', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.2)


class MaterialLawsSubWidget:
    """Subwidget for material constitutive laws visualization."""
    
    def __init__(self, model: RCModel):
        self.model = model
        self.output = widgets.Output()
        
    def update(self):
        """Update material law plots."""
        with self.output:
            clear_output(wait=True)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 5))
            self._plot_concrete_law(ax1)
            self._plot_steel_law(ax2)
            plt.tight_layout()
            plt.show()
    
    def _plot_concrete_law(self, ax):
        """Plot concrete stress-strain curve."""
        epsilon_c_range = np.linspace(-0.004, 0.0001, 200)
        sigma_c = self.model.get_concrete_stress_strain(epsilon_c_range)
        
        ax.plot(epsilon_c_range * 1000, sigma_c, 'b-', linewidth=3,
               label='EC2 Parabola-Rectangle')
        
        # Mark key points
        ax.plot([self.model.epsilon_cx2 * 1000], [-self.model.f_cd], 'ro',
               markersize=8, label=f'ε_cx2 = {self.model.epsilon_cx2:.4f}')
        ax.plot([self.model.epsilon_cu2 * 1000], [-self.model.f_cd], 'rs',
               markersize=8, label=f'ε_cu2 = {self.model.epsilon_cu2:.4f}')
        
        ax.text(self.model.epsilon_cu2 * 1000, -self.model.f_cd * 1.1,
               f'f_cd = {self.model.f_cd:.1f} MPa', ha='center', fontsize=9,
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
        
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε_c [‰]', fontsize=11)
        ax.set_ylabel('Stress σ_c [MPa]', fontsize=11)
        ax.set_title('Concrete Constitutive Law\n(EC2)', fontsize=11, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-4, 0.5)
    
    def _plot_steel_law(self, ax):
        """Plot steel stress-strain curve."""
        epsilon_s_range = np.linspace(0, 0.025, 200)
        sigma_s = self.model.get_steel_stress_strain(epsilon_s_range)
        
        ax.plot(epsilon_s_range * 1000, sigma_s, 'r-', linewidth=3,
               label='Bilinear Law')
        
        # Mark yield point
        ax.plot([self.model.epsilon_yd * 1000], [self.model.sigma_yd], 'ro',
               markersize=8, label=f'Yield: ε_yd = {self.model.epsilon_yd*1000:.2f}‰')
        
        ax.text(self.model.epsilon_yd * 1000 * 1.5, self.model.sigma_yd * 0.9,
               f'f_yd = {self.model.sigma_yd:.0f} MPa', fontsize=9,
               bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
        
        ax.text(self.model.epsilon_yd * 1000 * 0.5, self.model.sigma_yd * 0.5,
               f'E_s = {self.model.E_s/1000:.0f} GPa', fontsize=9, rotation=60)
        
        ax.axhline(y=self.model.sigma_yd, color='r', linestyle='--', linewidth=1, alpha=0.5)
        ax.set_xlabel('Strain ε_s [‰]', fontsize=11)
        ax.set_ylabel('Stress σ_s [MPa]', fontsize=11)
        ax.set_title('Steel Constitutive Law\n(Bilinear)', fontsize=11, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, self.model.sigma_yd * 1.2)


class IntegrationParametersSubWidget:
    """Subwidget for EC2 integration parameters visualization."""
    
    def __init__(self, model: RCModel):
        self.model = model
        self.output = widgets.Output()
        
    def update(self):
        """Update integration parameters plot."""
        with self.output:
            clear_output(wait=True)
            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
            self._plot_parameters(ax)
            plt.tight_layout()
            plt.show()
    
    def _plot_parameters(self, ax):
        """Plot k_a and alpha_r profiles."""
        epsilon_c_range, k_a_values, alpha_r_values = self.model.get_integration_parameter_profiles()
        
        ax.plot(-epsilon_c_range, k_a_values, 'b-', linewidth=2, label=r'$k_a$')
        ax.plot(-epsilon_c_range, alpha_r_values, 'g-', linewidth=2, label=r'$\alpha_r$')
        
        # Mark current values
        ax.axhline(y=self.model.k_a, color='blue', linestyle='--', linewidth=1, alpha=0.5)
        ax.axhline(y=self.model.alpha_r, color='green', linestyle='--', linewidth=1, alpha=0.5)
        
        # Mark transition
        ax.axvline(x=-self.model.epsilon_cx2, color='red', linestyle=':', linewidth=1.5, alpha=0.5)
        ax.text(-self.model.epsilon_cx2, 0.95, 'ε_cx2', ha='center', va='bottom',
               fontsize=11, color='red')
        
        # Current values annotation
        ax.text(0.3, self.model.k_a + 0.02, f'k_a = {self.model.k_a:.3f}\nat ε_cu2',
               fontsize=11, color='blue', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
        ax.text(0.3, self.model.alpha_r - 0.04, f'α_r = {self.model.alpha_r:.3f}\nat ε_cu2',
               fontsize=11, color='green', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
        
        ax.set_xlabel(r'$\varepsilon_\mathrm{c}$ [-]', fontsize=11)
        ax.set_ylabel(r'$k_a$, $\alpha_\mathrm{r}$ [-]', fontsize=11)
        ax.set_title('EC2 Integration Parameters', fontsize=11, fontweight='bold')
        ax.legend(fontsize=9)
        ax.set_ylim(ymax=1.0)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 3.5)


class StrainProfileSubWidget:
    """Subwidget for strain distribution visualization."""
    
    def __init__(self, model: RCModel):
        self.model = model
        self.output = widgets.Output()
        
    def update(self):
        """Update strain profile plot."""
        with self.output:
            clear_output(wait=True)
            fig, ax = plt.subplots(1, 1, figsize=(8, 6))
            self._plot_strain_profile(ax)
            plt.tight_layout()
            plt.show()
    
    def _plot_strain_profile(self, ax):
        """Plot strain distribution."""
        heights, strains = self.model.get_strain_profile()
        
        ax.plot(strains * 1000, heights, 'b-', linewidth=3, label='Linear strain profile')
        ax.plot(strains * 1000, heights, 'bo', markersize=8)
        
        # Key points
        ax.plot([self.model.epsilon_cu2 * 1000], [self.model.h], 'rs', markersize=10,
               label=f'Top: ε_c2 = {self.model.epsilon_cu2:.4f}')
        ax.plot([self.model.epsilon_s1 * 1000], [self.model.c_nom], 'ro', markersize=10,
               label=f'Steel: ε_s1 = {self.model.epsilon_s1:.4f}')
        
        # Zero strain line
        ax.axvline(x=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Reference lines
        ax.axhline(y=self.model.h - self.model.x, color='green', linestyle='--', alpha=0.3)
        ax.axhline(y=self.model.c_nom, color='red', linestyle='--', alpha=0.3)
        
        ax.set_ylabel('Height from BOTTOM [m]', fontsize=11)
        ax.set_xlabel('Strain [‰]', fontsize=11)
        ax.set_title('Strain Distribution\n(Linear, Bernoulli)\n(x={:.3f}m from TOP)'.format(self.model.x),
                    fontsize=11, fontweight='bold')
        ax.legend(fontsize=11, loc='best')
        ax.grid(True, alpha=0.3)
        
        # Set symmetric x-limits to center the zero axis
        strains_milli = strains * 1000
        max_strain = max(abs(strains_milli.min()), abs(strains_milli.max()))
        ax.set_xlim(-max_strain * 1.1, max_strain * 1.1)


class StressProfileSubWidget:
    """Subwidget for stress distribution and force resultants."""
    
    def __init__(self, model: RCModel):
        self.model = model
        self.output = widgets.Output()
        self.ax_stress_twin = None  # Store twin axis for stress scale
        
    def update(self):
        """Update stress profile plot."""
        # Clear the stored twin axis reference since we're creating a new figure
        self.ax_stress_twin = None
        with self.output:
            clear_output(wait=True)
            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
            self._plot_stress_profile(ax)
            plt.tight_layout()
            plt.show()
    
    def _plot_stress_profile(self, ax):
        """Plot stress distribution with forces on primary x-axis."""
        heights_c, stresses_c, heights_s, stresses_s = self.model.get_stress_profile()
        
        # Base stress scale on compressive strength with factor
        f_cd = self.model.f_ck / 1.5  # Design compressive strength
        max_stress = abs(f_cd) * 2.5  # Use 2.5x compressive strength for scale
        
        # Force range - primary axis
        max_force = max(abs(self.model.F_cd), abs(self.model.F_sd))
        
        # Scale factor: map stress to force axis
        stress_to_force_scale = max_force / max_stress if max_stress > 0 else 1.0
        
        # Concrete stress (plot as negative for compression, scaled to force axis)
        if len(heights_c) > 0:
            stresses_c_scaled = stresses_c * stress_to_force_scale
            ax.fill_betweenx(heights_c, 0, stresses_c_scaled, alpha=0.15, color='steelblue',
                           label='Compression zone')
            ax.plot(stresses_c_scaled, heights_c, 'b-', linewidth=3, label='Concrete stress')
            
            max_idx = np.argmax(np.abs(stresses_c))
        
        # Zero line
        ax.axvline(x=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Horizontal reference lines spanning full width (plot BEFORE arrows so they appear below)
        # Mid-height level (where N_Ed is positioned) - below everything
        mid_height = self.model.h / 2
        ax.axhline(y=mid_height, color='gray', linestyle='-', alpha=0.5, linewidth=1.0, zorder=0)
        
        # Compression level (at center of gravity)
        force_height_c = self.model.h - self.model.a
        ax.axhline(y=force_height_c, color='black', linestyle='--', alpha=0.7, linewidth=1.5, zorder=1)
        
        # Neutral axis (at height h-x from bottom)
        ax.axhline(y=self.model.h - self.model.x, color='darkgreen', linestyle='--', alpha=0.7,
                  linewidth=1.5, label=f'Neutral axis', zorder=1)
        
        # Reinforcement level
        ax.axhline(y=self.model.c_nom, color='black', linestyle='--', alpha=0.7, linewidth=1.5, zorder=1)
        
        # Set up twin x-axis for stress and store it
        self.ax_stress_twin = ax.twiny()
        
        # Label offset from arrow (increased by factor 1.4)
        label_offset = 0.028  # vertical offset from arrow: 0.02 * 1.4
        
        # External force N_Ed (at mid-height) - compression is negative
        if self.model.N_Ed != 0:
            mid_height = self.model.h / 2
            arrow_len = self.model.N_Ed
            ax.arrow(0, mid_height, arrow_len, 0, head_width=0.02, head_length=0.02,
                    fc='dimgray', ec='black', linewidth=4, length_includes_head=True, zorder=2)
            ax.text(arrow_len, mid_height + label_offset, 
                    f'N_Ed = {self.model.N_Ed:.3f} MN',
                    ha='right', va='bottom', fontsize=11, color='black',
                    bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.15, edgecolor='black', linewidth=1.0))
        
        # Compression force (at center of gravity: height h-a from bottom, where a is from top)
        if self.model.F_cd > 0:
            arrow_len = -self.model.F_cd
            ax.arrow(0, force_height_c, arrow_len, 0, head_width=0.02, head_length=0.02,
                    fc='cornflowerblue', ec='royalblue', linewidth=4, length_includes_head=True, zorder=2)
            
            # Combined label for F_cd and σ_cd
            if len(stresses_c) > 0:
                combined_text = f'F_cd = -{self.model.F_cd:.3f} MN\nσ_cd = {stresses_c[max_idx]:.1f} MPa'
            else:
                combined_text = f'F_cd = -{self.model.F_cd:.3f} MN'
            ax.text(arrow_len, force_height_c - label_offset, 
                    combined_text,
                    ha='left', va='top', fontsize=11, color='black',
                    bbox=dict(boxstyle='round', facecolor='steelblue', alpha=0.15, edgecolor='black', linewidth=1.0))
        
        # Tension force (at steel level: c_nom from bottom)
        if self.model.F_sd > 0:
            arrow_len = self.model.F_sd
            ax.arrow(0, self.model.c_nom, arrow_len, 0, head_width=0.02, head_length=0.02,
                    fc='coral', ec='firebrick', linewidth=4, length_includes_head=True, zorder=2)
            
            # Combined label for F_sd, F_cd, σ_sd, and A_s
            A_s_cm2 = self.model.A_s_cm2 if hasattr(self.model, 'A_s_cm2') else 0
            if len(stresses_s) > 0:
                combined_text = f'F_sd = F_cd = {self.model.F_sd:.3f} MN\nσ_sd = {stresses_s[0]:.1f} MPa\n$\\mathbf{{A_s = {A_s_cm2:.2f}~cm²}}$'
            else:
                combined_text = f'F_sd = F_cd = {self.model.F_sd:.3f} MN\n$\\mathbf{{A_s = {A_s_cm2:.2f}~cm²}}$'
            ax.text(arrow_len, self.model.c_nom + label_offset, 
                    combined_text,
                    ha='right', va='bottom', fontsize=11, color='black',
                    bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.15, edgecolor='black', linewidth=1.0))
        
        # Lever arm (between compression and tension forces) - at 1/4 distance to max force
        lever_x = max_force * 0.25
        # Use orange color for dimension line to make it distinct
        ax.plot([lever_x, lever_x], [force_height_c, self.model.c_nom], color='orange', 
                linestyle='-', linewidth=0.8, alpha=0.6, zorder=2)
        ax.annotate('', xy=(lever_x, force_height_c), xytext=(lever_x, self.model.c_nom),
                   arrowprops=dict(arrowstyle='<->', color='orange', lw=1.5), zorder=2)
        ax.text(lever_x + label_offset, (force_height_c + self.model.c_nom)/2, f'z = {self.model.z:.3f} m',
               rotation=90, va='center', ha='left', fontsize=11, color='black',
               bbox=dict(boxstyle='round', facecolor='orange', alpha=0.4, edgecolor='black', linewidth=1.0))
        
        # Disbalance force indicator (for unbalanced models)
        if hasattr(self.model, 'force_imbalance'):
            # Correct sign: F_sd - F_cd (tension minus compression)
            delta_F = -self.model.force_imbalance  # Negate to get F_sd - F_cd
            # Display as filled rectangle in cover area (half-height of c_nom)
            bar_height = self.model.c_nom / 2
            bar_bottom = 0
            bar_top = bar_bottom + bar_height
            
            # Use salmon color to indicate unacceptable state (fully opaque)
            if abs(delta_F) > 0.001:  # Show only if significant imbalance
                # Draw filled rectangle
                from matplotlib.patches import Rectangle
                rect = Rectangle((0, bar_bottom), delta_F, bar_height,
                                facecolor='lightsalmon', edgecolor='red', 
                                linewidth=2, alpha=1.0, zorder=3)
                ax.add_patch(rect)
                
                # Add label for disbalance force (positioned above the bar)
                ax.text(delta_F / 2, bar_top + label_offset, 
                       f'ΔF = {delta_F:.3f} MN',
                       ha='center', va='bottom', fontsize=12, color='darkred',
                       fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='white', 
                                alpha=0.8, edgecolor='black', linewidth=1.0))
        
        # Configure axes - force is primary (bottom), stress is twin (top)
        ax.set_ylabel('height [m]', fontsize=11)
        ax.set_xlabel('force [MN]', fontsize=11, color='black')
        self.ax_stress_twin.set_xlabel('(compression ← stress [MPa] → tension)', fontsize=11, color='black')
        self.ax_stress_twin.tick_params(axis='x', labelcolor='black', labelsize=11)
        ax.tick_params(labelsize=11)
        
        ax.set_title('stress distribution & force resultants', fontsize=11)
        # ax.legend(fontsize=11, loc='lower left')  # Legend removed as requested
        
        # Set y-limits: max at cross-section height, no extra space
        ax.set_ylim(0, self.model.h)
        
        # Set x-limits - force axis controls visual range (20% wider)
        ax.set_xlim(-max_force * 1.35, max_force * 1.35)
        self.ax_stress_twin.set_xlim(-max_stress * 1.35, max_stress * 1.35)
        
        # Get M_Eds if available
        M_Rd = self.model.M_Rds
        M_Eds = self.model.M_Eds if hasattr(self.model, 'M_Eds') else self.model.M_Ed
        M_Ed_label = 'M_Eds' if hasattr(self.model, 'M_Eds') else 'M_Ed'
        delta_M = M_Rd - M_Eds
        
        # Determine box background color based on Delta M (green if safe, red if unsafe)
        box_bg_color = 'lightgreen' if delta_M >= 0 else 'lightcoral'
        
        # Position box in bottom-left area
        # Horizontal: center between left boundary and zero force level
        x_pos = -max_force * 1.35 / 2
        # Vertical: center between reinforcement level (c_nom) and mid-axis (h/2)
        z_s1 = self.model.z_s1 if hasattr(self.model, 'z_s1') else (self.model.h / 2 - self.model.c_nom)
        y_pos = self.model.c_nom + z_s1 / 2
        
        # Add M_Rd ≤ M_Eds label with three lines
        label_text = f'M_Rd ≤ {M_Ed_label}\n{M_Rd:.3f} ≤ {M_Eds:.3f} [MNm]\n$\\mathbf{{ΔM = {delta_M:.3f}~[MNm]}}$'
        ax.text(x_pos, y_pos,
                label_text,
                ha='center', va='center', fontsize=11, color='black',
                bbox=dict(boxstyle='round', facecolor=box_bg_color, alpha=0.6, edgecolor='black', linewidth=1.0))


class StressStrainProfileSubWidget:
    """
    Combined subwidget for stress and strain distributions in one figure.
    
    This widget is model-agnostic and works with any model that provides:
    - Properties: h, x, c_nom, d, a, z, epsilon_cu2, epsilon_s1, F_cd, F_sd, M_Rds
    - Methods: get_strain_profile(), get_stress_profile()
    """
    
    def __init__(self, model: RCModel):
        """
        Initialize the widget with a model.
        
        Parameters:
        -----------
        model : RCBendingModelMN or RCBendingUnbalancedModel
            The computational model providing the data
        """
        self.model = model
        self.output = widgets.Output()
        self.fig = None
        self.ax_strain = None
        self.ax_stress = None
        self.ax_stress_twin = None  # Store twin axis for stress scale
        self.assessment_widget = None  # Will be set later if needed
        
        # Create epsilon_s_bottom slider if model has this attribute (unbalanced model)
        self.epsilon_s_bottom_slider = None
        if hasattr(model, 'epsilon_s_bottom'):
            self.epsilon_s_bottom_slider = widgets.FloatSlider(
                value=model.epsilon_s_bottom,
                min=0.0000, max=0.0100, step=0.0001,
                description='ε_s,bot [-]:',
                style={'description_width': '110px'},
                layout=widgets.Layout(width='500px'),
                readout_format='.4f',
                tooltip='Tensile strain at reinforcement level (positive for tension)'
            )
            self.epsilon_s_bottom_slider.observe(self._on_slider_change, names='value')
        
        # Create layout with output and optionally the slider
        if self.epsilon_s_bottom_slider:
            self.layout = widgets.VBox([self.output, self.epsilon_s_bottom_slider])
        else:
            self.layout = self.output
        
        self._create_figure()
        self.update()  # Plot initial state immediately
    
    def set_assessment_widget(self, assessment_widget):
        """Set the assessment widget to update when slider changes."""
        self.assessment_widget = assessment_widget
    
    def _on_slider_change(self, change):
        """Handle slider value changes."""
        if hasattr(self.model, 'epsilon_s_bottom'):
            self.model.epsilon_s_bottom = change['new']
            self.update()
            # Update assessment widget if available
            if self.assessment_widget:
                self.assessment_widget.update()
    
    def _create_figure(self):
        """Create the figure and axes layout (called once during initialization)."""
        with self.output:
            clear_output(wait=True)
            # Create horizontal layout with width ratio 1:2 (strain:stress)
            self.fig, (self.ax_strain, self.ax_stress) = plt.subplots(
                1, 2, figsize=(14, 4), 
                gridspec_kw={'width_ratios': [1, 2], 'wspace': 0},
                sharey=True
            )
            # Remove y-axis labels from right plot since they share the axis
            self.ax_stress.set_ylabel('')
            
            # Suppress the figure header/toolbar
            if hasattr(self.fig.canvas, 'header_visible'):
                self.fig.canvas.header_visible = False
            if hasattr(self.fig.canvas, 'toolbar_visible'):
                self.fig.canvas.toolbar_visible = False
            
            plt.show()
    
    def update(self):
        """Update the plot with current model data (efficient refresh)."""
        if self.fig is None or self.ax_strain is None or self.ax_stress is None:
            self._create_figure()
        
        # Clear both axes
        self.ax_strain.clear()
        self.ax_stress.clear()
        
        # Clear and recreate the twin axis to avoid accumulating tick marks
        if self.ax_stress_twin is not None:
            self.ax_stress_twin.remove()
            self.ax_stress_twin = None
        
        # Replot with current data
        self._plot_strain_profile(self.ax_strain)
        self._plot_stress_profile(self.ax_stress)
        
        # Remove y-axis labels from right plot since they share the axis
        self.ax_stress.set_ylabel('')
        
        # Redraw the canvas
        self.fig.canvas.draw_idle()
    
    def _plot_stress_profile(self, ax):
        """Plot stress distribution with forces on primary x-axis."""
        heights_c, stresses_c, heights_s, stresses_s = self.model.get_stress_profile()
        
        # Base stress scale on compressive strength with factor
        f_cd = self.model.f_ck / 1.5  # Design compressive strength
        max_stress = abs(f_cd) * 2.5  # Use 2.5x compressive strength for scale
        
        # Force range - primary axis
        max_force = max(abs(self.model.F_cd), abs(self.model.F_sd))
        
        # Scale factor: map stress to force axis
        stress_to_force_scale = max_force / max_stress if max_stress > 0 else 1.0
        
        # Concrete stress (plot as negative for compression, scaled to force axis)
        if len(heights_c) > 0:
            stresses_c_scaled = stresses_c * stress_to_force_scale
            ax.fill_betweenx(heights_c, 0, stresses_c_scaled, alpha=0.15, color='steelblue',
                           label='Compression zone')
            ax.plot(stresses_c_scaled, heights_c, 'b-', linewidth=3, label='Concrete stress')
            
            max_idx = np.argmax(np.abs(stresses_c))
        
        # Zero line
        ax.axvline(x=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Horizontal reference lines spanning full width (plot BEFORE arrows so they appear below)
        # Mid-height level (where N_Ed is positioned) - below everything
        mid_height = self.model.h / 2
        ax.axhline(y=mid_height, color='gray', linestyle='-', alpha=0.5, linewidth=1.0, zorder=0)
        
        # Compression level (at center of gravity)
        force_height_c = self.model.h - self.model.a
        ax.axhline(y=force_height_c, color='black', linestyle='--', alpha=0.7, linewidth=1.5, zorder=1)
        
        # Neutral axis (at height h-x from bottom)
        ax.axhline(y=self.model.h - self.model.x, color='darkgreen', linestyle='--', alpha=0.7,
                  linewidth=1.5, label=f'Neutral axis', zorder=1)
        
        # Reinforcement level
        ax.axhline(y=self.model.c_nom, color='black', linestyle='--', alpha=0.7, linewidth=1.5, zorder=1)
        
        # Set up twin x-axis for stress and store it
        self.ax_stress_twin = ax.twiny()
        
        # Label offset from arrow (increased by factor 1.4)
        label_offset = 0.028  # vertical offset from arrow: 0.02 * 1.4
        
        # External force N_Ed (at mid-height) - compression is negative
        if self.model.N_Ed != 0:
            mid_height = self.model.h / 2
            arrow_len = self.model.N_Ed
            ax.arrow(0, mid_height, arrow_len, 0, head_width=0.02, head_length=0.02,
                    fc='dimgray', ec='black', linewidth=4, length_includes_head=True, zorder=2)
            ax.text(arrow_len, mid_height + label_offset, 
                    f'N_Ed = {self.model.N_Ed:.3f} MN',
                    ha='right', va='bottom', fontsize=11, color='black',
                    bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.15, edgecolor='black', linewidth=1.0))
        
        # Compression force (at center of gravity: height h-a from bottom, where a is from top)
        if self.model.F_cd > 0:
            arrow_len = -self.model.F_cd
            ax.arrow(0, force_height_c, arrow_len, 0, head_width=0.02, head_length=0.02,
                    fc='cornflowerblue', ec='royalblue', linewidth=4, length_includes_head=True, zorder=2)
            
            # Combined label for F_cd and σ_cd
            if len(stresses_c) > 0:
                combined_text = f'F_cd = -{self.model.F_cd:.3f} MN\nσ_cd = {stresses_c[max_idx]:.1f} MPa'
            else:
                combined_text = f'F_cd = -{self.model.F_cd:.3f} MN'
            ax.text(arrow_len, force_height_c - label_offset, 
                    combined_text,
                    ha='left', va='top', fontsize=11, color='black',
                    bbox=dict(boxstyle='round', facecolor='steelblue', alpha=0.15, edgecolor='black', linewidth=1.0))
        
        # Tension force (at steel level: c_nom from bottom)
        if self.model.F_sd > 0:
            arrow_len = self.model.F_sd
            ax.arrow(0, self.model.c_nom, arrow_len, 0, head_width=0.02, head_length=0.02,
                    fc='coral', ec='firebrick', linewidth=4, length_includes_head=True, zorder=2)
            
            # Combined label for F_sd, F_cd, σ_sd, and A_s
            A_s_cm2 = self.model.A_s_cm2 if hasattr(self.model, 'A_s_cm2') else 0
            if len(stresses_s) > 0:
                combined_text = f'F_sd = F_cd = {self.model.F_sd:.3f} MN\nσ_sd = {stresses_s[0]:.1f} MPa\n$\\mathbf{{A_s = {A_s_cm2:.2f}~cm²}}$'
            else:
                combined_text = f'F_sd = F_cd = {self.model.F_sd:.3f} MN\n$\\mathbf{{A_s = {A_s_cm2:.2f}~cm²}}$'
            ax.text(arrow_len, self.model.c_nom + label_offset, 
                    combined_text,
                    ha='right', va='bottom', fontsize=11, color='black',
                    bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.15, edgecolor='black', linewidth=1.0))
        
        # Lever arm (between compression and tension forces) - at 1/4 distance to max force
        lever_x = max_force * 0.25
        # Use orange color for dimension line to make it distinct
        ax.plot([lever_x, lever_x], [force_height_c, self.model.c_nom], color='orange', 
                linestyle='-', linewidth=0.8, alpha=0.6, zorder=2)
        ax.annotate('', xy=(lever_x, force_height_c), xytext=(lever_x, self.model.c_nom),
                   arrowprops=dict(arrowstyle='<->', color='orange', lw=1.5), zorder=2)
        ax.text(lever_x + label_offset, (force_height_c + self.model.c_nom)/2, f'z = {self.model.z:.3f} m',
               rotation=90, va='center', ha='left', fontsize=11, color='black',
               bbox=dict(boxstyle='round', facecolor='orange', alpha=0.4, edgecolor='black', linewidth=1.0))
        
        # Disbalance force indicator (for unbalanced models)
        if hasattr(self.model, 'force_imbalance'):
            # Correct sign: F_sd - F_cd (tension minus compression)
            delta_F = -self.model.force_imbalance  # Negate to get F_sd - F_cd
            # Display as filled rectangle in cover area (half-height of c_nom)
            bar_height = self.model.c_nom / 2
            bar_bottom = 0
            bar_top = bar_bottom + bar_height
            
            # Use salmon color to indicate unacceptable state (fully opaque)
            if abs(delta_F) > 0.001:  # Show only if significant imbalance
                # Draw filled rectangle
                from matplotlib.patches import Rectangle
                rect = Rectangle((0, bar_bottom), delta_F, bar_height,
                                facecolor='lightsalmon', edgecolor='red', 
                                linewidth=2, alpha=1.0, zorder=3)
                ax.add_patch(rect)
                
                # Add label for disbalance force (positioned above the bar)
                ax.text(delta_F / 2, bar_top + label_offset, 
                       f'ΔF = {delta_F:.3f} MN',
                       ha='center', va='bottom', fontsize=12, color='darkred',
                       fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='white', 
                                alpha=0.8, edgecolor='black', linewidth=1.0))
        
        # Configure axes - force is primary (bottom), stress is twin (top)
        ax.set_ylabel('height [m]', fontsize=11)
        ax.set_xlabel('force [MN]', fontsize=11, color='black')
        self.ax_stress_twin.set_xlabel('(compression ← stress [MPa] → tension)', fontsize=11, color='black')
        self.ax_stress_twin.tick_params(axis='x', labelcolor='black', labelsize=11)
        ax.tick_params(labelsize=11)
        
        ax.set_title('stress distribution & force resultants', fontsize=11)
        # ax.legend(fontsize=11, loc='lower left')  # Legend removed as requested
        
        # Set y-limits: max at cross-section height, no extra space
        ax.set_ylim(0, self.model.h)
        
        # Set x-limits - force axis controls visual range (20% wider)
        ax.set_xlim(-max_force * 1.35, max_force * 1.35)
        self.ax_stress_twin.set_xlim(-max_stress * 1.35, max_stress * 1.35)
        
        # Get M_Eds if available
        M_Rd = self.model.M_Rds
        M_Eds = self.model.M_Eds if hasattr(self.model, 'M_Eds') else self.model.M_Ed
        
        
        M_Ed_label = 'M_Eds' if hasattr(self.model, 'M_Eds') else 'M_Ed'
        delta_M = M_Rd - M_Eds
        
        # Determine box background color based on Delta M (green if safe, red if unsafe)
        box_bg_color = 'lightgreen' if delta_M >= 0 else 'lightcoral'
        
        # Position box in bottom-left area
        # Horizontal: center between left boundary and zero force level
        x_pos = -max_force * 1.35 / 2
        # Vertical: center between reinforcement level (c_nom) and mid-axis (h/2)
        z_s1 = self.model.z_s1 if hasattr(self.model, 'z_s1') else (self.model.h / 2 - self.model.c_nom)
        y_pos = self.model.c_nom + z_s1 / 2
        
        # Add M_Rd ≤ M_Eds label with three lines
        label_text = f'M_Rd ≤ {M_Ed_label}\n{M_Rd:.3f} ≤ {M_Eds:.3f} [MNm]\n$\\mathbf{{ΔM = {delta_M:.3f}~[MNm]}}$'
        ax.text(x_pos, y_pos,
                label_text,
                ha='center', va='center', fontsize=11, color='black',
                bbox=dict(boxstyle='round', facecolor=box_bg_color, alpha=0.6, edgecolor='black', linewidth=1.0))
    
    def _plot_strain_profile(self, ax):
        """Plot strain distribution."""
        heights, strains = self.model.get_strain_profile()
        strains_milli = strains * 1000
        
        # Separate compression and tension zones
        neutral_axis_height = self.model.h - self.model.x
        
        # Compression zone (negative strain, above neutral axis)
        compression_mask = heights >= neutral_axis_height
        if np.any(compression_mask):
            heights_c = heights[compression_mask]
            strains_c = strains_milli[compression_mask]
            ax.fill_betweenx(heights_c, 0, strains_c, alpha=0.15, color='steelblue')
            ax.plot(strains_c, heights_c, 'b-', linewidth=3)
        
        # Tension zone (positive strain, below neutral axis)
        tension_mask = heights <= neutral_axis_height
        if np.any(tension_mask):
            heights_t = heights[tension_mask]
            strains_t = strains_milli[tension_mask]
            ax.fill_betweenx(heights_t, 0, strains_t, alpha=0.15, color='lightcoral')
            ax.plot(strains_t, heights_t, 'r-', linewidth=3)
        
        # Key points markers (without labels)
        ax.plot([self.model.epsilon_cu2 * 1000], [self.model.h], 'bs', markersize=10)
        ax.plot([self.model.epsilon_s1 * 1000], [self.model.c_nom], 'ro', markersize=10)
        
        # Zero strain line
        ax.axvline(x=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Horizontal reference lines
        # Mid-height level
        mid_height = self.model.h / 2
        ax.axhline(y=mid_height, color='gray', linestyle='-', alpha=0.5, linewidth=1.0)
        
        # Neutral axis (at height h-x from bottom)
        ax.axhline(y=neutral_axis_height, color='darkgreen', linestyle='--', alpha=0.7, linewidth=1.5)
        
        # Reinforcement level
        ax.axhline(y=self.model.c_nom, color='black', linestyle='--', alpha=0.7, linewidth=1.5)
        
        # Label boxes with strain values
        label_offset = 0.028
        
        # Calculate horizontal offset from zero line (same as vertical offset from boundaries)
        min_strain = strains_milli.min()
        max_strain = strains_milli.max()
        strain_range = max_strain - min_strain
        horizontal_offset = strain_range * 0.05  # Small offset from zero line
        
        # Compression strain label at top, to the right of zero line
        ax.text(horizontal_offset, self.model.h - label_offset, 
                f'ε_c2 = {self.model.epsilon_cu2 * 1000:.2f} ‰\n$\\mathbf{{given}}$',
                ha='left', va='top', fontsize=11, color='black',
                bbox=dict(boxstyle='round', facecolor='steelblue', alpha=0.15, 
                         edgecolor='black', linewidth=1.0))
        
        # Tension strain label at steel level, to the left of zero line
        ax.text(-horizontal_offset, self.model.c_nom + label_offset, 
                f'ε_s1 = {self.model.epsilon_s1 * 1000:.2f} ‰\n$\\mathbf{{unknown}}$',
                ha='right', va='bottom', fontsize=11, color='black',
                bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.15, 
                         edgecolor='black', linewidth=1.0))
        
        ax.set_ylabel('Height [m]', fontsize=11)
        ax.set_xlabel('Strain [‰]', fontsize=11)
        ax.set_title('Strain Distribution', fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=11)
        
        # Set x-limits based on actual strain range with margin
        margin = strain_range * 0.2
        ax.set_xlim(min_strain - margin, max_strain + margin)
        
        # Set y-limits to match stress plot
        ax.set_ylim(0, self.model.h)


class ResultsSummarySubWidget:
    """Subwidget for results summary display."""
    
    def __init__(self, model: RCModel):
        self.model = model
        self.output = widgets.Output()
        
    def update(self):
        """Update results table."""
        with self.output:
            clear_output(wait=True)
            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
            self._plot_results(ax)
            plt.tight_layout()
            plt.show()
    
    def _plot_results(self, ax):
        """Display results in table format."""
        ax.axis('off')
        
        data = [
            ['Parameter', 'Value', 'Unit'],
            ['─' * 30, '─' * 15, '─' * 10],
            ['Concrete comp. strain ε_c2', f"{self.model.epsilon_cu2:.4f}", '[-]'],
            ['Steel tensile strain ε_s1', f"{self.model.epsilon_s1:.4f}", '[-]'],
            ['Neutral axis depth x', f"{self.model.x:.3f}", '[m]'],
            ['Lever arm z', f"{self.model.z:.3f}", '[m]'],
            ['Concrete force F_cd', f"{self.model.F_cd:.3f}", '[MN]'],
            ['Steel force F_sd', f"{self.model.F_sd:.3f}", '[MN]'],
            ['Resisting moment M_Rds', f"{self.model.M_Rds:.3f}", '[MN·m]'],
            ['─' * 30, '─' * 15, '─' * 10],
            ['Required steel area A_s', f"{self.model.A_s_cm2:.2f}", '[cm²]'],
        ]
        
        table = ax.table(cellText=data, cellLoc='left', loc='center',
                        colWidths=[0.5, 0.3, 0.2])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)
        
        # Style header
        for i in range(3):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')
        
        # Style result row
        table[(10, 0)].set_text_props(weight='bold', size=11)
        table[(10, 1)].set_text_props(weight='bold', size=11, color='red')
        for i in range(3):
            table[(10, i)].set_facecolor('#FFF9C4')
        
        ax.set_title('Analysis Results', fontsize=12, weight='bold', pad=20)


class BalancedModelInputWidget:
    """
    Input parameter widget for RCBendingModelMN (balanced model).
    
    Provides sliders for all input parameters with automatic update
    of the visualization widget.
    """
    
    def __init__(self, model: RCBendingModelMN, viz_widget: StressStrainProfileSubWidget):
        """
        Initialize input widget.
        
        Parameters:
        -----------
        model : RCBendingModelMN
            The balanced model to control
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        """
        self.model = model
        self.viz_widget = viz_widget
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all input sliders with descriptions and tooltips."""
        
        # Geometry sliders
        self.M_Ed_slider = widgets.FloatSlider(
            value=self.model.M_Ed,
            min=0.05, max=1.0, step=0.01,
            description='M_Ed [MN·m]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Design bending moment acting on the cross-section'
        )
        
        self.N_Ed_slider = widgets.FloatSlider(
            value=self.model.N_Ed,
            min=-0.5, max=0.5, step=0.01,
            description='N_Ed [MN]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Design normal force (positive = tension, negative = compression)'
        )
        
        self.d_slider = widgets.FloatSlider(
            value=self.model.d,
            min=0.20, max=1.0, step=0.01,
            description='d [m]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Effective depth: distance from top to reinforcement centroid'
        )
        
        self.b_slider = widgets.FloatSlider(
            value=self.model.b,
            min=0.15, max=0.60, step=0.01,
            description='b [m]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Width of rectangular cross-section'
        )
        
        self.c_nom_slider = widgets.FloatSlider(
            value=self.model.c_nom,
            min=0.02, max=0.10, step=0.005,
            description='c_nom [m]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Nominal concrete cover to reinforcement'
        )
        
        # Material sliders
        self.f_ck_slider = widgets.FloatSlider(
            value=self.model.f_ck,
            min=20, max=50, step=5,
            description='f_ck [MPa]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Characteristic concrete compressive strength (cylinder)'
        )
        
        self.f_yk_slider = widgets.FloatSlider(
            value=self.model.f_yk,
            min=400, max=600, step=50,
            description='f_yk [MPa]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Characteristic yield strength of reinforcement steel'
        )
        
        # Observe changes
        for slider in [self.M_Ed_slider, self.N_Ed_slider, self.d_slider, 
                      self.b_slider, self.c_nom_slider, self.f_ck_slider, self.f_yk_slider]:
            slider.observe(self._on_value_change, names='value')
        
        # Layout
        loading_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px;">Loading</h4>'),
            self.M_Ed_slider,
            self.N_Ed_slider
        ])
        
        geometry_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px;">Geometry</h4>'),
            self.d_slider,
            self.b_slider,
            self.c_nom_slider
        ])
        
        materials_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px;">Materials</h4>'),
            self.f_ck_slider,
            self.f_yk_slider
        ])
        
        self.layout = widgets.HBox([loading_box, geometry_box, materials_box],
                                   layout=widgets.Layout(padding='10px'))
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        # Update model
        self.model.M_Ed = self.M_Ed_slider.value
        self.model.N_Ed = self.N_Ed_slider.value
        self.model.d = self.d_slider.value
        self.model.b = self.b_slider.value
        self.model.c_nom = self.c_nom_slider.value
        self.model.f_ck = self.f_ck_slider.value
        self.model.f_yk = self.f_yk_slider.value
        
        # Update visualization
        self.viz_widget.update()


class UnbalancedModelInputWidget:
    """
    Input parameter widget for RCBendingUnbalancedModel (trial-and-error model).
    
    Provides sliders for geometry, materials, strains, and steel area
    with automatic update of the visualization widget.
    """
    
    def __init__(self, model: RCBendingUnbalancedModel, viz_widget: StressStrainProfileSubWidget):
        """
        Initialize input widget.
        
        Parameters:
        -----------
        model : RCBendingUnbalancedModel
            The unbalanced model to control
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        """
        self.model = model
        self.viz_widget = viz_widget
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all input sliders with descriptions and tooltips."""
        
        # Geometry sliders
        self.d_slider = widgets.FloatSlider(
            value=self.model.d,
            min=0.20, max=1.0, step=0.01,
            description='d [m]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Effective depth: distance from top to reinforcement centroid'
        )
        
        self.b_slider = widgets.FloatSlider(
            value=self.model.b,
            min=0.15, max=0.60, step=0.01,
            description='b [m]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Width of rectangular cross-section'
        )
        
        self.c_nom_slider = widgets.FloatSlider(
            value=self.model.c_nom,
            min=0.02, max=0.10, step=0.005,
            description='c_nom [m]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Nominal concrete cover to reinforcement'
        )
        
        # Material sliders
        self.f_ck_slider = widgets.FloatSlider(
            value=self.model.f_ck,
            min=20, max=50, step=5,
            description='f_ck [MPa]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Characteristic concrete compressive strength (cylinder)'
        )
        
        self.f_yk_slider = widgets.FloatSlider(
            value=self.model.f_yk,
            min=400, max=600, step=50,
            description='f_yk [MPa]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Characteristic yield strength of reinforcement steel'
        )
        
        # Strain state sliders (key for unbalanced model)
        self.epsilon_c_top_slider = widgets.FloatSlider(
            value=self.model.epsilon_c_top,
            min=-0.0050, max=-0.0010, step=0.0001,
            description='ε_c,top [-]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            readout_format='.4f',
            tooltip='Compressive strain at top fiber (negative for compression)'
        )
        
        self.epsilon_s_bottom_slider = widgets.FloatSlider(
            value=self.model.epsilon_s_bottom,
            min=0.0000, max=0.0100, step=0.0001,
            description='ε_s,bottom [-]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            readout_format='.4f',
            tooltip='Tensile strain at reinforcement level (positive for tension)'
        )
        
        self.A_s_slider = widgets.FloatSlider(
            value=self.model.A_s_cm2,
            min=5.0, max=50.0, step=0.5,
            description='A_s [cm²]:',
            style={'description_width': '120px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Steel reinforcement area'
        )
        
        # Equilibrium check display
        self.equilibrium_output = widgets.HTML(
            layout=widgets.Layout(width='500px', padding='10px')
        )
        self._update_equilibrium_display()
        
        # Observe changes
        for slider in [self.d_slider, self.b_slider, self.c_nom_slider,
                      self.f_ck_slider, self.f_yk_slider, 
                      self.epsilon_c_top_slider, self.epsilon_s_bottom_slider,
                      self.A_s_slider]:
            slider.observe(self._on_value_change, names='value')
        
        # Layout
        geometry_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px;">Geometry</h4>'),
            self.d_slider,
            self.b_slider,
            self.c_nom_slider
        ])
        
        materials_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px;">Materials</h4>'),
            self.f_ck_slider,
            self.f_yk_slider
        ])
        
        strains_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px;">Strain State (Trial Values)</h4>'),
            self.epsilon_c_top_slider,
            self.epsilon_s_bottom_slider,
            self.A_s_slider,
            widgets.HTML('<h4 style="margin-bottom: 5px;">Equilibrium Check</h4>'),
            self.equilibrium_output
        ])
        
        self.layout = widgets.HBox([geometry_box, materials_box, strains_box],
                                   layout=widgets.Layout(padding='10px'))
    
    def _update_equilibrium_display(self):
        """Update the equilibrium check display."""
        force_imb = self.model.force_imbalance
        # Use M_Rd - M_Eds for consistency with stress profile plots
        M_Rd = self.model.M_Rds if hasattr(self.model, 'M_Rds') else self.model.M_Rd
        M_Eds = self.model.M_Eds if hasattr(self.model, 'M_Eds') else self.model.M_Ed
        moment_imb = M_Rd - M_Eds
        
        moment_color = 'green' if abs(moment_imb) < 0.001 else 'orange'
        
        html_content = f"""
        <div style="border: 1px solid #bbb; padding: 10px; background-color: #e8e8e8; border-radius: 5px;">
            <p style="margin: 5px 0;"><b>Moment balance:</b> 
               <span style="color: {moment_color}; font-weight: bold;">
               ΔM = {moment_imb:.4f} MN·m
               </span>
            </p>
            <p style="margin: 5px 0; font-size: 11px; color: #666;">
               <i>Target: both values close to zero for equilibrium</i>
            </p>
        </div>
        """
        self.equilibrium_output.value = html_content
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        # Update model
        self.model.d = self.d_slider.value
        self.model.b = self.b_slider.value
        self.model.c_nom = self.c_nom_slider.value
        self.model.f_ck = self.f_ck_slider.value
        self.model.f_yk = self.f_yk_slider.value
        self.model.epsilon_c_top = self.epsilon_c_top_slider.value
        self.model.epsilon_s_bottom = self.epsilon_s_bottom_slider.value
        self.model.A_s_cm2 = self.A_s_slider.value
        
        # Update equilibrium display
        self._update_equilibrium_display()
        
        # Update visualization
        self.viz_widget.update()


class DesignWidget:
    """
    Design input widget for geometry and material parameters.
    
    Organized in two columns: Geometry | Materials
    Optionally includes loading parameters for balanced model.
    Works with both RCBendingModelMN and RCBendingUnbalancedModel.
    """
    
    def __init__(self, model: RCModel, viz_widget: StressStrainProfileSubWidget, include_loading: bool = False):
        """
        Initialize design widget.
        
        Parameters:
        -----------
        model : RCModel
            The model to control (balanced or unbalanced)
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        include_loading : bool
            If True, includes M_Ed and N_Ed sliders (needed for balanced model)
        """
        self.model = model
        self.viz_widget = viz_widget
        self.include_loading = include_loading
        self._create_widgets()
    
    def _create_widgets(self):
        """Create geometry and material sliders in two-column layout."""
        
        # Loading sliders (optional, for balanced model)
        if self.include_loading:
            self.M_Ed_slider = widgets.FloatSlider(
                value=self.model.M_Ed,
                min=0.05, max=1.0, step=0.01,
                description='M_Ed [MN·m]:',
                style={'description_width': '110px'},
                layout=widgets.Layout(width='400px'),
                tooltip='Design bending moment acting on the cross-section'
            )
            
            self.N_Ed_slider = widgets.FloatSlider(
                value=self.model.N_Ed,
                min=-0.5, max=0.5, step=0.01,
                description='N_Ed [MN]:',
                style={'description_width': '110px'},
                layout=widgets.Layout(width='400px'),
                tooltip='Design normal force (positive = tension, negative = compression)'
            )
        
        # Geometry sliders
        self.d_slider = widgets.FloatSlider(
            value=self.model.d,
            min=0.20, max=1.0, step=0.01,
            description='d [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Effective depth: distance from top to reinforcement centroid'
        )
        
        self.b_slider = widgets.FloatSlider(
            value=self.model.b,
            min=0.15, max=0.60, step=0.01,
            description='b [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Width of rectangular cross-section'
        )
        
        self.c_nom_slider = widgets.FloatSlider(
            value=self.model.c_nom,
            min=0.02, max=0.10, step=0.005,
            description='c_nom [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Nominal concrete cover to reinforcement'
        )
        
        # Material sliders
        self.f_ck_slider = widgets.FloatSlider(
            value=self.model.f_ck,
            min=20, max=50, step=5,
            description='f_ck [MPa]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Characteristic concrete compressive strength (cylinder)'
        )
        
        self.f_yk_slider = widgets.FloatSlider(
            value=self.model.f_yk,
            min=400, max=600, step=50,
            description='f_yk [MPa]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Characteristic yield strength of reinforcement steel'
        )
        
        # Observe changes
        sliders = [self.d_slider, self.b_slider, self.c_nom_slider,
                  self.f_ck_slider, self.f_yk_slider]
        if self.include_loading:
            sliders.extend([self.M_Ed_slider, self.N_Ed_slider])
        
        for slider in sliders:
            slider.observe(self._on_value_change, names='value')
        
        # Build geometry box
        geometry_items = [widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Geometry</h4>')]
        if self.include_loading:
            geometry_items.extend([self.M_Ed_slider, self.N_Ed_slider, 
                                 widgets.HTML('<hr style="margin: 10px 0;">')])
        geometry_items.extend([self.d_slider, self.b_slider, self.c_nom_slider])
        
        geometry_box = widgets.VBox(geometry_items, layout=widgets.Layout(padding='10px'))
        
        materials_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Materials</h4>'),
            self.f_ck_slider,
            self.f_yk_slider
        ], layout=widgets.Layout(padding='10px'))
        
        self.layout = widgets.HBox(
            [geometry_box, materials_box],
            layout=widgets.Layout(
                padding='15px',
                border='2px solid #3498db',
                border_radius='5px',
                margin='5px'
            )
        )
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        # Update model
        if self.include_loading:
            self.model.M_Ed = self.M_Ed_slider.value
            self.model.N_Ed = self.N_Ed_slider.value
        self.model.d = self.d_slider.value
        self.model.b = self.b_slider.value
        self.model.c_nom = self.c_nom_slider.value
        self.model.f_ck = self.f_ck_slider.value
        self.model.f_yk = self.f_yk_slider.value
        
        # Update visualization
        self.viz_widget.update()


class LoadingWidget:
    """
    Loading input widget for design actions.
    
    Contains sliders for M_Ed (design bending moment) and N_Ed (design normal force).
    """
    
    def __init__(self, model: RCModel, viz_widget: StressStrainProfileSubWidget):
        """
        Initialize loading widget.
        
        Parameters:
        -----------
        model : RCModel
            The model to control
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        """
        self.model = model
        self.viz_widget = viz_widget
        self._create_widgets()
    
    def _create_widgets(self):
        """Create loading sliders."""
        
        self.M_Ed_slider = widgets.FloatSlider(
            value=self.model.M_Ed,
            min=0.05, max=1.0, step=0.01,
            description='M_Ed [MN·m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Design bending moment acting on the cross-section'
        )
        
        self.N_Ed_slider = widgets.FloatSlider(
            value=self.model.N_Ed,
            min=-0.5, max=0.5, step=0.01,
            description='N_Ed [MN]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='500px'),
            tooltip='Design normal force (positive = tension, negative = compression)'
        )
        
        # Observe changes
        self.M_Ed_slider.observe(self._on_value_change, names='value')
        self.N_Ed_slider.observe(self._on_value_change, names='value')
        
        # Info display for M_Eds
        self.info_html = widgets.HTML()
        self._update_info()
        
        self.layout = widgets.VBox(
            [self.M_Ed_slider, self.N_Ed_slider, self.info_html],
            layout=widgets.Layout(
                padding='15px',
                border='2px solid #e67e22',
                border_radius='5px',
                margin='5px'
            )
        )
    
    def _update_info(self):
        """Update the info display."""
        z_s1 = self.model.z_s1
        M_Eds = self.model.M_Eds
        
        self.info_html.value = f"""
        <div style="border: 1px solid #bbb; padding: 10px; background-color: #e8e8e8; border-radius: 5px; margin-top: 8px;">
            <b>Design moment at steel level:</b><br>
            z_s1 = h/2 - c_nom = {z_s1:.3f} m<br>
            M_Eds = M_Ed + N_Ed × z_s1 = {M_Eds:.3f} MN·m
        </div>
        """
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        self.model.M_Ed = self.M_Ed_slider.value
        self.model.N_Ed = self.N_Ed_slider.value
        
        # Update info display
        self._update_info()
        
        # Update visualization
        self.viz_widget.update()


class GeometryWidget:
    """
    Geometry input widget for cross-section dimensions.
    
    Contains sliders for d, b, and c_nom.
    """
    
    def __init__(self, model: RCModel, viz_widget: StressStrainProfileSubWidget, include_loading: bool = False, loading_widget=None):
        """
        Initialize geometry widget.
        
        Parameters:
        -----------
        model : RCModel
            The model to control
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        include_loading : bool
            If True, includes M_Ed and N_Ed sliders
        loading_widget : LoadingWidget, optional
            The loading widget to update when geometry changes (for M_Eds calculation)
        """
        self.model = model
        self.viz_widget = viz_widget
        self.include_loading = include_loading
        self.loading_widget = loading_widget
        self._create_widgets()
    
    def _create_widgets(self):
        """Create geometry sliders and visualization."""
        
        # Geometry visualization output
        self.geometry_plot_output = widgets.Output(
            layout=widgets.Layout(width='350px', height='350px')
        )
        self._update_geometry_plot()
        
        # Loading sliders (optional, for balanced model)
        items = []
        
        if self.include_loading:
            self.M_Ed_slider = widgets.FloatSlider(
                value=self.model.M_Ed,
                min=0.05, max=1.0, step=0.01,
                description='M_Ed [MN·m]:',
                style={'description_width': '110px'},
                layout=widgets.Layout(width='400px'),
                tooltip='Design bending moment acting on the cross-section'
            )
            
            self.N_Ed_slider = widgets.FloatSlider(
                value=self.model.N_Ed,
                min=-0.5, max=0.5, step=0.01,
                description='N_Ed [MN]:',
                style={'description_width': '110px'},
                layout=widgets.Layout(width='400px'),
                tooltip='Design normal force (positive = tension, negative = compression)'
            )
            items.extend([self.M_Ed_slider, self.N_Ed_slider,
                         widgets.HTML('<hr style="margin: 10px 0;">')])
        
        # Geometry sliders
        self.d_slider = widgets.FloatSlider(
            value=self.model.d,
            min=0.20, max=1.0, step=0.01,
            description='d [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Effective depth: distance from top to reinforcement centroid'
        )
        
        self.b_slider = widgets.FloatSlider(
            value=self.model.b,
            min=0.15, max=0.60, step=0.01,
            description='b [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Width of rectangular cross-section'
        )
        
        self.c_nom_slider = widgets.FloatSlider(
            value=self.model.c_nom,
            min=0.02, max=0.10, step=0.005,
            description='c_nom [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Nominal concrete cover to reinforcement'
        )
        
        items.extend([self.d_slider, self.b_slider, self.c_nom_slider])
        
        # Observe changes
        sliders = [self.d_slider, self.b_slider, self.c_nom_slider]
        if self.include_loading:
            sliders.extend([self.M_Ed_slider, self.N_Ed_slider])
        
        for slider in sliders:
            slider.observe(self._on_value_change, names='value')
        
        # Create two-column layout: sliders on left, plot on right
        sliders_box = widgets.VBox(
            items,
            layout=widgets.Layout(padding='10px')
        )
        
        plot_box = widgets.VBox(
            [self.geometry_plot_output],
            layout=widgets.Layout(padding='10px')
        )
        
        self.layout = widgets.HBox(
            [sliders_box, plot_box],
            layout=widgets.Layout(
                padding='15px',
                border='2px solid #3498db',
                border_radius='5px',
                margin='5px'
            )
        )
    
    def _update_geometry_plot(self):
        """Update the cross-section geometry plot."""
        with self.geometry_plot_output:
            clear_output(wait=True)
            fig, ax = plt.subplots(1, 1, figsize=(3.3, 3.3), dpi=100)
            self._plot_geometry(ax)
            plt.tight_layout(pad=0.3)
            # Hide the figure title
            if hasattr(fig.canvas, 'header_visible'):
                fig.canvas.header_visible = False
            plt.show()
    
    def _plot_geometry(self, ax):
        """Plot cross-section geometry with dimensions."""
        d = self.model.d
        b = self.model.b
        h = self.model.h
        c_nom = self.model.c_nom
        # Calculate reinforcement position from bottom (distance from top is h - d)
        d_s1 = h - d
        
        # Draw concrete section with thin black border
        rect = plt.Rectangle((0, 0), b, h, fill=True, facecolor='lightgray',
                            edgecolor='black', linewidth=1, alpha=1.0)
        ax.add_patch(rect)
        
        # Draw reinforcement bars (schematic)
        n_bars = 3
        bar_spacing = b / (n_bars + 1)
        for i in range(n_bars):
            x_bar = (i + 1) * bar_spacing
            ax.plot(x_bar, d_s1, 'ro', markersize=10, markeredgecolor='darkred',
                   markeredgewidth=2)
        
        # Add large question mark above reinforcement to indicate A_s is unknown
        question_mark_y = h / 3  # At 1/3 of height from bottom
        ax.text(b/2, question_mark_y, '?', ha='center', va='center',
               fontsize=60, fontweight='bold', color='red', alpha=0.4)
        
        # Dimensions - Effective depth d (from TOP to reinforcement)
        ax.annotate('', xy=(b + 0.05, h), xytext=(b + 0.05, c_nom),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
        ax.text(b + 0.08, h - d/2, f'd={d:.2f}m', rotation=90, va='center',
               fontsize=9, fontweight='bold', color='black')
        
        # Width b
        ax.annotate('', xy=(0, -0.03), xytext=(b, -0.03),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
        ax.text(b/2, -0.06, f'b={b:.2f}m', ha='center', fontsize=9,
               fontweight='bold', color='black')
        
        # Cover c_nom with black font
        ax.annotate('', xy=(-0.03, 0), xytext=(-0.03, c_nom),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
        ax.text(-0.06, c_nom/2, f'c_nom={c_nom:.3f}m', rotation=90,
               va='center', fontsize=7, fontweight='bold', color='black')
        
        ax.set_xlim(-0.15, b + 0.15)
        ax.set_ylim(-0.1, h + 0.05)
        ax.set_aspect('equal')
        # Remove axes, ticks, labels, title, legend, and grid
        ax.axis('off')
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        if self.include_loading:
            self.model.M_Ed = self.M_Ed_slider.value
            self.model.N_Ed = self.N_Ed_slider.value
        self.model.d = self.d_slider.value
        self.model.b = self.b_slider.value
        self.model.c_nom = self.c_nom_slider.value
        
        # Update geometry plot
        self._update_geometry_plot()
        
        # Update loading widget info (M_Eds depends on geometry)
        if self.loading_widget is not None:
            self.loading_widget._update_info()
        
        # Update visualization
        self.viz_widget.update()


class MaterialsWidget:
    """
    Materials widget showing characteristic and design values with safety factors.
    
    Layout: Characteristic values | Design values | Material stress-strain curves
    """
    
    def __init__(self, model: RCModel, viz_widget: StressStrainProfileSubWidget):
        """
        Initialize materials widget.
        
        Parameters:
        -----------
        model : RCModel
            The model to control
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        """
        self.model = model
        self.viz_widget = viz_widget
        self._create_widgets()
    
    def _create_widgets(self):
        """Create material sliders, design values display, and material law plots."""
        
        # Characteristic value sliders (left side)
        self.f_ck_slider = widgets.FloatSlider(
            value=self.model.f_ck,
            min=20, max=50, step=5,
            description='f_ck [MPa]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='350px'),
            tooltip='Characteristic concrete compressive strength (cylinder)'
        )
        
        self.f_yk_slider = widgets.FloatSlider(
            value=self.model.f_yk,
            min=400, max=600, step=50,
            description='f_yk [MPa]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='350px'),
            tooltip='Characteristic yield strength of reinforcement steel'
        )
        
        # Design values display (middle)
        self.design_values_output = widgets.HTML(
            layout=widgets.Layout(width='280px', padding='10px')
        )
        self._update_design_values_display()
        
        # Material law plots (right side)
        self.material_plots_output = widgets.Output(
            layout=widgets.Layout(width='840px', height='175px')
        )
        self._update_material_plots()
        
        # Observe changes
        self.f_ck_slider.observe(self._on_value_change, names='value')
        self.f_yk_slider.observe(self._on_value_change, names='value')
        
        # Layout
        left_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Characteristic Values</h4>'),
            self.f_ck_slider,
            self.f_yk_slider
        ], layout=widgets.Layout(padding='10px'))
        
        middle_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Design Values</h4>'),
            self.design_values_output
        ], layout=widgets.Layout(padding='10px'))
        
        right_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Constitutive Laws</h4>'),
            self.material_plots_output
        ], layout=widgets.Layout(padding='10px'))
        
        self.layout = widgets.HBox(
            [left_box, middle_box, right_box],
            layout=widgets.Layout(
                padding='15px',
                border='2px solid #3498db',
                border_radius='5px',
                margin='5px'
            )
        )
    
    def _update_design_values_display(self):
        """Update the design values display with safety factors."""
        f_cd = self.model.f_cd
        f_yd = self.model.sigma_yd
        gamma_c = self.model._gamma_c
        gamma_s = self.model._gamma_s
        
        html_content = f"""
        <div style="border: 1px solid #bbb; padding: 10px; background-color: #e8e8e8; border-radius: 5px;">
            <p style="margin: 5px 0;"><b>Concrete:</b></p>
            <p style="margin: 5px 0 5px 15px;">
               γ_c = {gamma_c:.2f}<br>
               <span style="font-weight: bold; color: #2980b9;">
               f_cd = {f_cd:.2f} MPa
               </span>
            </p>
            <hr style="margin: 10px 0;">
            <p style="margin: 5px 0;"><b>Steel:</b></p>
            <p style="margin: 5px 0 5px 15px;">
               γ_s = {gamma_s:.2f}<br>
               <span style="font-weight: bold; color: #2980b9;">
               f_yd = {f_yd:.2f} MPa
               </span>
            </p>
        </div>
        """
        self.design_values_output.value = html_content
    
    def _update_material_plots(self):
        """Update material constitutive law plots."""
        with self.material_plots_output:
            clear_output(wait=True)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 1.6), dpi=100)
            self._plot_concrete_law(ax1)
            self._plot_steel_law(ax2)
            plt.tight_layout(pad=0.3)
            # Hide the figure title (e.g., "Figure 2")
            if hasattr(fig.canvas, 'header_visible'):
                fig.canvas.header_visible = False
            plt.show()
    
    def _plot_concrete_law(self, ax):
        """Plot concrete stress-strain curve."""
        epsilon_c_range = np.linspace(-0.004, 0.0001, 200)
        sigma_c = self.model.get_concrete_stress_strain(epsilon_c_range)
        
        # Fill area under curve
        ax.fill_between(epsilon_c_range * 1000, 0, sigma_c, alpha=0.15, color='steelblue')
        ax.plot(epsilon_c_range * 1000, sigma_c, 'b-', linewidth=2.5,
               label='EC2')
        
        # Mark key points
        ax.plot([self.model.epsilon_cu2 * 1000], [-self.model.f_cd], 'ro',
               markersize=6, label=f'f_cd={self.model.f_cd:.1f}')
        
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε_c [‰]', fontsize=9)
        ax.set_ylabel('Stress σ_c [MPa]', fontsize=9)
        ax.set_title('Concrete', fontsize=11, fontweight='bold')
        ax.legend(fontsize=7, loc='lower right')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-4, 0.5)
        ax.tick_params(labelsize=8)
    
    def _plot_steel_law(self, ax):
        """Plot steel stress-strain curve."""
        epsilon_s_range = np.linspace(0, 0.025, 200)
        sigma_s = self.model.get_steel_stress_strain(epsilon_s_range)
        
        # Fill area under curve
        ax.fill_between(epsilon_s_range * 1000, 0, sigma_s, alpha=0.15, color='lightcoral')
        ax.plot(epsilon_s_range * 1000, sigma_s, 'r-', linewidth=2.5,
               label='Bilinear')
        
        # Mark yield point
        ax.plot([self.model.epsilon_yd * 1000], [self.model.sigma_yd], 'ro',
               markersize=6, label=f'f_yd={self.model.sigma_yd:.0f}')
        
        ax.axhline(y=self.model.sigma_yd, color='r', linestyle='--', linewidth=1, alpha=0.4)
        ax.set_xlabel('Strain ε_s [‰]', fontsize=9)
        ax.set_ylabel('Stress σ_s [MPa]', fontsize=9)
        ax.set_title('Steel', fontsize=11, fontweight='bold')
        ax.legend(fontsize=7, loc='lower right')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, self.model.sigma_yd * 1.2)
        ax.tick_params(labelsize=8)
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        self.model.f_ck = self.f_ck_slider.value
        self.model.f_yk = self.f_yk_slider.value
        
        # Update design values display
        self._update_design_values_display()
        
        # Update material plots
        self._update_material_plots()
        
        # Update visualization
        self.viz_widget.update()


class AssessmentResultWidget:
    """
    Assessment result widget showing required reinforcement and moment capacity.
    
    Displays:
    - Required reinforcement area: A_s = F_sd / f_yd
    - Moment capacity check: M_Rd >= M_Ed
    """
    
    def __init__(self, model: RCModel, viz_widget: StressStrainProfileSubWidget):
        """
        Initialize assessment result widget.
        
        Parameters:
        -----------
        model : RCModel
            The model providing results
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to monitor for updates
        """
        self.model = model
        self.viz_widget = viz_widget
        self._create_widgets()
    
    def _create_widgets(self):
        """Create assessment results display."""
        
        self.reinforcement_output = widgets.HTML(
            layout=widgets.Layout(width='310px', padding='10px')
        )
        self.capacity_output = widgets.HTML(
            layout=widgets.Layout(width='310px', padding='10px')
        )
        self.utilization_output = widgets.HTML(
            layout=widgets.Layout(width='310px', padding='10px')
        )
        self.state_output = widgets.HTML(
            layout=widgets.Layout(width='310px', padding='10px')
        )
        self.update()
        
        # Four boxes side by side
        box1 = widgets.VBox([self.reinforcement_output], layout=widgets.Layout(padding='5px'))
        box2 = widgets.VBox([self.capacity_output], layout=widgets.Layout(padding='5px'))
        box3 = widgets.VBox([self.utilization_output], layout=widgets.Layout(padding='5px'))
        box4 = widgets.VBox([self.state_output], layout=widgets.Layout(padding='5px'))
        
        self.layout = widgets.HBox(
            [box1, box2, box3, box4],
            layout=widgets.Layout(
                padding='15px',
                border='2px solid #27ae60',
                border_radius='5px',
                margin='5px'
            )
        )
    
    def update(self):
        """Update the assessment results display."""
        # Calculate required reinforcement
        if hasattr(self.model, 'F_sd'):
            F_sd = self.model.F_sd
            f_yd = self.model.sigma_yd
            A_s_required = (F_sd / f_yd) * 10000  # Convert m² to cm²
        else:
            A_s_required = 0
        
        # Get moment values - use M_Eds if available (unbalanced model)
        M_Rd = self.model.M_Rds if hasattr(self.model, 'M_Rds') else self.model.M_Rd
        M_Ed = self.model.M_Eds if hasattr(self.model, 'M_Eds') else self.model.M_Ed
        M_Ed_label = 'M_Eds' if hasattr(self.model, 'M_Eds') else 'M_Ed'
        
        # Check if moment capacity is sufficient
        moment_ok = M_Rd >= M_Ed
        moment_color = 'green' if moment_ok else 'red'
        moment_symbol = '✓' if moment_ok else '✗'
        
        # Calculate utilization
        utilization = M_Ed / M_Rd if M_Rd > 0 else 0
        
        # Determine utilization assessment
        if utilization > 1.0:
            util_emoji = '⚠️'
            util_text = 'UNSAFE'
            util_color = '#e74c3c'
            util_bg = '#fadbd8'
            util_msg = 'Design exceeds capacity!'
        elif utilization >= 0.9:
            util_emoji = '🎉'
            util_text = 'BRAVO'
            util_color = '#27ae60'
            util_bg = '#d5f4e6'
            util_msg = 'Excellent optimization!'
        elif utilization >= 0.8:
            util_emoji = '👍'
            util_text = 'FAIR'
            util_color = '#f39c12'
            util_bg = '#fef5e7'
            util_msg = 'Good design'
        else:
            util_emoji = '💰'
            util_text = 'UNECONOMICAL'
            util_color = '#95a5a6'
            util_bg = '#ecf0f1'
            util_msg = 'Over-designed'
        
        # Left box: Required Reinforcement
        reinforcement_html = f"""
        <div style="border: 1px solid #bbb; padding: 15px; background-color: #e8e8e8; border-radius: 5px; min-height: 180px; display: flex; flex-direction: column;">
            <h4 style="margin-top: 0; color: #27ae60;">Required Reinforcement</h4>
            
            <p style="margin: 5px 0 10px 0;">
               A_s = F_sd / f_yd = {F_sd:.3f} / {f_yd:.0f} × 10⁴<br>
               <span style="font-weight: bold; color: #27ae60; font-size: 18px;">
               A_s = {A_s_required:.2f} cm²
               </span>
            </p>
        </div>
        """
        
        # Check if moment capacity is sufficient
        moment_ok = M_Rd >= M_Ed
        moment_color = '#27ae60' if moment_ok else '#e74c3c'  # green if safe, red if unsafe
        moment_symbol = '✓' if moment_ok else '✗'
        
        # Right box: Moment Capacity Check
        capacity_html = f"""
        <div style="border: 1px solid #bbb; padding: 15px; background-color: #e8e8e8; border-radius: 5px; min-height: 180px; display: flex; flex-direction: column;">
            <h4 style="margin-top: 0; color: #27ae60;">Moment Capacity Check</h4>
            
            <p style="margin: 5px 0;">
               M_Rd = {M_Rd:.3f} MN·m<br>
               {M_Ed_label} = {M_Ed:.3f} MN·m
            </p>
            <p style="margin: 15px 0 10px 0; font-weight: bold; font-size: 18px;">
               <span style="color: {moment_color};">
               M_Rd {'≥' if moment_ok else '<'} {M_Ed_label} {moment_symbol}
               </span>
            </p>
        </div>
        """
        
        # Third box: Utilization (with assessment box on the right)
        utilization_html = f"""
        <div style="border: 1px solid #bbb; padding: 15px; background-color: #e8e8e8; border-radius: 5px; min-height: 180px; display: flex; flex-direction: column;">
            <h4 style="margin-top: 0; color: #27ae60;">Utilization</h4>
            
            <div style="display: flex; align-items: center; justify-content: space-between; flex: 1;">
                <div>
                    <p style="margin: 5px 0;">
                       η = {M_Ed_label} / M_Rd
                    </p>
                    <p style="margin: 10px 0; font-weight: bold; font-size: 24px;">
                       {utilization:.2f}
                    </p>
                </div>
                
                <div style="background-color: {util_bg}; padding: 10px; border-radius: 5px; display: flex; align-items: center; min-width: 160px;">
                    <div style="flex: 1;">
                        <div style="font-weight: bold; color: {util_color}; font-size: 14px;">{util_text}</div>
                        <div style="font-size: 11px; color: #666; margin-top: 3px;">{util_msg}</div>
                    </div>
                    <div style="font-size: 28px; margin-left: 8px;">{util_emoji}</div>
                </div>
            </div>
        </div>
        """
        
        # Fourth box: State Variables (from unbalanced model)
        x = self.model.x if hasattr(self.model, 'x') else 0
        z = self.model.z if hasattr(self.model, 'z') else 0
        F_cd = self.model.F_cd if hasattr(self.model, 'F_cd') else 0
        F_sd = self.model.F_sd if hasattr(self.model, 'F_sd') else 0
        
        state_html = f"""
        <div style="border: 1px solid #bbb; padding: 15px; background-color: #e8e8e8; border-radius: 5px; min-height: 180px; display: flex; flex-direction: column;">
            <h4 style="margin-top: 0; color: #27ae60;">State Variables</h4>
            
            <div style="display: flex; gap: 15px;">
                <div style="flex: 1;">
                    <p style="margin: 8px 0; font-size: 13px;">
                       <b>Neutral axis:</b><br>
                       x = {x:.3f} m
                    </p>
                    <p style="margin: 15px 0 8px 0; font-size: 13px;">
                       <b>Lever arm:</b><br>
                       z = {z:.3f} m
                    </p>
                </div>
                <div style="flex: 1;">
                    <p style="margin: 8px 0; font-size: 13px;">
                       <b>Compression:</b><br>
                       F_cd = {F_cd:.3f} MN
                    </p>
                    <p style="margin: 15px 0 8px 0; font-size: 13px;">
                       <b>Tension:</b><br>
                       F_sd = {F_sd:.3f} MN
                    </p>
                </div>
            </div>
        </div>
        """
        
        self.reinforcement_output.value = reinforcement_html
        self.capacity_output.value = capacity_html
        self.utilization_output.value = utilization_html
        self.state_output.value = state_html


class DesignWidget:
    """
    Combined design widget for cross-section geometry and material properties.
    
    Organized in two columns: Geometry | Materials
    """
    
    def __init__(self, model: RCModel, viz_widget: StressStrainProfileSubWidget, include_loading: bool = False):
        """
        Initialize design widget.
        
        Parameters:
        -----------
        model : RCModel
            The model to control (can be balanced or unbalanced)
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        include_loading : bool
            If True, includes M_Ed and N_Ed sliders in geometry section
        """
        self.model = model
        self.viz_widget = viz_widget
        self.include_loading = include_loading
        self._create_widgets()
    
    def _create_widgets(self):
        """Create geometry and material sliders in two-column layout."""
        
        # === GEOMETRY COLUMN (LEFT) ===
        geometry_items = []
        
        # Loading sliders (optional, for balanced model)
        if self.include_loading:
            self.M_Ed_slider = widgets.FloatSlider(
                value=self.model.M_Ed,
                min=0.05, max=1.0, step=0.01,
                description='M_Ed [MN·m]:',
                style={'description_width': '110px'},
                layout=widgets.Layout(width='400px'),
                tooltip='Design bending moment acting on the cross-section'
            )
            
            self.N_Ed_slider = widgets.FloatSlider(
                value=self.model.N_Ed,
                min=-0.5, max=0.5, step=0.01,
                description='N_Ed [MN]:',
                style={'description_width': '110px'},
                layout=widgets.Layout(width='400px'),
                tooltip='Design normal force (positive = tension, negative = compression)'
            )
            geometry_items.extend([self.M_Ed_slider, self.N_Ed_slider,
                                 widgets.HTML('<hr style="margin: 10px 0;">')])
        
        # Geometry sliders
        self.d_slider = widgets.FloatSlider(
            value=self.model.d,
            min=0.20, max=1.0, step=0.01,
            description='d [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Effective depth: distance from top to reinforcement centroid'
        )
        
        self.b_slider = widgets.FloatSlider(
            value=self.model.b,
            min=0.15, max=0.60, step=0.01,
            description='b [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Width of rectangular cross-section'
        )
        
        self.c_nom_slider = widgets.FloatSlider(
            value=self.model.c_nom,
            min=0.02, max=0.10, step=0.005,
            description='c_nom [m]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Nominal concrete cover to reinforcement'
        )
        
        geometry_items.extend([self.d_slider, self.b_slider, self.c_nom_slider])
        
        geometry_box = widgets.VBox(
            [widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Geometry</h4>')] + geometry_items,
            layout=widgets.Layout(padding='10px')
        )
        
        # === MATERIALS COLUMN (RIGHT) ===
        self.f_ck_slider = widgets.FloatSlider(
            value=self.model.f_ck,
            min=20, max=50, step=5,
            description='f_ck [MPa]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Characteristic concrete compressive strength (cylinder)'
        )
        
        self.f_yk_slider = widgets.FloatSlider(
            value=self.model.f_yk,
            min=400, max=600, step=50,
            description='f_yk [MPa]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='400px'),
            tooltip='Characteristic yield strength of reinforcement steel'
        )
        
        materials_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Materials</h4>'),
            self.f_ck_slider,
            self.f_yk_slider
        ], layout=widgets.Layout(padding='10px'))
        
        # Observe changes
        sliders = [self.d_slider, self.b_slider, self.c_nom_slider,
                   self.f_ck_slider, self.f_yk_slider]
        if self.include_loading:
            sliders.extend([self.M_Ed_slider, self.N_Ed_slider])
        
        for slider in sliders:
            slider.observe(self._on_value_change, names='value')
        
        # Layout
        self.layout = widgets.HBox(
            [geometry_box, materials_box],
            layout=widgets.Layout(
                padding='15px',
                border='2px solid #3498db',
                border_radius='5px',
                margin='5px'
            )
        )
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        if self.include_loading:
            self.model.M_Ed = self.M_Ed_slider.value
            self.model.N_Ed = self.N_Ed_slider.value
        self.model.d = self.d_slider.value
        self.model.b = self.b_slider.value
        self.model.c_nom = self.c_nom_slider.value
        self.model.f_ck = self.f_ck_slider.value
        self.model.f_yk = self.f_yk_slider.value
        
        # Update visualization
        self.viz_widget.update()


class TrialStrainStateWidget:
    """
    Trial strain state widget for iterative exploration (unbalanced model only).
    
    Organized in three columns: Strain State | Equilibrium Check | State Variables
    """
    
    def __init__(self, model: RCBendingUnbalancedModel, viz_widget: StressStrainProfileSubWidget, assessment_widget=None):
        """
        Initialize trial strain state widget.
        
        Parameters:
        -----------
        model : RCBendingUnbalancedModel
            The unbalanced model to control
        viz_widget : StressStrainProfileSubWidget
            The visualization widget to update
        assessment_widget : AssessmentResultWidget, optional
            The assessment widget to update when strains change
        """
        self.model = model
        self.viz_widget = viz_widget
        self.assessment_widget = assessment_widget
        self._create_widgets()
    
    def _create_widgets(self):
        """Create strain state sliders and equilibrium display in three-column layout."""
        
        # Strain state sliders (left box)
        self.epsilon_c_top_slider = widgets.FloatSlider(
            value=self.model.epsilon_c_top,
            min=-0.0050, max=-0.0010, step=0.0001,
            description='ε_c,top [-]:',
            style={'description_width': '110px'},
            layout=widgets.Layout(width='350px'),
            readout_format='.4f',
            tooltip='Compressive strain at top fiber (negative for compression)'
        )
        
        # Equilibrium check display (middle box)
        self.equilibrium_output = widgets.HTML(
            layout=widgets.Layout(width='350px', padding='10px')
        )
        
        self._update_displays()
        
        # Observe changes
        self.epsilon_c_top_slider.observe(self._on_value_change, names='value')
        
        # Two-column layout: Strain State | Equilibrium Check
        strain_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Strain State</h4>'),
            self.epsilon_c_top_slider
        ], layout=widgets.Layout(padding='10px'))
        
        equilibrium_box = widgets.VBox([
            widgets.HTML('<h4 style="margin-bottom: 10px; color: #2c3e50;">Equilibrium Check</h4>'),
            self.equilibrium_output
        ], layout=widgets.Layout(padding='10px'))
        
        self.layout = widgets.HBox(
            [strain_box, equilibrium_box],
            layout=widgets.Layout(
                padding='15px',
                border='2px solid #e74c3c',
                border_radius='5px',
                margin='5px'
            )
        )
    
    def _update_displays(self):
        """Update equilibrium display."""
        force_imb = self.model.force_imbalance
        moment_imb = self.model.moment_imbalance
        
        force_color = 'green' if abs(force_imb) < 0.001 else 'red'
        moment_color = 'green' if abs(moment_imb) < 0.001 else 'orange'
        
        # Equilibrium check display
        equilibrium_html = f"""
        <div style="border: 1px solid #bbb; padding: 15px; background-color: #e8e8e8; border-radius: 5px; height: 100%;">
            <p style="margin: 8px 0; font-size: 14px;"><b>Moment balance:</b> 
               <span style="color: {moment_color}; font-weight: bold; font-size: 15px;">
               ΔM = {moment_imb:.4f} MN·m
               </span>
            </p>
            <hr style="border: 1px solid #95a5a6; margin: 10px 0;">
            <p style="margin: 8px 0; font-size: 12px; color: #7f8c8d; font-style: italic;">
               Target: ΔM close to zero
            </p>
        </div>
        """
        
        self.equilibrium_output.value = equilibrium_html
    
    def _on_value_change(self, change):
        """Handle slider value changes."""
        # Update model
        self.model.epsilon_c_top = self.epsilon_c_top_slider.value
        
        # Update displays
        self._update_displays()
        
        # Update visualization
        self.viz_widget.update()
        
        # Update assessment widget if provided
        if self.assessment_widget:
            self.assessment_widget.update()


class RCBendingWidgetMN:
    """
    Main widget coordinating all subwidgets for RC bending analysis.
    """
    
    def __init__(self, model: Optional[RCBendingModelMN] = None):
        """
        Initialize the main widget with all subwidgets.
        
        Parameters:
        -----------
        model : RCBendingModelMN, optional
            Computational model instance. If None, creates new one.
        """
        self.model = model if model is not None else RCBendingModelMN()
        
        # Create subwidgets
        self.geometry_widget = GeometrySubWidget(self.model)
        self.materials_widget = MaterialLawsSubWidget(self.model)
        self.integration_widget = IntegrationParametersSubWidget(self.model)
        self.strain_widget = StrainProfileSubWidget(self.model)
        self.stress_widget = StressProfileSubWidget(self.model)
        self.results_widget = ResultsSummarySubWidget(self.model)
        
        self._create_controls()
        self._create_layout()
        
    def _create_controls(self):
        """Create input control widgets."""
        # Loading
        self.M_Ed_slider = widgets.FloatSlider(
            value=self.model.M_Ed, min=0.05, max=0.5, step=0.01,
            description='M_Ed [MN·m]:', style={'description_width': '120px'},
            continuous_update=False
        )
        self.N_Ed_slider = widgets.FloatSlider(
            value=self.model.N_Ed, min=-0.2, max=0.2, step=0.01,
            description='N_Ed [MN]:', style={'description_width': '120px'},
            continuous_update=False
        )
        
        # Geometry
        self.d_slider = widgets.FloatSlider(
            value=self.model.d, min=0.2, max=0.8, step=0.05,
            description='d [m]:', style={'description_width': '120px'},
            continuous_update=False
        )
        self.b_slider = widgets.FloatSlider(
            value=self.model.b, min=0.2, max=0.6, step=0.05,
            description='b [m]:', style={'description_width': '120px'},
            continuous_update=False
        )
        self.c_nom_slider = widgets.FloatSlider(
            value=self.model.c_nom, min=0.02, max=0.08, step=0.01,
            description='c_nom [m]:', style={'description_width': '120px'},
            continuous_update=False
        )
        
        # Materials - Concrete
        self.f_ck_slider = widgets.FloatSlider(
            value=self.model.f_ck, min=12, max=50, step=1,
            description='f_ck [MPa]:', style={'description_width': '120px'},
            continuous_update=False
        )
        self.epsilon_cx2_slider = widgets.FloatSlider(
            value=self.model.epsilon_cx2, min=-0.003, max=-0.001, step=0.0001,
            description='ε_cx2 [-]:', style={'description_width': '120px'},
            continuous_update=False, readout_format='.4f'
        )
        self.epsilon_cu2_slider = widgets.FloatSlider(
            value=self.model.epsilon_cu2, min=-0.004, max=-0.003, step=0.0001,
            description='ε_cu2 [-]:', style={'description_width': '120px'},
            continuous_update=False, readout_format='.4f'
        )
        
        # Materials - Steel
        self.f_yk_slider = widgets.FloatSlider(
            value=self.model.f_yk, min=400, max=600, step=50,
            description='f_yk [MPa]:', style={'description_width': '120px'},
            continuous_update=False
        )
        
        # Bind observers
        all_sliders = [
            self.M_Ed_slider, self.N_Ed_slider, self.d_slider, self.b_slider,
            self.c_nom_slider, self.f_ck_slider, self.epsilon_cx2_slider,
            self.epsilon_cu2_slider, self.f_yk_slider
        ]
        for slider in all_sliders:
            slider.observe(self._on_change, names='value')
    
    def _create_layout(self):
        """Create accordion layout."""
        # Section contents
        geometry_section = widgets.VBox([
            widgets.HTML("<b>Applied Loading:</b>"),
            self.M_Ed_slider,
            self.N_Ed_slider,
            widgets.HTML("<b>Cross-Section Geometry:</b>"),
            self.d_slider,
            self.b_slider,
            self.c_nom_slider,
            widgets.HTML("<hr><b>Visualization:</b>"),
            self.geometry_widget.output
        ])
        
        material_section = widgets.VBox([
            widgets.HTML("<b>Concrete (EC2):</b>"),
            self.f_ck_slider,
            self.epsilon_cx2_slider,
            self.epsilon_cu2_slider,
            widgets.HTML("<b>Steel:</b>"),
            self.f_yk_slider,
            widgets.HTML("<hr><b>Constitutive Laws:</b>"),
            self.materials_widget.output
        ])
        
        integration_section = widgets.VBox([
            widgets.HTML("<b>EC2 Stress Block Parameters (Calculated):</b>"),
            widgets.HTML(f"<p>k_a and α_r are calculated from concrete stress-strain curve</p>"),
            self.integration_widget.output
        ])
        
        strain_section = widgets.VBox([
            widgets.HTML("<b>Strain Distribution (Linear):</b>"),
            self.strain_widget.output
        ])
        
        stress_section = widgets.VBox([
            widgets.HTML("<b>Stress Distribution & Force Resultants:</b>"),
            self.stress_widget.output
        ])
        
        results_section = widgets.VBox([
            widgets.HTML("<b>Calculation Results:</b>"),
            self.results_widget.output
        ])
        
        # Accordion
        accordion = widgets.Accordion(children=[
            geometry_section,
            material_section,
            integration_section,
            strain_section,
            stress_section,
            results_section
        ])
        accordion.set_title(0, '📐 1. Geometry & Loading')
        accordion.set_title(1, '🔬 2. Material Laws')
        accordion.set_title(2, '⚙️ 3. Integration Parameters')
        accordion.set_title(3, '📊 4. Strain Distribution')
        accordion.set_title(4, '💪 5. Stress & Forces')
        accordion.set_title(5, '✅ 6. Results Summary')
        accordion.selected_index = 0
        
        self.main_layout = widgets.VBox([
            widgets.HTML("<h2>RC Bending + Normal Force Analysis</h2>"),
            widgets.HTML("<p><i>Modular analysis with cached computations (EC2)</i></p>"),
            accordion,
        ])
    
    def _on_change(self, change):
        """Handle parameter changes."""
        # Update model
        self.model.M_Ed = self.M_Ed_slider.value
        self.model.N_Ed = self.N_Ed_slider.value
        self.model.d = self.d_slider.value
        self.model.b = self.b_slider.value
        self.model.c_nom = self.c_nom_slider.value
        self.model.f_ck = self.f_ck_slider.value
        self.model.epsilon_cx2 = self.epsilon_cx2_slider.value
        self.model.epsilon_cu2 = self.epsilon_cu2_slider.value
        self.model.f_yk = self.f_yk_slider.value
        
        # Update all subwidgets
        self.update_all()
    
    def update_all(self):
        """Update all subwidgets."""
        self.geometry_widget.update()
        self.materials_widget.update()
        self.integration_widget.update()
        self.strain_widget.update()
        self.stress_widget.update()
        self.results_widget.update()
    
    def display(self):
        """Display the widget."""
        display(self.main_layout)
        self.update_all()


def create_rc_bending_widget(model: Optional[RCBendingModelMN] = None) -> RCBendingWidgetMN:
    """
    Factory function to create and display the RC bending analysis widget.
    
    Parameters:
    -----------
    model : RCBendingModelMN, optional
        Computational model. If None, creates new one.
        
    Returns:
    --------
    RCBendingWidgetMN
        The interactive widget instance
    """
    widget = RCBendingWidgetMN(model)
    widget.display()
    return widget
