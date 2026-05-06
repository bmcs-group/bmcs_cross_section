"""
EC2 Parabola-Rectangle Compression Law (Design Values)

Implements the parabolic-rectangular stress-strain relationship for concrete
in compression according to EC2 3.1.7, using design values (f_cd).

This is a compression-only model suitable for ULS design calculations.

References:
    EN 1992-1-1:2004 (Eurocode 2), Section 3.1.7, Figure 3.3
"""

from functools import cached_property
from typing import Optional

import numpy as np
import sympy as sp

from scite.core import BMCSModel, ui_field
from scite.core.symbolic import SymbolicExpression


class EC2ParabolaRectangle(BMCSModel):
    """
    EC2 Parabola-Rectangle compression law for concrete (design values).
    
    Implements the parabolic-rectangular stress-strain curve for concrete
    in compression according to EC2 Section 3.1.7 (Figure 3.3).
    
    Uses design compressive strength f_cd = α_cc × f_ck / γ_c
    
    The curve consists of:
    - Parabolic ascending branch up to ε_c2
    - Rectangular (constant stress) plateau from ε_c2 to ε_cu2
    - Zero stress for tension (ε > 0)
    
    Convention: Compression is negative strain, produces negative stress
    """
    
    # -------------------------------------------------------------------------
    # Primary parameters
    # -------------------------------------------------------------------------
    
    f_ck: float = ui_field(
        30.0,
        label=r"$f_{ck}$",
        unit="MPa",
        range=(12.0, 90.0),
        step=5.0,
        description="Characteristic compressive cylinder strength",
        gt=0
    )
    
    alpha_cc: float = ui_field(
        0.85,
        label=r"$\alpha_{cc}$",
        unit="-",
        range=(0.8, 1.0),
        step=0.05,
        description="Coefficient taking account of long term effects (typically 0.85 or 1.0)",
        gt=0,
        le=1.0
    )
    
    gamma_c: float = ui_field(
        1.5,
        label=r"$\gamma_c$",
        unit="-",
        range=(1.0, 1.5),
        step=0.1,
        description="Partial safety factor for concrete",
        ge=1.0
    )
    
    n: float = ui_field(
        2.0,
        label=r"$n$",
        unit="-",
        range=(1.5, 2.5),
        step=0.1,
        description="Exponent for parabolic branch (typically 2.0)",
        gt=0
    )
    
    # -------------------------------------------------------------------------
    # Optional override parameters (None = use EC2 formulas)
    # -------------------------------------------------------------------------
    
    eps_c2: Optional[float] = ui_field(
        None,
        label=r"$\varepsilon_{c2}$",
        unit="-",
        range=(-0.0035, -0.0015),
        step=0.0001,
        description="Strain at peak stress (None = EC2 formula based on f_ck)"
    )
    
    eps_cu2: Optional[float] = ui_field(
        None,
        label=r"$\varepsilon_{cu2}$",
        unit="-",
        range=(-0.0045, -0.0025),
        step=0.0001,
        description="Ultimate compressive strain (None = EC2 formula based on f_ck)"
    )
    
    # -------------------------------------------------------------------------
    # Derived properties (EC2 Table 3.1)
    # -------------------------------------------------------------------------
    
    @cached_property
    def f_cm(self) -> float:
        """Mean compressive strength [MPa] (EC2: f_cm = f_ck + 8)"""
        return self.f_ck + 8.0
    
    @cached_property
    def f_cd(self) -> float:
        """Design compressive strength [MPa]"""
        return self.alpha_cc * self.f_ck / self.gamma_c
    
    @cached_property
    def eps_c2_computed(self) -> float:
        """Strain at peak stress (compression) [-]"""
        if self.eps_c2 is not None:
            return self.eps_c2
        
        # EC2 Table 3.1: ε_c2 in ‰
        if self.f_ck <= 50:
            return -0.002  # 2.0‰ for f_ck ≤ 50 MPa
        else:
            eps_c2_permille = 2.0 + 0.085 * (self.f_ck - 50) ** 0.53
            return -0.001 * eps_c2_permille
    
    @cached_property
    def eps_cu2_computed(self) -> float:
        """Ultimate compressive strain [-]"""
        if self.eps_cu2 is not None:
            return self.eps_cu2
        
        # EC2 Table 3.1: ε_cu2 in ‰
        if self.f_ck <= 50:
            return -0.0035  # 3.5‰ for f_ck ≤ 50 MPa
        else:
            eps_cu2_permille = 2.6 + 35 * ((90 - self.f_ck) / 100) ** 4
            return -0.001 * eps_cu2_permille
    
    # -------------------------------------------------------------------------
    # Symbolic expressions
    # -------------------------------------------------------------------------
    
    @cached_property
    def symbolic_stress(self) -> SymbolicExpression:
        """
        Symbolic expression for parabola-rectangle stress-strain relationship.
        
        Returns:
            SymbolicExpression with signature (eps,) -> sig
        """
        # Define symbols
        eps = sp.Symbol('varepsilon', real=True)
        
        # Parameters
        f_cd = sp.Float(self.f_cd)
        n = sp.Float(self.n)
        eps_c2 = sp.Float(self.eps_c2_computed)
        eps_cu2 = sp.Float(self.eps_cu2_computed)
        
        # EC2 parabola-rectangle curve (Section 3.1.7)
        # Starting from ε = 0 going into compression (negative ε):
        # 1. From 0 to ε_c2: Parabolic ascending branch
        # 2. From ε_c2 to ε_cu2: Rectangular plateau (constant stress)
        # 3. Beyond ε_cu2: Zero (crushing failure)
        #
        # Note: ε_c2 = -0.002, ε_cu2 = -0.0035, so ε_cu2 < ε_c2 < 0
        
        # Parabolic formula: σ = f_cd × [1 - (1 - η)^n] where η = ε / ε_c2
        eta = eps / eps_c2
        sig_parabola = f_cd * (1 - (1 - eta) ** n)
        
        # Complete stress-strain curve
        # Convention: compression is negative strain/stress
        sig = sp.Piecewise(
            (0, eps < eps_cu2),              # Beyond ultimate (ε < -0.0035)
            (-f_cd, eps < eps_c2),           # Plateau (from -0.0035 to -0.002)
            (-sig_parabola, eps < 0),        # Parabola (from -0.002 to 0)
            (0, True)                        # Tension (ε ≥ 0)
        )
        
        return SymbolicExpression(
            name='ec2_parabola_rectangle',
            expression=sig,
            parameters=('varepsilon',)
        )
    
    # -------------------------------------------------------------------------
    # Numerical evaluation
    # -------------------------------------------------------------------------
    
    def get_sig(self, eps: np.ndarray) -> np.ndarray:
        """
        Evaluate stress for given strain.
        
        Args:
            eps: Strain array [-]
            
        Returns:
            Stress array [MPa] (negative for compression, zero for tension)
        """
        sig_func = self.symbolic_stress.lambdify()
        return sig_func(eps)
    
    def get_E_t(self, eps: np.ndarray) -> np.ndarray:
        """
        Evaluate tangent modulus for given strain.
        
        Args:
            eps: Strain array [-]
            
        Returns:
            Tangent modulus array [MPa]
        """
        eps_scalar = np.asarray(eps)
        h = 1e-8  # Small increment for numerical derivative
        
        # Compute derivative: dσ/dε ≈ (σ(ε+h) - σ(ε-h)) / (2h)
        sig_plus = self.get_sig(eps_scalar + h)
        sig_minus = self.get_sig(eps_scalar - h)
        
        E_t = (sig_plus - sig_minus) / (2 * h)
        
        return E_t
    
    # -------------------------------------------------------------------------
    # Plotting support
    # -------------------------------------------------------------------------
    
    def plot_stress_strain(self, ax, n_points: int = 500):
        """
        Plot stress-strain curve on given axes.
        
        Args:
            ax: Matplotlib axes
            n_points: Number of evaluation points
        """
        # Generate strain range (compression only, plus small tension region)
        eps_min = 1.5 * self.eps_cu2_computed
        eps_max = 0.001  # Small positive strain to show zero tension behavior
        eps = np.linspace(eps_min, eps_max, n_points)
        
        # Compute stress
        sig = self.get_sig(eps)
        
        # Plot
        ax.clear()
        ax.plot(eps, sig, 'b-', linewidth=2, label='EC2 Parabola-Rectangle')
        
        # Mark key points
        ax.plot([self.eps_c2_computed], [-self.f_cd], 
                'ro', markersize=8, label=f'Peak: ε_c2={abs(self.eps_c2_computed):.4f}')
        ax.plot([self.eps_cu2_computed], [self.get_sig(np.array([self.eps_cu2_computed]))[0]], 
                'rs', markersize=8, label=f'Ultimate: ε_cu2={abs(self.eps_cu2_computed):.4f}')
        
        # Formatting
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]')
        ax.set_ylabel('Stress σ [MPa]')
        ax.set_title(f'EC2 Parabola-Rectangle: $f_{{cd}}$ = {self.f_cd:.2f} MPa ($f_{{ck}}$ = {self.f_ck:.0f} MPa)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def get_plot_range(self) -> tuple[float, float]:
        """Get recommended strain range for plotting"""
        return (1.5 * self.eps_cu2_computed, 0.001)

    def plotly_figure(self):
        """Return a plotly Figure of the stress-strain curve (compression-only)."""
        import plotly.graph_objects as go

        eps_min, eps_max = self.get_plot_range()
        eps = np.linspace(eps_min, eps_max, 500)
        sig = self.get_sig(eps)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=eps.tolist(), y=sig.tolist(),
            mode="lines", name="EC2 Parabola-Rectangle",
            line=dict(color="#1f77b4", width=2),
        ))
        # Key points
        fig.add_trace(go.Scatter(
            x=[self.eps_c2_computed], y=[-self.f_cd],
            mode="markers+text", name=f"Peak  ε_c2={self.eps_c2_computed:.4f}",
            marker=dict(color="red", size=10, symbol="circle"),
            text=[f"ε_c2={self.eps_c2_computed:.4f}"], textposition="top right",
        ))
        fig.add_trace(go.Scatter(
            x=[self.eps_cu2_computed],
            y=[float(self.get_sig(np.array([self.eps_cu2_computed]))[0])],
            mode="markers+text", name=f"Ultimate  ε_cu2={self.eps_cu2_computed:.4f}",
            marker=dict(color="red", size=10, symbol="square"),
            text=[f"ε_cu2={self.eps_cu2_computed:.4f}"], textposition="top left",
        ))
        fig.add_hline(y=0, line=dict(color="black", width=0.5))
        fig.add_vline(x=0, line=dict(color="black", width=0.5))
        fig.update_layout(
            title=f"EC2 Parabola-Rectangle  f_cd = {self.f_cd:.2f} MPa  (f_ck = {self.f_ck:.0f} MPa)",
            xaxis_title="Strain ε [-]",
            yaxis_title="Stress σ [MPa]",
            legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
            margin=dict(l=60, r=20, t=50, b=50),
        )
        return fig

    # -------------------------------------------------------------------------
    # Information
    # -------------------------------------------------------------------------
    
    def summary(self) -> dict:
        """Get summary of material properties"""
        return {
            'f_ck': f'{self.f_ck:.1f} MPa',
            'f_cm': f'{self.f_cm:.1f} MPa',
            'f_cd': f'{self.f_cd:.2f} MPa',
            'alpha_cc': f'{self.alpha_cc:.2f}',
            'gamma_c': f'{self.gamma_c:.2f}',
            'eps_c2': f'{self.eps_c2_computed:.4f}',
            'eps_cu2': f'{self.eps_cu2_computed:.4f}',
            'n': f'{self.n:.1f}',
        }
