"""
scite.beam.continuous
======================

Two-span nonlinear continuous beam analysis via rotation compatibility.

Public API
----------
ContinuousBeamAnalysis — iterative solver for the interior support moment M_hog
                         using the SSB displacement BC and brentq root finding.
                         Provides moment profiles, deflection profiles, and a
                         full plotting suite (scheme, M, w, redistribution,
                         summary).
_phi_ssb               — standalone SSB rotation helper (w(0)=w(L)=0 BC).
"""
from .continuous_beam import ContinuousBeamAnalysis, _phi_ssb

__all__ = [
    "ContinuousBeamAnalysis",
    "_phi_ssb",
]
