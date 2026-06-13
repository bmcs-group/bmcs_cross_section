"""
EC2 Concrete Material Model (Modern Implementation)

Implements the stress-strain relationship for concrete according to EC2
(Eurocode 2), using the new core module with Pydantic validation and
symbolic expression support.

References:
    EN 1992-1-1:2004 (Eurocode 2), Section 3.1.5 and Table 3.1
"""

from functools import cached_property
from typing import Optional

import numpy as np
import sympy as sp

from scite.core import BMCSModel, ui_field
from scite.core.symbolic import SymbolicExpression


class EC2Concrete(BMCSModel):
    """
    EC2 Concrete constitutive model.
    
    Implements the parabolic-rectangular stress-strain curve for concrete
    in compression (EC2 Eq. 3.14) and a linear-softening branch in tension.
    
    Parameters are derived from the characteristic compressive strength f_ck
    according to EC2 Table 3.1, or can be specified explicitly.
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
        description="Characteristic compressive strength of concrete (cylinder)",
        gt=0
    )
    
    factor: float = ui_field(
        1.0,
        label=r"Factor",
        unit="-",
        range=(0.1, 2.0),
        step=0.1,
        description="Safety/adjustment factor for stress",
        gt=0
    )
    
    mu: float = ui_field(
        0.0,
        label=r"$\mu$",
        unit="-",
        range=(0.0, 1.0),
        step=0.05,
        description="Post-crack tensile strength ratio (for fiber reinforcement)",
        ge=0,
        le=1
    )
    
    # -------------------------------------------------------------------------
    # Optional override parameters (None = use EC2 formulas)
    # -------------------------------------------------------------------------
    
    E_cc: Optional[float] = ui_field(
        None,
        label=r"$E_{cc}$",
        unit="MPa",
        range=(20000.0, 50000.0),
        step=1000.0,
        description="Compression modulus (None = EC2 formula)"
    )
    
    E_ct: Optional[float] = ui_field(
        None,
        label=r"$E_{ct}$",
        unit="MPa",
        range=(20000.0, 50000.0),
        step=1000.0,
        description="Tension modulus (None = EC2 formula)"
    )
    
    eps_cr: Optional[float] = ui_field(
        None,
        label=r"$\varepsilon_{cr}$",
        unit="-",
        range=(0.00005, 0.0005),
        step=0.00001,
        description="Cracking strain (None = f_ctm/E_ct)"
    )
    
    eps_tu: Optional[float] = ui_field(
        None,
        label=r"$\varepsilon_{tu}$",
        unit="-",
        range=(0.0001, 0.001),
        step=0.0001,
        description="Ultimate tensile strain (None = eps_cr)"
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
        """Design compressive strength [MPa] (EC2: f_cd = α_cc × f_ck / γ_c)"""
        # Using α_cc = 1.0 and γ_c = 1.5 (typical EC2 values)
        alpha_cc = 1.0
        gamma_c = 1.5
        return alpha_cc * self.f_ck / gamma_c
    
    @cached_property
    def f_ctm(self) -> float:
        """Mean axial tensile strength [MPa]"""
        if self.f_ck <= 50:
            return 0.3 * self.f_ck ** (2/3)
        else:
            return 2.12 * np.log(1 + self.f_cm / 10)
    
    @cached_property
    def E_cm(self) -> float:
        """Secant modulus of elasticity [MPa]"""
        return 22000 * (self.f_cm / 10) ** 0.3
    
    @cached_property
    def E_cc_computed(self) -> float:
        """Compression modulus (computed or specified) [MPa]"""
        return self.E_cc if self.E_cc is not None else self.E_cm
    
    @cached_property
    def E_ct_computed(self) -> float:
        """Tension modulus (computed or specified) [MPa]"""
        return self.E_ct if self.E_ct is not None else self.E_cm
    
    @cached_property
    def eps_c1(self) -> float:
        """Strain at peak stress (compression) [-]"""
        eps_c1_permille = 0.7 * self.f_cm ** 0.31
        eps_c1_permille = min(eps_c1_permille, 2.8)
        return -0.001 * eps_c1_permille
    
    @cached_property
    def eps_cu1(self) -> float:
        """Ultimate compressive strain [-]"""
        if self.f_ck <= 50:
            return -0.0035
        else:
            return -0.001 * (2.8 + 27 * ((98 - self.f_cm) / 100) ** 4)
    
    @cached_property
    def eps_cr_computed(self) -> float:
        """Cracking strain (computed or specified) [-]"""
        return self.eps_cr if self.eps_cr is not None else self.f_ctm / self.E_ct_computed
    
    @cached_property
    def eps_tu_computed(self) -> float:
        """Ultimate tensile strain (computed or specified) [-]"""
        return self.eps_tu if self.eps_tu is not None else self.eps_cr_computed
    
    @cached_property
    def eps_cu2_computed(self) -> float:
        """Ultimate compressive strain (alias for eps_cu1, for API compatibility with EC2ParabolaRectangle)."""
        return self.eps_cu1

    @cached_property
    def k(self) -> float:
        """EC2 parameter k for compression curve [-]"""
        return 1.05 * self.E_cc_computed * abs(self.eps_c1) / self.f_cm
    
    # -------------------------------------------------------------------------
    # Symbolic expressions
    # -------------------------------------------------------------------------
    
    @cached_property
    def symbolic_stress(self) -> SymbolicExpression:
        """
        Symbolic expression for stress-strain relationship.
        
        Returns:
            SymbolicExpression with signature (eps,) -> sig
        """
        # Define symbols
        eps = sp.Symbol('varepsilon', real=True)
        
        # Parameters
        f_cm = sp.Float(self.f_cm)
        k = sp.Float(self.k)
        eps_c1 = sp.Float(self.eps_c1)
        eps_cu1 = sp.Float(self.eps_cu1)
        E_ct = sp.Float(self.E_ct_computed)
        eps_cr = sp.Float(self.eps_cr_computed)
        eps_tu = sp.Float(self.eps_tu_computed)
        mu = sp.Float(self.mu)
        
        # EC2 eq. (3.14) - compression
        eta = eps / eps_c1
        sig_c = f_cm * (k * eta - eta ** 2) / (1 + eta * (k - 2))
        
        # Find strain at zero stress (for limiting compression branch)
        # This is needed to avoid unphysical extension beyond ultimate strain
        try:
            roots = sp.solve(sig_c, eps)
            eps_c_min = min([float(r.evalf()) for r in roots if r.is_real])
        except:
            eps_c_min = float(eps_cu1)
        
        # Complete stress-strain curve
        # Convention: compression is negative, tension is positive
        sig = sp.Piecewise(
            (0, eps < eps_c_min),  # Beyond ultimate compression
            (-sig_c, eps < 0),  # Compression branch (negative stress)
            (E_ct * eps, eps < eps_cr),  # Elastic tension (positive stress)
            (mu * E_ct * eps_cr, eps < eps_tu),  # Post-crack tension
            (0, True)  # Beyond ultimate tension
        )
        
        return SymbolicExpression(
            name='ec2_stress',
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
            Stress array [MPa]
        """
        # Use lambdified function for efficiency
        sig_func = self.symbolic_stress.lambdify()
        sig = sig_func(eps)
        return self.factor * sig
    
    def get_E_t(self, eps: np.ndarray) -> np.ndarray:
        """
        Evaluate tangent modulus for given strain.
        
        Args:
            eps: Strain array [-]
            
        Returns:
            Tangent modulus array [MPa]
        """
        # Use numerical differentiation (more reliable than symbolic for Piecewise)
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
        # Generate strain range
        eps_min = 1.5 * self.eps_cu1
        eps_max = 3.0 * self.eps_tu_computed
        eps = np.linspace(eps_min, eps_max, n_points)
        
        # Compute stress
        sig = self.get_sig(eps)
        
        # Plot
        ax.clear()
        ax.plot(eps, sig, 'b-', linewidth=2, label='EC2 Concrete')
        
        # Mark key points
        ax.plot([self.eps_c1], [-self.factor * self.f_cm], 
                'ro', markersize=8, label=f'Peak: σ={self.f_cm:.1f} MPa')
        ax.plot([self.eps_cu1], [self.get_sig(np.array([self.eps_cu1]))[0]], 
                'rs', markersize=8, label=f'Ultimate: ε={self.eps_cu1:.4f}')
        ax.plot([self.eps_cr_computed], [self.factor * self.f_ctm], 
                'go', markersize=8, label=f'Crack: ε={self.eps_cr_computed:.5f}')
        
        # Formatting
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]')
        ax.set_ylabel('Stress σ [MPa]')
        ax.set_title(f'EC2 Concrete: $f_{{cm}}$ = {self.f_cm:.1f} MPa')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def get_plot_range(self) -> tuple[float, float]:
        """Get recommended strain range for plotting"""
        return (1.5 * self.eps_cu1, 3.0 * self.eps_tu_computed)

    def plotly_figure(self):
        """Return a plotly Figure of the stress-strain curve (compression + tension)."""
        import plotly.graph_objects as go

        eps_min, eps_max = self.get_plot_range()
        eps = np.linspace(eps_min, eps_max, 500)
        sig = self.get_sig(eps)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=eps.tolist(), y=sig.tolist(),
            mode="lines", name="EC2 Concrete",
            line=dict(color="#1f77b4", width=2),
        ))
        # Compression peak
        fig.add_trace(go.Scatter(
            x=[self.eps_c1], y=[-self.factor * self.f_cm],
            mode="markers+text", name=f"Peak  σ={self.f_cm:.1f} MPa",
            marker=dict(color="red", size=10, symbol="circle"),
            text=[f"σ_peak={self.f_cm:.1f}"], textposition="top right",
        ))
        # Ultimate compressive strain
        fig.add_trace(go.Scatter(
            x=[self.eps_cu1],
            y=[float(self.get_sig(np.array([self.eps_cu1]))[0])],
            mode="markers+text", name=f"ε_cu1={self.eps_cu1:.4f}",
            marker=dict(color="red", size=10, symbol="square"),
            text=[f"ε_cu1={self.eps_cu1:.4f}"], textposition="bottom right",
        ))
        # Crack point
        fig.add_trace(go.Scatter(
            x=[self.eps_cr_computed], y=[self.factor * self.f_ctm],
            mode="markers+text", name=f"Crack  ε_cr={self.eps_cr_computed:.5f}",
            marker=dict(color="green", size=10, symbol="diamond"),
            text=[f"f_ctm={self.f_ctm:.2f}"], textposition="top right",
        ))
        fig.add_hline(y=0, line=dict(color="black", width=0.5))
        fig.add_vline(x=0, line=dict(color="black", width=0.5))
        fig.update_layout(
            title=f"EC2 Concrete  f_cm = {self.f_cm:.1f} MPa  (μ = {self.mu:.2f})",
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
            'f_cm': f'{self.f_cm:.1f} MPa',
            'f_ck': f'{self.f_ck:.1f} MPa',
            'f_ctm': f'{self.f_ctm:.2f} MPa',
            'E_cm': f'{self.E_cm:.0f} MPa',
            'eps_c1': f'{self.eps_c1:.4f}',
            'eps_cu1': f'{self.eps_cu1:.4f}',
            'eps_cr': f'{self.eps_cr_computed:.5f}',
            'k': f'{self.k:.2f}',
        }
