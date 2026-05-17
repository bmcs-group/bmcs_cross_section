# Component Catalog Integration with cs_design

## Overview

This document describes the integration architecture between the component catalog system (`cs_components`) and the cross-section design module (`cs_design`).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Component Catalogs                        │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │   Concrete   │ │    Steel     │ │  Carbon/Textile    │  │
│  │   Catalog    │ │    Catalog   │ │     Catalog        │  │
│  └──────┬───────┘ └──────┬───────┘ └─────────┬──────────┘  │
│         │                │                    │              │
│         ▼                ▼                    ▼              │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │   Concrete   │ │    Steel     │ │  Carbon/Textile    │  │
│  │  Component   │ │   Rebar      │ │   Component        │  │
│  │              │ │  Component   │ │                    │  │
│  └──────┬───────┘ └──────┬───────┘ └─────────┬──────────┘  │
│         │ matmod          │ matmod            │ matmod       │
└─────────┼─────────────────┼───────────────────┼──────────────┘
          │                 │                   │
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│              Cross-Section Design Module                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         CrossSectionDesign                           │   │
│  │  ┌────────────────┐     ┌─────────────────────────┐ │   │
│  │  │  matrix        │     │  cross_section_shape    │ │   │
│  │  │  (ConcreteMatMod) │     │  (Rectangle/T/I/Custom) │ │   │
│  │  └────────────────┘     └─────────────────────────┘ │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │   CrossSectionLayout (csl)                   │  │   │
│  │  │  ┌────────────┐  ┌────────────┐             │  │   │
│  │  │  │  BarLayer  │  │ FabricLayer│             │  │   │
│  │  │  │  - z (pos) │  │  - z (pos) │             │  │   │
│  │  │  │  - ds      │  │  - width   │             │  │   │
│  │  │  │  - count   │  │  - spacing │             │  │   │
│  │  │  │  - matmod  │  │  - matmod  │             │  │   │
│  │  │  └────────────┘  └────────────┘             │  │   │
│  │  └──────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. Concrete Integration

**Current Approach:**
```python
cs_design = CrossSectionDesign()
cs_design.matrix = ConcreteMatMod()  # Direct matmod assignment
```

**Catalog-Based Approach:**
```python
concrete = get_concrete_by_class('C30/37')
cs_design.matrix = concrete.matmod
```

**Benefits:**
- Automatic f_cm configuration based on strength class
- Traceability to specific concrete grade
- Design strength (f_cd) calculation with safety factors
- Consistent with EC2 parameters

### 2. Reinforcement Integration

**Current Approach:**
```python
layer = BarLayer(z=50, ds=16, count=4)
layer.matmod = SteelReinfMatMod(f_y=500, E=200000)
```

**Catalog-Based Approach:**
```python
rebar = SteelRebarComponent(nominal_diameter=16, grade='B500B')
layer = BarLayer(
    z=50,
    ds=rebar.nominal_diameter,
    count=4
)
layer.matmod = rebar.matmod  # Includes correct f_yk, E, epsilon_uk
```

**Benefits:**
- Product traceability (product_id, manufacturer)
- Automatic area calculation from catalog
- Design values (f_td) include safety factors
- Support for different materials (steel, carbon, textile)

### 3. Positioning System

All reinforcement types use consistent positioning:

| Parameter | Type | Description | Units |
|-----------|------|-------------|-------|
| `z` | float | Vertical distance from bottom | mm |
| `x_offset` | float | Horizontal offset (optional) | mm |
| **Bar-Specific:** | | | |
| `ds` | float | Bar diameter | mm |
| `count` | int | Number of bars | - |
| **Textile-Specific:** | | | |
| `width` | float | Fabric width | mm |
| `spacing` | float | Grid spacing | mm |
| `A_roving` | float | Area per roving | mm² |

## Workflow Example

### Step 1: Select Components from Catalog

```python
from bmcs_cross_section.cs_components import (
    get_concrete_by_class,
    SteelRebarComponent,
    TextileReinforcementComponent
)

# Select concrete
concrete = get_concrete_by_class('C30/37')

# Select reinforcement
bottom_rebar = SteelRebarComponent(nominal_diameter=16, grade='B500B')
top_rebar = SteelRebarComponent(nominal_diameter=12, grade='B500B')
textile = TextileReinforcementComponent(material_type='carbon', roving_tex=3300)
```

### Step 2: Create Cross-Section Design

```python
from bmcs_cross_section.cs_design import CrossSectionDesign

cs = CrossSectionDesign(name='My Beam')
cs.cross_section_shape = 'rectangle'
cs.cross_section_shape_.b = 300
cs.cross_section_shape_.H = 500

# Assign concrete
cs.matrix = concrete.matmod
```

### Step 3: Add Reinforcement Layers

```python
from bmcs_cross_section.cs_design import BarLayer, FabricLayer

# Bottom steel
bottom_layer = BarLayer(
    name='Bottom bars',
    z=50,
    ds=bottom_rebar.nominal_diameter,
    count=4
)
bottom_layer.matmod = bottom_rebar.matmod
cs.csl['bottom_bars'] = bottom_layer

# Top steel
top_layer = BarLayer(
    name='Top bars',
    z=450,
    ds=top_rebar.nominal_diameter,
    count=2
)
top_layer.matmod = top_rebar.matmod
cs.csl['top_bars'] = top_layer

# Textile layer
fabric = FabricLayer(
    name='Carbon textile',
    z=15,
    width=300,
    spacing=textile.grid_spacing,
    A_roving=textile.area_per_roving
)
fabric.matmod = textile.matmod
cs.csl['textile'] = fabric
```

### Step 4: Use in Analysis

```python
# The cross-section is now ready for Phase 3 (mkappa analysis)
# All material properties come from validated catalog components
```

## Enhanced Features (Future)

### 1. Component Attribute (Planned)

Add explicit component reference to layers:

```python
class BarLayer(ReinfLayer):
    component = tr.Instance(SteelRebarComponent)  # Store reference
    
    def _component_changed(self):
        # Auto-update parameters when component changes
        self.ds = self.component.nominal_diameter
        self.matmod = self.component.matmod
```

### 2. Component-Based Plotting

Delegate plotting to component types:

```python
class SteelRebarComponent:
    def plot_in_section(self, ax, z, x_positions, **kwargs):
        """Plot bars in cross-section at given positions"""
        for x in x_positions:
            circle = plt.Circle((x, z), self.nominal_diameter/2, 
                              color='darkred', **kwargs)
            ax.add_patch(circle)

class TextileReinforcementComponent:
    def plot_in_section(self, ax, z, x_start, x_end, **kwargs):
        """Plot textile as horizontal band"""
        ax.plot([x_start, x_end], [z, z], 
               linewidth=2, color='blue', **kwargs)
```

### 3. Bill of Materials

Generate automatic material lists:

```python
cs.generate_bom()
# Output:
# Component              | Quantity | Unit | Product ID
# -----------------------|----------|------|------------
# Concrete C30/37        | 0.15 m³  | m³   | C30/37-EC2
# Steel D16 B500B        | 4 bars   | pcs  | B500B-D16
# Steel D12 B500B        | 2 bars   | pcs  | B500B-D12
# Carbon Textile 3300tex | 0.30 m   | m    | SOLIDIAN-C3300
```

### 4. Alternative Suggestions

```python
# Find similar products
alternatives = catalog.find_alternatives(
    component=bottom_rebar,
    criteria=['diameter', 'strength'],
    tolerance=0.1
)
```

## Implementation Status

### Phase 2 (Current) - ✅ Completed
- [x] Component catalog system created
- [x] Concrete, steel, carbon, textile catalogs populated
- [x] Component classes with matmod integration
- [x] Query functions for catalog access
- [x] Streamlit catalog browser app
- [x] Integration examples in notebook 09

### Phase 2.5 (Next Steps)
- [ ] Add `component` attribute to ReinfLayer classes
- [ ] Add `concrete_component` to CrossSectionDesign
- [ ] Implement component-based plotting
- [ ] Update cs_design.ipynb with catalog workflow
- [ ] Create helper functions for common patterns
- [ ] Add bill of materials generator

### Phase 3 (Future)
- [ ] mkappa integration with catalog components
- [ ] Optimization with catalog constraints
- [ ] Cost estimation from catalog data
- [ ] Alternative product suggestions
- [ ] Multi-criteria component selection

## Files Modified/Created

### Completed:
- `bmcs_cross_section/cs_components/` - Complete catalog system
- `notebooks/dev/08_reinforcement_component_catalogue.ipynb` - Catalog introduction
- `notebooks/dev/09_using_component_catalogs.ipynb` - Usage examples + cs_design integration
- `notebooks/dev/component_catalog_app.py` - Interactive catalog browser

### To Be Modified:
- `bmcs_cross_section/cs_design/cs_reinf_layer.py` - Add component attribute
- `bmcs_cross_section/cs_design/cs_design.py` - Add concrete_component
- `bmcs_cross_section/cs_design/cs_design.ipynb` - Update with catalog workflow

## Summary

The component catalog integration provides:

1. **Product Traceability**: Link designs to specific cataloged products
2. **Consistent Properties**: All parameters from validated components
3. **Safety Integration**: Design values include appropriate safety factors
4. **Flexible Positioning**: Unified coordinate system for all reinforcement types
5. **Future-Ready**: Foundation for BOM, optimization, cost estimation

The current implementation (Phase 2) provides a working integration pattern. Future enhancements (Phase 2.5) will make the integration more explicit and automated.
