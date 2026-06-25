# Concept: M-κ Discretization Refinement — Explicit Cracking Point

*Scite codebase concepts — relates to `MKappaAnalysis`, `EC2Concrete`,
`EC2ParabolaRectangle`, `CrossSection`, `BeamDeflectionAnalysis`*

---

## 1. Motivation

The current `MKappaAnalysis.solve()` samples curvature with:

```python
kappa_min = kappa_max * 0.001   # slightly above zero
kappa_array = np.linspace(kappa_min, kappa_max, n_kappa)
```

Two structural problems:

1. **Zero is missing.**  The origin $(κ=0,\,M=0)$ is never evaluated.  The
   `_ascending_envelope` method prepends it for interpolation purposes, but it
   does not appear in the raw solved arrays and is therefore absent from the
   plotted M-κ curve.

2. **The linear pre-cracking range wastes `n_kappa` capacity.**  From κ = 0 to
   the cracking curvature κ_cr the M-κ relationship is purely linear (uncracked
   elastic section, no nonlinearity).  Placing e.g. 30 out of 150 points in this
   trivially linear zone gives no additional information — those slots are needed
   in the post-cracking range where the curve is genuinely nonlinear and the
   solver convergence near cracking is problematic.  With coarser post-cracking
   resolution the `_ascending_envelope` must bridge larger gaps, reducing
   inversion accuracy.

3. **Cracking is a known discontinuity.**  At κ_cr the section transitions from
   uncracked to cracked, and the M-κ curve shows a sudden stiffness drop (the
   *cracking kink*).  This is precisely the source of the equilibrium-solver
   failures that motivate the `M_peak_reached` guard added to `failure_threshold`.
   Placing κ_cr explicitly in the sample array pins the discontinuity at a known
   point instead of relying on proximity and consecutive-failure counting.

---

## 2. The Cracking Curvature — Pure Bending

### 2.1 Notation

> **Code vs. EC2 coordinate convention**
>
> In the scite code, reinforcement layers are positioned by
> `z` = distance from the **bottom** face (e.g. `ReinforcementLayer.z = c_nom + φ/2`
> from the bottom).  A bottom layer with cover 40 mm sits at `z = 40 mm`.
>
> EC2 §1.6 uses a different set of symbols:
>
> | Symbol | EC2 meaning |
> |--------|-------------|
> | `c`, `c_nom` | Concrete cover — distance from the bar **surface** to the nearest concrete face |
> | `d` | Effective depth — from the **compressive** face to the tensile reinforcement centroid |
> | `x` | Neutral axis depth — from the **compressive** face |
> | `z` | Internal lever arm — distance between compression and tension resultants |
>
> The code's `z` (position from bottom) must not be confused with EC2's `z`
> (lever arm).  To avoid this clash the concept document uses `y_c` for the
> centroid (neutral axis) position measured from the **bottom** face, following
> the code's coordinate system.  The EC2 neutral axis depth from the compressive
> face is then $x_{sag} = h - y_c$ (sagging) or $x_{hog} = y_c$ (hogging).

### 2.2 Uncracked elastic section

Below κ_cr the cross-section behaves as a linear-elastic composite (concrete +
transformed reinforcement, modular ratio $n = E_s / E_c$).  The neutral axis
position $y_c$ from the **bottom** is determined by the transformed section:

$$
y_c = \frac{\frac{b\,h^2}{2} + \sum_i (n-1)\,A_{s,i}\,z_{s,i}}
           {b\,h + \sum_i (n-1)\,A_{s,i}}
$$

where $z_{s,i}$ is the centroid height of layer $i$ from the bottom (code
convention).  In general $y_c \neq h/2$; it shifts toward the heavier
reinforcement layer.  **No assumption of equal covers is made.**

The transformed second moment of area about $y_c$:

$$
I_{g} = \frac{b\,h^3}{12} + b\,h\,(y_c - h/2)^2
       + \sum_i (n-1)\,A_{s,i}\,(y_c - z_{s,i})^2
$$

### 2.3 Cracking moment and curvature (N_Ed = 0)

Cracking occurs at the extreme tensile fibre.  The tensile fibre distances from
the neutral axis are:

- **Sagging**: tensile face = bottom ($z = 0$), distance $= y_c$
- **Hogging**: tensile face = top ($z = h$), distance $= h - y_c$

These distances differ whenever $y_c \neq h/2$, which is the general case for
any section with unequal reinforcement or unequal covers.  **The same $y_c$
serves both branches — no separate centroid computation is needed.**

The cracking curvatures are:

$$
\kappa_{cr,sag} = \frac{f_{ctm}}{E_c \cdot y_c}
               = \frac{\varepsilon_{cr}}{y_c}
\qquad
\kappa_{cr,hog} = \frac{f_{ctm}}{E_c \cdot (h - y_c)}
               = \frac{\varepsilon_{cr}}{h - y_c}
$$

where $\varepsilon_{cr} = f_{ctm}/E_c$.  Verification: at cracking the bottom
strain is $\varepsilon_{bot} = \kappa_{cr,sag} \cdot y_c = \varepsilon_{cr}$ ✓.

For an asymmetric section with $A_{s,top} > A_{s,bot}$ the centroid shifts
upward ($y_c > h/2$), giving:
- $\kappa_{cr,sag} < 2\varepsilon_{cr}/h$ — bottom fibre farther from NA, section cracks at a lower curvature
- $\kappa_{cr,hog} > 2\varepsilon_{cr}/h$ — top fibre closer to NA, section needs more curvature to crack

The two cracking curvatures are in general **not equal** for asymmetric sections.

### 2.3 Numerical check on the T-section from notebook 10

For the T-section ($b_w = 300$, $h_w = 250$, $b_f = 1150$, $h_f = 150$,
$h = 400\,\text{mm}$, C30/37 → $f_{ctm} = 2.90\,\text{MPa}$,
$E_c = 32\,836\,\text{MPa}$, $\varepsilon_{cr} = 8.83\times10^{-5}$):

The flange area is large, which pulls the centroid upward relative to $h/2$.
At first approximation (ignoring the small reinforcement contribution):

| Branch  | Tensile fibre | $z_{NA}^{approx}$ | $\kappa_{cr}$ (‰/mm) |
|---------|--------------|-------------------|----------------------|
| Sagging | Bottom       | ≈ 230 mm (flange pulls up) | ≈ 0.000383 |
| Hogging | Top          | ≈ 170 mm (from top) | ≈ 0.000519 |

Compare with $\kappa_{max} \approx 0.076\,\text{‰/mm}$: the cracking curvatures
are roughly 0.5–0.7 % of $\kappa_{max}$.  With `n_kappa = 150` and the current
linspace, approximately **1 point** falls in $[0, \kappa_{cr}]$.  The cracking
kink is effectively invisible, and the solver hits an unsampled discontinuity.

---

## 3. Effect of Normal Force (Prestress or External N_Ed)

With a constant axial force $N_{Ed}$ (positive = tension) the uniform strain
background $\varepsilon_0 = N_{Ed} / (E_c\,A_g)$ shifts all fibre strains.

The cracking condition at the bottom fibre becomes:

$$
\varepsilon_{bot,cr} = \varepsilon_{cr} - \varepsilon_0
                     = \frac{f_{ctm}}{E_c} - \frac{N_{Ed}}{E_c\,A_g}
                     = \frac{f_{ctm} - N_{Ed}/A_g}{E_c}
$$

Equivalently, the cracking moment is shifted:

$$
M_{cr}(N_{Ed}) = \left(f_{ctm} - \frac{N_{Ed}}{A_g}\right) \frac{I_g}{z_{NA}}
$$

| $N_{Ed}$ | Effect on cracking |
|----------|--------------------|
| $0$ | baseline: $M_{cr} = f_{ctm}\,I_g/z_{NA}$ |
| $< 0$ (prestress, compression) | $f_{ctm} - N_{Ed}/A_g > f_{ctm}$ → higher $M_{cr}$, smaller section is cracked at service |
| $> 0$ (tension) | $f_{ctm} - N_{Ed}/A_g < f_{ctm}$ → lower $M_{cr}$, cracks at lower moment |
| $= f_{ctm}\,A_g$ (pure tension) | $M_{cr} = 0$ — section already cracked at $\kappa = 0$ |

When $N_{Ed} = f_{ctm}\,A_g$ there is no meaningful pre-cracking elastic zone
on the tension branch; the entire sagging range is post-cracking.  The
κ_cr insertion is skipped in this case.

---

## 4. Concrete Tensile Properties — Extended to Both Models

### 4.1 EC2ParabolaRectangle extension (implemented)

Both concrete models now expose the same tensile property interface:

| Property | Formula (EC2 Table 3.1) | Both models |
|----------|------------------------|-------------|
| `f_ctm` | 0.30·f_ck^(2/3) for f_ck ≤ 50; 2.12·ln(1+f_cm/10) for f_ck > 50 | ✓ |
| `E_cm` | 22 000·(f_cm/10)^0.3 | ✓ |
| `E_ct_computed` | = E_cm (alias, for API compatibility) | ✓ |
| `eps_cr_computed` | f_ctm / E_cm | ✓ |

`EC2ParabolaRectangle` was extended with these four `cached_property` methods.
The compression behaviour is unchanged: the model still returns zero stress for
ε > 0 — `f_ctm` is exposed as a *material property* used by the M-κ cracking
analysis and SLS crack-spacing calculations, not as a stress-return value.

**Rationale:**  `f_ctm` is a property of the concrete grade regardless of
whether a design or mean stress-block is used for the compression side.
Exposing it on `EC2ParabolaRectangle` allows:
- κ_cr identification in ULS/design-mode M-κ sweeps (shape of pre-cracking branch)
- SLS crack-spacing formulae ($s_{r,max}$, $w_k$) using the same section object
  that is already used for ULS assessment
- `ContinuousBeamModes.for_rc()` to compute cracking curvatures for all three
  modes without mode-specific branching

### 4.2 No duck-typing protocol needed

Since both models now provide `f_ctm` and `E_ct_computed`, the κ_cr calculation
in `MKappaAnalysis._kappa_cr()` can call these directly:

```python
f_ctm = self.cs.concrete.f_ctm          # always available
E_c   = self.cs.concrete.E_ct_computed   # always available
kappa_cr_pos, kappa_cr_neg = self._compute_kappa_cr(f_ctm, E_c)
```

The only remaining check is the N_Ed guard (section pre-cracked under large
axial tension) described in §6.3.

### 4.3 Numerical values for the reference section (C30/37)

```
f_ctm          =  2.896 MPa
E_cm           = 32 837 MPa
eps_cr         =  8.83 × 10⁻⁵  (≈ 0.088 ‰)
```

For the T-section (h = 400 mm, symmetric approximation):
```
kappa_cr,sag ≈ 2 × 8.83e-5 / 400 = 4.4 × 10⁻⁷ /mm  = 0.00044 ‰/mm
kappa_cr,hog ≈ same (symmetric)
kappa_max    ≈ 0.076 ‰/mm
kappa_cr / kappa_max ≈ 0.6 %
```

This confirms that κ_cr occupies less than 1 % of the full curvature range yet
is the site of the most severe numerical discontinuity.

---

## 5. Proposed Discretization Scheme

### 5.1 Principle

The new kappa array is built in three segments for each branch:

| Segment | Range | Points | Why |
|---------|-------|--------|-----|
| Origin | $[0, 0]$ | 1 | Ensures M=0 is present in the solved arrays |
| Pre-cracking | $(0, \kappa_{cr})$ | 1 (just $\kappa_{cr}$ itself) | Linear → 2 points define the line |
| Post-cracking | $[\kappa_{cr}, \kappa_{max}]$ | `n_kappa` | Full density where nonlinearity lives |

Total points per branch: $n_{kappa} + 2$ instead of $n_{kappa}$.
The pre-cracking segment costs one extra solve; the origin costs nothing
(M=0 at κ=0 is analytically exact, no equilibrium solve needed).

### 5.2 Pseudocode for `_build_kappa_array` (new cached property)

```python
def _build_kappa_array(self, branch: str) -> np.ndarray:
    """Return kappa sample points for 'positive' or 'negative' branch.

    Scheme:
      1. Compute kappa_cr analytically from uncracked elastic section (if
         f_ctm is available from the concrete model).
      2. Prepend 0 and kappa_cr; fill [kappa_cr, kappa_max] with n_kappa points.
      3. If kappa_cr is unavailable, fall back to linspace(kappa_min, kappa_max).
    """
    kappa_min, kappa_max = (
        self.get_kappa_range() if branch == 'positive'
        else self.get_kappa_range_neg()
    )
    # kappa_min, kappa_max are magnitudes (both positive)

    kappa_cr = self._kappa_cr(branch)   # None if concrete has no f_ctm

    if kappa_cr is None or kappa_cr >= kappa_max:
        # Fallback: existing equidistant scheme
        return np.linspace(kappa_min, kappa_max, self.n_kappa)

    # Skip kappa_cr if section is already cracked (e.g. large N_Ed)
    if kappa_cr <= 0:
        return np.linspace(kappa_min, kappa_max, self.n_kappa)

    post = np.linspace(kappa_cr, kappa_max, self.n_kappa)
    return np.concatenate([[0.0, kappa_cr], post[1:]])
    # post[1:] avoids duplicating kappa_cr; 0.0 is handled separately (M=0 point)
```

The **origin point** $(κ=0, M=0)$ is injected analytically (no solve) into the
results lists at the start of the sweep, avoiding the equilibrium-solve overhead
and the potential solver failure at κ=0 (zero curvature → degenerate bracket).

### 5.3 Sign convention for the negative branch

The negative branch uses magnitudes internally and applies signs at storage:

```python
kappa_neg_array = -self._build_kappa_array('negative')  # signed negative
```

The same cracking analysis applies (using the top-fibre geometry).

---

## 6. Cracking Curvature Computation — Implementation

### 6.1 Transformed section centroid

```python
def _transformed_section_centroid(self) -> float:
    """Centroid z_NA from bottom [mm] of the transformed uncracked section."""
    n  = self.cs.concrete.E_ct_computed / 200_000.0   # E_s assumed 200 GPa
    # ... or read from the reinforcement material

    # Concrete gross contribution
    # For non-rectangular shapes: use cross-section shape API
    h  = self.cs.h_total
    A_c = self.cs.shape.area        # concrete area [mm²]
    S_c = self.cs.shape.first_moment_of_area_bottom  # Σ b(z)·z·dz

    # Transformed reinforcement contribution
    A_tr = sum((n - 1) * lay.A_s for lay in self.cs.reinforcement.layers)
    S_tr = sum((n - 1) * lay.A_s * lay.z for lay in self.cs.reinforcement.layers)

    return (S_c + S_tr) / (A_c + A_tr)
```

> **Note:** `CrossSection.shape` currently provides `area` and `h_total` but may
> not yet expose `first_moment_of_area_bottom`.  This is a small addition to the
> shape API (see §8).

### 6.2 Second moment of area

```python
def _transformed_section_I(self, z_NA: float) -> float:
    """Second moment of area I_g [mm⁴] of the transformed section about z_NA."""
    n  = self.cs.concrete.E_ct_computed / 200_000.0

    # Gross concrete I about z_NA (Steiner + own)
    I_c = self.cs.shape.second_moment_of_area_bottom   # I_g about bottom reference
    A_c = self.cs.shape.area
    h_c = self.cs.shape.first_moment_of_area_bottom / A_c  # centroid of concrete
    I_c_NA = I_c - A_c * h_c**2 + A_c * (z_NA - h_c)**2  # parallel-axis to z_NA

    # Transformed reinforcement
    I_tr = sum((n - 1) * lay.A_s * (z_NA - lay.z)**2
               for lay in self.cs.reinforcement.layers)

    return I_c_NA + I_tr
```

### 6.3 Cracking curvature

```python
def _kappa_cr(self, branch: str) -> Optional[float]:
    """Cracking curvature [1/mm] magnitude for 'positive' or 'negative' branch."""
    f_ctm = getattr(self.cs.concrete, 'f_ctm', None)
    E_c   = getattr(self.cs.concrete, 'E_ct_computed', None)
    if f_ctm is None or E_c is None:
        return None

    # Account for axial force: effective cracking stress
    A_g  = self.cs.shape.area
    sig_N = self.N_Ed * 1000.0 / A_g   # N_Ed [kN] → [N], then [MPa]
    f_ctm_eff = f_ctm - sig_N          # tension N_Ed reduces cracking resistance

    if f_ctm_eff <= 0.0:
        return 0.0   # caller interprets as "already cracked"

    eps_cr_eff = f_ctm_eff / E_c

    z_NA = self._transformed_section_centroid()

    if branch == 'positive':
        # Sagging: tensile fibre at bottom (z = 0), distance from NA = z_NA
        return eps_cr_eff / z_NA
    else:
        # Hogging: tensile fibre at top (z = h), distance from NA = h - z_NA
        return eps_cr_eff / (self.cs.h_total - z_NA)
```

---

## 7. Pre-cracking M-κ Point (Origin Injection)

At κ = 0 the moment is exactly M = 0.  This point is injected analytically at
the start of each branch's result arrays:

```python
# Sagging branch — prepend origin
kappa_list     = [0.0]
eps_bot_list   = [0.0]
M_list         = [0.0]
N_list         = [0.0]

# ... equilibrium solve loop from kappa_cr onward ...
```

At κ = κ_cr the moment can also be injected analytically:

$$
M_{cr} = E_c \cdot I_g \cdot \kappa_{cr}
$$

Alternatively, the solver is called at κ_cr normally — the uncracked section
solves without issue since the concrete is still in its linear tensile zone.
The analytical formula is a useful cross-check.

---

## 8. Shape API Extensions Required

The transformation formulas in §6 require two integrals over the cross-section
shape that are not yet in the shape API:

| Property | Formula | Needed for |
|----------|---------|-----------|
| `shape.area` | $\int_0^h b(z)\,\mathrm{d}z$ | Centroid, N_Ed normalisation |
| `shape.first_moment_of_area_bottom` | $\int_0^h b(z)\cdot z\,\mathrm{d}z$ | Centroid $z_{NA}$ |
| `shape.second_moment_of_area_bottom` | $\int_0^h b(z)\cdot z^2\,\mathrm{d}z$ | $I_g$ (then Steiner to $z_{NA}$) |

For `RectangularShape` these are closed-form: $A = b\,h$, $S = b\,h^2/2$,
$I_0 = b\,h^3/3$ (about the bottom).

For `TShape` numerical integration over the piecewise $b(z)$ profile gives
exact results; the shape already exposes `get_width_at_y` so the integrals
are computable via `np.trapezoid` over a fine z-grid as a stopgap.

---

## 9. Open Questions

| Question | Impact | Proposed resolution |
|----------|--------|---------------------|
| `EC2ParabolaRectangle` tensile properties | **Done** — added `f_ctm`, `E_cm`, `E_ct_computed`, `eps_cr_computed` | No duck-typing needed; both models share the interface |
| **[Future] Origin point under non-zero N_Ed** | Medium — the strain at κ = 0 is not zero when an axial force is present: the bottom-fibre strain satisfies N(ε₀, κ=0) = N_Ed, giving ε₀ = N_Ed/(E_c·A_g). The injected (0, 0) point in the M-κ array is still correct for *external* moment (M = 0 at κ = 0 by definition), but ε_bot at that point is ε₀, not zero. The `eps_bot_values` array should store ε₀ at index 0 rather than 0.0. | Defer; add a `_eps_bot_at_zero_kappa()` helper that solves N(ε_bot, 0) = N_Ed once and uses the result as the injected eps_bot origin. |
| **[Future] Prescribed prestrain in reinforcement (ε_pt)** | Medium-high — an initial tendon strain ε_pt creates an internal prestress force P and moment M_p at κ = 0 even under zero external load. The "decompression moment" M_dec (the external moment needed to bring the tensile fibre back to zero net stress) becomes the effective cracking threshold offset. The κ_cr derivation in §6 must be shifted by M_dec/EI_g to obtain the curvature at which net-section cracking occurs under external moment. | Defer; the prescribed-strain reinforcement material model (a future `PrestrainedSteel` or `TendonLayer` class) will carry ε_pt. When present, `_kappa_cr` should compute M_dec from the uncracked section with ε_pt and add M_dec/EI_g to the bare κ_cr formula. The origin injection must solve the (κ = 0, N = N_Ed, ε_pt present) equilibrium to obtain the correct initial ε_bot. |
| Is the modular ratio $n = E_s / E_c$ constant? | Medium — E_c depends on f_ck | Use concrete's `E_ct_computed`; read E_s from first reinforcement layer |
| Is the transformed section formula valid for T-shapes? | Yes — the formula holds for any shape; only requires $A$, $S$, $I_0$ integrals | Numerical integration via `get_width_at_y` as stopgap |
| For large N_Ed (axial tension), can $\kappa_{cr} \le 0$? | Yes — section already pre-cracked | Check: if $f_{ctm,eff} \le 0$, skip pre-cracking segment entirely |
| Does the negative branch need a separate $z_{NA}$? | No — same uncracked section, only tensile fibre height differs | Use $z_{NA}$ for sagging, $h - z_{NA}$ for hogging |
| Should κ_cr be stored after solving? | Yes — needed for annotation and cracking marker in `plot_mk` | Store as `self.kappa_cr_pos` and `self.kappa_cr_neg` (None until solved) |

---

## 10. Relationship to Existing Code

| Component | Current state | Required change |
|-----------|--------------|-----------------|
| `MKappaAnalysis.solve()` | `linspace(kappa_min, kappa_max, n_kappa)` | Replace with `_build_kappa_array()` |
| `MKappaAnalysis.get_kappa_range()` | Returns `(kappa_min, kappa_max)` | Unchanged; called inside `_build_kappa_array` |
| `MKappaAnalysis` | No κ_cr stored | Add `kappa_cr_pos`, `kappa_cr_neg` fields (None until solved) |
| `MKappaAnalysis.plot_mk()` | No cracking marker | Optionally draw a vertical dashed line at $\kappa_{cr}$ if stored |
| `EC2Concrete` | `f_ctm`, `E_ct_computed`, `eps_cr_computed` ✓ | None |
| `EC2ParabolaRectangle` | No tensile properties | **Done** — added `f_ctm`, `E_cm`, `E_ct_computed`, `eps_cr_computed` via EC2 Table 3.1 |
| `RectangularShape` | Has `h_total`; no $A$, $S$, $I_0$ | Add `area`, `first_moment_of_area_bottom`, `second_moment_of_area_bottom` |
| `TShape` | Same | Same (or numerical integration stopgap) |
| `CrossSection` | Has shape + reinforcement | Add `_transformed_centroid()`, `_transformed_I()` as private helpers |

---

## 11. Summary of the Refinement

The proposed change is conservative and incremental:

1. **`EC2ParabolaRectangle` extension** ✓ **Done** — `f_ctm`, `E_cm`,
   `E_ct_computed`, `eps_cr_computed` added; both concrete models now share the
   same tensile property interface, enabling κ_cr computation for all three
   material modes (design, characteristic, mean) without any conditional branching.
2. **One new method** on `MKappaAnalysis`: `_build_kappa_array(branch)` with
   `_kappa_cr(branch)` as a helper.
3. **One new method** on `CrossSection` (or on `MKappaAnalysis` directly):
   transformed centroid and second moment of area.
4. **Shape API**: three new properties on `RectangularShape` and `TShape`.
5. **Two new stored fields**: `kappa_cr_pos`, `kappa_cr_neg` (optional floats).
6. **No change to the existing solve loop** beyond replacing the sample-point
   generation.

The M-κ curve produced by the refined scheme:

- Passes through $(0, 0)$ explicitly.
- Has the cracking kink pinned exactly at $\kappa_{cr}$ — no solver failures in
  the discontinuity neighbourhood.
- Devotes all `n_kappa` resolution to the post-cracking nonlinear range.
- Exposes $\kappa_{cr}$ as a named attribute for downstream annotation and
  analysis.
