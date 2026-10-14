"""
scite.safety — the safety concept of EN 1990: actions, combinations, reliability.

Headless core for the "load model and safety concept" part of the structural
concrete courses (moved from the gdt repository's ``safety_concept`` on 2026-10-14,
cscp-arch concept 08 step S3). No UI, no file I/O: pydantic models that a cframe
node, a notebook or a workflow can drive.

- ``actions``     — permanent and variable actions with their ψ factors; the ULS
                    combinations 6.10, 6.10a/b and the SLS combinations of EN 1990.
- ``reliability`` — the safety margin M = R − E of two independent normal variables:
                    reliability index β, probability of failure, and the
                    semi-probabilistic design values behind the partial factors.
"""
from .actions import (
    PARTIAL_FACTORS,
    PSI_FACTORS,
    CombinationResult,
    LoadCombination,
    PermanentAction,
    VariableAction,
    office_example,
)
from .reliability import SafetyMargin

__all__ = [
    "PARTIAL_FACTORS", "PSI_FACTORS", "PermanentAction", "VariableAction",
    "CombinationResult", "LoadCombination", "office_example", "SafetyMargin",
]
