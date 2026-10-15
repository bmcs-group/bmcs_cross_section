# Assessment Context Concept

**Purpose:** Define clear calculation contexts for structural analysis to ensure correct material strength values are used transparently.

**Date:** January 11, 2026  
**Status:** Conceptual Framework → Implementation Pending  
**Related:** [Full Architecture Discussion](../../dev_docs/MATERIAL_STRENGTH_MAPPING_ARCHITECTURE.md)

---

## The Core Problem

When analyzing a cross-section, we need to answer:
> **"What material strength values should I use?"**

The answer depends on **WHY** you're doing the analysis:

```
❌ BAD: "Use characteristic/design/mean values" (ambiguous)
✅ GOOD: "I'm performing ULS design per EC2" (clear intent)
```

---

## What is an Assessment Context?

An **Assessment Context** is a named scenario that defines:
1. **Purpose** of the analysis (design, teaching, research)
2. **Material strength level** to use (characteristic, design, mean)
3. **Safety factors** to apply (γ_c, γ_s, etc.)
4. **Modifiers** if needed (creep, temperature, long-term effects)

It answers: *"What calculation am I performing and what code requirements apply?"*

---

## Example Scenarios

### Scenario 1: Design Office - ULS Check

**Context:** `ULS_DESIGN`

**Story:**
> An engineer is designing a new building. They must verify that a beam can carry the design loads according to Eurocode 2.

**Material Values:**
- Concrete: f_cd = f_ck / γ_c = 30 / 1.5 = **20 MPa** (design)
- Steel: f_yd = f_yk / γ_s = 500 / 1.15 = **435 MPa** (design)

**Assessment:**
- Calculate M_Rd using design strengths
- Check: **M_Rd ≥ M_Ed** (capacity ≥ demand)
- Result: **Safe / Not Safe**

**Visualization Labels:**
- F_cd, F_sd (design forces)
- "M_Rd ≥ M_Ed" assessment box

```python
# Code Example
context = AssessmentContext.ULS_DESIGN
mapper = MaterialStrengthMapper(context)

# Concrete stress uses f_cd automatically
sig_concrete = mapper.get_concrete_stress(concrete, eps)
# → applies factor 1/1.5 to characteristic strength
```

---

### Scenario 2: University Lecture - Teaching Safety Factors

**Context:** `TEACHING_CHARACTERISTIC`

**Story:**
> A professor wants to show students HOW safety factors work. They display characteristic strengths first, then explain the reduction to design values.

**Material Values:**
- Concrete: f_ck = **30 MPa** (characteristic)
- Steel: f_yk = **500 MPa** (characteristic)

**Purpose:**
- Show students the ACTUAL material strengths from testing
- Then explain: "For design, we divide by safety factors"
- Transparency: Students see f_ck → f_cd transformation

**Visualization Labels:**
- F_ck, F_sk (characteristic forces)
- Display: "Characteristic values (no safety factors)"

```python
context = AssessmentContext.TEACHING_CHARACTERISTIC
mapper = MaterialStrengthMapper(context)

# Uses f_ck directly (factor = 1.0)
sig_concrete = mapper.get_concrete_stress(concrete, eps)
```

---

### Scenario 3: Research - Material Model Calibration

**Context:** `ANALYSIS_MEAN`

**Story:**
> A researcher is calibrating a new concrete model against experimental data. They compare their model predictions with MEAN test results (not characteristic or design).

**Material Values:**
- Concrete: f_cm = f_ck + 8 = **38 MPa** (mean from tests)
- Steel: f_ym ≈ **550 MPa** (mean from tests)

**Purpose:**
- Match experimental curves
- Validate numerical models
- NOT for code-compliant design!

**Visualization Labels:**
- F_cm, F_sm (mean forces)
- Display: "Mean values (research only)"

```python
context = AssessmentContext.ANALYSIS_MEAN
mapper = MaterialStrengthMapper(context)

# Uses mean strength
sig_concrete = mapper.get_concrete_stress(concrete, eps)
# → f_cm = f_ck + 8 MPa
```

---

### Scenario 4: SLS Check - Crack Width Calculation

**Context:** `SLS_CHARACTERISTIC`

**Story:**
> An engineer checks whether crack widths are acceptable under service loads. EC2 specifies using CHARACTERISTIC strengths (not design) for SLS.

**Material Values:**
- Concrete: f_ck = **30 MPa** (characteristic, no γ_c)
- Steel: f_yk = **500 MPa** (characteristic, no γ_s)

**Loads:**
- Service loads (NO load factors)
- Frequent or quasi-permanent combinations

**Assessment:**
- Calculate stresses under service conditions
- Check: **σ_s ≤ k × f_yk** (stress limits)
- Check: **w_k ≤ w_max** (crack width)

```python
context = AssessmentContext.SLS_CHARACTERISTIC
mapper = MaterialStrengthMapper(context)

# No safety factors applied
sig_steel = mapper.get_steel_stress(steel, eps)
```

---

### Scenario 5: Long-Term Loading - Carbon FRP Beam

**Context:** `ULS_DESIGN` + **Modifiers**

**Story:**
> An engineer designs a bridge deck with carbon FRP reinforcement. Under sustained loading, carbon exhibits creep-rupture. A reduction factor must be applied.

**Material Values:**
- Concrete: f_cd = 30 / 1.5 = **20 MPa**
- Carbon: f_td = f_tk / γ_s = 2400 / 1.25 = **1920 MPa**
- **+ Long-term reduction:** 0.7 × f_td = **1344 MPa**

**Modifiers:**
```python
context = AssessmentContext.ULS_DESIGN
mapper = MaterialStrengthMapper(context)

# Add long-term modifier for carbon
mapper.add_modifier(LongTermCarbonModifier(factor=0.7))

# Carbon strength now includes both safety factor AND long-term reduction
sig_carbon = mapper.get_carbon_stress(carbon, eps)
```

**Why Modifiers Matter:**
- Material type specific (only carbon, not steel)
- Context dependent (only for sustained loads)
- Stackable (temperature + long-term + ...)

---

### Scenario 6: Teaching - Show Design vs Characteristic

**Context:** Dual display with `TEACHING_DESIGN` + `TEACHING_CHARACTERISTIC`

**Story:**
> A professor shows TWO plots side-by-side: one with characteristic strengths, one with design strengths, to illustrate the safety factor effect.

**Display:**
```
Plot 1 (Characteristic)          Plot 2 (Design)
---------------------------      ---------------------------
F_ck = -300 kN                   F_cd = -200 kN
F_sk = +300 kN                   F_sd = +261 kN
σ_c,max = 30 MPa                 σ_c,max = 20 MPa
σ_s = 500 MPa                    σ_s = 435 MPa

"Characteristic values"          "Design values (with γ)"
```

**Teaching Value:**
- Students see EXACTLY how much strength is "lost" to safety
- Understand that real material is stronger than design assumes
- Learn where the safety margin comes from

---

## Context Comparison Table

| Context | Concrete | Steel | Purpose | Safety? |
|---------|----------|-------|---------|---------|
| **ULS_DESIGN** | f_cd = f_ck/1.5 | f_yd = f_yk/1.15 | Code compliance | ✅ Yes |
| **TEACHING_CHARACTERISTIC** | f_ck | f_yk | Show test values | ❌ No |
| **TEACHING_DESIGN** | f_cd | f_yd | Show code values | ✅ Yes |
| **SLS_CHARACTERISTIC** | f_ck | f_yk | Service checks | ❌ No |
| **SLS_QUASI_PERMANENT** | f_ck (+creep) | f_yk | Long-term SLS | ❌ No |
| **ANALYSIS_MEAN** | f_cm | f_ym | Research | ❌ No |

---

## Why Not "Select Strength Type"?

### ❌ Bad Interface:
```
Select material strength:
○ Characteristic  ○ Design  ○ Mean
```

**Problems:**
1. **Ambiguous:** What does "characteristic carbon" mean with long-term loading?
2. **Error-prone:** User might select "mean" for ULS design (WRONG!)
3. **Not extensible:** Where do modifiers go?
4. **No traceability:** Can't document why a value was chosen

### ✅ Good Interface:
```
Assessment Context:
○ ULS Design (EC2)
○ Teaching: Show Characteristic Values
○ Teaching: Show Design Values  
○ SLS: Crack Width Check
○ Research: Mean Values

[☑] Apply long-term reduction (carbon/GFRP)
[ ] Apply elevated temperature effects
```

**Benefits:**
1. **Clear intent:** User knows what calculation they're doing
2. **Correct by default:** Context ensures code compliance
3. **Extensible:** Add modifiers without changing interface
4. **Traceable:** Can log "ULS_DESIGN + LongTermCarbon(0.7)"

---

## Implementation Levels

### Level 0: Current State (No Context)
```python
# Ambiguous - what strength is this?
sig = concrete.get_sig(eps)
```

### Level 1: Simple Context String (Minimal)
```python
# Clear intent, simple implementation
profile.plot_stress_strain_profile(
    context='uls_design',  # or 'teaching_characteristic'
    concrete_label='F_cd',
    steel_label='F_sd'
)
```

### Level 2: Context Enum + Mapper (Recommended)
```python
# Full flexibility with transparency
context = AssessmentContext.ULS_DESIGN
mapper = MaterialStrengthMapper(context)

# Mapper knows material-specific logic
sig_c = mapper.get_concrete_stress(concrete, eps)
sig_s = mapper.get_steel_stress(steel, eps)
```

### Level 3: Context + Modifiers (Advanced)
```python
# Handle complex scenarios
context = AssessmentContext.ULS_DESIGN
mapper = MaterialStrengthMapper(context)
mapper.add_modifier(LongTermCarbonModifier(0.7))
mapper.add_modifier(TemperatureModifier(50))  # 50°C

# All effects applied transparently
sig_carbon, metadata = mapper.get_stress_with_metadata(carbon, eps)
print(metadata)
# → "ULS Design: f_tk=2400 MPa, γ_s=1.25, long-term=0.7, temp=0.95"
# → "Effective: f_td = 2400/1.25*0.7*0.95 = 1290 MPa"
```

---

## Transparency & Traceability

**Key Principle:** User should ALWAYS know what values are being used.

### Display in UI:
```python
st.info("""
**Assessment Context:** ULS Design (EC2)

**Concrete:**
- Characteristic: f_ck = 30 MPa
- Safety factor: γ_c = 1.5
- **Design: f_cd = 20 MPa** ✓

**Steel:**
- Characteristic: f_yk = 500 MPa
- Safety factor: γ_s = 1.15
- **Design: f_yd = 435 MPa** ✓

**Modifiers:** None
""")
```

### In Assessment Report:
```
MATERIAL VALUES USED:
=====================
Context: ULS_DESIGN
Date: 2026-01-11
Code: EN 1992-1-1:2004

Concrete C30/37:
  f_ck = 30.0 MPa (characteristic)
  γ_c = 1.50 (partial factor)
  α_cc = 1.00 (long-term factor)
  f_cd = 20.0 MPa (design) ← USED IN CALCULATION

Steel B500B:
  f_yk = 500 MPa (characteristic)
  γ_s = 1.15 (partial factor)
  f_yd = 435 MPa (design) ← USED IN CALCULATION
  
VERIFICATION:
M_Rd = 245.3 kNm ≥ M_Ed = 200.0 kNm ✓ SAFE
```

---

## Recommended Implementation Path

### Phase 1: **Simple Context String** (Now)
- Add `context` parameter to plot functions
- Use simple if-else for factor selection
- Display context in UI with explanation
- **Goal:** Make current usage explicit

### Phase 2: **Context Enum** (Next)
- Define `AssessmentContext` enum
- Create `MaterialStrengthMapper` class
- Support ULS_DESIGN and TEACHING contexts
- **Goal:** Type safety and clarity

### Phase 3: **Modifiers** (Later)
- Implement modifier pattern
- Add long-term, temperature, creep
- Enable stacking of effects
- **Goal:** Handle complex scenarios

### Phase 4: **Traceability** (Future)
- Generate calculation reports
- Export metadata with results
- Audit trail for design documentation
- **Goal:** Professional design workflow

---

## The Third Dimension: Material Model Selection

**Challenge:** A single material TYPE can have MULTIPLE valid stress-strain laws.

### Why Multiple Models?

**Concrete has 3+ constitutive laws:**
- **Parabola-Rectangle** (EC2 standard) - ULS design, accurate capacity
- **Bilinear** (Simplified) - Hand calculations, teaching
- **Sargin Curve** (Research) - Nonlinear FE, experimental validation

**Steel reinforcement has 2+ models:**
- **Elastic-Perfectly Plastic** (EC2 standard) - Design calculations
- **Elastic-Plastic with Hardening** (Research) - Accurate ultimate behavior

**Each model is appropriate for different contexts and purposes!**

### The Three-Layer Mapping

```
Layer 1: Product Database          Layer 2: Assessment Context      Layer 3: Constitutive Model
------------------------          ------------------------         -----------------------
Material: Concrete C30/37    →    Purpose: ULS Design       →     Model: Parabola-Rectangle
  f_ck = 30 MPa                   Safety: γ_c = 1.5               Parameters:
  f_cm = 38 MPa                   Strength: f_cd = 20 MPa           f_cd = 20 MPa
  E_cm = 33 GPa                                                     eps_c1 = 0.0022
                                                                    eps_cu1 = 0.0035
```

### Scenario 7: Teaching - Compare Concrete Models

**Context:** `TEACHING_CHARACTERISTIC`  
**Purpose:** Show students how different stress-strain assumptions affect results

**Setup:**
```python
# Same product, same context, DIFFERENT models
product = ConcreteC30()
context = AssessmentContext.TEACHING_CHARACTERISTIC

# Create three mappers with different models
mapper_parabola = MaterialStrengthMapper(context)
mapper_parabola.select_model(MaterialType.CONCRETE, "EC2 Parabola-Rectangle")

mapper_bilinear = MaterialStrengthMapper(context)
mapper_bilinear.select_model(MaterialType.CONCRETE, "Bilinear Simplified")

mapper_sargin = MaterialStrengthMapper(context)
mapper_sargin.select_model(MaterialType.CONCRETE, "Sargin Nonlinear")
```

**Side-by-Side Comparison:**
```
Strain: -0.002

Model 1: Parabola-Rectangle    Model 2: Bilinear           Model 3: Sargin Curve
σ_c = -27.3 MPa               σ_c = -22.0 MPa             σ_c = -28.1 MPa
(smooth parabola)             (elastic-plastic)           (gradual softening)

All use f_ck = 30 MPa, but DIFFERENT stress-strain laws!
```

**Teaching Value:**
- Students see that constitutive law MATTERS
- Understand trade-offs: accuracy vs simplicity
- Learn when to use which model

---

### Scenario 8: Design Office - Model Selection for Analysis Type

**Product:** Concrete C30/37, Steel B500B  
**Context:** `ULS_DESIGN`  
**Question:** Which constitutive models should I use?

**Analysis Type 1: Cross-Section Capacity (M-κ)**
```python
context = AssessmentContext.ULS_DESIGN
analysis_type = 'cross_section_capacity'

mapper = MaterialStrengthMapper(context, analysis_type)

# Automatic selection based on analysis type
concrete_model = mapper.select_model(MaterialType.CONCRETE)
# → EC2 Parabola-Rectangle (accurate, code-compliant)

steel_model = mapper.select_model(MaterialType.STEEL)
# → Elastic-Perfectly Plastic (standard EC2 assumption)
```

**Result:**
- M_Rd calculated per EC2 standard
- Code-compliant design values
- Ready for submission to authorities

**Analysis Type 2: Nonlinear Pushover Analysis**
```python
context = AssessmentContext.ANALYSIS_MEAN  # Use mean for research
analysis_type = 'nonlinear_pushover'

mapper = MaterialStrengthMapper(context, analysis_type)

# Different models selected automatically!
concrete_model = mapper.select_model(MaterialType.CONCRETE)
# → Sargin Curve (captures softening for FE)

steel_model = mapper.select_model(MaterialType.STEEL)
# → Hardening Model (captures strain hardening)
```

**Result:**
- Accurate post-yield behavior
- Softening branch for concrete
- Strain hardening for steel
- Research-grade simulation

---

### Scenario 9: Material Classification in Product Database

**Problem:** Database has 100+ products. How to organize?

**Solution:** Classify by `material_type`:

```python
# Database structure
products = {
    MaterialType.CONCRETE: [
        Product(name="C25/30", f_ck=25, ...),
        Product(name="C30/37", f_ck=30, ...),
        Product(name="C40/50", f_ck=40, ...),
    ],
    MaterialType.STEEL: [
        Product(name="B500A", f_yk=500, ductility='A', ...),
        Product(name="B500B", f_yk=500, ductility='B', ...),
    ],
    MaterialType.CARBON_FRP: [
        Product(name="SikaWrap-300C", f_tk=3500, E_t=230000, ...),
        Product(name="MBrace CF130", f_tk=3800, E_t=240000, ...),
    ]
}
```

**Model Registry Links to Material Type:**
```python
# Each model declares which material types it works with
EC2ParabolaRectangle.material_type = MaterialType.CONCRETE
ElasticPlasticSteel.material_type = MaterialType.STEEL
LinearElasticFRP.material_type = MaterialType.CARBON_FRP
```

**Filtering:**
```python
# Get all models for concrete
concrete_models = registry.get_models_for_type(MaterialType.CONCRETE)
# → [Parabola-Rectangle, Bilinear, Sargin, ...]

# Get models for concrete valid in ULS design
uls_models = registry.get_available_models(
    MaterialType.CONCRETE, 
    AssessmentContext.ULS_DESIGN,
    'cross_section_capacity'
)
# → [Parabola-Rectangle, Bilinear]  (Sargin filtered out - for research only)
```

---

### Scenario 10: Parameter Mapping - Product to Model

**Challenge:** Product database parameters ≠ Model parameters

**Example: Concrete C30/37 → EC2 Parabola-Rectangle**

**Product has:**
```python
product.parameters = {
    'f_ck': 30.0,      # Characteristic cylinder strength
    'f_cm': 38.0,      # Mean strength
    'E_cm': 33000.0,   # Mean elastic modulus
    'density': 2400.0  # kg/m³
}
```

**Model needs:**
```python
model.parameters = {
    'f_cd': ???,       # Design strength
    'eps_c1': ???,     # Strain at peak stress
    'eps_cu1': ???     # Ultimate strain
}
```

**Parameter Mapper bridges the gap:**
```python
class EC2ParabolaRectangle:
    def map_parameters(self, product, context):
        # Get base strength
        f_ck = product.parameters['f_ck']
        
        # Apply context (safety factor)
        if context == AssessmentContext.ULS_DESIGN:
            f_cd = f_ck / 1.5  # γ_c = 1.5
        elif context == AssessmentContext.TEACHING_CHARACTERISTIC:
            f_cd = f_ck  # No safety factor
        else:
            f_cd = product.parameters['f_cm']  # Mean for research
        
        # Compute strain parameters from EC2 Table 3.1
        if f_ck <= 50:
            eps_c1 = 0.0022
            eps_cu1 = 0.0035
        else:
            # High-strength concrete formulas
            eps_c1 = 0.0022 + 0.000012 * (f_ck - 50)
            eps_cu1 = 0.0026 + 0.0035 * ((98 - f_ck) / 100) ** 4
        
        return {
            'f_cd': f_cd,
            'eps_c1': eps_c1,
            'eps_cu1': eps_cu1
        }
```

**Benefits:**
1. **Separation:** Product database doesn't need to know about every model
2. **Flexibility:** Add new models without changing database schema
3. **Code compliance:** Mapper applies EC2 formulas correctly
4. **Transparency:** See exactly how parameters are derived

---

### Scenario 11: Model Validation and Filtering

**Challenge:** User selects incompatible combination

**Example: Research model for design submission**
```python
context = AssessmentContext.ULS_DESIGN
analysis_type = 'cross_section_capacity'

# User tries to select Sargin curve
mapper = MaterialStrengthMapper(context, analysis_type)

try:
    mapper.select_model(MaterialType.CONCRETE, "Sargin Nonlinear")
except ModelNotApplicableError as e:
    st.error(f"""
    ❌ Model 'Sargin Nonlinear' is not applicable!
    
    Selected context: {context.value}
    Selected analysis: {analysis_type}
    
    Model is valid for: {e.model.valid_contexts}
    
    Suggested models:
    - EC2 Parabola-Rectangle ✓
    - Bilinear Simplified ✓
    """)
```

**Validation Rules in Model:**
```python
class SarginConcrete(ConstitutiveModel):
    valid_contexts = [
        AssessmentContext.ANALYSIS_MEAN,
        AssessmentContext.RESEARCH_CALIBRATION
    ]
    
    def is_applicable(self, context, analysis_type):
        # NOT for code-compliant design!
        if context in [AssessmentContext.ULS_DESIGN, 
                       AssessmentContext.SLS_CHARACTERISTIC]:
            return False
        
        # Only for research/nonlinear analysis
        if analysis_type not in ['research', 'nonlinear_fe', 
                                 'model_calibration']:
            return False
        
        return True
```

**UI Shows Only Valid Options:**
```python
# Streamlit dropdown
available = registry.get_available_models(
    MaterialType.CONCRETE, context, analysis_type
)

model = st.selectbox(
    "Concrete Model",
    available,
    format_func=lambda m: f"{m.name} ✓"
)

# Invalid models never appear in list!
```

---

---

## Summary: The Complete Three-Layer Architecture

**Assessment Context orchestrates THREE independent but connected dimensions:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 1: PRODUCT DATABASE                        │
│  "What material am I using?"                                        │
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐               │
│  │ CONCRETE    │  │ STEEL       │  │ CARBON FRP   │               │
│  │ ─────────   │  │ ─────────   │  │ ────────────  │               │
│  │ C25/30      │  │ B500A       │  │ SikaWrap-300C│               │
│  │ C30/37  ←───┼──┼─ B500B      │  │ MBrace CF130 │               │
│  │ C40/50      │  │ S355        │  │ S&P C-Sheet  │               │
│  └─────────────┘  └─────────────┘  └──────────────┘               │
│                                                                       │
│  Properties: f_ck, f_tk, E_cm, certification, manufacturer          │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  LAYER 2: ASSESSMENT CONTEXT                        │
│  "What calculation am I performing?"                                │
│                                                                       │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────┐          │
│  │ ULS_DESIGN ←──┼──┼─ Apply γ_c=1.5│  │ + Modifiers  │          │
│  │ (EC2)         │  │   γ_s=1.15    │  │   Long-term  │          │
│  └───────────────┘  └────────────────┘  │   Temperature│          │
│                                          │   Creep      │          │
│  ┌───────────────┐  ┌────────────────┐  └──────────────┘          │
│  │ TEACHING_     │  │ Show f_ck, f_yk│                             │
│  │ CHARACTERISTIC│  │ (No factors)   │                             │
│  └───────────────┘  └────────────────┘                             │
│                                                                       │
│  ┌───────────────┐  ┌────────────────┐                             │
│  │ SLS_          │  │ Service loads  │                             │
│  │ CHARACTERISTIC│  │ Crack checks   │                             │
│  └───────────────┘  └────────────────┘                             │
│                                                                       │
│  ┌───────────────┐  ┌────────────────┐                             │
│  │ ANALYSIS_MEAN │  │ Research       │                             │
│  │               │  │ Calibration    │                             │
│  └───────────────┘  └────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  LAYER 3: CONSTITUTIVE MODEL                        │
│  "Which stress-strain law?"                                         │
│                                                                       │
│  Concrete Models:              Steel Models:                        │
│  ┌──────────────────┐          ┌──────────────────┐                │
│  │ EC2 Parabola-  ←─┼──────────┼─ Elastic-        │                │
│  │ Rectangle        │          │   Perfectly      │                │
│  │ (ULS Design)     │          │   Plastic        │                │
│  └──────────────────┘          │   (ULS Design)   │                │
│                                 └──────────────────┘                │
│  ┌──────────────────┐                                               │
│  │ Bilinear         │          ┌──────────────────┐                │
│  │ Simplified       │          │ Hardening Model  │                │
│  │ (Teaching)       │          │ (Research)       │                │
│  └──────────────────┘          └──────────────────┘                │
│                                                                       │
│  ┌──────────────────┐          Carbon Models:                       │
│  │ Sargin Nonlinear │          ┌──────────────────┐                │
│  │ (Research)       │          │ Linear Elastic   │                │
│  └──────────────────┘          └──────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         RESULT: σ(ε)                                │
│  Stress value at strain, with full traceability                    │
│                                                                       │
│  Example:                                                            │
│  ε = -0.002 → σ = -18.2 MPa                                        │
│                                                                       │
│  Metadata:                                                           │
│  - Product: C30/37 (f_ck=30 MPa)                                   │
│  - Context: ULS_DESIGN (γ_c=1.5, f_cd=20 MPa)                      │
│  - Model: EC2 Parabola-Rectangle                                   │
│  - Parameters: {f_cd: 20, eps_c1: 0.0022, eps_cu1: 0.0035}        │
│  - Modifiers: None                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

**✅ Separation of Concerns:**
- Product database: Stores certified material properties
- Assessment context: Defines calculation rules and safety
- Constitutive model: Implements stress-strain mathematics
- Each layer independent and testable!

**✅ Flexibility:**
- Same product + different contexts → Different safety factors
- Same context + different models → Different accuracy levels
- Same model + different products → Scalable to new materials

**✅ Validation:**
- Models declare valid contexts (no research model in design!)
- Registry filters incompatible combinations
- Parameter mappers enforce code compliance

**✅ Transparency:**
- See exactly which product, context, model used
- Trace all parameter transformations
- Generate calculation reports with full documentation

**✅ Extensibility:**
- Add new material type → Update enum + register models
- Add new context → Define safety factors + applicability
- Add new model → Implement interface + register
- Add new modifier → Stack with existing ones

### Comparison Table

| Aspect | Old Approach | New Architecture |
|--------|-------------|------------------|
| **Strength Selection** | "Characteristic/Design/Mean" selector | Assessment context (ULS_DESIGN, TEACHING, etc.) |
| **Model Selection** | Hardcoded in material class | Registry pattern with filtering |
| **Safety Factors** | Hidden in `factor` parameter | Explicit in context, traceable |
| **Parameter Mapping** | Manual in each script | Automated by model.map_parameters() |
| **Validation** | User responsibility | Model declares applicability |
| **Transparency** | Unclear what values used | Full metadata with get_metadata() |
| **Extensibility** | Modify core classes | Register new models/contexts |

### Implementation Roadmap

**Phase 1: Simple Context String (Immediate)**
```python
# Add context parameter to existing code
profile.plot(..., context='uls_design')

# Simple if-else for factor selection
if context == 'uls_design':
    factor_c = 1/1.5
    factor_s = 1/1.15
else:
    factor_c = 1.0
    factor_s = 1.0
```

**Phase 2: Context Enum + Basic Mapper (Next)**
```python
# Type-safe context
context = AssessmentContext.ULS_DESIGN

# Mapper applies factors
mapper = MaterialStrengthMapper(context)
sig = mapper.get_stress(product, eps)
```

**Phase 3: Model Registry (Then)**
```python
# Select constitutive model
mapper.select_model(MaterialType.CONCRETE, "EC2 Parabola-Rectangle")

# Multiple models available
models = registry.get_available_models(material_type, context)
```

**Phase 4: Full System with Modifiers (Later)**
```python
# Complete flexibility
mapper.add_modifier(LongTermCarbonModifier(0.7))
mapper.add_modifier(TemperatureModifier(50))

# Full transparency
metadata = mapper.get_metadata(product)
generate_calculation_report(metadata)
```

---

## Key Takeaways

1. **Three Dimensions Are Independent:**
   - Product (what material)
   - Context (what calculation)
   - Model (which stress-strain law)

2. **Each Dimension Has Clear Purpose:**
   - Products: Store certified properties with traceability
   - Contexts: Define safety factors and calculation rules
   - Models: Implement stress-strain mathematics

3. **Mapping Layers Bridge Dimensions:**
   - Context → Safety factors
   - Model → Parameter transformation
   - Modifiers → Case-specific effects

4. **Validation Ensures Correctness:**
   - Models declare valid contexts
   - Registry filters incompatible combinations
   - Parameter mappers enforce code rules

5. **Transparency Is Paramount:**
   - Show which product, context, model
   - Display all parameter transformations
   - Enable calculation report generation

---

## Summary

**Assessment Context** transforms:

```
FROM: "What strength value?" (ambiguous)
TO:   "What am I calculating?" (clear)
```

**Benefits:**
- ✅ Clear semantics (ULS design vs teaching)
- ✅ Correct by default (code compliance)
- ✅ Extensible (add modifiers)
- ✅ Transparent (show all factors)
- ✅ Traceable (document decisions)

**Next Steps:**
1. Review scenarios with team
2. Agree on initial contexts to support
3. Implement simple context string (Level 1)
4. Gather feedback before full mapper pattern

---

## Related Documentation

- [Full Architecture Discussion](../../dev_docs/MATERIAL_STRENGTH_MAPPING_ARCHITECTURE.md)
- [EC2 Concrete Model](02_ec2_concrete_model.ipynb)
- [Steel Reinforcement Model](03_steel_reinforcement_model.ipynb)
- [Component Catalog Integration](COMPONENT_CATALOG_INTEGRATION.md)

---

**Questions? Suggestions?**  
Discuss in: `/dev_docs/MATERIAL_STRENGTH_MAPPING_ARCHITECTURE.md`
