"""
DEPRECATED: Legacy traits-based material models.

These modules have been superseded by modern Pydantic-based implementations.

Migration Guide:
- matmod.MatMod → Use EC2Concrete or SteelReinforcement directly
- reinforcement.SteelReinfMatMod → steel_reinforcement.SteelReinforcement
- reinforcement.CarbonReinfMatMod → (no modern equivalent yet)
- concrete_old.py → concrete/ subfolder or ec2_concrete.EC2Concrete

For new code, use the modern API from bmcs_cross_section.matmod instead.
"""

import warnings

warnings.warn(
    "The matmod.legacy module contains deprecated traits-based material models. "
    "Use the modern Pydantic-based API from bmcs_cross_section.matmod instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy imports (if needed for backward compatibility)
# Uncomment only if absolutely necessary
# from .matmod import MatMod
# from .reinforcement import ReinfMatMod, SteelReinfMatMod, CarbonReinfMatMod
# from .concrete_old import ConcreteMatMod, PWLConcreteMatMod
# from .sz_advanced import SZAdvanced
