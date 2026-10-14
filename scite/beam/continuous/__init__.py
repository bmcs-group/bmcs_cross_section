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
ElasticContinuousBeam  — linear-elastic n-span beam (three-moment equation) with
                         uniform and point loads per span: support moments,
                         reactions, M/V profiles, field moments, deflection.
"""
from .continuous_beam import ContinuousBeamAnalysis, CompatibilityNoRoot, _phi_ssb
from .elastic import BeamProfiles, ElasticContinuousBeam, FieldMoment, PointLoad, UniformLoad
from .modes import ContinuousBeamModes

__all__ = [
    "ContinuousBeamAnalysis",
    "CompatibilityNoRoot",
    "_phi_ssb",
    "ContinuousBeamModes",
    "ElasticContinuousBeam",
    "UniformLoad",
    "PointLoad",
    "BeamProfiles",
    "FieldMoment",
]
