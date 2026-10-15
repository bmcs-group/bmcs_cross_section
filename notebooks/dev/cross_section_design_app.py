"""
Interactive Cross-Section Design Application
============================================

Streamlit app for designing reinforced concrete cross-sections with:
- Material selection from component catalogs
- Dynamic reinforcement layer management  
- Bar, Layer, and Area reinforcement types
- Live cross-section visualization

Run with: streamlit run cross_section_design_app.py
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from bmcs_cross_section.cs_design import (
    RectangularShape, TShape, IShape,
    BarReinforcement, LayerReinforcement, AreaReinforcement,
    ReinforcementLayout, CrossSection
)

from bmcs_cross_section.cs_components import (
    get_catalog_manager,
    get_concrete_by_class,
    SteelRebarComponent,
    CarbonBarComponent,
    TextileReinforcementComponent,
    ConcreteComponent
)

from bmcs_cross_section.matmod import create_steel, create_carbon

# ========================================
# INITIALIZATION & SESSION STATE
# ========================================

def initialize_session_state():
    """Initialize session state variables"""
    if 'layers' not in st.session_state:
        st.session_state.layers = []
    if 'layer_counter' not in st.session_state:
        st.session_state.layer_counter = 0
    if 'concrete_selected' not in st.session_state:
        st.session_state.concrete_selected = 'C30/37'
    if 'shape_params' not in st.session_state:
        st.session_state.shape_params = {
            'type': 'Rectangular',
            'b': 300.0,
            'h': 500.0
        }
    if 'workflow_step' not in st.session_state:
        st.session_state.workflow_step = 'Cross-Section'

def add_layer(layer_type):
    """Add a new reinforcement layer"""
    st.session_state.layer_counter += 1
    layer_id = st.session_state.layer_counter
    
    # Default position based on existing layers
    if len(st.session_state.layers) == 0:
        default_z = 450.0  # Bottom layer
    elif len(st.session_state.layers) == 1:
        default_z = 50.0   # Top layer
    else:
        default_z = 250.0  # Middle
    
    new_layer = {
        'id': layer_id,
        'type': layer_type,
        'z': default_z,
        'name': f'Layer {layer_id}',
    }
    
    # Type-specific defaults
    if layer_type == 'Bar':
        new_layer.update({
            'material': 'steel',
            'diameter': 20,
            'grade': 'B500B',
            'count': 4
        })
    elif layer_type == 'Layer':
        new_layer.update({
            'material': 'carbon',
            'roving_tex': 800,
            'width': 300
        })
    else:  # Area
        new_layer.update({
            'A_s': 1000.0,
            'material_type': 'steel',
            'grade': 'B500B'
        })
    
    st.session_state.layers.append(new_layer)

def delete_layer(layer_id):
    """Remove a layer by ID"""
    st.session_state.layers = [l for l in st.session_state.layers if l['id'] != layer_id]

def get_catalog_manager_cached():
    """Get cached catalog manager"""
    if 'catalog_manager' not in st.session_state:
        st.session_state.catalog_manager = get_catalog_manager()
    return st.session_state.catalog_manager

# ========================================
# CATALOG BROWSERS (Modal-like dialogs)
# ========================================

@st.dialog("🔍 Browse Steel Rebar Catalog", width="large")
def browse_steel_catalog():
    """Modal dialog for browsing steel catalog"""
    manager = get_catalog_manager_cached()
    catalog = manager.get_steel_catalog()
    
    st.markdown("### Available Steel Rebars")
    
    # Group by grade
    grades = catalog['name'].apply(lambda x: x.split()[0] if 'B500' in x else 'Other').unique()
    
    selected_grade = st.selectbox("Filter by grade:", ['All'] + list(grades))
    
    if selected_grade != 'All':
        catalog = catalog[catalog['name'].str.contains(selected_grade)]
    
    # Display table
    display_cols = ['nominal_diameter', 'area', 'f_tk', 'f_td', 'product_id']
    st.dataframe(catalog[display_cols], use_container_width=True)
    
    st.info(f"📊 {len(catalog)} products available")

@st.dialog("🔍 Browse Carbon Bar Catalog", width="large")
def browse_carbon_catalog():
    """Modal dialog for browsing carbon catalog"""
    manager = get_catalog_manager_cached()
    catalog = manager.get_carbon_catalog()
    
    st.markdown("### Available Carbon Bars (COMBAR)")
    
    display_cols = ['nominal_diameter', 'area', 'f_tk', 'f_td', 'E', 'product_id']
    st.dataframe(catalog[display_cols], use_container_width=True)
    
    st.info(f"📊 {len(catalog)} products available")

@st.dialog("🔍 Browse Concrete Catalog", width="large")
def browse_concrete_catalog():
    """Modal dialog for browsing concrete catalog"""
    manager = get_catalog_manager_cached()
    catalog = manager.get_concrete_catalog()
    
    st.markdown("### Available Concrete Grades")
    
    display_cols = ['strength_class', 'f_ck', 'f_cm', 'f_cd', 'E_cm']
    st.dataframe(catalog[display_cols], use_container_width=True)
    
    st.info(f"📊 {len(catalog)} grades available")

# ========================================
# SHAPE BUILDER
# ========================================

def build_shape():
    """Build cross-section shape from session state"""
    params = st.session_state.shape_params
    
    if params['type'] == 'Rectangular':
        return RectangularShape(b=params['b'], h=params['h'])
    elif params['type'] == 'T-Section':
        return TShape(
            b_f=params['b_f'], 
            h_f=params['h_f'],
            b_w=params['b_w'], 
            h=params['h']
        )
    else:  # I-Section
        return IShape(
            b_f=params['b_f'],
            h_f=params['h_f'],
            b_w=params['b_w'],
            h_w=params['h_w']
        )

# ========================================
# REINFORCEMENT BUILDER
# ========================================

def build_reinforcement_from_layers():
    """Build ReinforcementLayout from session state layers"""
    layers = []
    
    for layer_data in st.session_state.layers:
        try:
            if layer_data['type'] == 'Bar':
                # Create component
                if layer_data['material'] == 'steel':
                    component = SteelRebarComponent(
                        nominal_diameter=layer_data['diameter'],
                        grade=layer_data['grade']
                    )
                else:  # carbon
                    component = CarbonBarComponent(
                        nominal_diameter=layer_data['diameter']
                    )
                
                # Create layer
                layer = BarReinforcement(
                    z=layer_data['z'],
                    component=component,
                    count=layer_data['count'],
                    name=layer_data['name']
                )
                layers.append(layer)
                
            elif layer_data['type'] == 'Layer':
                # Create textile component
                component = TextileReinforcementComponent(
                    product_id=f"TEXTILE-{layer_data['roving_tex']}",
                    name=f"Textile {layer_data['roving_tex']}tex",
                    material_type=layer_data['material'],
                    roving_tex=layer_data['roving_tex'],
                    spacing=14.0,  # Default
                    A_roving=layer_data['roving_tex'] / 1670.0,  # Typical conversion
                    f_tk=2500 if layer_data['material'] == 'carbon' else 1800,
                    E=165000 if layer_data['material'] == 'carbon' else 72000
                )
                
                layer = LayerReinforcement(
                    z=layer_data['z'],
                    component=component,
                    width=layer_data['width'],
                    name=layer_data['name']
                )
                layers.append(layer)
                
            else:  # Area
                # Create material
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
                layers.append(layer)
                
        except Exception as e:
            st.error(f"Error creating layer '{layer_data['name']}': {str(e)}")
            continue
    
    return ReinforcementLayout(layers=layers)

# ========================================
# MAIN APP
# ========================================

def main():
    # Page config
    st.set_page_config(
        page_title="SCADT - Cross-Section Design",
        page_icon="📐",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_session_state()
    
    # Custom CSS to style Streamlit's native header bar
    st.markdown("""
    <style>
        /* Style the main header area */
        header[data-testid="stHeader"] {
            background: linear-gradient(135deg, #1f77b4 0%, #1565c0 100%);
            padding: 0.5rem 1rem;
        }
        
        /* Hide default Streamlit branding if present */
        header[data-testid="stHeader"] > div:first-child {
            display: flex;
            align-items: center;
            width: 100%;
        }
        
        /* Inject title into header */
        header[data-testid="stHeader"]::before {
            content: "SCADT — Structural Concrete Analysis and Design Tool";
            color: white;
            font-size: 1.5rem;
            font-weight: 600;
            font-family: 'Arial', sans-serif;
            margin-right: auto;
            white-space: nowrap;
            flex-grow: 1;
        }
        
        /* Ensure menu icon stays visible and white */
        button[kind="header"] {
            color: white !important;
        }
        
        /* Style the toolbar buttons */
        header[data-testid="stHeader"] button {
            color: white !important;
        }
        
        /* Make sidebar collapse button visible against blue background */
        button[data-testid="collapsedControl"] {
            background-color: white !important;
            color: #1f77b4 !important;
            border: 2px solid white !important;
            z-index: 999999 !important;
            display: block !important;
            visibility: visible !important;
        }
        
        button[data-testid="collapsedControl"]:hover {
            background-color: #e9ecef !important;
        }
        
        /* Force sidebar to be visible */
        section[data-testid="stSidebar"] {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Remove ALL padding from sidebar */
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 0 !important;
        }
        
        /* Remove padding from sidebar block container */
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            padding-top: 0 !important;
            gap: 0 !important;
        }
        
        /* Force logo container to top with negative margin */
        section[data-testid="stSidebar"] [data-testid="stImage"]:first-of-type {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            margin: -1rem -1rem 0 -1rem !important;
            padding: 0.25rem 0.5rem !important;
            height: 3.5rem !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-bottom: 2px solid #1f77b4 !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Logo sizing - fixed height, auto width */
        section[data-testid="stSidebar"] [data-testid="stImage"]:first-of-type img {
            height: 3rem !important;
            width: auto !important;
            max-width: 100% !important;
            object-fit: contain !important;
        }
        
        /* Style menu buttons - match the selected div exactly */
        section[data-testid="stSidebar"] button {
            margin: 0.25rem 0 !important;
            padding: 0.75rem 1rem !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
            font-size: 1.3rem !important;
            font-weight: 600 !important;
            border: none !important;
            border-radius: 0 !important;
            background: transparent !important;
            color: #333 !important;
            transition: background 0.2s ease, color 0.2s ease !important;
            text-align: center !important;
            line-height: 1.5 !important;
        }
        
        section[data-testid="stSidebar"] button:hover {
            background: #e9ecef !important;
            border-radius: 0 !important;
        }
        
        section[data-testid="stSidebar"] button:active {
            background: #dee2e6 !important;
            border-radius: 0 !important;
        }
        
        /* Position logo at absolute bottom of sidebar */
        section[data-testid="stSidebar"] [data-testid="stImage"]:last-of-type {
            position: fixed !important;
            bottom: 1rem !important;
            left: 1rem !important;
            right: 1rem !important;
            width: calc(100% - 2rem) !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ========================================
    # SIDEBAR - Workflow Navigation
    # ========================================
    
    with st.sidebar:
        # Workflow menu using buttons with matching font styling
        menu_items = ["Components", "Cross-Section", "Bending Analysis", "Summary"]
        
        for item in menu_items:
            is_selected = st.session_state.workflow_step == item
            
            if is_selected:
                # Selected state - gradient background
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1f77b4 0%, #1565c0 100%);
                            color: white;
                            padding: 0.75rem 1rem;
                            margin: 0.25rem 0;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                            font-size: 1.3rem;
                            font-weight: 600;
                            line-height: 1.5;
                            box-shadow: 0 2px 8px rgba(31, 119, 180, 0.3);
                            cursor: default;
                            text-align: center;
                            border-radius: 0;">
                    {item}
                </div>
                """, unsafe_allow_html=True)
            else:
                # Unselected state - clickable button
                if st.button(item, key=f"menu_{item}", use_container_width=True):
                    st.session_state.workflow_step = item
                    st.rerun()
                    st.rerun()
        
        workflow_step = st.session_state.workflow_step
        
        # Push logo to bottom with spacer
        st.markdown("<div style='flex-grow: 1;'></div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Load and display logo at the bottom
        logo_path = Path("rwth_cscp_bild_rgb.png")
        if logo_path.exists():
            st.image(str(logo_path), width="stretch")
    
    # ========================================
    # MAIN CONTENT - Workflow-based
    # ========================================
    
    # Parse workflow step
    step_map = {
        "Components": "components",
        "Cross-Section": "cross_section",
        "Bending Analysis": "analysis",
        "Summary": "summary"
    }
    current_step = step_map[workflow_step]
    
    # ========================================
    # STEP 1: COMPONENTS (Catalog Browsers)
    # ========================================
    
    if current_step == "components":
        st.header("Component Catalogs")
        st.markdown("""
        Browse available materials and products. View specifications, properties, and stress-strain curves.
        """)
        
        # Horizontal tabs for each component type
        tab_concrete, tab_steel, tab_carbon, tab_textile = st.tabs([
            "Concrete", "Steel Rebars", "Carbon Bars", "Textile Products"
        ])
        
        # Get catalog manager
        manager = get_catalog_manager_cached()
        
        # ========== CONCRETE TAB ==========
        with tab_concrete:
            catalog = manager.get_concrete_catalog()
            
            # Format display columns
            display_cols = ['product_id', 'strength_class', 'f_ck', 'f_cm', 'f_cd', 'E_cm']
            display_df = catalog[display_cols].copy()
            
            # Find C25/30 as default
            default_idx = 0
            if 'strength_class' in catalog.columns:
                c25_matches = catalog[catalog['strength_class'] == 'C25/30']
                if not c25_matches.empty:
                    default_idx = catalog.index.get_loc(c25_matches.index[0])
            
            # Table with selection
            if 'concrete_selected_idx' not in st.session_state:
                st.session_state.concrete_selected_idx = default_idx
            
            event = st.dataframe(
                display_df,
                height=200,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True
            )
            
            # Update selection
            if event.selection.rows:
                st.session_state.concrete_selected_idx = event.selection.rows[0]
            
            selected_idx = min(st.session_state.concrete_selected_idx, len(catalog) - 1)
            selected_row = catalog.iloc[selected_idx]
            
            # Create component
            from bmcs_cross_section.matmod.ec2_concrete import EC2Concrete
            concrete_matmod = EC2Concrete(f_cm=float(selected_row['f_cm']))
            component = ConcreteComponent(
                product_id=selected_row['product_id'],
                name=selected_row.get('name', selected_row['strength_class']),
                strength_class=selected_row['strength_class'],
                f_ck=selected_row['f_ck'],
                f_cm=selected_row['f_cm'],
                E_cm=selected_row['E_cm'],
                matmod=concrete_matmod,
            )
            
            # Two columns: parameters (left) and plot (right)
            col_params, col_plot = st.columns([1.2, 1])
            
            with col_params:
                st.markdown("#### Component Details")
                st.markdown(f"**{component.name}** ({component.product_id})")
                
                st.markdown("**Strength Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("f_ck", f"{component.f_ck} MPa", help="Characteristic strength")
                    st.metric("f_cm", f"{component.f_cm} MPa", help="Mean strength")
                with col2:
                    st.metric("f_cd", f"{component.f_cd:.1f} MPa", help="Design strength")
                    st.metric("γ_c", f"{component.gamma_c:.2f}", help="Safety factor")
                
                st.markdown("**Deformation Properties**")
                st.metric("E_cm", f"{component.E_cm} MPa", help="Elastic modulus")
            
            with col_plot:
                st.markdown("#### Stress-Strain Curve")
                fig, ax = plt.subplots(figsize=(6, 4.5))
                component.plot_stress_strain(ax=ax, show_limits=True, color='blue', alpha_fill=0.2)
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                plt.close()
        
        # ========== STEEL REBARS TAB ==========
        with tab_steel:
            catalog = manager.get_steel_catalog()
            
            # Format display columns
            display_cols = ['product_id', 'name', 'nominal_diameter', 'area', 'f_tk', 'f_td', 'E']
            display_df = catalog[display_cols].copy()
            
            # Table with selection
            if 'steel_selected_idx' not in st.session_state:
                st.session_state.steel_selected_idx = 0
            
            event = st.dataframe(
                display_df,
                height=200,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True
            )
            
            if event.selection.rows:
                st.session_state.steel_selected_idx = event.selection.rows[0]
            
            selected_idx = min(st.session_state.steel_selected_idx, len(catalog) - 1)
            selected_row = catalog.iloc[selected_idx]
            
            # Extract grade
            if 'B500A' in selected_row['name']:
                grade = 'B500A'
            elif 'B500B' in selected_row['name']:
                grade = 'B500B'
            elif 'B500C' in selected_row['name']:
                grade = 'B500C'
            else:
                grade = 'B500B'
            
            component = SteelRebarComponent(
                nominal_diameter=selected_row['nominal_diameter'],
                grade=grade
            )
            
            # Two columns: parameters (left) and plot (right)
            col_params, col_plot = st.columns([1.2, 1])
            
            with col_params:
                st.markdown("#### Component Details")
                st.markdown(f"**{component.name}** ({component.product_id})")
                
                st.markdown("**Geometric Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Diameter", f"{component.nominal_diameter} mm")
                with col2:
                    st.metric("Area", f"{component.area:.2f} mm²")
                
                st.markdown("**Characteristic Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("f_tk", f"{component.f_tk:.0f} MPa", help="Tensile strength")
                    st.metric("E", f"{component.E:.0f} MPa", help="Elastic modulus")
                with col2:
                    st.metric("ε_uk", f"{component.eps_uk:.4f}", help="Ultimate strain")
                    st.metric("γ_s", f"{component.gamma_s:.2f}", help="Safety factor")
                
                st.markdown("**Design Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("f_td", f"{component.f_td:.1f} MPa", help="Design strength")
                with col2:
                    st.metric("ε_ud", f"{component.eps_ud:.4f}", help="Design strain")
            
            with col_plot:
                st.markdown("#### Stress-Strain Curve")
                fig, ax = plt.subplots(figsize=(6, 4.5))
                component.plot_stress_strain(ax=ax, show_limits=True, color='darkred', alpha_fill=0.2)
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                plt.close()
        
        # ========== CARBON BARS TAB ==========
        with tab_carbon:
            catalog = manager.get_carbon_catalog()
            
            # Format display columns
            display_cols = ['product_id', 'name', 'nominal_diameter', 'area', 'f_tk', 'f_td', 'E']
            display_df = catalog[display_cols].copy()
            
            # Table with selection
            if 'carbon_selected_idx' not in st.session_state:
                st.session_state.carbon_selected_idx = 0
            
            event = st.dataframe(
                display_df,
                height=200,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True
            )
            
            if event.selection.rows:
                st.session_state.carbon_selected_idx = event.selection.rows[0]
            
            selected_idx = min(st.session_state.carbon_selected_idx, len(catalog) - 1)
            selected_row = catalog.iloc[selected_idx]
            
            component = CarbonBarComponent(
                nominal_diameter=selected_row['nominal_diameter']
            )
            
            # Two columns: parameters (left) and plot (right)
            col_params, col_plot = st.columns([1.2, 1])
            
            with col_params:
                st.markdown("#### Component Details")
                st.markdown(f"**{component.name}** ({component.product_id})")
                
                st.markdown("**Geometric Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Diameter", f"{component.nominal_diameter} mm")
                with col2:
                    st.metric("Area", f"{component.area:.2f} mm²")
                
                st.markdown("**Characteristic Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("f_tk", f"{component.f_tk:.0f} MPa", help="Tensile strength")
                    st.metric("E", f"{component.E:.0f} MPa", help="Elastic modulus")
                with col2:
                    st.metric("ε_uk", f"{component.eps_uk:.4f}", help="Ultimate strain")
                    st.metric("γ_s", f"{component.gamma_s:.2f}", help="Safety factor")
                
                st.markdown("**Design Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("f_td", f"{component.f_td:.1f} MPa", help="Design strength")
                with col2:
                    st.metric("ε_ud", f"{component.eps_ud:.4f}", help="Design strain")
            
            with col_plot:
                st.markdown("#### Stress-Strain Curve")
                fig, ax = plt.subplots(figsize=(6, 4.5))
                component.plot_stress_strain(ax=ax, show_limits=True, color='darkred', alpha_fill=0.2)
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                plt.close()
        
        # ========== TEXTILE PRODUCTS TAB ==========
        with tab_textile:
            catalog = manager.get_textile_catalog()
            
            # Format display columns
            display_cols = ['product_id', 'name', 'material_type', 'area_per_width', 'grid_spacing', 'f_tk', 'E']
            display_df = catalog[display_cols].copy()
            
            # Table with selection
            if 'textile_selected_idx' not in st.session_state:
                st.session_state.textile_selected_idx = 0
            
            event = st.dataframe(
                display_df,
                height=200,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True
            )
            
            if event.selection.rows:
                st.session_state.textile_selected_idx = event.selection.rows[0]
            
            selected_idx = min(st.session_state.textile_selected_idx, len(catalog) - 1)
            selected_row = catalog.iloc[selected_idx]
            
            component = TextileReinforcementComponent(
                product_id=selected_row['product_id'],
                name=selected_row['name'],
                material_type=selected_row['material_type'],
                roving_tex=selected_row['roving_tex'],
                spacing=selected_row['grid_spacing'],
                A_roving=selected_row.get('A_roving', selected_row['roving_tex'] / 1670.0),
                f_tk=selected_row['f_tk'],
                E=selected_row['E']
            )
            
            # Two columns: parameters (left) and plot (right)
            col_params, col_plot = st.columns([1.2, 1])
            
            with col_params:
                st.markdown("#### Component Details")
                st.markdown(f"**{component.name}** ({component.product_id})")
                
                st.markdown("**Geometric Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Area/Width", f"{component.area_per_width:.1f} mm²/m")
                with col2:
                    st.metric("Grid Spacing", f"{component.grid_spacing} mm")
                
                st.markdown("**Characteristic Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("f_tk", f"{component.f_tk:.0f} MPa", help="Tensile strength")
                    st.metric("E", f"{component.E:.0f} MPa", help="Elastic modulus")
                with col2:
                    st.metric("ε_uk", f"{component.eps_uk:.4f}", help="Ultimate strain")
                    st.metric("γ_s", f"{component.gamma_s:.2f}", help="Safety factor")
                
                st.markdown("**Design Properties**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("f_td", f"{component.f_td:.1f} MPa", help="Design strength")
                with col2:
                    st.metric("ε_ud", f"{component.eps_ud:.4f}", help="Design strain")
            
            with col_plot:
                st.markdown("#### Stress-Strain Curve")
                fig, ax = plt.subplots(figsize=(6, 4.5))
                component.plot_stress_strain(ax=ax, show_limits=True, color='darkred', alpha_fill=0.2)
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                plt.close()
    
    # ========================================
    # STEP 2: CROSS-SECTION (Geometry + Reinforcement)
    # ========================================
    
    elif current_step == "cross_section":
        st.header("2️⃣ Cross-Section Definition")
        
        # Sub-tabs for Geometry and Reinforcement
        subtab1, subtab2 = st.tabs(["Geometry", "Reinforcement Layout"])
        
        # --- GEOMETRY SUBTAB ---
        with subtab1:
            st.subheader("Geometry Definition")
            
            col1, col2 = st.columns([1, 1])
        
        with col1:
            shape_type = st.selectbox(
                "Shape Type",
                ["Rectangular", "T-Section", "I-Section"],
                key='shape_type_select'
            )
            st.session_state.shape_params['type'] = shape_type
            
            st.markdown("---")
            
            if shape_type == "Rectangular":
                st.session_state.shape_params['b'] = st.number_input(
                    "Width b [mm]", 100.0, 2000.0, 
                    st.session_state.shape_params.get('b', 300.0), 10.0
                )
                st.session_state.shape_params['h'] = st.number_input(
                    "Height h [mm]", 100.0, 3000.0,
                    st.session_state.shape_params.get('h', 500.0), 10.0
                )
                
            elif shape_type == "T-Section":
                st.session_state.shape_params['b_f'] = st.number_input(
                    "Flange width b_f [mm]", 100.0, 3000.0, 600.0, 10.0
                )
                st.session_state.shape_params['h_f'] = st.number_input(
                    "Flange height h_f [mm]", 50.0, 500.0, 150.0, 10.0
                )
                st.session_state.shape_params['b_w'] = st.number_input(
                    "Web width b_w [mm]", 100.0, 1000.0, 200.0, 10.0
                )
                st.session_state.shape_params['h'] = st.number_input(
                    "Total height h [mm]", 200.0, 2000.0, 600.0, 10.0
                )
            
            else:  # I-Section
                st.session_state.shape_params['b_f'] = st.number_input(
                    "Flange width b_f [mm]", 100.0, 2000.0, 400.0, 10.0
                )
                st.session_state.shape_params['h_f'] = st.number_input(
                    "Flange height h_f [mm]", 50.0, 300.0, 100.0, 10.0
                )
                st.session_state.shape_params['b_w'] = st.number_input(
                    "Web width b_w [mm]", 50.0, 800.0, 150.0, 10.0
                )
                st.session_state.shape_params['h_w'] = st.number_input(
                    "Web height h_w [mm]", 100.0, 1500.0, 300.0, 10.0
                )
            
            # Build and show properties
            shape = build_shape()
            h_total = shape.h if shape_type == "Rectangular" else shape.h_total
            
            st.success(f"""
            **Geometric Properties:**
            - Total height: {h_total:.0f} mm
            - Area: {shape.area:,.0f} mm²
            - Centroid: {shape.centroid_y:.1f} mm
            - I_y: {shape.I_y:.2e} mm⁴
            """)
        
        with col2:
            st.markdown("### Visualization")
            fig, ax = plt.subplots(figsize=(6, 8))
            
            # Get concrete for plotting
            concrete = get_concrete_by_class(st.session_state.concrete_selected)
            empty_reinf = ReinforcementLayout()
            cs = CrossSection(shape=shape, concrete=concrete.matmod, reinforcement=empty_reinf)
            cs.plot_cross_section(ax=ax, show_dimensions=True, show_reinforcement=False)
            
            st.pyplot(fig)
            plt.close()
        
        # --- REINFORCEMENT LAYOUT SUBTAB ---
        with subtab2:
            st.subheader("Materials & Reinforcement")
        
        # ===== MATERIALS SECTION =====
        st.subheader("Materials")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Concrete:**")
            manager = get_catalog_manager_cached()
            concrete_catalog = manager.get_concrete_catalog()
            strength_classes = concrete_catalog['strength_class'].tolist()
            
            selected_class = st.selectbox(
                "Strength Class",
                strength_classes,
                index=strength_classes.index(st.session_state.concrete_selected) 
                      if st.session_state.concrete_selected in strength_classes else 0,
                key='concrete_selector'
            )
            st.session_state.concrete_selected = selected_class
            
            concrete_comp = get_concrete_by_class(selected_class)
            st.info(f"f_ck = {concrete_comp.f_ck:.1f} MPa | f_cm = {concrete_comp.f_cm:.1f} MPa | E_cm = {concrete_comp.E_cm:.0f} MPa")
        
        with col2:
            st.markdown("**Default Steel Grade:**")
            default_steel_grade = st.selectbox(
                "Grade for Area Reinforcement",
                ['B500A', 'B500B', 'B500C'],
                index=1,
                key='default_steel_grade'
            )
            steel_test = create_steel(default_steel_grade)
            st.info(f"f_yk = {steel_test.f_sy:.0f} MPa | E_s = {steel_test.E_s:.0f} MPa")
        
            st.markdown("---")
            
            # ===== REINFORCEMENT LAYERS SECTION =====
            st.subheader("Reinforcement Layers")
            
            # Add layer buttons (moved from sidebar)
            st.markdown("**Add New Layer:**")
            col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
            with col1:
                if st.button("+ Bar", use_container_width=True, type="secondary"):
                    add_layer('Bar')
                    st.rerun()
            with col2:
                if st.button("+ Layer", use_container_width=True, type="secondary"):
                    add_layer('Layer')
                    st.rerun()
            with col3:
                if st.button("+ Area", use_container_width=True, type="secondary"):
                    add_layer('Area')
                    st.rerun()
            with col4:
                if st.button("Clear All", use_container_width=True):
                    st.session_state.layers = []
                    st.rerun()
            
            st.markdown("---")
            
            if len(st.session_state.layers) == 0:
                st.info("No layers yet. Click the buttons above to add reinforcement layers.")
            else:
                # Display each layer
                for layer_data in st.session_state.layers:
                    layer_id = layer_data['id']
                    
                    with st.expander(f"**{layer_data['name']}** ({layer_data['type']})", expanded=True):
                        # Layer controls
                        lcol1, lcol2, lcol3 = st.columns([2, 2, 1])
                    
                    with lcol1:
                        layer_data['name'] = st.text_input(
                            "Layer Name",
                            layer_data['name'],
                            key=f'name_{layer_id}'
                        )
                    
                    with lcol2:
                        layer_data['z'] = st.number_input(
                            "Position z [mm]",
                            0.0, 2000.0,
                            float(layer_data['z']),
                            10.0,
                            key=f'z_{layer_id}',
                            help="Distance from bottom fiber"
                        )
                    
                    with lcol3:
                        if st.button("🗑️", key=f'del_{layer_id}', help="Delete layer"):
                            delete_layer(layer_id)
                            st.rerun()
                    
                    st.markdown("---")
                    
                    # Type-specific inputs
                    if layer_data['type'] == 'Bar':
                        bcol1, bcol2, bcol3 = st.columns(3)
                        
                        with bcol1:
                            layer_data['material'] = st.radio(
                                "Material",
                                ['steel', 'carbon'],
                                index=0 if layer_data['material'] == 'steel' else 1,
                                key=f'mat_{layer_id}'
                            )
                        
                        with bcol2:
                            if layer_data['material'] == 'steel':
                                # Steel catalog
                                catalog = manager.get_steel_catalog()
                                diameters = sorted(catalog['nominal_diameter'].unique())
                                
                                layer_data['diameter'] = st.selectbox(
                                    "Diameter [mm]",
                                    diameters,
                                    index=diameters.index(layer_data['diameter']) if layer_data['diameter'] in diameters else 0,
                                    key=f'diam_{layer_id}'
                                )
                                
                                layer_data['grade'] = st.selectbox(
                                    "Grade",
                                    ['B500A', 'B500B', 'B500C'],
                                    index=['B500A', 'B500B', 'B500C'].index(layer_data['grade']),
                                    key=f'grade_{layer_id}'
                                )
                            else:  # carbon
                                catalog = manager.get_carbon_catalog()
                                diameters = sorted(catalog['nominal_diameter'].unique())
                                
                                layer_data['diameter'] = st.selectbox(
                                    "Diameter [mm]",
                                    diameters,
                                    index=diameters.index(layer_data['diameter']) if layer_data['diameter'] in diameters else 0,
                                    key=f'diam_{layer_id}'
                                )
                        
                        with bcol3:
                            layer_data['count'] = st.number_input(
                                "Number of bars",
                                1, 20,
                                layer_data['count'],
                                1,
                                key=f'count_{layer_id}'
                            )
                        
                        # Show computed area
                        try:
                            if layer_data['material'] == 'steel':
                                comp = SteelRebarComponent(
                                    nominal_diameter=layer_data['diameter'],
                                    grade=layer_data['grade']
                                )
                            else:
                                comp = CarbonBarComponent(
                                    nominal_diameter=layer_data['diameter']
                                )
                            
                            total_area = comp.area * layer_data['count']
                            st.caption(f"{layer_data['count']}×Ø{layer_data['diameter']} = {total_area:.0f} mm² | Product: {comp.product_id}")
                        except:
                            st.caption("⚠️ Invalid configuration")
                    
                    elif layer_data['type'] == 'Layer':
                        tcol1, tcol2, tcol3 = st.columns(3)
                        
                        with tcol1:
                            layer_data['material'] = st.selectbox(
                                "Material",
                                ['carbon', 'glass', 'basalt'],
                                index=0,
                                key=f'tmat_{layer_id}'
                            )
                        
                        with tcol2:
                            layer_data['roving_tex'] = st.selectbox(
                                "Roving [tex]",
                                [800, 1600, 2400, 3200],
                                index=0,
                                key=f'roving_{layer_id}'
                            )
                        
                        with tcol3:
                            layer_data['width'] = st.number_input(
                                "Width [mm]",
                                50.0, 2000.0,
                                float(layer_data['width']),
                                10.0,
                                key=f'width_{layer_id}'
                            )
                        
                        # Show computed area
                        spacing = 14.0  # Default
                        A_roving = layer_data['roving_tex'] / 1670.0
                        n_rovings = layer_data['width'] / spacing
                        total_area = n_rovings * A_roving
                        st.caption(f"{n_rovings:.1f} rovings × {A_roving:.2f} mm²/roving ≈ {total_area:.1f} mm²")
                    
                    else:  # Area
                        acol1, acol2, acol3 = st.columns(3)
                        
                        with acol1:
                            layer_data['A_s'] = st.number_input(
                                "Area A_s [mm²]",
                                0.0, 10000.0,
                                float(layer_data['A_s']),
                                50.0,
                                key=f'area_{layer_id}'
                            )
                        
                        with acol2:
                            layer_data['material_type'] = st.selectbox(
                                "Material Type",
                                ['steel', 'carbon'],
                                index=0 if layer_data['material_type'] == 'steel' else 1,
                                key=f'amat_{layer_id}'
                            )
                        
                        with acol3:
                            if layer_data['material_type'] == 'steel':
                                layer_data['grade'] = st.selectbox(
                                    "Grade",
                                    ['B500A', 'B500B', 'B500C'],
                                    index=['B500A', 'B500B', 'B500C'].index(layer_data.get('grade', 'B500B')),
                                    key=f'agrade_{layer_id}'
                                )
                        
                        st.caption(f"ℹ️ Product-independent reinforcement (for design optimization)")
        
        st.markdown("---")
        
        # ===== LIVE PREVIEW =====
        st.subheader("Live Preview")
        
        try:
            shape = build_shape()
            concrete = get_concrete_by_class(st.session_state.concrete_selected)
            reinforcement = build_reinforcement_from_layers()
            
            cs = CrossSection(
                shape=shape,
                concrete=concrete.matmod,
                reinforcement=reinforcement
            )
            
            fig, ax = plt.subplots(figsize=(8, 10))
            cs.plot_cross_section(ax=ax, show_dimensions=True, show_reinforcement=True)
            st.pyplot(fig)
            plt.close()
            
            # Summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Layers", reinforcement.n_layers)
            with col2:
                st.metric("Total A_s", f"{cs.A_s:.0f} mm²")
            with col3:
                st.metric("Ratio ρ", f"{cs.reinforcement_ratio:.4f}")
                    
        except Exception as e:
            st.error(f"⚠️ Error building cross-section: {str(e)}")
            
            st.markdown("---")
            st.info("**Next Step:** Go to **Bending Analysis** to analyze strain distributions and compute forces.")
    
    # ========================================
    # STEP 3: BENDING ANALYSIS
    # ========================================
    
    elif current_step == "analysis":
        st.header("Bending Analysis")
        st.markdown("""
        Analyze the cross-section under bending. Define strain distribution and compute internal forces.
        """)
        
        try:
            shape = build_shape()
            concrete = get_concrete_by_class(st.session_state.concrete_selected)
            reinforcement = build_reinforcement_from_layers()
            cs = CrossSection(shape=shape, concrete=concrete.matmod, reinforcement=reinforcement)
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Strain State")
                
                kappa = st.number_input(
                    "Curvature κ [1/mm]",
                    -0.0001, 0.0001, 0.00002,
                    0.000001, format="%.6f"
                )
                
                eps_top = st.number_input(
                    "Top strain ε_top [-]",
                    -0.01, 0.01, -0.002,
                    0.0001, format="%.6f"
                )
                
                eps_bottom = eps_top + kappa * cs.h_total
                
                st.info(f"ε_bottom = {eps_bottom:.6f}")
                
                # Compute forces
                N, M = cs.get_N_M(kappa, eps_bottom)
                
                st.markdown("---")
                st.metric("Axial Force N", f"{N/1000:.1f} kN")
                st.metric("Moment M", f"{M/1e6:.1f} kNm")
            
            with col2:
                st.subheader("Visualization")
                st.info("Strain/stress distribution plots coming soon")
            
            st.markdown("---")
            st.info("**Next Step:** Go to **Summary** for complete documentation and export options.")
                
        except Exception as e:
            st.warning(f"⚠️ Define cross-section first (Step 2). Error: {str(e)}")
    
    # ========================================
    # STEP 4: SUMMARY
    # ========================================
    
    elif current_step == "summary":
        st.header("Complete Summary")
        st.markdown("""
        Full documentation of the designed cross-section with all properties and layer details.
        """)
        
        try:
            shape = build_shape()
            concrete = get_concrete_by_class(st.session_state.concrete_selected)
            reinforcement = build_reinforcement_from_layers()
            cs = CrossSection(shape=shape, concrete=concrete.matmod, reinforcement=reinforcement)
            
            summary = cs.get_summary()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("Geometry")
                for key, value in summary['geometry'].items():
                    st.text(f"{key}: {value}")
            
            with col2:
                st.subheader("Concrete")
                st.text(f"Grade: {st.session_state.concrete_selected}")
                st.text(f"f_ck: {concrete.f_ck:.1f} MPa")
                st.text(f"f_cm: {concrete.f_cm:.1f} MPa")
                st.text(f"E_cm: {concrete.E_cm:.0f} MPa")
            
            with col3:
                st.subheader("Reinforcement")
                for key, value in summary['reinforcement'].items():
                    if isinstance(value, float):
                        st.text(f"{key}: {value:.2f}")
                    else:
                        st.text(f"{key}: {value}")
            
            st.markdown("---")
            
            # Layer details
            st.subheader("Layer Details")
            layer_data = []
            for layer in reinforcement.layers:
                layer_data.append({
                    'Name': layer.name,
                    'Type': type(layer).__name__,
                    'z [mm]': layer.z,
                    'A_s [mm²]': f"{layer.A_s:.1f}"
                })
            
            if layer_data:
                df = pd.DataFrame(layer_data)
                st.dataframe(df, use_container_width=True)
            
            st.markdown("---")
            
            # Export options (future)
            st.subheader("Export Options")
            st.info("Export to JSON/PDF coming in Phase 3")
            
            # Completion message
            st.success(
                "**Cross-section design complete**\n\n"
                "Ready for:\n"
                "- Moment-curvature analysis (Phase 3)\n"
                "- Ultimate capacity calculation\n"
                "- Design optimization"
            )
            
        except Exception as e:
            st.error(f"Error generating summary: {str(e)}")
            st.info("Complete Steps 1-2 first: Select materials and define cross-section.")

# ========================================
# RUN APP
# ========================================

if __name__ == "__main__":
    main()
