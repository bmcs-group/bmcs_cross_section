# Continuous Beam Analysis via Two Simply Supported Spans

## 1 — Motivation

`BeamDeflectionAnalysis` currently solves a **single simply supported span** under
symmetric loading (3-point bending or uniform distributed load).  For reinforced and
carbon-fibre-reinforced concrete beams, the nonlinear M-κ relationship — cracking,
tension stiffening, CFRP linear-to-fracture — means that **internal force redistribution**
in a continuous beam cannot be captured by elastic methods alone.

This concept introduces a **two-span continuous beam** model that retains the
`BeamDeflectionAnalysis` integration engine but determines the unknown hogging moment at
the middle support **iteratively** through a rotation-compatibility condition.  The approach
accounts for asymmetric spans and asymmetric material behaviour, and directly demonstrates
cracking-induced moment redistribution.

---

## 2 — Structural model

### 2.1 Decomposition into two simply supported beams

A two-span beam with span lengths $L_a$ (left) and $L_b$ (right) is characterised by the
span ratio $S = L_b / L_a$.  The beam rests on three simple supports — two outer supports
and one interior (middle) support.

The solution decomposes the statically indeterminate structure into
**two independent simply supported beams** (SSBs):

- **Beam a (left span)** — local coordinate $x \in [0,\,L_a]$;
  simple support at $x = 0$ (left outer support), simple support at $x = L_a$ (interior
  support).
- **Beam b (right span)** — local coordinate $x \in [0,\,L_b]$;
  simple support at $x = 0$ (interior support), simple support at $x = L_b$ (right outer
  support).

The unknown **hogging moment** $M_\mathrm{hog} \geq 0$ acts at the interior support —
between $x = L_a$ of beam a and $x = 0$ of beam b.  In the sagging-positive convention it
enters the moment diagram as $-M_\mathrm{hog}$ (negative = hogging, tension at top).
Compatibility of rotation at the interior support is the closing condition.

### 2.2 Moment distribution by superposition

Using the sagging-positive convention:

> **Sign reminder:** the mid-span (field) moment is **positive** (sagging, tension at
> bottom); the moment at the interior support is **negative** (hogging, tension at top).
> $M_\mathrm{hog}$ is defined as the *magnitude* of the support moment, so it enters
> all formulas with a leading minus sign $-M_\mathrm{hog}$.

Each span's moment is the superposition of the UDL parabola and a linear end-moment
diagram (the standard SSB result for a concentrated moment at one end):

**Beam a (left span)** — hogging $-M_\mathrm{hog}$ at its right end $x = L_a$:

$$
M_a(x;\,M_\mathrm{hog})
  = \underbrace{\frac{q}{2}\,x\,(L_a - x)}_{\text{parabola (sagging)}}
    \;-\; M_\mathrm{hog}\,\frac{x}{L_a}
$$

Checks: $M_a(0) = 0$, $M_a(L_a) = -M_\mathrm{hog}$ ✓

**Beam b (right span)** — hogging $-M_\mathrm{hog}$ at its left end $x = 0$:

$$
M_b(x;\,M_\mathrm{hog})
  = \underbrace{\frac{q}{2}\,x\,(L_b - x)}_{\text{parabola (sagging)}}
    \;-\; M_\mathrm{hog}\!\left(1 - \frac{x}{L_b}\right)
$$

Checks: $M_b(0) = -M_\mathrm{hog}$ ✓, $M_b(L_b) = 0$ ✓

Setting $M_\mathrm{hog} = 0$ recovers the standard SSB diagram for each span.

Reaction check (beam a): $R_0 = qL_a/2 - M_\mathrm{hog}/L_a$,
$R_{L_a} = qL_a/2 + M_\mathrm{hog}/L_a$.

---

## 3 — Rotation compatibility

### 3.1 Integration boundary conditions

`BeamDeflectionAnalysis.get_phi_x(F)` now enforces the **SSB displacement BC**
$w(0) = w(L) = 0$.  This replaced the earlier symmetry BC ($\varphi(L/2) = 0$) which was
valid only for symmetric loading.  The displacement BC is backward-compatible: for
symmetric $M(x)$ the integration constant derived from both approaches is identical.

Starting from $\kappa(x) = \bar\kappa(M(x))$ (the inverted M-κ curve), integrate once:

$$
\varphi_\mathrm{int}(x) = \int_0^x \kappa(x')\,\mathrm{d}x'
$$

Enforce $w(L) = \int_0^L \varphi(x)\,\mathrm{d}x = 0$:

$$
\int_0^L \bigl[\varphi_\mathrm{int}(x) + C_1\bigr]\,\mathrm{d}x = 0
\quad\Longrightarrow\quad
C_1 = -\frac{1}{L}\int_0^L \varphi_\mathrm{int}(x')\,\mathrm{d}x'
$$

The correct rotation profile is therefore:

$$
\varphi(x) = \varphi_\mathrm{int}(x)
             - \frac{1}{L}\int_0^L \varphi_\mathrm{int}(x')\,\mathrm{d}x'
$$

This collapses to the symmetry BC for symmetric $M(x)$, confirming consistency with the
existing code on that special case.

### 3.2 End-rotation extraction and compatibility condition

The **compatibility condition** requires that both spans share the same tangent (rotation)
at the interior support:

$$
\varphi_a(L_a;\,M_\mathrm{hog}) = \varphi_b(0;\,M_\mathrm{hog})
$$

That is: the rotation of **beam a evaluated at $x = L_a$** must equal the rotation of
**beam b evaluated at $x = 0$**.  Both rotations are computed using the SSB BC derived
in §3.1 from the respective span's moment diagram.

Defining shorthand:

$$
\varphi_L(M_\mathrm{hog}) \;\equiv\; \varphi_a(L_a;\,M_\mathrm{hog})
\qquad
\varphi_R(M_\mathrm{hog}) \;\equiv\; \varphi_b(0;\,M_\mathrm{hog})
$$

**Sign of $\varphi$ at the interior support** (using the convention $\varphi = -\mathrm{d}w/\mathrm{d}x$,
$w$ downward positive):

| Quantity | At $M_\mathrm{hog}=0$ | Physical meaning |
|---|---|---|
| $\varphi_L = \varphi_a(L_a)$ | $> 0$ | beam a slopes upward toward $x = L_a$ (coming out of the sag) |
| $\varphi_R = \varphi_b(0)$ | $< 0$ | beam b slopes downward away from $x = 0$ (entering the sag) |

Numerically for a 6 m span with $q = 1$ N/mm and $EI = 10^{12}$ N·mm²:
$\varphi_a(L_a) = +qL^3/(24EI) = +9\times10^{-3}$ rad, $\varphi_b(0) = -9\times10^{-3}$ rad.

### 3.3 Residuum function

Kinematic compatibility defines the residuum:

$$
\boxed{R(M_\mathrm{hog}) = \varphi_L(M_\mathrm{hog}) - \varphi_R(M_\mathrm{hog}) = 0}
$$

**Monotonicity:** at $M_\mathrm{hog} = 0$, $R(0) = \varphi_L - \varphi_R > 0$.
Increasing $M_\mathrm{hog}$ reduces the sagging in both spans at the interior-support end,
bringing $\varphi_L$ down and $\varphi_R$ up until they meet at zero.  $R$ is
monotonically decreasing, so the root is unique.

---

## 4 — Solver

### 4.1 Initial estimate from the three-moment equation

For an uncracked elastic beam the interior support moment follows from Clapeyron's
**three-moment equation** (zero moments at the outer supports, equal $EI$):

$$
\boxed{M_\mathrm{hog,el} = \frac{q\,(L_a^3 + L_b^3)}{8\,(L_a + L_b)}}
$$

For equal spans $L_a = L_b = L$ this reduces to the familiar $qL^2/8$.  For the span
ratio $S = L_b/L_a$ the formula becomes $M_\mathrm{hog,el} = qL_a^2\,(1 + S^3)/[8(1+S)]$.

> **Warning:** approximating with $L_\mathrm{eff} = (L_a+L_b)/2$ gives errors of
> 20–25 % for $S = 0.5$ or $S = 2.0$ and should not be used as the initial bracket.

Bracket for `brentq`: $[0,\; 1.5\,M_\mathrm{hog,el}]$.  $R(0) > 0$ is guaranteed by the
sign argument above.  At the upper end the over-large hogging reverses the slope imbalance,
so $R(1.5\,M_\mathrm{hog,el}) < 0$.  If this check fails for very asymmetric *nonlinear*
cases, a systematic sweep over $[0,\;2\,M_\mathrm{hog,el}]$ locates a sign change.

### 4.2 brentq (default solver)

`scipy.optimize.brentq` is bracket-safe and requires no gradient:

```python
from scipy.optimize import brentq

M_hog = brentq(
    residuum,
    a=0.0,
    b=1.5 * M_hog_el,
    xtol=1.0,           # 1 N·mm  ≈ 10⁻⁶ kN·m
)
```

Each `residuum` call performs two numerical integrations on a 200-point spatial grid —
essentially two vectorised `np.interp` calls plus two `cumtrapz` calls.  One solve
completes in a few milliseconds; convergence requires 8–12 function evaluations.

### 4.3 Numerical gradient for Newton–Raphson acceleration

When sweeping over load levels or reinforcement ratios, **Newton–Raphson (NR) pre-steps**
can halve the total call count.  The gradient is estimated by a **central finite difference**:

$$
R'(M) \approx \frac{R(M + \delta) - R(M - \delta)}{2\,\delta},
\qquad \delta = 10^{-2}\,M_\mathrm{hog,el}
$$

This costs two extra `residuum` evaluations per NR step but reduces the total from ~10
(brentq alone) to ~4 (2 NR steps + 2 brentq evaluations for convergence check).

```python
def _residuum_with_grad(residuum, M, M_hog_el):
    """Returns (R, dR/dM) via central differences."""
    delta = 1e-2 * M_hog_el
    Rm = residuum(M - delta)
    Rp = residuum(M + delta)
    return 0.5 * (Rm + Rp), (Rp - Rm) / (2 * delta)


def solve_nr_brentq(residuum, M_hog_el, n_nr=2, xtol=1.0):
    """Newton–Raphson warm-start followed by brentq refinement."""
    M = M_hog_el
    for _ in range(n_nr):
        R, dR = _residuum_with_grad(residuum, M, M_hog_el)
        if abs(dR) < 1e-30:
            break
        M = M - R / dR
        M = max(0.0, min(M, 1.5 * M_hog_el))  # stay in bracket
    return brentq(residuum, 0.0, 1.5 * M_hog_el, xtol=xtol)
```

For purely educational use, `brentq` alone is robust enough.  NR acceleration is relevant
only in outer loops that sweep hundreds of load-level or geometry combinations.

---

## 5 — Implementation plan

### 5.1 Helper `_phi_ssb` — general SSB rotation BC

Standalone function (in `continuous_beam.py`):

```python
from scipy.integrate import cumulative_trapezoid as cumtrapz
import numpy as np

def _phi_ssb(kappa_x: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Rotation profile φ(x) for a SSB, using w(0)=w(L)=0 BC."""
    phi_int = cumtrapz(kappa_x, x, initial=0.0)
    C1 = -np.trapezoid(phi_int, x) / (x[-1] - x[0])  # numpy ≥ 2.x
    return phi_int + C1
```

### 5.2 Extension of `BeamDeflectionAnalysis.get_M_x`

Add optional end-moment parameters (backward compatible via default `= 0`):

```python
def get_M_x(self, F: float,
            M_end_left: float = 0.0,
            M_end_right: float = 0.0) -> np.ndarray:
    x, L = self.x, self.L
    if self.load_type == 'dist':
        M_dist   = F * 0.5 * x * (L - x)
        # Linear moment from end moments (SSB superposition)
        M_linear = M_end_left * (1.0 - x / L) + M_end_right * (x / L)
        return M_dist + M_linear
    # '3pb' path unchanged …
```

For the **left span** call: `M_end_right = -M_hog`.  
For the **right span** call: `M_end_left = -M_hog`.

### 5.3 New dataclass `ContinuousBeamAnalysis`

Location: `scite/beam/floor/continuous_beam.py`

```python
@dataclass
class ContinuousBeamAnalysis:
    """Two-span continuous beam solved by rotation compatibility.

    Parameters
    ----------
    span_left  : BeamDeflectionAnalysis  — left span (cross-section + L [mm])
    span_right : BeamDeflectionAnalysis  — right span
    q          : float                   — uniform distributed load [N/mm]
    verbose    : bool                    — print solver trace
    """
    span_left:  BeamDeflectionAnalysis
    span_right: BeamDeflectionAnalysis
    q:          float
    verbose:    bool = False

    # ── residuum ──────────────────────────────────────────────────────────────

    def _end_phi(self, span: BeamDeflectionAnalysis,
                 M_end_left: float, M_end_right: float, end: str) -> float:
        M_x     = span.get_M_x(self.q,
                               M_end_left=M_end_left,
                               M_end_right=M_end_right)
        kappa_x = span.get_kappa_x_from_M(M_x)
        phi_x   = _phi_ssb(kappa_x, span.x)
        return float(phi_x[0] if end == 'left' else phi_x[-1])

    def residuum(self, M_hog: float) -> float:
        phi_L = self._end_phi(self.span_left,  0.0,    -M_hog, 'right')
        phi_R = self._end_phi(self.span_right, -M_hog,  0.0,   'left')
        if self.verbose:
            print(f"  M_hog={M_hog/1e6:8.3f} kN·m  "
                  f"φ_L={phi_L:+.6f}  φ_R={phi_R:+.6f}  R={phi_L-phi_R:+.2e}")
        return phi_L - phi_R

    # ── elastic estimate ──────────────────────────────────────────────────────

    @property
    def M_hog_elastic(self) -> float:
        """Uncracked-elastic estimate M_hog [N·mm] — three-moment equation."""
        La = self.span_left.L_mm
        Lb = self.span_right.L_mm
        return self.q * (La**3 + Lb**3) / (8.0 * (La + Lb))

    # ── solvers ───────────────────────────────────────────────────────────────

    def solve(self, xtol: float = 1.0) -> float:
        """Return M_hog [N·mm] via brentq."""
        from scipy.optimize import brentq
        return brentq(self.residuum, 0.0, 1.5 * self.M_hog_elastic, xtol=xtol)

    def solve_over_load(self, q_arr: np.ndarray) -> np.ndarray:
        """Solve for M_hog at each load level in *q_arr* [N/mm]."""
        M_hog_arr = np.empty_like(q_arr)
        for i, q in enumerate(q_arr):
            self.q = q
            M_hog_arr[i] = self.solve()
        return M_hog_arr
```

### 5.4 Backward compatibility

`BeamDeflectionAnalysis.get_phi_x(F)` has been updated to use the **SSB displacement BC**
($w(0)=w(L)=0$) instead of the symmetry BC.  All existing callers are unaffected: for
symmetric loading $\int_0^L \varphi_\mathrm{int}\,\mathrm{d}x = 0$ so $C_1 = 0$ and the
result is identical to the old code.

The `_phi_ssb` helper is still used in `ContinuousBeamAnalysis._end_phi` because it
receives a pre-computed `kappa_x` derived from an asymmetric $M(x)$ that includes the
end-moment term — bypassing the `get_kappa_x(F)` path inside `get_phi_x`.  The `get_M_x`
extension is additive (default arguments = 0 recover the existing behaviour).

### 5.5 Visualization plan

The plotting API mirrors the pattern of `BeamDeflectionAnalysis.plot_summary` (M-κ panel,
F-w panel, profile panels) adapted for the **two-span geometry**.

**Global x-coordinate convention:**
The two spans are concatenated on a single horizontal axis.  Left span occupies
$x \in [0,\, L_a]$; right span occupies $[L_a,\, L_a + L_b]$.  All plot methods work in
millimetres internally.

---

#### `plot_scheme(ax)` — structural schematic

Shows the beam set-up at a glance (no axes displayed):

- Horizontal beam reference axis at $y = 0$.
- Downward arrows at uniform spacing representing the distributed load $q$, with
  a filled bar at the top and a label showing the load intensity.
- Filled triangular support markers at $x = 0$, $x = L_a$ (interior support), and
  $x = L_a + L_b$ (right outer support), each labelled with its absolute coordinate
  in metres.
- Double-headed dimension arrows below the beam showing $L_a$ and $L_b$.

---

#### `plot_M(ax, show_elastic=True)` — bending moment diagram

Two overlaid curves:

| Curve | Style | Description |
|---|---|---|
| elastic | gray dashed | M from $M_\mathrm{hog,el}$ (three-moment equation) |
| nonlinear | blue solid | M from `solve()` |

Both spans are concatenated.  The **y-axis is inverted** (sagging below the reference
line, structural sign convention).  A circular marker at $x = L_a$ shows
$-M_\mathrm{hog}$ for each case.  Vertical dotted guide lines mark the support
positions.

---

#### `plot_w(ax, show_elastic=True)` — deflection profiles

Same two-curve layout as `plot_M`.  Deflection $w(x)$ is computed by integrating $\varphi$
from `_phi_ssb` once more.  The **y-axis is inverted** ($w$ downward positive).

---

#### `plot_redistribution(q_arr, ax)` — moment redistribution curve

Sweeps over a load array and plots
$$
\frac{M_\mathrm{hog}(q)}{M_\mathrm{hog,el}(q)} \quad \text{vs.} \quad q
$$
The elastic reference is a horizontal line at 1.  Cracking at mid-span raises the ratio;
cracking at the support lowers it.  This plot directly shows the **redistribution
phenomenon** that is the educational core of ICC Part 02.

---

#### `plot_summary(title='')` — 3-panel combined figure

```
┌─────────────────────────────────────┐  height 1
│  plot_scheme  (beam + load + dims)  │
├─────────────────────────────────────┤  height 2
│  plot_M       (M diagram, 2 curves) │
├─────────────────────────────────────┤  height 2
│  plot_w       (deflection, 2 curves)│
└─────────────────────────────────────┘
```

Follows `BeamDeflectionAnalysis.plot_summary` in using
`gridspec_kw={'height_ratios': [1, 2, 2]}` and calling
`IPython.display` so that the figure renders inline in Jupyter and is
then closed to free memory.

---

## 6 — Physical interpretation and educational value

| Load level | Expected $M_\mathrm{hog}$ behaviour |
|---|---|
| Elastic (uncracked) | $M_\mathrm{hog} = qL^2/8$ — matches the textbook two-span result |
| After first cracking at mid-span | $M_\mathrm{hog}$ **increases** — cracked mid-span rotates more, demands more hogging to restore compatibility |
| After cracking at the support | $M_\mathrm{hog}$ **decreases** — support-zone stiffness drops, allowing redistribution to the span |
| Near ULS, CFRP rib | Brittle failure limits redistribution; $M_\mathrm{hog}$ stays near the elastic value |
| Near ULS, steel RC rib | Ductile yielding allows significant redistribution; $M_\mathrm{hog}$ may be 20–30 % below elastic |

Plotting $M_\mathrm{hog}(q)/M_\mathrm{hog,el}(q)$ over the full load range reveals the
redistribution curve, with 1.0 in the elastic regime and a characteristic dip after
cracking at the critical zone.  This is the core phenomenon of **ICC Part 02**.

---

## 7 — References in the codebase

| Class / function | File | Role |
|---|---|---|
| `BeamDeflectionAnalysis` | `scite/beam/bending/beam_deflection.py` | κ-integration engine |
| `FloorAnalysis` | `scite/beam/floor/floor_analysis.py` | Tributary-width wrapper |
| `FloorAnalysisPair` | same | SLS + ULS pair |
| `SRCRibbedSlab`, `CRCRibbedSlab` | `scite/beam/floor/ribbed_slab.py` | Full floor-system models |
| `ContinuousBeamAnalysis` | `scite/beam/continuous/continuous_beam.py` | Two-span solver |

> **Usage from floor context:** `ContinuousBeamAnalysis` accepts `BeamDeflectionAnalysis`
> objects directly.  Pass `floor_analysis.bda` for each span when constructing from a
> `FloorAnalysis` or `FloorAnalysisPair`.
