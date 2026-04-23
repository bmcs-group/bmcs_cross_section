# Material Architecture - Concrete Implementation Example

**Date:** January 20, 2026  
**Purpose:** Assess the dual-adapter pattern with a complete implementation example

---

## User Workflow Example

### Step 1: User Selects Use Case (Entry Point)

```python
from scite.assessment import AssessmentContext, UseCase

# User's first choice: What am I doing?
context = AssessmentContext(UseCase.ULS_DESIGN)

# This automatically sets:
# - strength_level = 'design'
# - f_cd = 0.85 × f_ck / 1.5
# - f_yd = f_uk / 1.15
```

**Key Point:** Use case determines safety level, NOT model type selection.

---

### Step 2: Select Material Product

```python
from scite.cs_components import ConcreteProduct, SteelProduct

# Select from catalog
concrete = ConcreteProduct(grade="C30/37")  # f_ck = 30 MPa
steel = SteelProduct(grade="B500B")        # f_uk = 500 MPa

# Check what models are available
print(concrete.list_available_models())
# Output: ['parabola_rectangle', 'bilinear', 'parabola_drop']

print(steel.list_available_models())
# Output: ['bilinear', 'bilinear_hardening']
```

---

### Step 3: Create Material Model (Model Type Selection)

```python
# Create concrete model with context
concrete_model = concrete.create_model(
    model_type='parabola_rectangle',  # User chooses constitutive law
    context=context                    # Provides safety level
)

# Create steel model with context
steel_model = steel.create_model(
    model_type='bilinear_hardening',  # User chooses constitutive law
    context=context                    # Provides safety level
)

# Under the hood:
# 1. Product looks up adapter in registry: AVAILABLE_MODELS['parabola_rectangle']
# 2. Adapter extracts parameters from product
# 3. Base model is created with product data
# 4. SafetyAdapter wraps model with context.strength_level
# 5. Returns adjusted model
```

---

## Implementation: Product with Registry

```python
from dataclasses import dataclass, field
from typing import Dict, Type

@dataclass
class ConcreteProduct:
    """Concrete product from catalog"""
    
    grade: str = "C30/37"
    f_ck: float = 30.0
    density: float = 2400.0
    
    # Model registry: maps model_type → Adapter class
    AVAILABLE_MODELS: Dict[str, Type[ProductAdapter]] = field(default_factory=lambda: {
        'parabola_rectangle': ConcreteParabolaAdapter,
        'bilinear': ConcreteBilinearAdapter,
        'parabola_drop': ConcreteParabolaDropAdapter,
    })
    
    def list_available_models(self) -> list:
        """List model types available for this product"""
        return list(self.AVAILABLE_MODELS.keys())
    
    def create_model(
        self, 
        model_type: str,
        context: AssessmentContext
    ) -> MaterialModel:
        """
        Create material model with context-aware safety level
        
        Args:
            model_type: Type of constitutive law ('parabola_rectangle', 'bilinear', etc.)
            context: Assessment context (ULS, SLS, etc.) - determines strength level
        
        Returns:
            Material model adjusted for context
        """
        # 1. Look up adapter class
        if model_type not in self.AVAILABLE_MODELS:
            raise ValueError(f"Unknown model type: {model_type}. "
                           f"Available: {self.list_available_models()}")
        
        adapter_class = self.AVAILABLE_MODELS[model_type]
        
        # 2. Create adapter with product data
        adapter = adapter_class(product=self)
        
        # 3. Extract parameters
        params = adapter.extract_params()
        
        # 4. Build base model
        base_model = adapter.build_model(**params)
        
        # 5. Apply safety factors from context
        safety_adapter = ConcreteCompressionSafety(
            model=base_model,
            strength_level=context.get_strength_level(),
            f_ck=self.f_ck
        )
        
        # 6. Return adjusted model
        return safety_adapter.get_adjusted_model()
```

---

## Implementation: Product Adapter

```python
from abc import ABC, abstractmethod

class ProductAdapter(ABC):
    """Base class for product adapters"""
    
    def __init__(self, product):
        self.product = product
    
    @abstractmethod
    def extract_params(self) -> dict:
        """Extract parameters from product for specific model type"""
        pass
    
    @abstractmethod
    def build_model(self, **params) -> MaterialModel:
        """Build base model with extracted parameters"""
        pass


class ConcreteParabolaAdapter(ProductAdapter):
    """Adapter for EC2 parabola-rectangle model"""
    
    def extract_params(self) -> dict:
        """Extract parameters needed for parabola-rectangle"""
        f_ck = self.product.f_ck
        E_cm = 22000 * (f_ck / 10)**0.3  # EC2 formula
        
        return {
            'f_ck': f_ck,
            'E_cm': E_cm,
            # Model will compute n, eps_c1 internally
        }
    
    def build_model(self, **params) -> EC2ParabolaRectangle:
        """Build parabola-rectangle model"""
        return EC2ParabolaRectangle(**params)


class ConcreteBilinearAdapter(ProductAdapter):
    """Adapter for bilinear simplified model"""
    
    def extract_params(self) -> dict:
        """Extract parameters for bilinear approximation"""
        f_ck = self.product.f_ck
        E_cm = 22000 * (f_ck / 10)**0.3
        
        return {
            'f_ck': f_ck,
            'E_c': E_cm,
            'eps_cu': 0.0035,  # Ultimate strain
        }
    
    def build_model(self, **params) -> EC2Bilinear:
        """Build bilinear model"""
        return EC2Bilinear(**params)
```

---

## Assessment: Adapter Pattern Bloat?

### Current Count
- **Concrete:** 3 adapters (parabola, bilinear, drop)
- **Steel:** 2 adapters (bilinear, bilinear_hardening)
- **Total:** 5 adapters for 2 materials

### Projection for Full Framework
Assuming typical material library:
- **Concrete:** 5 variants × 1 material = 5 adapters
- **Steel:** 3 variants × 2 types (rebar, prestressing) = 6 adapters
- **Carbon:** 2 variants × 2 types (bar, textile) = 4 adapters
- **FRP:** 2 variants × 1 material = 2 adapters

**Total: ~17 adapters** for comprehensive material library

### Is This Too Many?

**Arguments FOR the pattern:**
1. **Separation of concerns:** Each adapter is simple (30-50 lines)
2. **Testable:** Easy to unit test parameter extraction
3. **Extensible:** Add new model without touching product or existing adapters
4. **Clear:** One adapter per model type, easy to understand
5. **Maintenance:** Bug in one adapter doesn't affect others

**Arguments AGAINST:**
1. **File count:** 17 files for adapters alone
2. **Boilerplate:** Similar structure across adapters
3. **Discovery:** Need to know which adapter for which model

### Alternative: Generic Adapter?

```python
class GenericModelAdapter(ProductAdapter):
    """Generic adapter using configuration"""
    
    def __init__(self, product, model_class, param_mapping):
        super().__init__(product)
        self.model_class = model_class
        self.param_mapping = param_mapping  # Dict: model_param → extraction_func
    
    def extract_params(self) -> dict:
        params = {}
        for model_param, extractor in self.param_mapping.items():
            params[model_param] = extractor(self.product)
        return params
    
    def build_model(self, **params):
        return self.model_class(**params)


# Usage in product
AVAILABLE_MODELS = {
    'parabola_rectangle': GenericModelAdapter(
        model_class=EC2ParabolaRectangle,
        param_mapping={
            'f_ck': lambda p: p.f_ck,
            'E_cm': lambda p: 22000 * (p.f_ck / 10)**0.3,
        }
    ),
    'bilinear': GenericModelAdapter(
        model_class=EC2Bilinear,
        param_mapping={
            'f_ck': lambda p: p.f_ck,
            'E_c': lambda p: 22000 * (p.f_ck / 10)**0.3,
            'eps_cu': lambda p: 0.0035,
        }
    ),
}
```

**Generic Adapter Trade-offs:**
- ✅ Fewer files (1 adapter class instead of 17)
- ✅ Less boilerplate
- ❌ Less discoverable (configuration in dict)
- ❌ Harder to test (need to test config)
- ❌ Less flexible (can't handle complex extraction logic)

---

## Recommendation

**Start with explicit adapters, refactor to generic if needed:**

1. **Phase 1** (Implementation): Use explicit adapters
   - Clear code structure
   - Easy to debug
   - Simple to test

2. **Phase 2** (If bloat occurs): Identify patterns
   - If adapters become too similar → introduce GenericModelAdapter
   - If extraction logic complex → keep explicit adapters

3. **Hybrid approach**: 
   - Simple models (bilinear, linear) → GenericModelAdapter
   - Complex models (parabola, FRC) → Explicit adapters

---

## Complete Usage Example: ULS Design

```python
# Step 1: Define context
context = AssessmentContext(UseCase.ULS_DESIGN)  # → strength_level = 'design'

# Step 2: Select products
concrete = ConcreteProduct(grade="C30/37")
steel = SteelProduct(grade="B500B")

# Step 3: Create models (user chooses constitutive law)
concrete_model = concrete.create_model('parabola_rectangle', context)
steel_model = steel.create_model('bilinear_hardening', context)

# Under the hood:
# - concrete_model has f_cd = 0.85 × 30 / 1.5 = 17 MPa
# - steel_model has f_yd = 500 / 1.15 = 435 MPa

# Step 4: Create cross-section
cs = CrossSection(
    shape=RectangularShape(b=300, h=500),
    concrete=concrete_model,
    reinforcement=[
        ReinforcementLayer(z=450, steel_model=steel_model, As=1256)
    ]
)

# Step 5: Design
M_Rd = cs.get_moment_capacity()
print(f"Design moment capacity: {M_Rd:.2f} kNm")
```

---

## Complete Usage Example: Teaching (Compare Models)

```python
# Step 1: Teaching context allows model comparison
context = AssessmentContext(UseCase.TEACHING)  # → user can override strength_level

# Step 2: Select product
concrete = ConcreteProduct(grade="C30/37")

# Step 3: Create different model variants at mean strength
parabola = concrete.create_model('parabola_rectangle', context.with_strength_level('mean'))
bilinear = concrete.create_model('bilinear', context.with_strength_level('mean'))
drop = concrete.create_model('parabola_drop', context.with_strength_level('mean'))

# Step 4: Compare stress-strain curves
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
eps = np.linspace(-0.0035, 0, 100)

ax.plot(eps*1000, parabola.get_sig(eps), label='Parabola-Rectangle')
ax.plot(eps*1000, bilinear.get_sig(eps), label='Bilinear')
ax.plot(eps*1000, drop.get_sig(eps), label='Parabola-Drop')

ax.set_xlabel('Strain ε [‰]')
ax.set_ylabel('Stress σ [MPa]')
ax.legend()
ax.grid(True)

# Step 5: Show equations
st.latex(parabola.get_latex())
st.latex(bilinear.get_latex())
```

---

## Conclusion

**The dual-adapter pattern is justified:**

1. **Clear separation:** UseCase → strength_level, ProductAdapter → model_type
2. **Manageable scale:** ~17 adapters for full library (not excessive)
3. **User-friendly workflow:** Context first, then model selection
4. **Extensible:** Add models without changing products or safety logic
5. **Can optimize later:** Generic adapter for simple cases if needed

**Key insight from example:**
- User doesn't create adapters directly
- Product registry hides complexity
- `product.create_model(type, context)` is simple and intuitive
- Adapter pattern is implementation detail, not user-facing complexity
