"""
BMCS Cross Section - Core Module

Modern foundation for computational structural mechanics models.
Provides base classes, symbolic math integration, and UI abstraction.
"""

from scite.core.model import BMCSModel
from scite.core.symbolic import SymbolicExpression, SymbolicModel
from scite.core.ui.base import (
    ui_field, 
    UIMetadata, 
    UIAdapter,
    get_ui_metadata,
    get_all_ui_fields,
)
from scite.core.types import (
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
