"""
Steel Rebar Components

Standard steel reinforcing bars according to EC2.
Includes catalog of all standard diameters and grades.
"""

import numpy as np
import numpy.typing as npt
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Any

from bmcs_cross_section.cs_components.component_base import ReinforcementComponent
from bmcs_cross_section.matmod.steel_reinforcement import create_steel


@dataclass
class SteelRebarComponent(ReinforcementComponent):
    """
    Steel reinforcing bar component.
    
    Standard diameters (EC2): 6, 8, 10, 12, 14, 16, 20, 25, 28, 32, 40 mm
    Grades: B500A, B500B, B500C (f_yk = 500 MPa)
    """
    
    grade: str = 'B500B'  # Steel grade
    
    def __post_init__(self):
        super().__post_init__()
        
        # Auto-generate identification fields if not provided
        if not self.product_id:
            self.product_id = f'REBAR-{self.grade}-D{int(self.nominal_diameter)}'
        if not self.name:
            self.name = f'Steel Rebar {self.grade} D{int(self.nominal_diameter)}'
        if not self.manufacturer:
            self.manufacturer = 'EC2 Standard'
        
        self.shape_type = 'bar'
        self.material_type = 'steel'
        
        # Create matmod if not provided
        if self.matmod is None:
            self.matmod = create_steel(self.grade)
            self.f_tk = self.matmod.f_sy  # Yield strength as characteristic
            self.E = self.matmod.E_s
            self.eps_uk = self.matmod.eps_ud  # Ultimate strain
    
    def get_design_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get design stress-strain curve.
        
        For steel: f_yd = f_yk / gamma_s
        """
        # Get characteristic curve from matmod
        sig_char = self.matmod.get_sig(eps)
        
        # Apply safety factor
        sig_design = sig_char / self.gamma_s
        
        return sig_design
    
    def get_characteristic_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Get characteristic stress-strain curve.
        
        For steel: uses matmod directly (f_yk, eps_uk with hardening).
        """
        # Matmod represents characteristic behavior
        return self.matmod.get_sig(eps)
    
    def to_dict(self):
        """Convert to dictionary for catalog, including steel grade."""
        base_dict = super().to_dict()
        base_dict['grade'] = self.grade
        return base_dict


def create_steel_rebar_catalog(use_cache: bool = True) -> pd.DataFrame:
    """
    Create catalog of standard steel rebars.
    
    Args:
        use_cache: If True, use cached catalog (default). 
                   If False, create fresh catalog.
    
    Returns:
        DataFrame with all standard products
        
    Note:
        By default, this function uses cached catalogs stored in JSON format.
        The catalog is created once and loaded from cache on subsequent calls.
        Use use_cache=False to force recreation (useful for development).
    """
    if use_cache:
        from bmcs_cross_section.cs_components.catalog_manager import get_catalog_manager
        return get_catalog_manager().get_steel_catalog()
    
    # Original creation logic (used when cache is bypassed or first time)
    catalog = []
    
    # Standard diameters (EC2)
    diameters = [6, 8, 10, 12, 14, 16, 20, 25, 28, 32, 40]
    
    # Grades
    grades = ['B500A', 'B500B', 'B500C']
    
    for grade in grades:
        for d in diameters:
            product_id = f"REBAR-{grade}-D{d}"
            component = SteelRebarComponent(
                product_id=product_id,
                name=f"Steel Rebar Ø{d} {grade}",
                manufacturer="Standard EC2",
                grade=grade,
                nominal_diameter=d,
                area=np.pi * (d/2)**2,
            )
            catalog.append(component.to_dict())
    
    return pd.DataFrame(catalog)
