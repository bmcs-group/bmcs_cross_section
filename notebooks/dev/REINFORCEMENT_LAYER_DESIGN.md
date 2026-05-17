# Reinforcement Layer Design with Component Catalog Integration

## Overview

Enhanced design coupling reinforcement layers in `cs_design` with the component catalog (`cs_components`), supporting both:
- **Product-based workflow** (analysis): Known components → calculate capacities
- **Design-oriented workflow** (synthesis): Required area → select/optimize components

## Architecture

### Three Reinforcement Layer Types

```
ReinforcementLayer (base class)
├── BarReinforcement        # Linked to bar catalog (steel rebars, carbon bars)
├── LayerReinforcement      # Linked to textile/mat catalog (textiles, grids)
└── AreaReinforcement       # Product-independent (design optimization)
```

### 1. BarReinforcement

**Purpose:** Discrete reinforcement bars from catalog

**Key Attributes:**
```python
class BarReinforcement(ReinforcementLayer):
    z: float                              # Position from top [mm]
    component: SteelRebarComponent |      # Link to catalog component
                CarbonBarComponent
    count: int                            # Number of bars
    
    # Auto-calculated
    @property
    def A_s(self) -> float:
        return self.component.area * self.count
    
    @property
    def material(self):
        return self.component.matmod
```

**Usage Example:**
```python
# Product-based analysis
from bmcs_cross_section.cs_components import SteelRebarComponent

steel_d20 = SteelRebarComponent(nominal_diameter=20, grade='B500B')

bottom_layer = BarReinforcement(
    z=450,
    component=steel_d20,  # Direct catalog link
    count=4               # 4 bars
)
# A_s = 4 × 314 = 1256 mm² (automatic)
```

**Benefits:**
- ✓ Product traceability (`component.product_id`, `manufacturer`)
- ✓ Automatic area calculation
- ✓ Material properties from catalog
- ✓ BOM generation straightforward

### 2. LayerReinforcement

**Purpose:** Distributed reinforcement from textile/mat catalog

**Key Attributes:**
```python
class LayerReinforcement(ReinforcementLayer):
    z: float                                    # Position from top [mm]
    component: TextileReinforcementComponent |  # Link to catalog component
                MatReinforcementComponent
    width: float                                # Active width [mm]
    
    # For textiles with rovings
    @property
    def A_s(self) -> float:
        if hasattr(self.component, 'spacing'):
            # Textile: n_rovings × A_roving
            n_rovings = int(self.width / self.component.spacing)
            return n_rovings * self.component.A_roving
        else:
            # Mat/grid: area per unit width
            return self.width * self.component.area_per_width
    
    @property
    def material(self):
        return self.component.matmod
```

**Usage Example:**
```python
# Textile reinforcement
from bmcs_cross_section.cs_components import TextileReinforcementComponent

carbon_textile = TextileReinforcementComponent(
    product_id='CARB-TEX-001',
    spacing=14,      # mm between rovings
    A_roving=1.8     # mm² per roving
)

textile_layer = LayerReinforcement(
    z=25,
    component=carbon_textile,
    width=300  # Active width
)
# A_s = (300/14) × 1.8 = 38.6 mm² (automatic)
```

**Benefits:**
- ✓ Handles spacing-based textiles
- ✓ Handles area-per-width mats
- ✓ Product traceability
- ✓ Accurate for distributed reinforcement

### 3. AreaReinforcement

**Purpose:** Product-independent reinforcement for design optimization

**Key Attributes:**
```python
class AreaReinforcement(ReinforcementLayer):
    z: float                    # Position from top [mm]
    A_s: float                  # Required area [mm²]
    material: SteelReinforcement | CarbonReinforcement  # Material model
    
    # Optional: constraints for later component selection
    material_type: Optional[str] = None  # 'steel', 'carbon', etc.
    max_diameter: Optional[float] = None  # Geometric constraints
```

**Usage Example:**
```python
# Design-oriented (area determined by calculation/optimization)
from bmcs_cross_section.matmod import create_steel

area_layer = AreaReinforcement(
    z=450,
    A_s=1500,  # Required area from design equations
    material=create_steel('B500B')
)

# Later: select components to match required area
# Option 1: 5×D20 = 1571 mm²
# Option 2: 6×D18 = 1526 mm²
# Option 3: 4×D22 = 1521 mm²
```

**Benefits:**
- ✓ Supports design optimization
- ✓ No premature component selection
- ✓ Can generate component suggestions
- ✓ Flexible for automated design

## Class Hierarchy

```python
# bmcs_cross_section/cs_design/reinforcement.py

from typing import Optional, Union
from bmcs_cross_section.core import BMCSModel, ui_field
from bmcs_cross_section.cs_components import (
    SteelRebarComponent, CarbonBarComponent,
    TextileReinforcementComponent
)
from bmcs_cross_section.matmod import SteelReinforcement, CarbonReinforcement


class ReinforcementLayer(BMCSModel):
    """Base class for all reinforcement layer types."""
    
    z: float = ui_field(50.0, unit="mm", description="Distance from top")
    name: Optional[str] = None
    
    @property
    def A_s(self) -> float:
        """Total reinforcement area [mm²]"""
        raise NotImplementedError
    
    @property
    def material(self):
        """Material model"""
        raise NotImplementedError


class BarReinforcement(ReinforcementLayer):
    """Bar reinforcement from catalog."""
    
    component: Union[SteelRebarComponent, CarbonBarComponent]
    count: int = ui_field(1, ge=1, description="Number of bars")
    
    @property
    def A_s(self) -> float:
        return self.component.area * self.count
    
    @property
    def material(self):
        return self.component.matmod
    
    @property
    def diameter(self) -> float:
        """Bar diameter [mm]"""
        return self.component.nominal_diameter
    
    def generate_bom_entry(self) -> dict:
        """Generate bill of materials entry."""
        return {
            'type': 'bar',
            'product_id': self.component.product_id,
            'product_name': self.component.name,
            'manufacturer': self.component.manufacturer,
            'diameter': self.diameter,
            'count': self.count,
            'area_per_bar': self.component.area,
            'total_area': self.A_s,
            'position_z': self.z
        }


class LayerReinforcement(ReinforcementLayer):
    """Distributed reinforcement (textile/mat) from catalog."""
    
    component: TextileReinforcementComponent
    width: float = ui_field(100.0, ge=0, unit="mm", description="Active width")
    
    @property
    def A_s(self) -> float:
        if hasattr(self.component, 'spacing') and hasattr(self.component, 'A_roving'):
            # Textile with rovings
            n_rovings = int(self.width / self.component.spacing)
            return n_rovings * self.component.A_roving
        elif hasattr(self.component, 'area_per_width'):
            # Mat with area per unit width
            return self.width * self.component.area_per_width
        else:
            raise ValueError("Component must have either (spacing, A_roving) or area_per_width")
    
    @property
    def material(self):
        return self.component.matmod
    
    @property
    def n_rovings(self) -> int:
        """Number of rovings (for textiles)"""
        if hasattr(self.component, 'spacing'):
            return int(self.width / self.component.spacing)
        return 0
    
    def generate_bom_entry(self) -> dict:
        """Generate bill of materials entry."""
        entry = {
            'type': 'layer',
            'product_id': self.component.product_id,
            'product_name': self.component.name,
            'manufacturer': self.component.manufacturer,
            'width': self.width,
            'total_area': self.A_s,
            'position_z': self.z
        }
        
        if hasattr(self.component, 'spacing'):
            entry.update({
                'spacing': self.component.spacing,
                'A_roving': self.component.A_roving,
                'n_rovings': self.n_rovings
            })
        
        return entry


class AreaReinforcement(ReinforcementLayer):
    """Product-independent reinforcement for design optimization."""
    
    A_s: float = ui_field(1000.0, ge=0, unit="mm²", description="Steel area")
    material: Union[SteelReinforcement, CarbonReinforcement]
    
    # Optional constraints for component suggestion
    material_type: Optional[str] = None
    max_diameter: Optional[float] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    
    @property
    def A_s(self) -> float:
        return self._A_s
    
    def suggest_components(self, catalog) -> list[dict]:
        """
        Suggest catalog components that match required area.
        
        Returns list of feasible options sorted by proximity to required area.
        """
        options = []
        
        # Filter catalog by constraints
        if self.material_type:
            filtered = catalog[catalog['material_type'] == self.material_type]
        else:
            filtered = catalog
        
        if self.max_diameter:
            filtered = filtered[filtered['nominal_diameter'] <= self.max_diameter]
        
        # Find combinations
        for _, component in filtered.iterrows():
            area_per_bar = component['area']
            
            # Try different bar counts
            for count in range(self.min_count or 1, self.max_count or 20):
                total_area = count * area_per_bar
                error = abs(total_area - self.A_s) / self.A_s
                
                if error < 0.1:  # Within 10%
                    options.append({
                        'component': component,
                        'count': count,
                        'total_area': total_area,
                        'error': error
                    })
        
        return sorted(options, key=lambda x: x['error'])
```

## Integration with CrossSection

```python
# Usage in CrossSection class
class CrossSection(BMCSModel):
    shape: Union[RectangularShape, TShape, IShape]
    concrete: ConcreteMatMod
    reinforcement: List[Union[BarReinforcement, LayerReinforcement, AreaReinforcement]]
    
    def generate_bom(self, length_m: float = 1.0) -> dict:
        """Generate complete bill of materials."""
        bom = {
            'concrete': {
                'product_id': self.concrete.product_id if hasattr(self.concrete, 'product_id') else 'N/A',
                'volume_m3': self.shape.area * length_m * 1000 / 1e9
            },
            'reinforcement': []
        }
        
        for layer in self.reinforcement:
            if isinstance(layer, (BarReinforcement, LayerReinforcement)):
                bom['reinforcement'].append(layer.generate_bom_entry())
            elif isinstance(layer, AreaReinforcement):
                bom['reinforcement'].append({
                    'type': 'area',
                    'A_s': layer.A_s,
                    'material_type': layer.material_type or 'unspecified',
                    'position_z': layer.z,
                    'note': 'Product selection pending'
                })
        
        return bom
```

## Workflow Examples

### Workflow 1: Product-Based Analysis (M-κ curves)

```python
# Known components → calculate capacity
steel_d25 = SteelRebarComponent(nominal_diameter=25, grade='B500B')
carbon_d8 = CarbonBarComponent(nominal_diameter=8, grade='C1570')

cs = CrossSection(
    shape=RectangularShape(b=300, h=500),
    concrete=get_concrete_by_class('C35/45').matmod,
    reinforcement=[
        BarReinforcement(z=450, component=steel_d25, count=6),
        BarReinforcement(z=50, component=carbon_d8, count=4)
    ]
)

# Run moment-curvature analysis
mkappa = MomentCurvature(cross_section=cs)
M_u = mkappa.get_ultimate_moment()

# Generate BOM with full traceability
bom = cs.generate_bom(length_m=6.0)
```

### Workflow 2: Design-Oriented (Optimize reinforcement)

```python
# Required areas determined by design equations
A_s_required_bottom = 2500  # mm² from design calc
A_s_required_top = 800      # mm²

cs_design = CrossSection(
    shape=RectangularShape(b=300, h=500),
    concrete=get_concrete_by_class('C30/37').matmod,
    reinforcement=[
        AreaReinforcement(
            z=450,
            A_s=A_s_required_bottom,
            material=create_steel('B500B'),
            material_type='steel',
            max_diameter=25
        ),
        AreaReinforcement(
            z=50,
            A_s=A_s_required_top,
            material=create_steel('B500B'),
            material_type='steel',
            max_diameter=16
        )
    ]
)

# Verify design meets requirements
M_d = design_moment  # Required design moment
M_u = mkappa.get_ultimate_moment()
assert M_u >= M_d * 1.1  # 10% overstrength

# Now select components
catalog = create_steel_rebar_catalog()
for layer in cs_design.reinforcement:
    if isinstance(layer, AreaReinforcement):
        suggestions = layer.suggest_components(catalog)
        print(f"Options for layer at z={layer.z}:")
        for opt in suggestions[:3]:
            print(f"  {opt['count']}×D{opt['component']['nominal_diameter']} = {opt['total_area']:.0f} mm²")
```

### Workflow 3: Hybrid (Mix product-based and area-based)

```python
# Known product for bottom, optimized for top
steel_d20 = SteelRebarComponent(nominal_diameter=20, grade='B500B')

cs_hybrid = CrossSection(
    shape=TShape(b_f=800, h_f=150, b_w=300, h=600),
    concrete=get_concrete_by_class('C40/50').matmod,
    reinforcement=[
        BarReinforcement(z=550, component=steel_d20, count=8),  # Known: 8×D20
        AreaReinforcement(z=50, A_s=1200, material=create_steel('B500B'))  # TBD
    ]
)
```

## Implementation Plan

### Phase 1: Core Classes ✓
- [x] Define `BarReinforcement` class
- [x] Define `LayerReinforcement` class  
- [x] Define `AreaReinforcement` class
- [x] Implement `A_s` properties
- [x] Implement `material` properties

### Phase 2: BOM Generation
- [ ] Add `generate_bom_entry()` to each class
- [ ] Add `generate_bom()` to `CrossSection`
- [ ] Include product traceability
- [ ] Calculate quantities (length, weight)

### Phase 3: Component Suggestion
- [ ] Implement `suggest_components()` for `AreaReinforcement`
- [ ] Filter catalog by constraints
- [ ] Rank options by area match
- [ ] Consider geometric constraints (spacing, cover)

### Phase 4: Validation
- [ ] Add geometric validation (spacing, cover)
- [ ] Check minimum reinforcement ratios
- [ ] Verify component compatibility
- [ ] Validate against code requirements

### Phase 5: Migration
- [ ] Update notebook examples
- [ ] Create migration guide from old API
- [ ] Update documentation
- [ ] Deprecate old `ReinfLayer`, `BarLayer`, `FabricLayer`

## Benefits Summary

### Product Traceability
- ✓ Every bar/textile linked to catalog component
- ✓ Product ID, manufacturer preserved
- ✓ BOM generation straightforward
- ✓ Audit trail for design decisions

### Design Flexibility
- ✓ Supports analysis (known products)
- ✓ Supports synthesis (optimize areas)
- ✓ Mixed workflows possible
- ✓ Component suggestion for area-based

### Code Clarity
- ✓ Clear semantic distinction (bar vs layer vs area)
- ✓ Type safety (components validated)
- ✓ Automatic calculations
- ✓ Explicit coupling to catalog

### Integration
- ✓ Works with existing `matmod`
- ✓ Compatible with `mkappa` analysis
- ✓ Fits `CrossSection` architecture
- ✓ Ready for optimization frameworks

## Migration Notes

### Old API (cs_reinf_layer.py)
```python
# OLD: Manual area calculation
layer = ReinfLayer(z=450, A=1256, matmod='steel')
```

### New API
```python
# NEW: Product-based
steel = SteelRebarComponent(nominal_diameter=20, grade='B500B')
layer = BarReinforcement(z=450, component=steel, count=4)
# A_s calculated automatically: 4 × 314 = 1256 mm²

# Or area-based for design
layer = AreaReinforcement(z=450, A_s=1256, material=create_steel('B500B'))
```

Both approaches coexist, serving different workflows.
