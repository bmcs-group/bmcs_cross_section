"""
Reinforcement layers for cross-section design.

This module provides classes for defining reinforcement in concrete cross-sections,
integrating with material models from Phase 1 (matmod).
"""

from __future__ import annotations
from typing import Optional, List, Any, Union
import numpy as np
import numpy.typing as npt
from pydantic import field_validator

from scite.core import BMCSModel, ui_field
from scite.matmod.steel_reinforcement import SteelReinforcement, create_steel


def to_scalar(val):
    """Convert numpy array or scalar to Python float (numpy 2.x compatible)."""
    if hasattr(val, 'item'):
        return float(val.item())
    return float(val)


class ReinforcementLayer(BMCSModel):
    """
    Single layer of reinforcement in a cross-section.
    
    Represents a horizontal layer of reinforcement bars at a specific
    depth with a defined steel area and material model.
    
    Coordinate system:
        - z is distance from top of cross-section [mm]
        - Positive z is downward
    
    Attributes:
        z: Distance from top of cross-section [mm]
        A_s: Total steel area in this layer [mm²]
        material: Steel material model (SteelReinforcement)
        name: Optional layer identifier
    """
    
    z: float = ui_field(
        50.0,
        label=r"$z$",
        unit="mm",
        range=(0.0, 2000.0),
        step=5.0,
        description="Distance from top",
        ge=0.0
    )
    
    A_s: float = ui_field(
        1000.0,
        label=r"$A_s$",
        unit="mm²",
        range=(0.0, 20000.0),
        step=100.0,
        description="Steel area",
        ge=0.0
    )
    
    material: Optional[SteelReinforcement] = None
    name: Optional[str] = None
    
    def model_post_init(self, __context) -> None:
        """Initialize with default material if none provided."""
        if self.material is None:
            # Default to B500B characteristic strength
            self.material = create_steel('B500B')
    
    @property
    def f_sy(self) -> float:
        """Yield strength from material model [MPa]"""
        return self.material.f_sy
    
    @property
    def f_st(self) -> float:
        """Tensile strength from material model [MPa]"""
        return self.material.f_st
    
    @property
    def E_s(self) -> float:
        """Elastic modulus from material model [MPa]"""
        return self.material.E_s
    
    @property
    def eps_sy(self) -> float:
        """Yield strain from material model [-]"""
        return self.material.eps_sy
    
    def get_sig(self, eps: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get stress for given strain(s).
        
        Args:
            eps: Strain value(s) [-]
            
        Returns:
            Stress value(s) [MPa]
        """
        eps_array = np.atleast_1d(eps)
        sig_array = self.material.get_sig(eps_array)
        
        # Return scalar if input was scalar
        if np.isscalar(eps):
            return to_scalar(sig_array[0])
        return sig_array
    
    def get_force(self, eps: float) -> float:
        """
        Get force in this layer for given strain.
        
        F = A_s × σ(ε)
        
        Args:
            eps: Strain [-]
            
        Returns:
            Force [N]
        """
        sig = self.get_sig(eps)
        return to_scalar(self.A_s * sig)
    
    def get_moment_arm(self, y_ref: float = 0.0) -> float:
        """
        Get moment arm relative to reference point.
        
        Args:
            y_ref: Reference y-coordinate [mm]
            
        Returns:
            Moment arm [mm]
        """
        return self.z - y_ref
    
    def get_moment(self, eps: float, y_ref: float = 0.0) -> float:
        """
        Get moment contribution relative to reference point.
        
        M = F × (z - y_ref)
        
        Args:
            eps: Strain [-]
            y_ref: Reference y-coordinate [mm]
            
        Returns:
            Moment [Nmm]
        """
        force = self.get_force(eps)
        arm = self.get_moment_arm(y_ref)
        return force * arm


class ReinforcementLayout(BMCSModel):
    """
    Collection of reinforcement layers in a cross-section.
    
    Manages multiple reinforcement layers and provides methods
    for computing total forces and moments.
    
    Accepts any layer type: ReinforcementLayer, BarReinforcement, 
    LayerReinforcement, or AreaReinforcement.
    
    Attributes:
        layers: List of reinforcement layers
    """
    
    layers: List[Any] = []
    
    @field_validator('layers', mode='before')
    @classmethod
    def validate_layers(cls, v):
        """Accept any layer type with required interface (z, A_s, get_force, get_moment)"""
        if v is None:
            return []
        return v
    
    def model_post_init(self, __context) -> None:
        """Initialize empty layer list if None."""
        if self.layers is None:
            self.layers = []
    
    def add_layer(
        self,
        z: float,
        A_s: float,
        material: Optional[SteelReinforcement] = None,
        name: Optional[str] = None
    ) -> ReinforcementLayer:
        """
        Add a reinforcement layer.
        
        Args:
            z: Distance from top [mm]
            A_s: Steel area [mm²]
            material: Steel material model (defaults to B500B)
            name: Optional layer identifier
            
        Returns:
            The created ReinforcementLayer
        """
        layer = ReinforcementLayer(z=z, A_s=A_s, material=material, name=name)
        self.layers.append(layer)
        return layer
    
    def remove_layer(self, index: int) -> None:
        """Remove layer by index."""
        if 0 <= index < len(self.layers):
            self.layers.pop(index)
    
    def clear(self) -> None:
        """Remove all layers."""
        self.layers.clear()
    
    @property
    def n_layers(self) -> int:
        """Number of layers"""
        return len(self.layers)
    
    @property
    def total_area(self) -> float:
        """Total steel area across all layers [mm²]"""
        return sum(layer.A_s for layer in self.layers)
    
    @property
    def z_min(self) -> float:
        """Minimum z-coordinate (top layer) [mm]"""
        if not self.layers:
            return 0.0
        return min(layer.z for layer in self.layers)
    
    @property
    def z_max(self) -> float:
        """Maximum z-coordinate (bottom layer) [mm]"""
        if not self.layers:
            return 0.0
        return max(layer.z for layer in self.layers)
    
    @property
    def centroid_z(self) -> float:
        """
        Centroid of reinforcement (area-weighted average z).
        
        Returns:
            Centroid z-coordinate [mm]
        """
        if not self.layers or self.total_area == 0:
            return 0.0
        
        sum_Az = sum(layer.A_s * layer.z for layer in self.layers)
        return sum_Az / self.total_area
    
    def get_layers_at_depth(self, z: float, tolerance: float = 1e-6) -> List[ReinforcementLayer]:
        """
        Get all layers at a specific depth.
        
        Args:
            z: Depth to search [mm]
            tolerance: Matching tolerance [mm]
            
        Returns:
            List of layers at that depth
        """
        return [layer for layer in self.layers if abs(layer.z - z) < tolerance]
    
    def get_strain_distribution(
        self,
        kappa: float,
        eps_bottom: float = 0.0
    ) -> npt.NDArray[np.float64]:
        """
        Get strain at each layer for plane section assumption.
        
        Standard coordinate system: ε(z) = ε_bottom - κ × z
        
        Args:
            kappa: Curvature [1/mm]
            eps_bottom: Strain at bottom [−]
            
        Returns:
            Array of strains at each layer [-]
        """
        z_coords = np.array([layer.z for layer in self.layers])
        return eps_bottom - kappa * z_coords
    
    def get_N_M(
        self,
        kappa: float,
        eps_bottom: float = 0.0,
        y_ref: float = 0.0
    ) -> tuple[float, float]:
        """
        Compute total axial force and moment from all layers.
        
        Standard coordinate system: ε(z) = ε_bottom + κ × z
        
        Args:
            kappa: Curvature [1/mm]
            eps_bottom: Strain at bottom [-]
            y_ref: Reference point for moment [mm]
            
        Returns:
            (N, M): Axial force [N] and moment [Nmm]
        """
        N_total = 0.0
        M_total = 0.0
        
        strains = self.get_strain_distribution(kappa, eps_bottom)
        
        for layer, eps in zip(self.layers, strains):
            N_total += layer.get_force(eps)
            M_total += layer.get_moment(eps, y_ref)
        
        return N_total, M_total
    
    def get_summary(self) -> dict:
        """
        Get summary information about the layout.
        
        Returns:
            Dictionary with layout statistics
        """
        return {
            'n_layers': self.n_layers,
            'total_area': self.total_area,
            'z_min': self.z_min,
            'z_max': self.z_max,
            'centroid_z': self.centroid_z,
            'layers': [
                {
                    'name': layer.name or f"Layer {i+1}",
                    'z': layer.z,
                    'A_s': layer.A_s,
                    'f_sy': layer.f_sy,
                    'material': type(layer.material).__name__
                }
                for i, layer in enumerate(self.layers)
            ]
        }


def create_symmetric_reinforcement(
    h: float,
    cover: float,
    A_s_top: float,
    A_s_bottom: float,
    material_top: Optional[SteelReinforcement] = None,
    material_bottom: Optional[SteelReinforcement] = None
) -> ReinforcementLayout:
    """
    Create symmetric reinforcement layout (top and bottom).
    
    Standard convention: z measured from bottom of cross-section.
    
    Common pattern for doubly reinforced beams.
    
    Args:
        h: Cross-section height [mm]
        cover: Concrete cover [mm]
        A_s_top: Top reinforcement area [mm²]
        A_s_bottom: Bottom reinforcement area [mm²]
        material_top: Top steel material (defaults to B500B)
        material_bottom: Bottom steel material (defaults to B500B)
        
    Returns:
        ReinforcementLayout with two layers
    """
    layout = ReinforcementLayout()
    
    # Bottom layer (z = cover from bottom)
    layout.add_layer(
        z=cover,
        A_s=A_s_bottom,
        material=material_bottom,
        name="Bottom"
    )
    
    # Top layer (z = h - cover from bottom)
    layout.add_layer(
        z=h - cover,
        A_s=A_s_top,
        material=material_top,
        name="Top"
    )
    
    return layout


def create_distributed_reinforcement(
    h: float,
    cover: float,
    n_layers: int,
    A_s_total: float,
    material: Optional[SteelReinforcement] = None
) -> ReinforcementLayout:
    """
    Create uniformly distributed reinforcement.
    
    Useful for walls or deep beams with multiple reinforcement rows.
    
    Args:
        h: Cross-section height [mm]
        cover: Concrete cover [mm]
        n_layers: Number of reinforcement layers
        A_s_total: Total steel area to distribute [mm²]
        material: Steel material (defaults to B500B)
        
    Returns:
        ReinforcementLayout with n_layers evenly spaced
    """
    layout = ReinforcementLayout()
    
    # Effective height (between covers)
    h_eff = h - 2 * cover
    
    # Area per layer
    A_s_per_layer = A_s_total / n_layers
    
    # Create layers
    for i in range(n_layers):
        if n_layers == 1:
            z = cover + h_eff / 2
        else:
            z = cover + i * h_eff / (n_layers - 1)
        
        layout.add_layer(
            z=z,
            A_s=A_s_per_layer,
            material=material,
            name=f"Layer {i+1}"
        )
    
    return layout


# ============================================================================
# Catalog-Integrated Reinforcement Layers (Product Proxies)
# ============================================================================

class BarReinforcement(BMCSModel):
    """
    Bar reinforcement with catalog component link.
    
    Proxy to catalog component - accesses product properties without duplication.
    For discrete bars (steel rebars, carbon bars).
    
    Attributes:
        z: Distance from top [mm]
        component: Reference to catalog component (SteelRebarComponent, CarbonBarComponent)
        count: Number of bars
        name: Optional layer identifier
    
    Example:
        >>> from scite.cs_components import SteelRebarComponent
        >>> steel = SteelRebarComponent(nominal_diameter=20, grade='B500B')
        >>> layer = BarReinforcement(z=450, component=steel, count=4)
        >>> print(layer.A_s)  # 4 × component.area
    """
    
    z: float = ui_field(
        50.0,
        label=r"$z$",
        unit="mm",
        range=(0.0, 2000.0),
        step=5.0,
        description="Distance from top",
        ge=0.0
    )
    
    component: Optional[Any] = None  # Reference to catalog component
    
    count: int = ui_field(
        1,
        label=r"$n$",
        range=(1, 50),
        step=1,
        description="Number of bars",
        ge=1,
        le=100
    )
    
    name: Optional[str] = None
    
    @property
    def A_s(self) -> float:
        """Total steel area: component.area × count [mm²]"""
        if self.component is None:
            return 0.0
        return self.component.area * self.count
    
    @property
    def material(self):
        """Material model from component"""
        if self.component is None:
            return None
        return self.component.matmod
    
    @property
    def diameter(self) -> float:
        """Bar diameter from component [mm]"""
        if self.component is None:
            return 0.0
        return self.component.nominal_diameter
    
    def get_sig(self, eps: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """Get stress from component material model"""
        if self.material is None:
            return np.zeros_like(eps)
        return self.material.get_sig(eps)
    
    def get_force(self, eps: float) -> float:
        """Get force: F = A_s × σ(ε)"""
        sig = self.get_sig(eps)
        return to_scalar(self.A_s * sig)
    
    def get_moment(self, eps: float, y_ref: float = 0.0) -> float:
        """Get moment: M = F × (z - y_ref)"""
        force = self.get_force(eps)
        arm = self.z - y_ref
        return force * arm


class LayerReinforcement(BMCSModel):
    """
    Layer reinforcement with catalog component link.
    
    Proxy to catalog component for distributed reinforcement (textiles, mats).
    Calculates area based on component spacing/width parameters.
    
    Attributes:
        z: Distance from top [mm]
        component: Reference to catalog component (TextileReinforcementComponent)
        width: Active width [mm]
        name: Optional layer identifier
    
    Example:
        >>> from scite.cs_components import TextileReinforcementComponent
        >>> textile = TextileReinforcementComponent(spacing=14, A_roving=1.8)
        >>> layer = LayerReinforcement(z=25, component=textile, width=300)
        >>> print(layer.A_s)  # (width / spacing) × A_roving
    """
    
    z: float = ui_field(
        50.0,
        label=r"$z$",
        unit="mm",
        range=(0.0, 2000.0),
        step=5.0,
        description="Distance from top",
        ge=0.0
    )
    
    component: Optional[Any] = None  # Reference to catalog component
    
    width: float = ui_field(
        100.0,
        label=r"$b$",
        unit="mm",
        range=(10.0, 2000.0),
        step=10.0,
        description="Active width",
        ge=0.0
    )
    
    name: Optional[str] = None
    
    @property
    def A_s(self) -> float:
        """
        Total reinforcement area [mm²].
        
        For textiles: (width / spacing) × A_roving
        For mats: width × area_per_width
        """
        if self.component is None:
            return 0.0
        
        if hasattr(self.component, 'spacing') and hasattr(self.component, 'A_roving'):
            # Textile with rovings
            n_rovings = int(self.width / self.component.spacing)
            return n_rovings * self.component.A_roving
        elif hasattr(self.component, 'area_per_width'):
            # Mat with area per unit width
            return self.width * self.component.area_per_width
        else:
            return 0.0
    
    @property
    def material(self):
        """Material model from component"""
        if self.component is None:
            return None
        return self.component.matmod
    
    @property
    def n_rovings(self) -> int:
        """Number of rovings (for textiles)"""
        if self.component is None or not hasattr(self.component, 'spacing'):
            return 0
        return int(self.width / self.component.spacing)
    
    def get_sig(self, eps: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """Get stress from component material model"""
        if self.material is None:
            return np.zeros_like(eps)
        return self.material.get_sig(eps)
    
    def get_force(self, eps: float) -> float:
        """Get force: F = A_s × σ(ε)"""
        sig = self.get_sig(eps)
        return to_scalar(self.A_s * sig)
    
    def get_moment(self, eps: float, y_ref: float = 0.0) -> float:
        """Get moment: M = F × (z - y_ref)"""
        force = self.get_force(eps)
        arm = self.z - y_ref
        return force * arm


class AreaReinforcement(BMCSModel):
    """
    Product-independent reinforcement for design optimization.
    
    No catalog link - area and material model specified explicitly.
    Used when reinforcement is determined by design equations.
    
    Attributes:
        z: Distance from top [mm]
        A_s: Required steel area [mm²]
        material: Material model (SteelReinforcement, CarbonReinforcement)
        name: Optional layer identifier
    
    Example:
        >>> from scite.matmod import create_steel
        >>> layer = AreaReinforcement(z=450, A_s=1500, material=create_steel('B500B'))
    """
    
    z: float = ui_field(
        50.0,
        label=r"$z$",
        unit="mm",
        range=(0.0, 2000.0),
        step=5.0,
        description="Distance from top",
        ge=0.0
    )
    
    A_s: float = ui_field(
        1000.0,
        label=r"$A_s$",
        unit="mm²",
        range=(0.0, 20000.0),
        step=100.0,
        description="Steel area",
        ge=0.0
    )
    
    material: Optional[SteelReinforcement] = None
    name: Optional[str] = None
    
    def model_post_init(self, __context) -> None:
        """Initialize with default material if none provided."""
        if self.material is None:
            self.material = create_steel('B500B')
    
    def get_sig(self, eps: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """Get stress from material model"""
        eps_array = np.atleast_1d(eps)
        sig_array = self.material.get_sig(eps_array)
        
        if np.isscalar(eps):
            return to_scalar(sig_array[0])
        return sig_array
    
    def get_force(self, eps: float) -> float:
        """Get force: F = A_s × σ(ε)"""
        sig = self.get_sig(eps)
        return to_scalar(self.A_s * sig)
    
    def get_moment(self, eps: float, y_ref: float = 0.0) -> float:
        """Get moment: M = F × (z - y_ref)"""
        force = self.get_force(eps)
        arm = self.z - y_ref
        return force * arm
