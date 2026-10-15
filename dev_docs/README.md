# Developer Documentation

**Last Updated**: January 20, 2026  
**Current Phase**: Material Architecture Strategy

## 📁 Directory Structure

```
dev_docs/
├── README.md                                ← You are here
├── MATERIAL_ARCHITECTURE_STRATEGY.md        ← 🎯 ACTIVE PLANNING
├── DOCKER_DEPLOYMENT.md                     ← Server deployment guide
├── strategic/                              ← Strategic planning docs
│   ├── MATERIAL_STRENGTH_MAPPING_ARCHITECTURE.md
│   └── STATE_MANAGEMENT_STRATEGY.md
├── archive/                                ← Historical documentation
│   ├── completed/                          ← Finished work logs
│   └── planning/                           ← Past planning docs
├── phase_1_core_and_matmod/               ← ✅ COMPLETED
├── phase_2_cs_design/                     ← ✅ COMPLETED
├── phase_3_mkappa/                        ← 📋 PLANNED
└── validation/                            ← Test results
```

## 🎯 Current Status

### ✅ Phase 1: Core Module & Material Models (COMPLETED)
- Core module with BMCSModel, SymbolicExpression, UI adapters
- EC2 Concrete model, Steel reinforcement model, Carbon reinforcement model
- Interactive Jupyter notebooks and Streamlit apps
- **Location**: `phase_1_core_and_matmod/`

### ✅ Phase 2: Cross-Section Design (COMPLETED)
- Geometric shapes (RectangularShape, TShape, IShape)
- Reinforcement layers with catalog integration
- Cross-section assembly with `get_N_M(kappa, eps_bottom)` interface
- Component catalog system (steel rebars, carbon bars, textiles)
- Full Streamlit application with 6-step workflow
- **Location**: `phase_2_cs_design/`

### 🎯 Current Focus: Material Architecture Strategy (Refined)

**Goal**: Dual-adapter system for Product → Model → Safety → Context

**Key Topics**:
1. **Dual-Adapter Pattern**: ProductAdapter (model type) + SafetyAdapter (strength level)
2. **Multiple Model Variants**: Parabola-rectangle, bilinear, parabola-drop for each material
3. **Sympy-Based Safety Factors**: Algebraic expressions for all strength transformations
4. **Composable Models**: Concrete = Compression + Tension (mix-and-match)
5. **Teaching Integration**: LaTeX rendering, equation display, model comparison

**Why Now**: 
- Support multiple constitutive laws per material (parabola, bilinear, etc.)
- Enable clean separation: model type selection vs safety level application
- Provide algebraic transparency via sympy for teaching/research
- Prepare for mkappa integration with flexible material models

**Documents**: 
- `MATERIAL_ARCHITECTURE_STRATEGY.md` (full strategy)
- `MATERIAL_ARCHITECTURE_QUICKREF.md` (quick reference)
- `material_architecture.puml` (class diagram)
- `material_flow_diagram.puml` (sequence diagram)

### 📋 Phase 3: Moment-Curvature Analysis (PLANNED)
- Refactor mkappa to use modern cs_design
- Apply material architecture strategy
- **Location**: `phase_3_mkappa/`

## 📖 Key Documents

### 1. MATERIAL_ARCHITECTURE_STRATEGY.md (READ FIRST! 🎯)

**Active strategic planning for dual-adapter material model system.**

**Covers**:
- Dual-adapter pattern: ProductAdapter + SafetyAdapter
- Multiple material model variants (parabola-rectangle, bilinear, parabola-drop)
- Sympy-based safety factors and constitutive equations
- Composable concrete models (compression + tension)
- 5-week implementation roadmap
- Design decisions and trade-offs

**Visual Aids**:
- `material_architecture.puml` - Complete class structure with relationships
- `material_flow_diagram.puml` - Step-by-step creation sequence

**Quick Reference**: `MATERIAL_ARCHITECTURE_QUICKREF.md` - Usage patterns and API summary

**Why Important**: Foundation for next development phase, enables flexible material modeling

### 2. DOCKER_DEPLOYMENT.md (OPERATIONAL)

Server deployment guide for SCITE Streamlit app.

**Content**:
- systemd service configuration
- Environment setup (matching local dev)
- Deployment workflow
- Troubleshooting

### 3. Strategic Planning Documents

**Location**: `strategic/`

- **MATERIAL_STRENGTH_MAPPING_ARCHITECTURE.md**: Deep dive into assessment contexts
- **STATE_MANAGEMENT_STRATEGY.md**: Streamlit app state handling patterns

### 4. Archive (Historical Reference)

**Location**: `archive/`

- **`completed/`**: Finished work logs (cleanup, refactoring completion)
- **`planning/`**: Past planning docs (original strategy, dependency analysis)

## 🚀 Quick Start for Contributors

### If You're New:

1. **Read**: `REVISED_STRATEGY.md` - Understand the plan
2. **Review**: `phase_1_core_and_matmod/` - See what's been done
3. **Check**: Current notebooks in `notebooks/dev/` - Working examples
4. **Start**: Pick a task from current phase directory

### If You're Continuing:

1. **Check**: Current phase README for tasks
2. **Update**: Progress tracking in phase directory
3. **Test**: Run validation notebooks
4. **Document**: Update phase documentation

## 🏗️ Architecture Overview

### Dependency Chain
```
┌──────────┐
│  matmod  │  ← Material models (concrete, steel, carbon)
└────┬─────┘
     │ uses
     ↓
┌──────────┐
│cs_design │  ← Cross-section geometry + materials
└────┬─────┘
     │ uses
     ↓
┌──────────┐
│  mkappa  │  ← Moment-curvature analysis
└────┬─────┘
     │ uses
     ↓
┌──────────┐
│   mxn    │  ← Interaction diagrams
└──────────┘
```

### Modern vs Legacy

| Aspect | Legacy (bmcs_utils) | Modern (New Core) |
|--------|---------------------|-------------------|
| **Base Class** | `bu.Model` (Traits) | `BMCSModel` (Pydantic) |
| **Properties** | `tr.Property(depends_on=...)` | `@cached_property` |
| **Validation** | Trait types | Pydantic validators |
| **Symbolic Math** | `bu.SymbExpr` + `InjectSymbExpr` | `SymbolicExpression` |
| **UI** | `bu.View` (coupled) | UI adapters (decoupled) |
| **Type Hints** | None | Full type hints |

## 📝 Development Workflow

### Working on a Phase:

1. **Plan**: Review phase README, understand goals
2. **Implement**: Create modern versions of legacy components
3. **Test**: Write unit tests, validate against legacy
4. **Document**: Create notebook demonstrating usage
5. **Integrate**: Ensure works with previous phases
6. **Review**: Update phase progress tracking

### Creating New Components:

```python
# Template for new model
from bmcs_cross_section.core import BMCSModel, ui_field
from functools import cached_property

class MyComponent(BMCSModel):
    """Brief description"""
    
    # Parameters with validation
    param1: float = ui_field(
        default=1.0,
        label="Parameter 1",
        unit="mm",
        range=(0.0, 100.0),
        description="What this parameter does",
        gt=0  # Validation: must be > 0
    )
    
    # Derived properties
    @cached_property
    def derived_value(self) -> float:
        """Computed from parameters"""
        return self.param1 * 2
    
    # Methods
    def compute_something(self, input: float) -> float:
        """What this method does"""
        return self.param1 + input
```

## 🧪 Testing Strategy

### Each Phase Should Have:

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test components working together
3. **Validation Tests**: Compare with legacy implementation
4. **Demonstration Notebooks**: Show how to use the new API

### Running Tests:

```bash
# Run all tests
pytest

# Run specific phase tests
pytest tests/test_matmod.py
pytest tests/test_cs_design.py

# Run validation tests (compare with legacy)
pytest tests/validation/
```

## 📚 Additional Resources

### Documentation:
- Core module API: `bmcs_cross_section/core/README.md`
- Material models: `bmcs_cross_section/matmod/README.md`
- Examples: `notebooks/dev/`

### Streamlit Apps:
- Concrete: `streamlit run notebooks/dev/ec2_concrete_streamlit_app.py`
- Steel: `streamlit run notebooks/dev/steel_reinforcement_streamlit_app.py --server.port 8502`

### Legacy Code:
- Original implementations are preserved
- Located in original module locations
- Used for validation comparisons

## ❓ FAQ

**Q: Why not refactor everything at once?**  
A: Risk management. Each phase validates before proceeding. Can stop at any phase and have working code.

**Q: Do we keep backward compatibility?**  
A: For now, yes. Legacy code remains. New code lives alongside. Eventually migrate.

**Q: What about other material models (carbon, FRP)?**  
A: Phase 1 focused on core models (concrete, steel). Others can follow the same pattern.

**Q: When do we remove bmcs_utils dependency?**  
A: After all phases complete and code is migrated. Gradual deprecation over time.

**Q: How do I contribute?**  
A: Check current phase directory for open tasks. Follow the component template above. Write tests.

## 🎯 Success Metrics

### Code Quality:
- ✅ Type hint coverage > 90%
- ✅ Pylance errors = 0
- ✅ All tests passing

### Functionality:
- ✅ Results match legacy (within tolerance)
- ✅ Performance no worse than legacy
- ✅ All features preserved

### Usability:
- ✅ Clear API with examples
- ✅ Interactive tools (Jupyter + Streamlit)
- ✅ Comprehensive documentation

---

**Next Action**: Review `phase_2_cs_design/` and start implementing geometric shapes!
