"""
scite.shared.units
==================

Unit-conversion infrastructure for scite structural models.

All scite model fields store values in **base units** (mm for lengths, mm² for
reinforcement areas).  This module provides:

- ``UnitLevel``  — tag enum that classifies a field's physical role
- ``UnitSystem`` — enum of supported display-unit conventions
- ``UnitContext`` — converts between display units and base units
- ``field_mm()``  — ``dataclasses.field`` wrapper that embeds ``UnitLevel``
                    metadata so ``UnitContext`` can discover it at runtime

Usage — notebook
----------------
::

    from scite.shared.units import UnitContext, UnitSystem
    from scite.beam.floor  import FlatSlab

    ctx  = UnitContext(UnitSystem.CUSTOMARY_STRUCTURAL)
    slab = ctx.adapt(FlatSlab, h=200, A_s=3.0, z_s=35, L=6.0)
    # stored internally as FlatSlab(h=200, A_s=300.0, z_s=35, L=6000.0)

    v = slab.volumes()
    print(ctx.label('L', FlatSlab))          # → 'm'
    print(ctx.label('A_s', FlatSlab))        # → 'cm²'

Usage — icc_app CNode
---------------------
::

    ctx = UnitContext(app_settings.unit_system)
    return ctx.adapt(_SciteFlatSlab, h=self.h, A_s=self.A_s, L=self.L)

Unit-level table
----------------
==================  ====  =======  =========  ========
UnitSystem          STRUCTURAL  CS_DIM  REINF_AREA
==================  ==========  ======  ==========
MM_BASE             mm          mm      mm²
CUSTOMARY           m           mm      cm²
ALL_METERS          m           m       m²
IMPERIAL            ft          in      in²
==================  ==========  ======  ==========
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Type


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class UnitLevel(str, Enum):
    """Physical role of a model field — determines which conversion applies."""
    STRUCTURAL = 'structural'   # span, member length         → base: mm
    CS_DIM     = 'cs_dim'       # cross-section dim (h, b, z) → base: mm
    REINF_AREA = 'reinf_area'   # reinforcement area (total)  → base: mm²


class UnitSystem(str, Enum):
    """Supported display-unit conventions."""
    MM_BASE              = 'mm_base'    # all in mm / mm²         (internal default)
    CUSTOMARY_STRUCTURAL = 'customary'  # m / mm / cm²            (European SE)
    ALL_METERS           = 'all_m'      # m / m / m²              (SI consistent)
    IMPERIAL             = 'imperial'   # ft / in / in²           (US / literature)


# ---------------------------------------------------------------------------
# Conversion tables
# ---------------------------------------------------------------------------

# Factor: display_value × factor → base_value (mm or mm²)
# Entries not listed → factor 1.0 (already in base units)
_TO_BASE: dict[tuple[UnitLevel, UnitSystem], float] = {
    # CUSTOMARY_STRUCTURAL
    (UnitLevel.STRUCTURAL,  UnitSystem.CUSTOMARY_STRUCTURAL): 1_000.0,
    (UnitLevel.CS_DIM,      UnitSystem.CUSTOMARY_STRUCTURAL): 1.0,
    (UnitLevel.REINF_AREA,  UnitSystem.CUSTOMARY_STRUCTURAL): 100.0,
    # ALL_METERS
    (UnitLevel.STRUCTURAL,  UnitSystem.ALL_METERS): 1_000.0,
    (UnitLevel.CS_DIM,      UnitSystem.ALL_METERS): 1_000.0,
    (UnitLevel.REINF_AREA,  UnitSystem.ALL_METERS): 1_000_000.0,
    # IMPERIAL
    (UnitLevel.STRUCTURAL,  UnitSystem.IMPERIAL): 304.8,
    (UnitLevel.CS_DIM,      UnitSystem.IMPERIAL): 25.4,
    (UnitLevel.REINF_AREA,  UnitSystem.IMPERIAL): 645.16,
    # MM_BASE: all 1.0 — handled by default
}

# Display label: what unit string to show in the UI
_DISPLAY_LABEL: dict[tuple[UnitLevel, UnitSystem], str] = {
    # CUSTOMARY_STRUCTURAL
    (UnitLevel.STRUCTURAL,  UnitSystem.CUSTOMARY_STRUCTURAL): 'm',
    (UnitLevel.CS_DIM,      UnitSystem.CUSTOMARY_STRUCTURAL): 'mm',
    (UnitLevel.REINF_AREA,  UnitSystem.CUSTOMARY_STRUCTURAL): 'cm²',
    # ALL_METERS
    (UnitLevel.STRUCTURAL,  UnitSystem.ALL_METERS): 'm',
    (UnitLevel.CS_DIM,      UnitSystem.ALL_METERS): 'm',
    (UnitLevel.REINF_AREA,  UnitSystem.ALL_METERS): 'm²',
    # IMPERIAL
    (UnitLevel.STRUCTURAL,  UnitSystem.IMPERIAL): 'ft',
    (UnitLevel.CS_DIM,      UnitSystem.IMPERIAL): 'in',
    (UnitLevel.REINF_AREA,  UnitSystem.IMPERIAL): 'in²',
    # MM_BASE
    (UnitLevel.STRUCTURAL,  UnitSystem.MM_BASE): 'mm',
    (UnitLevel.CS_DIM,      UnitSystem.MM_BASE): 'mm',
    (UnitLevel.REINF_AREA,  UnitSystem.MM_BASE): 'mm²',
}


# ---------------------------------------------------------------------------
# field_mm helper
# ---------------------------------------------------------------------------

_MISSING = object()  # sentinel for "no default provided"


def field_mm(level: UnitLevel, default: float = _MISSING, **kw: Any) -> Any:  # type: ignore[assignment]
    """``dataclasses.field`` wrapper that embeds ``UnitLevel`` metadata.

    Parameters
    ----------
    level   : UnitLevel tag for this field
    default : default value **in base units (mm / mm²)**.
              Omit to declare a *required* field (no default).
    **kw    : forwarded to ``dataclasses.field``

    Example
    -------
    ::

        @dataclass
        class FlatSlab(FloorSystemBase):
            h:   float = field_mm(UnitLevel.CS_DIM)            # required
            L:   float = field_mm(UnitLevel.STRUCTURAL, 5000.0)
            A_s: float = field_mm(UnitLevel.REINF_AREA,  300.0)
    """
    meta: dict[str, Any] = {'unit_level': level, 'base_unit': 'mm'}
    kwargs: dict[str, Any] = {'metadata': meta}
    if default is not _MISSING:
        kwargs['default'] = default
    kwargs.update(kw)
    return dataclasses.field(**kwargs)


# ---------------------------------------------------------------------------
# UnitContext
# ---------------------------------------------------------------------------

class UnitContext:
    """Converts values between a chosen display-unit system and base units (mm).

    Parameters
    ----------
    system : UnitSystem
        Active display-unit convention.  Defaults to ``MM_BASE`` (no
        conversion — values passed through unchanged).

    Methods
    -------
    to_base(value, level)
        Convert a single display-unit value to mm / mm².
    from_base(value, level)
        Convert a single base-unit value to display units.
    adapt(model_cls, **kwargs)
        Instantiate *model_cls* after converting all kwargs that carry
        ``UnitLevel`` metadata from display units to base units.
    display_value(field_name, model_cls, base_value)
        Convert a base-unit value to display units for a named field.
    label(field_name, model_cls)
        Return the display-unit label string (e.g. 'm', 'cm²') for a field.
    """

    def __init__(self, system: UnitSystem = UnitSystem.MM_BASE) -> None:
        self.system = system

    # ── scalar conversion ──────────────────────────────────────────────────

    def to_base(self, value: float, level: UnitLevel | None) -> float:
        """Display-unit value → base-unit value (mm / mm²)."""
        if level is None:
            return value
        return value * _TO_BASE.get((level, self.system), 1.0)

    def from_base(self, value: float, level: UnitLevel | None) -> float:
        """Base-unit value (mm / mm²) → display-unit value."""
        if level is None:
            return value
        factor = _TO_BASE.get((level, self.system), 1.0)
        return value / factor if factor else value

    # ── model construction ─────────────────────────────────────────────────

    def adapt(self, model_cls: type, **kwargs: Any) -> Any:
        """Construct *model_cls* with all kwargs converted to base units.

        Fields that carry ``UnitLevel`` metadata (via ``field_mm``) are
        converted automatically.  Fields without metadata pass through
        unchanged.

        Parameters
        ----------
        model_cls : dataclass type
        **kwargs  : field values in display units

        Returns
        -------
        An instance of *model_cls* with all values stored in base units (mm).
        """
        fields_by_name = {f.name: f for f in dataclasses.fields(model_cls)}
        converted: dict[str, Any] = {}
        for name, val in kwargs.items():
            f = fields_by_name.get(name)
            level = f.metadata.get('unit_level') if f else None
            converted[name] = self.to_base(val, level)
        return model_cls(**converted)

    # ── display helpers ────────────────────────────────────────────────────

    def display_value(self, field_name: str, model_cls: type,
                      base_value: float) -> float:
        """Return *base_value* converted to display units for *field_name*."""
        level = self._get_level(field_name, model_cls)
        return self.from_base(base_value, level)

    def label(self, field_name: str, model_cls: type) -> str:
        """Return the display-unit label string for *field_name*.

        Returns 'mm' / 'mm²' if the field is not annotated or system is
        ``MM_BASE``.
        """
        level = self._get_level(field_name, model_cls)
        if level is None:
            return ''
        return _DISPLAY_LABEL.get((level, self.system), 'mm')

    def labels(self, model_cls: type) -> dict[str, str]:
        """Return ``{field_name: unit_label}`` for all annotated fields."""
        result: dict[str, str] = {}
        for f in dataclasses.fields(model_cls):
            level = f.metadata.get('unit_level')
            if level is not None:
                result[f.name] = _DISPLAY_LABEL.get((level, self.system), 'mm')
        return result

    # ── private ────────────────────────────────────────────────────────────

    @staticmethod
    def _get_level(field_name: str, model_cls: type) -> UnitLevel | None:
        for f in dataclasses.fields(model_cls):
            if f.name == field_name:
                return f.metadata.get('unit_level')
        return None
