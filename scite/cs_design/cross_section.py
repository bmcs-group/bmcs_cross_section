"""
Cross-section assembly combining geometry, materials, and reinforcement.

This module provides the complete CrossSection class that integrates:
- Geometric shapes (from shapes.py)
- Concrete material (from matmod.ec2_concrete)
- Reinforcement layout (from reinforcement.py)

The key method get_N_M(kappa, eps_top) computes axial force and moment
for a given strain distribution, which is the interface mkappa will use.
"""

from typing import Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.patches import Polygon
from matplotlib.patches import Rectangle as MPLRectangle
from scite.core import BMCSModel, ui_field
from scite.cs_design.reinforcement import ReinforcementLayout
from scite.cs_design.shapes import IShape, RectangularShape, TShape
from scite.matmod.ec2_concrete import EC2Concrete
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle

ConcreteMaterial = Union[EC2ParabolaRectangle, EC2Concrete]


def to_scalar(val):
    """Convert numpy array or scalar to Python float (numpy 2.x compatible)."""
    if hasattr(val, 'item'):
        return float(val.item())
    return float(val)


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
        concrete: Concrete material model (EC2ParabolaRectangle)
        reinforcement: Reinforcement layout (ReinforcementLayout)
        n_points: Number of discretization points for integration
    """
    
    shape: RectangularShape | TShape | IShape
    concrete: ConcreteMaterial
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
            self.concrete = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=1.0, gamma_c=1.5)
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
        N_total = to_scalar(N_c + N_s)
        M_total = to_scalar(M_c + M_s)
        
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
        *,
        show_dimensions: bool = True,
        show_reinforcement: bool = True,
        show_neutral_axis: Optional[float] = None,
        show_beff_dashes: bool = True,
        show_layer_labels: bool = True,
        show_material_box: bool = False,
        title: str = '',
    ) -> None:
        """Draw this cross-section as a schematic sketch.

        All contexts in trr280_app use this single method so that the visual
        style is consistent everywhere.

        Parameters
        ----------
        ax : plt.Axes or None
            Target axes; a new figure is created when None.
        show_dimensions : bool
            Draw b and h dimension arrows with labels.
        show_reinforcement : bool
            Draw reinforcement layer circles.
        show_neutral_axis : float or None
            z-coordinate (from bottom) of neutral axis; draws a red dashed line.
        show_beff_dashes : bool
            For T-sections: draw dashed web-edge lines and b_w label.
        show_layer_labels : bool
            Draw "A=…mm²" text beside each reinforcement circle.
        show_material_box : bool
            Draw A_r / ρ annotation box (used in M-κ model view).
        title : str
            Axes title; empty string suppresses.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(5, 7))

        layers = []
        if show_reinforcement:
            for layer in self.reinforcement.layers:
                mat = layer.material
                color = '#e84e1b' if hasattr(mat, 'f_t') else '#1f77b4'
                layers.append({'z': float(layer.z), 'A': float(layer.A_s), 'color': color})

        CrossSection._sketch(
            ax, self.shape, layers,
            show_dimensions=show_dimensions,
            show_neutral_axis=show_neutral_axis,
            show_beff_dashes=show_beff_dashes,
            show_layer_labels=show_layer_labels,
            show_material_box=show_material_box,
            title=title,
        )

    @staticmethod
    def _sketch(
        ax,
        shape,
        layers,
        *,
        show_dimensions: bool = True,
        show_neutral_axis: Optional[float] = None,
        show_beff_dashes: bool = True,
        show_layer_labels: bool = True,
        show_material_box: bool = False,
        title: str = '',
    ) -> None:
        """Canonical cross-section sketch renderer.

        Parameters
        ----------
        ax : plt.Axes
        shape : scite Shape object (RectangularShape, TShape, IShape, …)
        layers : list of {'z': float, 'A': float, 'color': str}
            Reinforcement layers; empty list suppresses reinforcement drawing.
        show_dimensions : draw b / h arrows with numeric labels
        show_neutral_axis : z from bottom [mm], draws red dashed axhline
        show_beff_dashes : T-section web-edge dashes + b_w label
        show_layer_labels : "A=…mm²" text beside each circle
        show_material_box : A_r / ρ annotation box (mkappa / beam performance)
        title : axes title string
        """
        import matplotlib.patches as mpatches

        CONC_FACE = '#d9d9d9'
        CONC_EDGE = 'black'

        # ── Concrete body ─────────────────────────────────────────────────────
        is_rect = hasattr(shape, 'b') and hasattr(shape, 'h')
        is_t    = hasattr(shape, 'b_w') and hasattr(shape, 'h_w')

        if is_rect and not is_t:
            b   = float(shape.b)
            h   = float(shape.h)
            ax.add_patch(mpatches.Rectangle(
                (0, 0), b, h,
                linewidth=1.5, edgecolor=CONC_EDGE, facecolor=CONC_FACE, zorder=1,
            ))
            cx = b / 2.0
        else:
            vertices = shape.get_boundary_polygon()   # (n, 2), x centred at 0
            xs, ys   = vertices[:, 0], vertices[:, 1]
            x_shift  = float(-xs.min())
            b        = float(xs.max() - xs.min())
            h        = float(ys.max() - ys.min())
            poly_pts = np.column_stack([xs + x_shift, ys])
            ax.add_patch(mpatches.Polygon(
                poly_pts, closed=True,
                linewidth=1.5, edgecolor=CONC_EDGE, facecolor=CONC_FACE, zorder=1,
            ))
            cx = b / 2.0

        # ── T-section: web-edge dashes + b_w label ────────────────────────────
        if is_t and show_beff_dashes:
            b_w   = float(shape.b_w)
            h_w   = float(shape.h_w)
            h_f   = float(shape.h_f)
            x_wl  = (b - b_w) / 2.0
            x_wr  = (b + b_w) / 2.0
            for xv in (x_wl, x_wr):
                ax.plot([xv, xv], [0, h_w], color='#555', ls='--', lw=0.9,
                        alpha=0.7, zorder=2)
            y_bw = h_w + h_f * 0.45
            ax.annotate('', xy=(x_wr, y_bw), xytext=(x_wl, y_bw),
                        arrowprops=dict(arrowstyle='<->', color='#555', lw=0.8))
            ax.text(cx, h_w + h_f * 0.75, f'bw={b_w:.0f}',
                    ha='center', va='bottom', fontsize=6, color='#555')

        # ── Reinforcement circles ─────────────────────────────────────────────
        for layer in layers:
            z     = float(layer['z'])
            A     = float(layer['A'])
            color = layer.get('color', '#1f77b4')
            r     = max(min(np.sqrt(A / np.pi) * 0.5, b * 0.06), b * 0.025)
            ax.add_patch(mpatches.Circle(
                (cx, z), r, facecolor=color, edgecolor='black', lw=1.0, zorder=3,
            ))
            if show_layer_labels:
                ax.text(b + b * 0.07, z, f'A={A:.0f} mm²',
                        va='center', fontsize=6, color='black')

        # ── Neutral axis ──────────────────────────────────────────────────────
        if show_neutral_axis is not None and 0.0 < show_neutral_axis < h:
            ax.axhline(y=show_neutral_axis, color='red', ls='--', lw=1.2, alpha=0.85)
            ax.text(b * 1.02, show_neutral_axis,
                    f'z_na={show_neutral_axis:.0f}', va='bottom', fontsize=6, color='red')

        # ── A_r / ρ box (optional, used by M-κ / beam-performance views) ──────
        if show_material_box and layers:
            A_s_tot  = sum(float(l['A']) for l in layers)
            z_min    = min(float(l['z']) for l in layers)
            d_eff    = max(h - z_min, 1.0)
            rho      = A_s_tot / (b * d_eff) if b > 0 else 0.0
            ann      = f'$A_r$ = {A_s_tot/100:.2f} cm²\n$\\rho$ = {rho*100:.3f} %'
            ax.text(b * 1.22, 0.0, ann,
                    ha='left', va='bottom', fontsize=9, color='black',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightcoral',
                              alpha=0.15, edgecolor='black', linewidth=0.7))

        # ── Dimension arrows ──────────────────────────────────────────────────
        if show_dimensions:
            b_label = f'b_eff={b:.0f}' if is_t else f'b={b:.0f}'
            # b-arrow: below section (tripled gap)
            ax.annotate('', xy=(b, -h * 0.15), xytext=(0, -h * 0.15),
                        arrowprops=dict(arrowstyle='<->', color='black', lw=1.0))
            ax.text(b / 2, -h * 0.22, b_label, ha='center', va='top', fontsize=9)
            # h-arrow: to the left of section (tripled gap)
            ax.annotate('', xy=(-b * 0.3, h), xytext=(-b * 0.3, 0),
                        arrowprops=dict(arrowstyle='<->', color='black', lw=1.0))
            ax.text(-b * 0.42, h / 2, f'h={h:.0f}',
                    ha='center', va='center', fontsize=9, rotation=90)

        # ── Axes formatting ───────────────────────────────────────────────────
        ax.set_xlim(-b * 0.55, b * 1.5)
        ax.set_ylim(-h * 0.40, h * 1.15)
        ax.set_aspect('equal', adjustable='datalim')
        ax.axis('off')
        if title:
            ax.set_title(title, fontsize=8, loc='left')
    
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
