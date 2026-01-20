"""
Cross-Section View - Geometry and Reinforcement Definition
==========================================================

Define cross-section geometry (rectangular, T, I) and reinforcement layout.
Manage reinforcement layers (bars, textiles, area).

Can be run standalone for testing:
    streamlit run -m bmcs_cross_section.streamlit_app.cross_section_view
"""

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from scite.cs_components import (CarbonBarComponent, SteelRebarComponent,
                                 TextileReinforcementComponent,
                                 get_catalog_manager, get_concrete_by_class)
from scite.cs_design import (AreaReinforcement, BarReinforcement, CrossSection,
                             IShape, LayerReinforcement, RectangularShape,
                             ReinforcementLayout, TShape)
from scite.matmod import create_carbon, create_steel


def get_catalog_manager_cached():
    """Get cached catalog manager"""
    if 'catalog_manager' not in st.session_state:
        st.session_state.catalog_manager = get_catalog_manager()
    return st.session_state.catalog_manager


def initialize_cross_section_state():
    """Initialize session state for cross-section view"""
    if 'cs_layers' not in st.session_state:
        st.session_state.cs_layers = []
    if 'cs_layer_counter' not in st.session_state:
        st.session_state.cs_layer_counter = 0
    if 'cs_concrete_selected' not in st.session_state:
        st.session_state.cs_concrete_selected = 'C30/37'
    if 'cs_shape_params' not in st.session_state:
        st.session_state.cs_shape_params = {
            'type': 'Rectangular',
            'b': 300.0,
            'h': 500.0
        }
    if 'cs_expanded_layer' not in st.session_state:
        st.session_state.cs_expanded_layer = None
    if 'cs_expanded_layer' not in st.session_state:
        st.session_state.cs_expanded_layer = None


def add_layer(layer_type):
    """Add a new reinforcement layer of specified type"""
    st.session_state.cs_layer_counter += 1
    layer_id = st.session_state.cs_layer_counter
    
    # Default position based on existing layers
    if len(st.session_state.cs_layers) == 0:
        default_z = 450.0  # Bottom layer
    elif len(st.session_state.cs_layers) == 1:
        default_z = 50.0   # Top layer
    else:
        default_z = 250.0  # Middle
    
    new_layer = {
        'id': layer_id,
        'type': layer_type,
        'z': default_z,
        'name': f'Layer {layer_id}',
    }
    
    # Type-specific defaults - store product selection info
    if layer_type == 'Bar':
        # For Bar: need to select from steel/carbon catalog
        # Material is determined by the selected product (not selectable separately)
        new_layer.update({
            'catalog_type': 'steel',  # Which catalog to browse (steel or carbon)
            'product_id': None,  # Will be selected from catalog
            'count': 4
        })
    elif layer_type == 'Layer':
        # For Layer: need to select from textile catalog
        # Material is determined by the selected product
        new_layer.update({
            'product_id': None,  # Will be selected from catalog
            'width': 300.0
        })
    else:  # Area
        # Area uses direct material model (no component)
        new_layer.update({
            'A_s': 1000.0,
            'material_type': 'steel',
            'grade': 'B500B'
        })
    
    st.session_state.cs_layers.append(new_layer)
    # Set this layer to be expanded when rendered
    st.session_state.cs_expanded_layer = layer_id


def delete_layer(layer_id):
    """Remove a layer by ID"""
    st.session_state.cs_layers = [l for l in st.session_state.cs_layers if l['id'] != layer_id]


def create_shape_from_params():
    """Create shape object from session state parameters"""
    params = st.session_state.cs_shape_params
    shape_type = params['type']
    
    if shape_type == 'Rectangular':
        return RectangularShape(b=params['b'], h=params['h'])
    elif shape_type == 'T-Section':
        return TShape(
            b_f=params.get('b_f', 600.0),
            h_f=params.get('h_f', 150.0),
            b_w=params.get('b_w', 200.0),
            h_w=params.get('h_w', 400.0)
        )
    elif shape_type == 'I-Section':
        return IShape(
            b_f=params.get('b_f', 400.0),
            h_f=params.get('h_f', 100.0),
            b_w=params.get('b_w', 150.0),
            h_w=params.get('h_w', 300.0)
        )
    else:
        return RectangularShape(b=300.0, h=500.0)


def build_reinforcement_from_layers():
    """Build ReinforcementLayout from session state layers using selected catalog products"""
    layers = []
    manager = get_catalog_manager_cached()
    
    for layer_data in st.session_state.cs_layers:
        try:
            if layer_data['type'] == 'Bar':
                # Get component from selected product
                product_id = layer_data.get('product_id')
                if product_id is None:
                    st.warning(f"No product selected for {layer_data['name']}")
                    continue
                
                # Find product in appropriate catalog
                # The catalog_type determines which catalog, and thus which material
                catalog_type = layer_data.get('catalog_type', 'steel')
                if catalog_type == 'steel':
                    catalog = manager.get_steel_catalog()
                    product = catalog[catalog['product_id'] == product_id].iloc[0]
                    # Get grade from catalog or extract from product_id (e.g., "REBAR-B500B-D12" -> "B500B")
                    grade = product.get('grade', product_id.split('-')[1] if '-' in product_id else 'B500B')
                    component = SteelRebarComponent(
                        nominal_diameter=product['nominal_diameter'],
                        grade=grade
                    )
                else:  # carbon
                    catalog = manager.get_carbon_catalog()
                    product = catalog[catalog['product_id'] == product_id].iloc[0]
                    component = CarbonBarComponent(
                        nominal_diameter=product['nominal_diameter']
                    )
                
                # Create BarReinforcement with component
                # Material model comes from component.matmod (property)
                reinf = BarReinforcement(
                    z=layer_data['z'],
                    component=component,
                    count=layer_data['count'],
                    name=layer_data.get('name')
                )
                layers.append(reinf)
                
            elif layer_data['type'] == 'Layer':
                # Get component from selected product
                product_id = layer_data.get('product_id')
                if product_id is None:
                    st.warning(f"No product selected for {layer_data['name']}")
                    continue
                
                # Find product in textile catalog
                catalog = manager.get_textile_catalog()
                product = catalog[catalog['product_id'] == product_id].iloc[0]
                
                component = TextileReinforcementComponent(
                    product_id=product['product_id'],
                    name=product['name'],
                    material_type=product['material_type'],
                    roving_tex=product['roving_tex'],
                    grid_spacing=product['grid_spacing'],
                    area_per_width=product['area_per_width'],
                    f_tk=product['f_tk'],
                    E=product['E'],
                    eps_uk=product['eps_uk']
                )
                
                # Create LayerReinforcement with component
                reinf = LayerReinforcement(
                    z=layer_data['z'],
                    component=component,
                    width=layer_data['width'],
                    name=layer_data.get('name')
                )
                layers.append(reinf)
                
            else:  # Area
                # Area reinforcement uses material model directly (no component)
                if layer_data['material_type'] == 'steel':
                    matmod = create_steel(layer_data['grade'])
                else:  # carbon
                    matmod = create_carbon()
                
                reinf = AreaReinforcement(
                    z=layer_data['z'],
                    A_s=layer_data['A_s'],
                    matmod=matmod,
                    name=layer_data.get('name')
                )
                layers.append(reinf)
                
        except Exception as e:
            st.error(f"Error creating layer '{layer_data['name']}': {str(e)}")
            continue
    
    return ReinforcementLayout(layers=layers)


def plot_geometry(shape):
    """Plot cross-section geometry"""
    fig, ax = plt.subplots(figsize=(6, 5))
    
    # Get boundary polygon from shape
    vertices = shape.get_boundary_polygon()
    
    # Close the polygon
    vertices_closed = np.vstack([vertices, vertices[0]])
    
    # Plot
    ax.plot(vertices_closed[:, 0], vertices_closed[:, 1], 'b-', linewidth=2)
    ax.fill(vertices_closed[:, 0], vertices_closed[:, 1], color='lightblue', alpha=0.3)
    
    # Formatting
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.set_xlabel('Width [mm]')
    ax.set_ylabel('Height [mm]')
    ax.set_title('Cross-Section Geometry')
    
    # Set limits
    ax.set_xlim(shape.get_plot_xlim())
    ax.set_ylim(shape.get_plot_ylim())
    
    return fig


def plot_reinforcement_layout(shape, layers):
    """Plot reinforcement layout on cross-section"""
    fig, ax = plt.subplots(figsize=(6, 5))
    
    # Get boundary polygon from shape
    vertices = shape.get_boundary_polygon()
    vertices_closed = np.vstack([vertices, vertices[0]])
    
    # Plot shape outline
    ax.plot(vertices_closed[:, 0], vertices_closed[:, 1], 'b-', linewidth=2)
    ax.fill(vertices_closed[:, 0], vertices_closed[:, 1], color='lightblue', alpha=0.2)
    
    # Plot reinforcement layers
    manager = get_catalog_manager_cached()
    
    for layer in layers:
        if layer['type'] == 'Bar':
            # Plot bars as circles - get diameter from selected product
            z = layer['z']
            count = layer['count']
            
            # Get diameter from catalog product
            product_id = layer.get('product_id')
            if product_id:
                catalog_type = layer.get('catalog_type', 'steel')
                if catalog_type == 'steel':
                    catalog = manager.get_steel_catalog()
                else:
                    catalog = manager.get_carbon_catalog()
                product = catalog[catalog['product_id'] == product_id].iloc[0]
                diameter = product['nominal_diameter']
            else:
                diameter = 20  # default
            
            # Distribute bars evenly across width
            b = st.session_state.cs_shape_params.get('b', 300.0)
            if count > 1:
                x_positions = np.linspace(-b/2 + 50, b/2 - 50, count)
            else:
                x_positions = [0]
            
            for x in x_positions:
                circle = plt.Circle((x, z), diameter/2, color='red', alpha=0.7)
                ax.add_patch(circle)
        
        elif layer['type'] == 'Layer':
            # Plot textile layer as rectangle
            z = layer['z']
            width = layer.get('width', 300.0)
            
            # Get thickness estimate from catalog product
            product_id = layer.get('product_id')
            if product_id:
                catalog = manager.get_textile_catalog()
                product = catalog[catalog['product_id'] == product_id].iloc[0]
                roving_tex = product['roving_tex']
            else:
                roving_tex = 800  # default
            
            thickness = roving_tex / 1000.0  # Approximate
            rect = plt.Rectangle((-width/2, z - thickness/2), width, thickness, 
                                color='green', alpha=0.6)
            ax.add_patch(rect)
        
        else:  # Area
            # Plot as rectangular strip
            z = layer['z']
            A_s = layer['A_s']
            # Approximate width from area
            width = st.session_state.cs_shape_params.get('b', 300.0) * 0.8
            thickness = A_s / width
            rect = plt.Rectangle((-width/2, z - thickness/2), width, thickness, 
                                color='orange', alpha=0.6)
            ax.add_patch(rect)
    
    # Formatting
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.set_xlabel('Width [mm]')
    ax.set_ylabel('Height [mm]')
    ax.set_title('Reinforcement Layout')
    
    # Set limits
    ax.set_xlim(shape.get_plot_xlim())
    ax.set_ylim(shape.get_plot_ylim())
    
    return fig


def render_cross_section_view():
    """Render the Cross-Section definition view"""
    
    # Initialize state
    initialize_cross_section_state()
    
    # Custom CSS for consistent font sizing (matching components_view)
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
    
    st.header("Cross-Section Definition")
    
    # Sub-tabs for Concrete Section, Reinforcement, and Complete View
    subtab1, subtab2, subtab3 = st.tabs(["🏗️ Concrete Section", "⚡ Reinforcement Layout", "📊 Complete Cross-Section"])
    
    # --- CONCRETE SECTION SUBTAB ---
    with subtab1:
        col_params, col_plot = st.columns([1, 1])
        
        with col_params:
            # Geometry first
            shape_type = st.selectbox(
                "Cross-Section Shape",
                ["Rectangular", "T-Section", "I-Section"],
                key='cs_shape_type_select'
            )
            st.session_state.cs_shape_params['type'] = shape_type
            
            st.markdown("---")
            
            if shape_type == "Rectangular":
                st.session_state.cs_shape_params['b'] = st.number_input(
                    "Width b [mm]", 100.0, 2000.0, 
                    st.session_state.cs_shape_params.get('b', 300.0), 10.0
                )
                st.session_state.cs_shape_params['h'] = st.number_input(
                    "Height h [mm]", 100.0, 3000.0,
                    st.session_state.cs_shape_params.get('h', 500.0), 10.0
                )
                
            elif shape_type == "T-Section":
                st.session_state.cs_shape_params['b_f'] = st.number_input(
                    "Flange width b_f [mm]", 100.0, 3000.0, 
                    st.session_state.cs_shape_params.get('b_f', 600.0), 10.0
                )
                st.session_state.cs_shape_params['h_f'] = st.number_input(
                    "Flange height h_f [mm]", 50.0, 500.0, 
                    st.session_state.cs_shape_params.get('h_f', 150.0), 10.0
                )
                st.session_state.cs_shape_params['b_w'] = st.number_input(
                    "Web width b_w [mm]", 100.0, 1000.0, 
                    st.session_state.cs_shape_params.get('b_w', 200.0), 10.0
                )
                st.session_state.cs_shape_params['h_w'] = st.number_input(
                    "Web height h_w [mm]", 200.0, 2000.0, 
                    st.session_state.cs_shape_params.get('h_w', 400.0), 10.0
                )
            
            else:  # I-Section
                st.session_state.cs_shape_params['b_f'] = st.number_input(
                    "Flange width b_f [mm]", 100.0, 2000.0, 
                    st.session_state.cs_shape_params.get('b_f', 400.0), 10.0
                )
                st.session_state.cs_shape_params['h_f'] = st.number_input(
                    "Flange height h_f [mm]", 50.0, 300.0, 
                    st.session_state.cs_shape_params.get('h_f', 100.0), 10.0
                )
                st.session_state.cs_shape_params['b_w'] = st.number_input(
                    "Web width b_w [mm]", 50.0, 800.0, 
                    st.session_state.cs_shape_params.get('b_w', 150.0), 10.0
                )
                st.session_state.cs_shape_params['h_w'] = st.number_input(
                    "Web height h_w [mm]", 100.0, 1500.0, 
                    st.session_state.cs_shape_params.get('h_w', 300.0), 10.0
                )
            
            st.markdown("---")
            
            # Concrete material selection
            from scite.cs_components import get_catalog_manager
            from scite.matmod.ec2_parabola_rectangle import \
                EC2ParabolaRectangle
            
            catalog_manager = get_catalog_manager()
            concrete_catalog = catalog_manager.get_concrete_catalog()
            
            # Default to C25/30
            default_idx = concrete_catalog.index[concrete_catalog['strength_class'] == 'C25/30'].tolist()
            default_idx = default_idx[0] if default_idx else 0
            
            grade = st.selectbox(
                "Concrete Grade",
                concrete_catalog['strength_class'].tolist(),
                index=default_idx,
                key='cs_concrete_grade'
            )
            
            # Get concrete properties
            selected_row = concrete_catalog[concrete_catalog['strength_class'] == grade].iloc[0]
            concrete = EC2ParabolaRectangle(
                f_ck=float(selected_row['f_ck']),
                alpha_cc=1.0,
                gamma_c=1.5
            )
            
            # Display properties in colored frame
            st.markdown(f"""
            <div style="background-color: #E3F2FD; padding: 1rem; border-radius: 5px; border-left: 5px solid #1976D2;">
                <h4 style="margin-top: 0;">Material Properties</h4>
                <p><b>f<sub>ck</sub></b>: {selected_row['f_ck']:.1f} MPa</p>
                <p><b>f<sub>cm</sub></b>: {selected_row['f_cm']:.1f} MPa</p>
                <p><b>E<sub>cm</sub></b>: {selected_row['E_cm']:.0f} MPa</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_plot:
            shape = create_shape_from_params()
            fig = plot_geometry(shape)
            st.pyplot(fig)
            plt.close()
    
    # --- REINFORCEMENT SUBTAB ---
    with subtab2:
        col_params, col_plot = st.columns([1, 1])
        
        with col_params:
            st.subheader("Reinforcement Layers")
            
            # Add layer buttons - three types
            st.markdown("**Add New Layer:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("➕ Bar", use_container_width=True, help="Discrete bars (steel/carbon)"):
                    add_layer('Bar')
                    st.rerun()
            with col2:
                if st.button("➕ Layer", use_container_width=True, help="Textile/mat reinforcement"):
                    add_layer('Layer')
                    st.rerun()
            with col3:
                if st.button("➕ Area", use_container_width=True, help="Area reinforcement"):
                    add_layer('Area')
                    st.rerun()
            
            st.markdown("---")
            
            # Display existing layers
            if len(st.session_state.cs_layers) == 0:
                st.info("No layers added yet. Click 'Add Bar', 'Add Layer', or 'Add Area' to start.")
            else:
                for i, layer in enumerate(st.session_state.cs_layers):
                    # Check if this layer should be expanded
                    is_expanded = (st.session_state.cs_expanded_layer == layer['id'])
                    with st.expander(f"{layer['name']}: {layer['type']} at z={layer['z']:.0f}mm", expanded=is_expanded):
                        # Clear the expanded state after rendering
                        if is_expanded:
                            st.session_state.cs_expanded_layer = None
                        # Common parameters
                        layer['name'] = st.text_input(
                            "Name", layer['name'],
                            key=f"name_{layer['id']}"
                        )
                        layer['z'] = st.number_input(
                            "Position z [mm]", 0.0, 1000.0, layer['z'], 10.0,
                            key=f"z_{layer['id']}"
                        )
                        
                        # Type-specific parameters
                        if layer['type'] == 'Bar':
                            # Catalog selection (steel or carbon)
                            # This determines the material - no separate material selector needed
                            layer['catalog_type'] = st.selectbox(
                                "Catalog", ['steel', 'carbon'],
                                index=0 if layer.get('catalog_type', 'steel') == 'steel' else 1,
                                key=f"catalog_{layer['id']}",
                                help="Material is determined by catalog selection"
                            )
                            
                            # Product selection from the chosen catalog
                            manager = get_catalog_manager_cached()
                            if layer['catalog_type'] == 'steel':
                                catalog = manager.get_steel_catalog()
                            else:  # carbon
                                catalog = manager.get_carbon_catalog()
                            
                            products = catalog['product_id'].tolist()
                            product_names = catalog['name'].tolist()
                            display_options = [f"{name} (ø{catalog.iloc[i]['nominal_diameter']}mm)" 
                                             for i, name in enumerate(product_names)]
                            
                            # Find current selection index
                            current_product = layer.get('product_id')
                            if current_product and current_product in products:
                                current_idx = products.index(current_product)
                            else:
                                current_idx = 0
                            
                            selected_display = st.selectbox(
                                "Product",
                                display_options,
                                index=current_idx,
                                key=f"product_{layer['id']}",
                                help="Material model comes from selected product"
                            )
                            layer['product_id'] = products[display_options.index(selected_display)]
                            
                            # Count
                            layer['count'] = st.number_input(
                                "Count", 1, 20, layer.get('count', 4), 1,
                                key=f"count_{layer['id']}"
                            )
                            
                            # Show selected product details (including material info)
                            if layer['product_id']:
                                selected_row = catalog[catalog['product_id'] == layer['product_id']].iloc[0]
                                material_info = "Steel" if layer['catalog_type'] == 'steel' else "Carbon FRP"
                                st.info(f"**{material_info}** | "
                                       f"Diameter: {selected_row['nominal_diameter']} mm | "
                                       f"Area: {selected_row['area']:.1f} mm² | "
                                       f"Total: {selected_row['area'] * layer['count']:.1f} mm²")
                            
                        elif layer['type'] == 'Layer':
                            # Product selection from textile catalog
                            manager = get_catalog_manager_cached()
                            catalog = manager.get_textile_catalog()
                            products = catalog['product_id'].tolist()
                            product_names = catalog['name'].tolist()
                            display_options = [f"{pid}: {name}" for pid, name in zip(products, product_names)]
                            
                            # Find current selection index
                            current_product = layer.get('product_id')
                            if current_product and current_product in products:
                                current_idx = products.index(current_product)
                            else:
                                current_idx = 0
                            
                            selected_display = st.selectbox(
                                "Product",
                                display_options,
                                index=current_idx,
                                key=f"product_{layer['id']}"
                            )
                            layer['product_id'] = products[display_options.index(selected_display)]
                            
                            # Width
                            layer['width'] = st.number_input(
                                "Width [mm]", 50.0, 500.0, layer.get('width', 300.0), 10.0,
                                key=f"width_{layer['id']}"
                            )
                            
                            # Show selected product details
                            if layer['product_id']:
                                selected_row = catalog[catalog['product_id'] == layer['product_id']].iloc[0]
                                area_per_width = selected_row.get('area_per_width', 0)
                                total_area = area_per_width * layer['width'] if area_per_width > 0 else 0
                                st.info(f"Material: {selected_row['material_type']} | "
                                       f"Area/width: {area_per_width:.2f} mm²/mm | "
                                       f"Total: {total_area:.1f} mm²")
                            
                        else:  # Area
                            layer['A_s'] = st.number_input(
                                "Area A_s [mm²]", 100.0, 10000.0, layer.get('A_s', 1000.0), 50.0,
                                key=f"area_{layer['id']}"
                            )
                            layer['material_type'] = st.selectbox(
                                "Material Type", ['steel', 'carbon'],
                                index=0 if layer.get('material_type', 'steel') == 'steel' else 1,
                                key=f"mattype_{layer['id']}"
                            )
                            layer['grade'] = st.selectbox(
                                "Grade",
                                ['B500A', 'B500B', 'B500C'] if layer['material_type'] == 'steel' else ['COMBAR'],
                                index=1 if layer['material_type'] == 'steel' else 0,
                                key=f"grade_{layer['id']}"
                            )
                        
                        if st.button("🗑️ Delete", key=f"del_{layer['id']}"):
                            delete_layer(layer['id'])
                            st.rerun()
        
        with col_plot:
            shape = create_shape_from_params()
            fig = plot_reinforcement_layout(shape, st.session_state.cs_layers)
            st.pyplot(fig)
            plt.close()
    
    # --- COMPLETE CROSS-SECTION TAB ---
    with subtab3:
        if len(st.session_state.cs_layers) > 0:
            try:
                shape = create_shape_from_params()
                
                # Build concrete component
                from scite.cs_components import get_concrete_by_class
                concrete = get_concrete_by_class(st.session_state.cs_concrete_selected)
                
                # Build reinforcement from layers using component database
                reinforcement = build_reinforcement_from_layers()
                
                # Create complete cross-section
                cs = CrossSection(
                    shape=shape,
                    concrete=concrete.matmod,
                    reinforcement=reinforcement
                )
                
                # Plot
                col1, col2 = st.columns([2, 1])
                with col1:
                    fig, ax = plt.subplots(figsize=(8, 10))
                    cs.plot_cross_section(ax=ax, show_dimensions=True, show_reinforcement=True)
                    st.pyplot(fig)
                    plt.close()
                
                with col2:
                    st.markdown("### Summary")
                    st.metric("Total Height", f"{cs.h_total:.0f} mm")
                    st.metric("Concrete Area", f"{cs.A_c:,.0f} mm²")
                    st.metric("Reinforcement Area", f"{cs.A_s:.0f} mm²")
                    st.metric("Reinforcement Ratio", f"{cs.reinforcement_ratio:.4f}")
                    
            except Exception as e:
                st.error(f"⚠️ Error building cross-section: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
        else:
            st.info("Add reinforcement layers to see the complete cross-section")

# Standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Cross-Section - SCADT",
        page_icon="📐",
        layout="wide"
    )
    
    render_cross_section_view()
