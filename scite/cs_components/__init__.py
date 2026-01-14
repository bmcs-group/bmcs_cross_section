"""
Component Catalog System for BMCS Cross Section

This package provides standardized product catalogs for reinforcement
and concrete materials, separating physical products from mathematical
material models (matmod).

Architecture:
-------------
- **Products (cs_components)**: Standardized catalog of certified
  components with manufacturer info, geometric properties, and
  characteristic material properties.
  
- **Models (matmod)**: Mathematical stress-strain relationships
  for material behavior simulation.
  
- **Caching (catalog_manager)**: Persistent JSON-based catalog storage
  with lazy loading for performance optimization.

Key Features:
-------------
- Traceability: Product ID, manufacturer, certification
- Standardization: Validated properties from standards (EC2, etc.)
- Safety: Built-in characteristic → design value conversion
- Query interface: Pandas-based catalog filtering
- Integration: Automatic matmod creation for each product
- Caching: JSON-based persistent storage with lazy loading

Component Types:
---------------
- ReinforcementComponent: Abstract base for all reinforcement
- SteelRebarComponent: Standard steel rebars (EC2 grades)
- CarbonBarComponent: Carbon FRP bars (COMBAR)
- TextileReinforcementComponent: Textile grids (Solidian)
- ConcreteComponent: Concrete grades (EC2 strength classes)

Usage Example (Cached Catalogs):
--------------------------------
    >>> from scite.cs_components import (
    ...     create_steel_rebar_catalog,
    ...     get_concrete_by_class,
    ...     get_catalog_manager
    ... )
    >>> 
    >>> # Get cached steel catalog (loaded from JSON if available)
    >>> steel_catalog = create_steel_rebar_catalog()
    >>> 
    >>> # Or use catalog manager directly for more control
    >>> manager = get_catalog_manager()
    >>> steel_catalog = manager.get_steel_catalog()  # Cached
    >>> 
    >>> # Get concrete component (also cached)
    >>> concrete = get_concrete_by_class("C30/37")
    >>> 
    >>> # Force refresh if needed
    >>> steel_catalog = manager.get_steel_catalog(force_refresh=True)
    >>> 
    >>> # Clear all caches
    >>> manager.clear_all_caches()

Design vs Characteristic Values:
-------------------------------
Components store characteristic values (f_tk, f_ck) and provide
design values through safety factors:

- Reinforcement: f_td = f_tk / γ_s (γ_s ≈ 1.15)
- Concrete: f_cd = α_cc × f_ck / γ_c (γ_c = 1.5, α_cc = 1.0)

This ensures consistent safety factor application across all designs.
"""

# Base classes
from .component_base import ReinforcementComponent, ConcreteComponent

# Catalog manager (caching system)
from .catalog_manager import CatalogManager, get_catalog_manager

# Reinforcement components
from .steel_rebars import SteelRebarComponent, create_steel_rebar_catalog
from .carbon_bars import CarbonBarComponent, create_carbon_bar_catalog
from .textile_products import (
    TextileReinforcementComponent,
    create_textile_catalog
)

# Concrete catalog
from .concrete_catalog import (
    create_concrete_catalog,
    get_concrete_by_class,
    get_concrete_by_fck
)

# Unified catalog queries
from .reinforcement_catalog import (
    get_full_reinforcement_catalog,
    search_by_diameter,
    search_by_material,
    search_by_shape,
    search_by_strength,
    find_product,
    get_steel_rebars,
    get_carbon_bars,
    get_textile_products
)

__all__ = [
    # Base classes
    'ReinforcementComponent',
    'ConcreteComponent',
    
    # Catalog manager (caching)
    'CatalogManager',
    'get_catalog_manager',
    
    # Reinforcement components
    'SteelRebarComponent',
    'CarbonBarComponent',
    'TextileReinforcementComponent',
    
    # Steel catalog
    'create_steel_rebar_catalog',
    
    # Carbon catalog
    'create_carbon_bar_catalog',
    
    # Textile catalog
    'create_textile_catalog',
    
    # Concrete catalog
    'create_concrete_catalog',
    'get_concrete_by_class',
    'get_concrete_by_fck',
    
    # Unified queries
    'get_full_reinforcement_catalog',
    'search_by_diameter',
    'search_by_material',
    'search_by_shape',
    'search_by_strength',
    'find_product',
    'get_steel_rebars',
    'get_carbon_bars',
    'get_textile_products',
]

__version__ = '1.0.0'
