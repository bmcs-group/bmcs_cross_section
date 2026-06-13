"""
scite.beam.floor
================

Building blocks for floor-system load-deflection analysis.

All classes are pure Python — no CFrame, usable in notebooks and scripts.

Public API
----------
Primitives
~~~~~~~~~~
FloorSectionRC     — rectangular RC section (flat slab strip)
FloorSectionRCRib  — T-section RC rib (ribbed slab, web + bay-slab flange)
FloorSectionCRC    — rectangular CRC section (flat slab strip, CFRP)
FloorSectionCRCRib — T-section CRC rib (ribbed slab, web + bay-slab flange)
FloorAnalysis      — single BeamDeflectionAnalysis wrapper with p-conversion
FloorAnalysisPair  — SLS + ULS pair (alias: BeamPair); factory methods:
                       .for_rc()       — flat slab (rectangular RC)
                       .for_rc_rib()   — ribbed slab rib (T-section RC)
                       .for_crc()      — flat slab (rectangular CRC/CFRP)
                       .for_crc_rib()  — ribbed slab rib (T-section CRC/CFRP)
BeamPair           — alias for FloorAnalysisPair
ec2_beff_rib       — EC2 §5.3.2.1 effective flange width for T-section rib

Floor system models
~~~~~~~~~~~~~~~~~~~
FloorSystemBase    — mixin providing assess() / print_assessment()
LoadModel          — EN 1990 surface load combination (p_Ed_qp, p_Ed_u)
FlatSlab           — SRC flat slab (rectangular, 1 m strip)
CRCFlatSlab        — CRC flat slab (rectangular, 1 m strip, CFRP)
SRCRibbedSlab      — SRC ribbed slab (T-section rib + bay slab, steel)
CRCRibbedSlab      — CRC ribbed slab (T-section rib, CFRP + bay slab, CFRP)
"""
from .flat_slab import CRCFlatSlab, FlatSlab
from .floor_analysis import FloorAnalysis, FloorAnalysisPair, ec2_beff_rib
from .floor_system_base import FloorSystemBase
from .load_model import LoadModel
from .ribbed_slab import CRCRibbedSlab, SRCRibbedSlab
from .section_crc import FloorSectionCRC, FloorSectionCRCRib
from .section_rc import FloorSectionRC, FloorSectionRCRib

# Preferred short alias — FloorAnalysisPair kept for backward compatibility
BeamPair = FloorAnalysisPair

__all__ = [
    # Primitives
    "FloorSectionRC",
    "FloorSectionRCRib",
    "FloorSectionCRC",
    "FloorSectionCRCRib",
    "FloorAnalysis",
    "FloorAnalysisPair",
    "BeamPair",
    "ec2_beff_rib",
    # Floor system models
    "FloorSystemBase",
    "LoadModel",
    "FlatSlab",
    "CRCFlatSlab",
    "SRCRibbedSlab",
    "CRCRibbedSlab",
]
