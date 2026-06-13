# Floor System Refactoring Plan
## `scite.beam.floor` — Self-contained, Notebook-ready Architecture

**Date:** 2026-05-24  
**Status:** Planning  

---

## 1  Motivation and Diagnosis

### 1.1  Current state of affairs

The floor analysis logic is split across two packages with blurred
responsibilities:

| Location | What is there | Problem |
|---|---|---|
| `scite/beam/floor/` | Primitive building blocks + three dataclass models | Models are already mostly correct but **incomplete** (missing uniform base class, `CRCFlatSlab`, resource fields not user-adjustable, no standalone notebook demonstrating the full system) |
| `icc_apps/icc_app/part01/models/` | CNode UI wrappers (`SRCFlatSlab`, `SRCRibbedSlab`, `CRCRibbedSlab`, …) | These wrappers **carry computational logic** that belongs in scite: geometry→load transformation, g_k derivation, GWP computation |
| `icc_apps/icc_app/part01/models/floor_system.py` | Abstract `FloorSystem` CNode base with 890 lines | Plotting helpers (`_draw_Fw_panel`, `_draw_combined_section_plot`) and static builders belong in scite, not in the UI adapter |

### 1.2  Role separation (target)

```
scite.beam.floor            ← pure Python, no UI framework, notebook-first
├── FloorSystemBase         abstract base: g_k, volumes(), report(), plot_*()
├── FlatSlab                SRC rectangular slab strip
├── CRCFlatSlab             CRC rectangular slab strip  [NEW]
├── SRCRibbedSlab           SRC T-section rib + bay slab
├── CRCRibbedSlab           CRC T-section rib + bay slab
└── LoadModel               EN 1990 load combinations + line-load conversion

icc_apps/icc_app/part01/models/
├── src_flat_slab.py        CNode — NOT yet refactored; all physics still inline  ← TODO
├── src_ribbed_slab.py      CNode UI adapter — delegates to scite ✓
└── crc_ribbed_slab.py      CNode UI adapter — delegates to scite ✓

(src_flat_plate.py and src_one_way_slab.py deleted — superseded by the three classes above)
```

The **CNode is a thin adapter** that:
1. Exposes `CField` sliders/inputs to the web UI
2. Calls `_make_model()` to instantiate the scite dataclass from current CField values
3. Delegates all computation and plotting to the scite model

---

## 2  Target Architecture for `scite.beam.floor`

### 2.1  `FloorSystemBase` — abstract base class

A lightweight abstract Python class (not a dataclass itself) with the shared
protocol:

```python
class FloorSystemBase:
    @property
    def g_k(self) -> float:
        """Structural self-weight [kN/m²]."""
        ...

    @property
    def span(self) -> float:
        """Primary span for L/250 check [mm]."""
        ...

    def primary_beam(self) -> FloorAnalysisPair:
        """Main load-carrying beam (rib or slab strip)."""
        ...

    def volumes(self) -> dict:
        """Material volumes and GWP per reference area."""
        ...

    def report(self, lm: LoadModel | None = None) -> None: ...

    # ── Plotting ──────────────────────────────────────────────────────────────
    def plot_pw(self, ax, lm=None, *, element='primary', title='') -> None:
        """p-w capacity + demand curves for the specified beam element."""

    def plot_floor_assessment(self, axes, lm: LoadModel | None = None) -> None:
        """Multi-panel assessment figure (load, beam p-w, …)."""
```

Each concrete subclass declares its specific geometry, section, and material
dataclass fields and implements the abstract interface.

### 2.2  `FlatSlab` — SRC rectangular slab strip

Already substantially complete.  Gaps to close:

- **`plot_floor_assessment(axes, lm)`** — two-panel layout (load bar + p-w
  curve) to match ribbed-slab three-panel convention; or a single panel to
  reflect the simpler geometry.  Should accept either 1 or 2 axes.
- **`volumes()`** key harmonisation — currently returns per-m² only.  Add
  `A_ref = L * b / 1e6` and consistent keys (`V_c`, `m_c_kg`, etc.) matching
  the ribbed-slab dict so downstream GWP comparison code is uniform.
- **User-adjustable resource parameters** — currently hardcoded constants
  (`_RHO_CONCRETE_KN`, `_E_CONC_CO2`).  Promote to optional dataclass fields
  with defaults (e.g., `rho_conc=25.0`, `e_conc=0.17`, `rho_steel=7850.0`,
  `e_steel=1.50`).
- **`r_transverse` factor** — icc_app uses `r_transverse` (transverse/main
  reinforcement ratio) in the slab volume calculation.  Expose as optional
  field `r_transverse: float = 0.20`.
- **Price per m²** — add unit-cost fields `p_conc=150.0` [€/m³],
  `p_reinf=1.20` [€/kg]; `volumes()` to include `cost_conc`, `cost_reinf`,
  `cost_total`, `cost_per_m2` [€/m²].

### 2.3  `CRCFlatSlab` — CRC rectangular slab strip  [NEW]

Mirror of `FlatSlab` but with CFRP reinforcement:

```python
@dataclass
class CRCFlatSlab(FloorSystemBase):
    h:        float         # slab depth [mm]
    A_f:      float         # CFRP area [mm²]
    z_f:      float         # cover to CFRP centroid [mm]
    f_ck:     float = 30.0
    E_f:      float = 210_000.0
    f_fk:     float = 3000.0
    L:        float = 5000.0
    b:        float = 1000.0
    rho_conc: float = 25.0
    gamma_c:  float = 1.50
    gamma_f:  float = 1.25

    beam: FloorAnalysisPair = field(init=False, repr=False)

    def __post_init__(self):
        self.beam = FloorAnalysisPair.for_crc(...)
```

Needed so `icc_app` can have a `CRCFlatSlab` CNode adapter identical in
structure to `SRCFlatSlab`.

### 2.4  `SRCRibbedSlab` — gaps to close

**Current split:** icc_app `_Resources._compute()` already calls `m.volumes()`
for concrete volumes (T-section correct), then computes steel volumes itself
using `r_long` and `a_slab`/`A_rib` CFields.  Emission factors (`e_conc`,
`e_reinf`) are CNode CFields.  The goal is to consolidate all of this into
scite so the icc_app CNode only passes values to the constructor.

- **User-adjustable resource parameters** — promote `_RHO_STEEL_KG`,
  `_E_CONC_CO2`, `_E_STEEL_CO2` from module-level constants to optional fields
  `rho_steel=7850.0`, `e_conc=0.17`, `e_steel=1.50`.
- **`r_long` factor** — icc_app CNode uses `r_long` (ratio of transverse to
  longitudinal bay reinforcement, default 0.5) when computing `V_steel_slab =
  a_slab * (1 + r_long) * L_rib * L_bay`.  Expose as optional field
  `r_long: float = 0.5`.
- **`volumes()` completeness** — add `V_steel`, `mass_steel`,
  per-m² variants for both steel and concrete; consistent `A_bay` / `A_ref`
  key alongside per-bay totals.
- **Price per m²** — add unit-cost fields `p_conc=150.0` [€/m³],
  `p_reinf=1.20` [€/kg]; `volumes()` to include `cost_conc`, `cost_steel`,
  `cost_total`, `cost_per_m2` [€/m²].

### 2.5  `CRCRibbedSlab` — gaps to close

**Current split:** same pattern as SRC — icc_app calls `m.volumes()` for
concrete, then computes CFRP volumes from `r_long`, `a_f`, `A_f_rib` CFields,
applies `e_conc` and `e_cfrp` emission factors from CNode CFields.

- Same resource-parameter promotion as SRC.
- Add `rho_cfrp=1600.0`, `e_cfrp=19.0` optional fields (19 kgCO₂/kg is the
  icc_app default, not 30).
- `r_long: float = 0.5` for bay CFRP volume (same formula as SRC).
- `volumes()` — rename to use `V_f_rib`, `V_f_bay`, `m_f_rib_kg`,
  `m_f_slab_kg` etc. for CFRP clarity; add per-m² variants.
- **Price per m²** — add unit-cost fields `p_conc=150.0` [€/m³],
  `p_cfrp=100.0` [€/kg]; `volumes()` to include `cost_conc`, `cost_cfrp`,
  `cost_total`, `cost_per_m2` [€/m²].

### 2.6  `LoadModel` — enrichments

The current `LoadModel` only has `surface_loads(g_k) -> dict`.  Three
additions are needed:

```python
def line_load(self, p_area: float, w_trib_m: float) -> float:
    """Convert area load [kN/m²] to line load [kN/m = N/mm]."""
    return p_area * w_trib_m

def beam_loads(self, g_k: float, w_trib_m: float) -> dict:
    """Surface loads + equivalent beam line loads for SLS/ULS.

    Extends surface_loads() with:
      q_Ed_qp : quasi-permanent line load [N/mm]
      q_Ed_u  : ULS design line load      [N/mm]
    """

def plot_breakdown(self, ax, g_k, w_trib_m=None) -> None:
    """Bar chart; optionally shows beam line-load axis on the right."""
```

The `material_safety_factors()` method (currently only in icc_app CNodes)
should move here:

```python
def material_safety_factors(self) -> tuple[float, float]:
    """Return (gamma_c, gamma_s)."""
    return self.gamma_c, self.gamma_s
```

---

## 3  Module structure after refactoring

```
scite/beam/floor/
├── __init__.py           (updated public API)
├── floor_system_base.py  [NEW]  FloorSystemBase abstract class
├── flat_slab.py          [UPDATE]  FlatSlab + CRCFlatSlab; resource fields; volumes harmonized
├── ribbed_slab.py        [UPDATE]  resource fields; r_long; CFRP volume keys; CRCRibbedSlab CFRP keys
├── load_model.py         [UPDATE]  beam_loads(), line_load(), material_safety_factors()
├── floor_analysis.py     [no change needed]
├── section_rc.py         [no change needed]
└── section_crc.py        [no change needed]
```

---

## 4  New notebook: `04_floor_system_assessment.ipynb`

Filename: `notebooks/beam/verification/04_floor_system_assessment.ipynb`

**Purpose:** Demonstrate the high-level floor system API at the model level,
mirroring the later icc_app projection.

**Structure:**

| Section | Content |
|---|---|
| 0 — Setup | Imports only from `scite.beam.floor` |
| 1 — SRC Flat Slab | `FlatSlab.report(lm)`, `plot_floor_assessment`, `volumes()` |
| 2 — CRC Flat Slab | `CRCFlatSlab.report(lm)`, same pattern |
| 3 — SRC vs CRC Flat Slab | Normalised p-w comparison, GWP bar |
| 4 — SRC Ribbed Slab | `SRCRibbedSlab.report(lm)`, `plot_floor_assessment`, `volumes()` |
| 5 — CRC Ribbed Slab | `CRCRibbedSlab.report(lm)`, same pattern |
| 6 — SRC vs CRC Ribbed Slab | Normalised comparison (reuses Section 7 of notebook 02) |
| 7 — GWP comparison | Bar chart: all four system types at standard parameters |
| 8 — Geometry sweep | Span sweep for flat slab and ribbed slab |

Each section calls only **model-level** methods — no `FloorAnalysisPair.for_rc()`
or manual SLS/ULS assembly visible in the notebook code.

---

## 5  Relationship to icc_app refactoring (later milestone)

Once the notebook (`04`) is verified, the icc_app CNode wrappers can be
drastically simplified.  The current redundancy:

```
icc_app SRCRibbedSlab CNode (648 lines)
  ├── _RibGeometry       CNode  (holds CFields + 3D Plotly fig)
  ├── _RibSection        CNode  (CFields + update_plot → delegates to scite)   ← keep
  ├── _SlabSection       CNode  (CFields + update_plot → delegates to scite)   ← keep
  ├── _LoadAndSelfWeight CNode  (CFields + plotly_figure)                       ← keep
  ├── _Resources         CNode  (CFields + _compute → delegates to scite)      ← keep
  └── SRCRibbedSlab      CNode  (update_plot, _get_Fw_panel_specs, _make_model) ← delegates to scite
```

Post-refactoring, `_Resources._compute()` becomes a one-liner delegating to
`scite.SRCRibbedSlab.volumes()`; `_structural_self_weight()` to `scite.SRCRibbedSlab.g_k`.
The CNode's only job is to map `CField` values to the scite model constructor
and relay the results to the Streamlit/Plotly UI.  **No physics in icc_app**.

---

## 6  Execution sequence (milestones)

### Milestone 1 — `scite.beam.floor` completion  ← **current milestone**

1. [ ] Add `FloorSystemBase` (abstract protocol mixin) in `floor_system_base.py`
2. [ ] Add `CRCFlatSlab` dataclass in `flat_slab.py`
3. [ ] Promote resource constants to optional fields in all four models:
       `rho_conc`, `rho_steel`/`rho_cfrp`, `e_conc`, `e_steel`/`e_cfrp`
4. [ ] Add `r_long` to `SRCRibbedSlab` / `CRCRibbedSlab`, `r_transverse` to
       `FlatSlab` / `CRCFlatSlab`; update `volumes()` accordingly
5. [ ] Add unit-cost fields to all four models:
       `p_conc` [€/m³], `p_reinf` [€/kg] for SRC; `p_cfrp` [€/kg] for CRC
6. [ ] Harmonise `volumes()` dict across all four models — return:
       - per-element volumes and masses
       - `gwp_per_m2`, `cost_per_m2`, `A_ref`
       - both per-bay/strip totals and per-m² normalised values
7. [ ] Add `beam_loads()` and `material_safety_factors()` to `LoadModel`
8. [ ] Add `plot_floor_assessment()` to `FlatSlab` and `CRCFlatSlab`
9. [ ] Update `__init__.py` public API

### Milestone 2 — Notebook `04_floor_system_assessment.ipynb`

9. [ ] Write notebook using only the updated scite API (no manual pair assembly)
10. [ ] Verify all eight sections execute correctly

### Milestone 3 — icc_app CNode simplification  ← deferred

11. [ ] Simplify `src_flat_slab.py` CNode to a thin adapter (post-notebook verification)
12. [ ] Remove dead code (`_build_dp`, `_build_dp_pair`, legacy DeflectionProfile
        path in `floor_system.py`)

---

## 7  Design decisions and open questions

| Question | Decision |
|---|---|
| Should `FloorSystemBase` be an ABC or a Protocol? | Protocol (structural subtyping) — avoids metaclass complexity; scite dataclasses inherit it optionally |
| Where does `_draw_Fw_panel` live? | Move to `flat_slab.py` as module-level `plot_pw_panel()`; keep internal to scite |
| Should `LoadModel` own `gamma_c/s/f`? | Yes — already does. `material_safety_factors()` is just a convenience accessor |
| Should `volumes()` use per-bay or per-m²? | Both — return both in the same dict, with a clear `A_ref` key for normalisation |
| CRC bay slab material in `CRCRibbedSlab` | Bay slab uses steel (as currently); only rib uses CFRP.  `CRCFlatSlab` is all-CFRP |
| GWP emission factors — hardcoded or fields? | Optional dataclass fields with sensible defaults (matches icc_app CField pattern) |
| Price per m² — where does it live? | In the scite model as optional unit-cost fields (`p_conc`, `p_reinf`/`p_cfrp`); `volumes()` returns `cost_per_m2`; icc_app CNode exposes them as CFields |
| Default unit costs | `p_conc = 150 €/m³` (cast + formwork), `p_reinf = 1.20 €/kg` (rebar), `p_cfrp = 100 €/kg` (CFRP textile/bar) |
