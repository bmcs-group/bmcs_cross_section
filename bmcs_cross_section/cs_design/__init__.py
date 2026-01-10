"""
Cross-section design module - Modern Pydantic-based implementation.

This module provides a clean, type-safe API for cross-section design with:
- Geometric shapes (RectangularShape, TShape, IShape)
- Catalog-integrated reinforcement layers (proxy pattern)
- Complete cross-section assembly

Reinforcement Layer Types:
- BarReinforcement: Proxy to bar catalog components (steel, carbon)
- LayerReinforcement: Proxy to textile/mat catalog components
- AreaReinforcement: Product-independent (explicit area + material)
- ReinforcementLayout: Container accepting all layer types

Legacy traits-based modules have been moved to legacy/ folder.
"""

# Geometric shapes
from .shapes import RectangularShape, TShape, IShape

# Reinforcement layers (catalog-integrated proxies)
from .reinforcement import (
    # Catalog-integrated layer types
    BarReinforcement,
    LayerReinforcement,
    AreaReinforcement,
    # Container and utilities
    ReinforcementLayout,
    create_symmetric_reinforcement,
    create_distributed_reinforcement,
    # Legacy compatibility (deprecated - use AreaReinforcement)
    ReinforcementLayer,
)

# Cross-section assembly
from .cross_section import CrossSection

__all__ = [
    # Shapes
    'RectangularShape',
    'TShape',
    'IShape',
    # Reinforcement - Catalog-integrated proxies
    'BarReinforcement',
    'LayerReinforcement',
    'AreaReinforcement',
    # Reinforcement - Container and utilities
    'ReinforcementLayout',
    'create_symmetric_reinforcement',
    'create_distributed_reinforcement',
    # Cross-section assembly
    'CrossSection',
    # Deprecated (use AreaReinforcement instead)
    'ReinforcementLayer',
]