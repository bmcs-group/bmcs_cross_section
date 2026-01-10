"""
Textile Reinforcement Components

Grid/fabric reinforcement for textile-reinforced concrete (TRC).
Includes Solidian products and similar textile grids.
"""

import numpy as np
import numpy.typing as npt
import pandas as pd
from dataclasses import dataclass

from bmcs_cross_section.cs_components.component_base import ReinforcementComponent


@dataclass
class TextileReinforcementComponent(ReinforcementComponent):
    """
    Textile reinforcement (grid, fabric).
    
    Properties:
    - Area given per unit width [mm²/m]
    - Can be carbon, glass, basalt, aramid
    - Grid spacing defines effective area
    """
    
    # Textile-specific properties
    area_per_width: float = 0.0  # [mm²/m] cross-sectional area per meter width
    grid_spacing: float = 0.0    # [mm] spacing between rovings
    roving_tex: float = 0.0      # [tex = g/km] roving fineness
    
    def __post_init__(self):
        super().__post_init__()
        
        # Auto-generate identification fields if not provided
        if not self.product_id and self.material_type and self.roving_tex:
            mat_short = 'C' if self.material_type == 'carbon' else 'G'
            self.product_id = f'SOLIDIAN-{mat_short}{int(self.roving_tex)}'
        if not self.name and self.material_type and self.roving_tex:
            mat_name = self.material_type.capitalize()
            self.name = f'Solidian {mat_name} {int(self.roving_tex)}tex'
        if not self.manufacturer:
            self.manufacturer = 'Solidian'
        
        self.shape_type = 'textile'
        # Area is specified directly for textiles, not calculated from diameter
    
    def get_design_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Linear elastic to failure (typical for textile).
        """
        f_td = self.f_td
        eps_ud = self.eps_ud
        
        # Linear elastic
        sig = np.minimum(self.E * np.abs(eps), f_td)
        sig = np.sign(eps) * sig
        
        # Limit to ultimate strain
        sig = np.where(np.abs(eps) > eps_ud, 0, sig)
        
        return sig
    
    def to_dict(self):
        """Convert to dictionary for catalog, including textile-specific fields."""
        base_dict = super().to_dict()
        base_dict.update({
            'area_per_width': self.area_per_width,
            'grid_spacing': self.grid_spacing,
            'roving_tex': self.roving_tex,
        })
        return base_dict


def create_textile_catalog() -> pd.DataFrame:
    """
    Create catalog of Solidian textile products.
    
    Common products:
    - Carbon grids (high strength, high stiffness)
    - Glass grids (lower cost)
    - Basalt grids (corrosion resistant)
    """
    catalog = []
    
    # Carbon textile properties
    carbon_products = [
        {'roving': '800tex', 'spacing': 10, 'area_per_m': 107, 'f_tk': 3200, 'E': 240000},
        {'roving': '1600tex', 'spacing': 15, 'area_per_m': 214, 'f_tk': 3200, 'E': 240000},
        {'roving': '3200tex', 'spacing': 20, 'area_per_m': 428, 'f_tk': 3200, 'E': 240000},
    ]
    
    for prod in carbon_products:
        product_id = f"SOLIDIAN-C-{prod['roving']}-{prod['spacing']}"
        eps_uk = prod['f_tk'] / prod['E']
        component = TextileReinforcementComponent(
            product_id=product_id,
            name=f"Solidian GRID Q{prod['spacing']}-C-{prod['roving']}",
            manufacturer="Solidian",
            material_type='carbon',
            area_per_width=prod['area_per_m'],
            area=prod['area_per_m'],  # For compatibility
            grid_spacing=prod['spacing'],
            roving_tex=float(prod['roving'].replace('tex', '')),
            f_tk=prod['f_tk'],
            E=prod['E'],
            eps_uk=eps_uk,
            gamma_s=1.25,
        )
        catalog.append(component.to_dict())
    
    # Glass textile properties
    glass_products = [
        {'roving': '1200tex', 'spacing': 10, 'area_per_m': 168, 'f_tk': 1700, 'E': 72000},
        {'roving': '2400tex', 'spacing': 15, 'area_per_m': 336, 'f_tk': 1700, 'E': 72000},
    ]
    
    for prod in glass_products:
        product_id = f"SOLIDIAN-G-{prod['roving']}-{prod['spacing']}"
        eps_uk = prod['f_tk'] / prod['E']
        component = TextileReinforcementComponent(
            product_id=product_id,
            name=f"Solidian GRID Q{prod['spacing']}-G-{prod['roving']}",
            manufacturer="Solidian",
            material_type='glass',
            area_per_width=prod['area_per_m'],
            area=prod['area_per_m'],
            grid_spacing=prod['spacing'],
            roving_tex=float(prod['roving'].replace('tex', '')),
            f_tk=prod['f_tk'],
            E=prod['E'],
            eps_uk=eps_uk,
            gamma_s=1.30,  # Slightly higher for glass
        )
        catalog.append(component.to_dict())
    
    return pd.DataFrame(catalog)
