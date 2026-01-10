"""
Component Catalog Browser - Streamlit Application

Interactive browser for concrete and reinforcement component catalogs.
Provides table views, parameter details, and stress-strain visualizations.
Features: filtering, search, comparison, export.

Run with: streamlit run component_catalog_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json

# Import catalog functions
from bmcs_cross_section.cs_components import (
    # Catalog creation
    create_steel_rebar_catalog,
    create_carbon_bar_catalog,
    create_textile_catalog,
    create_concrete_catalog,
    # Component classes
    SteelRebarComponent,
    CarbonBarComponent,
    TextileReinforcementComponent,
    ConcreteComponent,
)


# Configure Streamlit page
st.set_page_config(
    page_title="Component Catalog",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for compact layout
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    h1 {font-size: 1.5rem; margin-bottom: 0.5rem;}
    h2 {font-size: 1.2rem; margin-bottom: 0.3rem;}
    h3 {font-size: 1rem; margin-bottom: 0.2rem;}
    .stMetric {padding: 0.2rem 0;}
    .stMetric label {font-size: 0.8rem;}
    .stMetric [data-testid="stMetricValue"] {font-size: 1.2rem;}
</style>
""", unsafe_allow_html=True)


# Cache catalog loading
@st.cache_data
def load_catalogs():
    """Load all catalogs (cached for performance)"""
    return {
        'steel': create_steel_rebar_catalog(),
        'carbon': create_carbon_bar_catalog(),
        'textile': create_textile_catalog(),
        'concrete': create_concrete_catalog(),
    }


def format_catalog_table(df, catalog_type):
    """Format catalog dataframe for display"""
    if catalog_type == 'concrete':
        # Concrete: show key columns
        display_cols = ['product_id', 'strength_class', 'f_ck', 'f_cm', 'f_cd', 'E_cm']
        if all(col in df.columns for col in display_cols):
            return df[display_cols].copy()
    elif catalog_type in ['steel', 'carbon']:
        # Bar reinforcement: show diameter, strength, modulus
        display_cols = ['product_id', 'name', 'nominal_diameter', 'area', 'f_tk', 'f_td', 'E']
        if all(col in df.columns for col in display_cols):
            return df[display_cols].copy()
    elif catalog_type == 'textile':
        # Textile: show material, area per width, properties
        display_cols = ['product_id', 'name', 'material_type', 'area_per_width', 'grid_spacing', 'f_tk', 'E']
        if all(col in df.columns for col in display_cols):
            return df[display_cols].copy()
    
    return df


def create_component_from_row(row, catalog_type):
    """Recreate component instance from catalog row"""
    if catalog_type == 'steel':
        # Extract diameter and grade from product_id or name
        diameter = row['nominal_diameter']
        # Extract grade (B500A, B500B, B500C)
        if 'B500A' in row['name']:
            grade = 'B500A'
        elif 'B500B' in row['name']:
            grade = 'B500B'
        elif 'B500C' in row['name']:
            grade = 'B500C'
        else:
            grade = 'B500B'  # default
        return SteelRebarComponent(nominal_diameter=diameter, grade=grade)
    
    elif catalog_type == 'carbon':
        diameter = row['nominal_diameter']
        return CarbonBarComponent(nominal_diameter=diameter)
    
    elif catalog_type == 'textile':
        material = row['material_type']
        roving = row['roving_tex']
        return TextileReinforcementComponent(material_type=material, roving_tex=roving)
    
    elif catalog_type == 'concrete':
        strength_class = row['strength_class']
        # Create concrete component with matmod using f_cm
        from bmcs_cross_section.matmod.ec2_concrete import EC2Concrete
        concrete_matmod = EC2Concrete(f_cm=float(row['f_cm']))
        
        return ConcreteComponent(
            product_id=row['product_id'],
            name=row.get('name', strength_class),
            strength_class=strength_class,
            f_ck=row['f_ck'],
            f_cm=row['f_cm'],
            E_cm=row['E_cm'],
            matmod=concrete_matmod,
        )
    
    return None


def display_component_parameters(component, catalog_type):
    """Display component parameters in formatted frame with comprehensive descriptions"""
    
    # Set color based on material type
    if catalog_type == 'concrete':
        frame_color = "#E3F2FD"  # Pale blue
    else:
        frame_color = "#FFEBEE"  # Pale red
    
    # Create styled container
    st.markdown(f"""
    <div style="background-color: {frame_color}; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
        <h4 style="margin-top: 0; margin-bottom: 10px; color: #424242;">{component.name}</h4>
        <p style="margin: 0; color: #757575; font-size: 0.9em;">{component.product_id}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Type-specific parameters in clear layout
    if catalog_type in ['steel', 'carbon', 'textile']:
        st.markdown("**Geometric Properties**")
        col1, col2 = st.columns(2)
        with col1:
            if hasattr(component, 'nominal_diameter'):
                st.metric("Nominal Diameter", f"{component.nominal_diameter} mm", 
                         help="Nominal diameter of the bar")
            if hasattr(component, 'area_per_width'):
                st.metric("Area per Width", f"{component.area_per_width:.1f} mm²/m",
                         help="Total reinforcement area per meter width")
        with col2:
            if hasattr(component, 'area'):
                st.metric("Cross-sectional Area", f"{component.area:.2f} mm²",
                         help="Cross-sectional area of single bar")
            if hasattr(component, 'grid_spacing'):
                st.metric("Grid Spacing", f"{component.grid_spacing} mm",
                         help="Distance between parallel rovings")
        
        st.markdown("**Characteristic Properties**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Tensile Strength f_tk", f"{component.f_tk:.0f} MPa",
                     help="Characteristic tensile strength (5% fractile)")
            st.metric("Elastic Modulus E", f"{component.E:.0f} MPa",
                     help="Young's modulus of elasticity")
        with col2:
            st.metric("Ultimate Strain ε_uk", f"{component.eps_uk:.4f}",
                     help="Characteristic ultimate strain")
            st.metric("Safety Factor γ_s", f"{component.gamma_s:.2f}",
                     help="Partial safety factor for reinforcement")
        
        st.markdown("**Design Properties**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Design Strength f_td", f"{component.f_td:.1f} MPa",
                     help="Design tensile strength = f_tk / γ_s")
        with col2:
            st.metric("Design Strain ε_ud", f"{component.eps_ud:.4f}",
                     help="Design ultimate strain = ε_uk / γ_s")
    
    elif catalog_type == 'concrete':
        st.markdown("**Strength Properties**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Characteristic Strength f_ck", f"{component.f_ck} MPa",
                     help="Characteristic compressive cylinder strength (5% fractile)")
            st.metric("Mean Strength f_cm", f"{component.f_cm} MPa",
                     help="Mean compressive cylinder strength")
        with col2:
            st.metric("Design Strength f_cd", f"{component.f_cd:.1f} MPa",
                     help="Design compressive strength = α_cc × f_ck / γ_c")
            st.metric("Safety Factor γ_c", f"{component.gamma_c:.2f}",
                     help="Partial safety factor for concrete")
        
        st.markdown("**Deformation Properties**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Elastic Modulus E_cm", f"{component.E_cm} MPa",
                     help="Secant modulus of elasticity")
        with col2:
            st.metric("Strength Factor α_cc", f"{component.alpha_cc:.2f}",
                     help="Coefficient for long-term effects on strength")


def plot_stress_strain_curve(component, catalog_type):
    """Plot stress-strain curve for component"""
    
    fig, ax = plt.subplots(figsize=(7, 5))
    
    if catalog_type == 'concrete':
        # Concrete: blue, compression quadrant
        component.plot_stress_strain(ax=ax, show_limits=True, color='blue', alpha_fill=0.2)
    else:
        # Reinforcement: dark red
        component.plot_stress_strain(ax=ax, show_limits=True, color='darkred', alpha_fill=0.2)
    
    ax.grid(True, alpha=0.3)
    
    st.pyplot(fig)
    plt.close()


def plot_comparison(components, catalog_types):
    """Plot multiple components for comparison"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for component, cat_type in zip(components, catalog_types):
        if cat_type == 'concrete':
            color = 'blue'
        else:
            color = 'darkred'
        
        # Plot with label
        component.plot_stress_strain(ax=ax, show_limits=False, color=color, alpha_fill=0.1)
    
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    st.pyplot(fig)
    plt.close()


def export_component_to_json(component):
    """Export component parameters to JSON"""
    data = {
        'product_id': component.product_id,
        'name': component.name,
    }
    
    # Add all numeric attributes
    for attr in dir(component):
        if not attr.startswith('_') and not callable(getattr(component, attr)):
            value = getattr(component, attr)
            if isinstance(value, (int, float, str)):
                data[attr] = value
    
    return json.dumps(data, indent=2)


def apply_filters(df, catalog_type, filters):
    """Apply filters to catalog dataframe"""
    filtered_df = df.copy()
    
    if catalog_type in ['steel', 'carbon']:
        # Filter by diameter
        if filters.get('diameter_range'):
            min_d, max_d = filters['diameter_range']
            filtered_df = filtered_df[
                (filtered_df['nominal_diameter'] >= min_d) & 
                (filtered_df['nominal_diameter'] <= max_d)
            ]
        
        # Filter by strength
        if filters.get('strength_range'):
            min_s, max_s = filters['strength_range']
            filtered_df = filtered_df[
                (filtered_df['f_tk'] >= min_s) & 
                (filtered_df['f_tk'] <= max_s)
            ]
    
    elif catalog_type == 'textile':
        # Filter by area per width
        if filters.get('area_range'):
            min_a, max_a = filters['area_range']
            filtered_df = filtered_df[
                (filtered_df['area_per_width'] >= min_a) & 
                (filtered_df['area_per_width'] <= max_a)
            ]
    
    elif catalog_type == 'concrete':
        # Filter by strength class
        if filters.get('strength_range'):
            min_s, max_s = filters['strength_range']
            filtered_df = filtered_df[
                (filtered_df['f_ck'] >= min_s) & 
                (filtered_df['f_ck'] <= max_s)
            ]
    
    # Search by product ID or name
    if filters.get('search_text'):
        search = filters['search_text'].lower()
        mask = filtered_df['product_id'].str.lower().str.contains(search, na=False)
        if 'name' in filtered_df.columns:
            mask = mask | filtered_df['name'].str.lower().str.contains(search, na=False)
        filtered_df = filtered_df[mask]
    
    return filtered_df


def main():
    """Main application"""
    
    # Load catalogs
    catalogs = load_catalogs()
    
    # Sidebar - Component Selection
    st.sidebar.title("Component Selection")
    
    # View mode selection
    view_mode = st.sidebar.radio(
        "View Mode:",
        options=['Single View', 'Comparison'],
        index=0
    )
    
    # Main category
    main_category = st.sidebar.radio(
        "Category:",
        options=['Concrete', 'Reinforcement'],
        index=0
    )
    
    # Subcategory for reinforcement
    catalog_type = None
    current_catalog = None
    
    if main_category == 'Concrete':
        catalog_type = 'concrete'
        current_catalog = catalogs['concrete']
        st.sidebar.caption(f"{len(current_catalog)} grades available")
    
    else:  # Reinforcement
        sub_category = st.sidebar.selectbox(
            "Type:",
            options=['Steel Rebars', 'Carbon Bars', 'Textile Products'],
            index=0
        )
        
        if sub_category == 'Steel Rebars':
            catalog_type = 'steel'
            current_catalog = catalogs['steel']
            st.sidebar.caption(f"{len(current_catalog)} products")
        elif sub_category == 'Carbon Bars':
            catalog_type = 'carbon'
            current_catalog = catalogs['carbon']
            st.sidebar.caption(f"{len(current_catalog)} products")
        else:  # Textile
            catalog_type = 'textile'
            current_catalog = catalogs['textile']
            st.sidebar.caption(f"{len(current_catalog)} products")
    
    # === FILTERING SECTION ===
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")
    
    filters = {}
    
    # Search box
    search_text = st.sidebar.text_input("🔍 Search", placeholder="Product ID or name...")
    if search_text:
        filters['search_text'] = search_text
    
    # Type-specific filters
    if catalog_type in ['steel', 'carbon']:
        # Diameter range
        diameters = current_catalog['nominal_diameter'].unique()
        min_d, max_d = float(diameters.min()), float(diameters.max())
        
        if min_d < max_d:
            diameter_filter = st.sidebar.slider(
                "Diameter (mm)",
                min_value=min_d,
                max_value=max_d,
                value=(min_d, max_d)
            )
            if diameter_filter != (min_d, max_d):
                filters['diameter_range'] = diameter_filter
        
        # Strength range
        strengths = current_catalog['f_tk']
        min_s, max_s = float(strengths.min()), float(strengths.max())
        
        if min_s < max_s:
            strength_filter = st.sidebar.slider(
                "Tensile Strength f_tk (MPa)",
                min_value=min_s,
                max_value=max_s,
                value=(min_s, max_s)
            )
            if strength_filter != (min_s, max_s):
                filters['strength_range'] = strength_filter
    
    elif catalog_type == 'textile':
        # Area per width range
        areas = current_catalog['area_per_width']
        min_a, max_a = float(areas.min()), float(areas.max())
        
        if min_a < max_a:
            area_filter = st.sidebar.slider(
                "Area per Width (mm²/m)",
                min_value=min_a,
                max_value=max_a,
                value=(min_a, max_a)
            )
            if area_filter != (min_a, max_a):
                filters['area_range'] = area_filter
    
    elif catalog_type == 'concrete':
        # Strength class range
        strengths = current_catalog['f_ck']
        min_s, max_s = float(strengths.min()), float(strengths.max())
        
        if min_s < max_s:
            strength_filter = st.sidebar.slider(
                "Characteristic Strength f_ck (MPa)",
                min_value=min_s,
                max_value=max_s,
                value=(min_s, max_s)
            )
            if strength_filter != (min_s, max_s):
                filters['strength_range'] = strength_filter
    
    # Apply filters
    filtered_catalog = current_catalog
    if filters:
        filtered_catalog = apply_filters(current_catalog, catalog_type, filters)
        st.sidebar.caption(f"Showing {len(filtered_catalog)} items")
    
    # Reset filters button
    if st.sidebar.button("🔄 Reset Filters"):
        # Clear session state and rerun
        if 'selected_idx' in st.session_state:
            del st.session_state['selected_idx']
        st.rerun()
    
    # === MAIN CONTENT AREA ===
    
    # Adaptive title based on catalog type
    if catalog_type == 'concrete':
        catalog_title = "Concrete Catalog"
    elif catalog_type == 'steel':
        catalog_title = "Steel Reinforcement Catalog"
    elif catalog_type == 'carbon':
        catalog_title = "Carbon Reinforcement Catalog"
    elif catalog_type == 'textile':
        catalog_title = "Textile Reinforcement Catalog"
    else:
        catalog_title = "Component Catalog"
    
    st.markdown(f"## {catalog_title}")
    
    # Format table for display
    display_df = format_catalog_table(filtered_catalog, catalog_type)
    
    # Handle different view modes
    if view_mode == 'Single View':
        # === SINGLE VIEW MODE ===
        
        # Find default selection index (C25/30 for concrete, first item otherwise)
        default_idx = 0
        if catalog_type == 'concrete' and len(filtered_catalog) > 0:
            # Find C25/30 in filtered results
            c25_matches = filtered_catalog[filtered_catalog['strength_class'] == 'C25/30']
            if not c25_matches.empty:
                # Get position in filtered dataframe (not absolute index)
                default_idx = filtered_catalog.reset_index(drop=True).index[
                    filtered_catalog.reset_index(drop=True)['strength_class'] == 'C25/30'
                ].tolist()[0]
        
        # Use session state to track selection
        if 'selected_idx' not in st.session_state:
            st.session_state.selected_idx = default_idx
        
        # Display table with selection
        event = st.dataframe(
            display_df,
            width='stretch',
            height=150,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Update selected index
        selected_rows = event.selection.rows if event.selection else []
        if len(selected_rows) > 0:
            st.session_state.selected_idx = selected_rows[0]
        
        # Get selected row (use session state if no explicit selection)
        if len(filtered_catalog) == 0:
            st.warning("No components match the current filters")
            return
        
        selected_idx = min(st.session_state.selected_idx, len(filtered_catalog) - 1)
        selected_row = filtered_catalog.iloc[selected_idx]
        
        # Recreate component from row
        component = create_component_from_row(selected_row, catalog_type)
        
        if component:
            # Export button
            col_export, col_space = st.columns([1, 4])
            with col_export:
                if st.button("📥 Export JSON"):
                    json_data = export_component_to_json(component)
                    st.download_button(
                        label="Download",
                        data=json_data,
                        file_name=f"{component.product_id}.json",
                        mime="application/json"
                    )
            
            # Lower section: Parameters (left) and Plot (right)
            col_left, col_right = st.columns([1.2, 1])
            
            with col_left:
                display_component_parameters(component, catalog_type)
            
            with col_right:
                plot_stress_strain_curve(component, catalog_type)
        else:
            st.error("Could not load component")
    
    else:
        # === COMPARISON MODE ===
        st.info("💡 Select multiple components to compare their stress-strain behavior")
        
        # Display table with multi-selection
        event = st.dataframe(
            display_df,
            width='stretch',
            height=250,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row"
        )
        
        selected_rows = event.selection.rows if event.selection else []
        
        if len(selected_rows) == 0:
            st.info("Select components from the table above to compare")
        elif len(selected_rows) > 5:
            st.warning("Please select 5 or fewer components for comparison")
        else:
            # Create components from selected rows
            components = []
            catalog_types = []
            
            for idx in selected_rows:
                row = filtered_catalog.iloc[idx]
                component = create_component_from_row(row, catalog_type)
                if component:
                    components.append(component)
                    catalog_types.append(catalog_type)
            
            if components:
                st.markdown(f"### Comparing {len(components)} components")
                
                # Export all button
                if st.button("📥 Export All as JSON"):
                    all_data = [json.loads(export_component_to_json(c)) for c in components]
                    json_str = json.dumps(all_data, indent=2)
                    st.download_button(
                        label="Download",
                        data=json_str,
                        file_name="comparison_export.json",
                        mime="application/json"
                    )
                
                # Show comparison plot
                plot_comparison(components, catalog_types)
                
                # Show parameter table
                st.markdown("#### Component Parameters")
                
                # Build comparison dataframe
                comp_data = []
                for comp in components:
                    row_data = {'Product ID': comp.product_id, 'Name': comp.name}
                    
                    if catalog_type in ['steel', 'carbon']:
                        row_data.update({
                            'Diameter (mm)': comp.nominal_diameter,
                            'Area (mm²)': f"{comp.area:.2f}",
                            'f_tk (MPa)': f"{comp.f_tk:.0f}",
                            'f_td (MPa)': f"{comp.f_td:.1f}",
                            'E (MPa)': f"{comp.E:.0f}",
                        })
                    elif catalog_type == 'textile':
                        row_data.update({
                            'Material': comp.material_type,
                            'Area/Width (mm²/m)': f"{comp.area_per_width:.1f}",
                            'Grid (mm)': comp.grid_spacing,
                            'f_tk (MPa)': f"{comp.f_tk:.0f}",
                            'E (MPa)': f"{comp.E:.0f}",
                        })
                    elif catalog_type == 'concrete':
                        row_data.update({
                            'Class': comp.strength_class,
                            'f_ck (MPa)': comp.f_ck,
                            'f_cm (MPa)': comp.f_cm,
                            'f_cd (MPa)': f"{comp.f_cd:.1f}",
                            'E_cm (MPa)': comp.E_cm,
                        })
                    
                    comp_data.append(row_data)
                
                comp_df = pd.DataFrame(comp_data)
                st.dataframe(comp_df, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
