"""
Material models module - Modern Pydantic-based implementation.

This module provides material constitutive models for:
- Concrete (EC2-based models)
- Steel reinforcement (bilinear elastic-plastic)
- Carbon FRP reinforcement (linear elastic-brittle)

Modern API (Pydantic-based):
- EC2Concrete: Modern concrete model (ec2_concrete.py)
- SteelReinforcement: Modern steel model (steel_reinforcement.py)
- CarbonReinforcement: Modern carbon FRP model (carbon_reinforcement.py)
- create_steel: Helper function for steel material creation
- create_carbon: Helper function for carbon material creation

Note: MatMod base class is still used internally by concrete/ subfolder.
Legacy reinforcement models have been moved to legacy/ folder.
"""

# Base class (used by concrete subfolder)
from .matmod import MatMod

# Modern Pydantic-based API
from .ec2_concrete import EC2Concrete
from .steel_reinforcement import SteelReinforcement, create_steel
from .carbon_reinforcement import CarbonReinforcement, create_carbon

# Concrete models from subfolder (traits-based but with modern exports)
from .concrete import (
    ConcreteMatMod,
    pwl_concrete_matmod,
    ec2_concrete_matmod,
    ec2_with_plateau_matmod
)

__all__ = [
    # Base class (internal use)
    'MatMod',
    # Modern Pydantic API
    'EC2Concrete',
    'SteelReinforcement',
    'CarbonReinforcement',
    'create_steel',
    'create_carbon',
    # Concrete models (subfolder)
    'ConcreteMatMod',
    'pwl_concrete_matmod',
    'ec2_concrete_matmod',
    'ec2_with_plateau_matmod',
]