# Concept: Tension Stiffening in M-κ Analysis

*Scite codebase concepts — relates to `CrossSection`, `StressStrainProfile`,
`SteelReinforcement`, `EC2ParabolaRectangle`, `BeamDeflectionAnalysis`*

---

## 1. Motivation

The current M-κ solver treats the cracked cross-section using:

- **Concrete**: zero tensile strength (EC2 parabola-rectangle in compression,
  nothing in tension).
- **Reinforcement**: bare bilinear elastic-plastic law (B500B, etc.).

This is correct for ultimate-limit-state design but overestimates crack widths
and underestimates stiffness under service loads.  In reality, the concrete
between cracks still transfers tension to the rebar via bond — the
*tension stiffening* effect.  Its magnitude is significant:

- It raises the effective steel stiffness (lower strains for a given moment).
- It dominates the difference between the uncracked stiffness $EI_g$ and the
  fully cracked stiffness $EI_{cr}$ in the service-load range.
- It is the mechanism that EC2 \S7.4.3 captures via the interpolation
  coefficient $\zeta$ and that Eurocode recommends accounting for in deflection
  calculations.

---

## 2. Modelling Philosophy: Tension Stiffening Ascribed to Reinforcement

Two physically equivalent ways exist to incorporate tension stiffening:

| Option | Where the effect lives | Remark |
|--------|------------------------|--------|
| A | **Concrete** gets a post-cracking tension branch (fictitious crack model, CEB-FIP 1990) | Requires modifying concrete $\sigma$-$\varepsilon$; double-counts if real $f_{ct}$ is also present in concrete |
| B | **Concrete** contributes zero tension; the *effective reinforcement* carries the smeared bond-stress contribution | Clean separation: concrete = pure compression; rebar = bare steel + stiffening |

We adopt **Option B**.  The concrete model stays exactly as-is (no tensile
stress), and the additional tension contribution from concrete between cracks is
added to the reinforcement response as an *effective* constitutive law.

---

## 3. The ACK Model for Multiple Cracking

The Aveston-Cooper-Kelly (ACK) model was originally developed for
fibre-reinforced composites but is directly applicable to RC under uniaxial
tension.

### 3.1 Uniaxial reference configuration

Consider a reinforced concrete prism with:

- $A_s$ = steel area, $E_s$ = steel modulus, $\rho = A_s / A_c$ where $A_c$
  is the total concrete cross-section
- $A_{c,\text{eff}}$ = effective concrete area in tension around the bar
  (geometry-dependent, see §5)
- $\rho_\text{eff} = A_s / A_{c,\text{eff}}$
- Concrete tensile strength $f_{ct}$ and modulus $E_c$

Three characteristic strains define the ACK response in the uniaxial prism:

$$
\varepsilon_1 = \frac{f_{ct}}{E_c}\bigl(1 - \rho_\text{eff}\bigr)
$$

This is the strain at first cracking (the composite strains up to this point
as an uncracked section).

$$
\varepsilon_3 = \frac{f_{ct}}{\rho_\text{eff}\,E_s}
  + \frac{f_{ct}}{2\,E_c}\bigl(1 - \rho_\text{eff}\bigr)
$$

This is the strain at saturation of multiple cracking (all cracks have formed;
the concrete between cracks is at the average tensile stress $\tfrac{1}{2}f_{ct}$).
Beyond $\varepsilon_3$ the response follows the bare steel stiffness $A_s E_s$.

The stress carried by the *effective reinforcement* (steel + smeared concrete
contribution, per unit area $A_s$) is:

$$
\sigma_\text{eff}(\varepsilon_s) = \begin{cases}
  E_s\,\varepsilon_s + \dfrac{(1-\rho_\text{eff})\,E_c}{\rho_\text{eff}}\,\varepsilon_s
    & \varepsilon_s < \varepsilon_1 \quad \text{(uncracked composite)} \\[8pt]
  \sigma_1 + \text{[cracking plateau branch]}
    & \varepsilon_1 \leq \varepsilon_s \leq \varepsilon_3 \\[6pt]
  E_s\bigl(\varepsilon_s - \varepsilon_3\bigr) + \sigma_3
    & \varepsilon_s > \varepsilon_3 \quad \text{(fully cracked, bare steel)}
\end{cases}
$$

where $\sigma_1 = E_s\,\varepsilon_1 (1 + (1-\rho_\text{eff})\,E_c/(\rho_\text{eff}\,E_s))$
and $\sigma_3 = f_{ct}/\rho_\text{eff}$.

### 3.2 Shift-and-replace interpretation

A convenient way to implement this: the effective reinforcement law is the
**bare steel law shifted horizontally by $\varepsilon_3$** in the tensile
branch, with the uncracked composite ramp spliced in for $\varepsilon_s < \varepsilon_3$.
The tail of the law (post-yield, post-ultimate) is unchanged — tension stiffening
only affects the pre-yield cracking range.

This shift-and-splice is the "long-term goal" formulation: identify
$\varepsilon_3(\rho_\text{eff}, f_{ct}, E_c, E_s)$ and construct the effective
steel law from it.

---

## 4. The Geometric Mapping Problem

The fundamental complication for a beam cross-section is that tension stiffening
operates at the level of an individual reinforcement layer, not the section as a
whole.

### 4.1 Strain profile at the layer

The plane-section assumption gives the strain at any height $z$ measured from
the bottom reference:

$$
\varepsilon(z) = \varepsilon_\text{bot} - \kappa \cdot z
$$

For a layer at height $z_s$, the steel strain is $\varepsilon_s = \varepsilon(z_s)$,
which is already used in the current solver.

### 4.2 Cracking strain at the layer position vs. boundary

The ACK model requires the *cracking strain of the surrounding concrete*
evaluated **at the rebar level**, not at the section boundary.

The concrete starts cracking when $\varepsilon > f_{ct}/E_c$ at the point of
maximum tension.  For a beam in pure bending, the maximum tension fibre is at
$z = 0$ (bottom).  The boundary cracking strain is:

$$
\varepsilon_{cr,\text{bot}} = f_{ct} / E_c
$$

But the rebar sits at $z_s > 0$, where the strain is smaller:

$$
\varepsilon_{cr,\text{at layer}} = \varepsilon_{cr,\text{bot}} - \kappa \cdot z_s
\quad \Bigl( = \frac{f_{ct}}{E_c} - \kappa\,z_s \Bigr)
$$

Because the strain at the rebar level at first cracking is already reduced by
$\kappa\,z_s$ relative to the bottom fibre, the effective first-cracking
strain for the ACK model at the rebar level must be corrected:

$$
\varepsilon_{1,s} = \varepsilon_{cr,\text{bot}} - \kappa\,z_s
$$

This correction depends on the current curvature $\kappa$ and the layer
geometry $z_s$ — so it cannot be precomputed once; it must be re-evaluated at
each curvature step.  This is the key reason why the tension stiffening model
needs access to the strain profile state, not just the bare strain at the layer.

### 4.3 Multiple layers

If the cross-section has layers at $z_{s,1}$ and $z_{s,2}$ (e.g. top and
bottom reinforcement), each layer has its own:

- effective concrete area $A_{c,\text{eff},i}$ (geometry-dependent),
- effective reinforcement ratio $\rho_{\text{eff},i}$,
- cracking strain correction $\kappa \cdot z_{s,i}$.

The corrections are independent and layers are processed separately.

### 4.4 Variable section width $b(z)$

For a T-section or I-section, $A_{c,\text{eff}}$ around the tension bar depends
on the actual width at the layer's height and the surrounding concrete area
available for bond.  EC2 Annex L gives prescriptive formulas; for the numerical
model the effective area can be derived from the shape geometry:

$$
A_{c,\text{eff},i} = \int_{z_{s,i} - h_\text{eff}/2}^{z_{s,i} + h_\text{eff}/2}
                     b(z)\,\mathrm{d}z
$$

where $h_\text{eff}$ is the effective height around the bar (typically
$2.5(h - z_{s,i})$ per EC2 or computed from the actual cover geometry).

### 4.5 Sagging vs. hogging

For a **sagging** section the bottom bars are in tension, and the cracking
develops from the bottom face ($z = 0$) upward.  The reference boundary strain
is $\varepsilon_\text{bot}$.

For a **hogging** section the top bars are in tension, and the cracking develops
from the top face ($z = h$) downward.  The reference boundary strain is
$\varepsilon_\text{top} = \varepsilon_\text{bot} - \kappa \cdot h$.

The ACK model applies symmetrically — the tensile branch of the effective law
activates whichever layer is in tension.  Both branches of the M-κ curve
(positive and negative) are handled by the same mechanism, as long as the
layer's own strain $\varepsilon_{s,i}$ and the appropriate boundary strain are
used.

---

## 5. Interface Design: Keeping Cross-Section and Material Levels Clean

### 5.1 Current interface

```
CrossSection.get_N_M(kappa, eps_top)
  │
  ├─ concrete.get_sig(eps_array)     # over n_points z-slices
  └─ for each layer:
       layer.material.get_sig(eps_s)  # eps_s = eps_top - kappa * z_s
```

The material models (`get_sig`) currently receive only the scalar strain at
their point.  No additional geometric or profile information is passed.

### 5.2 Proposed extension: `EffectiveSteelLayer`

The cleanest extension is to introduce a new wrapper class at the
**reinforcement layer** level (not at the bare material level):

```python
class EffectiveSteelLayer(ReinforcementLayer):
    """
    Reinforcement layer with ACK tension stiffening.

    Parameters additional to bare steel:
      - A_c_eff : effective concrete area around this bar [mm²]
      - f_ct    : concrete tensile strength [MPa]
      - E_c     : concrete modulus [MPa]

    The get_sig(eps_s, kappa) method replaces get_sig(eps_s) in the base class.
    """
    A_c_eff: float   # effective concrete area
    f_ct:    float   # concrete tensile strength
    E_c:     float   # concrete initial modulus

    def get_sig(self, eps_s: float, kappa: float = 0.0) -> float:
        ...
```

The `kappa` argument is the missing information from §4.2.  Passing it at the
layer-evaluation call is minimal: it does not change the cross-section
integration structure, it only adds one scalar to each layer call.

### 5.3 Changes in `CrossSection.get_N_M`

```python
# current (bare steel)
F_s = layer.A_s * layer.material.get_sig(eps_s)

# extended (effective layer)
if isinstance(layer, EffectiveSteelLayer):
    F_s = layer.A_s * layer.get_sig(eps_s, kappa=kappa)
else:
    F_s = layer.A_s * layer.material.get_sig(eps_s)
```

The check is local to the force-summation loop; the rest of `CrossSection` is
unchanged.  Alternatively, the base `ReinforcementLayer` could accept `**kwargs`
so the signature is always compatible.

### 5.4 What is *not* needed in the material model

The concrete model (`EC2ParabolaRectangle`) does not need to change.
It continues to return zero stress in tension.  The smeared tension contribution
is entirely encapsulated in `EffectiveSteelLayer.get_sig`.

---

## 6. Construction of $\varepsilon_3$ from Section Geometry

The saturation strain $\varepsilon_3$ for layer $i$ is:

$$
\varepsilon_{3,i}
  = \frac{f_{ct}}{\rho_{\text{eff},i}\,E_s}
  + \frac{f_{ct}}{2\,E_c}\bigl(1 - \rho_{\text{eff},i}\bigr)
$$

where $\rho_{\text{eff},i} = A_{s,i} / A_{c,\text{eff},i}$.

From the section geometry:

$$
A_{c,\text{eff},i} = b(z_{s,i}) \cdot h_{\text{eff},i}
\quad \text{with} \quad
h_{\text{eff},i} = \min\!\bigl(2.5\,(h - z_{s,i}),\ (h - x)/3,\ h/2\bigr)
$$

(EC2 Figure 7.1 prescription; $x$ is the compression zone depth).

For a first implementation, $A_{c,\text{eff}}$ can be treated as a user-supplied
parameter; the geometric derivation from the shape can be added later via a
factory method on `CrossSection`.

---

## 7. Effective Steel Law Construction (Step by Step)

Given $(\varepsilon_3, f_{ct}, \rho_\text{eff}, E_s, E_c)$, the effective steel
law for the tensile branch is built as follows:

1. **Uncracked composite branch** ($\varepsilon_s < \varepsilon_1$):

   $$\sigma_\text{eff} = \Bigl(E_s + \frac{(1 - \rho_\text{eff})\,E_c}{\rho_\text{eff}}\Bigr)\,\varepsilon_s$$

2. **Cracking plateau** ($\varepsilon_1 \leq \varepsilon_s \leq \varepsilon_3$):

   Linear interpolation between $(\varepsilon_1, \sigma_1)$ and
   $(\varepsilon_3, \sigma_3)$ where $\sigma_3 = f_{ct}/\rho_\text{eff}$.

3. **Post-cracking bare-steel with shift** ($\varepsilon_s > \varepsilon_3$):

   $$\sigma_\text{eff} = \sigma_3 + E_s\,(\varepsilon_s - \varepsilon_3)$$

   followed by the yield plateau and hardening of the bare steel law, shifted
   to align with $\varepsilon_3$ as the new zero-strain origin of the
   post-cracking branch.

The compression branch (negative strains) is identical to the bare steel model
— tension stiffening only affects the tensile side.

---

## 8. Open Questions and Complexity Drivers

| Question | Impact | Note |
|----------|--------|------|
| How to compute $A_{c,\text{eff}}$ for variable-width sections? | Medium | EC2 prescription exists; shape API (`b(z)`) already supports numerical integration |
| How to handle the curvature correction $\kappa \cdot z_s$ for hogging layers? | Low | Sign convention: top layer in hogging → tensile strain with $\varepsilon_\text{top}$; layer formula is general |
| Is $\varepsilon_3$ constant or updated with $x$ (neutral axis) at each step? | Medium | $x$ changes with $\kappa$; $h_\text{eff}$ and hence $A_{c,\text{eff}}$ strictly depend on $x$ — an iterative update loop |
| Long-term creep and shrinkage modify tension stiffening | Out of scope | Noted for later |
| Consistency with the compression concrete model (no double-counting)? | Low | Guaranteed by Option B: concrete model retains zero tension |

---

## 9. Relationship to Existing Code

| Component | Current state | Required change |
|-----------|--------------|-----------------|
| `EC2ParabolaRectangle` | Zero tensile stress | None |
| `SteelReinforcement.get_sig(eps)` | Bare bilinear | None (used inside `EffectiveSteelLayer`) |
| `ReinforcementLayer` | Wraps material | New subclass `EffectiveSteelLayer` |
| `CrossSection.get_N_M` | Calls `layer.material.get_sig(eps_s)` | Forward `kappa` to effective layers |
| `StressStrainProfile` | Displays current state | No change needed for core; plotting may add stiffening contribution |
| `BeamDeflectionAnalysis` / `BeamMKappaAnalysis` | Use `CrossSection` | No change; benefit propagates automatically |

---

## 10. Suggested Implementation Sequence

1. **Unit test in uniaxial**: implement `EffectiveSteelLayer.get_sig(eps_s,
   kappa=0)` for a uniaxial prism ($\kappa = 0$) and verify against the
   hand-computed ACK $\sigma_3$ at saturation.

2. **Rectangle section, single bottom layer**: add `EffectiveSteelLayer` to a
   standard rectangular section and compare the M-κ curve against the current
   (bare steel) result — expect higher stiffness in the cracking range, same
   ultimate capacity.

3. **Add curvature correction**: pass `kappa` to the layer call; verify that
   the cracking strain at the layer level is correctly reduced relative to the
   boundary.

4. **Two layers (sagging + hogging)**: verify that the top layer (compression in
   sagging) activates its tensile branch only when the section is in hogging.

5. **Variable-width section (T-shape)**: implement $A_{c,\text{eff}}$ from the
   shape geometry; compare with EC2 formula.

6. **M-κ comparison with Eurocode $EI_\text{eff}$**: at service moments, check
   that the effective stiffness implied by the M-κ curve with tension stiffening
   matches the EC2 interpolation $EI_\text{eff} = (1-\zeta) EI_g + \zeta EI_{cr}$.
