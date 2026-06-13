# Concept 09 — Unit System for Structural Concrete Parameters

**Status:** Proposal — under review  
**Scope:** `scite.beam` (mkappa, beam, continuous, floor) + `scite/shared`

---

## 1  Problem statement

All scite model parameters currently use **mm as the base unit** for all length
quantities. This is internally consistent and numerically safe (e.g. N/mm² = MPa
avoids the 10⁶ factor present in SI N/m²). However, structural engineers work
with a **mixed unit convention**:

| Parameter level | Customary unit | Base (model) unit | Factor |
|---|---|---|---|
| Structural / span | m | mm | × 1000 |
| Cross-section dimension | mm | mm | × 1 |
| Reinforcement area (per width) | cm²/m | mm²/m | × 100 |
| Reinforcement area (total) | cm² | mm² | × 100 |
| Load (surface) | kN/m² | kN/m² | × 1 |
| Load (line) | kN/m | kN/m | × 1 |
| Moment | kN·m | kN·mm | × 1000 |

A user entering a span expects to type `6.0` (metres), not `6000` (mm). The
mismatch is a persistent source of input errors and cognitive friction.

---

## 2  Scope of affected modules

The unit concern is **cross-cutting** — it applies everywhere a user-facing
parameter exists:

- `scite.beam.mkappa` — κ [1/mm], M [kN·m vs kN·mm], b/h [mm]
- `scite.beam.bending` — span L [m vs mm], load q [kN/m]
- `scite.beam.continuous` — same as `bending`
- `scite.beam.floor` — span L [m], cs dims [mm], A_s [cm²/m vs mm²/m]

This argues for a **shared infrastructure** rather than per-module ad-hoc
conversion — otherwise the same conversion logic is duplicated in every CNode
and every notebook.

---

## 3  Option analysis

### 3a  Convert in `icc_app` CNodes only

Each CNode widget converts from display units → mm before calling `_make_model()`.

**Pros:** scite models stay unit-agnostic; no changes to existing code.  
**Cons:**
- The *same* field (e.g. `L=6000`) appears differently in notebooks vs. the app.
  Notebooks must still know to pass mm; the app uses m. Impedance mismatch.
- The conversion logic must be duplicated for every CNode that has a span field.
- No machine-readable record of which fields expect which unit level — the
  metadata lives only in widget configuration strings, not in the model.
- A second frontend (e.g. a REST API or a CLI) would need to re-implement
  the same conversions independently.

**Verdict:** viable short-term; does not scale.

---

### 3b  Annotate model fields with unit metadata (recommended)

Embed **unit-level tags** directly in the model field definitions. The
conversion from display units to base units then happens at a single, explicit
boundary driven by this metadata.

#### 3b-1  Python `dataclasses.field(metadata=…)`

Standard library. `field(metadata=...)` accepts any mapping; accessible via
`dataclasses.fields(cls)` at runtime.

```python
from dataclasses import dataclass, field

@dataclass
class FlatSlab(FloorSystemBase):
    L:   float = field(default=5000.0, metadata={'unit': 'mm', 'level': 'structural'})
    h:   float = field(default=200.0,  metadata={'unit': 'mm', 'level': 'cs_dim'})
    A_s: float = field(default=300.0,  metadata={'unit': 'mm2', 'level': 'reinf_area'})
```

Readable at class level:
```python
import dataclasses
for f in dataclasses.fields(FlatSlab):
    print(f.name, f.metadata)
```

**Pros:** zero dependencies; already the style used in scite.  
**Cons:** metadata is a plain dict — no type checking, no validator hooks.

#### 3b-2  Pydantic v2 `Annotated` + `Field`

Pydantic 2.13 (already in the venv) supports rich annotation metadata:

```python
from typing import Annotated
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

class UnitTag:
    """Marker attached to a field to declare its unit level."""
    def __init__(self, level: str, base_unit: str):
        self.level = level
        self.base_unit = base_unit  # always mm or mm2

Span       = Annotated[float, UnitTag(level='structural',  base_unit='mm')]
CsDim      = Annotated[float, UnitTag(level='cs_dim',      base_unit='mm')]
ReinfArea  = Annotated[float, UnitTag(level='reinf_area',  base_unit='mm2')]
```

```python
class FlatSlab(BaseModel, FloorSystemBase):
    L:   Span      = 5000.0
    h:   CsDim     = 200.0
    A_s: ReinfArea = 300.0
```

A **validator** on the model (or on the `UnitContext` adapter) intercepts
incoming values and converts before storage.  Pydantic keeps models in base
units internally; display conversion is always explicit.

**Pros:** type aliases are self-documenting; Pydantic validators make the
conversion automatic at model construction.  
**Cons:** requires migrating dataclasses to Pydantic BaseModel (significant
refactor); Pydantic adds overhead per instantiation.

#### 3b-3  Hybrid — dataclass fields + lightweight `UnitContext` adapter

Keep scite models as plain dataclasses with metadata dict. Add a thin
`scite.shared.units` module that provides:

1. `UnitLevel` enum (`STRUCTURAL`, `CS_DIM`, `REINF_AREA`)
2. `UnitSystem` enum (`MM_BASE`, `CUSTOMARY_STRUCTURAL`)
3. `UnitContext` class — reads field metadata, applies conversion factors
4. A `field_mm(level, default)` helper — wraps `dataclasses.field` with
   standard metadata

```python
# scite/shared/units.py

from enum import Enum
import dataclasses

class UnitLevel(str, Enum):
    STRUCTURAL  = 'structural'   # span, member length  → mm
    CS_DIM      = 'cs_dim'       # h, b, d, z, cover    → mm
    REINF_AREA  = 'reinf_area'   # A_s, A_f (total)     → mm²

class UnitSystem(str, Enum):
    MM_BASE              = 'mm_base'      # all in mm / mm²      (internal base)
    CUSTOMARY_STRUCTURAL = 'customary'    # m / mm / cm²         (European SE default)
    ALL_METERS           = 'all_m'        # m / m / m²           (SI consistent)
    IMPERIAL             = 'imperial'     # ft / in / in²        (US / literature)

# Conversion factors: display_unit → base_unit (mm / mm²)
# Missing entries → factor 1.0 (already in base units)
_TO_BASE: dict[tuple[UnitLevel, UnitSystem], float] = {
    # CUSTOMARY_STRUCTURAL: m for spans, mm for cross-section, cm² for reinf
    (UnitLevel.STRUCTURAL,  UnitSystem.CUSTOMARY_STRUCTURAL): 1_000.0,   # m   → mm
    (UnitLevel.CS_DIM,      UnitSystem.CUSTOMARY_STRUCTURAL): 1.0,       # mm  → mm
    (UnitLevel.REINF_AREA,  UnitSystem.CUSTOMARY_STRUCTURAL): 100.0,     # cm² → mm²
    # ALL_METERS: every length in m, area in m²
    (UnitLevel.STRUCTURAL,  UnitSystem.ALL_METERS):           1_000.0,   # m   → mm
    (UnitLevel.CS_DIM,      UnitSystem.ALL_METERS):           1_000.0,   # m   → mm
    (UnitLevel.REINF_AREA,  UnitSystem.ALL_METERS):           1_000_000.0, # m² → mm²
    # IMPERIAL: ft for spans, in for cs dims, in² for reinf
    (UnitLevel.STRUCTURAL,  UnitSystem.IMPERIAL):             304.8,     # ft  → mm
    (UnitLevel.CS_DIM,      UnitSystem.IMPERIAL):             25.4,      # in  → mm
    (UnitLevel.REINF_AREA,  UnitSystem.IMPERIAL):             645.16,    # in² → mm²
    # MM_BASE: all factors implicitly 1.0
}

def field_mm(level: UnitLevel, default: float, **kw):
    """dataclasses.field wrapper that embeds unit metadata."""
    return dataclasses.field(
        default=default,
        metadata={'unit': 'mm', 'level': level},
        **kw,
    )


class UnitContext:
    """Converts user-supplied values to base units (mm) before model construction."""

    def __init__(self, system: UnitSystem = UnitSystem.MM_BASE):
        self.system = system

    def to_base(self, value: float, level: UnitLevel) -> float:
        factor = _TO_BASE.get((level, self.system), 1.0)
        return value * factor

    def from_base(self, value: float, level: UnitLevel) -> float:
        factor = _TO_BASE.get((level, self.system), 1.0)
        return value / factor

    def adapt(self, model_cls, **kwargs):
        """Construct *model_cls* after converting all kwargs to base units."""
        fields_by_name = {f.name: f for f in dataclasses.fields(model_cls)}
        converted = {}
        for name, val in kwargs.items():
            f = fields_by_name.get(name)
            level = f.metadata.get('level') if f else None
            converted[name] = self.to_base(val, level) if level else val
        return model_cls(**converted)
```

Usage in a notebook:

```python
from scite.shared.units import UnitContext, UnitSystem

ctx = UnitContext(UnitSystem.CUSTOMARY_STRUCTURAL)
slab = ctx.adapt(FlatSlab, h=200, A_s=3.0, z_s=35, L=6.0)
# → FlatSlab(h=200, A_s=300.0, z_s=35, L=6000.0)  # stored in mm
```

Usage in `icc_app` CNodes:

```python
# _make_model() receives display-unit values from the CNode fields
ctx = UnitContext(app_settings.unit_system)
return ctx.adapt(_SciteFlatSlab, h=self.h, A_s=self.A_s, L=self.L, …)
```

---

## 4  Recommended approach

**Option 3b-3 — hybrid dataclass + `UnitContext`.**

| Criterion | Rationale |
|---|---|
| No breaking changes | scite model internals stay in mm; all existing notebooks and tests remain valid |
| Single source of truth | Unit metadata lives *on the model field*, not scattered across CNodes |
| Framework-agnostic | Works for notebooks, icc_app CNodes, REST adapters, CLI — any caller uses `UnitContext.adapt()` |
| Incremental adoption | Fields can be annotated one module at a time; unannotated fields pass through unchanged |
| No new dependencies | Pure stdlib + existing venv |

---

## 5  Implementation plan

### Phase 1 — Infrastructure (new `scite/shared/`)

1. Create `scite/shared/__init__.py`
2. Create `scite/shared/units.py` with `UnitLevel`, `UnitSystem`, `UnitContext`,
   `field_mm()` helper
3. Unit tests: `tests/shared/test_units.py` — round-trip conversion for all
   levels and systems

### Phase 2 — Annotate `scite.beam.floor` fields

Replace bare `float` fields with `field_mm(level, default)` calls:

```python
# flat_slab.py
from scite.shared.units import UnitLevel, field_mm

@dataclass
class FlatSlab(FloorSystemBase):
    h:   float = field_mm(UnitLevel.CS_DIM,     200.0)
    A_s: float = field_mm(UnitLevel.REINF_AREA, 300.0)
    z_s: float = field_mm(UnitLevel.CS_DIM,      35.0)
    L:   float = field_mm(UnitLevel.STRUCTURAL, 5000.0)
    b:   float = field_mm(UnitLevel.CS_DIM,     1000.0)
    …
```

### Phase 3 — Annotate remaining `scite.beam` modules

Apply the same treatment to `ribbed_slab.py`, `mkappa`, `beam`, `continuous`.

### Phase 4 — Integrate `UnitContext` in `icc_app`

Add `unit_system` setting to `icc_app` global settings (CNode or environment).
Update `_make_model()` in all CNodes to route through `ctx.adapt(…)`.

### Phase 5 — Output conversion

Extend `UnitContext` with an `output_map` for `volumes()` / `assess()` dict
keys, so `ctx.from_base_dict(v, key_map)` can present results in display units.
This is lower priority than input conversion since outputs are primarily
shown in plots/tables, not fed back as inputs.

---

## 6  Open questions / resolutions

1. **Mixed reinf_area units — RESOLVED.**  
   A single `REINF_AREA` level covers all cases (mm² → cm², factor ×100).
   The user always supplies a **total reinforcement area**; the 1 m strip
   normalisation is an internal model convention never exposed at the API
   boundary. This applies uniformly to floor slab strips, bay assessments,
   mkappa, beam, and continuous. Auto-adapting the reinforcement area when
   geometry changes (e.g. width `b` changes) is explicitly **not** desired
   behaviour.

2. **`UnitSystem` enumeration — RESOLVED.**  
   Four systems defined (see updated code above):

   | System | Span | CS dim | Reinf area | Use case |
   |---|---|---|---|---|
   | `MM_BASE` | mm | mm | mm² | internal base; existing notebooks |
   | `CUSTOMARY_STRUCTURAL` | m | mm | cm² | European SE practice (default for app) |
   | `ALL_METERS` | m | m | m² | SI-consistent; scientific publications |
   | `IMPERIAL` | ft | in | in² | US codes; literature interpretation |

3. **icc_app display labels**: the CFrame `CField` `unit` string (displayed next
   to the input widget) should be driven by the active `UnitSystem` and the
   field's `UnitLevel`, not hard-coded. A small lookup table
   `_DISPLAY_UNIT[UnitLevel, UnitSystem] → str` in `scite/shared/units.py`
   provides the label; `CField` reads it via the field metadata. This is a
   targeted addition to the CFrame `CField` descriptor — no architectural change.

4. **Pydantic migration — RECOMMENDED as next major refactor.**

   *Overhead concern* — negligible in this application.  Pydantic v2 uses a
   Rust-backed core (pydantic-core); instantiation of a ~15-field model with
   float validation takes **< 5 µs**.  The dominant runtime cost in scite is
   `BeamDeflectionAnalysis` (numerical ODE integration, ~1–100 ms per call) and
   `brentq` solves.  Pydantic adds at most 0.01 % to any realistic workload.
   Future optimisation calls (parameter sweeps, feasibility search) will
   multiply the integration calls, not the model construction.

   *Migration effort* — moderate, not large.  The mechanical changes per class are:

   | Change | Notes |
   |---|---|
   | `@dataclass` removed; class inherits `BaseModel` | one line |
   | `field(default=x)` → `Field(default=x)` | near-identical syntax |
   | `__post_init__` → `@model_validator(mode='after')` | direct translation |
   | `@property` retained as-is | Pydantic does not interfere |
   | Computed attrs (e.g. `beam`) need `arbitrary_types_allowed=True` in `model_config` | one config line per class |

   Estimated effort: ~15–20 model classes across `floor`, `mkappa`, `beam`,
   `continuous` → **3–5 days** for a careful, tested migration.

   *Benefits that tip the decision:*
   - `Annotated[float, UnitTag(...)]` replaces `field_mm()` with proper typing —
     unit metadata becomes part of the type system, not a plain dict.
   - Field validators apply `UnitContext` conversion **inside** the model
     constructor, eliminating the external `ctx.adapt()` call entirely.
   - `model.model_dump()` / `model.model_validate(dict)` enable
     save/restore of app state, REST API, test fixtures — for free.
   - Explicit input validation catches nonsensical values (negative h, zero L)
     at model boundary rather than silently producing garbage results.

   *Strategy:* implement option 3b-3 (dataclass + `field_mm` metadata) first as
   a zero-risk pilot on `scite.beam.floor`.  This establishes the `UnitLevel`
   vocabulary and `UnitContext` contract.  The Pydantic migration then becomes a
   clean swap: `field_mm(level, x)` → `Field(default=x)` with `Annotated` type
   alias, `UnitContext` converter moves into a `@field_validator`.  No
   downstream code (notebooks, CNodes) changes — the public API is identical.
