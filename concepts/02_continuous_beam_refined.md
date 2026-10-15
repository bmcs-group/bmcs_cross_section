# Continuous Beam: Refined Problem Formulation

This document refines the analysis in `02_continuous_beam.md` by addressing two
conceptual issues that arise when extending the rotation-compatibility solver beyond
the SSB failure load $q_{field,u}$.

---

## 1 — What the current solver actually inverts

The solver uses linear statics to obtain $M_x(x;\, M_{hog})$ for a trial $M_{hog}$, then
calls `get_kappa_x_from_M` to invert the M-κ curve at each cross-section:

$$
\kappa(x) = f^{-1}(M_x(x))
$$

This inversion defines the computation chain:

```
M_hog  →  M(x) [linear statics]  →  κ(x) [M-κ inversion]  →  φ [integration]
```

The M-κ curve from `MKappaAnalysis` **does** contain all cross-sectional nonlinearity —
cracking, tension stiffening, steel yielding, CFRP linear-to-rupture.  There is
no missing physical content.  The problem is purely **mathematical**: the inversion
$M \mapsto \kappa$ is ill-posed in different ways depending on material.

---

## 2 — The ill-posedness of $M \mapsto \kappa$

### 2.1 Steel (plateau branch)

A steel-reinforced section has a long post-yield plateau at $M \approx M_R$ where the
M-κ curve is nearly horizontal.  The same moment $M_R$ corresponds to an unbounded
range of curvatures $\kappa \in [\kappa_R, \kappa_{ult}]$:

$$
M = M_R \quad \Longrightarrow \quad \kappa \in [\kappa_R,\; \kappa_{ult}]
\quad \text{(ill-posed)}
$$

The inversion $M \mapsto \kappa$ is **not unique** on the plateau.  Any M-controlled
algorithm that clips $M$ to $M_R$ and maps it to $\kappa_R$ (the ascending-branch peak)
**underestimates** the rotation $\varphi = \int \kappa\, dx$ near the support.  This is
exactly what the current `get_kappa_x_from_M` does — and why the solver's residuum
$R(M_{hog}) = \varphi_L - \varphi_R$ does not cross zero for $q > q_{field,u}$.

### 2.2 CFRP (brittle rupture)

A CFRP section has a descending branch immediately after peak (brittle rupture / snap-back).
The inversion is unique up to $M_R$, and there is no plateau.  The rotation-compatibility
equation has a valid root for all $q \leq q_{field,u}$.  Once $M_{hog}$ reaches $M_R$,
the cross-section has failed and there is no Phase 2.  **The current solver already
delivers the physically correct collapse load for CFRP.**

---

## 3 — Does introducing $\theta_p$ double-count the constitutive law?

No. The issue is not double-counting — it is a change of primary variable to resolve
the ill-posedness.

The plastic hinge rotation $\theta_p$ is the concentrated integral of the plateau
curvature over the yielded zone:

$$
\theta_p = \int_{\text{plastic zone}} (\kappa(x) - \kappa_{\text{elastic}}(x))\, dx
$$

For a perfectly plastic section, this integral collapses to a point at $x = L_a$ (the
support), i.e.\ a Dirac delta of curvature with weight $\theta_p$.  The
constitutive law (M-κ) is still respected — $M_{hog} = M_R$ on the plateau.
$\theta_p$ is simply the integral that the M-controlled inversion cannot evaluate
because $\kappa$ is indeterminate at $M = M_R$.

**The M-κ integration and the $\theta_p$ representation are two descriptions of the
same physics, not two separate mechanisms.**

---

## 4 — Notation: $\kappa_R$ vs $\kappa_y$

Two curvature landmarks appear on the M-κ curve:

| Symbol | Definition |
|--------|------------|
| $\kappa_y$ | Curvature at first steel yielding (steel only; onset of nonlinearity) |
| $\kappa_R$ | Curvature at **peak moment** $M_R$ — the end of the ascending branch |

For steel, $\kappa_R$ is the curvature at which the plateau begins (not the yield
curvature).  For CFRP, $\kappa_R$ is the rupture curvature.  Throughout this document
$\kappa_R$ always denotes the ascending-branch endpoint.

---

## 5 — Curvature at the support as primary kinematic variable

In the Bernoulli beam, $\kappa(x)$ is continuous.  Both sides of the interior support
share the same hogging moment $M_{hog}$, so:

$$
\kappa_L(L_a) = f^{-1}(M_{hog}) = \kappa_R(0)
$$

As an **equation**, this carries no new information — it is automatically satisfied.
But as a **design of the primary unknown** it is decisive.  On the ascending
branch $[0,\,\kappa_R]$ the forward map $f: \kappa \mapsto M$ is strictly monotone
and therefore uniquely invertible.  The same is true of $f^{-1}$ — but only on
the ascending branch.  The plateau ($\kappa > \kappa_R$, steel) breaks the inverse
uniqueness while leaving the forward map single-valued.

This asymmetry is the motivation for Strategy C below: use the **kinematic variable
$\kappa_{hog}$** as the loop parameter instead of the static variable $M_{hog}$.

---

## 6 — Why M-controlled inversion is the root of the limitation

The natural (well-posed) formulation of the nonlinear beam is **deformation-controlled**:

$$
\text{primary unknown: } w(x) \quad \Longrightarrow \quad
\kappa(x) = -w''(x) \quad \Longrightarrow \quad
M(x) = f(\kappa(x))
$$

Here $\kappa$ is the primary variable; the constitutive map $\kappa \mapsto M$ is
always unique (even on the plateau, $\kappa \mapsto M$ is single-valued — the plateau
just means the inverse is not).  Equilibrium then becomes:

$$
M''(x) + q = 0 \quad \Leftrightarrow \quad [f(\kappa)]'' + q = 0
$$

with displacement BCs at the three supports.  This is a genuine nonlinear BVP.  In this
formulation:

- No ill-posedness at any load level.
- $\theta_p$ is a post-processing quantity: $\int (\kappa - \kappa_{el})\, dx$ over
  the yielded zone — it does not appear in the solver.
- The rotation at the interior support and the curvature continuity condition are both
  automatically satisfied by the BVP solution.

**The current solver uses the inverse map ($M \mapsto \kappa$) for implementation
convenience.  This is what limits it to $q \leq q_{field,u}$.**

---

## 7 — Three strategies for extending the solver to $q > q_{field,u}$

### Strategy A — Add $\theta_p$ as an explicit degree of freedom (practical, steel only)

This preserves the existing moment-controlled architecture with a minimal change:

**Phase 1** ($q \leq q_{field,u}$, $M_{hog} \leq M_R$):
Current solver unchanged.  `brentq` finds $M_{hog}$ from $R(M_{hog}) = 0$.

**Phase 2** ($q > q_{field,u}$):
$M_{hog} = M_R$ is prescribed (support section on plateau).
A plastic hinge rotation $\theta_p$ is added as a discrete DOF at the support.
The compatibility condition becomes:

$$
\varphi_L(L_a,\; M_R) = \varphi_R(0,\; M_R) - \theta_p
$$

$\theta_p \geq 0$ is the new unknown, solved analytically:

$$
\theta_p(q) = \varphi_R(0,\; M_R) - \varphi_L(L_a,\; M_R)
$$

Both rotations on the right-hand side are evaluated with the existing integration
engine using the ascending M-κ branch (which is correct everywhere except at
$x = L_a$ — a set of measure zero in the integration).

The collapse load $q_{mech}$ is reached when $\theta_p(q)$ equals the rotation
capacity $\theta_{p,u}$ of the section (from the M-κ post-peak area, ductility class,
or prescribed limit).

This is algebraically simple: no new solver is needed.  It is also consistent with
the M-κ constitutive law — no double-counting.

### Strategy B — Deformation-controlled BVP (rigorous, any material)

Solve the nonlinear ODE $M(w'') + q = 0$ with three-point BCs directly.
This requires:
- Finite difference or finite element spatial discretisation.
- Newton-Raphson iteration on the displacement field.
- No structural change to the constitutive models.

In this formulation $\theta_p$ is a post-processing output, not a solver variable.
The deformation-controlled M-κ (κ as primary axis) is the correct numerical tool.

### Strategy C — $\kappa_{hog}$-controlled compatibility (practical, any material)

This is the key insight from the current discussion.  Instead of sweeping $M_{hog}$
(static variable) and solving the M-κ inversion at the support, sweep the **curvature
at the support** $\kappa_{hog}$ as the primary kinematic parameter.

**Computation chain:**

```
κ_hog  →  M_hog = f(κ_hog)  [forward map, always unique]
       →  M(x; q, M_hog)    [linear statics, parametric in q]
       →  κ(x)  =  f⁻¹(M(x)) [M-κ inversion on interior sections only]
       →  φ_L, φ_R           [rotation integrals]
       →  solve q: φ_L(L_a) = φ_R(0)  [brentq over q, not M_hog]
```

**Why the ill-posedness disappears:**

1. The support section at $x = L_a$ has $\kappa = \kappa_{hog}$ *prescribed* — no
   inversion is needed there.  That single point contributes measure zero to the
   rotation integral.
2. All interior sections have $|M_x(x)| < M_{hog} \leq M_R$ — strictly below the
   peak — so $f^{-1}$ is unique there regardless of material.
3. The forward map $f(\kappa_{hog})$ is single-valued everywhere on the M-κ curve,
   including on the steel plateau ($\kappa_{hog} > \kappa_R$, $M_{hog} \approx M_R$).

**Sweep structure:**

$$
\kappa_{hog} \in [0,\, \kappa_{ult}] \quad \xrightarrow{f} \quad M_{hog}(\kappa_{hog})
\quad \xrightarrow{\text{compat.}} \quad q(\kappa_{hog})
$$

- **Ascending branch** $[0, \kappa_R]$: $M_{hog}$ grows monotonically, $q$ increases.
  Identical result to the current `brentq` over $M_{hog}$.
- **Steel plateau** $[\kappa_R, \kappa_{ult}]$: $M_{hog} \approx M_R$ (constant),
  $q$ continues to increase as redistribution occurs.  The same compatibility
  solver works without any phase change — it simply finds $q$ for a fixed
  $M_{hog} = f(\kappa_{hog}) \approx M_R$.
- **CFRP**: $\kappa_{ult} = \kappa_R$ (no plateau).  The sweep ends naturally at
  fracture.  No special case is needed.

**Plastic rotation capacity as post-processing:**

$$
\theta_p(\kappa_{hog}) = \int_0^{L_a} \max(\kappa(x) - \kappa_R,\; 0)\, dx
$$

where $\kappa(x) = f^{-1}(M_x(x))$ uses the ascending-branch inverse.  This integral
is nonzero only in the yielded zone near the support and is evaluated after the
solver has converged — it never enters the compatibility equation.

**Comparison with Strategy A:**

For the plateau, Strategy A prescribes $M_{hog} = M_R$ and sweeps $q$ directly.
Strategy C sweeps $\kappa_{hog}$ and recovers $q$ from compatibility.  Both deliver
the same $(q, M_{hog})$ pairs; Strategy C is strictly more general because it is
a single continuous parametrization with no phase-detection logic and works for
any M-κ shape.

**Implementation change from the current solver:**
- Current: outer loop over $q$, inner `brentq` over $M_{hog}$.
- Strategy C: outer loop over $\kappa_{hog}$ (from M-κ curve), inner `brentq` over $q$.
- `get_kappa_x_from_M` is called only on interior sections ($|M| < M_R$) — always
  on the ascending branch — so the inversion is always unique.

---

## 8 — Implementation Plan: Strategy C Refactoring

This section translates Strategy C into a concrete refactoring of the current solver.
The goal is a **minimal change**: keep the outer loop over $q$, but replace the inner
`brentq` unknown from $M_{hog}$ to $\kappa_{hog}$.

### 8.1 — Sign convention: $\kappa_{hog}$ as a magnitude

The current solver uses $M_{hog} \geq 0$ as the **magnitude** of the hogging moment;
the actual (signed) end-moment entered into the span is $-M_{hog} < 0$.  Strategy C
follows the **same convention**: $\kappa_{hog} \geq 0$ is the magnitude of the hogging
curvature.  The signed curvature at the support is $-\kappa_{hog}$.

This keeps the refactoring minimal: all call sites that currently pass $-M_{hog}$ as
an end-moment argument are unchanged; only the mapping $M_{hog} = f(\kappa_{hog})$
is added before those calls.

> **Why not use signed $\kappa_{hog} < 0$?**
> The existing bracket for `brentq` over $M_{hog}$ is $[0, M_R]$ (non-negative).
> Keeping the same sign class for the new unknown avoids rewriting all the
> sign-dependent code in `_end_phi` and `M_profiles`.

### 8.2 — Admissible domain and the correct branch

The hogging M-κ curve is the **negative branch**:
$(\kappa_{neg},\, M_{neg})$ with $\kappa_{neg} < 0$ and $M_{neg} < 0$.
`MKappaAnalysis` stores this in `kappa_neg_values` and `M_neg_values`
when `solve_mode='both'` (the default for the cross-section object; note that
`BeamDeflectionAnalysis.mk` currently requests `solve_mode='positive'` and relies
on a sagging-branch mirror for the hogging zone — see §8.7).

The ascending sub-segment of the hogging branch runs from $(0, 0)$ to the peak
hogging moment:

$$
\kappa_{R,hog} \;=\;
\bigl|\kappa_{neg\_values}\bigl[\operatorname{argmin}(M_{neg\_values})\bigr]\bigr|
\qquad \text{(magnitude at peak hogging moment)}
$$

$$
M_{R,hog} \;=\;
\bigl|M_{neg\_values}\bigl[\operatorname{argmin}(M_{neg\_values})\bigr]\bigr|
\qquad [\text{kN·m}]
$$

The admissible domain for the new unknown is therefore:

$$
\kappa_{hog} \in \bigl[0,\; \kappa_{R,hog}\bigr]
$$

Note: $\kappa_{R,hog} \neq \kappa_{R,sag}$ for asymmetric sections (different
top/bottom reinforcement), so the hogging branch must be queried explicitly.

### 8.3 — Forward map $f(\kappa_{hog})$

The forward map evaluates $M_{hog}$ from $\kappa_{hog}$ using the hogging branch
ascending sub-segment (both arrays expressed as magnitudes):

```python
idx_peak_hog = int(np.argmin(mk.M_neg_values))          # most-negative M
kappa_hog_ref = np.abs(mk.kappa_neg_values[:idx_peak_hog + 1])   # magnitudes, ascending
M_hog_ref_Nmm = np.abs(mk.M_neg_values[:idx_peak_hog + 1]) * 1e6  # N·mm magnitudes

M_hog = float(np.interp(kappa_hog, kappa_hog_ref, M_hog_ref_Nmm))  # N·mm
```

This is identical in structure to the hogging interpolation already inside
`get_kappa_x_from_M` — no new logic, just the same table queried by the
forward direction.

### 8.4 — Residuum function with $\kappa_{hog}$ as primary unknown

$$
R(\kappa_{hog};\; q) \;=\;
\varphi_L\!\bigl(L_a,\; -f(\kappa_{hog})\bigr)
\;-\;
\varphi_R\!\bigl(0,\; -f(\kappa_{hog})\bigr)
$$

where $f(\kappa_{hog})$ returns the **magnitude** $M_{hog} \geq 0$, and
$-f(\kappa_{hog})$ is the signed (negative) end-moment passed to `_end_phi` —
identical to the current `residuum(M_hog)` call pattern.

### 8.5 — `brentq` bracketing as the domain guard

`scipy.optimize.brentq(R, a, b)` guarantees that **all function evaluations remain
within** $[a,\, b]$.  Brent's method falls back to bisection whenever a secant or
inverse-quadratic step would exit the bracket.  No clamping inside $R$ is needed.

Setting:

$$
a = \varepsilon_\kappa = 10^{-8}\,\kappa_{R,hog},
\qquad
b = \kappa_{R,hog}
$$

ensures that $R$ is **never called with $\kappa_{hog} > \kappa_{R,hog}$**.
Interior sections always have $|M_x(x)| < f(\kappa_{hog}) \leq M_{R,hog}$, so
`get_kappa_x_from_M` operates strictly on the ascending branch — ill-posedness
is structurally excluded.

### 8.6 — Failure detection via bracket pre-check

When $q$ approaches the failure load $q_u$, the root $\kappa_{hog}^*$ approaches
$\kappa_{R,hog}$ from below.  At $q \geq q_u$ no root exists in the admissible
domain; both bracket endpoints carry the same sign.

**Protocol before calling `brentq`:**

```python
R_lo = residuum_kappa(kappa_eps, q)
R_hi = residuum_kappa(kappa_R_hog, q)

if R_lo * R_hi >= 0:
    raise CompatibilityNoRoot(q)   # failure load reached
```

`brentq` itself raises `ValueError` on a bad bracket, but a named exception is
cleaner — it carries `q` and lets the outer loop report the bracketed failure load
without relying on exception message parsing.

### 8.7 — Why clamping is the wrong approach

Clamping $\kappa_{hog}$ to $\kappa_{R,hog}$ inside $R$ would:

1. Make $R$ flat for $\kappa_{hog} > \kappa_{R,hog}$: $R(\kappa) = R(\kappa_{R,hog})$ = const.
2. Brent's method would interpret the collapsing bracket as convergence and
   silently return $\kappa_{R,hog}$ even when no physical root exists at that load.
3. The outer loop would never detect failure — it would accumulate false solutions
   at the capacity boundary.

The bracket approach avoids all three: the solver either finds a valid root or
raises `CompatibilityNoRoot`.

### 8.8 — Outer loop

```python
results = []
for q in q_values:
    try:
        R_lo = residuum_kappa(kappa_eps, q)
        R_hi = residuum_kappa(kappa_R_hog, q)
        if R_lo * R_hi >= 0:
            raise CompatibilityNoRoot(q)
        kappa_hog = brentq(
            lambda k: residuum_kappa(k, q),
            kappa_eps,
            kappa_R_hog,
            xtol=1e-8 * kappa_R_hog,
        )
        M_hog = forward_map(kappa_hog)          # forward map, N·mm magnitude
        results.append(dict(q=q, kappa_hog=kappa_hog, M_hog=M_hog))
    except CompatibilityNoRoot:
        q_u = q                                 # failure between q_prev and q
        break
```

### 8.9 — Changes from the current implementation

| Aspect | Current ($M$-controlled) | Strategy C ($\kappa$-controlled) |
|--------|--------------------------|----------------------------------|
| Inner `brentq` unknown | $M_{hog} \in [0, M_{R,hog}]$ | $\kappa_{hog} \in [\varepsilon, \kappa_{R,hog}]$ |
| Sign convention | magnitude (non-negative) | magnitude (non-negative) — same |
| M-κ call at support | `get_kappa_x_from_M(M_R)` — ill-posed on plateau | `forward_map(κ_hog)` — always unique |
| Interior sections | `get_kappa_x_from_M` at $\|M\| \leq M_R$ | same, unchanged |
| $\kappa_R$ reference | sagging branch peak | **hogging branch peak** $\kappa_{R,hog}$ |
| Domain guard | none (relies on M ≤ M_R bracket) | bracket $[\varepsilon, \kappa_{R,hog}]$ + pre-check |
| Failure detection | no sign change → `brentq` error | `R_lo * R_hi ≥ 0` → `CompatibilityNoRoot` |
| Steel plateau ($q > q_{field,u}$) | fails (ill-posed inversion) | works ($f(\kappa_{hog})$ stays on plateau) |
| CFRP | works ($\kappa_R = \kappa_{ult}$) | works (sweep ends at $\kappa_{R,hog}$ naturally) |
| $\theta_p$ | unavailable | post-processing: $\int \max(\kappa - \kappa_R, 0)\, dx$ |

### 8.10 — `solve_mode` requirement and the symmetric fallback

`MKappaAnalysis` exposes the hogging branch via `kappa_neg_values` / `M_neg_values`
only when `solve_mode='both'` (the class default).

**Current situation:** `BeamDeflectionAnalysis.mk` requests `solve_mode='positive'`,
so `kappa_neg_values` is empty.  The symmetric fallback inside `get_kappa_x_from_M`
mirrors the sagging branch for the hogging zone.  Strategy C must consistently use
the **same branch** for the forward map and the bracket endpoint:

```python
if len(mk.kappa_neg_values) > 0:
    # Asymmetric section: use true hogging branch
    idx_peak = int(np.argmin(mk.M_neg_values))
    kappa_R_hog = float(np.abs(mk.kappa_neg_values[idx_peak]))
    kappa_hog_ref = np.abs(mk.kappa_neg_values[:idx_peak + 1])
    M_hog_ref_Nmm = np.abs(mk.M_neg_values[:idx_peak + 1]) * 1e6
else:
    # Symmetric fallback: mirror sagging branch
    idx_peak = int(np.argmax(mk.M_values))
    kappa_R_hog = float(mk.kappa_values[idx_peak])
    kappa_hog_ref = mk.kappa_values[:idx_peak + 1]
    M_hog_ref_Nmm = mk.M_values[:idx_peak + 1] * 1e6
```

For asymmetric sections (different top/bottom reinforcement), change
`BeamDeflectionAnalysis.mk` to `solve_mode='both'` to activate the true hogging
branch and avoid the symmetric approximation error.

---

## 9 — Strategy D: $q$-solving at prescribed $\kappa_{hog}$

Strategy D inverts the roles of kinematic and static variable relative to the current
Strategy C implementation: $\kappa_{hog}$ is the outer sweep parameter and the
distributed load $q$ is the inner unknown.

### 9.1 — Change of primary unknown

**Strategy C (current):** $q$ is prescribed; the inner `brentq` solves for
$\kappa_{hog} \in [0, \kappa_{R,hog}]$.

**Strategy D:** $\kappa_{hog}$ is prescribed (stepped through the ascending
sub-segment of the hogging M-κ branch); the inner `brentq` solves for $q$.

The rotation-compatibility condition is unchanged:

$$
R(q;\; \kappa_{hog}) \;=\;
\varphi_L\!\bigl(L_a;\; q,\; f(\kappa_{hog})\bigr)
\;-\;
\varphi_R\!\bigl(0;\; q,\; f(\kappa_{hog})\bigr) \;=\; 0
$$

where $f(\kappa_{hog})$ is the same forward map $\kappa_{hog} \mapsto M_{hog}$ as in
Strategy C, and both spans carry **the same** distributed load $q$ (the physical
constraint that links the two fields).

### 9.2 — Natural bracketing of the inner `brentq`

For fixed $M_{hog} = f(\kappa_{hog}) > 0$, the residuum has analytically known signs
at the bracket endpoints.

**Lower bound $q = 0$:** With no UDL, only the prescribed end moments $\pm M_{hog}$
load the spans.  For each span in isolation (SSB, elastic with uniform stiffness $EI$):

- *Left span* — end moment $-M_{hog}$ at $x = L_a$:
$$
\varphi_L(L_a;\; 0,\; M_{hog}) = -\frac{M_{hog}\,L_a}{3\,EI} < 0
$$

- *Right span* — end moment $-M_{hog}$ at $x = 0$:
$$
\varphi_R(0;\; 0,\; M_{hog}) = +\frac{M_{hog}\,L_b}{3\,EI} > 0
$$

Hence:

$$
R(0;\; M_{hog}) = -\frac{M_{hog}\,L_a}{3\,EI} - \frac{M_{hog}\,L_b}{3\,EI}
= -\frac{M_{hog}(L_a + L_b)}{3\,EI} < 0
$$

This inequality holds for **any** $M_{hog} > 0$, **any** span ratio $L_a / L_b$, and in
the **nonlinear** case as well, because at $q = 0$ the moment distributions are
anti-symmetric: the left span carries sagging moments (forward M-κ branch, unique) and
the right span carries hogging moments (hogging branch, also unique on the ascending
sub-segment).  The opposite signs of $\varphi_L$ and $\varphi_R$ are therefore
preserved in the nonlinear regime — the sign of $R(q=0)$ is guaranteed negative.

**Upper bound $q = q_\mathrm{hi}$:** In the elastic limit, the residuum is:

$$
R(q;\; M_{hog}) \;\approx\;
\frac{q\,L_a^3}{12\,EI} + \frac{q\,L_b^3}{12\,EI}
- \frac{2\,M_{hog}(L_a + L_b)}{3\,EI}
\;\to\; +\infty \quad (q \to \infty)
$$

A safe upper bound is $q_\mathrm{hi} = 4\,q_\mathrm{el}$ where the elastic compatibility
load is:

$$
q_\mathrm{el} = \frac{8\,M_{hog}\,(L_a + L_b)}{L_a^3 + L_b^3}
\qquad \bigl(\text{reduces to } 8\,M_{hog}/L^2 \text{ for equal spans}\bigr)
$$

The bracket $\bigl[0,\, 4\,q_\mathrm{el}\bigr]$ requires **no pre-check** — $R(0) < 0$
is analytically guaranteed, eliminating the `R_lo * R_hi ≥ 0` test that Strategy C
requires before each `brentq` call.

### 9.3 — Outer loop: stepping through the M-κ table

The outer parameter steps directly through the ascending sub-segment of the hogging
M-κ branch stored in `mk.kappa_neg_values` / `mk.M_neg_values`:

```python
idx_peak   = int(np.argmin(mk.M_neg_values))         # peak hogging index
kappa_sweep = -mk.kappa_neg_values[:idx_peak + 1]     # magnitudes, ascending

results = []
for kappa_hog in kappa_sweep:
    M_hog = forward_map(kappa_hog)                    # N·mm   (prepend origin)
    La, Lb = span_left.L, span_right.L
    q_el   = 8 * M_hog * (La + Lb) / (La**3 + Lb**3) # elastic estimate
    q = brentq(
        lambda q_: residuum_q(q_, M_hog),
        0.0,
        4 * q_el,
        xtol=1e-4 * q_el,
    )
    results.append((kappa_hog, M_hog / 1e6, q))       # [mm⁻¹], [kN·m], [N/mm]
```

Key observations:

1. **No load grid is needed.** The outer discretisation is inherited from the M-κ
   table — the same $n_\kappa$ steps used for the section analysis.
2. **The failure load $q_u$ is the last entry.** When `kappa_hog = kappa_R_hog`
   (the final step), the returned $q$ is the ultimate load directly.  No
   `CompatibilityNoRoot` detection is required.
3. **The origin is included.** Prepending $(0, 0)$ to `forward_map` (see §8.3) ensures
   the very first step at `kappa_sweep[0]` yields a nonzero bracket for `brentq`.

### 9.4 — Residuum implementation

```python
def residuum_q(q: float, M_hog: float) -> float:
    """R(q; M_hog) = φ_L(L_a) − φ_R(0), M_hog prescribed."""
    phi_L = _end_phi(span_left,  q, 0.0,    -M_hog, 'right')
    phi_R = _end_phi(span_right, q, -M_hog,  0.0,   'left')
    return phi_L - phi_R
```

This is structurally identical to `residuum(M_hog)` in the current solver.  The calls
to `get_M_x(q, …)`, `get_kappa_x_from_M(…)`, and `_phi_ssb(…)` inside `_end_phi`
are **unchanged**.  All interior sections have $|M_x(x)| < M_{hog} = f(\kappa_{hog})$,
so the M-κ inversion is unique — the same well-posedness guarantee as Strategy C.

The key difference is that `q` is now the free variable passed to `brentq`, while
`M_hog` is a fixed parameter for each outer step.

### 9.5 — Extension to the steel plateau

If the M-κ table contains the post-peak segment ($\kappa_{hog} > \kappa_R$,
$M_{hog} \approx M_R$), the outer loop extends without any phase-detection:

$$
f(\kappa_{hog}) \approx M_R = \text{const} \quad \text{for } \kappa_{hog} > \kappa_R
$$

The residuum $R(q;\; M_R)$ has the same bracket structure and `brentq` continues to
find increasing $q$ values — the ascending $q(\kappa_{hog})$ curve continues past
$\kappa_R$ without a kink.  This is equivalent to Strategy A on the plateau but without
any phase-change logic.

### 9.6 — Comparison with Strategies C and A

| Aspect | Strategy A (plateau only) | Strategy C (current) | **Strategy D** |
|--------|--------------------------|---------------------|----------------|
| Outer loop | $q$ (user grid) | $q$ (user grid) | **$\kappa_{hog}$ (M-κ table)** |
| Inner unknown | $\theta_p$ (explicit DOF) | $\kappa_{hog}$ (brentq) | **$q$ (brentq)** |
| Phase detection (elastic/plastic) | Required | None | **None** |
| Bracket pre-check | — | `R_lo·R_hi ≥ 0`? | **Not needed** |
| Failure load $q_u$ | at $\theta_p = \theta_{p,u}$ | `CompatibilityNoRoot` | **last outer step** |
| Plateau (steel) | native | requires extended M-κ | **natural continuation** |
| CFRP | N/A | works ($\kappa_R = \kappa_{ult}$) | **works** |
| Calls to `_end_phi` | modified | unchanged | **unchanged** |

### 9.7 — When Strategy D is preferable

**Prefer Strategy D when:**

- The **ultimate load $q_u$** is the primary output — it emerges from the last outer
  step without a search.
- The **M-κ curve is the driving discretisation** (section design loops, sensitivity
  studies where the section varies and $q_u$ is recomputed each time).
- **Plastic redistribution on the steel plateau** is needed without restructuring the
  solver.
- A **guaranteed valid bracket** for the inner `brentq` is important (robustness in
  automated parameter studies).

**Prefer Strategy C (current) when:**

- **Specific load levels** are prescribed (SLS checks at characteristic loads,
  comparison against measured data at known $q$).
- **Intermediate $\kappa_{hog}$ histories** at user-defined load steps are needed.

---

## 10 — Summary

| Issue | Conclusion |
|-------|-----------|
| Does M-κ already contain yielding? | Yes — but M-controlled inversion is ill-posed on the plateau |
| Does introducing $\theta_p$ double-count? | No — it is the integral of the plateau curvature, an equivalent representation |
| What does $\kappa_R$ denote? | Curvature at **peak moment** (ascending branch end), not yield curvature |
| Why does the solver fail at $q > q_{field,u}$? | `get_kappa_x_from_M` must invert $M \mapsto \kappa$ at the support where $M = M_R$ — ill-posed on steel plateau |
| Does curvature continuity add an equation? | No — automatically satisfied; but it motivates using $\kappa_{hog}$ as primary variable |
| Best practical fix (any material) | **Strategy C**: sweep $\kappa_{hog}$, evaluate $M_{hog} = f(\kappa_{hog})$ forward, solve compatibility for $q$ |
| Why Strategy C resolves ill-posedness | Support section uses forward map (unique); interior sections have $\|M\| < M_R$ (ascending branch) |
| Steel plateau in Strategy C | $\kappa_{hog} > \kappa_R$: $M_{hog} \approx M_R$, $q$ increases — redistribution traced continuously |
| CFRP in Strategy C | Sweep ends at $\kappa_R$ naturally — no special case |
| $\theta_p$ role in Strategy C | Post-processing: $\int \max(\kappa - \kappa_R, 0)\, dx$ over yielded zone |
| Strategy A (steel only) | Prescribe $M_{hog} = M_R$, sweep $q$ — equivalent to Strategy C on the plateau, requires phase detection |
| Strategy B | Deformation-controlled BVP (FE) — rigorous but requires stiffness matrix and NR solver |
