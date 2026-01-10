"""
Cross-section geometric shapes for structural analysis.

This module provides modern, type-safe shape classes for defining
cross-section geometry. All shapes inherit from the Shape base class
and provide methods for discretization and geometric properties.
"""

from typing import Protocol, List, Tuple
import numpy as np
import numpy.typing as npt
from matplotlib.patches import Rectangle

from bmcs_cross_section.core import BMCSModel, ui_field


class Shape(Protocol):
    """
    Protocol for cross-section shapes.
    
    All shape implementations must provide:
    - get_y_coordinates: Discretization points along height
    - get_width_at_y: Width at given y-coordinate(s)
    - get_area: Total cross-sectional area
    """
    
    def get_y_coordinates(self, n: int) -> npt.NDArray[np.float64]:
        """
        Get discretization points along the height.
        
        Args:
            n: Number of discretization points
            
        Returns:
            Array of y-coordinates from top (y=0) to bottom (y=h)
        """
        ...
    
    def get_width_at_y(self, y: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get cross-section width at given y-coordinate(s).
        
        Args:
            y: Y-coordinate(s) from top [mm]
            
        Returns:
            Width(s) at the specified y-coordinate(s) [mm]
        """
        ...
    
    def get_area(self) -> float:
        """
        Get total cross-sectional area.
        
        Returns:
            Area [mm²]
        """
        ...


class RectangularShape(BMCSModel):
    """
    Rectangular cross-section shape.
    
    Coordinate system:
        - Origin at top center of cross-section
        - y-axis positive downward
        - Width b is constant along height
    
    Attributes:
        b: Width of the rectangle [mm]
        h: Height of the rectangle [mm]
    """
    
    b: float = ui_field(
        300.0,
        label=r"$b$",
        unit="mm",
        range=(10.0, 2000.0),
        step=10.0,
        description="Width",
        ge=10.0,
        le=2000.0
    )
    
    h: float = ui_field(
        500.0,
        label=r"$h$",
        unit="mm",
        range=(10.0, 3000.0),
        step=10.0,
        description="Height",
        ge=10.0,
        le=3000.0
    )
    
    # Derived properties
    @property
    def area(self) -> float:
        """Total cross-sectional area [mm²]"""
        return self.b * self.h
    
    @property
    def centroid_y(self) -> float:
        """Y-coordinate of centroid from bottom [mm]"""
        return self.h / 2.0
    
    @property
    def I_y(self) -> float:
        """Second moment of area about horizontal centroidal axis [mm⁴]"""
        return self.b * self.h**3 / 12.0
    
    @property
    def W_top(self) -> float:
        """Section modulus at top fiber [mm³]"""
        return self.I_y / self.centroid_y
    
    @property
    def W_bottom(self) -> float:
        """Section modulus at bottom fiber [mm³]"""
        return self.I_y / self.centroid_y
    
    def get_y_coordinates(self, n: int = 100) -> npt.NDArray[np.float64]:
        """
        Get uniformly spaced discretization points.
        
        Standard convention: y=0 at bottom, y=h at top.
        
        Args:
            n: Number of points (default: 100)
            
        Returns:
            Array of y-coordinates from 0 (bottom) to h (top) [mm]
        """
        return np.linspace(0, self.h, n)
    
    def get_width_at_y(self, y: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get width at given y-coordinate(s).
        
        For rectangular shape, width is constant.
        
        Args:
            y: Y-coordinate(s) [mm]
            
        Returns:
            Width (b) for all y-coordinates [mm]
        """
        y_array = np.atleast_1d(y)
        return np.full_like(y_array, self.b)
    
    def get_area(self) -> float:
        """
        Get total cross-sectional area.
        
        Returns:
            Area = b × h [mm²]
        """
        return self.area
    
    def get_plot_patches(self) -> List[Tuple[Rectangle, str]]:
        """
        Get matplotlib patches for plotting (horizontally centered).
        
        Returns:
            List of (patch, label) tuples for plotting
        """
        # Center horizontally: x from -b/2 to +b/2
        rect = Rectangle((-self.b/2, 0), self.b, self.h,
                        fill=False, edgecolor='blue', linewidth=2)
        return [(rect, 'Concrete')]
    
    def get_boundary_polygon(self) -> npt.NDArray[np.float64]:
        """
        Get external boundary polygon vertices (horizontally centered).
        
        Returns:
            Array of (x, y) coordinates defining external boundary, shape (n, 2)
        """
        # Rectangle: 4 vertices, counter-clockwise from bottom-left
        vertices = np.array([
            [-self.b/2, 0],        # bottom-left
            [self.b/2, 0],         # bottom-right
            [self.b/2, self.h],    # top-right
            [-self.b/2, self.h],   # top-left
        ])
        return vertices
    
    def get_plot_xlim(self) -> Tuple[float, float]:
        """Get x-axis limits for centered plot."""
        margin = 50.0
        return (-self.b/2 - margin, self.b/2 + margin)
    
    def get_plot_ylim(self) -> Tuple[float, float]:
        """Get y-axis limits."""
        margin = 50.0
        return (-margin, self.h + margin)


class TShape(BMCSModel):
    """
    T-shaped cross-section (flange at top).
    
    Coordinate system:
        - y=0 at bottom of web, positive upward
        - Web extends from y=0 to y=h_w (bottom part)
        - Flange extends from y=h_w to y=h_total (top part)
    
    Attributes:
        b_f: Flange width [mm]
        h_f: Flange height [mm]
        b_w: Web width [mm]
        h_w: Web height [mm]
    """
    
    b_f: float = ui_field(
        600.0,
        label=r"$b_f$",
        unit="mm",
        range=(10.0, 3000.0),
        step=10.0,
        description="Flange width",
        ge=10.0,
        le=3000.0
    )
    
    h_f: float = ui_field(
        150.0,
        label=r"$h_f$",
        unit="mm",
        range=(10.0, 500.0),
        step=10.0,
        description="Flange height",
        ge=10.0,
        le=500.0
    )
    
    b_w: float = ui_field(
        200.0,
        label=r"$b_w$",
        unit="mm",
        range=(10.0, 1000.0),
        step=10.0,
        description="Web width",
        ge=10.0,
        le=1000.0
    )
    
    h_w: float = ui_field(
        400.0,
        label=r"$h_w$",
        unit="mm",
        range=(10.0, 2000.0),
        step=10.0,
        description="Web height",
        ge=10.0,
        le=2000.0
    )
    
    @property
    def h_total(self) -> float:
        """Total height [mm]"""
        return self.h_f + self.h_w
    
    @property
    def area(self) -> float:
        """Total cross-sectional area [mm²]"""
        return self.b_f * self.h_f + self.b_w * self.h_w
    
    @property
    def centroid_y(self) -> float:
        """Y-coordinate of centroid from bottom [mm]"""
        A_f = self.b_f * self.h_f
        A_w = self.b_w * self.h_w
        # Web centroid from bottom
        y_w = self.h_w / 2.0
        # Flange centroid from bottom
        y_f = self.h_w + self.h_f / 2.0
        return (A_f * y_f + A_w * y_w) / self.area
    
    @property
    def I_y(self) -> float:
        """Second moment of area about horizontal centroidal axis [mm⁴]"""
        # Web contribution (bottom part)
        I_w_own = self.b_w * self.h_w**3 / 12.0
        d_w = abs(self.h_w / 2.0 - self.centroid_y)
        I_w = I_w_own + self.b_w * self.h_w * d_w**2
        
        # Flange contribution (top part)
        I_f_own = self.b_f * self.h_f**3 / 12.0
        d_f = abs(self.h_w + self.h_f / 2.0 - self.centroid_y)
        I_f = I_f_own + self.b_f * self.h_f * d_f**2
        
        return I_f + I_w
    
    @property
    def W_top(self) -> float:
        """Section modulus at top fiber [mm³]"""
        return self.I_y / self.centroid_y
    
    @property
    def W_bottom(self) -> float:
        """Section modulus at bottom fiber [mm³]"""
        return self.I_y / (self.h_total - self.centroid_y)
    
    def get_y_coordinates(self, n: int = 100) -> npt.NDArray[np.float64]:
        """
        Get discretization points with denser spacing at flange-web junction.
        
        Args:
            n: Total number of points (default: 100)
            
        Returns:
            Array of y-coordinates from 0 to h_total [mm]
        """
        # Allocate points proportional to segment heights
        ratio = self.h_w / self.h_total
        n_web = max(int(n * ratio), 2)
        n_flange = n - n_web + 1  # +1 for overlap at junction
        
        y_web = np.linspace(0, self.h_w, n_web)
        y_flange = np.linspace(self.h_w, self.h_total, n_flange)[1:]  # Skip duplicate
        
        return np.concatenate([y_web, y_flange])
    
    def get_width_at_y(self, y: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get width at given y-coordinate(s).
        
        Width is b_w in web (y ≤ h_w) and b_f in flange (y > h_w).
        
        Args:
            y: Y-coordinate(s) [mm]
            
        Returns:
            Width at each y-coordinate [mm]
        """
        y_array = np.atleast_1d(y)
        width = np.where(y_array <= self.h_w, self.b_w, self.b_f)
        return width
    
    def get_area(self) -> float:
        """
        Get total cross-sectional area.
        
        Returns:
            Area = b_f×h_f + b_w×h_w [mm²]
        """
        return self.area
    
    def get_plot_patches(self) -> List[Tuple[Rectangle, str]]:
        """
        Get matplotlib patches for plotting (horizontally centered).
        
        Returns:
            List of (patch, label) tuples for plotting
        """
        patches = []
        
        # Web (bottom, centered)
        web = Rectangle((-self.b_w/2, 0), self.b_w, self.h_w,
                       fill=False, edgecolor='blue', linewidth=2)
        patches.append((web, 'Web'))
        
        # Flange (top, centered)
        flange = Rectangle((-self.b_f/2, self.h_w), self.b_f, self.h_f,
                          fill=False, edgecolor='blue', linewidth=2)
        patches.append((flange, 'Flange'))
        
        return patches
    
    def get_boundary_polygon(self) -> npt.NDArray[np.float64]:
        """
        Get external boundary polygon vertices (horizontally centered).
        
        Returns:
            Array of (x, y) coordinates defining external boundary, shape (n, 2)
            Counter-clockwise from bottom-left
        """
        # T-section: 8 vertices (web bottom -> transition to flange -> flange top -> back)
        vertices = np.array([
            [-self.b_w/2, 0],          # bottom-left (web)
            [self.b_w/2, 0],           # bottom-right (web)
            [self.b_w/2, self.h_w],    # transition right (web to flange)
            [self.b_f/2, self.h_w],    # flange bottom-right
            [self.b_f/2, self.h_total],# flange top-right
            [-self.b_f/2, self.h_total],# flange top-left
            [-self.b_f/2, self.h_w],   # flange bottom-left
            [-self.b_w/2, self.h_w],   # transition left (flange to web)
        ])
        return vertices
    
    def get_plot_xlim(self) -> Tuple[float, float]:
        """Get x-axis limits for centered plot."""
        margin = 50.0
        max_width = max(self.b_f, self.b_w)
        return (-max_width/2 - margin, max_width/2 + margin)
    
    def get_plot_ylim(self) -> Tuple[float, float]:
        """Get y-axis limits."""
        margin = 50.0
        return (-margin, self.h_total + margin)


class IShape(BMCSModel):
    """
    I-shaped cross-section (symmetric double-T).
    
    Coordinate system:
        - y=0 at bottom, positive upward
        - Bottom flange: y=0 to y=h_f
        - Web: y=h_f to y=h_f+h_w
        - Top flange: y=h_f+h_w to y=h_total
    
    Attributes:
        b_f: Flange width [mm]
        h_f: Flange height [mm]
        b_w: Web width [mm]
        h_w: Web height [mm]
    """
    
    b_f: float = ui_field(
        400.0,
        label=r"$b_f$",
        unit="mm",
        range=(10.0, 2000.0),
        step=10.0,
        description="Flange width",
        ge=10.0,
        le=2000.0
    )
    
    h_f: float = ui_field(
        100.0,
        label=r"$h_f$",
        unit="mm",
        range=(10.0, 300.0),
        step=10.0,
        description="Flange height",
        ge=10.0,
        le=300.0
    )
    
    b_w: float = ui_field(
        150.0,
        label=r"$b_w$",
        unit="mm",
        range=(10.0, 800.0),
        step=10.0,
        description="Web width",
        ge=10.0,
        le=800.0
    )
    
    h_w: float = ui_field(
        300.0,
        label=r"$h_w$",
        unit="mm",
        range=(10.0, 1500.0),
        step=10.0,
        description="Web height",
        ge=10.0,
        le=1500.0
    )
    
    @property
    def h_total(self) -> float:
        """Total height [mm]"""
        return 2 * self.h_f + self.h_w
    
    @property
    def area(self) -> float:
        """Total cross-sectional area [mm²]"""
        return 2 * self.b_f * self.h_f + self.b_w * self.h_w
    
    @property
    def centroid_y(self) -> float:
        """Y-coordinate of centroid from bottom [mm] - at mid-height due to symmetry"""
        return self.h_total / 2.0
    
    @property
    def I_y(self) -> float:
        """Second moment of area about horizontal centroidal axis [mm⁴]"""
        # Due to symmetry, can compute for half and double
        # Bottom flange contribution (calculation same for top due to symmetry)
        I_f_own = self.b_f * self.h_f**3 / 12.0
        d_f = self.centroid_y - self.h_f / 2.0
        I_f = I_f_own + self.b_f * self.h_f * d_f**2
        
        # Web contribution
        I_w_own = self.b_w * self.h_w**3 / 12.0
        # Web centroid is at centroid_y (symmetric), so d_w = 0
        I_w = I_w_own
        
        # Total (top flange + web + bottom flange)
        return 2 * I_f + I_w
    
    @property
    def W_top(self) -> float:
        """Section modulus at top fiber [mm³]"""
        return self.I_y / self.centroid_y
    
    @property
    def W_bottom(self) -> float:
        """Section modulus at bottom fiber [mm³] - same as W_top due to symmetry"""
        return self.W_top
    
    def get_y_coordinates(self, n: int = 100) -> npt.NDArray[np.float64]:
        """
        Get discretization points with denser spacing at flange-web junctions.
        
        Args:
            n: Total number of points (default: 100)
            
        Returns:
            Array of y-coordinates from 0 to h_total [mm]
        """
        # Allocate points proportional to segment heights
        h_total = self.h_total
        ratio_f = self.h_f / h_total
        ratio_w = self.h_w / h_total
        
        n_flange_top = max(int(n * ratio_f), 2)
        n_web = max(int(n * ratio_w), 2)
        n_flange_bottom = n - n_flange_top - n_web + 2  # +2 for overlaps
        
        y_top_flange = np.linspace(0, self.h_f, n_flange_top)
        y_web = np.linspace(self.h_f, self.h_f + self.h_w, n_web)[1:]
        y_bottom_flange = np.linspace(self.h_f + self.h_w, h_total, n_flange_bottom)[1:]
        
        return np.concatenate([y_top_flange, y_web, y_bottom_flange])
    
    def get_width_at_y(self, y: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get width at given y-coordinate(s).
        
        Width is b_f in flanges and b_w in web.
        
        Args:
            y: Y-coordinate(s) [mm]
            
        Returns:
            Width at each y-coordinate [mm]
        """
        y_array = np.atleast_1d(y)
        
        # In flange if y ≤ h_f (top) or y ≥ h_f + h_w (bottom)
        in_flange = (y_array <= self.h_f) | (y_array >= self.h_f + self.h_w)
        width = np.where(in_flange, self.b_f, self.b_w)
        
        return width
    
    def get_area(self) -> float:
        """
        Get total cross-sectional area.
        
        Returns:
            Area = 2×b_f×h_f + b_w×h_w [mm²]
        """
        return self.area
    
    def get_plot_patches(self) -> List[Tuple[Rectangle, str]]:
        """
        Get matplotlib patches for plotting (horizontally centered).
        
        Returns:
            List of (patch, label) tuples for plotting
        """
        patches = []
        
        # Bottom flange (centered)
        bot_flange = Rectangle((-self.b_f/2, 0), self.b_f, self.h_f,
                              fill=False, edgecolor='blue', linewidth=2)
        patches.append((bot_flange, 'Bottom Flange'))
        
        # Web (middle, centered)
        web = Rectangle((-self.b_w/2, self.h_f), self.b_w, self.h_w,
                       fill=False, edgecolor='blue', linewidth=2)
        patches.append((web, 'Web'))
        
        # Top flange (centered)
        top_flange = Rectangle((-self.b_f/2, self.h_f + self.h_w), self.b_f, self.h_f,
                              fill=False, edgecolor='blue', linewidth=2)
        patches.append((top_flange, 'Top Flange'))
        
        return patches
    
    def get_boundary_polygon(self) -> npt.NDArray[np.float64]:
        """
        Get external boundary polygon vertices (horizontally centered).
        
        Returns:
            Array of (x, y) coordinates defining external boundary, shape (n, 2)
            Counter-clockwise from bottom-left
        """
        # I-section: 12 vertices (bottom flange -> web transitions -> top flange -> back)
        vertices = np.array([
            [-self.b_f/2, 0],              # bottom-left (bottom flange)
            [self.b_f/2, 0],               # bottom-right (bottom flange)
            [self.b_f/2, self.h_f],        # bottom flange top-right
            [self.b_w/2, self.h_f],        # web bottom-right
            [self.b_w/2, self.h_f + self.h_w],  # web top-right
            [self.b_f/2, self.h_f + self.h_w],  # top flange bottom-right
            [self.b_f/2, self.h_total],    # top-right (top flange)
            [-self.b_f/2, self.h_total],   # top-left (top flange)
            [-self.b_f/2, self.h_f + self.h_w], # top flange bottom-left
            [-self.b_w/2, self.h_f + self.h_w], # web top-left
            [-self.b_w/2, self.h_f],       # web bottom-left
            [-self.b_f/2, self.h_f],       # bottom flange top-left
        ])
        return vertices
    
    def get_plot_xlim(self) -> Tuple[float, float]:
        """Get x-axis limits for centered plot."""
        margin = 50.0
        return (-self.b_f/2 - margin, self.b_f/2 + margin)
    
    def get_plot_ylim(self) -> Tuple[float, float]:
        """Get y-axis limits."""
        margin = 50.0
        return (-margin, self.h_total + margin)
