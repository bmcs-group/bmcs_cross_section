"""
Components View - Component Catalog Browser
===========================================

Interactive catalog browser for concrete and reinforcement components.
Shows table view, parameter details, and stress-strain curves.

Can be run standalone for testing:
    streamlit run -m bmcs_cross_section.streamlit_app.components_view
"""

import streamlit as st
import matplotlib.pyplot as plt
from bmcs_cross_section.cs_components import (
    get_catalog_manager,
    SteelRebarComponent,
    CarbonBarComponent,
    TextileReinforcementComponent,
    ConcreteComponent,
)
from bmcs_cross_section.matmod.ec2_concrete import EC2Concrete


def get_catalog_manager_cached():
    """Get cached catalog manager"""
    if 'catalog_manager' not in st.session_state:
        st.session_state.catalog_manager = get_catalog_manager()
    return st.session_state.catalog_manager


def render_components_view():
    """Render the Components catalog browser view"""
    
    # Custom CSS for consistent font sizing
    st.markdown("""
    <style>
        /* Consistent typography */
        h1 {font-size: 1.8rem; margin-bottom: 0.5rem;}
        h2 {font-size: 1.5rem; margin-bottom: 0.5rem;}
        h3 {font-size: 1.2rem; margin-bottom: 0.3rem;}
        h4 {font-size: 1.1rem; margin-bottom: 0.3rem;}
        
        /* Make tab text larger and prominent */
        .stTabs [data-baseweb="tab-list"] button {
            font-size: 1.4rem !important;
            font-weight: 600 !important;
            padding: 0.75rem 1.5rem !important;
        }
        
        .stTabs [data-baseweb="tab-list"] button div {
            font-size: 1.4rem !important;
            font-weight: 600 !important;
        }
        
        .stTabs [data-baseweb="tab-list"] button p {
            font-size: 1.4rem !important;
            font-weight: 600 !important;
        }
        
        /* Compact metrics - smaller value, normal label */
        .stMetric {padding: 0.3rem 0;}
        .stMetric label {font-size: 0.85rem; font-weight: 500;}
        .stMetric [data-testid="stMetricValue"] {font-size: 1.1rem;}
        
        /* Table font size */
        .stDataFrame {font-size: 0.9rem;}
    </style>
    """, unsafe_allow_html=True)
    
    st.header("Component Catalogs")
    
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
            width='stretch'
        )
        
        # Update selection
        if event.selection.rows:
            st.session_state.concrete_selected_idx = event.selection.rows[0]
        
        selected_idx = min(st.session_state.concrete_selected_idx, len(catalog) - 1)
        selected_row = catalog.iloc[selected_idx]
        
        # Create component - EC2Concrete expects f_ck not f_cm
        concrete_matmod = EC2Concrete(f_ck=float(selected_row['f_ck']))
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
            # Styled container with colored frame
            st.markdown(f"""
            <div style="background-color: #E3F2FD; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                <h4 style="margin-top: 0; margin-bottom: 10px; color: #424242;">{component.name}</h4>
                <p style="margin: 0; color: #757575; font-size: 0.9em;">{component.product_id}</p>
            </div>
            """, unsafe_allow_html=True)
            
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
            st.markdown("**Stress-Strain Curve**")
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
            width='stretch'
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
            # Styled container with colored frame
            st.markdown(f"""
            <div style="background-color: #FFEBEE; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                <h4 style="margin-top: 0; margin-bottom: 10px; color: #424242;">{component.name}</h4>
                <p style="margin: 0; color: #757575; font-size: 0.9em;">{component.product_id}</p>
            </div>
            """, unsafe_allow_html=True)
            
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
            st.markdown("**Stress-Strain Curve**")
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
            width='stretch'
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
            # Styled container with colored frame
            st.markdown(f"""
            <div style="background-color: #FFEBEE; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                <h4 style="margin-top: 0; margin-bottom: 10px; color: #424242;">{component.name}</h4>
                <p style="margin: 0; color: #757575; font-size: 0.9em;">{component.product_id}</p>
            </div>
            """, unsafe_allow_html=True)
            
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
            st.markdown("**Stress-Strain Curve**")
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
            width='stretch'
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
            grid_spacing=selected_row['grid_spacing'],
            area_per_width=selected_row['area_per_width'],
            f_tk=selected_row['f_tk'],
            E=selected_row['E']
        )
        
        # Two columns: parameters (left) and plot (right)
        col_params, col_plot = st.columns([1.2, 1])
        
        with col_params:
            # Styled container with colored frame
            st.markdown(f"""
            <div style="background-color: #FFEBEE; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                <h4 style="margin-top: 0; margin-bottom: 10px; color: #424242;">{component.name}</h4>
                <p style="margin: 0; color: #757575; font-size: 0.9em;">{component.product_id}</p>
            </div>
            """, unsafe_allow_html=True)
            
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
            st.markdown("**Stress-Strain Curve**")
            fig, ax = plt.subplots(figsize=(6, 4.5))
            component.plot_stress_strain(ax=ax, show_limits=True, color='darkred', alpha_fill=0.2)
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            plt.close()


# Standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Components - SCADT",
        page_icon="📚",
        layout="wide"
    )
    
    render_components_view()
