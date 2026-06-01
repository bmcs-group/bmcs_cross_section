# scite.beam — beam deflection, SLS checks, and structural system analysis
# Migrated from bmcs_beam (April 2026)

# New Pydantic-based API (no legacy dependencies)
from scite.beam.bending.beam_deflection import BeamDeflectionAnalysis
from scite.beam.continuous import ContinuousBeamAnalysis

# Legacy traits-based API (requires bmcs_utils / traits; optional in modern envs)
try:
    from scite.beam.api import (
        BeamDesign,
        BeamSLSCurve,
        BoundaryConditions,
        BoundaryConfig,
        CantileverDistLoadSystem,
        DeflectionProfile,
        FourPBSystem,
        SimpleDistLoadSystem,
        ThreePBSystem,
    )
except (ModuleNotFoundError, ImportError):
    pass  # traits not available or circular import in legacy modules
