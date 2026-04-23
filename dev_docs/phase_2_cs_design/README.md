# Phase 2: Cross-Section Design

**Status**: 🔄 CURRENT WORK  
**Duration**: Estimated 1-2 weeks  
**Goal**: Modern cs_design using modern matmod

## Why This Phase Comes Now

**Dependency chain**: matmod → **cs_design** → mkappa

- ✅ Phase 1 (matmod) is complete - we have EC2Concrete and SteelReinforcement
- 🔄 Phase 2 (cs_design) uses matmod to define cross-sections with materials
- 📋 Phase 3 (mkappa) uses cs_design to analyze cross-sections

**Cannot proceed to mkappa without modern cs_design!**

## Current Legacy Code

Located in: `bmcs_cross_section/cs_design/`

### Key Files:
- `cs_shape.py` - Geometric shapes (Rectangle, T-beam, I-beam)
- `cs_reinf_layer.py` - Reinforcement layer definition
- `cs_layout.py` - Cross-section layout and assembly
- `cs_design.py` - Main design interface

### Dependencies:
- Uses `bmcs_utils.Model` for reactive properties
- Uses `traits` for type definitions
- UI coupled with business logic

## Refactoring Plan

### Step 1: Geometric Shapes (2-3 days)

**Goal**: Define cross-section geometry with modern API

**New file**: `bmcs_cross_section/cs_design/shapes.py`

**Components**:
```python
class Shape(BMCSModel):
    """Base class for cross-section shapes"""
    
    def get_y_coordinates(self, n: int) -> np.ndarray:
        """Discretization points"""
        
    def get_width_at_y(self, y: np.ndarray) -> np.ndarray:
        """Width at height y"""
        
    def get_area(self) -> float:
        """Total area"""

class RectangularShape(Shape):
    b: float  # width
    h: float  # height

class TShape(Shape):
    b_f: float  # flange width
    h_f: float  # flange height
    b_w: float  # web width
    h_w: float  # web height

class IShape(Shape):
    # Similar to T-shape but symmetric
```

**Tasks**:
- [ ] Implement `Shape` base class
- [ ] Implement `RectangularShape`
- [ ] Implement `TShape`
- [ ] Implement `IShape`
- [ ] Add validation (dimensions > 0, realistic proportions)
- [ ] Create unit tests
- [ ] Create demo notebook

### Step 2: Reinforcement Layers (2-3 days)

**Goal**: Define reinforcement with material model integration

**New file**: `bmcs_cross_section/cs_design/reinforcement.py`

**Components**:
```python
class ReinforcementLayer(BMCSModel):
    """Single layer of reinforcement"""
    
    z: float                              # Distance from top [mm]
    A_s: float                            # Steel area [mm²]
    material: SteelReinforcement          # Material model
    
    def get_sig(self, eps: float) -> float:
        """Get stress for given strain"""
        return self.material.get_sig(np.array([eps]))[0]
    
    def get_force(self, eps: float) -> float:
        """Get force: F = A_s × σ"""
        return self.A_s * self.get_sig(eps)

class ReinforcementLayout:
    """Collection of reinforcement layers"""
    
    layers: List[ReinforcementLayer]
    
    def add_layer(self, z, A_s, material=None):
        """Add layer (with default material if none)"""
        
    def get_total_area(self) -> float:
        """Total steel area"""
        
    def get_N_M(self, eps_distribution) -> tuple:
        """Compute axial force and moment"""
```

**Tasks**:
- [ ] Implement `ReinforcementLayer`
- [ ] Implement `ReinforcementLayout`
- [ ] Integration with `SteelReinforcement` from Phase 1
- [ ] Support for different steel grades
- [ ] Create unit tests
- [ ] Create demo notebook

### Step 3: Cross-Section Assembly (3-4 days)

**Goal**: Complete cross-section with geometry + materials

**New file**: `bmcs_cross_section/cs_design/cross_section.py`

**Components**:
```python
class CrossSection(BMCSModel):
    """Complete cross-section definition"""
    
    shape: Shape                           # Geometry
    concrete: EC2Concrete                  # Concrete material
    reinforcement: ReinforcementLayout     # Steel reinforcement
    
    def get_N_M(
        self, 
        kappa: float, 
        eps_top: float = 0.0
    ) -> tuple[float, float]:
        """
        Compute axial force and moment for strain distribution.
        
        This is the KEY METHOD that mkappa will use!
        
        Args:
            kappa: Curvature [1/mm]
            eps_top: Strain at top fiber [-]
            
        Returns:
            (N, M): Axial force [N] and moment [Nmm]
        """
        # 1. Get strain distribution: ε(y) = ε_top - κ×y
        # 2. Compute concrete contribution (integrate)
        # 3. Compute steel contribution (sum layers)
        # 4. Return total N and M
        
    def plot_cross_section(self, ax):
        """Visualize cross-section with materials"""
        
    def plot_strain_distribution(self, ax, kappa, eps_top):
        """Show strain profile"""
        
    def plot_stress_distribution(self, ax, kappa, eps_top):
        """Show stress profile"""
```

**Tasks**:
- [ ] Implement `CrossSection` class
- [ ] Implement `get_N_M()` method (key for mkappa)
- [ ] Implement visualization methods
- [ ] Add method to discretize cross-section
- [ ] Create comprehensive tests
- [ ] Validate against legacy cs_design
- [ ] Create demo notebook

### Step 4: Integration & Validation (2-3 days)

**Goal**: Ensure everything works together

**Tasks**:
- [ ] Create comprehensive example notebook
- [ ] Test various cross-section configurations
- [ ] Compare results with legacy implementation
- [ ] Performance benchmarking
- [ ] Create Streamlit app for interactive design
- [ ] Documentation and API reference

## Deliverables

### Code:
1. `shapes.py` - Geometric shape classes
2. `reinforcement.py` - Reinforcement layer management
3. `cross_section.py` - Complete cross-section assembly
4. Unit tests for all components

### Documentation:
1. `04_cross_section_design.ipynb` - Comprehensive demo
2. Examples with different shapes and configurations
3. Validation against legacy cs_design

### Interactive Tools:
1. `cross_section_design_streamlit_app.py` - Web UI
   - Shape selection and sizing
   - Reinforcement layout editor
   - Material selection (from Phase 1)
   - Cross-section visualization
   - Strain/stress distribution plots

## Success Criteria

### Functionality:
- ✅ Can define rectangular, T-beam, and I-beam shapes
- ✅ Can add reinforcement layers with material models
- ✅ `get_N_M(kappa, eps_top)` returns correct N and M
- ✅ Results match legacy cs_design (within 0.1% tolerance)

### Code Quality:
- ✅ Full type hints throughout
- ✅ Pylance clean (0 errors)
- ✅ All tests passing
- ✅ Test coverage > 80%

### Usability:
- ✅ Clear, documented API
- ✅ Working examples in notebook
- ✅ Interactive Streamlit app
- ✅ Can create typical cross-sections in < 10 lines of code

## Example Usage (Target API)

```python
from bmcs_cross_section.cs_design import CrossSection, RectangularShape
from bmcs_cross_section.matmod import EC2Concrete, create_steel

# 1. Define geometry
shape = RectangularShape(b=300, h=500)  # 300×500 mm

# 2. Define materials
concrete = EC2Concrete(f_cm=38.0)
steel = create_steel('B500B')

# 3. Create cross-section
cs = CrossSection(shape=shape, concrete=concrete)

# 4. Add reinforcement
cs.add_reinforcement(z=50, A_s=1000, material=steel)   # Top layer
cs.add_reinforcement(z=450, A_s=2000, material=steel)  # Bottom layer

# 5. Compute for given curvature
N, M = cs.get_N_M(kappa=0.00001, eps_top=-0.002)

# 6. Visualize
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
cs.plot_cross_section(axes[0])
cs.plot_strain_distribution(axes[1], kappa=0.00001, eps_top=-0.002)
cs.plot_stress_distribution(axes[2], kappa=0.00001, eps_top=-0.002)
plt.show()
```

## Integration with Phase 1 (matmod)

### Material Models:
```python
# Concrete from Phase 1
from bmcs_cross_section.matmod.ec2_concrete import EC2Concrete

concrete = EC2Concrete(f_cm=38.0, mu=0.2)
sig_c = concrete.get_sig(eps)

# Steel from Phase 1
from bmcs_cross_section.matmod.steel_reinforcement import create_steel

steel = create_steel('B500B', factor=1/1.15)  # Design strength
sig_s = steel.get_sig(eps)
```

### Cross-section uses these:
```python
class CrossSection:
    concrete: EC2Concrete       # ← Phase 1
    reinforcement: [
        ReinforcementLayer(material=SteelReinforcement)  # ← Phase 1
    ]
```

## Interface for Phase 3 (mkappa)

The key method mkappa needs:

```python
def get_N_M(self, kappa: float, eps_top: float) -> tuple[float, float]:
    """
    Given curvature κ and top strain ε_top, return (N, M).
    
    mkappa will:
    1. Loop over curvature values
    2. For each κ, find ε_top where N = 0 (pure bending)
    3. Record the corresponding M value
    4. Build M-κ curve
    """
```

## Questions & Decisions

### 1. Shape Types Priority
- Start with RectangularShape (simplest, most common)
- Add T-shape and I-shape after rectangular works
- Custom shapes can wait for later phase

### 2. Reinforcement Patterns
- Individual layers (most flexible)
- Can add helper functions for common patterns later
- Support for stirrups/shear reinforcement in future

### 3. Discretization
- User specifies number of points (default: 100)
- Finer discretization near compression zone
- Adaptive refinement in future if needed

### 4. Coordinate System
- Origin at top of cross-section
- Positive y downward
- Compression negative, tension positive (consistent with Phase 1)

## Risk Mitigation

### Risk 1: Integration with mkappa
- **Mitigation**: Design `get_N_M()` interface carefully upfront
- **Validation**: Test with simple hand calculations
- **Fallback**: Can adjust interface if mkappa needs changes

### Risk 2: Performance
- **Mitigation**: Profile key methods (get_N_M is critical)
- **Optimization**: Use NumPy vectorization
- **Benchmark**: Compare with legacy performance

### Risk 3: Complex shapes
- **Mitigation**: Start simple (rectangular), validate thoroughly
- **Expansion**: Add complexity incrementally
- **Testing**: Each shape has its own test suite

## Next Steps

1. **Review legacy code**: Understand current cs_design implementation
2. **Start with shapes**: Implement RectangularShape first
3. **Add reinforcement**: Simple layer implementation
4. **Integrate**: Create CrossSection that combines them
5. **Validate**: Compare with legacy results
6. **Polish**: Add UI and documentation

---

**Ready to start!** Begin with implementing `RectangularShape` in a new notebook.
