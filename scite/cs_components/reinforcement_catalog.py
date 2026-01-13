"""
Reinforcement Catalog Infrastructure

Provides unified catalog access and query functions for all
reinforcement and concrete products.
"""

import pandas as pd
from typing import Optional, List, Union

from bmcs_cross_section.cs_components.component_base import (
    ReinforcementComponent,
    ConcreteComponent
)
from bmcs_cross_section.cs_components.steel_rebars import (
    SteelRebarComponent,
    create_steel_rebar_catalog
)
from bmcs_cross_section.cs_components.carbon_bars import (
    CarbonBarComponent,
    create_carbon_bar_catalog
)
from bmcs_cross_section.cs_components.textile_products import (
    TextileReinforcementComponent,
    create_textile_catalog
)
from bmcs_cross_section.cs_components.concrete_catalog import (
    create_concrete_catalog,
    get_concrete_by_class,
    get_concrete_by_fck
)


def get_full_reinforcement_catalog() -> pd.DataFrame:
    """
    Get complete reinforcement catalog (all types).
    
    Returns:
        DataFrame with all reinforcement products
    """
    steel_cat = create_steel_rebar_catalog()
    carbon_cat = create_carbon_bar_catalog()
    textile_cat = create_textile_catalog()
    
    return pd.concat([steel_cat, carbon_cat, textile_cat], ignore_index=True)


def search_by_diameter(diameter: float, tolerance: float = 0.1) -> pd.DataFrame:
    """
    Search reinforcement by nominal diameter.
    
    Args:
        diameter: Nominal diameter [mm]
        tolerance: Search tolerance [mm]
        
    Returns:
        DataFrame with matching products
    """
    catalog = get_full_reinforcement_catalog()
    return catalog[
        (catalog['nominal_diameter'] >= diameter - tolerance) &
        (catalog['nominal_diameter'] <= diameter + tolerance)
    ]


def search_by_material(material_type: str) -> pd.DataFrame:
    """
    Search reinforcement by material type.
    
    Args:
        material_type: Material type ('steel', 'carbon', 'glass', etc.)
        
    Returns:
        DataFrame with matching products
    """
    catalog = get_full_reinforcement_catalog()
    return catalog[catalog['material_type'] == material_type]


def search_by_shape(shape_type: str) -> pd.DataFrame:
    """
    Search reinforcement by shape type.
    
    Args:
        shape_type: Shape type ('bar', 'textile', 'grid', etc.)
        
    Returns:
        DataFrame with matching products
    """
    catalog = get_full_reinforcement_catalog()
    return catalog[catalog['shape_type'] == shape_type]


def search_by_strength(f_tk_min: float) -> pd.DataFrame:
    """
    Search reinforcement by minimum tensile strength.
    
    Args:
        f_tk_min: Minimum characteristic strength [MPa]
        
    Returns:
        DataFrame with matching products
    """
    catalog = get_full_reinforcement_catalog()
    return catalog[catalog['f_tk'] >= f_tk_min]


def find_product(product_id: str) -> Optional[pd.Series]:
    """
    Find specific product by ID.
    
    Args:
        product_id: Product identifier
        
    Returns:
        Product data as Series or None if not found
    """
    catalog = get_full_reinforcement_catalog()
    result = catalog[catalog['product_id'] == product_id]
    
    if result.empty:
        return None
    
    return result.iloc[0]


# Convenience functions for common queries
def get_steel_rebars(grade: Optional[str] = None) -> pd.DataFrame:
    """Get steel rebar catalog, optionally filtered by grade."""
    catalog = create_steel_rebar_catalog()
    if grade:
        return catalog[catalog['name'].str.contains(grade)]
    return catalog


def get_carbon_bars() -> pd.DataFrame:
    """Get carbon bar catalog."""
    return create_carbon_bar_catalog()


def get_textile_products(material: Optional[str] = None) -> pd.DataFrame:
    """Get textile catalog, optionally filtered by material."""
    catalog = create_textile_catalog()
    if material:
        return catalog[catalog['material_type'] == material]
    return catalog
