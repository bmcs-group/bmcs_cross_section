# REVISED Refactoring Strategy - Based on Dependency Analysis

**Date**: January 10, 2026  
**Revision**: Based on actual implementation experience

## Executive Summary

After implementing Phase 1 (matmod), we've identified that the **original phase ordering was incorrect**. The dependency chain is:

```
matmod → cs_design → mkappa → mxn
```

Therefore, the revised strategy is:

## ✅ Phase 1: Core + Material Models (COMPLETED)

**Status**: DONE  
**Duration**: 5 days (Day 1-5)

### Completed Work:
- ✅ Core module infrastructure (BMCSModel, SymbolicExpression, UI adapters)
- ✅ EC2 Concrete model (modern implementation)
- ✅ Steel reinforcement model (modern implementation)
- ✅ Jupyter notebook UI with interactive widgets
- ✅ Streamlit web applications (both concrete and steel)
- ✅ Validation against legacy implementations

### Deliverables:
- `bmcs_cross_section/core/` - Base classes and utilities
- `bmcs_cross_section/matmod/ec2_concrete.py` - Modern concrete model
- `bmcs_cross_section/matmod/steel_reinforcement.py` - Modern steel model
- `notebooks/dev/02_ec2_concrete_model.ipynb` - Concrete demo
- `notebooks/dev/03_steel_reinforcement_model.ipynb` - Steel demo
- `notebooks/dev/ec2_concrete_streamlit_app.py` - Concrete web app
- `notebooks/dev/steel_reinforcement_streamlit_app.py` - Steel web app

## ✅ Phase 2: Cross-Section Design (COMPLETED)

**Status**: COMPLETE  
**Duration**: 1 week (Day 6-12)  
**Goal**: Modern cs_design that uses modern matmod

### Completed Work:

All four steps of Phase 2 have been completed:

#### ✅ Step 1: Geometric Shapes (DONE)
- **File**: `bmcs_cross_section/cs_design/shapes.py`
- **Classes**: `RectangularShape`, `TShape`, `IShape`
- **Features**:
  - Full Pydantic validation with type hints
  - Cached geometric properties (area, centroid, I_y)
  - Width distribution methods for numerical integration
  - Standard coordinate system (y=0 at bottom, positive upward)
  - Variable discretization for complex shapes

#### ✅ Step 2: Reinforcement Layers (DONE)
- **File**: `bmcs_cross_section/cs_design/reinforcement.py`  
- **Classes**: `ReinforcementLayer`, `ReinforcementLayout`
- **Helper**: `create_symmetric_reinforcement()` function
- **Features**:
  - Integration with `SteelReinforcement` material model
  - Layer-based reinforcement definition
  - Automatic strain/stress computation at bar positions
  - Force and moment contributions
  - Support for multiple layers with different materials

#### ✅ Step 3: Cross-Section Assembly (DONE)
- **File**: `bmcs_cross_section/cs_design/cross_section.py`
- **Class**: `CrossSection`
- **Key Methods**:
  - `get_N_M(kappa, eps_bottom, y_ref)` - **Core interface for mkappa**
  - `get_neutral_axis(kappa)` - Finds N=0 condition (Newton-Raphson)
  - `get_strain_at_y(y, kappa, eps_bottom)` - Strain at any height
  - `get_stress_distribution(kappa, eps_bottom)` - Full stress profile
  - `plot_cross_section()` - Geometry visualization
  - `plot_strain_distribution()` - Linear strain profile
  - `plot_stress_distribution()` - Nonlinear stress profile
  - `get_summary()` - Comprehensive cross-section info
- **Features**:
  - Combines shape + concrete + reinforcement
  - Numerical integration using trapezoidal rule
  - Standard structural engineering conventions
  - Fully type-hinted and validated

#### ✅ Step 4: Integration & Testing (DONE)
- **Test Notebook**: `notebooks/dev/06_cross_section_assembly.ipynb`
  - 10 comprehensive tests covering all functionality
  - Tests for rectangular and T-sections
  - Pure compression and bending validation
  - M-κ curve generation
  - Visualization methods
  - All tests passing with corrected coordinate system
  
- **Validation Notebook**: `notebooks/dev/07_phase2_validation.ipynb`
  - Geometric property validation (hand calculations)
  - Force equilibrium verification
  - Coordinate system convention tests
  - Neutral axis finder validation
  - Material model integration tests
  - Moment reference point verification
  
- **Streamlit App**: `notebooks/dev/cross_section_design_app.py`
  - Interactive cross-section designer
  - All three shape types supported
  - Material selection and configuration
  - Real-time strain/stress analysis
  - Combined visualization panels
  - Ready for user testing

### Phase 2 Deliverables:

✅ **Core Classes**:
   - `RectangularShape`, `TShape`, `IShape` - Geometric shapes with full validation
   - `ReinforcementLayer`, `ReinforcementLayout` - Reinforcement definition with materials
   - `CrossSection` - Complete assembly with analysis capabilities

✅ **Key Interface Method**:
   - `get_N_M(kappa, eps_bottom)` - Ready for Phase 3 (mkappa) integration

✅ **Notebooks**:
   - `06_cross_section_assembly.ipynb` - Comprehensive testing (10 tests)
   - `07_phase2_validation.ipynb` - Validation against hand calculations

✅ **Streamlit App**:
   - `cross_section_design_app.py` - Interactive web application
   - Four-tab interface (Geometry, Reinforcement, Analysis, Summary)
   - Real-time visualization and analysis

✅ **Module Exports**:
   - `bmcs_cross_section/cs_design/__init__.py` - Clean API exports
   - All classes accessible via `from bmcs_cross_section.cs_design import ...`

### Success Criteria - All Met:

✅ Can define rectangular cross-section with modern API  
✅ Can add reinforcement layers with material models  
✅ Can compute N and M for given strain distribution  
✅ Results validated against hand calculations  
✅ Interactive tools work in Jupyter and Streamlit  
✅ Full type hints and Pylance clean  
✅ Standard coordinate system (y=0 at bottom)  
✅ Correct strain formula: ε(y) = ε_bottom - κ×y  
✅ All visualizations showing correct behavior  

### Key Achievements:

1. **Complete Modern Implementation**: No dependencies on legacy `bmcs_utils`
2. **Standard Conventions**: Following structural engineering standards (y from bottom)
3. **Correct Physics**: Positive curvature → compression at top, tension at bottom
4. **Type Safety**: Full Pydantic validation with type hints
5. **Ready for mkappa**: `get_N_M()` interface is exactly what Phase 3 needs
6. **Comprehensive Testing**: 10+ tests covering all functionality
7. **User-Friendly Tools**: Interactive Streamlit app for design exploration

### Why This Phase Comes Next:

1. **Dependency Requirement**: mkappa NEEDS cs_design to work
2. **Material Integration**: cs_design assigns materials to cross-section components
3. **Logical Flow**: Can't analyze a cross-section until you can define it
4. **Validation**: Can validate geometry independently before adding analysis

### Current cs_design Structure Analysis:

```
bmcs_cross_section/cs_design/
├── cs_shape.py           # Geometric shapes (rectangle, T-beam, etc.)
├── cs_layout.py          # Overall cross-section layout
├── cs_reinf_layer.py     # Reinforcement layer definition
├── cs_layout_dict.py     # Dictionary-based layout
└── cs_design.py          # Main design class
```

### Key Dependencies to Address:

1. **cs_shape.py** - Defines geometric shapes
   - Currently uses bmcs_utils.Model
   - Needs: Geometry definition (width, height, etc.)
   - **Refactor to**: BMCSModel with cached_property

2. **cs_reinf_layer.py** - Reinforcement layers
   - Currently uses bmcs_utils for material assignment
   - Needs: Position, area, material model reference
   - **Refactor to**: BMCSModel + reference to SteelReinforcement/etc.

3. **cs_layout.py** - Cross-section assembly
   - Combines shape + reinforcement layers
   - Needs: Coordinate system, discretization
   - **Refactor to**: BMCSModel that composes shapes and layers

4. **cs_design.py** - Main interface
   - High-level cross-section definition
   - **Refactor to**: Modern API with material model integration

### Refactoring Plan for cs_design:

#### Step 1: Geometric Shapes (2-3 days)
```python
# New: bmcs_cross_section/cs_design/shapes.py
from bmcs_cross_section.core import BMCSModel, ui_field
import numpy as np

class RectangularShape(BMCSModel):
    """Rectangular cross-section shape"""
    
    b: float = ui_field(
        300.0,
        label="Width b",
        unit="mm",
        range=(100.0, 1000.0),
        description="Cross-section width",
        gt=0
    )
    
    h: float = ui_field(
        500.0,
        label="Height h",
        unit="mm",
        range=(100.0, 2000.0),
        description="Cross-section height",
        gt=0
    )
    
    @cached_property
    def A_c(self) -> float:
        """Concrete area"""
        return self.b * self.h
    
    def get_y_coordinates(self, n_points: int = 100) -> np.ndarray:
        """Get vertical discretization"""
        return np.linspace(0, self.h, n_points)
    
    def get_width_at_y(self, y: np.ndarray) -> np.ndarray:
        """Get width at given height(s)"""
        return np.full_like(y, self.b)
```

#### Step 2: Reinforcement Layers (2-3 days)
```python
# New: bmcs_cross_section/cs_design/reinforcement.py
from bmcs_cross_section.core import BMCSModel, ui_field
from bmcs_cross_section.matmod.steel_reinforcement import SteelReinforcement
from typing import Optional

class ReinforcementLayer(BMCSModel):
    """Single layer of reinforcement"""
    
    z: float = ui_field(
        50.0,
        label="Distance z",
        unit="mm",
        range=(0.0, 1000.0),
        description="Distance from top of cross-section",
        ge=0
    )
    
    A_s: float = ui_field(
        1000.0,
        label="Steel area A_s",
        unit="mm²",
        range=(0.0, 10000.0),
        description="Total steel area in this layer",
        ge=0
    )
    
    material: Optional[SteelReinforcement] = None
    
    def __post_init__(self):
        """Set default material if none provided"""
        if self.material is None:
            from bmcs_cross_section.matmod.steel_reinforcement import create_steel
            self.material = create_steel('B500B')
    
    def get_sig(self, eps: float) -> float:
        """Get stress for given strain"""
        return self.material.get_sig(np.array([eps]))[0]
    
    @cached_property
    def f_sy(self) -> float:
        """Yield strength (convenience)"""
        return self.material.f_sy
```

#### Step 3: Cross-Section Assembly (3-4 days)
```python
# New: bmcs_cross_section/cs_design/cross_section.py
from bmcs_cross_section.core import BMCSModel
from typing import List
import numpy as np

class CrossSection(BMCSModel):
    """Complete cross-section with geometry and reinforcement"""
    
    shape: RectangularShape
    concrete: EC2Concrete
    reinf_layers: List[ReinforcementLayer]
    
    def __post_init__(self):
        """Initialize defaults"""
        if not self.reinf_layers:
            self.reinf_layers = []
    
    def add_reinforcement(
        self, 
        z: float, 
        A_s: float, 
        material: Optional[SteelReinforcement] = None
    ) -> ReinforcementLayer:
        """Add reinforcement layer"""
        layer = ReinforcementLayer(z=z, A_s=A_s, material=material)
        self.reinf_layers.append(layer)
        return layer
    
    def get_N_M(
        self, 
        kappa: float, 
        eps_top: float = 0.0
    ) -> tuple[float, float]:
        """
        Compute axial force and moment for given curvature and top strain.
        
        This is the key method that mkappa will use!
        
        Args:
            kappa: Curvature [1/mm]
            eps_top: Strain at top fiber [-]
            
        Returns:
            (N, M): Axial force [N] and moment [Nmm]
        """
        # Get strain distribution
        y = self.shape.get_y_coordinates()
        eps = eps_top - kappa * y
        
        # Concrete contribution
        b = self.shape.get_width_at_y(y)
        sig_c = self.concrete.get_sig(eps)
        dA_c = b * np.diff(y, prepend=0)
        
        N_c = np.sum(sig_c * dA_c)
        M_c = np.sum(sig_c * dA_c * y)
        
        # Steel contribution
        N_s = 0.0
        M_s = 0.0
        for layer in self.reinf_layers:
            eps_s = eps_top - kappa * layer.z
            sig_s = layer.get_sig(eps_s)
            N_s += sig_s * layer.A_s
            M_s += sig_s * layer.A_s * layer.z
        
        return N_c + N_s, M_c + M_s
    
    def plot_cross_section(self, ax):
        """Visualize cross-section"""
        # Draw concrete shape
        # Mark reinforcement layers
        # Add dimensions
        pass
```

#### Step 4: Integration & Testing (2-3 days)
- Create demonstration notebooks
- Validation against legacy cs_design
- Interactive Streamlit app for cross-section design
- Unit tests for each component

### Phase 2 Deliverables:

1. **Core Classes**:
   - `RectangularShape`, `TShape`, `IShape` (geometric shapes)
   - `ReinforcementLayer` (reinforcement definition)
   - `CrossSection` (complete cross-section assembly)

2. **Notebooks**:
   - `04_cross_section_design.ipynb` - Demo and testing
   - Examples with different shapes and reinforcement layouts

3. **Streamlit App**:
   - `cross_section_design_streamlit_app.py`
   - Interactive cross-section builder
   - Visualization of geometry + reinforcement
   - Material assignment interface

4. **Tests**:
   - Geometry validation
   - Reinforcement positioning
   - Material integration
   - Comparison with legacy

### Success Criteria for Phase 2:

✅ Can define rectangular cross-section with modern API  
✅ Can add reinforcement layers with material models  
✅ Can compute N and M for given strain distribution  
✅ Results match legacy cs_design (within tolerance)  
✅ Interactive tools work in Jupyter and Streamlit  
✅ Full type hints and Pylance clean  

## 📋 Phase 3: Moment-Curvature Analysis (mkappa) - NEXT PRIORITY

**Status**: READY TO START  
**Duration**: 2-3 weeks  
**Goal**: Modern mkappa using modern cs_design

### Why This Phase Comes After cs_design:

1. **mkappa USES cs_design**: ✅ Modern cs_design is now complete
2. **Clear Interface**: ✅ cs_design provides `get_N_M(kappa, eps_bottom)` method
3. **Validation Path**: ✅ Can validate analysis with tested cross-sections

### Refactoring Plan for mkappa:

#### Key Components:
1. **MKappa solver** - Iterative solution for M(κ)
2. **Discretization** - Strain distribution
3. **Convergence** - Newton-Raphson or similar
4. **Results handling** - M-κ curve storage and plotting

#### New Structure:
```python
# New: bmcs_cross_section/mkappa/solver.py
from bmcs_cross_section.core import BMCSModel
from bmcs_cross_section.cs_design import CrossSection

class MKappaSolver(BMCSModel):
    """Moment-curvature solver"""
    
    cross_section: CrossSection
    
    kappa_min: float = 0.0
    kappa_max: float = 0.0001
    n_steps: int = 100
    
    def solve(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Solve for M-κ curve.
        
        Returns:
            (kappa, M): Curvature and moment arrays
        """
        kappa_range = np.linspace(self.kappa_min, self.kappa_max, self.n_steps)
        M_values = np.zeros_like(kappa_range)
        
        for i, kappa in enumerate(kappa_range):
            # Find eps_top that gives N = 0 (pure bending)
            eps_top = self._find_neutral_axis(kappa)
            N, M = self.cross_section.get_N_M(kappa, eps_top)
            M_values[i] = M
        
        return kappa_range, M_values
    
    def _find_neutral_axis(self, kappa: float) -> float:
        """Find eps_top such that N(kappa, eps_top) = 0"""
        # Newton-Raphson or bisection
        pass
```

### Phase 3 Deliverables:

1. **Solver**: Modern MKappa implementation
2. **Notebook**: `05_mkappa_analysis.ipynb`
3. **Streamlit**: `mkappa_streamlit_app.py`
4. **Tests**: Validation vs legacy mkappa

## 📊 Phase 4: Interaction Diagrams (mxn)

**Status**: NOT STARTED  
**Duration**: 2-3 weeks  
**Goal**: M-N interaction diagrams using modern cs_design

### After Phase 3, this becomes straightforward:
- Already have `get_N_M(kappa, eps_top)` from cs_design
- Sweep over (kappa, eps_top) space to generate M-N envelope
- Visualize interaction diagram

## Summary: Revised Phase Timeline

| Phase | Duration | Status | Dependencies |
|-------|----------|--------|--------------|
| **Phase 1: matmod** | 5 days | ✅ COMPLETE | None |
| **Phase 2: cs_design** | 1 week | ✅ COMPLETE | Phase 1 |
| **Phase 3: mkappa** | 2-3 weeks | 📋 NEXT | Phase 2 |
| **Phase 4: mxn** | 2-3 weeks | 📋 Planned | Phase 3 |
| **Phase 5: Validation & Polish** | 1-2 weeks | 📋 Planned | All above |

## Why This Revised Order is Better:

### 1. **Respects Dependencies**
- Can't refactor mkappa without cs_design
- Can't refactor cs_design without matmod
- Bottom-up approach ensures each layer works before building on it

### 2. **Incremental Validation**
- Validate geometry (cs_design) before analysis (mkappa)
- Each phase has clear success criteria
- Can pivot if something doesn't work

### 3. **Practical Development Flow**
- Natural workflow: define cross-section → analyze it
- Matches how users actually work
- Can demonstrate progress at each phase

### 4. **Agile & Iterative**
- Can stop after any phase and have working code
- Each phase delivers value
- Risk is distributed across phases

## Next Immediate Actions for Phase 3:

1. **Review mkappa legacy code** - Understand current implementation
2. **Design MKappaSolver class** - Plan API and solve method
3. **Implement iterative solver** - Use cs.get_N_M() with neutral axis finding
4. **Create M-κ curve storage** - Results data structure
5. **Add convergence criteria** - Strain limits, failure detection
6. **Build visualization** - M-κ curve plotting
7. **Create demo notebook** - Validate and demonstrate
8. **Develop Streamlit app** - Interactive M-κ analysis tool

## Questions for Phase 3:

1. What convergence criteria should we use for M-κ analysis?
2. Should we detect concrete crushing (ε_c > ε_cu) and steel yielding automatically?
3. How should we handle post-peak behavior (descending branch)?
4. Should mkappa support axial load (N ≠ 0) or just pure bending (N = 0)?
5. What output format for M-κ results (arrays, DataFrame, custom class)?

---

**Phase 2 Complete!** 🎉

The modern cs_design module is fully implemented, tested, and ready for Phase 3 (mkappa) integration. The `get_N_M(kappa, eps_bottom)` interface provides exactly what mkappa needs to perform moment-curvature analysis.
