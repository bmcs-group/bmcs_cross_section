# Material Strength Mapping Architecture - Design Discussion

**Date:** January 11, 2026  
**Status:** 🤔 Conceptual Discussion - Not Yet Implemented  
**Context:** NM Assessment enhancement for transparent strength value management

## Current Situation Analysis

### What We Have Now

**1. Component Layer (cs_components):**
```python
# Products store characteristic values + safety factors
@dataclass
class ReinforcementComponent:
    f_tk: float         # Characteristic tensile strength
    gamma_s: float = 1.15  # Safety factor
    
    @property
    def f_td(self) -> float:
        return self.f_tk / self.gamma_s
```

✅ **Strengths:**
- Clear separation: products → material models
- Safety factors stored with products
- Traceability (manufacturer, certification)

**2. Material Models (matmod):**
```python
class EC2Concrete:
    f_ck: float = 30.0    # Characteristic (input)
    factor: float = 1.0    # Generic multiplier
    
    @cached_property
    def f_cd(self) -> float:
        return self.f_ck / 1.5  # Design (computed)
    
    def get_sig(self, eps):
        # Uses f_cm = f_ck + 8 internally! ⚠️
```

❌ **Issues:**
- **Hidden semantics**: `get_sig()` uses `f_cm` (mean), not `f_ck` (characteristic)
- **Ambiguous `factor`**: What does it represent? Design? Safety? Long-term reduction?
- **No context awareness**: Model doesn't know if it's for ULS, SLS, teaching, etc.

**3. Layer/Profile Access:**
```python
class ReinforcementLayer:
    material: SteelReinforcement
    
    def get_sig(self, eps):
        return self.material.get_sig(eps)  # Direct delegation
```

❌ **Problems:**
- **No interception point** for context-aware mapping
- **Opaque**: User can't tell what strength level is being used
- **Inflexible**: Can't switch assessment contexts

## The Fundamental Challenge

### Why "Use Characteristic/Design/Mean" is NOT Orthogonal

You're absolutely right that this formulation is misleading:

```
❌ BAD: "Select strength type: [Characteristic] [Design] [Mean]"
```

**Why it's problematic:**

1. **Semantic Confusion:**
   - Characteristic: 5% fractile (testing standard)
   - Design: Characteristic / safety factor (code requirement)
   - Mean: Average from testing (NOT for design!)

2. **Context Dependency:**
   - **ULS Design** → Must use design values (f_cd, f_yd)
   - **Teaching/Analysis** → May use characteristic to show safety factors
   - **SLS Checks** → Might use characteristic (uncracked) or mean (cracked)
   - **Research** → Could use mean values for comparison

3. **Material-Specific Logic:**
   - Concrete: f_cd = α_cc × f_ck / γ_c (γ_c = 1.5)
   - Steel: f_yd = f_yk / γ_s (γ_s = 1.15)
   - Carbon: f_td = f_tk / γ_s (γ_s = 1.25)
   - Long-term carbon: Additional 0.7 factor for creep-rupture

4. **Case-Specific Modifiers:**
   - Creep coefficient φ for long-term deflection
   - Sustained load reduction for brittle materials
   - Temperature effects
   - Fatigue factors

## Proposed Architecture: Assessment Context Pattern

### Core Concept: Assessment Context as First-Class Citizen

```python
class AssessmentContext(Enum):
    """Defines the calculation context with clear semantics."""
    
    # Design contexts (normative)
    ULS_DESIGN = "uls_design"           # Ultimate Limit State → design values
    SLS_CHARACTERISTIC = "sls_char"     # Serviceability → characteristic
    SLS_QUASI_PERMANENT = "sls_qp"      # Long-term SLS → + creep
    
    # Teaching contexts (non-normative)
    TEACHING_CHARACTERISTIC = "teaching_char"  # Show characteristic curves
    TEACHING_DESIGN = "teaching_design"        # Show design curves
    
    # Research contexts
    ANALYSIS_MEAN = "analysis_mean"     # Mean values for calibration
    ANALYSIS_LOWER_BOUND = "analysis_lb" # Conservative bounds
```

### Material Strength Mapper (MSM)

**Central abstraction** for context-aware strength access:

```python
class MaterialStrengthMapper:
    """
    Maps material models to assessment-appropriate strength values.
    
    Responsibilities:
    1. Apply safety factors based on context
    2. Apply case-specific modifiers (creep, temperature, etc.)
    3. Provide transparency (what values are being used)
    4. Enable traceability (audit trail)
    """
    
    def __init__(self, context: AssessmentContext):
        self.context = context
        self.modifiers = []  # Stack of modifiers
        
    def get_concrete_strength(self, concrete: EC2Concrete) -> float:
        """Get appropriate compressive strength for context."""
        if self.context == AssessmentContext.ULS_DESIGN:
            return concrete.f_cd  # Design: f_ck / γ_c
            
        elif self.context == AssessmentContext.TEACHING_CHARACTERISTIC:
            return concrete.f_ck  # Characteristic
            
        elif self.context == AssessmentContext.ANALYSIS_MEAN:
            return concrete.f_cm  # Mean
            
        elif self.context == AssessmentContext.SLS_QUASI_PERMANENT:
            # Characteristic + long-term effects
            return concrete.f_ck  # + creep consideration in strains
            
        else:
            raise ValueError(f"Unknown context: {self.context}")
    
    def get_material_curve(self, material, eps_range):
        """
        Get stress-strain curve with all context modifiers applied.
        
        Returns: (eps, sig, metadata)
        """
        base_sig = material.get_sig(eps_range)
        
        # Apply context-specific factor
        factor = self._get_context_factor(material)
        sig = base_sig * factor
        
        # Apply modifiers (creep, temperature, etc.)
        for modifier in self.modifiers:
            sig = modifier.apply(sig, material, self.context)
        
        # Metadata for transparency
        metadata = {
            'context': self.context.value,
            'base_strength': material.f_ck,  # or f_tk
            'applied_factor': factor,
            'modifiers': [m.description for m in self.modifiers],
            'effective_strength': sig.max()
        }
        
        return eps_range, sig, metadata
    
    def _get_context_factor(self, material) -> float:
        """Get safety factor based on material type and context."""
        if isinstance(material, EC2Concrete):
            gamma_c = 1.5
            if self.context == AssessmentContext.ULS_DESIGN:
                return 1.0 / gamma_c  # Design
            elif self.context in [AssessmentContext.TEACHING_CHARACTERISTIC,
                                   AssessmentContext.SLS_CHARACTERISTIC]:
                return 1.0  # Characteristic
            elif self.context == AssessmentContext.ANALYSIS_MEAN:
                return (material.f_cm / material.f_ck)  # Mean ratio
                
        elif isinstance(material, SteelReinforcement):
            gamma_s = 1.15
            if self.context == AssessmentContext.ULS_DESIGN:
                return 1.0 / gamma_s
            else:
                return 1.0
                
        # Add carbon, textile, etc.
        
        return 1.0
    
    def add_modifier(self, modifier):
        """Add case-specific modifier (creep, temperature, etc.)."""
        self.modifiers.append(modifier)
        return self
```

### Modifier Pattern for Case-Specific Effects

```python
class StrengthModifier(ABC):
    """Base class for strength modifiers."""
    
    @abstractmethod
    def apply(self, sig, material, context):
        """Apply modification to stress values."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for transparency."""
        pass


class LongTermCarbonModifier(StrengthModifier):
    """Reduce carbon strength for long-term loading (creep-rupture)."""
    
    def __init__(self, reduction_factor=0.7):
        self.factor = reduction_factor
    
    def apply(self, sig, material, context):
        if isinstance(material, CarbonReinforcement):
            return sig * self.factor
        return sig
    
    @property
    def description(self):
        return f"Long-term carbon reduction ({self.factor})"


class CreepCoefficientModifier(StrengthModifier):
    """Apply creep effects for SLS deflection checks."""
    
    def __init__(self, phi=2.0):
        self.phi = phi
    
    def apply(self, sig, material, context):
        # Modifies effective modulus, not strength directly
        # This is a simplified example
        if context == AssessmentContext.SLS_QUASI_PERMANENT:
            return sig / (1 + self.phi)
        return sig
    
    @property
    def description(self):
        return f"Creep coefficient φ={self.phi}"
```

### Integration with StressStrainProfile

```python
class StressStrainProfile:
    def __init__(self, cs: CrossSection, 
                 mapper: Optional[MaterialStrengthMapper] = None):
        self.cs = cs
        self.mapper = mapper or MaterialStrengthMapper(
            AssessmentContext.TEACHING_CHARACTERISTIC  # Safe default
        )
    
    def get_concrete_stress_profile(self, n_points=100):
        """Get concrete stress with context-aware strength."""
        z_coords, strains = self.get_strain_profile(n_points)
        
        # Get stress through mapper for transparency
        _, stresses, metadata = self.mapper.get_material_curve(
            self.cs.concrete, strains
        )
        
        # Store metadata for display
        self._last_concrete_metadata = metadata
        
        return z_coords, stresses
```

### UI Integration: Transparent Display

```python
# In NM Assessment View
def render_nm_assessment_view():
    # Context selection
    context = st.selectbox(
        "Assessment Context",
        options=[
            ("ULS Design (f_cd, f_yd)", AssessmentContext.ULS_DESIGN),
            ("Teaching: Characteristic (f_ck, f_yk)", 
             AssessmentContext.TEACHING_CHARACTERISTIC),
            ("SLS: Characteristic", AssessmentContext.SLS_CHARACTERISTIC),
        ],
        format_func=lambda x: x[0]
    )
    
    # Create mapper with selected context
    mapper = MaterialStrengthMapper(context[1])
    
    # Optional modifiers
    if st.checkbox("Apply long-term carbon reduction"):
        mapper.add_modifier(LongTermCarbonModifier(0.7))
    
    # Create profile with mapper
    nm.profile.mapper = mapper
    
    # Plot shows context-aware values
    nm.profile.plot_stress_strain_profile(...)
    
    # Display transparency info
    with st.expander("📊 Material Values Used"):
        metadata = nm.profile._last_concrete_metadata
        st.write(f"**Context:** {metadata['context']}")
        st.write(f"**Base Strength:** {metadata['base_strength']:.1f} MPa")
        st.write(f"**Factor Applied:** {metadata['applied_factor']:.3f}")
        st.write(f"**Effective Strength:** {metadata['effective_strength']:.1f} MPa")
        if metadata['modifiers']:
            st.write(f"**Modifiers:** {', '.join(metadata['modifiers'])}")
```

## Comparison of Approaches

### Approach 1: "Strength Type" Selector (❌ Rejected)
```
Select: [Characteristic] [Design] [Mean]
```
**Problems:**
- Semantically unclear what "characteristic + carbon" means
- No place for case modifiers
- User confusion about when to use what

### Approach 2: Assessment Context (✅ Recommended)
```
Context: [ULS Design] [Teaching: Characteristic] [SLS: Quasi-Permanent]
Modifiers: [☑ Long-term carbon] [ ] Elevated temperature]
```
**Benefits:**
- **Clear intent**: "ULS Design" → user knows code requirements apply
- **Extensible**: Add modifiers without changing core interface
- **Transparent**: Metadata shows exactly what was done
- **Traceable**: Audit trail for design documentation

## Implementation Phases

### Phase 1: Minimal Viable Context (Current Sprint)
1. Add `AssessmentContext` enum
2. Implement `MaterialStrengthMapper` base
3. Support ULS_DESIGN and TEACHING_CHARACTERISTIC only
4. Add transparency display in UI

### Phase 2: Full Context Support
1. Add all EC2 contexts (SLS, accidental, seismic)
2. Implement all material-specific factors
3. Add modifier framework
4. Create context selection UI component

### Phase 3: Advanced Features
1. Long-term strength reduction (carbon, GFRP)
2. Creep coefficient support
3. Temperature effects
4. Fatigue considerations
5. Custom context definitions

### Phase 4: Documentation & Traceability
1. Generate assessment reports with used values
2. Export material metadata
3. Code compliance checking
4. Validation against hand calculations

## My Recommendation

### For Now (Short Term):

**Don't implement full system yet**, but prepare the ground:

1. **Add `context` parameter** to `plot_stress_strain_profile()`:
   ```python
   context: str = 'teaching_characteristic'  # or 'uls_design'
   ```

2. **Simple if-else logic** in StressStrainProfile:
   ```python
   if context == 'uls_design':
       concrete_factor = 1 / 1.5
       steel_factor = 1 / 1.15
       labels = ('F_cd', 'F_sd')
   else:
       concrete_factor = 1.0
       steel_factor = 1.0
       labels = ('F_ck', 'F_sk')
   ```

3. **Display transparency** in UI:
   ```python
   st.info(f"Using {context}: f_ck={...}, γ_c={...}, f_cd={...}")
   ```

### For Later (Long Term):

Implement full `MaterialStrengthMapper` pattern when:
- Multiple assessment types are needed
- Modifiers become necessary (creep, long-term)
- Traceability becomes critical
- Code compliance checking is required

## Material Model Selection & Parameter Mapping

**New Dimension:** A single material TYPE (concrete, steel, carbon) can have MULTIPLE valid constitutive models, each appropriate for different contexts and use cases.

### The Challenge

```
Product Database          Assessment Context        Constitutive Model
----------------          ------------------        ------------------
Concrete C30/37     →     ULS Design         →      Which stress-strain law?
  f_ck = 30 MPa           γ_c = 1.5                 - Parabola-rectangle?
  f_cm = 38 MPa           f_cd = 20 MPa             - Bilinear?
  E_cm = 33 GPa                                     - Sargin nonlinear?
```

**The mapping has THREE independent dimensions:**

1. **Material Type** (concrete, steel, carbon, glass) - Product classification
2. **Assessment Context** (ULS_DESIGN, SLS, TEACHING, etc.) - What calculation?
3. **Constitutive Model** (parabola-rectangle, bilinear, etc.) - Which stress-strain law?

### Material Type Classification

**Product Database Structure:**
```python
@dataclass
class MaterialProduct:
    """Base class for all material products"""
    material_type: MaterialType  # CONCRETE, STEEL, CARBON, GLASS
    name: str
    manufacturer: str
    
    # Material-type-specific parameters
    parameters: Dict[str, float]
    
    # Metadata
    certification: Optional[str]
    date_tested: Optional[datetime]
```

**Material Type Enum:**
```python
class MaterialType(Enum):
    CONCRETE = "concrete"
    STEEL = "steel"
    CARBON_FRP = "carbon"
    GLASS_FRP = "glass"
    BASALT_FRP = "basalt"
    ARAMID_FRP = "aramid"
```

### Constitutive Model Registry

Each material type has a REGISTRY of available constitutive models:

```python
class ConstitutiveModel(ABC):
    """Base class for all constitutive models"""
    
    # Metadata
    name: str
    material_type: MaterialType
    valid_contexts: List[AssessmentContext]
    
    # Parameter requirements
    @abstractmethod
    def get_required_parameters(self) -> List[str]:
        """What parameters does this model need?"""
        pass
    
    @abstractmethod
    def map_parameters(self, product: MaterialProduct, 
                       context: AssessmentContext) -> Dict[str, float]:
        """Convert product parameters → model parameters"""
        pass
    
    @abstractmethod
    def get_sig(self, eps: float, params: Dict[str, float]) -> float:
        """Compute stress given strain and parameters"""
        pass
    
    @abstractmethod
    def is_applicable(self, context: AssessmentContext, 
                     analysis_type: str) -> bool:
        """Can this model be used for this context/analysis?"""
        pass
```

### Example: Concrete Constitutive Models

**EC2 Parabola-Rectangle (Design):**
```python
class EC2ParabolaRectangle(ConstitutiveModel):
    name = "EC2 Parabola-Rectangle"
    material_type = MaterialType.CONCRETE
    valid_contexts = [
        AssessmentContext.ULS_DESIGN,
        AssessmentContext.TEACHING_DESIGN
    ]
    
    def get_required_parameters(self):
        return ['f_ck', 'eps_c1', 'eps_cu1']
    
    def map_parameters(self, product, context):
        """Convert C30/37 product → model parameters"""
        f_ck = product.parameters['f_ck']
        
        # Apply assessment context
        if context in [AssessmentContext.ULS_DESIGN, 
                       AssessmentContext.TEACHING_DESIGN]:
            f_cd = f_ck / 1.5  # Design strength
        else:
            f_cd = f_ck  # Characteristic (teaching)
        
        # EC2 Table 3.1: strain parameters based on f_ck
        if f_ck <= 50:
            eps_c1 = 0.0022
            eps_cu1 = 0.0035
        else:
            eps_c1 = 0.0022 + 0.000012 * (f_ck - 50)
            eps_cu1 = 0.0026 + 0.0035 * ((98 - f_ck) / 100) ** 4
        
        return {
            'f_cd': f_cd,
            'eps_c1': eps_c1,
            'eps_cu1': eps_cu1
        }
    
    def get_sig(self, eps, params):
        """EC2 parabola-rectangle diagram"""
        f_cd = params['f_cd']
        eps_c1 = params['eps_c1']
        eps_cu1 = params['eps_cu1']
        
        eps = abs(eps)
        if eps <= eps_c1:
            # Parabola
            eta = eps / eps_c1
            return -f_cd * (1 - (1 - eta)**2)
        elif eps <= eps_cu1:
            # Rectangle
            return -f_cd
        else:
            # Crushing
            return 0.0
    
    def is_applicable(self, context, analysis_type):
        """Only for cross-section capacity (not nonlinear FE)"""
        if context not in self.valid_contexts:
            return False
        if analysis_type in ['cross_section_capacity', 'mkappa']:
            return True
        return False
```

**Bilinear Simplified (Hand Calculations):**
```python
class BilinearConcrete(ConstitutiveModel):
    name = "Bilinear Simplified"
    material_type = MaterialType.CONCRETE
    valid_contexts = [
        AssessmentContext.ULS_DESIGN,
        AssessmentContext.TEACHING_DESIGN,
        AssessmentContext.TEACHING_CHARACTERISTIC
    ]
    
    def map_parameters(self, product, context):
        f_ck = product.parameters['f_ck']
        E_cm = product.parameters['E_cm']
        
        if context == AssessmentContext.TEACHING_CHARACTERISTIC:
            f_c = f_ck
        else:
            f_c = f_ck / 1.5
        
        eps_elastic = f_c / E_cm
        eps_crush = 0.0035
        
        return {
            'f_c': f_c,
            'E_cm': E_cm,
            'eps_elastic': eps_elastic,
            'eps_crush': eps_crush
        }
    
    def get_sig(self, eps, params):
        """Elastic-perfectly plastic"""
        eps = abs(eps)
        if eps <= params['eps_elastic']:
            return -params['E_cm'] * eps
        elif eps <= params['eps_crush']:
            return -params['f_c']
        else:
            return 0.0
    
    def is_applicable(self, context, analysis_type):
        # Good for teaching, hand calculations
        return analysis_type in ['teaching', 'simplified_analysis']
```

**Sargin Nonlinear (Research):**
```python
class SarginConcrete(ConstitutiveModel):
    name = "Sargin Nonlinear"
    material_type = MaterialType.CONCRETE
    valid_contexts = [
        AssessmentContext.ANALYSIS_MEAN,
        AssessmentContext.RESEARCH_CALIBRATION
    ]
    
    def map_parameters(self, product, context):
        f_cm = product.parameters['f_cm']  # Use MEAN for research
        E_cm = product.parameters['E_cm']
        
        eps_c1 = 0.0022
        k = 2.0  # Shape parameter (can be calibrated)
        
        return {
            'f_cm': f_cm,
            'E_cm': E_cm,
            'eps_c1': eps_c1,
            'k': k
        }
    
    def get_sig(self, eps, params):
        """Sargin equation: σ = f_cm * (k*η - η²) / (1 + (k-2)*η)"""
        # Implementation...
        pass
    
    def is_applicable(self, context, analysis_type):
        # For research and nonlinear FE
        return context == AssessmentContext.ANALYSIS_MEAN
```

### Example: Steel Reinforcement Models

**Elastic-Perfectly Plastic (EC2 Standard):**
```python
class ElasticPlasticSteel(ConstitutiveModel):
    name = "Elastic-Perfectly Plastic"
    material_type = MaterialType.STEEL
    valid_contexts = [
        AssessmentContext.ULS_DESIGN,
        AssessmentContext.SLS_CHARACTERISTIC,
        AssessmentContext.TEACHING_DESIGN
    ]
    
    def map_parameters(self, product, context):
        f_yk = product.parameters['f_yk']
        E_s = product.parameters['E_s']
        
        if context in [AssessmentContext.ULS_DESIGN, 
                       AssessmentContext.TEACHING_DESIGN]:
            f_y = f_yk / 1.15  # Design
        else:
            f_y = f_yk  # Characteristic
        
        return {
            'f_y': f_y,
            'E_s': E_s,
            'eps_y': f_y / E_s
        }
    
    def get_sig(self, eps, params):
        if abs(eps) <= params['eps_y']:
            return params['E_s'] * eps
        else:
            return np.sign(eps) * params['f_y']
```

**Elastic-Plastic with Hardening (Research):**
```python
class HardeningSteel(ConstitutiveModel):
    name = "Elastic-Plastic with Hardening"
    material_type = MaterialType.STEEL
    valid_contexts = [
        AssessmentContext.ANALYSIS_MEAN,
        AssessmentContext.RESEARCH_CALIBRATION
    ]
    
    def map_parameters(self, product, context):
        f_ym = product.parameters['f_ym']  # Mean yield
        f_um = product.parameters['f_um']  # Mean ultimate
        E_s = product.parameters['E_s']
        eps_u = product.parameters['eps_u']
        
        return {
            'f_y': f_ym,
            'f_u': f_um,
            'E_s': E_s,
            'eps_y': f_ym / E_s,
            'eps_u': eps_u,
            'E_sh': (f_um - f_ym) / (eps_u - f_ym/E_s)  # Hardening modulus
        }
```

### Material Model Registry Pattern

```python
class MaterialModelRegistry:
    """Registry of available constitutive models"""
    
    def __init__(self):
        self._models: Dict[MaterialType, List[ConstitutiveModel]] = {}
    
    def register(self, model: ConstitutiveModel):
        """Register a constitutive model"""
        if model.material_type not in self._models:
            self._models[model.material_type] = []
        self._models[model.material_type].append(model)
    
    def get_available_models(self, 
                            material_type: MaterialType,
                            context: AssessmentContext,
                            analysis_type: str) -> List[ConstitutiveModel]:
        """Get models applicable for given context"""
        models = self._models.get(material_type, [])
        return [m for m in models 
                if m.is_applicable(context, analysis_type)]
    
    def select_default(self,
                      material_type: MaterialType,
                      context: AssessmentContext,
                      analysis_type: str) -> ConstitutiveModel:
        """Select default model for context"""
        available = self.get_available_models(material_type, context, analysis_type)
        
        if not available:
            raise ValueError(f"No models available for {material_type} in {context}")
        
        # Default selection logic
        if context == AssessmentContext.ULS_DESIGN:
            # Prefer EC2 models for design
            for model in available:
                if "EC2" in model.name:
                    return model
        
        return available[0]  # First available

# Global registry
MATERIAL_MODEL_REGISTRY = MaterialModelRegistry()

# Register available models
MATERIAL_MODEL_REGISTRY.register(EC2ParabolaRectangle())
MATERIAL_MODEL_REGISTRY.register(BilinearConcrete())
MATERIAL_MODEL_REGISTRY.register(SarginConcrete())
MATERIAL_MODEL_REGISTRY.register(ElasticPlasticSteel())
MATERIAL_MODEL_REGISTRY.register(HardeningSteel())
```

### Enhanced MaterialStrengthMapper with Model Selection

```python
class MaterialStrengthMapper:
    """Maps products → models → stresses with context awareness"""
    
    def __init__(self, 
                 context: AssessmentContext,
                 analysis_type: str = 'cross_section_capacity'):
        self.context = context
        self.analysis_type = analysis_type
        self.modifiers: List[StrengthModifier] = []
        
        # Model selections (can be overridden)
        self._model_selections: Dict[MaterialType, ConstitutiveModel] = {}
    
    def select_model(self, 
                     material_type: MaterialType,
                     model_name: Optional[str] = None) -> ConstitutiveModel:
        """Select constitutive model for material type"""
        
        if model_name:
            # Explicit selection
            models = MATERIAL_MODEL_REGISTRY.get_available_models(
                material_type, self.context, self.analysis_type
            )
            model = next((m for m in models if m.name == model_name), None)
            if not model:
                raise ValueError(f"Model '{model_name}' not available")
        else:
            # Use default
            model = MATERIAL_MODEL_REGISTRY.select_default(
                material_type, self.context, self.analysis_type
            )
        
        self._model_selections[material_type] = model
        return model
    
    def get_stress(self, 
                   product: MaterialProduct,
                   eps: float) -> float:
        """Compute stress for product at strain eps"""
        
        # Get or select model
        if product.material_type not in self._model_selections:
            self.select_model(product.material_type)
        
        model = self._model_selections[product.material_type]
        
        # Map product parameters → model parameters
        params = model.map_parameters(product, self.context)
        
        # Apply modifiers (long-term, temperature, etc.)
        for modifier in self.modifiers:
            if modifier.applies_to(product.material_type):
                params = modifier.modify_parameters(params)
        
        # Compute stress
        return model.get_sig(eps, params)
    
    def get_metadata(self, product: MaterialProduct) -> Dict:
        """Get transparency information"""
        model = self._model_selections.get(product.material_type)
        
        return {
            'product': product.name,
            'material_type': product.material_type.value,
            'context': self.context.value,
            'model': model.name if model else 'Not selected',
            'parameters': model.map_parameters(product, self.context) if model else {},
            'modifiers': [m.name for m in self.modifiers]
        }
```

### Usage Example: Full Pipeline

```python
# 1. Product from database
concrete_product = MaterialProduct(
    material_type=MaterialType.CONCRETE,
    name="C30/37",
    manufacturer="Local Supplier",
    parameters={
        'f_ck': 30.0,
        'f_cm': 38.0,
        'E_cm': 33000.0
    }
)

steel_product = MaterialProduct(
    material_type=MaterialType.STEEL,
    name="B500B",
    manufacturer="ArcelorMittal",
    parameters={
        'f_yk': 500.0,
        'f_ym': 550.0,
        'E_s': 200000.0
    }
)

# 2. Define assessment context
context = AssessmentContext.ULS_DESIGN

# 3. Create mapper
mapper = MaterialStrengthMapper(context, analysis_type='cross_section_capacity')

# 4. Select models (or use defaults)
mapper.select_model(MaterialType.CONCRETE)  # → EC2ParabolaRectangle
mapper.select_model(MaterialType.STEEL)     # → ElasticPlasticSteel

# 5. Add modifiers if needed
# (none needed for simple ULS design)

# 6. Compute stresses
eps_c = -0.002
sig_c = mapper.get_stress(concrete_product, eps_c)
# → Uses f_cd = 30/1.5 = 20 MPa with parabola-rectangle

eps_s = 0.010
sig_s = mapper.get_stress(steel_product, eps_s)
# → Uses f_yd = 500/1.15 = 435 MPa (plastic plateau)

# 7. Get transparency metadata
print(mapper.get_metadata(concrete_product))
# {
#   'product': 'C30/37',
#   'material_type': 'concrete',
#   'context': 'uls_design',
#   'model': 'EC2 Parabola-Rectangle',
#   'parameters': {'f_cd': 20.0, 'eps_c1': 0.0022, 'eps_cu1': 0.0035},
#   'modifiers': []
# }
```

### Model Selection UI

```python
# Streamlit interface
st.subheader("Assessment Setup")

# Context selection
context = st.selectbox(
    "Assessment Context",
    [
        AssessmentContext.ULS_DESIGN,
        AssessmentContext.TEACHING_CHARACTERISTIC,
        AssessmentContext.SLS_CHARACTERISTIC
    ],
    format_func=lambda x: x.value.replace('_', ' ').title()
)

# Model selection
st.subheader("Constitutive Models")

available_concrete = MATERIAL_MODEL_REGISTRY.get_available_models(
    MaterialType.CONCRETE, context, 'cross_section_capacity'
)

concrete_model = st.selectbox(
    "Concrete Model",
    available_concrete,
    format_func=lambda m: f"{m.name} ({'✓' if m.is_applicable(context, 'cross_section_capacity') else '✗'})"
)

st.info(f"""
**Selected: {concrete_model.name}**

Valid for: {', '.join(c.value for c in concrete_model.valid_contexts)}

Parameters: {', '.join(concrete_model.get_required_parameters())}
""")
```

### Benefits of This Architecture

1. **Separation of Concerns**:
   - Product database: Store material properties
   - Assessment context: Define calculation intent
   - Constitutive models: Define stress-strain behavior
   - Parameter mapping: Convert between layers

2. **Extensibility**:
   - Add new material types → Register in enum
   - Add new models → Register in registry
   - Add new contexts → Update valid_contexts

3. **Validation**:
   - Model declares what contexts it's valid for
   - Registry filters to show only applicable models
   - User can't accidentally use wrong combination

4. **Transparency**:
   - See exactly which model is used
   - See all parameter mappings
   - Trace: Product → Context → Model → Parameters → Stress

5. **Flexibility**:
   - Override default model selection
   - Mix models (parabola-rectangle concrete + hardening steel)
   - Apply modifiers selectively by material type

## Open Questions for Discussion

1. **Default Context**: Should default be "teaching" or "uls_design"?
   - Teaching: Safe for exploration, clear factors shown
   - ULS: Realistic design values, but may confuse learners

2. **Model Selection UI**: Automatic vs Manual?
   - Automatic: Easier for users, but less transparent
   - Manual: More control, but overwhelming for beginners
   - Hybrid: Default with "Advanced: Custom Model" option

3. **Parameter Validation**: How to ensure product has required parameters?
   - Strict: Raise error if missing → Forces complete database
   - Lenient: Use defaults if missing → Risk wrong values
   - Recommended: Validation layer with warnings

4. **Model Compatibility**: Can models be mixed?
   - Example: EC2 concrete + Hardening steel for ULS design?
   - Need compatibility matrix?
   - Or trust user judgment with warnings?

5. **Backwards Compatibility**: How to handle existing code?
   - Option A: Default model selection transparent to user
   - Option B: Require explicit model selection (break old code)
   - Recommended: Deprecation warnings, migrate gradually

6. **Database Schema**: How to store model selections?
   - For reproducibility: Store (product_id, context, model_name)
   - For flexibility: Just store context, recompute model on load
   - Trade-off: Exact reproducibility vs evolving defaults

## Conclusion

The **Material Strength Mapping Architecture** addresses the complete lifecycle from product database to stress computation:

### Three Independent Dimensions

1. **Product Database Layer**
   - Material classification (concrete, steel, carbon, glass)
   - Certified properties (f_ck, f_tk, E_cm, manufacturer)
   - Traceability and documentation

2. **Assessment Context Layer**
   - Clear semantic intent (ULS design, SLS check, teaching, research)
   - Safety factor application (γ_c, γ_s material-specific)
   - Modifiers for special cases (long-term, temperature, creep)

3. **Constitutive Model Layer**
   - Multiple stress-strain laws per material type
   - Applicability validation (context + analysis type)
   - Parameter mapping (product properties → model parameters)

### Key Benefits

- ✅ **Clear semantics**: "ULS Design per EC2" vs "Show characteristic values"
- ✅ **Extensibility**: Add contexts, models, modifiers without refactoring
- ✅ **Validation**: Models declare valid contexts, prevent misuse
- ✅ **Transparency**: Full traceability from product → stress
- ✅ **Flexibility**: Mix and match products, contexts, models appropriately
- ✅ **Code compliance**: Automated application of EC2 rules and safety factors

### Implementation Strategy

**Phase 1 (Immediate)**: Simple context string
- Add `context` parameter to plotting/calculation functions
- Use if-else for basic strength factor selection
- Display context and factors in UI

**Phase 2 (Next)**: Context enum + mapper
- Define `AssessmentContext` enum
- Implement `MaterialStrengthMapper` class
- Support ULS_DESIGN and TEACHING contexts

**Phase 3 (Then)**: Model registry
- Create `ConstitutiveModel` base class
- Implement EC2 models (parabola-rectangle, bilinear)
- Build `MaterialModelRegistry` with filtering

**Phase 4 (Later)**: Full system with modifiers
- Implement modifier pattern for long-term, temperature effects
- Add calculation report generation
- Enable audit trail for design documentation

### Recommended Path Forward

1. **Review and discuss** this architecture with team
2. **Validate** scenarios match actual use cases  
3. **Start simple**: Implement Phase 1 (context string) now
4. **Gather feedback** from users on clarity and usability
5. **Evolve incrementally** to Phase 2/3 as needs become clear
6. **Maintain backwards compatibility** during transition

This architecture transforms ambiguous "characteristic/design/mean" selection into a clear, validated, traceable system that serves design offices, educators, and researchers with equal clarity.
- ✅ Flexibility (switch contexts easily)
- ✅ Correctness (material-specific logic encapsulated)

It avoids the pitfalls of the "strength type selector" which conflates:
- Testing standards (characteristic, mean)
- Design codes (safety factors)
- Analysis purposes (teaching, research)

**Next Step:** Start with simple context string in current implementation, 
gather feedback, then evolve toward full mapper pattern as needs clarify.

---

**Your thoughts? Should we:**
1. Start with simple context string now?
2. Wait until pattern is fully designed?
3. Prototype mapper pattern first in separate module?
