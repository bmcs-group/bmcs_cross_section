# CS_DESIGN Module Cleanup Plan

## Current Status (January 2026)

The `cs_design` module has both **legacy** (traits-based) and **modern** (Pydantic-based) implementations.

## Files Analysis

### ✅ Modern Implementation (KEEP)

1. **`shapes.py`** - Modern Pydantic shape classes
   - `RectangularShape`, `TShape`, `IShape`
   - Clean, type-safe, no traits dependency

2. **`reinforcement.py`** - Modern reinforcement system
   - **Redundancy identified**: `ReinforcementLayer` ≈ `AreaReinforcement`
   - **Catalog proxies**: `BarReinforcement`, `LayerReinforcement`, `AreaReinforcement`
   - **Container**: `ReinforcementLayout` (accepts all layer types)

3. **`cross_section.py`** - Modern cross-section assembly
   - `CrossSection` class combining shape + concrete + reinforcement
   - Pydantic-based, clean API

### ❌ Legacy Implementation (REMOVE/DEPRECATE)

1. **`cs_design.py`** - Old traits-based design
   - Class: `CrossSectionDesign`
   - Uses bmcs_utils traits API
   - Dependencies: `cs_layout_dict`, `cs_shape`, `ConcreteMatMod`
   - **Action**: Mark as deprecated, remove from `__init__.py`

2. **`cs_layout.py`** - Old traits-based layout
   - Class: `CrossSectionLayout` (ModelList)
   - Uses old `ReinfLayer`
   - **Action**: Remove or move to legacy folder

3. **`cs_layout_dict.py`** - Old dictionary-based layout
   - Dictionary-style cross-section layout
   - **Action**: Remove or move to legacy folder

4. **`cs_reinf_layer.py`** - Old traits-based reinforcement
   - Classes: `ReinfLayer`, `BarLayer`, `FabricLayer`
   - Uses traits `EitherType`
   - **Action**: Remove or move to legacy folder

5. **`cs_shape.py`** - Old traits-based shapes
   - Classes: `Rectangle`, `Circle`, `TShape`, `IShape`, `CustomShape`
   - Uses traits API
   - **Action**: Remove or move to legacy folder (replaced by `shapes.py`)

## Redundancy Issues

### ReinforcementLayer vs AreaReinforcement

Both classes serve the same purpose: **product-independent reinforcement with explicit area**.

**ReinforcementLayer** (older):
```python
ReinforcementLayer(z=450, A_s=1000, material=steel, name="Bottom")
```

**AreaReinforcement** (newer):
```python
AreaReinforcement(z=450, A_s=1000, material=steel, name="Bottom")
```

**Recommendation**: 
- Deprecate `ReinforcementLayer`
- Keep only `AreaReinforcement` for product-independent layers
- `ReinforcementLayout.add_layer()` should create `AreaReinforcement` instead

## Cleanup Strategy

### Phase 1: Mark as Deprecated (Safe)

1. Add deprecation warnings to legacy classes
2. Update `__init__.py` comments
3. Keep imports but mark clearly as deprecated

### Phase 2: Move to Legacy Folder (Medium Risk)

```
bmcs_cross_section/cs_design/
├── __init__.py
├── cross_section.py  ✅
├── shapes.py  ✅
├── reinforcement.py  ✅
└── legacy/
    ├── cs_design.py  (deprecated)
    ├── cs_layout.py  (deprecated)
    ├── cs_layout_dict.py  (deprecated)
    ├── cs_reinf_layer.py  (deprecated)
    └── cs_shape.py  (deprecated)
```

### Phase 3: Remove Redundancy

**In `reinforcement.py`:**

1. Deprecate `ReinforcementLayer`:
   ```python
   import warnings
   
   class ReinforcementLayer(BMCSModel):
       """DEPRECATED: Use AreaReinforcement instead."""
       
       def __init__(self, **kwargs):
           warnings.warn(
               "ReinforcementLayer is deprecated. Use AreaReinforcement instead.",
               DeprecationWarning,
               stacklevel=2
           )
           super().__init__(**kwargs)
   ```

2. Update `ReinforcementLayout.add_layer()` to create `AreaReinforcement`

3. Eventually remove `ReinforcementLayer` entirely

### Phase 4: Update Notebooks

**Notebooks using legacy API:**
- `05_reinforcement_layers.ipynb` - Uses `ReinforcementLayer`
- `07_phase2_validation.ipynb` - Uses `ReinforcementLayer`
- `08_reinforcement_component_catalogue.ipynb` - Uses `ReinforcementLayer`
- `10_cs_design_with_catalog_components.ipynb` - Uses `ReinforcementLayer`

**Action**: Update to use:
- `AreaReinforcement` for product-independent
- `BarReinforcement` for catalog bars
- `LayerReinforcement` for catalog textiles

## Final Modern API

After cleanup, `cs_design` should expose only:

```python
# Shapes
from .shapes import RectangularShape, TShape, IShape

# Reinforcement (catalog-integrated proxies)
from .reinforcement import (
    BarReinforcement,        # Proxy to bar catalog
    LayerReinforcement,      # Proxy to textile catalog
    AreaReinforcement,       # Product-independent
    ReinforcementLayout,     # Container for all layer types
    create_symmetric_reinforcement,
    create_distributed_reinforcement,
)

# Cross-section assembly
from .cross_section import CrossSection
```

**No more**: `ReinforcementLayer`, `CrossSectionDesign`, old shape classes, etc.

## Migration Guide for Users

### Old Code (deprecated):
```python
from bmcs_cross_section.cs_design import ReinforcementLayer, ReinforcementLayout

layer = ReinforcementLayer(z=450, A_s=1000, material=steel)
layout = ReinforcementLayout()
layout.add_layer(z=450, A_s=1000, material=steel)
```

### New Code (recommended):
```python
from bmcs_cross_section.cs_design import AreaReinforcement, ReinforcementLayout

layer = AreaReinforcement(z=450, A_s=1000, material=steel)
layout = ReinforcementLayout(layers=[layer])
```

### Catalog-Integrated (best for analysis):
```python
from bmcs_cross_section.cs_components import SteelRebarComponent
from bmcs_cross_section.cs_design import BarReinforcement, ReinforcementLayout

steel = SteelRebarComponent(nominal_diameter=20, grade='B500B')
layer = BarReinforcement(z=450, component=steel, count=6)
layout = ReinforcementLayout(layers=[layer])
```

## Summary

✅ **Keep**: `shapes.py`, `reinforcement.py`, `cross_section.py`  
❌ **Deprecate**: `cs_design.py`, `cs_layout.py`, `cs_layout_dict.py`, `cs_reinf_layer.py`, `cs_shape.py`  
🔄 **Merge**: `ReinforcementLayer` → `AreaReinforcement` (remove redundancy)  
📝 **Update**: Old notebooks to use modern API

This will result in a clean, maintainable, Pydantic-based module with catalog integration.
