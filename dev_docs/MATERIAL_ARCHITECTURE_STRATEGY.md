# Material Architecture Strategy

**Date:** January 20, 2026  
**Status:** 🎯 Active Planning - Core Architecture Design  
**Priority:** High - Foundation for next development phase

---

## The Triangle: Product - Material Model - Safety Concept - Use Case

### Core Challenge

We need a clear architecture that separates:

1. **Material Products** (catalog components)
   - Manufacturer specifications
   - Characteristic values (test data, 5% fractile)
   - Certification marks
   - Physical dimensions

2. **Material Models** (constitutive laws)
   - Stress-strain relationships
   - Mathematical formulation
   - Numerical properties

3. **Safety Concept** (code requirements)
   - Partial safety factors (γ_c, γ_s)
   - Load factors
   - Long-term reduction factors
   - Context-specific modifiers

4. **Use Cases** (application context)
   - **ULS Design**: Design values (f_cd, f_yd)
   - **SLS Verification**: Characteristic values (f_ck, f_yk) or mean values
   - **M-κ Teaching**: Characteristic values with visible safety factors
   - **Research/Analysis**: Mean values, parametric studies

---

## Current State Analysis

### What Works Well ✅

**1. Component Catalog System:**
```python
# Products store characteristic values
@dataclass
class SteelRebarComponent:
    nominal_diameter: float
    f_yk: float = 500.0  # Characteristic yield strength [MPa]
    grade: str = "B500B"
    
# Clear product → material model link
rebar = SteelRebarComponent(diameter=12)
steel_matmod = create_steel(rebar.grade)
```

**2. Separation: Components vs Models:**
- Components in `cs_components/` (products)
- Material models in `matmod/` (constitutive laws)
- No confusion between product and behavior

### What Needs Improvement 🔧

**1. Concrete Material Model - Hidden Semantics:**
```python
class EC2Concrete:
    f_ck: float = 30.0  # Input: Characteristic
    
    def get_sig(self, eps):
        # PROBLEM: Uses f_cm = f_ck + 8 internally!
        # User expects f_ck behavior, gets f_cm
```

**Issue:** The `get_sig()` method uses **mean strength** (f_cm), not characteristic (f_ck).  
**Why:** EC2 parabola-rectangle diagram is calibrated for mean values.

**2. Ambiguous Safety Factor Application:**
```python
# Current approach - unclear semantics
concrete = EC2Concrete(f_ck=30, factor=0.85)  # What does 0.85 mean?
# Is it: α_cc? Long-term reduction? Safety factor? Design conversion?
```

**3. No Use-Case Context:**
- Model doesn't know if it's being used for ULS, SLS, teaching, research
- Same material used in different contexts without clear distinction
- User can't tell what strength level is active

---

## Proposed Solution: Decomposed Material Models

### Inspiration: Legacy Concrete Structure

The original `concrete_matmod.py` had a good pattern:

```python
class ConcreteMatMod(MatMod):
    """Composed Concrete Material Model"""
    
    compression = EitherType(options=[
        ('piecewise-linear', ConcreteCompressionPWL),
        ('EC2 with plateau', ConcreteCompressionEC2Plateau),
        ('EC2', ConcreteCompressionEC2)
    ])
    
    tension = EitherType(options=[
        ('piecewise-linear', ConcreteTensionPWL)
    ])
    
    def get_sig(self, eps):
        return np.where(eps > 0,
            self.tension_.get_sig(eps),
            self.compression_.get_sig(eps)
        )
```

**Benefits:**
- Separate tension and compression laws
- Mix-and-match for special cases (e.g., fiber-reinforced tension + standard compression)
- Fewer material model variants needed
- Clear mathematical structure

### Architecture Pattern

```
┌─────────────────────────────────────────────┐
│        Material Product (Catalog)           │
│  • Manufacturer specs                       │
│  • Characteristic values (f_ck, f_yk)       │
│  • Certification                            │
└─────────────┬───────────────────────────────┘
              │ creates
              ▼
┌─────────────────────────────────────────────┐
│         Base Material Model                 │
│  • Pure constitutive law                    │
│  • Uses mean/reference values internally    │
│  • Decomposed (compression + tension)       │
└─────────────┬───────────────────────────────┘
              │ wrapped by
              ▼
┌─────────────────────────────────────────────┐
│       Context-Aware Material Adapter        │
│  • Knows use case (ULS, SLS, Teaching)      │
│  • Applies appropriate strength level       │
│  • Applies safety factors                   │
│  • Transparent to user                      │
└─────────────────────────────────────────────┘
```

---

## Concrete Material Model Redesign

### Current Problem in Detail

**EC2 Parabola-Rectangle Diagram:**
```
σ = f_cm · [1 - (1 - ε/ε_c1)^n]  for ε ≤ ε_c1
σ = f_cm                          for ε_c1 < ε ≤ ε_cu1

Where: f_cm = f_ck + 8 MPa (mean strength)
```

The diagram is **calibrated for mean strength**, not characteristic!

### Proposed Structure

**1. Base Compressive Law (Internal):**
```python
class EC2CompressionLaw:
    """Pure EC2 compressive law - uses mean strength internally"""
    
    f_cm: float  # Mean strength (explicit!)
    
    @property
    def eps_c1(self) -> float:
        """Peak strain - depends on f_cm"""
        return 0.7 * self.f_cm**0.31 / 1000
    
    def get_sig(self, eps: np.ndarray) -> np.ndarray:
        """Returns stress for mean strength level"""
        n = 1.4 + 23.4 * ((90 - self.f_cm) / 100)**4
        # ... parabola-rectangle implementation
```

**2. Tensile Law (Multiple Options):**
```python
class LinearTensionLaw:
    """Linear tension until f_ct, then sudden drop"""
    f_ctm: float  # Mean tensile strength
    E_ct: float   # Tensile modulus
    
class FiberTensionLaw:
    """For fiber-reinforced concrete - strain-hardening"""
    f_ctm: float
    eps_peak: float
    sigma_plateau: float
```

**3. Composed Concrete Model:**
```python
class EC2Concrete:
    """
    EC2 concrete material model
    Uses mean values internally (as per EC2 calibration)
    """
    
    # Input: Characteristic strength (user-facing)
    f_ck: float = 30.0
    
    # Strength level context (explicit!)
    strength_level: Literal['mean', 'characteristic', 'design'] = 'mean'
    
    # Components
    compression: EC2CompressionLaw = field(init=False)
    tension: LinearTensionLaw = field(init=False)
    
    def __post_init__(self):
        # Create internal laws with mean strength
        f_cm = self.f_ck + 8.0
        f_ctm = 0.3 * self.f_ck**(2/3)
        
        self.compression = EC2CompressionLaw(f_cm=f_cm)
        self.tension = LinearTensionLaw(f_ctm=f_ctm, E_ct=...)
    
    def get_sig(self, eps):
        """Combined tension/compression response"""
        return np.where(eps > 0,
            self.tension.get_sig(eps),
            self.compression.get_sig(eps)
        )
    
    def with_strength_level(self, level: str):
        """Return scaled model for different strength context"""
        if level == 'design':
            # Apply safety factor α_cc/γ_c = 0.85/1.5
            factor = 0.85 / 1.5
        elif level == 'characteristic':
            # Convert from mean to characteristic
            factor = self.f_ck / (self.f_ck + 8)
        else:
            factor = 1.0
        
        return ScaledConcrete(base=self, factor=factor)
```

---

## Use Case Patterns

### Pattern 1: ULS Cross-Section Design

```python
# Step 1: Select component (product)
concrete_product = ConcreteProduct(grade="C30/37")

# Step 2: Create material model
concrete = EC2Concrete(f_ck=concrete_product.f_ck)

# Step 3: Apply ULS context
concrete_design = concrete.with_strength_level('design')

# Step 4: Use in cross-section
cs = CrossSection(
    shape=RectangularShape(b=300, h=500),
    concrete=concrete_design,  # Uses f_cd = 0.85·f_ck/1.5
    reinforcement=...
)
```

### Pattern 2: SLS Deflection Check

```python
# Same concrete product
concrete_product = ConcreteProduct(grade="C30/37")

# Same base model
concrete = EC2Concrete(f_ck=concrete_product.f_ck)

# Different context - characteristic values for SLS
concrete_sls = concrete.with_strength_level('characteristic')

cs_sls = CrossSection(
    shape=...,
    concrete=concrete_sls,  # Uses f_ck (or f_cm for cracked section)
    reinforcement=...
)
```

### Pattern 3: M-κ Teaching Example

```python
# Show safety factors explicitly
concrete = EC2Concrete(f_ck=30.0)

# Student sees: mean → characteristic → design progression
st.write("Mean strength:", concrete.f_cm)
st.write("Characteristic strength:", concrete.f_ck)
st.write("Design strength:", concrete.f_cd)

# Can compare curves
fig, ax = plt.subplots()
concrete.with_strength_level('mean').plot(ax, label='Mean')
concrete.with_strength_level('characteristic').plot(ax, label='Char')
concrete.with_strength_level('design').plot(ax, label='Design')
```

---

## Implementation Roadmap

### Phase 1: Concrete Model Decomposition (Week 1)
- [ ] Create `EC2CompressionLaw` (pure parabola-rectangle)
- [ ] Create `LinearTensionLaw` (standard)
- [ ] Create `FiberTensionLaw` (optional, for FRC)
- [ ] Compose into `EC2Concrete`
- [ ] Add `with_strength_level()` method
- [ ] Unit tests for all strength levels

### Phase 2: Use-Case Contexts (Week 2)
- [ ] Define `AssessmentContext` enum (ULS, SLS, Teaching, Research)
- [ ] Create context adapters for concrete and steel
- [ ] Update cross-section assembly to accept contexts
- [ ] Add context switching in Streamlit app

### Phase 3: Steel Model Alignment (Week 3)
- [ ] Review steel model for consistency
- [ ] Add strength level methods if needed
- [ ] Ensure steel follows same pattern as concrete

### Phase 4: Documentation & Examples (Week 4)
- [ ] Update notebooks with use-case examples
- [ ] Document strength level semantics
- [ ] Create teaching examples (mean vs char vs design)
- [ ] Update Streamlit app with context selection

---

## Open Questions

1. **Should we expose compression/tension components to user?**
   - Pro: Maximum flexibility for FRC, special materials
   - Con: More complex API
   
2. **Where should long-term factors be applied?**
   - In material model? (α_cc for concrete)
   - In assessment context? (creep factor φ)
   
3. **How to handle load combinations?**
   - Part of assessment context?
   - Separate load case object?

4. **Carbon material: does it need compression law?**
   - Currently only tension
   - Should we follow same pattern for consistency?

---

## References

- Legacy implementation: `scite/matmod/legacy/concrete/concrete_matmod.py`
- Current EC2 model: `scite/matmod/ec2_concrete.py`
- Assessment context discussion: `strategic/MATERIAL_STRENGTH_MAPPING_ARCHITECTURE.md`

---

## Next Steps

1. Review this strategy with team
2. Prototype concrete decomposition
3. Test with mkappa integration
4. Implement in Streamlit app
5. Document use-case patterns
