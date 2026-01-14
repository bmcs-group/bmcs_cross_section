"""
Concrete Component Catalog

Standard concrete grades according to Eurocode 2.
Provides catalog of common ready-mix concrete strength classes.
"""

import pandas as pd
from dataclasses import dataclass
from typing import Optional, Any

from scite.cs_components.component_base import ConcreteComponent
from scite.matmod.ec2_concrete import EC2Concrete


def create_concrete_catalog(use_cache: bool = True) -> pd.DataFrame:
    """
    Create catalog of standard concrete grades according to EC2.
    
    Args:
        use_cache: If True, use cached catalog (default). 
                   If False, create fresh catalog.
    
    Strength classes from C12/15 to C90/105.
    Format: C(f_ck)/(f_ck,cube)
    
    Returns:
        DataFrame with all standard concrete grades
        
    Note:
        By default, this function uses cached catalogs stored in JSON format.
        The catalog is created once and loaded from cache on subsequent calls.
        Use use_cache=False to force recreation (useful for development).
    """
    if use_cache:
        from scite.cs_components.catalog_manager import get_catalog_manager
        return get_catalog_manager().get_concrete_catalog()
    
    # Original creation logic (used when cache is bypassed or first time)
    catalog = []
    
    # EC2 Table 3.1: Concrete strength classes
    # [strength_class, f_ck, f_ck_cube, f_cm, E_cm]
    concrete_grades = [
        # Lower strength classes
        ('C12/15', 12, 15, 20, 27000),
        ('C16/20', 16, 20, 24, 29000),
        ('C20/25', 20, 25, 28, 30000),
        ('C25/30', 25, 30, 33, 31000),
        ('C30/37', 30, 37, 38, 33000),
        ('C35/45', 35, 45, 43, 34000),
        ('C40/50', 40, 50, 48, 35000),
        ('C45/55', 45, 55, 53, 36000),
        ('C50/60', 50, 60, 58, 37000),
        
        # High strength classes
        ('C55/67', 55, 67, 63, 38000),
        ('C60/75', 60, 75, 68, 39000),
        ('C70/85', 70, 85, 78, 41000),
        ('C80/95', 80, 95, 88, 42000),
        ('C90/105', 90, 105, 98, 44000),
    ]
    
    for strength_class, f_ck, f_ck_cube, f_cm, E_cm in concrete_grades:
        product_id = f"CONCRETE-EC2-{strength_class}"
        
        # Create component with material model
        matmod = EC2Concrete(f_ck=f_ck)
        
        component = ConcreteComponent(
            product_id=product_id,
            name=f"Concrete {strength_class}",
            strength_class=strength_class,
            f_ck=f_ck,
            f_cm=f_cm,
            E_cm=E_cm,
            matmod=matmod,
        )
        
        catalog.append(component.to_dict())
    
    return pd.DataFrame(catalog)


def get_concrete_by_class(strength_class: str) -> Optional[ConcreteComponent]:
    """
    Get concrete component by strength class.
    
    Args:
        strength_class: EC2 strength class (e.g., "C30/37")
        
    Returns:
        ConcreteComponent or None if not found
        
    Note:
        Uses cached catalog for performance. First call creates and caches
        the catalog, subsequent calls load from JSON cache.
    """
    # Use catalog manager for cached access
    from scite.cs_components.catalog_manager import get_catalog_manager
    return get_catalog_manager().get_concrete_by_class(strength_class)


def get_concrete_by_fck(f_ck_min: float) -> pd.DataFrame:
    """
    Get concrete grades with f_ck >= specified value.
    
    Args:
        f_ck_min: Minimum characteristic strength [MPa]
        
    Returns:
        DataFrame with matching concrete grades
    """
    catalog = create_concrete_catalog()
    return catalog[catalog['f_ck'] >= f_ck_min]
