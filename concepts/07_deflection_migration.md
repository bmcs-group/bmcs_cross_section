# Migration: `DeflectionProfile` → `BeamDeflectionAnalysis` + scite-level `FloorAnalysis`

**Status**: Proposal — May 2026  
**Scope**: scite + icc_apps

---

## 1. Problem Statement

Two parallel implementations exist for the same numerical kernel (κ integration):

| | `DeflectionProfile` | `BeamDeflectionAnalysis` |
|---|---|---|
| Framework | `traits` / `bmcs_utils` (legacy) | Pydantic `BMCSModel` (current) |
| Input | `BeamDesign` + legacy `MKappa` | `CrossSection` directly |
| State | Stateful (`system_.F = -F`) | Functional (cached properties) |
| SLS/ULS | `_build_dp_pair()` bridge in icc_apps | Not yet present |
| Experimental overlay | `add_fw_exp()` | Not yet present |
| Shrinkage κ | `get_kappa_shrinkage()` (hardcoded params) | Not yet present |
| Shear check (CRC) | Empirical formula, carbon only | Not present |
| Interactive widgets | `ipw_view`, `update_plot()` | Via CNode wrapper in icc_apps |

The `icc_apps` models (`nonlinear_beam.py`, `floor_system.py`) still delegate
entirely to `DeflectionProfile` via a manual translation layer that is complex,
brittle, and requires `traits` at runtime.

The goal is to:
1. Complete `BeamDeflectionAnalysis` with the missing functionality that matters.
2. Create a scite-level `FloorAnalysis` / `FloorAnalysisPair` Pydantic model
   that encodes the SLS/ULS analysis logic currently buried in icc_apps.
3. Migrate `icc_apps` CNode wrappers to use the new scite models directly.
4. Retire `DeflectionProfile` once all callers have been migrated.

---

## 2. Gap Analysis

### 2.1 Already present in `BeamDeflectionAnalysis`
- Dense load stepping near cracking: 40% of steps in 0–20% of F_R (same as `DeflectionProfile._get_F_arr()`).
- `E_cm`, `I_g`, elastic reference curves (`plot_Fw_vs_elastic()`).
- Structural convention plots (y-axis inverted, downward positive).
- `plot_summary()` four-panel overview.

### 2.2 Missing functionality — priority-ranked

| # | Feature | Priority | Notes |
|---|---|---|---|
| A | Experimental F-w overlay (`add_exp_data`, `plot_exp_Fw`) | **High** | Needed for validation notebooks and beam validation app |
| B | SLS/ULS analysis pair (two BDAs from same geometry, different safety factors) | **High** | Currently only in `FloorSystem._build_dp_pair()` in icc_apps |
| C | Surface-load → pressure conversion (`F [N/mm] → p [kN/m²]` for tributary widths) | **High** | Needed for all ribbed floor panels |
| D | Shrinkage curvature `get_kappa_shrinkage()` (EC2 §3.1.4) | **Medium** | Params currently hardcoded in `DeflectionProfile`; should become model fields |
| E | CRC empirical shear capacity | **Low** | Carbon-rectangle only; keep as separate utility, not in BDA |

### 2.3 Shrinkage note
The current `get_kappa_shrinkage()` in `DeflectionProfile` has hardcoded section
dimensions (1000×300 mm) and concrete props.  It needs to be rewritten as a proper
parametric method using the cross-section geometry and concrete model already
available in `BeamDeflectionAnalysis.cs`.

---

## 3. New scite Module Structure

```
scite/beam/
    bending/
        beam_deflection.py      ← extend (Items A, D above)
    floor/
        __init__.py
        section_rc.py           ← FloorSectionRC   (f_ck, f_yk, b, h, A_s, z_s)
        section_crc.py          ← FloorSectionCRC  (f_ck, E_f, f_fk, b, h, A_s, z_s)
        floor_analysis.py       ← FloorAnalysis, FloorAnalysisPair
        ribbed_slab.py          ← RibbedSlabGeometry (structural calc only)
```

### 3.1 `FloorSectionRC` / `FloorSectionCRC`

Pydantic `BMCSModel` holding the parametric description of a cross-section and
its material safety levels.  Provides factory methods for `CrossSection`:

```python
class FloorSectionRC(BMCSModel):
    b: float; h: float; f_ck: float; f_yk: float; A_s: float; z_s: float

    def build_cs(self, gamma_c: float = 1.0, gamma_s: float = 1.0) -> CrossSection:
        """Return CrossSection with EC2ParabolaRectangle + SteelReinforcement."""
        ...

class FloorSectionCRC(BMCSModel):
    b: float; h: float; f_ck: float; E_f: float; f_fk: float; A_s: float; z_s: float

    def build_cs(self, gamma_c: float = 1.0, gamma_f: float = 1.0) -> CrossSection:
        """Return CrossSection with EC2ParabolaRectangle + CarbonReinforcement."""
        ...
```

For SLS: call `build_cs(gamma_c=1.0, gamma_s=1.0)` (characteristic strengths,
`f_cm = f_ck + 8` passed via concrete model).
For ULS: call `build_cs(gamma_c=1.5, gamma_s=1.15)`.

### 3.2 `FloorAnalysis`

A thin wrapper that owns a `FloorSection*` and produces a `BeamDeflectionAnalysis`:

```python
class FloorAnalysis(BMCSModel):
    section: FloorSectionRC | FloorSectionCRC
    L: float               # span [mm]
    load_type: Literal['dist', '3pb'] = 'dist'
    gamma_c: float = 1.0   # concrete safety factor
    gamma_s: float = 1.0   # steel/CFRP safety factor
    n_load_steps: int = 31

    @cached_property
    def cs(self) -> CrossSection:
        return self.section.build_cs(gamma_c=self.gamma_c, gamma_s=self.gamma_s)

    @cached_property
    def bda(self) -> BeamDeflectionAnalysis:
        return BeamDeflectionAnalysis(cs=self.cs, L=self.L,
                                      load_type=self.load_type,
                                      n_load_steps=self.n_load_steps)

    def get_p_arr(self, w_trib_m: float) -> tuple[np.ndarray, np.ndarray]:
        """Convert F [N/mm] → p [kN/m²] for the given tributary width [m]."""
        F_arr, w_arr = self.bda.get_Fw()
        p_arr = F_arr / (w_trib_m * 1000.0)  # N/mm / (m * 1000) = kN/m²
        return p_arr, w_arr
```

### 3.3 `FloorAnalysisPair`

Holds SLS and ULS `FloorAnalysis` objects for the same section:

```python
class FloorAnalysisPair(BMCSModel):
    section: FloorSectionRC | FloorSectionCRC
    L: float
    load_type: Literal['dist', '3pb'] = 'dist'
    # SLS: characteristic (gamma=1.0)
    # ULS: gamma_c=1.5, gamma_s=1.15 (or gamma_f for CFRP)
    gamma_c: float = 1.5
    gamma_s: float = 1.15  # or gamma_f for CFRP

    @cached_property
    def sls(self) -> FloorAnalysis:
        return FloorAnalysis(section=self.section, L=self.L,
                             load_type=self.load_type,
                             gamma_c=1.0, gamma_s=1.0)

    @cached_property
    def uls(self) -> FloorAnalysis:
        return FloorAnalysis(section=self.section, L=self.L,
                             load_type=self.load_type,
                             gamma_c=self.gamma_c, gamma_s=self.gamma_s)

    def plot_Fw_pair(self, ax, surface_loads: dict,
                     w_trib_m: float = 1.0, title: str = '') -> None:
        """
        Replaces FloorSystem._draw_Fw_panel().
        Plots SLS + ULS capacity curves and demand lines on ax.
        surface_loads: dict with keys p_Ed_qp, p_Ed_u, L (mm).
        """
        ...
```

This completely replaces the four static methods in `FloorSystem`:
`_build_dp`, `_build_dp_pair`, `_build_dp_cfrp`, `_build_dp_pair_cfrp`.

### 3.4 `RibbedSlabGeometry`

Structural-calculation counterpart of `_RibGeometryBase` in icc_apps.
Contains only geometry parameters and T-section builders — **no Plotly, no CNode**:

```python
class RibbedSlabGeometry(BMCSModel):
    L_rib: float = 6000.0   # mm
    L_bay: float = 1200.0   # mm
    H_rib: float = 200.0    # mm
    B_rib: float = 200.0    # mm
    H_bay: float = 80.0     # mm

    @cached_property
    def h_total(self) -> float:
        return self.H_rib + self.H_bay

    def build_T_shape(self) -> TShape:
        return TShape(b_w=self.B_rib, h_w=self.H_rib,
                      b_f=self.L_bay, h_f=self.H_bay)

    def structural_self_weight(self, gamma_c_kNm3: float = 25.0) -> float:
        """g_k [kN/m²] from rib + slab volumes."""
        ...
```

The 3-D Plotly figure in `_RibGeometryBase` stays in `icc_apps` (it is pure UI).

---

## 4. Extension to `BeamDeflectionAnalysis`

### 4.1 Experimental data overlay (Item A)

```python
class BeamDeflectionAnalysis(BMCSModel):
    ...
    # Stored as list of (w_arr, F_arr) pairs so the model remains serialisable
    exp_data: list[tuple[list, list]] = Field(default_factory=list)

    def add_exp_Fw(self, w_arr: np.ndarray, F_arr: np.ndarray) -> None:
        self.exp_data.append((w_arr.tolist(), F_arr.tolist()))

    def plot_exp_Fw(self, ax: plt.Axes, color: str = 'gray',
                    label_prefix: str = 'exp') -> None:
        for i, (w, F) in enumerate(self.exp_data):
            ax.plot(w, np.array(F) * self._F_scale,
                    color=color, lw=1.5, linestyle=':', marker='o', ms=4,
                    label=f'{label_prefix} {i+1}' if len(self.exp_data) > 1
                    else label_prefix)
```

`plot_Fw()` should call `plot_exp_Fw()` automatically when `exp_data` is not empty.

### 4.2 Shrinkage curvature (Item D)

```python
@cached_property
def kappa_cs(self) -> float:
    """
    Shrinkage curvature [1/mm] per EC2 §3.1.4.
    Uses concrete model (f_ck, f_cm) and gross section geometry (I_g, S_g, A_g).
    Returns zero for CRC sections (no shrinkage correction needed).
    """
    ...
```

Calling `get_kappa_x(F, include_shrinkage=False)` by default keeps backward
compatibility; `include_shrinkage=True` adds the uniform `kappa_cs` offset.

---

## 5. Migration of `icc_apps`

### Phase 1 — Extend `BeamDeflectionAnalysis` (scite-side)
Add `exp_data` / `plot_exp_Fw()`.  No icc_apps changes yet.

### Phase 2 — Create `scite/beam/floor/` (scite-side)
Implement `FloorSectionRC`, `FloorSectionCRC`, `FloorAnalysis`, `FloorAnalysisPair`,
`RibbedSlabGeometry`.  Write verification notebooks.

### Phase 3 — Migrate `icc_apps/floor_system.py`
- Remove static methods `_build_dp`, `_build_dp_pair`, `_build_dp_cfrp`,
  `_build_dp_pair_cfrp`.
- Replace with calls to `FloorAnalysisPair`.
- `_draw_Fw_panel()` delegates to `FloorAnalysisPair.plot_Fw_pair()`.
- `FloorSystem` base class stays as `CNode` — it still owns `CField`s, UI layout,
  Plotly figures.  The structural calculation layer is now clean scite objects.

### Phase 4 — Migrate `icc_apps/nonlinear_beam.py`
- Replace `_build_dp()` with direct `BeamDeflectionAnalysis` construction from
  `_build_cs()`.
- `update_plot()` calls `bda.plot_summary()` or custom subplots directly.
- Remove all legacy trait imports (`EC2PlateauConcreteMatMod`, `ReinfLayer`,
  `BeamDesign`, `F_max_override` hack).
- Repeat for `nonlinear_beam_validation.py`.

### Phase 5 — Mark `DeflectionProfile` deprecated
- Add `DeprecationWarning` at import time.
- Keep the file but add a banner in its docstring.
- Retain only for `BeamSLSCurve` if that widget is still active; otherwise remove.

### Phase 6 — Remove `DeflectionProfile` (deferred)
Once no active code imports it, delete the file and the traits dependency
from `scite/beam/__init__.py`.

---

## 6. Scope boundary: what stays in `icc_apps`

| Concern | Stays in icc_apps | Moves to scite |
|---|---|---|
| `CField` UI parameters | Yes | — |
| Plotly 3-D geometry figure | Yes | — |
| Load table (`_LoadAndSelfWeightBase`) | Yes (CNode) | — |
| Surface load → line load conversion (`w_trib`) | No → `FloorAnalysisPair.get_p_arr()` | Yes |
| SLS/ULS cross-section construction | No → `FloorSectionRC.build_cs()` | Yes |
| F-w pair computation | No → `FloorAnalysisPair` | Yes |
| F-w pair plotting | No → `FloorAnalysisPair.plot_Fw_pair()` | Yes |
| Structural self-weight | No → `RibbedSlabGeometry.structural_self_weight()` | Yes |
| GWP summary bars | Yes (educational content) | — |
| `EducationalSpec` / theory markdown | Yes | — |

The guiding principle: **anything that can be computed from geometry + material params
without a UI** belongs in scite.  `icc_apps` provides only the CNode adapter (field
declarations, layout, educational specs).

---

## 7. Dependency graph after migration

```
scite/beam/floor/
    FloorSectionRC / FloorSectionCRC
         │  build_cs()
         ▼
    CrossSection  ──────────────────────────────────────────┐
         │                                                  │
    FloorAnalysis                                    FloorAnalysisPair
         │  bda                                            │ sls / uls
         ▼                                                  ▼
    BeamDeflectionAnalysis ←─────────────────────────────────┘
         │  mk
         ▼
    MKappaAnalysis
         │  cs
         ▼
    CrossSection

icc_apps/part01/models/
    SRCOneWaySlab (CNode)
         │  _build_pair_spec() → FloorAnalysisPair
         ▼
    FloorAnalysisPair.plot_Fw_pair(ax, surface_loads)

    NonlinearBeamModel (CNode)
         │  _build_cs() → CrossSection
         ▼
    BeamDeflectionAnalysis.plot_summary(...)
```

---

## 8. Open Questions

- **`get_kappa_shrinkage()` scope**: The current implementation is hardcoded for a
  1000×300 slab.  A proper parametric version requires a `phi` (creep coefficient)
  and `t` (age) field.  Add these to `BeamDeflectionAnalysis` as optional fields with
  sensible defaults, and skip the shrinkage term when `phi = 0`.

- **Cantilever / 4PB support**: `DeflectionProfile` has partial support for these via
  `BeamSystem` subclasses.  `BeamDeflectionAnalysis` currently handles only simply
  supported systems.  This can be addressed later by adding `beam_system` as a
  discriminated union field.

- **`BeamSLSCurve`**: Still imports `DeflectionProfile`.  Assess whether this widget is
  still used before deciding to migrate or remove it.
