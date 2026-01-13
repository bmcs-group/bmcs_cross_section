"""
DEPRECATED: Legacy traits-based cross-section design modules.

These modules have been superseded by modern Pydantic-based implementations.

Migration Guide:
- cs_design.CrossSectionDesign → cross_section.CrossSection
- cs_shape.Rectangle → shapes.RectangularShape  
- cs_shape.TShape → shapes.TShape
- cs_shape.IShape → shapes.IShape
- cs_reinf_layer.ReinfLayer → reinforcement.AreaReinforcement
- cs_layout.CrossSectionLayout → reinforcement.ReinforcementLayout

For new code, use the modern API from the parent module.
"""

import warnings

warnings.warn(
    "The cs_design.legacy module contains deprecated traits-based classes. "
    "Use the modern Pydantic-based API from bmcs_cross_section.cs_design instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy imports (if needed for backward compatibility)
# Uncomment only if absolutely necessary
# from .cs_design import CrossSectionDesign
# from .cs_layout import CrossSectionLayout
# from .cs_layout_dict import CrossSectionLayout as CrossSectionLayoutDict
# from .cs_reinf_layer import ReinfLayer, BarLayer, FabricLayer
# from .cs_shape import Rectangle, Circle, TShape, IShape, CustomShape
