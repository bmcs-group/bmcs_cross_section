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

Note: Legacy traits-based concrete models and MatMod base class have been 
moved to legacy/ folder and are no longer part of the public API.
"""

from .carbon_reinforcement import CarbonReinforcement, create_carbon
# Modern Pydantic-based API
from .ec2_concrete import EC2Concrete
from .ec2_parabola_rectangle import EC2ParabolaRectangle
from .steel_reinforcement import SteelReinforcement, create_steel

__all__ = [
    # Modern Pydantic API
    'EC2Concrete',
    'EC2ParabolaRectangle',
    'SteelReinforcement',
    'CarbonReinforcement',
    'create_steel',
    'create_carbon',
]