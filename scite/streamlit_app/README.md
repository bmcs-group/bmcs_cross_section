# SCADT Streamlit Application
## Structural Concrete Analysis and Design Tool

Modular Streamlit interface with standalone testable components.

## Structure

```
streamlit_app/
├── __init__.py                  # Module exports
├── components_view.py           # Material catalog browser
├── cross_section_view.py        # Geometry & reinforcement definition
├── bending_analysis_view.py     # Moment-curvature analysis
├── summary_view.py              # Design summary & documentation
├── scadt_app.py                 # Main integrated application
├── rwth_cscp_bild_rgb.png       # Logo asset
└── README.md                    # This file
```

## Usage

### Standalone Testing

Each view module can be run independently for development and testing:

```bash
# Test Components view
streamlit run bmcs_cross_section/streamlit_app/components_view.py

# Test Cross-Section view
streamlit run bmcs_cross_section/streamlit_app/cross_section_view.py

# Test Bending Analysis view
streamlit run bmcs_cross_section/streamlit_app/bending_analysis_view.py

# Test Summary view
streamlit run bmcs_cross_section/streamlit_app/summary_view.py
```

### Integrated Application

Run the complete SCADT application with all workflow steps:

```bash
streamlit run bmcs_cross_section/streamlit_app/scadt_app.py
```

## Development Workflow

1. **Develop module independently**: Edit individual view files with standalone testing
2. **Test locally**: Run the specific module with `streamlit run`
3. **Integrate**: The main `scadt_app.py` imports and orchestrates all views
4. **Test integration**: Run complete app to verify workflow navigation

## Module Structure

Each view module follows this pattern:

```python
"""
Module docstring with description
"""

import streamlit as st
# ... other imports

def render_xxx_view():
    """Main render function for this view"""
    st.header("...")
    # ... view implementation

# Standalone testing
if __name__ == "__main__":
    st.set_page_config(...)
    render_xxx_view()
```

## Session State

Session state variables are managed in `scadt_app.py` and shared across all views:

- `workflow_step`: Current active workflow step
- `layers`: Reinforcement layer definitions
- `layer_counter`: Layer ID counter
- `concrete_selected`: Selected concrete grade
- `shape_params`: Cross-section geometry parameters
- `concrete_selected_idx`, `steel_selected_idx`, etc.: Catalog selection indices

## Styling

The main app (`scadt_app.py`) includes:
- Custom CSS for header bar with SCADT branding
- Sidebar menu styling (gradient for selected, hover effects)
- Consistent typography (1.3rem, 600 weight)
- Professional color scheme (blue gradient #1f77b4 → #1565c0)

## Components View Features

- ✅ Horizontal tabs for material types (Concrete, Steel, Carbon, Textile)
- ✅ Interactive table with row selection
- ✅ Parameter details panel (left side)
- ✅ Stress-strain curve visualization (right side)
- ✅ Fixed `spacing` → `grid_spacing` parameter name for textiles
- ✅ Default selection (C25/30 for concrete)

## TODO

- [ ] Implement Cross-Section view (geometry editor + reinforcement layer management)
- [ ] Implement Bending Analysis view (strain input + force calculation)
- [ ] Implement Summary view (complete design documentation)
- [ ] Add state persistence between views
- [ ] Export functionality (JSON/PDF)

## Dependencies

- `streamlit`: Web interface framework
- `matplotlib`: Plotting stress-strain curves
- `bmcs_cross_section.cs_components`: Component catalogs and classes
- `bmcs_cross_section.matmod`: Material models (concrete, steel, carbon)
- `bmcs_cross_section.cs_design`: Cross-section geometry and reinforcement classes
