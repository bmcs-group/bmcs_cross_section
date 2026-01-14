"""
Cross-section assembly combining geometry, materials, and reinforcement.

This module provides the complete CrossSection class that integrates:
- Geometric shapes (from shapes.py)
- Concrete material (from matmod.ec2_concrete)
- Reinforcement layout (from reinforcement.py)

The key method get_N_M(kappa, eps_top) computes axial force and moment
for a given strain distribution, which is the interface mkappa will use.
"""

from typing import Optional
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle as MPLRectangle, Polygon

from scite.core import BMCSModel, ui_field
from scite.cs_design.shapes import RectangularShape, TShape, IShape
from scite.cs_design.reinforcement import ReinforcementLayout
from scite.matmod.ec2_concrete import EC2Concrete


class CrossSection(BMCSModel):
    """
    Complete cross-section assembly with geometry, concrete, and reinforcement.
    
    This class combines:
    - Geometric shape (defines cross-section geometry)
    - Concrete material (EC2Concrete model)
    - Reinforcement layout (steel layers)
    
    The main analysis method is get_N_M(kappa, eps_top) which computes
    axial force N and bending moment M for a given strain distribution.
    This is the key interface that mkappa will use in Phase 3.
    
    Coordinate system:
        - y-axis: Positive downward from top of section
        - Strain: ε(y) = ε_top - κ×y (plane sections remain plane)
        - Compression: Negative strain/stress
        - Tension: Positive strain/stress
    
    Attributes:
        shape: Geometric shape (RectangularShape, TShape, IShape)
        concrete: Concrete material model (EC2Concrete)
        reinforcement: Reinforcement layout (ReinforcementLayout)
        n_points: Number of discretization points for integration
    """
    
    shape: RectangularShape | TShape | IShape
    concrete: EC2Concrete
    reinforcement: ReinforcementLayout
    
    n_points: int = ui_field(
        100,
        label=r"$n_{points}$",
        unit="-",
        range=(10, 500),
        step=10,
        description="Discretization points",
        ge=10,
        le=500
    )
    
    def model_post_init(self, __context) -> None:
        """Initialize with defaults if needed."""
        if self.concrete is None:
            self.concrete = EC2Concrete()
        if self.reinforcement is None:
            self.reinforcement = ReinforcementLayout()
    
    @property
    def h_total(self) -> float:
        """Total height of cross-section [mm]"""
        if hasattr(self.shape, 'h'):
            return self.shape.h
        elif hasattr(self.shape, 'h_total'):
            return self.shape.h_total
        return 0.0
    
    @property
    def A_c(self) -> float:
        """Concrete area [mm²]"""
        return self.shape.area
    
    @property
    def A_s(self) -> float:
        """Total steel area [mm²]"""
        return self.reinforcement.total_area
    
    @property
    def reinforcement_ratio(self) -> float:
        """Reinforcement ratio ρ = A_s / A_c [-]"""
        if self.A_c == 0:
            return 0.0
        return self.A_s / self.A_c
    
    def get_N_M(
        self,
        kappa: float,
        eps_bottom: float = 0.0,
        y_ref: float = 0.0
    ) -> tuple[float, float]:
        """
        Compute axial force and moment for given strain distribution.
        
        This is the KEY METHOD that mkappa will use in Phase 3!
        
        Standard coordinate system:
        - y = 0 at BOTTOM of section
        - y = h at TOP of section
        - y-axis positive UPWARD
        
        The method:
        1. Computes strain distribution: ε(y) = ε_bottom - κ×y
        2. Evaluates concrete stresses from material model
        3. Integrates concrete contribution to N and M
        4. Evaluates steel stresses for each layer
        5. Sums steel contribution to N and M
        6. Returns total (N, M)
        
        Args:
            kappa: Curvature [1/mm]
                   Positive κ → compression at top, tension at bottom
            eps_bottom: Strain at bottom fiber (y=0) [-]
                   Negative = compression, Positive = tension
            y_ref: Reference point for moment computation [mm]
                   Default y_ref=0 gives moment about bottom
        
        Returns:
            (N, M): Tuple of:
                N: Axial force [N] (negative=compression, positive=tension)
                M: Bending moment [Nmm] (about y_ref)
        
        Example:
            >>> cs = CrossSection(shape=RectangularShape(b=300, h=500), ...)
            >>> kappa = 0.00001  # Positive curvature (top in compression)
            >>> eps_bottom = 0.001  # Bottom in tension
            >>> N, M = cs.get_N_M(kappa, eps_bottom)
        """
        # 1. Get discretization points (y from bottom to top)
        y = self.shape.get_y_coordinates(self.n_points)
        widths = self.shape.get_width_at_y(y)
        
        # 2. Compute strain distribution (plane sections remain plane)
        # ε(y) = ε_bottom - κ×y (strain decreases going upward for positive κ)
        strains = eps_bottom - kappa * y
        
        # 3. Get concrete stresses
        sig_c = self.concrete.get_sig(strains)
        
        # 4. Compute element areas (trapezoidal rule)
        dy = np.diff(y, prepend=0)
        dA_c = widths * dy
        
        # 5. Concrete contribution to N and M
        N_c = np.sum(sig_c * dA_c)
        M_c = np.sum(sig_c * dA_c * (y - y_ref))
        
        # 6. Steel contribution from reinforcement layout
        N_s, M_s = self.reinforcement.get_N_M(kappa, eps_bottom, y_ref)
        
        # 7. Total force and moment
        N_total = float(N_c + N_s)
        M_total = float(M_c + M_s)
        
        return N_total, M_total
    
    def get_neutral_axis(
        self,
        kappa: float,
        eps_bottom_initial: float = 0.001,
        tol: float = 100.0,
        max_iter: int = 50
    ) -> float:
        """
        Find neutral axis position for pure bending (N = 0).
        
        Uses Newton-Raphson iteration to find eps_bottom such that N(kappa, eps_bottom) = 0.
        This is used for pure bending analysis where axial force is zero.
        
        Standard coordinate system: y=0 at bottom, positive upward.
        For positive curvature, top is in compression, bottom in tension.
        
        Args:
            kappa: Curvature [1/mm]
            eps_bottom_initial: Initial guess for bottom strain [-]
            tol: Convergence tolerance for N [N]
            max_iter: Maximum iterations
        
        Returns:
            eps_bottom: Bottom strain that gives N ≈ 0 [-]
        
        Raises:
            ValueError: If convergence not achieved
        """
        # Ensure kappa is not zero
        if abs(kappa) < 1e-12:
            raise ValueError("Cannot find neutral axis for zero curvature")
        
        eps_bottom = eps_bottom_initial
        
        for i in range(max_iter):
            # Compute N at current eps_bottom
            N, _ = self.get_N_M(kappa, eps_bottom)
            
            # Check convergence
            if abs(N) < tol:
                return eps_bottom
            
            # Compute derivative dN/d(eps_bottom) numerically
            deps = 1e-8
            N_plus, _ = self.get_N_M(kappa, eps_bottom + deps)
            dN_deps = (N_plus - N) / deps
            
            # Newton-Raphson update
            if abs(dN_deps) > 1e-6:
                delta_eps = -N / dN_deps
                # Limit step size to avoid overshooting
                max_step = 0.001
                if abs(delta_eps) > max_step:
                    delta_eps = np.sign(delta_eps) * max_step
                eps_bottom = eps_bottom + delta_eps
            else:
                # Fallback to bisection if derivative too small
                eps_bottom = eps_bottom - np.sign(N) * 0.0001
        
        raise ValueError(f"Neutral axis not found after {max_iter} iterations. "
                        f"Final N = {N:.1f} N")
    
    def get_strain_at_y(self, y: float, kappa: float, eps_bottom: float) -> float:
        """
        Get strain at specific y-coordinate.
        
        Standard convention: y measured from bottom upward.
        
        Args:
            y: Y-coordinate from bottom [mm]
            kappa: Curvature [1/mm]
            eps_bottom: Bottom strain [-]
        
        Returns:
            Strain at y [-]
        """
        return eps_bottom - kappa * y
    
    def get_stress_distribution(
        self,
        kappa: float,
        eps_bottom: float
    ) -> tuple[npt.NDArray, npt.NDArray, npt.NDArray]:
        """
        Get stress distribution in concrete.
        
        Args:
            kappa: Curvature [1/mm]
            eps_bottom: Bottom strain [-]
        
        Returns:
            (y, eps, sig): Y-coordinates [mm], strains [-], stresses [MPa]
        """
        y = self.shape.get_y_coordinates(self.n_points)
        eps = eps_bottom - kappa * y
        sig = self.concrete.get_sig(eps)
        
        return y, eps, sig
    
    def plot_cross_section(
        self,
        ax: Optional[plt.Axes] = None,
        show_dimensions: bool = True,
        show_reinforcement: bool = True
    ) -> plt.Axes:
        """
        Plot cross-section geometry with reinforcement.
        
        Standard convention: y=0 at bottom, positive upward.
        Horizontally centered: x=0 at center of shape.
        
        Args:
            ax: Matplotlib axes (creates new if None)
            show_dimensions: Show dimension labels
            show_reinforcement: Show reinforcement layers
        
        Returns:
            Matplotlib axes
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 10))
        
        # Get boundary polygon for external outline only
        vertices = self.shape.get_boundary_polygon()
        polygon = Polygon(vertices, fill=True, facecolor='lightgray', 
                         edgecolor='blue', linewidth=2, alpha=0.3, label='Concrete')
        ax.add_patch(polygon)
        
        # Plot reinforcement layers
        if show_reinforcement and self.reinforcement.n_layers > 0:
            for layer in self.reinforcement.layers:
                # Bar diameter scaled for visibility
                bar_radius = np.sqrt(layer.A_s / np.pi / 4) / 2
                
                # Draw bar at centerline (y measured from bottom, x=0 at center)
                circle = plt.Circle((0, layer.z), bar_radius,
                                  color='red', alpha=0.8, zorder=10, label='Reinforcement')
                ax.add_patch(circle)
        
        # Configure axes
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linewidth=0.5, alpha=0.5)
        ax.axvline(x=0, color='black', linewidth=0.5, alpha=0.5)
        ax.set_xlabel('Width [mm]')
        ax.set_ylabel('Height from bottom [mm]')
        
        # Set limits using shape's methods
        ax.set_xlim(self.shape.get_plot_xlim())
        ax.set_ylim(self.shape.get_plot_ylim())
        
        # Add single legend entry for concrete
        ax.plot([], [], 's', color='lightgray', markersize=10, 
                markeredgecolor='blue', markeredgewidth=2, label='Concrete')
        if show_reinforcement and self.reinforcement.n_layers > 0:
            ax.plot([], [], 'ro', markersize=8, label='Reinforcement')
        ax.legend()
        
        # Dimensions
        if show_dimensions:
            h = self.h_total
            xlim = ax.get_xlim()
            text_x = float(xlim[1] - 80)
            ax.text(text_x, float(h/2), 
                   f'h = {h:.0f} mm\nA_c = {self.A_c:,.0f} mm²\nA_s = {self.A_s:.0f} mm²\nρ = {self.reinforcement_ratio:.4f}',
                   verticalalignment='center',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        return ax
    
    def plot_strain_distribution(
        self,
        kappa: float,
        eps_bottom: float,
        ax: Optional[plt.Axes] = None
    ) -> plt.Axes:
        """
        Plot strain distribution through height.
        
        Standard convention: y=0 at bottom, positive upward.
        
        Args:
            kappa: Curvature [1/mm]
            eps_bottom: Bottom strain [-]
            ax: Matplotlib axes (creates new if None)
        
        Returns:
            Matplotlib axes
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 8))
        
        y, eps, _ = self.get_stress_distribution(kappa, eps_bottom)
        
        # Plot strain profile
        ax.plot(eps, y, 'b-', linewidth=2, label='Concrete')
        
        # Mark zero strain (neutral axis)
        # ε(y) = ε_bottom - κ×y, at neutral axis ε=0, so y_na = ε_bottom / κ
        if kappa != 0:
            y_na = eps_bottom / kappa
            if 0 <= y_na <= self.h_total:
                ax.axhline(y=y_na, color='green', linestyle='--', 
                          linewidth=1.5, label=f'N.A. (y={y_na:.1f}mm)')
                ax.plot(0, y_na, 'go', markersize=10)
        
        # Mark reinforcement layer strains
        for layer in self.reinforcement.layers:
            eps_s = self.get_strain_at_y(layer.z, kappa, eps_bottom)
            ax.plot(eps_s, layer.z, 'ro', markersize=8)
        
        ax.axvline(x=0, color='black', linewidth=0.5, alpha=0.5)
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('Strain [-]')
        ax.set_ylabel('Height from bottom [mm]')
        ax.set_title(f'Strain Distribution\nκ={kappa:.6f} 1/mm, ε_bottom={eps_bottom:.5f}')
        ax.legend()
        
        return ax
    
    def plot_stress_distribution(
        self,
        kappa: float,
        eps_bottom: float,
        ax: Optional[plt.Axes] = None
    ) -> plt.Axes:
        """
        Plot stress distribution through height.
        
        Standard convention: y=0 at bottom, positive upward.
        
        Args:
            kappa: Curvature [1/mm]
            eps_bottom: Bottom strain [-]
            ax: Matplotlib axes (creates new if None)
        
        Returns:
            Matplotlib axes
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 8))
        
        y, eps, sig = self.get_stress_distribution(kappa, eps_bottom)
        
        # Plot stress profile
        ax.plot(sig, y, 'b-', linewidth=2, label='Concrete')
        
        # Shade compression/tension zones
        ax.fill_betweenx(y, sig, 0, where=(sig < 0).tolist(), 
                        alpha=0.2, color='blue', label='Compression')
        ax.fill_betweenx(y, sig, 0, where=(sig > 0).tolist(), 
                        alpha=0.2, color='red', label='Tension')
        
        # Mark reinforcement layer stresses
        for layer in self.reinforcement.layers:
            eps_s = self.get_strain_at_y(layer.z, kappa, eps_bottom)
            sig_s = layer.get_sig(eps_s)
            ax.plot(sig_s, layer.z, 'ro', markersize=8)
        
        ax.axvline(x=0, color='black', linewidth=0.5, alpha=0.5)
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('Stress [MPa]')
        ax.set_ylabel('Height from bottom [mm]')
        ax.set_title(f'Stress Distribution\nκ={kappa:.6f} 1/mm, ε_bottom={eps_bottom:.5f}')
        ax.legend()
        
        return ax
    
    def get_summary(self) -> dict:
        """
        Get summary information about the cross-section.
        
        Returns:
            Dictionary with cross-section properties
        """
        return {
            'geometry': {
                'type': type(self.shape).__name__,
                'height': self.h_total,
                'concrete_area': self.A_c,
            },
            'concrete': {
                'f_cm': self.concrete.f_cm,
                'f_ck': self.concrete.f_ck,
                'E_cm': self.concrete.E_cm,
            },
            'reinforcement': {
                'n_layers': self.reinforcement.n_layers,
                'total_area': self.A_s,
                'ratio': self.reinforcement_ratio,
                'centroid_z': self.reinforcement.centroid_z,
            }
        }
