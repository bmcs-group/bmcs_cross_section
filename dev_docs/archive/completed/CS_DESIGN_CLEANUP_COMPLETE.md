# CS_DESIGN Module Cleanup - Completed

**Date**: January 10, 2026  
**Branch**: `restructuring_concrete_matmod`

## Changes Made

### 1. Moved Legacy Files to `legacy/` Folder

The following traits-based files have been moved to `bmcs_cross_section/cs_design/legacy/`:

**Python modules:**
- ❌ `cs_design.py` → `legacy/cs_design.py`
- ❌ `cs_layout.py` → `legacy/cs_layout.py`  
- ❌ `cs_layout_dict.py` → `legacy/cs_layout_dict.py`
- ❌ `cs_reinf_layer.py` → `legacy/cs_reinf_layer.py`
- ❌ `cs_shape.py` → `legacy/cs_shape.py`

**Notebooks:**
- ❌ `cs_design.ipynb` → `legacy/cs_design.ipynb`
- ❌ `cs_design_app.ipynb` → `legacy/cs_design_app.ipynb`

Both notebooks use the old traits-based API (`CrossSectionDesign`, `BarLayer`, etc.)

### 2. Updated `__init__.py` - Modern API Only

The module now exports only the modern Pydantic-based API:

```python
from bmcs_cross_section.cs_design import (
    # Shapes
    RectangularShape, TShape, IShape,
    # Reinforcement layers (catalog-integrated)
    BarReinforcement, LayerReinforcement, AreaReinforcement,
    # Container and utilities
    ReinforcementLayout,
    create_symmetric_reinforcement,
    create_distributed_reinforcement,
    # Cross-section assembly
    CrossSection,
)
```

### 3. Created `legacy/__init__.py` with Deprecation Warning

A deprecation warning is shown if anyone tries to import from the legacy module.

## Current Modern API Structure

```
bmcs_cross_section/cs_design/
├── __init__.py           # ✅ Modern API exports
├── shapes.py            # ✅ RectangularShape, TShape, IShape  
├── reinforcement.py     # ✅ All reinforcement layer types
├── cross_section.py     # ✅ CrossSection assembly
├── __pycache__/         # Python cache
├── .ipynb_checkpoints/  # Notebook checkpoints
└── legacy/              # ❌ Deprecated traits-based modules
    ├── __init__.py      # Deprecation warning
    ├── cs_design.py     # Old CrossSectionDesign
    ├── cs_layout.py     # Old CrossSectionLayout
    ├── cs_layout_dict.py
    ├── cs_reinf_layer.py # Old BarLayer, ReinfLayer
    ├── cs_shape.py      # Old Rectangle, TShape, etc.
    ├── cs_design.ipynb  # Old notebook
    └── cs_design_app.ipynb # Old notebook
```

**Clean modern API** - Only 4 essential files:
1. `__init__.py` - Exports
2. `shapes.py` - Geometric shapes
3. `reinforcement.py` - All layer types
4. `cross_section.py` - Assembly

## Reinforcement Layer Types (Final)

### Three Catalog-Integrated Proxies:

1. **`BarReinforcement`** - Proxy to bar catalog (steel, carbon)
   ```python
   steel = SteelRebarComponent(nominal_diameter=20, grade='B500B')
   layer = BarReinforcement(z=450, component=steel, count=6)
   # A_s = component.area × count
   ```

2. **`LayerReinforcement`** - Proxy to textile/mat catalog
   ```python
   textile = TextileReinforcementComponent(spacing=14, A_roving=1.8, ...)
   layer = LayerReinforcement(z=25, component=textile, width=300)
   # A_s = (width / spacing) × A_roving
   ```

3. **`AreaReinforcement`** - Product-independent (explicit area + material)
   ```python
   layer = AreaReinforcement(z=450, A_s=1000, material=create_steel('B500B'))
   # A_s explicitly specified, no catalog link
   ```

### Container:

**`ReinforcementLayout`** - Accepts all three layer types
```python
layout = ReinforcementLayout(layers=[layer1, layer2, layer3])
```

## About ReinforcementLayer

**Status**: Kept for backward compatibility but redundant with `AreaReinforcement`

- `ReinforcementLayer` and `AreaReinforcement` are functionally identical
- Both take explicit `z`, `A_s`, and `material`
- `ReinforcementLayer` is still exported for compatibility with old notebooks
- **Recommendation**: New code should use `AreaReinforcement`

**Future action**: Can add deprecation warning to `ReinforcementLayer` and eventually remove it.

## Notebooks Requiring Updates

The following notebooks use the old `ReinforcementLayer` class and should be updated to use the three-layer-type system:

- `notebooks/dev/05_reinforcement_layers.ipynb`
- `notebooks/dev/07_phase2_validation.ipynb`
- `notebooks/dev/08_reinforcement_component_catalogue.ipynb`
- `notebooks/dev/10_cs_design_with_catalog_components.ipynb`

**Current working notebook**:
- ✅ `notebooks/dev/11_reinforcement_catalog_integration.ipynb` - Uses new system

## Testing

Tested all modern API components:
```
✓ RectangularShape: 300.0×500.0 mm, area=150000 mm²
✓ AreaReinforcement: z=450.0, A_s=1000.0 mm²
✓ BarReinforcement: 6×D20, A_s=1885 mm²
✓ ReinforcementLayout: 2 layers
✓ CrossSection: 300.0×500.0 mm with 2 layers

✓ All modern API components working correctly!
```

## Benefits of Cleanup

1. ✅ **Single source of truth**: Only Pydantic-based modern API
2. ✅ **No traits dependency**: Clean, type-safe code
3. ✅ **Catalog integration**: Full product traceability
4. ✅ **Clear separation**: Legacy code isolated in `legacy/` folder
5. ✅ **Backward compatible**: Old imports still work via `ReinforcementLayer`
6. ✅ **Ready for Phase 3**: Clean API for mkappa integration

## Next Steps

1. ✅ **Done**: Move legacy files to `legacy/` folder
2. ✅ **Done**: Update `__init__.py` with modern API only
3. ✅ **Done**: Test modern API
4. 🔄 **Optional**: Add deprecation warning to `ReinforcementLayer`
5. 🔄 **Optional**: Update old notebooks to use new three-layer-type system
6. 🔄 **Future**: Remove `legacy/` folder entirely when no longer needed

## Migration Guide for Existing Code

### Old traits-based code:
```python
from bmcs_cross_section.cs_design.cs_design import CrossSectionDesign
from bmcs_cross_section.cs_design.cs_shape import Rectangle
cs_design = CrossSectionDesign(...)
```

### New Pydantic-based code:
```python
from bmcs_cross_section.cs_design import CrossSection, RectangularShape
from bmcs_cross_section.cs_components import get_concrete_by_class

shape = RectangularShape(b=300, h=500)
concrete = get_concrete_by_class('C30/37')
cs = CrossSection(shape=shape, concrete=concrete.matmod, reinforcement=layout)
```

### Old ReinforcementLayer:
```python
from bmcs_cross_section.cs_design import ReinforcementLayer
layer = ReinforcementLayer(z=450, A_s=1000, material=steel)
```

### New AreaReinforcement (recommended):
```python
from bmcs_cross_section.cs_design import AreaReinforcement
layer = AreaReinforcement(z=450, A_s=1000, material=steel)
```

### Or catalog-integrated (best):
```python
from bmcs_cross_section.cs_components import SteelRebarComponent
from bmcs_cross_section.cs_design import BarReinforcement

steel = SteelRebarComponent(nominal_diameter=20, grade='B500B')
layer = BarReinforcement(z=450, component=steel, count=6)
```

---

**Cleanup complete**. The `cs_design` module now has a clean, modern API with full catalog integration support.
