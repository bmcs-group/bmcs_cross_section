# bmcs_utils Dependency Analysis

## Overview

This document analyzes the dependency on `bmcs_utils.api` in the `bmcs_cross_section` repository. The `bmcs_utils` package is based on Enthought Traits and provides a framework for building hierarchical, reactive models with automatic UI generation.

## Current Usage Patterns

### 1. Core Framework Components

#### Model Base Class (`bu.Model`)
- **Purpose**: Base class for all computational models with reactive properties
- **Key Features**:
  - Trait-based property system with change notifications
  - Dependency tracking via `depends_on` attribute
  - Cached properties that automatically invalidate on dependencies change
  - Tree structure support for nested models (`tree`, `ipw_tree` attributes)
- **Usage Examples**:
  - `MKappa` in `mkappa/mkappa.py`
  - `CrossSectionDesign` in `cs_design/cs_design.py`
  - `MatMod` in `matmod/matmod.py`
  - All material models (concrete, reinforcement)

#### SymbExpr and InjectSymbExpr
- **Purpose**: Framework for symbolic math integration with models
- **Key Features**:
  - `SymbExpr`: Base class for symbolic expression containers
  - Defines symbolic parameters and expressions using SymPy
  - `InjectSymbExpr`: Mixin that injects lambdified methods from symbolic class
  - Protocol: `symb_class`, `symb_model_params`, `symb_expressions`
- **Usage Examples**:
  - `MKappaSymbolic` + `MKappa` (uses `InjectSymbExpr`)
  - Material models: `EC2ConcreteMatModSymbExpr` + `EC2ConcreteMatMod`
  - `SteelReinfMatModSymbExpr` + `SteelReinfMatMod`
  - `CarbonReinfMatModSymbExpr` + `CarbonReinfMatMod`
  - Pullout models: `PO_ELF_RLM`, `PullOutAModel`

**Pattern**: Separate symbolic class inherits from `SymbExpr`, main model inherits from both `Model` and `InjectSymbExpr`, and references symbolic class via `symb_class` attribute.

### 2. UI and Interactive Components

#### View System
- **Components**: `View`, `Item`
- **Purpose**: Declarative UI definition for model properties
- **Features**:
  - Automatic UI generation from model properties
  - LaTeX rendering for labels
  - Custom editors (FloatEditor, ButtonEditor, TextAreaEditor, etc.)
- **Usage**: All major model classes define `ipw_view` attribute

#### Interactive Models
- **InteractiveModel**: Base class with UI interaction capabilities
- **Usage**: `CrossSectionShapeBase` in `cs_design/cs_shape.py`

### 3. Data Types and Traits

From imports across the codebase:
- **Basic Types**: `Float`, `Int`, `Bool`, `Str`, `Array`
- **Containers**: `List`, `Instance`, `ModelList`, `ModelDict`
- **Special Types**: `EitherType` (union type selector with UI)
- **Editors**: `FloatRangeEditor`, `FloatEditor`, `ButtonEditor`, `TextAreaEditor`, `HistoryEditor`

### 4. Utility Components

- **ParametricStudy**: Framework for parameter sweep studies (`mkappa/mkappa_pstudy.py`)
- **InteractiveWindow**: UI window management
- **Cymbol**: Custom symbolic type (used in notebooks)
- **mpl_align_xaxis**: Matplotlib utility for axis alignment

## Files with bmcs_utils Dependencies

### Core Package Files (19 Python files):
1. `mkappa/mkappa.py` - Main moment-curvature model
2. `mkappa/mkappa_pstudy.py` - Parametric studies
3. `cs_design/cs_design.py` - Cross-section design
4. `cs_design/cs_shape.py` - Cross-section geometry
5. `cs_design/cs_layout.py` - Reinforcement layout (list-based)
6. `cs_design/cs_layout_dict.py` - Reinforcement layout (dict-based)
7. `cs_design/cs_reinf_layer.py` - Individual reinforcement layers
8. `matmod/matmod.py` - Material model base class
9. `matmod/reinforcement.py` - Steel and carbon reinforcement
10. `matmod/concrete_old.py` - Legacy concrete models
11. `matmod/sz_advanced.py` - Advanced shear zone model
12. `matmod/concrete/*.py` - Multiple concrete constitutive models (7 files)
13. `pullout/pull_out.py` - Pullout analytical model
14. `pullout/pullout_ELF_RLM.py` - Pullout with ELF-RLM
15. `mxn/mxn_diagram.py` - M-N interaction diagrams
16. `mxn/mxn_tree_node.py` - Tree structure for M-N
17. `mxn/cross_section.py` - Cross-section for M-N
18. `mxn/matrix_cross_section/matrix_cross_section.py` - Matrix cross-section

### Notebooks:
Multiple Jupyter notebooks in `notebooks/` directory use `bmcs_utils.api` for interactive demonstrations and teaching materials.

## Key Dependencies by Feature Area

### mkappa Package
- **Model framework**: Reactive property system, cached properties
- **SymbExpr**: Symbolic derivation of strain profiles
- **UI**: View system for parameter input

### cs_design Package
- **Model composition**: Nested models (shape, layout, materials)
- **EitherType**: User-selectable cross-section shapes
- **ModelList/ModelDict**: Managing multiple reinforcement layers

### matmod Package
- **SymbExpr**: Constitutive law derivations (stress-strain relations)
- **InjectSymbExpr**: Lambdified stress functions
- **Model**: Parameter management and caching

### mxn Package
- **Model framework**: Complex interaction diagrams
- **Tree structures**: Hierarchical model composition

### pullout Package
- **SymbExpr**: Bond-slip analytical solutions
- **Model**: Simulation framework

## Critical Features Provided by bmcs_utils

1. **Reactive Property System**: Automatic change propagation through dependency graphs
2. **Cached Property Management**: Performance optimization by caching computed results
3. **Symbolic-to-Numeric Pipeline**: SymPy → lambdify → numpy-compatible functions
4. **Hierarchical Model Composition**: Parent-child relationships, delegated attributes
5. **Automatic UI Generation**: From model structure to interactive widgets
6. **Dependency Tracking**: Via `depends_on` strings and trait notifications

## Technical Debt and Modernization Opportunities

### Issues with Current Approach:
1. **Traits dependency**: Heavy reliance on aging Enthought Traits framework
2. **Complex dependency tracking**: Manual `depends_on` strings are error-prone
3. **Mixed concerns**: Business logic coupled with UI definitions
4. **Limited type safety**: Trait types don't integrate well with modern type hints
5. **Implicit behavior**: "Magic" dependency resolution can be hard to debug

### Modern Alternatives to Consider:
1. **Pydantic**: Modern Python validation and settings management
2. **dataclasses + cached_property**: Python 3.8+ standard library
3. **attrs/cattrs**: Lightweight attribute management
4. **SymPy lambdify**: Direct usage without wrapper framework
5. **Jupyter widgets**: Modern UI framework for notebooks
6. **Streamlit/Gradio**: Modern web-based UI frameworks

## Next Steps

See `refactoring_strategy.md` for detailed migration plan.
