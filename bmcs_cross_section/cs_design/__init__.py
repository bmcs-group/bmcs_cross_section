"""
Cross-section design module.

Modern implementation:
- shapes: Geometric shape classes (RectangularShape, TShape, IShape)
- reinforcement: Reinforcement layer classes (ReinforcementLayer, ReinforcementLayout)

Legacy modules (being refactored):
- cs_design, cs_layout_dict, cs_shape, cs_reinf_layer
"""

# Modern API
from .shapes import RectangularShape, TShape, IShape
from .reinforcement import (
    ReinforcementLayer,
    ReinforcementLayout,
    create_symmetric_reinforcement,
    create_distributed_reinforcement
)
from .cross_section import CrossSection

# Legacy API (commented out to avoid dependencies during refactoring)
# from .cs_design import CrossSectionDesign
# from .cs_layout_dict import CrossSectionLayout
# from .cs_shape import CustomShape, TShape as TShapeLegacy, Rectangle, Circle, ICrossSectionShape, IShape as IShapeLegacy
# from .cs_reinf_layer import FabricLayer, BarLayer, ReinfLayer

__all__ = [
    # Modern API - Shapes
    'RectangularShape',
    'TShape',
    'IShape',
    # Modern API - Reinforcement
    'ReinforcementLayer',
    'ReinforcementLayout',
    'create_symmetric_reinforcement',
    'create_distributed_reinforcement',
    # Modern API - Cross-section assembly
    'CrossSection',
]