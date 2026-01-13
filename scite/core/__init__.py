"""
BMCS Cross Section - Core Module

Modern foundation for computational structural mechanics models.
Provides base classes, symbolic math integration, and UI abstraction.
"""

from bmcs_cross_section.core.model import BMCSModel
from bmcs_cross_section.core.symbolic import SymbolicExpression, SymbolicModel
from bmcs_cross_section.core.ui.base import (
    ui_field, 
    UIMetadata, 
    UIAdapter,
    get_ui_metadata,
    get_all_ui_fields,
)
from bmcs_cross_section.core.types import (
    ArrayLike,
    FloatArray,
    StressStrainCurve,
)

__all__ = [
    'BMCSModel',
    'SymbolicExpression',
    'SymbolicModel',
    'ui_field',
    'UIMetadata',
    'UIAdapter',
    'get_ui_metadata',
    'get_all_ui_fields',
    'ArrayLike',
    'FloatArray',
    'StressStrainCurve',
]
