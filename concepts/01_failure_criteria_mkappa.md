# Failure Mode Identification in M-κ Analysis

*Scite codebase concepts — relates to `MKappaAnalysis`, `AnaFRPBending`, `ttc_derivation.ipynb`*

---

## 1. The Question

When `MKappaAnalysis.solve()` terminates at a peak moment, it currently prints
*"equilibrium lost, section failed"* — but **which component failed?**
The answer matters for:

- Educational annotation of M-κ diagrams (failure marker symbol, colour, label)
- Design optimisation (drive toward simultaneous failure for minimum material use)
- Understanding whether a wider flange changed the governing mode
- Connecting numerical results back to the analytical TTC/ACI framework

---

## 2. What Failure Means Here

In a cross-section under monotonically increasing curvature, **two strain limits
define the boundaries of admissible states:**

| Material | Strain limit | Symbol | Meaning |
|----------|-------------|--------|---------|
| Concrete (top fiber) | Ultimate compressive strain | $\varepsilon_{cu}$ | Crushing / spalling |
| Reinforcement (bottom fiber) | Ultimate tensile strain | $\varepsilon_{ud}$ | Steel fracture or CFRP rupture |

The curvature at which *both* limits are reached simultaneously defines the
**balanced curvature** $\kappa_b$ and the corresponding balanced reinforcement
ratio $\rho_{fb}$.

**Important:** the solver parametrises each curvature step by finding the bottom
strain $\varepsilon_{bot}$ that satisfies $N = 0$ (or $N = N_{Ed}$). At each step the top
strain is then:

$$
\varepsilon_{top} = \varepsilon_{bot} - \kappa \cdot h
$$

Failure is reached when the Brent-method bracket becomes degenerate — i.e. the
force residual no longer changes sign in the admissible interval. This happens
at precisely the curvature where one strain limit is hit.

### Answer to the curve-termination question

> *All M-κ curves in the flange-width sweep (`02_verify_cs_shape_crc.ipynb`) do
> show the peak.* The solver terminates when equilibrium can no longer be
> satisfied, which occurs in the post-peak regime where the moment is already
> falling. The last point on each plotted curve is at or very near the true
> M-peak. The "equilibrium lost" message is the stopping criterion, not an
> error — it simply means the section has exhausted its capacity.

---

## 3. Three Candidate Criteria for Failure Mode Identification

### 3.1 Strain utilisation at peak moment (recommended)

Compute the **utilisation ratio** for each material at the state corresponding
to M-peak:

$$
\eta_c = \frac{|\varepsilon_{top}^{\,\text{peak}}|}{|\varepsilon_{cu}|}
\qquad
\eta_f = \frac{\varepsilon_{bot}^{\,\text{peak}}}{\varepsilon_{ud}}
$$

| Result | Failure mode |
|--------|-------------|
| $\eta_c > \eta_f$ | **Concrete crushing** governs |
| $\eta_f > \eta_c$ | **Reinforcement rupture** governs |
| $\eta_c \approx \eta_f \approx 1$ | **Balanced / simultaneous** |

**Why strain, not stress?**

For steel reinforcement the stress–strain curve has a plateau: $\sigma = f_{yd}$
for all $\varepsilon \geq \varepsilon_{yd}$. At M-peak the reinforcement is
almost always on the plateau, so the stress ratio $\sigma_s / f_{yd} = 1$
regardless of how deeply into yielding the section is. The strain utilisation
$\eta_f$ is therefore *more informative than* the stress ratio for steel.

For the EC2 parabola-rectangle model the compressive stress also saturates at
$f_{cd}$ for $|\varepsilon_c| \in [\varepsilon_{c2}, \varepsilon_{cu2}]$. The
maximum *stress* is reached at $\varepsilon_{c2}$ (start of the plateau), well
before crushing at $\varepsilon_{cu2}$. Therefore, checking
$\sigma_{c,max} / f_{cd} = 1$ only tells you that the plateau was entered — not
that crushing occurred. The strain limit $\varepsilon_{cu2}$ is the unique
failure boundary.

For a **general nonlinear concrete law** (e.g. Sargin, Popovics, or a
user-defined curve), the peak stress may be at an intermediate strain and the
post-peak branch may allow large strains before structural failure. In all
cases, the *ultimate compressive strain* $\varepsilon_{cu}$ (whether taken from
EC2 or from the model's own definition) is the controlling boundary — the stress
at that strain may be significantly below $f_{cm}$. **Therefore strain-based
utilisation is always unambiguous and independent of the constitutive law shape.**

### 3.2 Post-peak force resultant evolution (not recommended as primary)

The user correctly identified this idea: at and after M-peak, observe which
component's force resultant is decreasing:

- If $F_c$ drops while $F_s$ is stable → concrete governs
- If $F_s$ drops while $F_c$ is still growing → reinforcement governs

This is physically rigorous, but practically limited:

1. **The solver may not converge past the peak.** For brittle CFRP the
   post-peak regime is extremely narrow; for steep concrete softening it may
   not exist at all within the admissible strain bracket.
2. It requires at least two post-peak converged points.
3. For a sharp brittle failure (CFRP rupture) both $F_c$ and $F_s$ drop
   simultaneously in the first post-peak step — it provides no differentiation.

The post-peak method is useful for ductile steel RC where the post-yield plateau
is wide and the concrete compression zone evolves clearly. It is unreliable for
CRC.

### 3.3 Lever arm evolution (qualitative indicator only)

The internal moment arm $z = M / F_T$ (distance between the compression
resultant $C$ and the tension resultant $T$) evolves differently depending on
the governing mode:

- **Concrete-governed:** the neutral axis depth $c$ increases as more concrete
  enters the crushing plateau, reducing the effective lever arm. $z$ decreases
  at peak and post-peak.
- **Reinforcement-governed:** the tension force $F_T = A_s f_{fu}$ stays
  constant up to rupture; the neutral axis shifts to maintain equilibrium as
  $\kappa$ increases, but $z$ changes relatively little up to the peak.

The lever arm signature is useful for educational explanation but is not a
sharp numerical criterion and requires access to $F_c$ separately from $M$.

---

## 4. The Balanced Reinforcement Ratio $\rho_{fb}$

The failure mode is determined *structurally* by whether the actual
reinforcement ratio $\rho$ is above or below the **balanced ratio** $\rho_{fb}$:

$$
\rho_{fb} = \text{reinforcement ratio at which } \eta_c = \eta_f = 1 \text{ simultaneously}
$$

### ACI 440.1R-15 (rectangular stress block, valid for any FRP)

$$
\rho_{fb} = 0.85\,\beta_1 \,\frac{f_{cm}}{f_{fu}} \cdot
            \frac{E_f\,\varepsilon_{cu}}{E_f\,\varepsilon_{cu} + f_{fu}}
$$

where $\beta_1$ is the equivalent stress block depth factor.

### TTC model (bilinear concrete — triangular + trapezoidal)

The derivation in `notebooks/mkappa/material_utilization/ttc_derivation.ipynb`
gives a closed-form $\rho_{fb}$ based on the bilinear parameters
$(\sigma_{cy}, \varepsilon_{cy}, \sigma_{cu}, \varepsilon_{cu})$. This is more
accurate for EC2-grade concretes than the ACI rectangular block.

In both formulations the failure mode test is:

$$
\rho < \rho_{fb} \;\Rightarrow\; \text{Reinforcement-governed (FRP/steel rupture)}
\qquad
\rho > \rho_{fb} \;\Rightarrow\; \text{Concrete-governed (crushing)}
$$

---

## 5. Material Utilisation Factors $\psi_c$ and $\psi_f$

The TTC-based analytical framework (see `AnaFRPBending`, `ttc_derivation.ipynb`)
expresses the *degree of underutilisation* of the non-governing material:

$$
\psi_c = \frac{|\varepsilon_{top}^{\,\text{peak}}|}{|\varepsilon_{cu}|}
       = \eta_c \leq 1
\qquad
\psi_f = \frac{\sigma_f^{\,\text{peak}}}{f_{fu}}
       = \eta_f^{\,\sigma} \leq 1
$$

At the balanced point both $\psi_c = 1$ and $\psi_f = 1$.  
For $\rho < \rho_{fb}$: $\psi_f = 1$, $\psi_c < 1$ (concrete underutilised).  
For $\rho > \rho_{fb}$: $\psi_c = 1$, $\psi_f < 1$ (reinforcement underutilised).

**Note on $\psi_f$ for steel:** after yielding the stress is fixed at $f_{yd}$,
so $\psi_f^{\,\sigma} = 1$ trivially. The more informative quantity is
$\eta_f^{\,\varepsilon} = \varepsilon_s / \varepsilon_{ud}$, which reveals how
far the section is from steel fracture — a meaningful ductility indicator.

---

## 6. Practical Implementation in `MKappaAnalysis`

The recommended approach is a lightweight post-processing step on the solved
M-κ data:

```python
def get_failure_mode(mk: MKappaAnalysis) -> dict:
    """
    Identify the governing failure mode from the peak-moment state.

    Returns:
        dict with keys:
          'mode'       : 'concrete' | 'reinforcement' | 'balanced'
          'eta_c'      : concrete strain utilisation [0, 1+]
          'eta_f'      : reinforcement strain utilisation [0, 1+]
          'eps_top'    : top fibre strain at M-peak [–]
          'eps_bot'    : bottom fibre strain at M-peak [–]
    """
    if mk.M_values is None or len(mk.M_values) == 0:
        return {'mode': 'unknown'}

    idx = int(np.argmax(mk.M_values))
    kappa  = mk.kappa_values[idx]
    eps_bot = mk.eps_bot_values[idx]
    eps_top = eps_bot - kappa * mk.cs.h_total   # negative = compression

    eps_cu  = abs(mk.cs.concrete.eps_cu2_computed)
    # Take eps_ud from the first (main) reinforcement layer
    eps_ud  = getattr(mk.cs.reinforcement.layers[0].material, 'eps_ud', None)
    if eps_ud is None:
        eps_ud = getattr(mk.cs.reinforcement.layers[0].material, 'eps_cr', 0.025)

    eta_c = abs(eps_top) / eps_cu
    eta_f = eps_bot / eps_ud

    tol = 0.05   # within 5% → "balanced"
    if abs(eta_c - eta_f) < tol:
        mode = 'balanced'
    elif eta_c > eta_f:
        mode = 'concrete'
    else:
        mode = 'reinforcement'

    return {
        'mode': mode,
        'eta_c': float(eta_c),
        'eta_f': float(eta_f),
        'eps_top': float(eps_top),
        'eps_bot': float(eps_bot),
    }
```

This computes entirely from data already present on the solved `mk` object.
No re-evaluation of the section or the solver is needed.

---

## 7. The CFRP T-Section Flange-Width Example

The flange-width sweep in `02_verify_cs_shape_crc.ipynb` illustrates the mode
transition cleanly:

| b_f [mm] | M_peak [kN·m] | Expected mode |
|----------|--------------|---------------|
| 50 (rect) | 8.7  | **CFRP rupture** — tiny concrete area, very little compression → concrete far from crushing |
| 100       | 13.1 | CFRP rupture |
| 150       | 17.4 | CFRP rupture |
| 200       | 21.8 | CFRP rupture → approaching balanced |
| 300       | 28.9 | Transition zone |
| 400       | 31.1 | **Concrete governs** — wide flange supplies large compression force; CFRP still at $< f_{fu}$ |

At small b_f the compression area is tiny (web only), so the neutral axis must
sit very high to balance the CFRP tension force. The concrete reaches its
crushing strain at a large curvature. But the CFRP failure strain
$\varepsilon_{cr} = f_{fu}/E_f \approx 0.012$ is reached at the bottom fibre
at a much smaller curvature — so CFRP governs.

At large b_f the wide flange generates a much larger compression resultant per
unit curvature increment. The neutral axis can sit lower, giving a larger lever
arm and higher moment capacity. The concrete compression zone reaches
$\varepsilon_{cu2}$ before the bottom CFRP reaches $\varepsilon_{cr}$ —
concrete governs.

This transition is precisely the ACI balanced failure condition, but here
realised numerically via the full parabola-rectangle model and the T-shaped
geometry.

---

## 8. Edge Cases and Limitations

### Multiple reinforcement layers
If there are both tension and compression steel layers, compute $\eta_f$
independently for each and take the maximum. For compression reinforcement the
equivalent check is $|\varepsilon_{layer}| / \varepsilon_{s,\text{limit}}$ 
(e.g. $\varepsilon_{cu2}$ for bars in the compression zone that are not
buckle-restrained, since they are effectively governed by the surrounding concrete).

### Axial force ($N_{Ed} \neq 0$)
Under significant axial compression both $\varepsilon_{top}$ and
$\varepsilon_{bot}$ shift in the compressive direction. The balanced curvature
concept still holds, but $\rho_{fb}$ changes. The strain-utilisation criterion
(`η_c`, `η_f`) remains valid without modification.

### Nonlinear concrete laws with post-peak branch
For a Popovics or user-defined law, the ultimate strain $\varepsilon_{cu}$ must
be defined explicitly. If a softening branch is used for solver robustness (as
in `CarbonReinforcement.post_peak_factor`), care must be taken not to confuse
the "numerical softening tail" with genuine post-peak material behavior. Only
strains up to the *physical* rupture strain should be used in $\eta_f$.

### Zero-moment states
At κ → 0, $\eta_c → 0$ and $\eta_f → 0$ by construction. The failure mode is
only meaningful at or near M-peak.

---

## 9. Relationship to Existing Code

| Component | Status | Notes |
|-----------|--------|-------|
| `MKappaAnalysis` | No failure detection | `solve()` stops at equilibrium loss; no `eta_c`/`eta_f` stored |
| `AnaFRPBending` | Full $\rho_{fb}$, $\psi_c$, $\psi_f$ | Analytical only, TTC model |
| Legacy `MKappa`/`MKappaRho` | ACI $\rho_{fb}$ + stress readout | `legacy/` folder, not used by new solver |
| `ttc_derivation.ipynb` | Most complete derivation | Sympy-based, validated against experiments |
| `NMAssessment` | Global $M_{Ed}/M_R$ only | No material-level information |

**Recommended next step:** add `get_failure_mode()` as a method on `MKappaAnalysis`
and use its output to:
1. Place a small marker (◆ for concrete, ✕ for CFRP, ○ for balanced) at the
   terminal point of each M-κ curve.
2. Include $\eta_c$ and $\eta_f$ values in the convergence report.
3. Label the 4-panel `plot_summary()` figure with the identified mode.
