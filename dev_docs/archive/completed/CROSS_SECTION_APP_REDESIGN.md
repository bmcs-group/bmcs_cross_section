# Cross-Section Design App - Interactive UI Patterns

## Overview
Redesigned the cross-section design app with **catalog-aware, composable architecture** enabling intuitive interactive composition of reinforced concrete cross-sections.

**Running at:** http://localhost:8501

## Key Architectural Patterns

### 1. Session State Management
**Pattern:** Persistent state across user interactions

```python
st.session_state.layers = []           # Dynamic layer list
st.session_state.layer_counter = 0     # Unique ID generator
st.session_state.concrete_selected = 'C30/37'  # Material selection
st.session_state.shape_params = {...}  # Geometry parameters
```

**Benefits:**
- State persists across reruns (button clicks, input changes)
- Enables dynamic add/delete operations
- Maintains user selections during session

### 2. Modal-like Dialogs (`@st.dialog`)
**Pattern:** Catalog browsers in popup-style overlays

```python
@st.dialog("🔍 Browse Steel Rebar Catalog", width="large")
def browse_steel_catalog():
    manager = get_catalog_manager_cached()
    catalog = manager.get_steel_catalog()
    st.dataframe(catalog[...], use_container_width=True)
```

**Benefits:**
- Non-blocking catalog inspection
- Keeps main UI clean
- Side-by-side comparison capability

**Note:** Streamlit dialogs are experimental but provide the best "popup" experience in a web browser (no true browser popups due to security).

### 3. Expander-Based Layer Management
**Pattern:** Collapsible sections for each reinforcement layer

```python
for layer_data in st.session_state.layers:
    with st.expander(f"**{layer_data['name']}** ({layer_data['type']})", expanded=True):
        # Layer-specific controls
        # Delete button
        # Computed values
```

**Benefits:**
- Clean UI with many layers
- Easy to focus on one layer
- Visual grouping of related controls

### 4. Conditional UI Based on Type
**Pattern:** Show different inputs based on reinforcement type

```python
if layer_data['type'] == 'Bar':
    # Bar-specific: diameter, count, catalog selection
elif layer_data['type'] == 'Layer':
    # Textile-specific: roving, width, material
else:  # Area
    # Design-specific: A_s, material model
```

**Benefits:**
- Type-safe inputs
- Catalog integration for Bar/Layer
- Manual parameters for Area (design mode)

### 5. Cached Catalog Manager
**Pattern:** Singleton catalog manager in session state

```python
@st.cache_data
def get_catalog_manager_cached():
    if 'catalog_manager' not in st.session_state:
        st.session_state.catalog_manager = get_catalog_manager()
    return st.session_state.catalog_manager
```

**Benefits:**
- Catalogs loaded once per session
- Fast access (memory + disk cache)
- No repeated file I/O

### 6. Builder Pattern for Complex Objects
**Pattern:** Construct cross-section from session state

```python
def build_reinforcement_from_layers():
    layers = []
    for layer_data in st.session_state.layers:
        if layer_data['type'] == 'Bar':
            component = SteelRebarComponent(...)
            layer = BarReinforcement(z=..., component=component, count=...)
        # ... similar for other types
    return ReinforcementLayout(layers=layers)
```

**Benefits:**
- Separation of UI state and domain objects
- Error handling per layer
- Incremental construction

## User Workflows

### Workflow 1: Product-Based Analysis (Known Components)
**Scenario:** Analyze existing structure

1. **Select Concrete** from catalog (dropdown)
   - Shows: f_ck, f_cm, E_cm
   
2. **Add Bar Reinforcement** layers
   - Click "➕ Bar" in sidebar
   - Select material: steel/carbon
   - Choose diameter from catalog
   - Set count
   - Auto-computes: A_s = area × count
   
3. **Visualize** in live preview
   - Cross-section with bars positioned
   - Shows total A_s, reinforcement ratio
   
4. **Analyze** strain distributions
   - Set curvature κ and top strain ε_top
   - Compute N, M
   - Plot strain/stress distributions

**Full traceability:** Component → Product ID → Material model

### Workflow 2: Design-Oriented (Unknown Reinforcement)
**Scenario:** Design new member, optimize reinforcement

1. **Select Concrete** from catalog
   
2. **Add Area Reinforcement** layers
   - Click "➕ Area" in sidebar
   - Enter required A_s (from design equations)
   - Select material type (steel/carbon)
   - Choose grade
   
3. **Analyze** with design values
   - Moment-curvature analysis
   - Check capacity
   
4. **Product Selection** (Phase 3 - future)
   - Optimize bar configuration
   - Match A_s from catalog
   - Convert to BarReinforcement

**Product-independent until optimization complete**

### Workflow 3: Hybrid Reinforcement
**Scenario:** TRC with steel + textile

1. **Add steel bars** (bottom, tension)
   - BarReinforcement with steel catalog
   
2. **Add textile layer** (top, distributed)
   - LayerReinforcement with textile specs
   - Set width, material, roving
   
3. **Mix product-based and design**
   - Known products: Bar/Layer
   - Optimized: Area
   
4. **Visualize hybrid** cross-section
   - Different layer types shown distinctly
   - Total reinforcement computed

## UI Components Explained

### Sidebar - Quick Actions
**Purpose:** Primary controls always visible

- **Add Layer Buttons:** ➕ Bar, ➕ Layer, ➕ Area
  - Instant layer creation with defaults
  - Reruns app to show new layer
  
- **Browse Catalogs:** 🔍 buttons
  - Opens modal dialogs
  - Inspect without cluttering main UI
  
- **Clear All:** 🗑️
  - Reset to clean slate
  - Confirmation implicit (immediate)
  
- **Stats:** Active Layers counter
  - Quick status overview

### Tab 1: Geometry
**Purpose:** Shape definition

- Shape type selection (Rectangular/T/I)
- Dimension inputs (conditional based on type)
- Live geometry preview
- Geometric properties display

### Tab 2: Reinforcement (Main Tab)
**Purpose:** Material selection + layer composition

**Materials Section:**
- Concrete: Dropdown from catalog
- Steel grade: Default for Area reinforcement

**Layers Section:**
- **Each layer in expander:**
  - Name (editable)
  - Position z (from bottom)
  - Delete button (🗑️)
  
- **Type-specific controls:**
  - **Bar:** material, diameter (from catalog), count
  - **Layer:** material, roving, width
  - **Area:** A_s, material type, grade
  
- **Computed values shown:**
  - Total area per layer
  - Product IDs (for Bar/Layer)
  - Guidance text

**Live Preview:**
- Full cross-section with all layers
- Metrics: layers, total A_s, ratio ρ

### Tab 3: Analysis
**Purpose:** Strain/stress distributions

- Input: κ (curvature), ε_top
- Compute: N (axial force), M (moment)
- Plot: Strain and stress distributions side-by-side

### Tab 4: Summary
**Purpose:** Complete documentation

- Geometry properties
- Concrete specifications
- Reinforcement summary
- Layer detail table (all layers with z, A_s)

## Technical Implementation

### Layer Data Structure
```python
layer = {
    'id': unique_int,           # For deletion
    'type': 'Bar'|'Layer'|'Area',  # Determines UI
    'z': float,                 # Position
    'name': str,                # User-editable
    # Type-specific fields:
    'material': 'steel'|'carbon',  # For Bar
    'diameter': int,            # For Bar
    'grade': str,               # For Bar/Area
    'count': int,               # For Bar
    'roving_tex': int,          # For Layer
    'width': float,             # For Layer
    'A_s': float,               # For Area
    'material_type': str,       # For Area
}
```

### Component Creation
**Bar Reinforcement:**
```python
if layer_data['material'] == 'steel':
    component = SteelRebarComponent(
        nominal_diameter=layer_data['diameter'],
        grade=layer_data['grade']
    )
else:  # carbon
    component = CarbonBarComponent(
        nominal_diameter=layer_data['diameter']
    )

layer = BarReinforcement(
    z=layer_data['z'],
    component=component,
    count=layer_data['count'],
    name=layer_data['name']
)
```

**Layer Reinforcement:**
```python
component = TextileReinforcementComponent(
    product_id=f"TEXTILE-{layer_data['roving_tex']}",
    material_type=layer_data['material'],
    roving_tex=layer_data['roving_tex'],
    # ... other textile properties
)

layer = LayerReinforcement(
    z=layer_data['z'],
    component=component,
    width=layer_data['width'],
    name=layer_data['name']
)
```

**Area Reinforcement:**
```python
if layer_data['material_type'] == 'steel':
    material = create_steel(layer_data['grade'])
else:  # carbon
    material = create_carbon('C2000')

layer = AreaReinforcement(
    z=layer_data['z'],
    A_s=layer_data['A_s'],
    material=material,
    name=layer_data['name']
)
```

## Answer to User Questions

### Q1: Material selection from catalog?
**✓ Solved:** Dropdown populated from catalog with `get_catalog_manager()`
- Concrete: All strength classes available
- Shows properties: f_ck, f_cm, E_cm
- Selected material used throughout analysis

### Q2: Adding reinforcement entities dynamically?
**✓ Solved:** Sidebar buttons + session state
- ➕ Bar, ➕ Layer, ➕ Area buttons
- Each click adds layer to `st.session_state.layers`
- Layers displayed in expanders (collapsible)
- Delete button per layer

### Q3: Product selection for Bar/Layer?
**✓ Solved:** Catalog-aware dropdowns
- **Bar:** Diameter from steel/carbon catalog
- **Layer:** Roving from textile options
- Shows product ID after selection
- Component created from catalog data

### Q4: Material model editing for Area?
**✓ Solved:** Type selection + parameters
- Select material type (steel/carbon)
- Choose grade (for steel)
- Material model created automatically
- **Future:** Expander with editable parameters (E_s, f_sy, etc.)

### Q5: Dialog/popup windows?
**✓ Addressed:** `@st.dialog` (experimental)
- Catalog browsers open in overlay
- Not true popups (browser security)
- Best available solution in Streamlit
- Alternative: Expanders or modal-like columns

## Future Enhancements

### Phase 3 Integration
- [ ] Connect to mkappa solver
- [ ] Moment-curvature diagrams
- [ ] Ultimate capacity calculations
- [ ] Automated reinforcement optimization

### Advanced Material Editing
- [ ] Expander for Area reinforcement material params
- [ ] Custom material models
- [ ] Material library management

### Product Optimization
- [ ] Convert Area → Bar (find best bar configuration)
- [ ] Genetic algorithm for bar placement
- [ ] Cost optimization

### Export/Import
- [ ] Save cross-section to JSON
- [ ] Load predefined cross-sections
- [ ] Share designs via file

### Visualization
- [ ] 3D cross-section rendering
- [ ] Animation of strain distributions
- [ ] Interactive neutral axis adjustment

## Conclusion

The redesigned app provides a **professional, catalog-aware UI** for cross-section design with:

- ✓ Intuitive layer management (add/delete dynamically)
- ✓ Full catalog integration (concrete, steel, carbon, textiles)
- ✓ Three reinforcement types (Bar, Layer, Area)
- ✓ Live preview with automatic updates
- ✓ Modal-like catalog browsers
- ✓ Product traceability (ID → component → material model)
- ✓ Analysis-ready cross-sections

The architecture supports the full design workflow from initial concept (Area reinforcement) through product selection (Bar/Layer from catalogs) to final analysis.

**Ready for Phase 3:** mkappa integration and automated design optimization.

---
**Date:** January 10, 2026  
**App URL:** http://localhost:8501  
**Status:** ✅ Fully functional and tested
