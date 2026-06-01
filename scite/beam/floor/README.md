# `scite.beam.floor` — Floor System Analysis Module

Pure-Python module for one-way floor system structural assessment, GWP, and cost
analysis. No CFrame or widget framework dependency; all classes are plain
dataclasses usable directly in notebooks and scripts.

---

## Module architecture

```
scite.beam.floor
│
├── section_rc.py      ← cross-section containers (RC, steel)
├── section_crc.py     ← cross-section containers (CRC, CFRP)
│        │
│        ▼
├── floor_analysis.py  ← BeamDeflectionAnalysis wrappers + EC2 b_eff
│        │
│        ▼
├── load_model.py      ← EN 1990 load combinations
├── floor_system_base.py  ← abstract base class (assess / volumes)
│        │
│        ├── flat_slab.py     ← FlatSlab (SRC) · CRCFlatSlab
│        └── ribbed_slab.py   ← SRCRibbedSlab · CRCRibbedSlab
│
└── __init__.py        ← public API
```

---

## File roles and composition

### `section_rc.py` — `FloorSectionRC`, `FloorSectionRCRib`

Lightweight dataclasses that hold the **geometric and material parameters** of a
rectangular or T-shaped reinforced-concrete section and can assemble a
`scite.cs_design.CrossSection` at arbitrary material safety levels.

```
FloorSectionRC(b, h, f_ck, f_yk, A_s, z_s)
  .build_cs(gamma_c, gamma_s)  →  CrossSection   (SLS: γ=1, ULS: γ=EC2)

FloorSectionRCRib(b_w, h_w, b_f, h_f, …)        (T-section for ribbed slabs)
```

### `section_crc.py` — `FloorSectionCRC`, `FloorSectionCRCRib`

Same responsibility as `section_rc.py` but for **CFRP reinforcement**.
Uses `scite.matmod.carbon_reinforcement.CarbonReinforcement` instead of
`SteelReinforcement`.

```
FloorSectionCRC(b, h, f_ck, A_s, z_s, E_f, f_fk)
  .build_cs(gamma_c, gamma_f)  →  CrossSection

FloorSectionCRCRib(b_w, h_w, b_f, h_f, …)
```

### `floor_analysis.py` — `FloorAnalysis`, `FloorAnalysisPair`, `ec2_beff_rib`

**Central assembly layer.** Wraps `scite.beam.bending.BeamDeflectionAnalysis`
(which performs numerical load–deflection integration) and adds the
tributary-width conversion from line load $q$ [kN/m] to surface pressure
$p$ [kN/m²].

`FloorAnalysisPair` holds one SLS instance and one ULS instance and exposes
four **factory methods** that internally create the appropriate section objects:

| Method | Section type | Reinforcement |
|---|---|---|
| `.for_rc(b, h, …, f_yk)` | rectangular | steel |
| `.for_rc_rib(b_w, h_w, b_f, h_f, …, f_yk)` | T-section | steel |
| `.for_crc(b, h, …, E_f, f_fk)` | rectangular | CFRP |
| `.for_crc_rib(b_w, h_w, b_f, h_f, …, E_f, f_fk)` | T-section | CFRP |

`ec2_beff_rib(b_w, L_bay, L_rib, l0_factor)` implements EC2 §5.3.2.1
effective flange width; called automatically in ribbed slab `__post_init__`.

### `load_model.py` — `LoadModel`

EN 1990 surface load combination model. Holds the characteristic loads and
partial factors; provides:

```python
LoadModel(q_k=5.0, delta_g_k=1.5)
  .surface_loads(g_k)   →  dict  # p_Ed_qp, p_Ed_u, …
  .beam_loads(g_k, w)   →  dict  # adds line-load equivalents
  .plot_breakdown(ax, g_k)
```

`g_k` (structural self-weight) is supplied at call time rather than stored in
`LoadModel` so that the same model instance can be reused across systems with
different self-weights.

### `floor_system_base.py` — `FloorSystemBase` (ABC)

Abstract base class shared by all four floor system dataclasses.
Provides **no fields** — only shared behaviour via three abstract hooks:

| Hook | Returns | Purpose |
|---|---|---|
| `g_k` (property) | `float` | structural self-weight [kN/m²] |
| `_beam_elements()` | `list[(FloorAnalysisPair, w_trib_m, label)]` | elements to assess |
| `volumes()` | `dict` | material volumes, GWP, cost |

Concrete methods derived from those hooks:

```python
system.assess(lm)            →  dict[label, {p_R_sls, p_R_uls, eta_SLS, eta_ULS}]
system.print_assessment(lm)  →  (console table)
```

### `flat_slab.py` — `FlatSlab`, `CRCFlatSlab`

Concrete `FloorSystemBase` dataclasses for **solid flat slab strips** (1 m wide).
`__post_init__` constructs a `FloorAnalysisPair` via the appropriate factory method.

Also defines the **module-level material constants** re-used across the package:

```python
_RHO_CONCRETE_KN = 25.0    # kN/m³
_RHO_STEEL_KG    = 7850.0  # kg/m³
_RHO_CFRP_KG     = 1600.0  # kg/m³
_E_CONC_CO2      = 0.17    # kgCO₂/kg  (concrete)
_E_STEEL_CO2     = 1.50    # kgCO₂/kg  (steel)
_E_CFRP_CO2      = 19.0    # kgCO₂/kg  (CFRP, icc_app default)
_P_CONC          = 150.0   # €/m³       (concrete incl. formwork)
_P_REINF         = 1.20    # €/kg       (reinforcing steel)
_P_CFRP          = 100.0   # €/kg       (CFRP)
```

The shared plotting helper `_plot_pw_demands(ax, beam_pair, …)` is also defined
here and imported by `ribbed_slab.py`.

### `ribbed_slab.py` — `SRCRibbedSlab`, `CRCRibbedSlab`

Concrete `FloorSystemBase` dataclasses for **one-way ribbed slabs** (T-section
rib + bay slab strip). `__post_init__` computes EC2 effective flange width and
constructs two `FloorAnalysisPair` instances — one for the rib, one for the bay
slab. The CFRP variant uses `for_crc` / `for_crc_rib` for both elements.

Material constants and `_plot_pw_demands` are **imported from `flat_slab.py`**
to avoid duplication.

`_beam_elements()` returns two entries:

```python
[(bay_beam, 1.0, 'Bay slab'), (rib_beam, s_m, 'Rib')]   # SRC
[(bay_beam, 1.0, 'Bay slab'), (rib_beam, s_m, 'CRC rib')]  # CRC
```

---

## Data flow (assessment path)

```
User code
  │
  ├─ LoadModel(q_k, delta_g_k)              # demand
  │
  └─ FlatSlab(h, A_s, z_s, L, …)           # or CRCFlatSlab / SRCRibbedSlab / CRCRibbedSlab
       │  __post_init__
       │    └─ FloorAnalysisPair.for_rc(…)  # builds FloorSectionRC → CrossSection
       │         ├─ .sls : FloorAnalysis    #   BeamDeflectionAnalysis (mean strengths)
       │         └─ .uls : FloorAnalysis    #   BeamDeflectionAnalysis (design strengths)
       │
       ├─ .g_k                              # self-weight [kN/m²]
       ├─ .assess(lm)                       # LoadModel.surface_loads → utilisation ratios
       ├─ .volumes()                        # V_c, V_s/V_f, GWP/m², cost/m²
       └─ .plot_floor_assessment(axes, lm)  # p–w capacity/demand plot
```

---

## Key design decisions

- **All lengths in mm** throughout; conversion to m happens internally in
  `volumes()` and `floor_analysis.py`.
- **`volumes()` is span-independent** at fixed geometry: per-m² quantities
  normalise out the span. A meaningful *span sweep* requires an inverse design
  step (find minimum reinforcement satisfying SLS + ULS for each L).
- Material constants are **model fields with module-level defaults**, so any
  instance can override `e_cfrp`, `p_cfrp`, etc. without touching the module.
- `FloorAnalysisPair` is **constructed fresh** in `__post_init__`; it is not a
  mutable field. Changing a geometry field requires creating a new instance.
