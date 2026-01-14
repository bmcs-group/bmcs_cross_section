"""
State Profiles View
==================

Visualize strain and stress distributions with force resultants.
Compact widget for cross-section state analysis.

Can be run standalone for testing:
    streamlit run -m bmcs_cross_section.streamlit_app.bending_analysis_view
"""

import streamlit as st
import matplotlib.pyplot as plt
import numpy as np

from scite.cs_design import CrossSection
from scite.cs_design.cs_stress_strain_profile import StressStrainProfile
from scite.matmod import EC2Concrete


def get_reasonable_ranges():
    """Get reasonable parameter ranges for RC structures"""
    return {
        'kappa': {'min': -0.00005, 'max': 0.00005, 'default': 0.00001, 'step': 0.000001, 'format': '%.6f'},
        'eps_bot': {'min': -0.005, 'max': 0.015, 'default': 0.002, 'step': 0.0001, 'format': '%.4f'},
        'eps_top': {'min': -0.005, 'max': 0.005, 'default': -0.002, 'step': 0.0001, 'format': '%.4f'},
        'eps_s1': {'min': -0.005, 'max': 0.020, 'default': 0.005, 'step': 0.0001, 'format': '%.4f'},
    }


def initialize_bending_state():
    """Initialize session state for state profiles"""
    ranges = get_reasonable_ranges()
    
    if 'sp_control_mode' not in st.session_state:
        st.session_state.sp_control_mode = 'M-κ analysis'
    if 'sp_kappa' not in st.session_state:
        st.session_state.sp_kappa = ranges['kappa']['default']
    if 'sp_eps_bot' not in st.session_state:
        st.session_state.sp_eps_bot = ranges['eps_bot']['default']
    if 'sp_eps_top' not in st.session_state:
        st.session_state.sp_eps_top = ranges['eps_top']['default']
    if 'sp_eps_s1' not in st.session_state:
        st.session_state.sp_eps_s1 = ranges['eps_s1']['default']
    if 'sp_layer_index' not in st.session_state:
        st.session_state.sp_layer_index = 0


def get_cross_section_hash(cs):
    """
    Generate a hash representing the cross-section state.
    Used to detect if cross-section parameters have changed.
    """
    import hashlib
    import json
    
    # Collect all relevant parameters
    cs_data = {
        'shape': {
            'type': cs.shape.__class__.__name__,
            'b': cs.shape.b,
            'h': cs.shape.h if hasattr(cs.shape, 'h') else cs.shape.h_total,
        },
        'concrete': {
            'f_ck': cs.concrete.f_ck,
            'E_ct': cs.concrete.E_ct if hasattr(cs.concrete, 'E_ct') else None,
        },
        'layers': [
            {
                'z': layer.z,
                'A_s': layer.A_s,
                'material': {
                    'f_sy': layer.material.f_sy,
                    'E_s': layer.material.E_s,
                }
            }
            for layer in cs.reinforcement.layers
        ]
    }
    
    # Create JSON string and hash it
    cs_json = json.dumps(cs_data, sort_keys=True)
    return hashlib.md5(cs_json.encode()).hexdigest()


def initialize_default_cross_section():
    """Initialize a default cross-section for standalone testing"""
    from scite.cs_design import (
        RectangularShape, BarReinforcement, ReinforcementLayout
    )
    from scite.cs_components import SteelRebarComponent
    
    # Default rectangular cross-section: b=300mm, h=500mm
    if 'cs_shape_params' not in st.session_state:
        st.session_state.cs_shape_params = {
            'type': 'Rectangular',
            'b': 300.0,
            'h': 500.0
        }
    
    # Default concrete: C30/37
    if 'cs_concrete_selected' not in st.session_state:
        st.session_state.cs_concrete_selected = 'C30/37'
    
    # Default reinforcement: 4 bars D20, cover = 50mm from bottom
    if 'cs_layers' not in st.session_state:
        c_nom = 50.0  # Nominal cover
        h = st.session_state.cs_shape_params['h']
        
        # Bottom layer at 50mm from bottom (z=0 is bottom, z=h is top)
        st.session_state.cs_layers = [
            {
                'id': 1,
                'type': 'Bar',
                'z': c_nom,  # 50mm from bottom
                'name': 'Bottom reinforcement',
                'catalog_type': 'steel',
                'product_id': 'REBAR-B500B-D20',
                'count': 4
            }
        ]


def get_cross_section_from_state():
    """Build CrossSection from session state (from cross_section_view)"""
    # Import here to avoid circular imports
    from scite.streamlit_app.cross_section_view import (
        create_shape_from_params, 
        build_reinforcement_from_layers
    )
    
    # Check if cross-section is defined
    if 'cs_shape_params' not in st.session_state:
        return None
    
    shape = create_shape_from_params()
    
    # Get concrete - use EC2Concrete directly for standalone mode
    concrete_class = st.session_state.get('cs_concrete_selected', 'C30/37')
    # Extract f_ck from class name (e.g., 'C30/37' -> 30)
    try:
        f_ck = int(concrete_class.split('/')[0][1:])
        concrete = EC2Concrete(f_ck=f_ck)
    except:
        concrete = EC2Concrete(f_ck=30)  # Default to C30/37
    
    reinforcement = build_reinforcement_from_layers()
    
    return CrossSection(
        shape=shape,
        concrete=concrete,
        reinforcement=reinforcement
    )


def render_bending_analysis_view():
    """Render the State Profiles view (single state only)"""
    
    initialize_bending_state()
    initialize_default_cross_section()  # For standalone mode
    
    st.header("State Profiles")
    
    render_single_state_profile()


def render_single_state_profile():
    """Render single state profile with control parameters"""
    
    try:
        cs = get_cross_section_from_state()
        
        if cs is None:
            st.warning("⚠️ Please define a cross-section first.")
            return
        
        if len(cs.reinforcement.layers) == 0:
            st.info("ℹ️ No reinforcement layers defined.")
        
        # Compact control parameters - mode selector + parameters in one row
        st.subheader("Control Parameters")
        
        # Get reasonable ranges
        ranges = get_reasonable_ranges()
        
        # Create compact layout: mode selector on left, parameters on right
        col_mode, col_param1, col_param2 = st.columns([1, 2, 2])
        
        with col_mode:
            st.write("**Mode**")
            control_mode = st.selectbox(
                "Mode selector",
                ['M-κ analysis', 'Unbalanced model', 'RC design'],
                key='sp_control_mode',
                label_visibility="collapsed"
            )
        
        with col_param1:
            # Mode-specific inputs with sliders and number inputs
            if control_mode == 'M-κ analysis':
                st.write("**κ [1/mm]**")
                col_k_slider, col_k_input = st.columns([4, 1])
                with col_k_slider:
                    kappa_slider = st.slider(
                        "κ slider",
                        min_value=ranges['kappa']['min'],
                        max_value=ranges['kappa']['max'],
                        value=st.session_state.sp_kappa,
                        step=ranges['kappa']['step'],
                        format=ranges['kappa']['format'],
                        label_visibility="collapsed"
                    )
                with col_k_input:
                    kappa = st.number_input(
                        "κ value",
                        value=kappa_slider,
                        step=ranges['kappa']['step'],
                        format=ranges['kappa']['format'],
                        label_visibility="collapsed"
                    )
                st.session_state.sp_kappa = kappa
                
            elif control_mode == 'Unbalanced model':
                st.write("**ε_top [-]**")
                col_t_slider, col_t_input = st.columns([4, 1])
                with col_t_slider:
                    eps_top_slider = st.slider(
                        "ε_top slider",
                        min_value=ranges['eps_top']['min'],
                        max_value=ranges['eps_top']['max'],
                        value=st.session_state.sp_eps_top,
                        step=ranges['eps_top']['step'],
                        format=ranges['eps_top']['format'],
                        label_visibility="collapsed"
                    )
                with col_t_input:
                    eps_top = st.number_input(
                        "ε_top value",
                        value=eps_top_slider,
                        step=ranges['eps_top']['step'],
                        format=ranges['eps_top']['format'],
                        label_visibility="collapsed"
                    )
                st.session_state.sp_eps_top = eps_top
                
            else:  # RC design
                st.write("**ε_top [-]**")
                col_t_slider, col_t_input = st.columns([4, 1])
                with col_t_slider:
                    eps_top_slider = st.slider(
                        "ε_top slider",
                        min_value=ranges['eps_top']['min'],
                        max_value=ranges['eps_top']['max'],
                        value=st.session_state.sp_eps_top,
                        step=ranges['eps_top']['step'],
                        format=ranges['eps_top']['format'],
                        label_visibility="collapsed"
                    )
                with col_t_input:
                    eps_top = st.number_input(
                        "ε_top value",
                        value=eps_top_slider,
                        step=ranges['eps_top']['step'],
                        format=ranges['eps_top']['format'],
                        label_visibility="collapsed"
                    )
                st.session_state.sp_eps_top = eps_top
        
        with col_param2:
            # Second parameter
            if control_mode == 'M-κ analysis':
                st.write("**ε_bot [-]**")
                col_e_slider, col_e_input = st.columns([4, 1])
                with col_e_slider:
                    eps_bot_slider = st.slider(
                        "ε_bot slider",
                        min_value=ranges['eps_bot']['min'],
                        max_value=ranges['eps_bot']['max'],
                        value=st.session_state.sp_eps_bot,
                        step=ranges['eps_bot']['step'],
                        format=ranges['eps_bot']['format'],
                        label_visibility="collapsed"
                    )
                with col_e_input:
                    eps_bot = st.number_input(
                        "ε_bot value",
                        value=eps_bot_slider,
                        step=ranges['eps_bot']['step'],
                        format=ranges['eps_bot']['format'],
                        label_visibility="collapsed"
                    )
                st.session_state.sp_eps_bot = eps_bot
                
                # Create profile
                profile = StressStrainProfile(cs)
                profile.set_state(kappa=kappa, eps_bot=eps_bot)
                
            elif control_mode == 'Unbalanced model':
                st.write("**ε_bot [-]**")
                col_b_slider, col_b_input = st.columns([4, 1])
                with col_b_slider:
                    eps_bot_slider = st.slider(
                        "ε_bot slider",
                        min_value=ranges['eps_bot']['min'],
                        max_value=ranges['eps_bot']['max'],
                        value=st.session_state.sp_eps_bot,
                        step=ranges['eps_bot']['step'],
                        format=ranges['eps_bot']['format'],
                        label_visibility="collapsed"
                    )
                with col_b_input:
                    eps_bot = st.number_input(
                        "ε_bot value",
                        value=eps_bot_slider,
                        step=ranges['eps_bot']['step'],
                        format=ranges['eps_bot']['format'],
                        label_visibility="collapsed"
                    )
                st.session_state.sp_eps_bot = eps_bot
                
                profile = StressStrainProfile(cs)
                profile.set_state(eps_top=eps_top, eps_bot=eps_bot)
                
            else:  # RC design - always use lowest layer (layer_index=0)
                st.write("**ε_s1 [-]**")
                col_s_slider, col_s_input = st.columns([4, 1])
                with col_s_slider:
                    eps_s1_slider = st.slider(
                        "ε_s1 slider",
                        min_value=ranges['eps_s1']['min'],
                        max_value=ranges['eps_s1']['max'],
                        value=st.session_state.sp_eps_s1,
                        step=ranges['eps_s1']['step'],
                        format=ranges['eps_s1']['format'],
                        label_visibility="collapsed"
                    )
                with col_s_input:
                    eps_s1 = st.number_input(
                        "ε_s1 value",
                        value=eps_s1_slider,
                        step=ranges['eps_s1']['step'],
                        format=ranges['eps_s1']['format'],
                        label_visibility="collapsed"
                    )
                st.session_state.sp_eps_s1 = eps_s1
                
                profile = StressStrainProfile(cs)
                n_layers = len(cs.reinforcement.layers)
                if n_layers > 0:
                    # Always use lowest layer (layer_index=0)
                    profile.set_state(eps_top=eps_top, eps_s1=eps_s1, layer_index=0)
                else:
                    profile.set_state(eps_top=eps_top, eps_bot=0.0)
        
        st.markdown("---")
        
        # Compute forces
        F_c, F_s, N_total, M_total = profile.get_force_resultants()
        
        # Plot
        fig, (ax_strain, ax_stress) = plt.subplots(
            1, 2, figsize=(12, 5), 
            gridspec_kw={'width_ratios': [1, 2], 'wspace': 0},
            sharey=True
        )
        profile.plot_stress_strain_profile(ax_strain, ax_stress, show_resultants=True)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        # Plot options below figure
        st.subheader("Plot Options")
        show_resultants = st.checkbox("Show force arrows", value=True)
        if not show_resultants:
            # Redraw without force arrows
            fig, (ax_strain, ax_stress) = plt.subplots(
                1, 2, figsize=(12, 5), 
                gridspec_kw={'width_ratios': [1, 2], 'wspace': 0},
                sharey=True
            )
            profile.plot_stress_strain_profile(ax_strain, ax_stress, show_resultants=False)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
        
        # Resultants below plot options
        st.subheader("Force Resultants")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("F_c", f"{F_c/1000:.1f} kN")
        col2.metric("F_s", f"{F_s/1000:.1f} kN")
        col3.metric("N", f"{N_total/1000:.1f} kN")
        col4.metric("M", f"{M_total/1e6:.1f} kNm")
        
    except Exception as e:
        st.error(f"⚠️ Error: {str(e)}")
        import traceback
        with st.expander("Details"):
            st.code(traceback.format_exc())


# Standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="State Profiles - SCADT",
        page_icon="📊",
        layout="wide"
    )
    
    render_bending_analysis_view()
