"""
Concrete Component Catalog

Standard concrete grades according to Eurocode 2.
Provides catalog of common ready-mix concrete strength classes.
"""

import pandas as pd
from dataclasses import dataclass
from typing import Optional, Any

from bmcs_cross_section.cs_components.component_base import ConcreteComponent
from bmcs_cross_section.matmod.ec2_concrete import EC2Concrete


def create_concrete_catalog() -> pd.DataFrame:
    """
    Create catalog of standard concrete grades according to EC2.
    
    Strength classes from C12/15 to C90/105.
    Format: C(f_ck)/(f_ck,cube)
    
    Returns:
        DataFrame with all standard concrete grades
    """
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
        matmod = EC2Concrete(f_cm=f_cm)
        
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
    """
    catalog = create_concrete_catalog()
    result = catalog[catalog['strength_class'] == strength_class]
    
    if result.empty:
        return None
    
    row = result.iloc[0]
    matmod = EC2Concrete(f_cm=row['f_cm'])
    
    return ConcreteComponent(
        product_id=row['product_id'],
        name=row['name'],
        strength_class=row['strength_class'],
        f_ck=row['f_ck'],
        f_cm=row['f_cm'],
        E_cm=row['E_cm'],
        gamma_c=row['gamma_c'],
        alpha_cc=row['alpha_cc'],
        matmod=matmod,
    )


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
