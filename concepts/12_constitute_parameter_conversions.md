# Concept: Constitutive Parameter Conversions — Characteristic → Mean Values

*Scite codebase concepts — relates to `SteelReinforcement`, `CarbonReinforcement`,
`ReinforcementComponent`, `SteelRebarComponent`, `TextileReinforcementComponent`,
`ContinuousBeamModes`, `EC2Concrete`*

---

## 1. Motivation

For nonlinear analysis (moment redistribution, deflection prediction) the EC2
§5.7(NA.10) requires **mean material values** rather than characteristic or
design values.  The conversion from the characteristic (5th-percentile) value
to the mean value is product-specific — it depends on the material type, the
manufacturing process, and the statistical properties of the product.

The current codebase already has a three-level analysis mode (design /
characteristic / mean) for concrete (concept `11_resistance_access_modes.md`),
but the **reinforcement side only covers γ_s** — it does not yet implement the
characteristic → mean conversion for steel or FRP products.

---

## 2. Steel Reinforcement: EC2 §5.7(NA.10) Formula

### 2.1 The norm reference

German National Annex to EC2, §5.7(NA.10), equations (NA.5.12.2)–(NA.5.12.7):

$$f_{yR} = 1.1\, f_{yk} \tag{NA.5.12.2}$$

$$f_{tR} = 1.08\, f_{yR} \quad \text{(B500B)} \tag{NA.5.12.3}$$

$$f_{tR} = 1.05\, f_{yR} \quad \text{(B500A)} \tag{NA.5.12.4}$$

Cross-referenced from §3.2.7(NA.5), PDF page 43 of Fingerloos/Hegger/Zilch
*Kommentierte Fassung Eurocode 2*.

The subscript R denotes the *rechnerischer Mittelwert* (computational mean).
These are **not** statistical means estimated from test data — they are
**code-prescribed approximations** intended for nonlinear analysis.

### 2.2 Is the mean curve just a vertical shift?

No. The `SteelReinforcement` constitutive law has the following skeleton:

```
σ  ▲      k·f_yd ─────────────── ← f_td (design) or f_tR (mean)
   │      /
   │     /  hardening slope (f_td - f_yd) / (eps_ud - eps_yd)
   │    /
   │   ────── ← f_yd (design) or f_yR (mean)
   │  /  elastic slope E_s = 200 000 MPa (unchanged)
   │ /
───┼───────────────────────────────────►  ε
   0    eps_yd       eps_ud
```

Going from characteristic to mean (B500B):

| Quantity | Characteristic | Mean (B500B) |
|----------|---------------|--------------|
| Yield strength | `f_yk = 500` | `f_yR = 1.1 × 500 = 550` |
| Tensile strength | `f_tk = 540` | `f_tR = 1.08 × 550 = 594` |
| Ductility ratio `k = f_t/f_y` | `540/500 = 1.08` | `594/550 = 1.08` ← preserved |
| Elastic modulus `E_s` | 200 000 MPa | 200 000 MPa ← unchanged |
| Yield strain | `eps_yd = 500/200000 = 0.0025` | `eps_yR = 550/200000 = 0.00275` |
| Ultimate strain `eps_ud` | 0.025 | 0.025 ← unchanged (NA gives no formula for mean strain) |
| Hardening slope | `(540−500)/(0.025−0.0025) = 1778 MPa` | `(594−550)/(0.025−0.00275) = 1977 MPa` |

**Key observations:**

1. The ductility ratio `k = f_tk/f_yk` is grade-specific and preserved under
   the mean conversion (`k = 1.08` for B500B, `k = 1.05` for B500A).
2. The yield strain `eps_yd` increases proportionally to the strength, since
   `E_s` is unchanged.  This makes the hardening branch slightly steeper.
3. `eps_ud` is **not** scaled — the NA formula gives mean strength only.  The
   design strain limit 0.025 is a lower bound; for nonlinear analysis with mean
   values, keeping `eps_ud` unchanged is conservative.
4. Consequently, the mean curve is **not** the characteristic curve shifted
   upward by `0.1 f_yk`.  It is a fully re-parameterised curve with higher
   yield strain and steeper post-yield hardening, while sharing the same `E_s`
   and `eps_ud`.

### 2.3 Implementation in `SteelReinforcement`

The cleanest way to instantiate a mean steel model is:

```python
# B500B mean values per EC2 §5.7(NA.10)
f_yk_char = 500.0
k_B500B   = 1.08          # f_tk / f_yk — grade ductility ratio
phi_y     = 1.1           # f_yR / f_yk
phi_t     = k_B500B * phi_y   # f_tR / f_yk = 1.188

SteelReinforcement(
    f_yk    = phi_y * f_yk_char,   # 550 MPa
    f_tk    = phi_t * f_yk_char,   # 594 MPa
    gamma_s = 1.0,                  # no safety factor for mean
    eps_ud  = 0.025,                # unchanged
)
```

No changes to `SteelReinforcement` itself are needed — the conversion factors
live in the caller (product catalog or factory method).

---

## 3. Carbon / FRP Reinforcement: No Standardised Formula

`CarbonReinforcement` uses a `factor` parameter that multiplies `f_t`:

```python
CarbonReinforcement(E=165000, f_t=2000, factor=1.0)   # factor=1.0 → mean
CarbonReinforcement(E=165000, f_t=2000, factor=1/1.25) # factor<1 → design
```

The `factor` approach treats `f_t` as the **mean** value and scales it down
for design.  This is the inverse convention from steel (where `f_yk` is the
characteristic value and safety factor scales down, or mean factor scales up).

For FRP materials there is **no EC2 formula** analogous to §5.7(NA.10).
Mean values must come from:
- Product approval documents (ETA, DIBt approval)
- Manufacturer test data
- Material standards (ISIS, ACI 440, CNR-DT 203)

Typical COV for carbon FRP tensile strength ≈ 5–8 % (much lower than steel ≈ 8–12 %),
so the mean-to-characteristic ratio for FRP is often smaller than 1.1:

$$f_{t,\text{mean}} \approx f_{tk} \cdot \frac{1}{1 - k_n \cdot \text{COV}}$$

where `k_n ≈ 1.645` for the 5th percentile.  For COV = 0.06:
`f_t_mean ≈ f_tk / (1 - 1.645 × 0.06) ≈ 1.11 f_tk` — similar ratio to steel
but derived differently and product-specific.

---

## 4. Current State of the Catalog Layer

`ReinforcementComponent` in `cs_components/component_base.py` already has the
hook:

```python
def get_mean_stress_strain(self, eps) -> Optional[ndarray]:
    """Returns None by default — subclasses override if mean values exist."""
    return None
```

`ConcreteComponent` correctly implements it by scaling the design curve by
`f_cm / f_cd`.  But for reinforcement:

| Class | `get_mean_stress_strain` | Status |
|-------|--------------------------|--------|
| `SteelRebarComponent` | not overridden | **Missing** |
| `CarbonBarComponent` | not overridden | **Missing** |
| `TextileReinforcementComponent` | not overridden | **Missing** |
| `ConcreteComponent` | scales by `f_cm / f_cd` | Implemented ✓ |

---

## 5. Proposed Polymorphic Design

### 5.1 Conversion descriptor in each product class

Add a `mean_conversion` property that returns a lightweight dataclass:

```python
@dataclass
class MeanConversion:
    """Characteristic → mean conversion for one reinforcement product."""
    f_factor:   float = 1.0   # f_mean  = f_factor  * f_characteristic
    ft_factor:  float | None = None  # if None → same as f_factor
    E_factor:   float = 1.0   # E_mean  = E_factor  * E_characteristic
    eps_factor: float = 1.0   # eps_u_mean = eps_factor * eps_u_characteristic
    source:     str   = ''    # norm / document reference
```

Override `get_mean_stress_strain` in the base class to consume it:

```python
# in ReinforcementComponent
def get_mean_stress_strain(self, eps):
    conv = self.mean_conversion()
    # rebuild a scaled matmod and evaluate
    ...
```

### 5.2 Per-product implementations

**`SteelRebarComponent` (B500B)**:

```python
def mean_conversion(self) -> MeanConversion:
    k  = self.matmod.f_tk / self.matmod.f_yk   # grade ductility ratio (1.08 B500B)
    return MeanConversion(
        f_factor  = 1.1,
        ft_factor = 1.1 * k,    # 1.188 for B500B, 1.155 for B500A
        E_factor  = 1.0,
        eps_factor = 1.0,
        source    = 'EC2 §5.7(NA.10), eqns (NA.5.12.2)–(NA.5.12.3)',
    )

def get_mean_stress_strain(self, eps):
    conv = self.mean_conversion()
    mat = SteelReinforcement(
        f_yk    = conv.f_factor   * self.matmod.f_yk,
        f_tk    = conv.ft_factor  * self.matmod.f_yk,
        gamma_s = 1.0,
        E_s     = self.matmod.E_s,
        eps_ud  = conv.eps_factor * self.matmod.eps_ud,
    )
    return mat.get_sig(eps)
```

**`CarbonBarComponent`** (no standard formula — uses `factor=1.0`):

```python
def mean_conversion(self) -> MeanConversion:
    return MeanConversion(
        f_factor  = 1.0,   # f_t is already a mean value in CarbonReinforcement
        E_factor  = 1.0,
        source    = 'CarbonReinforcement factor=1.0 = mean; no EC2 formula',
    )
```

**`TextileReinforcementComponent`** (product-specific, manufacturer approval):

```python
def mean_conversion(self) -> MeanConversion:
    return MeanConversion(
        f_factor  = getattr(self, 'mean_f_factor', 1.0),  # from product data
        E_factor  = 1.0,
        source    = 'ETA / manufacturer approval',
    )
```

### 5.3 Integration into `ContinuousBeamModes.for_rc()`

Once `SteelRebarComponent.get_mean_stress_strain()` is in place, the
`for_rc()` factory in `modes.py` can delegate to it instead of hardcoding
the `1.1 * f_yk` factor directly:

```python
# Current (hardcoded):
cs_mean = _cs(EC2Concrete(f_ck=f_ck, factor=1.0), gamma_s=1.0)
# → steel at f_yk, NOT at 1.1*f_yk

# Desired (via catalog):
rebar = SteelRebarComponent(grade='B500B', ...)
cs_mean = CrossSection(
    concrete = EC2Concrete(f_ck=f_ck, factor=1.0),
    reinforcement = ReinforcementLayout(layers=[
        AreaReinforcement(z=z_s_bot, A_s=A_s_bot, material=rebar.mean_matmod()),
        AreaReinforcement(z=z_s_top, A_s=A_s_top, material=rebar.mean_matmod()),
    ]),
)
```

A `mean_matmod()` convenience method on `SteelRebarComponent` returns a
`SteelReinforcement` instance built from the `MeanConversion` factors.

---

## 6. Quantitative Impact for B500B in the Continuous Beam

For the existing two-span beam (C30/37, B500B, `f_yk=500`, `f_tk=540`):

| Mode | `f_y` [MPa] | `f_t` [MPa] | `eps_y` [‰] | `eps_ud` [‰] | Source |
|------|------------|------------|-------------|-------------|--------|
| Design | 435 | 470 | 2.17 | 25.0 | EC2 design (`gamma_s=1.15`) |
| Characteristic | 500 | 540 | 2.50 | 25.0 | `gamma_s=1.0` |
| Mean (current `modes.py`) | 500 | 540 | 2.50 | 25.0 | `gamma_s=1.0` ← same as char. |
| Mean (§5.7 NA.10) | **550** | **594** | **2.75** | 25.0 | EC2 (NA) |

The current `ContinuousBeamModes.for_rc()` sets `gamma_s=1.0` for the mean
mode, which gives **characteristic** steel strength, not the NA.10 mean.  The
mean concrete is correctly modelled via `EC2Concrete(factor=1.0)` (Sargin
parabola at `f_cm = f_ck + 8 = 38 MPa`), but the steel uplift `f_yR = 1.1 f_yk`
is not yet applied.

Correcting this in `for_rc()`:

```python
cs_mean = _cs(
    concrete  = EC2Concrete(f_ck=f_ck, factor=1.0),
    gamma_s   = 1.0,
    f_yk_mean = 1.1 * f_yk,                      # 550 MPa
    f_tk_mean = k_ductility(grade) * 1.1 * f_yk,  # 594 MPa  B500B
)
```

Expected effect: `q_hog_u` for mean mode increases from ~119.8 → ~125–128 N/mm
(rough estimate; higher steel yield pushes up both `M_R,hog` and the compatible load).

---

## 7. Relationship to Existing Code

| Component | Current state | Required change |
|-----------|--------------|-----------------|
| `SteelReinforcement` | Takes `f_yk`, `f_tk`, `gamma_s` | No change needed; caller provides mean values |
| `create_steel(grade, gamma_s)` | No mean-value variant | Add `create_steel_mean(grade)` or extend |
| `SteelRebarComponent` | `get_mean_stress_strain` → None | Implement using NA.10 factors |
| `CarbonReinforcement` | `factor=1.0` already = mean | No change; clarify convention in docstring |
| `CarbonBarComponent` | `get_mean_stress_strain` → None | Implement as `factor=1.0` pass-through |
| `TextileReinforcementComponent` | `get_mean_stress_strain` → None | Expose `mean_f_factor` field |
| `ContinuousBeamModes.for_rc()` | Steel at characteristic level | Apply `f_yR = 1.1*f_yk`, `f_tR = k*f_yR` |
| `MeanConversion` dataclass | Missing | New in `cs_components/component_base.py` |

---

## 8. Summary

- The mean steel curve is **not** a vertical shift — it re-parameterises both
  yield and tensile strengths while preserving the grade ductility ratio `k`
  and keeping `E_s` and `eps_ud` unchanged.
- The conversion is material/grade-specific.  EC2 §5.7(NA.10) gives it for
  B500A and B500B; FRP materials require product-approval data.
- The catalog base class already has the `get_mean_stress_strain()` stub.
  Filling it in polymorphically in each product subclass, via a `MeanConversion`
  descriptor, is the correct OO design.
- The highest-priority concrete action is to apply `f_yR = 1.1 f_yk` in
  `ContinuousBeamModes.for_rc()`, so that the mean mode sweep reflects the
  full EC2(NA) mean material response.
