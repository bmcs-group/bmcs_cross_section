"""
Carbon Bar Components

Carbon fiber reinforced polymer bars (e.g., COMBAR).
"""

import numpy as np
import numpy.typing as npt
import pandas as pd
from dataclasses import dataclass

from scite.cs_components.component_base import ReinforcementComponent
from scite.matmod import create_carbon


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
        
        # Create material model if not provided
        if self.matmod is None:
            # Use characteristic values with factor=1.0
            self.matmod = create_carbon(
                grade='C2000',  # Standard COMBAR grade
                factor=1.0,     # Characteristic values
                post_peak_factor=2.5  # For numerical stability
            )
            # Override with actual component properties
            self.matmod.E = self.E
            self.matmod.f_t = self.f_tk
    
    def get_design_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Linear elastic to failure for carbon bars (design values).
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
    
    def get_characteristic_stress_strain(self, eps: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Linear elastic to failure for carbon bars (characteristic values).
        """
        # Characteristic values
        f_tk = self.f_tk
        eps_uk = self.eps_uk
        
        # Linear elastic
        sig = np.minimum(self.E * np.abs(eps), f_tk)
        sig = np.sign(eps) * sig  # Keep sign
        
        # Limit to ultimate strain
        sig = np.where(np.abs(eps) > eps_uk, 0, sig)
        
        return sig


def create_carbon_bar_catalog(use_cache: bool = True) -> pd.DataFrame:
    """
    Create catalog of COMBAR products.
    
    Args:
        use_cache: If True, use cached catalog (default). 
                   If False, create fresh catalog.
    
    Typical COMBAR diameters: 6, 8, 10, 12, 14, 16, 20, 25, 28, 32 mm
    
    Note:
        By default, this function uses cached catalogs stored in JSON format.
        The catalog is created once and loaded from cache on subsequent calls.
        Use use_cache=False to force recreation (useful for development).
    """
    if use_cache:
        from scite.cs_components.catalog_manager import get_catalog_manager
        return get_catalog_manager().get_carbon_catalog()
    
    # Original creation logic (used when cache is bypassed or first time)
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
