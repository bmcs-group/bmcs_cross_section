# Developer Documentation

**Last Updated**: January 10, 2026  
**Current Phase**: Phase 2 - Cross-Section Design

## 📁 Directory Structure

```
dev_docs/
├── README.md                          ← You are here
├── REVISED_STRATEGY.md                ← Current refactoring strategy
├── bmcs_utils_dependency_analysis.md  ← Technical reference
├── phase_1_core_and_matmod/          ← ✅ COMPLETED
├── phase_2_cs_design/                ← 🔄 CURRENT WORK
├── phase_3_mkappa/                   ← 📋 NEXT
└── validation/                       ← Test results
```

## 🎯 Current Status

### ✅ Phase 1: Core Module & Material Models (COMPLETED)

**Duration**: 5 days (January 6-10, 2026)

**Deliverables**:
- Core module with BMCSModel, SymbolicExpression, UI adapters
- EC2 Concrete model (modern implementation)
- Steel reinforcement model (modern implementation)
- Interactive Jupyter notebooks with widgets
- Streamlit web applications (concrete and steel)
- Validation against legacy implementations

**Location**: `phase_1_core_and_matmod/`

### 🔄 Phase 2: Cross-Section Design (CURRENT)

**Goal**: Refactor cs_design to use modern matmod

**Why This Phase**: cs_design is used by mkappa, so it must come first

**Key Components**:
1. Geometric shapes (RectangularShape, TShape, IShape)
2. Reinforcement layers (with material model integration)
3. Cross-section assembly (combines shape + materials)
4. `get_N_M(kappa, eps_top)` interface for mkappa

**Location**: `phase_2_cs_design/`

### 📋 Phase 3: Moment-Curvature Analysis (NEXT)

**Goal**: Refactor mkappa to use modern cs_design

**Location**: `phase_3_mkappa/`

## 📖 Key Documents

### 1. REVISED_STRATEGY.md (READ THIS FIRST!)

The current, correct refactoring strategy based on dependency analysis.

**Key Points**:
- Dependency chain: matmod → cs_design → mkappa → mxn
- Phase 1 (matmod): ✅ Complete
- Phase 2 (cs_design): 🔄 Current priority
- Phase 3 (mkappa): 📋 Next
- Why the order matters (dependency flow)

### 2. bmcs_utils_dependency_analysis.md (REFERENCE)

Technical analysis of bmcs_utils usage across the codebase.

**Use when**:
- Understanding legacy code patterns
- Finding bmcs_utils features to replace
- Planning refactoring of specific modules

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
