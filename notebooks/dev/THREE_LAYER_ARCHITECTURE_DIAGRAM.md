# Three-Layer Material Strength Architecture - Visual Overview

**Date:** January 11, 2026  
**Purpose:** Quick reference diagram for the complete architecture

---

## The Big Picture

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                     PRODUCT DATABASE (Layer 1)                            ║
║  Classification + Certified Properties + Traceability                     ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   MaterialType.CONCRETE     MaterialType.STEEL      MaterialType.CARBON  ║
║   ┌──────────────────┐      ┌──────────────────┐   ┌──────────────────┐ ║
║   │ Product: C30/37  │      │ Product: B500B   │   │ Product: SikaWrap│ ║
║   │ ─────────────    │      │ ─────────────    │   │ ───────────────  │ ║
║   │ f_ck: 30 MPa     │      │ f_yk: 500 MPa    │   │ f_tk: 3500 MPa   │ ║
║   │ f_cm: 38 MPa     │      │ E_s: 200 GPa     │   │ E_t: 230 GPa     │ ║
║   │ E_cm: 33 GPa     │      │ ductility: B     │   │ eps_uk: 1.5%     │ ║
║   │ gamma_c: 1.5     │      │ gamma_s: 1.15    │   │ gamma_s: 1.25    │ ║
║   └──────────────────┘      └──────────────────┘   └──────────────────┘ ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
                                    ↓
╔═══════════════════════════════════════════════════════════════════════════╗
║                    ASSESSMENT CONTEXT (Layer 2)                           ║
║  Calculation Intent + Safety Factors + Modifiers                          ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Context Selection:                     Modifiers (Optional):             ║
║  ┌─────────────────────────────┐       ┌──────────────────────────┐      ║
║  │ ○ ULS_DESIGN               │       │ ☐ Long-term reduction    │      ║
║  │   → f_cd = f_ck / γ_c      │       │   (Carbon: 0.7×)         │      ║
║  │   → f_yd = f_yk / γ_s      │       │                          │      ║
║  │   Purpose: Code compliance  │       │ ☐ Temperature effects    │      ║
║  │                             │       │   (T > 20°C: reduced)    │      ║
║  │ ○ TEACHING_CHARACTERISTIC  │       │                          │      ║
║  │   → f_c = f_ck (no γ)      │       │ ☐ Creep coefficient      │      ║
║  │   Purpose: Show real values │       │   (φ = 2.0 typical)      │      ║
║  │                             │       └──────────────────────────┘      ║
║  │ ○ SLS_CHARACTERISTIC       │                                           ║
║  │   → Service load checks     │       Material-Specific Factors:         ║
║  │   → Crack width limits      │       • Concrete: γ_c = 1.5              ║
║  │                             │       • Steel: γ_s = 1.15                ║
║  │ ○ ANALYSIS_MEAN            │       • Carbon: γ_s = 1.25 + 0.7 LT      ║
║  │   → f_cm for research       │       • Glass: γ_s = 1.30 + 0.5 LT       ║
║  │   → Model calibration       │                                           ║
║  └─────────────────────────────┘                                          ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
                                    ↓
╔═══════════════════════════════════════════════════════════════════════════╗
║                  CONSTITUTIVE MODEL (Layer 3)                             ║
║  Stress-Strain Law + Parameter Mapping + Applicability                    ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Model Registry by Material Type:                                         ║
║                                                                            ║
║  CONCRETE Models:                  STEEL Models:                          ║
║  ┌────────────────────────┐        ┌────────────────────────┐            ║
║  │ EC2 Parabola-Rectangle│        │ Elastic-Perfectly      │            ║
║  │ ───────────────────── │        │ Plastic                │            ║
║  │ Valid: ULS_DESIGN     │        │ ─────────────────────  │            ║
║  │ Params: f_cd, eps_c1, │        │ Valid: ULS_DESIGN,     │            ║
║  │         eps_cu1        │        │        TEACHING        │            ║
║  │ Use: Cross-section    │        │ Params: f_yd, E_s      │            ║
║  │      capacity         │        │ Use: Standard design   │            ║
║  └────────────────────────┘        └────────────────────────┘            ║
║                                                                            ║
║  ┌────────────────────────┐        ┌────────────────────────┐            ║
║  │ Bilinear Simplified   │        │ Hardening Model        │            ║
║  │ ───────────────────── │        │ ─────────────────────  │            ║
║  │ Valid: TEACHING,      │        │ Valid: ANALYSIS_MEAN   │            ║
║  │        ULS_DESIGN     │        │ Params: f_y, f_u, E_s, │            ║
║  │ Params: f_c, E_cm     │        │         E_sh           │            ║
║  │ Use: Hand calcs       │        │ Use: Nonlinear FE,     │            ║
║  │                        │        │      research          │            ║
║  └────────────────────────┘        └────────────────────────┘            ║
║                                                                            ║
║  ┌────────────────────────┐        CARBON Models:                         ║
║  │ Sargin Nonlinear      │        ┌────────────────────────┐            ║
║  │ ───────────────────── │        │ Linear Elastic         │            ║
║  │ Valid: ANALYSIS_MEAN, │        │ ─────────────────────  │            ║
║  │        RESEARCH       │        │ Valid: All contexts    │            ║
║  │ Params: f_cm, E_cm, k │        │ Params: f_td, E_t      │            ║
║  │ Use: FE simulation,   │        │ Use: Standard design   │            ║
║  │      calibration      │        │      (brittle rupture) │            ║
║  └────────────────────────┘        └────────────────────────┘            ║
║                                                                            ║
║  Parameter Mapping Example:                                               ║
║  Product {f_ck: 30} + Context {ULS_DESIGN} → Model {f_cd: 20, ...}      ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
                                    ↓
╔═══════════════════════════════════════════════════════════════════════════╗
║                           COMPUTATION RESULT                              ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Input: ε = -0.002 (compression)                                         ║
║                                                                            ║
║  Output: σ = -18.2 MPa                                                   ║
║                                                                            ║
║  Metadata (Full Traceability):                                            ║
║  ┌───────────────────────────────────────────────────────────────────┐   ║
║  │ Product:    C30/37 (f_ck = 30 MPa)                                │   ║
║  │ Context:    ULS_DESIGN                                            │   ║
║  │ Safety:     γ_c = 1.5                                             │   ║
║  │ Strength:   f_cd = f_ck / γ_c = 30 / 1.5 = 20 MPa               │   ║
║  │ Model:      EC2 Parabola-Rectangle                                │   ║
║  │ Parameters: {f_cd: 20.0, eps_c1: 0.0022, eps_cu1: 0.0035}       │   ║
║  │ Modifiers:  None                                                  │   ║
║  │                                                                    │   ║
║  │ Calculation: η = ε/eps_c1 = 0.002/0.0022 = 0.909                │   ║
║  │              σ = -f_cd × (1 - (1-η)²)                            │   ║
║  │                = -20 × (1 - 0.091²) = -18.2 MPa                  │   ║
║  └───────────────────────────────────────────────────────────────────┘   ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## Example Use Cases

### Use Case 1: Design Office
```
Layer 1: C30/37 concrete, B500B steel (from certified suppliers)
Layer 2: ULS_DESIGN context (EC2 compliance)
Layer 3: EC2 Parabola-Rectangle + Elastic-Plastic models
Result:  M_Rd = 245 kNm, ready for submission
```

### Use Case 2: University Teaching
```
Layer 1: Same products (C30/37, B500B)
Layer 2: TEACHING_CHARACTERISTIC (show actual strengths)
Layer 3: Bilinear models (simplified for hand calcs)
Result:  Students see f_ck, f_yk directly, understand safety factor effect
```

### Use Case 3: Research Lab
```
Layer 1: Test specimens with measured f_cm, f_ym
Layer 2: ANALYSIS_MEAN (calibration mode)
Layer 3: Sargin + Hardening models (capture softening/hardening)
Result:  Accurate prediction of experimental load-deflection curves
```

### Use Case 4: Carbon FRP Bridge
```
Layer 1: SikaWrap-300C carbon sheets
Layer 2: ULS_DESIGN + LongTermModifier(0.7)
Layer 3: Linear Elastic model
Result:  f_td = (3500/1.25) × 0.7 = 1960 MPa (sustained load capacity)
```

---

## Decision Tree

```
START: "I need to analyze a cross-section"
  │
  ├─ Question 1: WHAT MATERIAL?
  │   ↓
  │   Choose from Product Database
  │   → Material Type auto-classified
  │   → Properties retrieved
  │
  ├─ Question 2: WHY AM I ANALYZING?
  │   ↓
  │   ┌─ Code compliance design → ULS_DESIGN
  │   ├─ Service load check → SLS_CHARACTERISTIC
  │   ├─ Teaching demonstration → TEACHING_*
  │   └─ Research/calibration → ANALYSIS_MEAN
  │
  ├─ Question 3: WHICH STRESS-STRAIN LAW?
  │   ↓
  │   Registry filters by:
  │   - Material type (concrete/steel/carbon)
  │   - Assessment context validity
  │   - Analysis type compatibility
  │   ↓
  │   User selects from valid options
  │
  ├─ Question 4: ANY SPECIAL CONDITIONS?
  │   ↓
  │   ┌─ Long-term loading? → Add LongTermModifier
  │   ├─ Elevated temperature? → Add TemperatureModifier
  │   └─ Creep effects? → Add CreepModifier
  │
  └─ COMPUTE!
      ↓
      σ(ε) with full metadata
```

---

## Validation Matrix

| Context | Concrete Model | Steel Model | Purpose | Valid? |
|---------|---------------|-------------|---------|--------|
| ULS_DESIGN | Parabola-Rectangle | Elastic-Plastic | Design per EC2 | ✅ |
| ULS_DESIGN | Sargin | Elastic-Plastic | Design per EC2 | ❌ Research model |
| TEACHING_CHAR | Bilinear | Elastic-Plastic | Show strengths | ✅ |
| TEACHING_CHAR | Parabola-Rectangle | Hardening | Show strengths | ⚠️ Mismatch |
| ANALYSIS_MEAN | Sargin | Hardening | Research | ✅ |
| ANALYSIS_MEAN | Parabola-Rectangle | Hardening | Research | ⚠️ Design model |
| SLS_CHAR | Bilinear | Elastic-Plastic | Crack check | ✅ |

**Legend:**
- ✅ Valid and recommended
- ⚠️ Technically possible but unusual (warn user)
- ❌ Invalid combination (prevent)

---

## Implementation Phases

### Phase 1: Context String ⚡ **Start Here**
```python
# Simple addition to existing code
profile.plot(context='uls_design')  # or 'teaching_characteristic'

# Basic if-else
if context == 'uls_design':
    factor_concrete = 1/1.5
    factor_steel = 1/1.15
else:
    factor_concrete = 1.0
    factor_steel = 1.0
```

### Phase 2: Context Enum + Mapper
```python
context = AssessmentContext.ULS_DESIGN
mapper = MaterialStrengthMapper(context)
sig = mapper.get_stress(product, eps)
```

### Phase 3: Model Registry
```python
model = registry.select_default(MaterialType.CONCRETE, context)
params = model.map_parameters(product, context)
sig = model.get_sig(eps, params)
```

### Phase 4: Full System
```python
mapper.add_modifier(LongTermCarbonModifier(0.7))
sig, metadata = mapper.get_stress_with_metadata(product, eps)
report = generate_calculation_report(metadata)
```

---

## Key Principles

1. **Three dimensions are INDEPENDENT**
   - Change product → Same context, same model
   - Change context → Same product, same model (if valid)
   - Change model → Same product, same context (if valid)

2. **Validation prevents errors**
   - Model declares valid contexts
   - Registry filters incompatible combinations
   - User sees only applicable options

3. **Transparency is mandatory**
   - Always show which product/context/model
   - Display all parameter transformations
   - Enable full calculation traceability

4. **Extensibility without refactoring**
   - Add material type → Update enum, register models
   - Add context → Define factors, update applicability
   - Add model → Implement interface, register
   - Add modifier → Inherit base, stack with existing

---

## Related Documentation

- [Full Architecture Discussion](../../dev_docs/MATERIAL_STRENGTH_MAPPING_ARCHITECTURE.md)
- [Assessment Context Concept with Scenarios](ASSESSMENT_CONTEXT_CONCEPT.md)
- [Component Catalog Integration](COMPONENT_CATALOG_INTEGRATION.md)

---

**Quick Reference:** Bookmark this diagram for understanding the complete material strength mapping system.
