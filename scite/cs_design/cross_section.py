"""
Cross-section assembly combining geometry, materials, and reinforcement.

This module provides the complete CrossSection class that integrates:
- Geometric shapes (from shapes.py)
- Concrete material (from matmod.ec2_concrete)
- Reinforcement layout (from reinforcement.py)

The key method get_N_M(kappa, eps_top) computes axial force and moment
for a given strain distribution, which is the interface mkappa will use.
"""

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.patches import Polygon
from matplotlib.patches import Rectangle as MPLRectangle
from scite.core import BMCSModel, ui_field
from scite.cs_design.reinforcement import ReinforcementLayout
from scite.cs_design.shapes import BandShape, IShape, InvTShape, RectangularShape, TShape
from scite.matmod.carbon_reinforcement import CarbonReinforcement
from scite.matmod.ec2_concrete import EC2Concrete
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.matmod.foam_concrete import FoamConcrete
from scite.matmod.steel_reinforcement import SteelReinforcement

ConcreteMaterial = Union[EC2ParabolaRectangle, EC2Concrete]
RegionShape = Union[BandShape, RectangularShape, TShape, InvTShape, IShape]
RegionMaterial = Union[EC2ParabolaRectangle, EC2Concrete, FoamConcrete,
                       SteelReinforcement, CarbonReinforcement]

# Default sketch colour of an additional matrix region (ochre — ballast / fill)
REGION_COLOR = '#d4a017'


def to_scalar(val):
    """Convert numpy array or scalar to Python float (numpy 2.x compatible)."""
    if hasattr(val, 'item'):
        return float(val.item())
    return float(val)


# ── Integration kernel helpers ────────────────────────────────────────────────

# Strain attributes at which a material law changes branch.  Inserting the
# corresponding heights as integration breakpoints makes the 2-point Gauss rule
# exact for piecewise-polynomial laws (parabola-rectangle) and removes the
# quadrature error at kinks and cliffs.
_BREAKPOINT_ATTRS = ('eps_c2_computed', 'eps_cu2_computed', 'eps_c1', 'eps_cu1',
                     'eps_cr_computed', 'eps_tu_computed', 'eps_cr', 'eps_end')
_SYMMETRIC_BREAKPOINT_ATTRS = ('eps_yd', 'eps_ud')


def _strain_breakpoints(material) -> np.ndarray:
    """Branch strains of a material law (the law's own list when it provides one)."""
    bp = getattr(material, 'strain_breakpoints', None)
    if bp is not None:
        return np.asarray(bp, dtype=float)
    out = [0.0]
    for name in _BREAKPOINT_ATTRS:
        v = getattr(material, name, None)
        if isinstance(v, (int, float)) and np.isfinite(v):
            out.append(float(v))
    for name in _SYMMETRIC_BREAKPOINT_ATTRS:
        v = getattr(material, name, None)
        if isinstance(v, (int, float)) and np.isfinite(v):
            out.extend((float(v), -float(v)))
    return np.asarray(out, dtype=float)


def _initial_modulus(material) -> float:
    """Initial (uncracked) modulus of a matrix or reinforcement material [MPa]."""
    for name in ('E_ct_computed', 'E_s', 'E'):
        v = getattr(material, name, None)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def _band_moments(bands) -> tuple[float, float, float]:
    """(A, S_0, I_0) about y = 0 of piecewise-constant width bands."""
    A = S = I = 0.0
    for y0, y1, b in bands:
        A += b * (y1 - y0)
        S += b * (y1 ** 2 - y0 ** 2) / 2.0
        I += b * (y1 ** 3 - y0 ** 3) / 3.0
    return A, S, I


class MatrixRegion(BMCSModel):
    """
    Additional matrix component of a composite cross-section.

    A region shares the plane-section strain field of the primary section
    (rigid connection) but carries its own constitutive law — e.g. a foam
    concrete ballast between and above the ribs, a concrete top cover plate,
    or a steel plate / profile.  Regions are assumed disjoint from the primary
    shape and from each other.

    Attributes:
        shape: Geometry on the section's y-axis (y=0 at the primary bottom).
               ``BandShape`` is the usual choice; other shapes start at y=0
               and are lifted by ``y_offset``.
        material: Constitutive law (compression-only or symmetric).
        y_offset: Vertical shift of the shape [mm].
        label: Component name — regions with the same label are reported
               together (e.g. a fill split into two bands).
        color: Sketch / plot colour (None → default ochre).
    """

    shape: RegionShape
    material: RegionMaterial
    y_offset: float = 0.0
    label: str = 'region'
    color: Optional[str] = None

    def get_bands(self) -> list[tuple[float, float, float]]:
        """Width bands ``[(y0, y1, b), ...]`` on the section's y-axis."""
        o = self.y_offset
        return [(y0 + o, y1 + o, b) for y0, y1, b in self.shape.get_bands()]

    @property
    def y_bot(self) -> float:
        """Lowest fibre of the region [mm]."""
        return min(y0 for y0, _, _ in self.get_bands())

    @property
    def y_top(self) -> float:
        """Highest fibre of the region [mm]."""
        return max(y1 for _, y1, _ in self.get_bands())

    @property
    def area(self) -> float:
        """Region area [mm²]."""
        return _band_moments(self.get_bands())[0]

    def get_width_at_y(self, y: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Region width at y [mm] (0 outside the region)."""
        y = np.atleast_1d(np.asarray(y, dtype=float))
        w = np.zeros_like(y)
        for y0, y1, b in self.get_bands():
            w = np.where((y >= y0) & (y <= y1), b, w)
        return w

    def get_boundary_polygons(self) -> list[npt.NDArray[np.float64]]:
        """Drawing polygons, horizontally centred at x = 0."""
        if hasattr(self.shape, 'get_boundary_polygons'):
            polys = self.shape.get_boundary_polygons()
        else:
            polys = [self.shape.get_boundary_polygon()]
        return [p + np.array([0.0, self.y_offset]) for p in polys]


@dataclass
class ComponentResultant:
    """Force resultant of one matrix component (primary concrete or a region)."""

    label: str
    N: float            # axial force [N] (negative = compression)
    M: float            # Σ dF·(y − y_ref) [N·mm]
    y_ref: float
    y_bot: float
    y_top: float

    @property
    def y_centroid(self) -> float:
        """Height of the force resultant [mm] (mid-height when |N| is negligible)."""
        if abs(self.N) > 1e-9:
            return self.y_ref + self.M / self.N
        return 0.5 * (self.y_bot + self.y_top)


@dataclass
class SectionResultants:
    """Result of ``CrossSection.integrate``: per-component and total N, M."""

    components: List[ComponentResultant]      # [0] = primary concrete
    N_reinf: float                            # [N]
    M_reinf: float                            # [N·mm] about y_ref
    layer_forces: List[float] = field(default_factory=list)
    y_ref: float = 0.0

    @property
    def N_matrix(self) -> float:
        return sum(c.N for c in self.components)

    @property
    def M_matrix(self) -> float:
        return sum(c.M for c in self.components)

    @property
    def N(self) -> float:
        return self.N_matrix + self.N_reinf

    @property
    def M(self) -> float:
        """Σ dF·(y − y_ref) over all components [N·mm] — negative for sagging."""
        return self.M_matrix + self.M_reinf

    def grouped(self) -> List[ComponentResultant]:
        """Components merged by label (e.g. a fill split into two bands), in order."""
        out: dict[str, ComponentResultant] = {}
        for c in self.components:
            g = out.get(c.label)
            if g is None:
                out[c.label] = ComponentResultant(c.label, c.N, c.M, c.y_ref, c.y_bot, c.y_top)
            else:
                g.N += c.N
                g.M += c.M
                g.y_bot, g.y_top = min(g.y_bot, c.y_bot), max(g.y_top, c.y_top)
        return list(out.values())


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
    
    Composite sections: ``regions`` adds further matrix components (each a
    ``MatrixRegion`` with its own shape and law) that share the strain field.
    ``h_total`` is then the envelope height over all components, while
    ``y_top_primary`` is the top fibre of the primary concrete.

    Attributes:
        shape: Geometric shape (RectangularShape, TShape, InvTShape, IShape)
        concrete: Concrete material model (EC2ParabolaRectangle)
        reinforcement: Reinforcement layout (ReinforcementLayout)
        regions: Additional matrix components (empty = plain section)
        n_points: Number of discretization points for integration
        quadrature: 'gauss' (band-wise Gauss with breakpoints) or 'legacy'
                    (100-point uniform rule used before the kernel refactor)
    """

    shape: RectangularShape | TShape | InvTShape | IShape
    concrete: ConcreteMaterial
    reinforcement: ReinforcementLayout
    regions: List[MatrixRegion] = []

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

    quadrature: Literal['gauss', 'legacy'] = ui_field(
        'gauss',
        label="Quadrature",
        description=("'gauss' = 2-point Gauss per band between breakpoints (exact for "
                     "parabola-rectangle); 'legacy' = former 100-point uniform rule"),
    )

    def model_post_init(self, __context) -> None:
        """Initialize with defaults if needed."""
        if self.concrete is None:
            self.concrete = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=1.0, gamma_c=1.5)
        if self.reinforcement is None:
            self.reinforcement = ReinforcementLayout()

    @property
    def y_top_primary(self) -> float:
        """Top fibre of the primary concrete shape [mm]."""
        if hasattr(self.shape, 'h'):
            return self.shape.h
        elif hasattr(self.shape, 'h_total'):
            return self.shape.h_total
        return 0.0

    @property
    def h_total(self) -> float:
        """Total (envelope) height of the cross-section over all components [mm]."""
        h = self.y_top_primary
        for reg in self.regions:
            h = max(h, reg.y_top)
        return h

    def get_width_at_y(self, y: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Total matrix width at y, summed over the primary shape and all regions [mm]."""
        y = np.atleast_1d(np.asarray(y, dtype=float))
        w = np.where(y <= self.y_top_primary, self.shape.get_width_at_y(y), 0.0)
        for reg in self.regions:
            w = w + reg.get_width_at_y(y)
        return w

    def transformed_properties(self, E_ref: Optional[float] = None) -> tuple[float, float, float]:
        """Uncracked transformed matrix properties ``(A, S_0, I_0)`` about y = 0.

        Region contributions are weighted by n_r = E_r / E_ref (default E_ref =
        primary concrete modulus).  Reinforcement is NOT included — callers add
        it with their own modular ratio.
        """
        if E_ref is None:
            E_ref = _initial_modulus(self.concrete)
        A, S, I = _band_moments(self.shape.get_bands())
        for reg in self.regions:
            n_r = _initial_modulus(reg.material) / E_ref if E_ref > 0 else 0.0
            A_r, S_r, I_r = _band_moments(reg.get_bands())
            A, S, I = A + n_r * A_r, S + n_r * S_r, I + n_r * I_r
        return A, S, I

    # ── Integration kernel ────────────────────────────────────────────────────

    def _components(self):
        """(label, bands, material, width_fn) for the primary and each region."""
        yield ('concrete', self.shape.get_bands(), self.concrete, self.shape.get_width_at_y)
        for reg in self.regions:
            yield (reg.label, reg.get_bands(), reg.material, reg.get_width_at_y)

    def _integrate_gauss(self, bands, material, kappa, eps_bot, y_ref, H):
        n_sub = max(self.n_points // 2, 10)
        bps = _strain_breakpoints(material)
        nodes, weights = [], []
        for y0, y1, b in bands:
            if b == 0.0 or y1 <= y0:
                continue
            m = max(1, int(np.ceil(n_sub * (y1 - y0) / H)))
            pts = np.linspace(y0, y1, m + 1)
            if abs(kappa) > 0.0:
                yb = (eps_bot - bps) / kappa
                pts = np.union1d(pts, yb[(yb > y0) & (yb < y1)])
            half = 0.5 * np.diff(pts)
            mid = 0.5 * (pts[:-1] + pts[1:])
            off = half / np.sqrt(3.0)
            nodes.extend((mid - off, mid + off))
            weights.extend((half * b, half * b))
        if not nodes:
            return 0.0, 0.0
        y = np.concatenate(nodes)
        w = np.concatenate(weights)
        sig = np.broadcast_to(np.asarray(material.get_sig(eps_bot - kappa * y), dtype=float),
                              y.shape)
        F = sig * w
        return float(np.sum(F)), float(np.sum(F * (y - y_ref)))

    @staticmethod
    def _integrate_legacy(width_fn, material, kappa, eps_bot, y_ref, H, y_cap):
        # Former StressStrainProfile rule: 100 uniform points, weight H/100.
        z = np.linspace(0.0, H, 100)
        dz = H / 100.0
        width = np.where(z <= y_cap, np.asarray(width_fn(z), dtype=float), 0.0)
        sig = np.broadcast_to(np.asarray(material.get_sig(eps_bot - kappa * z), dtype=float),
                              z.shape)
        F = sig * width * dz
        return float(np.sum(F)), float(np.sum(F * (z - y_ref)))

    def integrate(self, kappa: float, eps_bot: float, y_ref: float = 0.0) -> SectionResultants:
        """Integrate all matrix components and reinforcement layers.

        Plane sections: ε(y) = eps_bot − κ·y (y from the bottom, positive up).

        Args:
            kappa: Curvature [1/mm] (positive → compression at the top)
            eps_bot: Strain at y = 0 [-]
            y_ref: Moment reference height [mm]

        Returns:
            SectionResultants with per-component ``N``, ``M = Σ dF·(y − y_ref)``
            and the reinforcement contribution.  Note the sign: ``M`` is
            negative for sagging (``StressStrainProfile`` reports −M).
        """
        H = self.h_total
        comps = []
        for label, bands, material, width_fn in self._components():
            if self.quadrature == 'legacy':
                y_cap = self.y_top_primary if material is self.concrete else np.inf
                N, M = self._integrate_legacy(width_fn, material, kappa, eps_bot, y_ref, H, y_cap)
            else:
                N, M = self._integrate_gauss(bands, material, kappa, eps_bot, y_ref, H)
            comps.append(ComponentResultant(
                label=label, N=N, M=M, y_ref=y_ref,
                y_bot=min(y0 for y0, _, _ in bands), y_top=max(y1 for _, y1, _ in bands)))

        N_s = M_s = 0.0
        forces = []
        for layer in self.reinforcement.layers:
            eps = eps_bot - kappa * layer.z
            F = to_scalar(layer.get_force(eps))
            forces.append(F)
            N_s += F
            M_s += to_scalar(layer.get_moment(eps, y_ref))
        return SectionResultants(components=comps, N_reinf=N_s, M_reinf=M_s,
                                 layer_forces=forces, y_ref=y_ref)
    
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
        res = self.integrate(kappa, eps_bottom, y_ref)
        return float(res.N), float(res.M)
    
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
