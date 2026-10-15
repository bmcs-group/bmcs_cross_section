# Phase 1: Core Module and Material Models

**Duration**: 2 weeks (aggressive)  
**Goal**: Modern foundation with working material models and dual UI support

## Week 1: Core Infrastructure

### Day 1-2: Core Module
- [x] Create folder structure
- [ ] Implement `core/model.py` - BaseModel with Pydantic
- [ ] Implement `core/symbolic.py` - SymPy integration
- [ ] Implement `core/ui.py` - UI abstraction layer
- [ ] Implement `core/types.py` - Common types
- [ ] Write tests for core module

### Day 3-4: EC2 Concrete Model
- [ ] Refactor `matmod/concrete/ec2_concrete_matmod.py`
- [ ] Implement compression law with symbolic derivation
- [ ] Implement tension law
- [ ] Create Jupyter UI adapter
- [ ] Create Streamlit UI adapter
- [ ] Validation tests vs legacy

### Day 5: Steel Reinforcement
- [ ] Refactor `matmod/reinforcement.py` (steel)
- [ ] Implement bilinear law
- [ ] UI adapters (Jupyter + Streamlit)
- [ ] Validation tests

### Weekend: Review and Polish
- [ ] Code review
- [ ] Documentation
- [ ] Clean up tests

## Week 2: Complete Material Models + UI

### Day 6-7: Additional Models
- [ ] Carbon reinforcement
- [ ] PWL concrete (if needed for mkappa)
- [ ] Material model interface protocol
- [ ] Factory functions for model creation

### Day 8-9: UI Layer Polish
- [ ] Complete Jupyter widget system
- [ ] Create reusable plotting utilities
- [ ] Streamlit components library
- [ ] Interactive examples

### Day 10: Integration Testing
- [ ] End-to-end material model tests
- [ ] Performance benchmarks
- [ ] Validation notebook with plots

## Detailed Implementation Tasks

### Task 1: Core Module Structure

Create the following files:

```
bmcs_cross_section/
└── core/
    ├── __init__.py
    ├── model.py           # BaseModel, validation
    ├── symbolic.py        # SymPy integration
    ├── ui.py              # UI abstraction
    ├── types.py           # Type definitions
    └── plotting.py        # Plotting utilities
```

### Task 2: BaseModel Implementation

```python
# bmcs_cross_section/core/model.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, ClassVar, Optional
from functools import cached_property
import numpy as np

class BMCSModel(BaseModel):
    """
    Base model for all BMCS components.
    
    Combines Pydantic validation with NumPy compatibility
    and UI metadata support.
    """
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra='forbid'
    )
    
    # Class-level metadata for UI generation
    _ui_fields: ClassVar[dict[str, dict]] = {}
    
    def update_params(self, **kwargs) -> None:
        """Update parameters and invalidate caches"""
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def invalidate_caches(self) -> None:
        """Clear all cached properties"""
        for attr in dir(self):
            if isinstance(getattr(type(self), attr, None), cached_property):
                self.__dict__.pop(attr, None)
    
    def model_post_init(self, __context: Any) -> None:
        """Hook for post-initialization"""
        pass
```

### Task 3: SymPy Integration

```python
# bmcs_cross_section/core/symbolic.py
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Dict, Tuple
import sympy as sp
import numpy as np

@dataclass
class SymbolicExpression:
    """Container for symbolic expressions with lambdification"""
    
    name: str
    expression: sp.Expr
    parameters: Tuple[str, ...]
    _lambdified: Optional[Callable] = field(default=None, init=False)
    
    def lambdify(self, use_numpy: bool = True) -> Callable:
        """Lambdify expression for numerical evaluation"""
        if self._lambdified is None:
            modules = ['numpy'] if use_numpy else ['math']
            self._lambdified = sp.lambdify(
                self.parameters,
                self.expression,
                modules=modules
            )
        return self._lambdified
    
    def __call__(self, *args, **kwargs):
        """Direct evaluation"""
        func = self.lambdify()
        return func(*args, **kwargs)

class SymbolicModel:
    """Registry for symbolic expressions"""
    
    def __init__(self):
        self.symbols: Dict[str, sp.Symbol] = {}
        self.expressions: Dict[str, SymbolicExpression] = {}
    
    def symbol(self, name: str, **assumptions) -> sp.Symbol:
        """Define or retrieve a symbol"""
        if name not in self.symbols:
            self.symbols[name] = sp.Symbol(name, **assumptions)
        return self.symbols[name]
    
    def expression(
        self, 
        name: str, 
        expr: sp.Expr, 
        params: Tuple[str, ...]
    ) -> SymbolicExpression:
        """Register a symbolic expression"""
        symb_expr = SymbolicExpression(name, expr, params)
        self.expressions[name] = symb_expr
        return symb_expr
```

### Task 4: UI Abstraction Layer

```python
# bmcs_cross_section/core/ui.py
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple, Callable, Literal
from pydantic import Field as PydanticField

UIFramework = Literal["jupyter", "streamlit", "gradio"]

@dataclass
class UIMetadata:
    """Metadata for UI widget generation"""
    label: str
    unit: Optional[str] = None
    range: Optional[Tuple[float, float]] = None
    step: Optional[float] = None
    description: Optional[str] = None
    widget_type: str = "slider"  # slider, input, dropdown, etc.

def ui_field(
    default: Any,
    *,
    label: str,
    unit: Optional[str] = None,
    range: Optional[Tuple[float, float]] = None,
    step: Optional[float] = None,
    description: Optional[str] = None,
    **pydantic_kwargs
):
    """
    Create a Pydantic field with UI metadata.
    
    Example:
        f_cm: float = ui_field(
            30.0,
            label="f_{cm}",
            unit="MPa",
            range=(20, 100),
            description="Mean compressive strength"
        )
    """
    metadata = UIMetadata(
        label=label,
        unit=unit,
        range=range,
        step=step,
        description=description
    )
    
    return PydanticField(
        default=default,
        json_schema_extra={'ui_metadata': metadata},
        **pydantic_kwargs
    )

# UI adapters for different frameworks
class UIAdapter:
    """Base class for UI adapters"""
    
    def create_widget(self, model: Any, field_name: str) -> Any:
        """Create widget for a model field"""
        raise NotImplementedError
    
    def render_plot(self, model: Any) -> Any:
        """Render plot for model"""
        raise NotImplementedError
```

### Task 5: Refactored EC2 Concrete Model

Target structure:
```
bmcs_cross_section/matmod/
├── __init__.py
├── base.py                    # IMaterialModel protocol
├── concrete/
│   ├── __init__.py
│   ├── ec2.py                 # EC2 concrete implementation
│   └── symbolic.py            # Symbolic expressions
└── ui/
    ├── __init__.py
    ├── jupyter.py             # Jupyter adapters
    └── streamlit.py           # Streamlit adapters
```

## Testing Strategy

### Unit Tests
```
tests/
├── core/
│   ├── test_model.py
│   ├── test_symbolic.py
│   └── test_ui.py
├── matmod/
│   ├── test_concrete.py
│   ├── test_reinforcement.py
│   └── test_interface.py
└── validation/
    └── test_matmod_vs_legacy.py
```

### Validation Tests
```python
# tests/validation/test_matmod_vs_legacy.py
import pytest
import numpy as np
from numpy.testing import assert_allclose

@pytest.fixture
def eps_range():
    return np.linspace(0, 0.004, 1000)

@pytest.fixture
def legacy_ec2():
    """Legacy EC2 model from main branch"""
    # Import from copied legacy code or pickle
    pass

@pytest.fixture
def new_ec2():
    """New EC2 model"""
    from bmcs_cross_section.matmod.concrete import EC2ConcreteMatMod
    return EC2ConcreteMatMod(f_cm=30.0)

def test_compression_matches_legacy(eps_range, legacy_ec2, new_ec2):
    """Test that compression matches legacy implementation"""
    sig_legacy = legacy_ec2.get_sig(eps_range)
    sig_new = new_ec2.get_sig(eps_range)
    
    assert_allclose(sig_legacy, sig_new, rtol=1e-10)
```

## Deliverables Checklist

### Week 1
- [ ] Core module implemented and tested
- [ ] EC2 concrete model working
- [ ] Steel reinforcement working
- [ ] Basic Jupyter UI working
- [ ] Validation tests passing

### Week 2
- [ ] All material models refactored
- [ ] Full UI support (Jupyter + Streamlit)
- [ ] Complete test coverage (>80%)
- [ ] Validation notebook with comparisons
- [ ] Documentation updated
- [ ] Ready for Phase 2 (mkappa)

## Success Metrics

- ✅ All validation tests pass (100% match with legacy)
- ✅ Type hints coverage: 100%
- ✅ Test coverage: >80%
- ✅ No Pylance errors
- ✅ Interactive notebooks work
- ✅ Streamlit demo works
- ✅ Performance: No regression (within 10%)

## Files to Delete/Archive

### Delete (not mkappa-relevant)
```bash
rm -rf bmcs_cross_section/mxn/
rm -rf bmcs_cross_section/pullout/
rm -rf notebooks/temp/
rm -rf notebooks/wb_tessellation/
```

### Archive (keep reference)
```bash
git mv bmcs_cross_section/mxn bmcs_cross_section/_archived_mxn
git mv bmcs_cross_section/pullout bmcs_cross_section/_archived_pullout
```

## Daily Progress Tracking

Update this section daily:

### Day 1: [Date]
- [ ] Tasks completed
- [ ] Blockers
- [ ] Next day plan

### Day 2: [Date]
- [ ] Tasks completed
- [ ] Blockers
- [ ] Next day plan

[Continue for each day...]

## Resources

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SymPy Lambdify](https://docs.sympy.org/latest/modules/utilities/lambdify.html)
- [ipywidgets Guide](https://ipywidgets.readthedocs.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)

## Questions and Decisions

Document any decisions made during implementation:

### Decision Log
1. **Date**: Decision description and rationale
2. **Date**: Next decision...
