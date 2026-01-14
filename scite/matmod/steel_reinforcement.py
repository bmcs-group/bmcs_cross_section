"""
Steel Reinforcement Material Model (Modern Implementation)

Implements a bilinear elastic-plastic stress-strain relationship for
steel reinforcement with strain hardening, using the new core module
with Pydantic validation and symbolic expression support.

References:
    Typical reinforcing steel behavior with yield plateau and hardening
"""

import numpy as np
import sympy as sp
from functools import cached_property
from typing import Optional

from scite.core import BMCSModel, ui_field
from scite.core.symbolic import SymbolicExpression


class SteelReinforcement(BMCSModel):
    """
    Steel reinforcement constitutive model.
    
    Implements a bilinear elastic-plastic relationship with:
    - Linear elastic behavior up to yield stress
    - Yield plateau (optional)
    - Strain hardening to ultimate stress
    - Symmetric behavior in tension and compression
    
    The model includes a softening branch after ultimate strain to
    avoid numerical instabilities.
    """
    
    # -------------------------------------------------------------------------
    # Primary parameters
    # -------------------------------------------------------------------------
    
    E_s: float = ui_field(
        200000.0,
        label=r"$E_s$",
        unit="MPa",
        range=(150000.0, 250000.0),
        step=1000.0,
        description="Young's modulus of steel",
        gt=0
    )
    
    f_sy: float = ui_field(
        500.0,
        label=r"$f_{sy}$",
        unit="MPa",
        range=(300.0, 700.0),
        step=10.0,
        description="Yield strength of steel",
        gt=0
    )
    
    f_st: float = ui_field(
        525.0,
        label=r"$f_{st}$",
        unit="MPa",
        range=(400.0, 800.0),
        step=10.0,
        description="Ultimate tensile strength (f_st ≥ f_sy)",
        gt=0
    )
    
    eps_ud: float = ui_field(
        0.025,
        label=r"$\varepsilon_{ud}$",
        unit="-",
        range=(0.01, 0.15),
        step=0.005,
        description="Ultimate strain at peak stress",
        gt=0
    )
    
    factor: float = ui_field(
        1.0,
        label=r"Factor",
        unit="-",
        range=(0.5, 1.5),
        step=0.05,
        description="Safety/adjustment factor for stress",
        gt=0
    )
    
    ext_factor: float = ui_field(
        0.7,
        label=r"Extension",
        unit="-",
        range=(0.1, 2.0),
        step=0.1,
        description="Post-ultimate softening extension factor",
        gt=0
    )
    
    # -------------------------------------------------------------------------
    # Derived properties
    # -------------------------------------------------------------------------
    
    @cached_property
    def eps_sy(self) -> float:
        """Yield strain (derived from yield stress and modulus)"""
        return self.f_sy_scaled / self.E_s
    
    @cached_property
    def f_sy_scaled(self) -> float:
        """Scaled yield strength (with safety factor)"""
        return self.factor * self.f_sy
    
    @cached_property
    def f_st_scaled(self) -> float:
        """Scaled ultimate strength (with safety factor)"""
        return self.factor * self.f_st
    
    @cached_property
    def ductility_ratio(self) -> float:
        """Ductility ratio k = f_st / f_sy"""
        return self.f_st / self.f_sy
    
    # -------------------------------------------------------------------------
    # Symbolic expression
    # -------------------------------------------------------------------------
    
    @cached_property
    def symbolic_stress(self) -> SymbolicExpression:
        """
        Create symbolic stress-strain expression.
        
        The model consists of 7 branches (symmetric):
        1. Zero stress before ultimate compression strain + extension
        2. Softening from zero to ultimate stress (compression)
        3. Hardening from yield to ultimate stress (compression)
        4. Linear elastic (compression)
        5. Linear elastic (tension)
        6. Hardening from yield to ultimate stress (tension)
        7. Softening from ultimate stress to zero (tension)
        8. Zero stress after ultimate tension strain + extension
        """
        eps = sp.Symbol('varepsilon', real=True)
        
        # Parameters
        E_s = self.E_s
        eps_sy = self.eps_sy
        eps_ud = self.eps_ud
        f_sy = self.f_sy_scaled
        f_st = self.f_st_scaled
        ext = self.ext_factor
        
        # Piecewise stress function
        sig = sp.Piecewise(
            # Far compression (zero stress)
            (0, eps < -eps_ud - ext * eps_sy),  # type: ignore[operator]
            # Post-ultimate softening (compression)
            (-f_st + f_st * (-eps - eps_ud) / (ext * eps_sy), 
             eps < -eps_ud),  # type: ignore[operator]
            # Strain hardening (compression)
            (-f_sy - (f_st - f_sy) * ((-eps - eps_sy) / (eps_ud - eps_sy)), 
             eps < -eps_sy),  # type: ignore[operator]
            # Elastic (compression)
            (E_s * eps, eps < eps_sy),  # type: ignore[operator]
            # Strain hardening (tension)
            (f_sy + (f_st - f_sy) * ((eps - eps_sy) / (eps_ud - eps_sy)), 
             eps < eps_ud),  # type: ignore[operator]
            # Post-ultimate softening (tension)
            (f_st - f_st * (eps - eps_ud) / (ext * eps_sy), 
             eps < eps_ud + ext * eps_sy),  # type: ignore[operator]
            # Far tension (zero stress)
            (0, True)
        )
        
        return SymbolicExpression(
            name='steel_stress',
            expression=sig,
            parameters=('varepsilon',)
        )
    
    # -------------------------------------------------------------------------
    # Evaluation methods
    # -------------------------------------------------------------------------
    
    def get_sig(self, eps: np.ndarray) -> np.ndarray:
        """
        Evaluate stress for given strain(s).
        
        Args:
            eps: Strain value(s)
            
        Returns:
            Stress value(s) in MPa
        """
        eps = np.atleast_1d(eps)
        sig_func = self.symbolic_stress.lambdify()
        return sig_func(eps)
    
    def get_E_t(self, eps: np.ndarray, h: float = 1e-8) -> np.ndarray:
        """
        Compute tangent modulus (numerical derivative).
        
        Args:
            eps: Strain value(s)
            h: Step size for numerical differentiation
            
        Returns:
            Tangent modulus E_t = dσ/dε in MPa
        """
        eps = np.atleast_1d(eps)
        # Central difference approximation
        sig_plus = self.get_sig(eps + h)
        sig_minus = self.get_sig(eps - h)
        return (sig_plus - sig_minus) / (2 * h)
    
    def get_plot_range(self) -> tuple[float, float]:
        """Get appropriate strain range for plotting"""
        eps_max = self.eps_ud * 1.1
        return (-eps_max, eps_max)
    
    def plot_stress_strain(
        self, 
        ax, 
        n_points: int = 500,
        show_key_points: bool = True
    ):
        """
        Plot stress-strain curve on given axes.
        
        Args:
            ax: Matplotlib axes
            n_points: Number of points for smooth curve
            show_key_points: Whether to mark yield and ultimate points
        """
        eps_min, eps_max = self.get_plot_range()
        eps = np.linspace(eps_min, eps_max, n_points)
        sig = self.get_sig(eps)
        
        # Main curve
        ax.plot(eps, sig, 'b-', linewidth=2, label='σ-ε curve')
        
        # Key points
        if show_key_points:
            # Yield points
            ax.plot([self.eps_sy, -self.eps_sy], 
                   [self.f_sy_scaled, -self.f_sy_scaled],
                   'ro', markersize=8, label=f'Yield: ε_sy={self.eps_sy:.4f}')
            
            # Ultimate points
            ax.plot([self.eps_ud, -self.eps_ud],
                   [self.f_st_scaled, -self.f_st_scaled],
                   'rs', markersize=8, label=f'Ultimate: ε_ud={self.eps_ud:.4f}')
        
        # Axes and labels
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]')
        ax.set_ylabel('Stress σ [MPa]')
        ax.set_title(f'Steel Reinforcement: f_sy={self.f_sy:.0f} MPa, E_s={self.E_s:.0f} MPa')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def summary(self) -> dict:
        """Return summary of material properties"""
        return {
            'Material': 'Steel Reinforcement',
            'E_s [MPa]': f"{self.E_s:.0f}",
            'f_sy [MPa]': f"{self.f_sy:.1f}",
            'f_st [MPa]': f"{self.f_st:.1f}",
            'eps_sy [-]': f"{self.eps_sy:.6f}",
            'eps_ud [-]': f"{self.eps_ud:.4f}",
            'Ductility k': f"{self.ductility_ratio:.3f}",
            'Factor': f"{self.factor:.2f}",
        }


# Convenience function for common steel grades
def create_steel(
    grade: str = 'B500B',
    factor: float = 1.0
) -> SteelReinforcement:
    """
    Create steel reinforcement with predefined properties.
    
    Args:
        grade: Steel grade ('B500A', 'B500B', 'B500C', etc.)
        factor: Safety/adjustment factor
        
    Returns:
        SteelReinforcement instance
        
    Examples:
        >>> steel = create_steel('B500B')
        >>> steel = create_steel('B500C', factor=1/1.15)  # Design strength
    """
    # Common European steel grades (EN 10080)
    grades = {
        'B500A': {'f_sy': 500, 'f_st': 525, 'eps_ud': 0.025},  # k ≥ 1.05
        'B500B': {'f_sy': 500, 'f_st': 540, 'eps_ud': 0.050},  # k ≥ 1.08
        'B500C': {'f_sy': 500, 'f_st': 575, 'eps_ud': 0.075},  # k ≥ 1.15
        'B600A': {'f_sy': 600, 'f_st': 630, 'eps_ud': 0.020},
        'B600B': {'f_sy': 600, 'f_st': 660, 'eps_ud': 0.050},
    }
    
    if grade not in grades:
        raise ValueError(f"Unknown steel grade '{grade}'. "
                        f"Available: {list(grades.keys())}")
    
    props = grades[grade]
    return SteelReinforcement(
        f_sy=props['f_sy'],
        f_st=props['f_st'],
        eps_ud=props['eps_ud'],
        factor=factor
    )
