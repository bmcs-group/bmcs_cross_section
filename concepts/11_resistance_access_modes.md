# Concept: Resistance Access Modes — Design, Characteristic, Mean

*Scite codebase concepts — relates to `EC2ParabolaRectangle`, `EC2Concrete`,
`SteelReinforcement`, `CrossSection`, `FloorSectionRC`, `FloorAnalysisPair`,
`BeamDeflectionAnalysis`, `ContinuousBeamAnalysis`*

---

## 1. Overview

The M-κ → beam → continuous-beam analysis chain is fully orthogonal to the
choice of material strength level.  Because each `CrossSection` holds concrete
and steel model instances, and both models expose their strength through their
`get_sig(eps)` call, changing the strength level requires only substituting
different model instances at construction time.  The solver stack above
(`MKappaAnalysis`, `BeamDeflectionAnalysis`, `ContinuousBeamAnalysis`) does
not see the change — it always calls `get_sig`.

Three modes are recognised throughout the codebase:

| Mode | Concrete peak stress | Steel peak stress | When used |
|------|---------------------|-------------------|-----------|
| **Design** (`ULS`) | $f_{cd} = \alpha_{cc} f_{ck} / \gamma_c$ | $f_{yd} = f_{yk} / \gamma_s$ | Ultimate limit state capacity |
| **Characteristic** | $f_{ck}$ (γ_c = 1, α_cc = 1) | $f_{yk}$ (γ_s = 1) | Code-level SLS checks |
| **Mean** | $f_{cm} = f_{ck} + 8$ (Sargin shape) | ≈ $f_{yk}$ (γ_s ≈ 1) | Realistic stiffness; nonlinear deflection |

---

## 2. Material Models and Their Mode Parameters

### 2.1 Concrete: `EC2ParabolaRectangle` (ULS/characteristic)

The parabola-rectangle model is parameterised by three partial-safety scalars:

```python
EC2ParabolaRectangle(f_ck=30.0, alpha_cc=0.85, gamma_c=1.5)
```

| Parameter | Design | Characteristic | Mean |
|-----------|--------|----------------|------|
| `alpha_cc` | 0.85 | 1.0 | 1.0 |
| `gamma_c` | 1.50 | 1.0 | 1.0 |
| Peak stress used | `f_cd = alpha_cc * f_ck / gamma_c` | `f_ck` | — (not used for mean) |

The strain limits ($\varepsilon_{c2}$, $\varepsilon_{cu2}$) are derived from
`f_ck` via EC2 3.1.7 and are the same across modes.

The model also exposes `f_cm = f_ck + 8` as a `cached_property` but does not
use it internally — the constitutive law is always expressed through `f_cd`.

### 2.2 Concrete: `EC2Concrete` (mean — Sargin parabola)

The Sargin-type parabola peaks at $f_{cm}$ and has a descending branch beyond
$\varepsilon_{c1}$:

```python
EC2Concrete(f_ck=30.0, factor=1.0)
```

| Parameter | Mean use | Design-like use |
|-----------|----------|-----------------|
| `f_ck` | input (derives f_cm = f_ck + 8) | same |
| `factor` | 1.0 | 0.85/1.5 = 0.567 |
| Peak stress | `factor * f_cm` | `factor * f_cm` |

All strain parameters ($\varepsilon_{c1}$, $\varepsilon_{cu1}$, $E_{cm}$,
$f_{ctm}$) are derived from `f_cm` via EC2 Table 3.1 formulae, so they
automatically reflect mean material properties.  Setting `factor = 1.0` gives
the pure mean response.

**Summary: for mean concrete → use `EC2Concrete(f_ck, factor=1.0)`.**  
**For design concrete → use `EC2ParabolaRectangle(f_ck, alpha_cc=0.85, gamma_c=1.5)`.**

### 2.3 Steel: `SteelReinforcement`

```python
SteelReinforcement(f_yk=500.0, f_tk=540.0, gamma_s=1.15, eps_ud=0.05)
```

| Mode | `gamma_s` | Peak stress | Usage |
|------|-----------|-------------|-------|
| Design | 1.15 | `f_yd = f_yk / 1.15` | ULS |
| Characteristic | 1.00 | `f_yk` | SLS, characteristic |
| Mean | 1.00 (+ mean f_yk) | `f_yk` (= f_ym in tests) | Realistic |

For the purposes of most structural analyses the steel mean strength ($f_{ym}
\approx 1.1 f_{yk}$) is not used — the characteristic $f_{yk}$ with $\gamma_s =
1.0$ is the correct SLS value.  The `create_steel(grade, gamma_s)` convenience
function accepts `gamma_s` directly:

```python
create_steel('B500B', gamma_s=1.0)   # characteristic / SLS
create_steel('B500B', gamma_s=1.15)  # design / ULS (default)
```

---

## 3. CrossSection Construction at Different Modes

`CrossSection` is **immutable once built** (Pydantic model with `cached_property`
on `MKappaAnalysis`).  Each mode therefore requires a separate `CrossSection`
instance built with the appropriate material instances.

The factory method `FloorSectionRC.build_cs(gamma_c, gamma_s, alpha_cc)` already
encapsulates this:

```python
sec = FloorSectionRC(b=300, h=700, f_ck=30, f_yk=500, A_s=1257, z_s=50)

# Design (ULS)
cs_uls  = sec.build_cs(gamma_c=1.5, gamma_s=1.15, alpha_cc=0.85)

# Characteristic (code SLS)
cs_char = sec.build_cs(gamma_c=1.0, gamma_s=1.0,  alpha_cc=1.0)

# Mean — needs EC2Concrete instead; no factory yet (see §6)
from scite.matmod.ec2_concrete import EC2Concrete
cs_mean = CrossSection(
    shape   = RectangularShape(b=300, h=700),
    concrete = EC2Concrete(f_ck=30, factor=1.0),
    reinforcement = ReinforcementLayout(layers=[
        ReinforcementLayer(z=50, A_s=1257,
                           material=create_steel('B500B', gamma_s=1.0))
    ]),
)
```

---

## 4. Propagation Through the Analysis Chain

The mode choice propagates upward through the chain without any code change in
the upper layers:

```
EC2ParabolaRectangle / EC2Concrete / SteelReinforcement
        │  get_sig(eps)
        ▼
  CrossSection.get_N_M(kappa, eps_top)
        │
        ▼
  MKappaAnalysis.solve()          →  M-κ table
        │
        ▼
  BeamDeflectionAnalysis          →  F-w curve, M_R, κ(x, F)
        │
        ▼
  ContinuousBeamAnalysis          →  sweep, q_hog_u, δ_M
```

**Each level in the chain is a pure consumer of the level below.**
Swapping `gamma_c` changes `f_cd`, which changes `get_sig`, which changes the
M-κ table, which changes `M_R` and `F_R`, which changes the F-w curve and the
sweep — no other code path is touched.

---

## 5. SLS and ULS Pairs — Existing Pattern

The `FloorAnalysisPair` class provides the established pattern for paired SLS/ULS
analyses:

```python
pair = FloorAnalysisPair.for_rc(
    b=300, h=700, f_ck=30, A_s=1257, z_s=50, f_yk=500,
    L_mm=6000,
    gamma_c=1.5, gamma_s=1.15, alpha_cc=0.85,  # ULS factors
)

# pair.sls  →  FloorAnalysis with cs built at gamma_c=1.0, gamma_s=1.0
# pair.uls  →  FloorAnalysis with cs built at gamma_c=1.5, gamma_s=1.15
```

Internally, `for_rc()` calls `FloorSectionRC.build_cs` twice:
```python
cs_sls = sec.build_cs(gamma_c=1.0, gamma_s=1.0, alpha_cc=1.0)
cs_uls = sec.build_cs(gamma_c=gamma_c, gamma_s=gamma_s, alpha_cc=alpha_cc)
```

The same pattern exists for `for_crc()` (carbon reinforcement) and
`for_rc_rib()` (T-section rib).  For SLS the convention is to use the
parabola-rectangle model with γ = 1.0 (not the Sargin mean model), which is
conservative and consistent with code practice.

---

## 6. Missing: Mode Control for Continuous Beams

`ContinuousBeamAnalysis` takes two `BeamDeflectionAnalysis` objects and is
therefore already capable of running at any mode — but there is no convenience
factory analogous to `FloorAnalysisPair` for continuous beams.

Currently, to run a characteristic or mean sweep, the user must manually
construct two `BeamDeflectionAnalysis` instances with appropriate cross-sections
and pass them to `ContinuousBeamAnalysis`:

```python
# Manual mode switching — works but verbose
bda_char = BeamDeflectionAnalysis(cs=cs_char, L=6000, load_type='dist', solve_mode='both')
bda_uls  = BeamDeflectionAnalysis(cs=cs_uls,  L=6000, load_type='dist', solve_mode='both')

cba_char = ContinuousBeamAnalysis(span_left=bda_char, span_right=bda_char, q=1.0)
cba_uls  = ContinuousBeamAnalysis(span_left=bda_uls,  span_right=bda_uls,  q=1.0)
```

### Proposed: `ContinuousBeamAnalysisPair`

A lightweight factory class (dataclass, no Pydantic) analogous to
`FloorAnalysisPair`:

```python
@dataclass
class ContinuousBeamAnalysisPair:
    """Design / characteristic / mean triple for a two-span RC continuous beam."""

    design:         ContinuousBeamAnalysis   # γ_c = 1.5, γ_s = 1.15
    characteristic: ContinuousBeamAnalysis   # γ_c = 1.0, γ_s = 1.0
    mean:           ContinuousBeamAnalysis   # EC2Concrete (f_cm), γ_s = 1.0

    @classmethod
    def for_rc(
        cls,
        b: float, h: float,
        A_s_bot: float, z_s_bot: float,
        A_s_top: float, z_s_top: float,
        f_ck: float, f_yk: float,
        L_a: float, L_b: float,
        gamma_c: float = 1.5, gamma_s: float = 1.15, alpha_cc: float = 0.85,
        n_kappa: int = 150, n_load_steps: int = 41,
    ) -> "ContinuousBeamAnalysisPair":
        ...
```

Each arm builds its own `CrossSection` (using the appropriate model and γ
values), wraps it in a `BeamDeflectionAnalysis` with `solve_mode='both'`
(required for the hogging branch), and passes the pair to
`ContinuousBeamAnalysis`.

---

## 7. Naming Convention and EC Correspondence

| scite mode | γ_c | γ_s | α_cc | EC2 context |
|-----------|-----|-----|------|-------------|
| `design` | 1.50 | 1.15 | 0.85 | ULS ultimate capacity, §6.1 |
| `characteristic` | 1.00 | 1.00 | 1.00 | SLS code check, §7.4.3 |
| `mean` | 1.00 (EC2Concrete) | 1.00 | — | Deflection prediction, §7.4.3 formula |

**Note on SLS convention in floor analyses:**
The `FloorAnalysisPair` uses `EC2ParabolaRectangle` with γ = 1.0 (not
`EC2Concrete`) for the SLS arm.  This is a deliberate choice: the
parabola-rectangle shape is slightly more conservative and keeps the
two arms comparable in shape (both cut off at `eps_cu2`).  For stiffness-critical
comparisons (deflection prediction against measurement) the `EC2Concrete` Sargin
model with `factor=1.0` is more appropriate.

---

## 8. Summary: How to Access Each Mode

```python
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.matmod.ec2_concrete            import EC2Concrete
from scite.matmod.steel_reinforcement     import create_steel

# ── Design (ULS) ──────────────────────────────────────────────────────────────
concrete_d = EC2ParabolaRectangle(f_ck=30, alpha_cc=0.85, gamma_c=1.5)
steel_d    = create_steel('B500B', gamma_s=1.15)

# ── Characteristic (code SLS) ─────────────────────────────────────────────────
concrete_k = EC2ParabolaRectangle(f_ck=30, alpha_cc=1.0,  gamma_c=1.0)
steel_k    = create_steel('B500B', gamma_s=1.0)

# ── Mean (realistic prediction) ───────────────────────────────────────────────
concrete_m = EC2Concrete(f_ck=30, factor=1.0)          # peak at f_cm = 38 MPa
steel_m    = create_steel('B500B', gamma_s=1.0)         # f_yk; f_ym not modelled

# ── CrossSection assembly (same for all three) ────────────────────────────────
# Replace concrete_d / steel_d with the desired mode variants
cs = CrossSection(
    shape         = RectangularShape(b=b, h=h),
    concrete      = concrete_d,   # ← swap here
    reinforcement = ReinforcementLayout(layers=[
        ReinforcementLayer(z=z_s_bot, A_s=A_s_bot, material=steel_d),  # ← and here
        ReinforcementLayer(z=z_s_top, A_s=A_s_top, material=steel_d),
    ]),
)

# ── MKappaAnalysis → BeamDeflectionAnalysis → ContinuousBeamAnalysis ─────────
# all layers above are mode-agnostic; only the CrossSection differs
bda = BeamDeflectionAnalysis(cs=cs, L=6000, load_type='dist', solve_mode='both')
cba = ContinuousBeamAnalysis(span_left=bda, span_right=bda, q=1.0)
```

---

## 9. Relationship to Existing Code

| Component | Mode-aware? | How |
|-----------|-------------|-----|
| `EC2ParabolaRectangle` | Yes | `gamma_c`, `alpha_cc` parameters |
| `EC2Concrete` | Yes | `factor` parameter (= 1.0 for mean) |
| `SteelReinforcement` | Yes | `gamma_s` parameter |
| `FloorSectionRC.build_cs` | Yes | Passes `gamma_c`, `gamma_s`, `alpha_cc` |
| `FloorAnalysisPair.for_rc` | Yes | SLS + ULS arms built automatically |
| `FloorAnalysisPair.for_crc` | Yes | SLS + ULS arms for CRC |
| `BeamDeflectionAnalysis` | Transparent | Receives `CrossSection`; no mode logic |
| `MKappaAnalysis` | Transparent | Same |
| `ContinuousBeamAnalysis` | Transparent | Receives `BeamDeflectionAnalysis`; no mode logic |
| `ContinuousBeamAnalysisPair` | **Missing** | To be implemented (§6) |
