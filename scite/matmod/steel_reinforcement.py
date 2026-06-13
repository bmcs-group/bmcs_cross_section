"""
Steel Reinforcement Material Model (Modern Implementation)

Implements a bilinear elastic-plastic stress-strain relationship for
steel reinforcement with strain hardening, using the new core module
with Pydantic validation and symbolic expression support.

References:
    Typical reinforcing steel behavior with yield plateau and hardening
"""

from functools import cached_property
from typing import Optional

import numpy as np
import sympy as sp

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
    
    f_yk: float = ui_field(
        500.0,
        label=r"$f_{yk}$",
        unit="MPa",
        range=(300.0, 700.0),
        step=10.0,
        description="Characteristic yield strength",
        gt=0
    )
    
    f_tk: float = ui_field(
        525.0,
        label=r"$f_{tk}$",
        unit="MPa",
        range=(400.0, 800.0),
        step=10.0,
        description="Characteristic tensile strength (f_tk ≥ f_yk)",
        gt=0
    )
    
    gamma_s: float = ui_field(
        1.15,
        label=r"$\gamma_s$",
        unit="-",
        range=(1.0, 1.5),
        step=0.05,
        description="Partial safety factor for steel (EC2: 1.15)",
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
    def f_yd(self) -> float:
        """Design yield strength: f_yd = f_yk / γ_s"""
        return self.f_yk / self.gamma_s
    
    @cached_property
    def f_td(self) -> float:
        """Design tensile strength: f_td = f_tk / γ_s"""
        return self.f_tk / self.gamma_s
    
    @cached_property
    def eps_yd(self) -> float:
        """Yield strain at design strength (derived from f_yd and modulus)"""
        return self.f_yd / self.E_s
    
    @cached_property
    def ductility_ratio(self) -> float:
        """Ductility ratio k = f_tk / f_yk"""
        return self.f_tk / self.f_yk
    
    # -------------------------------------------------------------------------
    # Symbolic expression
    # -------------------------------------------------------------------------
    
    @cached_property
    def symbolic_stress(self) -> SymbolicExpression:
        """
        Create symbolic stress-strain expression using design values.
        
        The model consists of 7 branches (symmetric):
        1. Zero stress before ultimate compression strain + extension
        2. Softening from zero to ultimate stress (compression)
        3. Hardening from yield to ultimate stress (compression)
        4. Linear elastic (compression)
        5. Linear elastic (tension)
        6. Hardening from yield to ultimate stress (tension)
        7. Softening from ultimate stress to zero (tension)
        8. Zero stress after ultimate tension strain + extension
        
        All stresses are design values: f_yd = f_yk / γ_s
        """
        eps = sp.Symbol('varepsilon', real=True)
        
        # Parameters (design values)
        E_s = self.E_s
        eps_yd = self.eps_yd  # Yield strain at design strength
        eps_ud = self.eps_ud
        f_yd = self.f_yd      # Design yield strength
        f_td = self.f_td      # Design tensile strength
        ext = self.ext_factor
        
        # Piecewise stress function
        sig = sp.Piecewise(
            # Far compression (zero stress)
            (0, eps < -eps_ud - ext * eps_yd),  # type: ignore[operator]
            # Post-ultimate softening (compression)
            (-f_td + f_td * (-eps - eps_ud) / (ext * eps_yd), 
             eps < -eps_ud),  # type: ignore[operator]
            # Strain hardening (compression)
            (-f_yd - (f_td - f_yd) * ((-eps - eps_yd) / (eps_ud - eps_yd)), 
             eps < -eps_yd),  # type: ignore[operator]
            # Elastic (compression)
            (E_s * eps, eps < eps_yd),  # type: ignore[operator]
            # Strain hardening (tension)
            (f_yd + (f_td - f_yd) * ((eps - eps_yd) / (eps_ud - eps_yd)), 
             eps < eps_ud),  # type: ignore[operator]
            # Post-ultimate softening (tension)
            (f_td - f_td * (eps - eps_ud) / (ext * eps_yd), 
             eps < eps_ud + ext * eps_yd),  # type: ignore[operator]
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

    def plotly_figure(self):
        """Return a plotly Figure of the symmetric bilinear stress-strain curve."""
        import plotly.graph_objects as go

        eps_min, eps_max = self.get_plot_range()
        eps = np.linspace(eps_min, eps_max, 500)
        sig = self.get_sig(eps)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=eps.tolist(), y=sig.tolist(),
            mode="lines", name="Steel (design)",
            line=dict(color="#1f77b4", width=2),
        ))
        # Yield points
        fig.add_trace(go.Scatter(
            x=[self.eps_yd, -self.eps_yd], y=[self.f_yd, -self.f_yd],
            mode="markers+text", name=f"Yield  f_yd={self.f_yd:.0f} MPa",
            marker=dict(color="orange", size=10, symbol="circle"),
            text=[f"f_yd={self.f_yd:.0f}", None], textposition="top right",
        ))
        # Ultimate points
        fig.add_trace(go.Scatter(
            x=[self.eps_ud, -self.eps_ud], y=[self.f_td, -self.f_td],
            mode="markers+text", name=f"Ultimate  f_td={self.f_td:.0f} MPa",
            marker=dict(color="red", size=10, symbol="square"),
            text=[f"f_td={self.f_td:.0f}", None], textposition="top right",
        ))
        fig.add_hline(y=0, line=dict(color="black", width=0.5))
        fig.add_vline(x=0, line=dict(color="black", width=0.5))
        fig.update_layout(
            title=f"Steel Reinforcement  f_yk={self.f_yk:.0f} MPa,  f_yd={self.f_yd:.0f} MPa",
            xaxis_title="Strain ε [-]",
            yaxis_title="Stress σ [MPa]",
            legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
            margin=dict(l=60, r=20, t=50, b=50),
        )
        return fig

    def plot_stress_strain(
        self,
        ax,
        n_points: int = 500,
        show_key_points: bool = True,
    ):
        """Plot stress-strain curve on given axes (matplotlib, legacy)."""
        eps_min, eps_max = self.get_plot_range()
        eps = np.linspace(eps_min, eps_max, n_points)
        sig = self.get_sig(eps)
        ax.plot(eps, sig, 'b-', linewidth=2, label='σ-ε curve (design)')
        if show_key_points:
            ax.plot([self.eps_yd, -self.eps_yd], [self.f_yd, -self.f_yd],
                    'ro', markersize=8, label=f'Yield: ε_yd={self.eps_yd:.4f}')
            ax.plot([self.eps_ud, -self.eps_ud], [self.f_td, -self.f_td],
                    'rs', markersize=8, label=f'Ultimate: ε_ud={self.eps_ud:.4f}')
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]')
        ax.set_ylabel('Stress σ [MPa]')
        ax.set_title(f'Steel Reinforcement: f_yk={self.f_yk:.0f} MPa, f_yd={self.f_yd:.0f} MPa')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def summary(self) -> dict:
        """Return summary of material properties"""
        return {
            'Material': 'Steel Reinforcement',
            'E_s [MPa]': f"{self.E_s:.0f}",
            'f_yk [MPa]': f"{self.f_yk:.1f}",
            'f_yd [MPa]': f"{self.f_yd:.1f}",
            'f_tk [MPa]': f"{self.f_tk:.1f}",
            'f_td [MPa]': f"{self.f_td:.1f}",
            'γ_s [-]': f"{self.gamma_s:.2f}",
            'eps_yd [-]': f"{self.eps_yd:.6f}",
            'eps_ud [-]': f"{self.eps_ud:.4f}",
            'Ductility k': f"{self.ductility_ratio:.3f}",
        }


# Convenience function for common steel grades
def create_steel(
    grade: str = 'B500B',
    gamma_s: float = 1.15
) -> SteelReinforcement:
    """
    Create steel reinforcement with predefined properties.
    
    Args:
        grade: Steel grade ('B500A', 'B500B', 'B500C', etc.)
        gamma_s: Partial safety factor (default 1.15 for EC2 design)
        
    Returns:
        SteelReinforcement instance with design values
        
    Examples:
        >>> steel = create_steel('B500B')  # Uses γ_s = 1.15 (design)
        >>> steel = create_steel('B500B', gamma_s=1.0)  # Characteristic values
    """
    # Common European steel grades (EN 10080)
    grades = {
        'B500A': {'f_yk': 500, 'f_tk': 525, 'eps_ud': 0.025},  # k ≥ 1.05
        'B500B': {'f_yk': 500, 'f_tk': 540, 'eps_ud': 0.050},  # k ≥ 1.08
        'B500C': {'f_yk': 500, 'f_tk': 575, 'eps_ud': 0.075},  # k ≥ 1.15
        'B600A': {'f_yk': 600, 'f_tk': 630, 'eps_ud': 0.020},
        'B600B': {'f_yk': 600, 'f_tk': 660, 'eps_ud': 0.050},
    }
    
    if grade not in grades:
        raise ValueError(f"Unknown steel grade '{grade}'. "
                        f"Available: {list(grades.keys())}")
    
    props = grades[grade]
    return SteelReinforcement(
        f_yk=props['f_yk'],
        f_tk=props['f_tk'],
        eps_ud=props['eps_ud'],
        gamma_s=gamma_s
    )
