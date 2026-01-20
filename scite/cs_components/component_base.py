"""
Reinforcement Component Base Classes

This module defines the base class for all reinforcement components,
providing a common interface for standardized products with geometric
properties, material behavior, and safety factors.
"""

import numpy as np
import numpy.typing as npt
from dataclasses import dataclass
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod


@dataclass
class ReinforcementComponent(ABC):
    """
    Base class for all reinforcement components.
    
    A component represents a standardized product with:
    - Geometric properties (area, diameter, etc.)
    - Material behavior (stress-strain curve)
    - Safety factors for design
    - Manufacturer/certification info
    
    This provides a product catalog layer between physical products
    and material models (matmod), enabling traceability and standardization.
    """
    
    # Product identification
    product_id: str = ''
    name: str = ''
    manufacturer: str = ''
    
    # Shape category
    shape_type: str = ''  # 'bar', 'mat', 'textile', 'grid'
    
    # Material type
    material_type: str = ''  # 'steel', 'carbon', 'glass', 'basalt', 'aramid'
    
    # Geometric properties
    nominal_diameter: Optional[float] = None  # [mm] for bars
    area: float = 0.0  # [mm²] cross-sectional area
    
    # Material properties (characteristic values)
    f_tk: float = 0.0  # [MPa] characteristic tensile strength
    E: float = 0.0     # [MPa] elastic modulus
    eps_uk: float = 0.0  # [-] characteristic ultimate strain
    
    # Safety factors (EC2 typical values)
    gamma_s: float = 1.15  # Partial safety factor for reinforcement
    
    # Optional: link to full material model
    matmod: Optional[Any] = None
    
    def __post_init__(self):
        """Calculate derived properties."""
        if self.nominal_diameter and self.area == 0.0:
            # Calculate area from diameter for circular bars
            self.area = np.pi * (self.nominal_diameter / 2) ** 2
    
    @property
    def f_td(self) -> float:
        """Design tensile strength [MPa]."""
        return self.f_tk / self.gamma_s
    
    @property
    def eps_ud(self) -> float:
        """Design ultimate strain [-]."""
        return self.eps_uk  # Usually not reduced by gamma_s
    
    @abstractmethod
    def get_design_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get design stress-strain curve.
        
        Args:
            eps: Strain array [-]
            
        Returns:
            Stress array [MPa] at design values
        """
        pass
    
    def get_characteristic_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get characteristic stress-strain curve (using f_tk, eps_uk).
        
        This is the base curve from material testing (5% fractile).
        Default implementation: linear elastic to f_tk.
        Subclasses should override for specific behavior.
        """
        sig = np.minimum(self.E * np.abs(eps), self.f_tk)
        sig = np.sign(eps) * sig
        sig = np.where(np.abs(eps) > self.eps_uk, 0, sig)
        return sig
    
    def get_mean_stress_strain(self, eps: npt.NDArray[np.float64]) -> Optional[npt.NDArray[np.float64]]:
        """
        Get mean stress-strain curve (if available).
        
        For most reinforcement, mean values are not standardized.
        Returns None by default. Subclasses can override if mean values exist.
        """
        return None
    
    def plot_stress_strain(self, ax=None, eps_max=None, n_points=200, 
                           show_limits=True, color='darkred', alpha_fill=0.15, **plot_kwargs):
        """
        Plot stress-strain curves (mean, characteristic, design) for this component.
        
        Args:
            ax: Matplotlib axes to plot on. If None, creates new figure.
            eps_max: Maximum strain to plot. If None, uses 1.2 * eps_ud.
            n_points: Number of points in the curve.
            show_limits: Whether to show design strength and ultimate strain lines.
            color: Line color (default: 'darkred' for reinforcement).
            alpha_fill: Transparency for area fill (0-1, default: 0.15).
            **plot_kwargs: Additional keyword arguments for the plot line.
            
        Returns:
            Matplotlib axes object.
        """
        import matplotlib.pyplot as plt
        
        # Create figure if no axes provided
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        # Determine strain range
        if eps_max is None:
            eps_max = self.eps_ud * 1.2 if self.eps_ud > 0 else 0.05
        
        # Generate strain array
        eps = np.linspace(0, eps_max, n_points)
        
        # Get all available curves
        sig_design = self.get_design_stress_strain(eps)
        sig_char = self.get_characteristic_stress_strain(eps)
        sig_mean = self.get_mean_stress_strain(eps)
        
        # Convert color to RGBA for transparency control
        from matplotlib.colors import to_rgba
        base_rgba = to_rgba(color)
        pale_color = (*base_rgba[:3], 0.4)  # More transparent for characteristic
        
        # Plot design curve (filled, solid line)
        ax.plot(eps * 1000, sig_design, linewidth=2.5, color=color, 
               label=f'Design (f_td={self.f_td:.0f} MPa)', solid_capstyle='round')
        if alpha_fill > 0:
            ax.fill_between(eps * 1000, 0, sig_design, color=color, alpha=alpha_fill)
        
        # Plot characteristic curve (dashed, pale)
        ax.plot(eps * 1000, sig_char, linewidth=2.0, color=pale_color, 
               linestyle='--', label=f'Characteristic (f_tk={self.f_tk:.0f} MPa)')
        
        # Plot mean curve if available (dotted, no fill)
        if sig_mean is not None:
            ax.plot(eps * 1000, sig_mean, linewidth=2.0, color=color, 
                   linestyle=':', label='Mean', alpha=0.6)
        
        # Add limit lines if requested
        if show_limits:
            ax.axhline(y=self.f_td, color='gray', linestyle='--', alpha=0.3)
            ax.axvline(x=self.eps_ud * 1000, color='gray', linestyle='--', alpha=0.3)
        
        # Labels and formatting
        ax.set_xlabel('Strain ε [‰]', fontsize=11)
        ax.set_ylabel('Stress σ [MPa]', fontsize=11)
        ax.set_title(f'{self.name}', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=9)
        
        return ax
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for catalog."""
        return {
            'product_id': self.product_id,
            'name': self.name,
            'manufacturer': self.manufacturer,
            'shape_type': self.shape_type,
            'material_type': self.material_type,
            'nominal_diameter': self.nominal_diameter,
            'area': self.area,
            'f_tk': self.f_tk,
            'f_td': self.f_td,
            'E': self.E,
            'eps_uk': self.eps_uk,
            'gamma_s': self.gamma_s,
        }


@dataclass
class ConcreteComponent:
    """
    Concrete component representing a specific concrete grade.
    
    Properties:
    - Strength class (EC2: C20/25, C30/37, etc.)
    - Characteristic and design strength
    - Elastic modulus
    - Safety factors
    """
    
    # Product identification
    product_id: str = ''
    name: str = ''
    strength_class: str = ''  # e.g., "C30/37"
    
    # Strength properties (characteristic values)
    f_ck: float = 0.0  # [MPa] characteristic cylinder strength
    f_cm: float = 0.0  # [MPa] mean compressive strength
    
    # Elastic properties
    E_cm: float = 0.0  # [MPa] secant modulus
    
    # Safety factors
    gamma_c: float = 1.5  # Partial safety factor for concrete
    alpha_cc: float = 1.0  # Coefficient for long-term effects
    
    # Optional: link to full material model
    matmod: Optional[Any] = None
    
    @property
    def f_cd(self) -> float:
        """Design compressive strength [MPa]."""
        return self.alpha_cc * self.f_ck / self.gamma_c
    
    def get_design_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Get design stress-strain curve for concrete (using f_cd)."""
        if self.matmod is None:
            return np.zeros_like(eps)
        # EC2ParabolaRectangle already returns design stress based on f_cd
        # No scaling needed - use matmod directly
        return self.matmod.get_sig(eps)
    
    def get_characteristic_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Get characteristic stress-strain curve for concrete (using f_ck)."""
        if self.matmod is None:
            return np.zeros_like(eps)
        # Scale matmod curve to characteristic strength
        return self.matmod.get_sig(eps) * (self.f_ck / self.f_cm) if self.f_cm > 0 else np.zeros_like(eps)
    
    def get_mean_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Get mean stress-strain curve for concrete (using f_cm)."""
        if self.matmod is None:
            return np.zeros_like(eps)
        # Matmod is based on f_cm, so use it directly
        return self.matmod.get_sig(eps)
    
    def plot_stress_strain(self, ax=None, eps_max=0.0035, n_points=100,
                          show_limits=True, color='blue', alpha_fill=0.15, **plot_kwargs):
        """
        Plot stress-strain curves (mean, characteristic, design) for concrete (compression).
        
        Args:
            ax: Matplotlib axes to plot on. If None, creates new figure.
            eps_max: Maximum compressive strain (positive value). Default 0.0035.
            n_points: Number of points in the curve.
            show_limits: Whether to show design strength line.
            color: Line color (default: 'blue' for concrete).
            alpha_fill: Transparency for area fill (0-1, default: 0.15).
            **plot_kwargs: Additional keyword arguments for the plot line.
            
        Returns:
            Matplotlib axes object.
        """
        import matplotlib.pyplot as plt
        
        if self.matmod is None:
            raise ValueError(f"No material model available for {self.name}")
        
        # Create figure if no axes provided
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        # Generate strain array (compression is negative)
        eps = np.linspace(0, -eps_max, n_points)
        
        # Get all available curves
        sig_design = self.get_design_stress_strain(eps)
        sig_char = self.get_characteristic_stress_strain(eps)
        sig_mean = self.get_mean_stress_strain(eps)
        
        # Convert color to RGBA for transparency control
        from matplotlib.colors import to_rgba
        base_rgba = to_rgba(color)
        pale_color = (*base_rgba[:3], 0.4)  # More transparent for characteristic
        
        # Plot design curve (filled, solid line)
        ax.plot(eps * 1000, sig_design, linewidth=2.5, color=color, 
               label=f'Design (f_cd={self.f_cd:.1f} MPa)', solid_capstyle='round')
        if alpha_fill > 0:
            ax.fill_between(eps * 1000, 0, sig_design, color=color, alpha=alpha_fill)
        
        # Plot characteristic curve (dashed, pale)
        ax.plot(eps * 1000, sig_char, linewidth=2.0, color=pale_color, 
               linestyle='--', label=f'Characteristic (f_ck={self.f_ck:.0f} MPa)')
        
        # Plot mean curve (dotted, no fill)
        ax.plot(eps * 1000, sig_mean, linewidth=2.0, color=color, 
               linestyle=':', label=f'Mean (f_cm={self.f_cm:.0f} MPa)', alpha=0.6)
        
        # Add design strength line if requested
        if show_limits:
            ax.axhline(y=-self.f_cd, color='gray', linestyle='--', alpha=0.3)
        
        # Labels and formatting
        ax.set_xlabel('Compressive Strain ε_c [‰]', fontsize=11)
        ax.set_ylabel('Compressive Stress σ_c [MPa]', fontsize=11)
        ax.set_title(f'{self.name}', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=9)
        
        return ax
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for catalog."""
        return {
            'product_id': self.product_id,
            'name': self.name,
            'strength_class': self.strength_class,
            'f_ck': self.f_ck,
            'f_cm': self.f_cm,
            'f_cd': self.f_cd,
            'E_cm': self.E_cm,
            'gamma_c': self.gamma_c,
            'alpha_cc': self.alpha_cc,
        }
