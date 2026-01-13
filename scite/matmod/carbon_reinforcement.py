"""
Carbon Reinforcement Material Model

Linear elastic-brittle behavior with optional post-peak softening
for numerical stability in nonlinear analysis.
"""

import numpy as np
import numpy.typing as npt
from pydantic import Field, field_validator
import matplotlib.pyplot as plt
from typing import Optional

from bmcs_cross_section.core import BMCSModel


class CarbonReinforcement(BMCSModel):
    """
    Carbon FRP reinforcement material model.
    
    Behavior:
    - Linear elastic up to failure: σ = E·ε
    - Brittle failure at f_t (no yielding)
    - Optional post-peak softening for numerical stability
    
    The post-peak softening prevents abrupt stress drops that can
    cause convergence issues in nonlinear solvers.
    
    Parameters:
    - E: Elastic modulus [MPa]
    - f_t: Tensile strength [MPa]
    - post_peak_factor: Softening slope relative to elastic slope
                        (2.5 means softening is 2.5× steeper)
    - factor: Safety factor for design (e.g., 1.0 for mean, 1/1.25 for design)
    """
    
    # Material properties
    E: float = Field(
        default=165000.0,
        description="Elastic modulus [MPa]",
        gt=0
    )
    
    f_t: float = Field(
        default=2000.0,
        description="Tensile strength [MPa]",
        gt=0
    )
    
    post_peak_factor: float = Field(
        default=2.5,
        description="Post-peak softening slope factor (relative to elastic slope)",
        gt=0
    )
    
    factor: float = Field(
        default=1.0,
        description="Safety factor (1.0 for mean values, 1/gamma_s for design)",
        gt=0,
        le=1.0
    )
    
    @property
    def f_t_scaled(self) -> float:
        """Scaled tensile strength (considering safety factor)."""
        return self.factor * self.f_t
    
    @property
    def eps_cr(self) -> float:
        """Cracking/failure strain [-]."""
        return self.f_t_scaled / self.E
    
    @property
    def eps_end(self) -> float:
        """End of post-peak softening strain [-]."""
        return (1 + 1.0 / self.post_peak_factor) * self.eps_cr
    
    def get_sig(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get stress for given strain(s).
        
        Stress-strain relationship:
        - ε < 0: σ = 0 (no compression capacity)
        - 0 ≤ ε < ε_cr: σ = E·ε (linear elastic)
        - ε_cr ≤ ε < ε_end: σ = f_t - k·E·(ε - ε_cr) (softening)
        - ε ≥ ε_end: σ = 0 (complete failure)
        
        where k = post_peak_factor
        
        Args:
            eps: Strain value(s) [-]
            
        Returns:
            Stress value(s) [MPa]
        """
        eps = np.atleast_1d(eps)
        sig = np.zeros_like(eps)
        
        f_t = self.f_t_scaled
        eps_cr = self.eps_cr
        eps_end = self.eps_end
        k = self.post_peak_factor
        
        # Linear elastic range: 0 ≤ ε < ε_cr
        elastic_mask = (eps >= 0) & (eps < eps_cr)
        sig[elastic_mask] = self.E * eps[elastic_mask]
        
        # Post-peak softening: ε_cr ≤ ε < ε_end
        softening_mask = (eps >= eps_cr) & (eps < eps_end)
        sig[softening_mask] = f_t - k * self.E * (eps[softening_mask] - eps_cr)
        
        # Beyond ε_end: σ = 0 (already initialized to zero)
        
        return sig if sig.shape[0] > 1 else sig[0]
    
    def get_eps_plot_range(self) -> npt.NDArray[np.float64]:
        """Get strain range for plotting."""
        return np.linspace(-0.1 * self.eps_cr, 1.2 * self.eps_end, 300)
    
    def plot_stress_strain(
        self,
        ax: Optional[plt.Axes] = None,
        show_limits: bool = True,
        color: str = 'darkred',
        alpha_fill: float = 0.1,
        label: Optional[str] = None
    ) -> plt.Axes:
        """
        Plot stress-strain curve.
        
        Args:
            ax: Matplotlib axes (creates new if None)
            show_limits: Show characteristic points
            color: Curve color
            alpha_fill: Fill transparency
            label: Legend label
            
        Returns:
            Matplotlib axes
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))
        
        # Calculate curve
        eps_range = self.get_eps_plot_range()
        sig_range = self.get_sig(eps_range)
        
        # Plot
        plot_label = label or f'Carbon FRP (f_t={self.f_t:.0f} MPa)'
        ax.plot(eps_range * 1000, sig_range, color=color, linewidth=2, label=plot_label)
        ax.fill_between(eps_range * 1000, 0, sig_range, color=color, alpha=alpha_fill)
        
        # Mark characteristic points
        if show_limits:
            # Failure point
            ax.plot(self.eps_cr * 1000, self.f_t_scaled, 'o', 
                   color=color, markersize=8, label=f'Failure (ε={self.eps_cr*1000:.2f}‰)')
            
            # End of softening
            ax.axvline(self.eps_end * 1000, color=color, linestyle='--', 
                      alpha=0.5, linewidth=1)
        
        # Labels
        ax.set_xlabel('Strain ε [‰]')
        ax.set_ylabel('Stress σ [MPa]')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        return ax


def create_carbon(
    grade: str = 'C1500',
    factor: float = 1.0,
    post_peak_factor: float = 2.5
) -> CarbonReinforcement:
    """
    Create carbon FRP material from typical grades.
    
    Common grades:
    - C1500: f_t = 1500 MPa, E = 150 GPa
    - C2000: f_t = 2000 MPa, E = 165 GPa (typical COMBAR)
    - C2500: f_t = 2500 MPa, E = 170 GPa
    
    Args:
        grade: Material grade
        factor: Safety factor (1.0 for mean, 1/1.25 for design)
        post_peak_factor: Softening slope factor
        
    Returns:
        CarbonReinforcement instance
    """
    grade_params = {
        'C1500': {'E': 150000, 'f_t': 1500},
        'C2000': {'E': 165000, 'f_t': 2000},
        'C2500': {'E': 170000, 'f_t': 2500},
    }
    
    if grade not in grade_params:
        raise ValueError(f"Unknown carbon grade: {grade}. Available: {list(grade_params.keys())}")
    
    params = grade_params[grade]
    
    return CarbonReinforcement(
        E=params['E'],
        f_t=params['f_t'],
        factor=factor,
        post_peak_factor=post_peak_factor
    )


if __name__ == '__main__':
    # Demonstration
    import matplotlib.pyplot as plt
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Compare grades
    ax1 = axes[0]
    for grade in ['C1500', 'C2000', 'C2500']:
        carbon = create_carbon(grade)
        carbon.plot_stress_strain(ax=ax1, show_limits=False, label=grade)
    ax1.set_title('Carbon FRP Grades Comparison')
    ax1.legend()
    
    # Compare post-peak factors
    ax2 = axes[1]
    for ppf in [1.0, 2.5, 5.0]:
        carbon = CarbonReinforcement(post_peak_factor=ppf)
        carbon.plot_stress_strain(
            ax=ax2, 
            show_limits=False,
            label=f'Post-peak factor = {ppf}'
        )
    ax2.set_title('Post-Peak Softening Effect')
    ax2.legend()
    
    plt.tight_layout()
    plt.show()
