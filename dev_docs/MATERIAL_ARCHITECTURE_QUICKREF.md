# Material Architecture - Quick Reference

**Last Updated:** January 20, 2026

This is a quick reference guide to the refined material model architecture. For full details, see [`MATERIAL_ARCHITECTURE_STRATEGY.md`](MATERIAL_ARCHITECTURE_STRATEGY.md).

---

## Core Concepts

### 1. The Separation Triangle

```
┌─────────────┐
│   PRODUCT   │  ← Catalog data (f_ck=30, grade="C30/37")
└──────┬──────┘
       │ creates via
       ▼
┌─────────────┐
│    MODEL    │  ← Constitutive law (σ-ε relationship)
└──────┬──────┘
       │ adjusted by
       ▼
┌─────────────┐
│   SAFETY    │  ← Context (mean/char/design strength)
└─────────────┘
```

**Key Principle:** Product ≠ Model ≠ Safety Context

---

## 2. Dual-Adapter Pattern

### Why Two Adapters?

**Problem:** Need to support multiple concerns:
- **Model Type Selection:** Which constitutive law? (parabola, bilinear, etc.)
- **Safety Level:** Which strength? (mean, characteristic, design)

**Solution:** Two independent adapters

```
Product → [ProductAdapter] → Base Model → [SafetyAdapter] → Model in Context
           ↑                                ↑
           Selects model type              Applies strength level
           Extracts parameters             Uses SAFETY_FACTORS dict
```

### Adapter 1: ProductAdapter

**Purpose:** Extract parameters for specific model type

**Example:**
```python
class ConcreteParabolaAdapter:
    def extract_params(self) -> dict:
        return {
            'f_ck': self.product.f_ck,
            'E_cm': 22000 * (self.product.f_ck / 10)**0.3,
            # Model computes n, eps_c1 internally
        }
```

**Why?** Different models need different parameters:
- Parabola-rectangle: needs `n`, `eps_c1`, `eps_cu1`
- Bilinear: needs `E_c`, `eps_cu`
- Parabola-drop: needs `eps_cu` (drop point)

### Adapter 2: SafetyAdapter

**Purpose:** Apply strength level transformation

**Example:**
```python
class ConcreteCompressionSafety:
    def get_adjusted_model(self):
        # Get sympy expression for this strength level
        safety_expr = SAFETY_FACTORS['concrete_compression'][self.strength_level]
        
        # Compute adjusted strength
        f_adjusted = safety_expr.get_value(f_ck=self.f_ck)
        # e.g., 'design' → 0.85 × 30 / 1.5 = 17 MPa
        
        # Create new model instance with adjusted strength
        return EC2ParabolaRectangle(f_ck=f_adjusted, ...)
```

**Why?** Same model type, different strength levels:
- Mean: f_cm = f_ck + 8
- Characteristic: f_ck
- Design: f_cd = 0.85 · f_ck / 1.5

---

## 3. Material Model Variants

### Concrete Compression Options

| Model Type | Description | Use Case |
|------------|-------------|----------|
| `parabola_rectangle` | EC2 standard, continuous curve | General design (ULS) |
| `bilinear` | Linear + drop at eps_cu | Simplified analysis, teaching |
| `parabola_drop` | Parabola + drop at eps_cu | High-strain scenarios |

### Concrete Tension Options

| Model Type | Description | Use Case |
|------------|-------------|----------|
| `linear` | Linear elastic until f_ct, then drop | Standard concrete |
| `fiber_reinforced` | Strain-hardening after cracking | Fiber-reinforced concrete (FRC) |

### Composition

```python
# Mix and match!
concrete = product.create_concrete_model(
    compression_type='parabola_rectangle',  # Standard compression
    tension_type='fiber_reinforced',        # FRC tension
    strength_level='design'                 # ULS context
)
```

---

## 4. Sympy Integration

### SAFETY_FACTORS Dictionary

**Structure:**
```python
SAFETY_FACTORS = {
    'concrete_compression': {
        'mean': SymbolicExpression(
            expr='f_ck + 8',
            params={'f_ck': 30},
            latex_str=r'f_{cm} = f_{ck} + 8'
        ),
        'characteristic': SymbolicExpression(
            expr='f_ck',
            latex_str=r'f_{ck}'
        ),
        'design': SymbolicExpression(
            expr='alpha_cc * f_ck / gamma_c',
            params={'alpha_cc': 0.85, 'gamma_c': 1.5},
            latex_str=r'f_{cd} = \alpha_{cc} \cdot \frac{f_{ck}}{\gamma_c}'
        ),
    },
    # ... more materials
}
```

### Benefits

1. **Algebraic transparency:** All equations visible as sympy
2. **LaTeX rendering:** Built-in documentation
3. **Extensible:** Add new factors without changing code
4. **Code-compliant:** Direct mapping to EC2 formulas

---

## 5. Usage Patterns

### Pattern 1: Simple ULS Design (90% of cases)

```python
# 1. Select product from catalog
concrete = ConcreteProduct(grade="C30/37", f_ck=30)

# 2. Create model for ULS (one line!)
concrete_uls = concrete.create_concrete_model(strength_level='design')

# 3. Use in cross-section
cs = CrossSection(shape=..., concrete=concrete_uls, reinforcement=...)
```

### Pattern 2: Teaching - Compare Model Variants

```python
concrete = ConcreteProduct(grade="C30/37")

# Create different models at same strength level
parabola = concrete.create_compression_model('parabola_rectangle', 'mean')
bilinear = concrete.create_compression_model('bilinear', 'mean')
drop = concrete.create_compression_model('parabola_drop', 'mean')

# Plot comparison
fig, ax = plt.subplots()
eps = np.linspace(-0.0035, 0, 100)
ax.plot(eps*1000, parabola.get_sig(eps), label='Parabola')
ax.plot(eps*1000, bilinear.get_sig(eps), label='Bilinear')
ax.plot(eps*1000, drop.get_sig(eps), label='Drop')

# Show equations
st.latex(parabola.get_latex())
```

### Pattern 3: Advanced - Fiber-Reinforced Concrete

```python
# Special case: different tension behavior
frc = ConcreteProduct(grade="C30/37")

concrete_frc = frc.create_concrete_model(
    compression_type='parabola_rectangle',  # Standard
    tension_type='fiber_reinforced',        # Special!
    strength_level='characteristic'
)

# FRC has strain-hardening after cracking
cs_sls = CrossSection(shape=..., concrete=concrete_frc, reinforcement=...)
```

### Pattern 4: Show Strength Level Progression

```python
concrete = ConcreteProduct(grade="C30/37")

# Create same model at different strength levels
mean = concrete.create_compression_model('parabola', 'mean')
char = concrete.create_compression_model('parabola', 'characteristic')
design = concrete.create_compression_model('parabola', 'design')

# Display in Streamlit
col1, col2, col3 = st.columns(3)
with col1:
    st.latex(mean.get_latex())
    st.write(f"f_cm = {mean.f_c:.1f} MPa")
with col2:
    st.latex(char.get_latex())
    st.write(f"f_ck = {char.f_c:.1f} MPa")
with col3:
    st.latex(design.get_latex())
    st.write(f"f_cd = {design.f_c:.1f} MPa")
```

---

## 6. Key Design Decisions

### ✅ Composition over Inheritance

**Concrete = Compression + Tension**

Benefits:
- Mix-and-match components
- Fewer model classes needed
- Clear mathematical structure

### ✅ Sympy for All Equations

**All constitutive laws as SymbolicExpression**

Benefits:
- Three-fold utility: integration, plotting, documentation
- LaTeX rendering built-in
- Can be used in symbolic integration

### ✅ Explicit Strength Levels

**No hidden transformations**

Benefits:
- User always knows what strength is active
- Can compare mean/char/design side-by-side
- Teaching-friendly

### ✅ Adapter Pattern for Extensibility

**Add new models without changing products**

Benefits:
- Open/closed principle
- Easy to add custom models
- Testable components

---

## 7. Implementation Checklist

### Week 1: Foundation
- [ ] Define SAFETY_FACTORS dict with sympy
- [ ] Implement concrete compression variants (parabola, bilinear, drop)
- [ ] Implement concrete tension variants (linear, fiber)
- [ ] Unit tests for all variants

### Week 2: Adapters
- [ ] ProductAdapter base class + concrete adapters
- [ ] SafetyAdapter base class + concrete/steel/carbon adapters
- [ ] Integration with SAFETY_FACTORS dict
- [ ] Unit tests for adapter workflow

### Week 3: Products & Composition
- [ ] Refactor ConcreteProduct with model registry
- [ ] Refactor SteelProduct with model registry
- [ ] EC2Concrete composition with `with_strength_level()`
- [ ] Integration tests

### Week 4: Context & UI
- [ ] AssessmentContext enum (ULS/SLS/Teaching)
- [ ] Streamlit model selector + equation display
- [ ] Update notebooks with new API
- [ ] Teaching notebook: "Material Models Explained"

### Week 5: Documentation
- [ ] User guide
- [ ] API reference
- [ ] Migration guide
- [ ] Video tutorial

---

## 8. Visual References

**Diagrams:**
1. [`material_architecture.puml`](material_architecture.puml) - Complete class structure
2. [`material_flow_diagram.puml`](material_flow_diagram.puml) - Creation sequence

**Render with:**
- VS Code: PlantUML extension
- Online: http://www.plantuml.com/plantuml/
- CLI: `plantuml *.puml`

---

## 9. Quick API Reference

### Product Methods

```python
# ConcreteProduct
product.create_compression_model(type, level) → CompressionLaw
product.create_tension_model(type, level) → TensionLaw
product.create_concrete_model(comp_type, tens_type, level) → EC2Concrete

# Available types for concrete
compression_types = ['parabola_rectangle', 'bilinear', 'parabola_drop']
tension_types = ['linear', 'fiber_reinforced']
strength_levels = ['mean', 'characteristic', 'design']
```

### Model Methods

```python
# All models
model.get_sig(eps: ndarray) → ndarray  # Stress-strain evaluation
model.get_latex() → str                # LaTeX equation
model.plot(ax, label)                  # Matplotlib plotting

# Composed models
concrete.with_strength_level(level) → EC2Concrete  # Create variant
concrete.get_latex_documentation() → str           # Full docs
concrete.plot_with_equations(ax)                   # Annotated plot
```

---

## 10. Common Questions

**Q: Why two adapters instead of one?**  
A: Separation of concerns. Model selection (which constitutive law) is independent from safety context (which strength level). This allows any model type with any strength level.

**Q: Why sympy instead of just hardcoding formulas?**  
A: Three-fold utility - same expression used for: (1) numerical evaluation (lambdified), (2) LaTeX rendering (documentation), (3) symbolic integration (future). Plus extensibility.

**Q: Can I add custom material models?**  
A: Yes! Implement `CompressionLaw` or `TensionLaw` interface, add to product's `AVAILABLE_MODELS` registry. See Q5 in strategy document.

**Q: Performance impact of sympy?**  
A: Negligible. Expressions are lambdified once at creation, then use fast numpy evaluation. See Q6 in strategy document.

**Q: How to handle FRC with different tension behavior?**  
A: Use `tension_type='fiber_reinforced'` when creating model. Compression and tension are independent components.

---

**For full details and rationale, see:** [`MATERIAL_ARCHITECTURE_STRATEGY.md`](MATERIAL_ARCHITECTURE_STRATEGY.md)
