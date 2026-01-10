"""
Carbon Bar Components

Carbon fiber reinforced polymer bars (e.g., COMBAR).
"""

import numpy as np
import numpy.typing as npt
import pandas as pd
from dataclasses import dataclass

from bmcs_cross_section.cs_components.component_base import ReinforcementComponent


@dataclass
class CarbonBarComponent(ReinforcementComponent):
    """
    Carbon fiber reinforced polymer bar (e.g., COMBAR).
    
    Properties:
    - Linear elastic to failure
    - High tensile strength (1500-2500 MPa)
    - High stiffness (E ≈ 150-170 GPa)
    - No yielding (brittle failure)
    """
    
    product_line: str = 'COMBAR'  # Product line
    
    def __post_init__(self):
        super().__post_init__()
        
        # Auto-generate identification fields if not provided
        if not self.product_id:
            self.product_id = f'COMBAR-D{int(self.nominal_diameter)}'
        if not self.name:
            self.name = f'Carbon Bar COMBAR D{int(self.nominal_diameter)}'
        if not self.manufacturer:
            self.manufacturer = 'COMBAR'
        
        self.shape_type = 'bar'
        self.material_type = 'carbon'
        
        # Set default properties if not provided
        if self.f_tk == 0.0:
            self.f_tk = 2000.0  # MPa - Tensile strength
        if self.E == 0.0:
            self.E = 165000.0  # MPa - Young's modulus
        if self.eps_uk == 0.0:
            self.eps_uk = self.f_tk / self.E  # Ultimate strain
        
        # Carbon FRP typically has higher safety factor
        if self.gamma_s == 1.15:  # If default
            self.gamma_s = 1.25  # EC2-like value for FRP
    
    def get_design_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Linear elastic to failure for carbon bars.
        """
        # Design values
        f_td = self.f_td
        eps_ud = self.eps_ud
        
        # Linear elastic
        sig = np.minimum(self.E * np.abs(eps), f_td)
        sig = np.sign(eps) * sig  # Keep sign
        
        # Limit to ultimate strain
        sig = np.where(np.abs(eps) > eps_ud, 0, sig)
        
        return sig


def create_carbon_bar_catalog() -> pd.DataFrame:
    """
    Create catalog of COMBAR products.
    
    Typical COMBAR diameters: 6, 8, 10, 12, 14, 16, 20, 25, 28, 32 mm
    """
    catalog = []
    
    # COMBAR typical properties
    diameters = [6, 8, 10, 12, 14, 16, 20, 25, 28, 32]
    f_tk_carbon = 2000  # MPa (typical)
    E_carbon = 165000   # MPa
    eps_uk_carbon = f_tk_carbon / E_carbon
    
    for d in diameters:
        product_id = f"COMBAR-D{d}"
        component = CarbonBarComponent(
            product_id=product_id,
            name=f"COMBAR Ø{d} Carbon",
            manufacturer="Schöck",
            product_line='COMBAR',
            nominal_diameter=d,
            area=np.pi * (d/2)**2,
            f_tk=f_tk_carbon,
            E=E_carbon,
            eps_uk=eps_uk_carbon,
            gamma_s=1.25,
        )
        catalog.append(component.to_dict())
    
    return pd.DataFrame(catalog)
