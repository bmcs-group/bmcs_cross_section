"""
NM Assessment Module
====================

Normal force and moment assessment for reinforced concrete cross-sections.

Uses design material properties and iterative equilibrium solving to assess
cross-section capacity under combined N and M loading.
"""

from .nm_assessment import NMAssessment

__all__ = ['NMAssessment']
