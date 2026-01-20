"""
M-κ Analysis View
=================

Interactive M-κ (moment-curvature) analysis with state visualization.
Shows the relationship between bending moment and curvature with
corresponding strain and stress distributions.

Can be run standalone for testing:
    streamlit run -m bmcs_cross_section.streamlit_app.mkappa_analysis_view
"""

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from scite.cs_design import CrossSection
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.mkappa.mkappa import MKappaAnalysis
from scite.mkappa.mkappa_state_profiles import MKappaStateProfiles


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
    from scite.cs_components import SteelRebarComponent
    from scite.cs_design import (BarReinforcement, RectangularShape,
                                 ReinforcementLayout)

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
        build_reinforcement_from_layers, create_shape_from_params)

    # Check if cross-section is defined
    if 'cs_shape_params' not in st.session_state:
        return None
    
    shape = create_shape_from_params()
    
    # Get concrete - use design values for standalone mode
    concrete_class = st.session_state.get('cs_concrete_selected', 'C30/37')
    # Extract f_ck from class name (e.g., 'C30/37' -> 30)
    try:
        f_ck = int(concrete_class.split('/')[0][1:])
        concrete = EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=0.85, gamma_c=1.5)
    except:
        concrete = EC2ParabolaRectangle(f_ck=30, alpha_cc=0.85, gamma_c=1.5)  # Default to C30/37
    
    reinforcement = build_reinforcement_from_layers()
    
    return CrossSection(
        shape=shape,
        concrete=concrete,
        reinforcement=reinforcement
    )


def render_mkappa_analysis_view():
    """Render M-κ analysis with interactive state profiles"""
    
    # Initialize and get cross-section
    initialize_default_cross_section()
    
    try:
        cs = get_cross_section_from_state()
        
        if cs is None:
            st.warning("⚠️ Please define a cross-section first.")
            return
        
        if len(cs.reinforcement.layers) == 0:
            st.info("ℹ️ No reinforcement layers defined.")
        
        # Initialize solver parameters if not in session
        if 'mkappa_n_points' not in st.session_state:
            st.session_state.mkappa_n_points = 100
        if 'mkappa_N_tol' not in st.session_state:
            st.session_state.mkappa_N_tol = 0.01
        
        # Initialize change tracking flags
        if 'mkappa_params_changed' not in st.session_state:
            st.session_state.mkappa_params_changed = False
        if 'cs_design_changed' not in st.session_state:
            st.session_state.cs_design_changed = False
        if 'matmod_changed' not in st.session_state:
            st.session_state.matmod_changed = False
        
        # Initialize mkappa_solved flag
        if 'mkappa_solved' not in st.session_state:
            st.session_state.mkappa_solved = False
        
        # Check for parameter changes from widgets (they update on rerun)
        # Widget keys will have new values if user changed them
        if st.session_state.mkappa_solved:
            if 'mkappa_n_points_slider' in st.session_state:
                new_n_points = st.session_state.mkappa_n_points_slider
                if new_n_points != st.session_state.mkappa_n_points:
                    st.session_state.mkappa_params_changed = True
                    st.session_state.mkappa_n_points = new_n_points
            
            if 'mkappa_N_tol_input' in st.session_state:
                new_N_tol = st.session_state.mkappa_N_tol_input
                if abs(new_N_tol - st.session_state.mkappa_N_tol) > 1e-6:
                    st.session_state.mkappa_params_changed = True
                    st.session_state.mkappa_N_tol = new_N_tol
        
        # Check if cross-section has changed
        current_cs_hash = get_cross_section_hash(cs)
        
        if 'mkappa_cs_hash' not in st.session_state:
            st.session_state.mkappa_cs_hash = None
        
        if st.session_state.mkappa_cs_hash != current_cs_hash:
            # Mark cross-section/material as changed
            if st.session_state.mkappa_solved:
                st.session_state.cs_design_changed = True
                st.session_state.matmod_changed = True
        
        # Auto-solve on first view (when mkappa_solved is False and nothing solved yet)
        auto_solve = not st.session_state.mkappa_solved and 'mkappa' not in st.session_state
        
        # Determine if recalculation is needed
        needs_recalculation = (st.session_state.mkappa_params_changed or 
                              st.session_state.cs_design_changed or 
                              st.session_state.matmod_changed or 
                              not st.session_state.mkappa_solved)
        
        # Build change message
        change_reasons = []
        if st.session_state.mkappa_params_changed:
            change_reasons.append("Analysis Parameters")
        if st.session_state.cs_design_changed:
            change_reasons.append("Cross-Section Design")
        if st.session_state.matmod_changed:
            change_reasons.append("Material Models")
        
        # Solve button at top
        if needs_recalculation:
            if change_reasons:
                button_label = f"⚠️ Recalculate ({', '.join(change_reasons)} Changed)"
            else:
                button_label = "🔄 Solve M-κ Analysis"
            button_disabled = False
            button_type = "primary"
        else:
            button_label = "✓ Up to Date"
            button_disabled = True
            button_type = "secondary"
        
        solve_button = st.button(button_label, type=button_type, use_container_width=True, disabled=button_disabled)
        
        if solve_button or auto_solve:
            with st.spinner("Solving M-κ relationship..."):
                mkappa = MKappaAnalysis(
                    cs=cs, 
                    n_kappa=st.session_state.mkappa_n_points, 
                    N_tol=st.session_state.mkappa_N_tol
                )
                mkappa.solve()
                st.session_state.mkappa = mkappa
                st.session_state.mkappa_solved = True
                st.session_state.mkappa_cs_hash = current_cs_hash
                # Reset all change flags
                st.session_state.mkappa_params_changed = False
                st.session_state.cs_design_changed = False
                st.session_state.matmod_changed = False
                # Clear old state when new solution computed
                if 'mkappa_state' in st.session_state:
                    del st.session_state.mkappa_state
                if not auto_solve:
                    st.success(f"✓ Solved {len(mkappa.kappa_values)} points")
                st.rerun()
        
        if 'mkappa_solved' in st.session_state and st.session_state.mkappa_solved:
            mkappa = st.session_state.mkappa
            
            # Show warning if outdated
            if needs_recalculation and st.session_state.mkappa_solved:
                warning_msg = "⚠️ Changes detected: " + ", ".join(change_reasons) + ". Click button above to recalculate."
                st.warning(warning_msg)
            
            # Show M-κ statistics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("M_max", f"{mkappa.M_values.max():.2f} kNm")
            idx_max = np.argmax(mkappa.M_values)
            col2.metric("κ at M_max", f"{mkappa.kappa_values[idx_max]*1000:.4f} ‰/mm")
            col3.metric("Max |N_err|", f"{np.abs(mkappa.N_values).max():.4f} kN")
            col4.metric("Points", len(mkappa.kappa_values))
            
            # Create state profiles if not exists, initialized at peak moment
            if 'mkappa_state' not in st.session_state:
                st.session_state.mkappa_state = MKappaStateProfiles(mkappa=mkappa)
                # Set initial state to peak moment
                st.session_state.mkappa_state.set_kappa(mkappa.kappa_values[idx_max])
            
            mkappa_state = st.session_state.mkappa_state
            
            # Control method selection
            col_method, col_control = st.columns([1, 3])
            
            with col_method:
                st.write("**Scale**")
                control_method = st.selectbox(
                    "Scale selector",
                    ["Percentage", "Curvature", "Point Index"],
                    key='mkappa_control_method',
                    label_visibility="collapsed"
                )
            
            with col_control:
                if control_method == "Percentage":
                    # Calculate percentage at peak moment
                    # Map percentage from solved range (not from zero)
                    kappa_range = mkappa.kappa_values[-1] - mkappa.kappa_values[0]
                    peak_percentage = ((mkappa.kappa_values[idx_max] - mkappa.kappa_values[0]) / kappa_range) * 100.0
                    percentage = st.slider(
                        "Position on curve [%]",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(peak_percentage),
                        step=1.0,
                        format="%.1f%%"
                    )
                    # Map percentage to solved curvature range (from kappa_min to kappa_max)
                    kappa_selected = mkappa.kappa_values[0] + kappa_range * (percentage / 100.0)
                    
                elif control_method == "Curvature":
                    kappa_min = mkappa.kappa_values[0]
                    kappa_max = mkappa.kappa_values[-1]
                    kappa_range_slider = kappa_max - kappa_min
                    # Dynamic step: 1% of range for smooth control (converted to [1/m] scale)
                    kappa_step = (kappa_range_slider * 1000 * 0.01) if kappa_range_slider > 0 else 0.01
                    kappa_selected = st.slider(
                        "Curvature [1/m]",
                        min_value=float(kappa_min*1000),
                        max_value=float(kappa_max*1000),
                        value=float(mkappa_state.kappa*1000),
                        step=float(kappa_step),
                        format="%.3f"
                    ) / 1000.0
                    
                else:  # Point Index
                    point_idx = st.slider(
                        "Point index",
                        min_value=0,
                        max_value=len(mkappa.kappa_values)-1,
                        value=idx_max,
                        step=1
                    )
                    kappa_selected = mkappa.kappa_values[point_idx]
            
            # Update state
            mkappa_state.set_kappa(kappa_selected)
            
            # Plot combined visualization
            fig, ax_strain, ax_stress, ax_mk = mkappa_state.plot_mkappa_state(figsize=(18, 6))
            st.pyplot(fig)
            plt.close()
            
            # Display current state info below figure
            M_current = mkappa_state._get_M_at_kappa(kappa_selected)
            st.info(f"**Current State:** κ = {kappa_selected*1000:.4f} ‰/mm  |  M = {M_current:.2f} kNm")
            
            # Quick navigation buttons
            col1, col2, col3, col4, col5 = st.columns(5)
            
            if col1.button("Start (0%)"):
                st.session_state.mkappa_state.set_kappa(mkappa.kappa_values[0])
                st.rerun()
            
            if col2.button("25%"):
                st.session_state.mkappa_state.set_kappa(mkappa.kappa_values[-1] * 0.25)
                st.rerun()
            
            if col3.button("Peak M"):
                st.session_state.mkappa_state.set_kappa(mkappa.kappa_values[idx_max])
                st.rerun()
            
            if col4.button("75%"):
                st.session_state.mkappa_state.set_kappa(mkappa.kappa_values[-1] * 0.75)
                st.rerun()
            
            if col5.button("End (100%)"):
                st.session_state.mkappa_state.set_kappa(mkappa.kappa_values[-1])
                st.rerun()
        
        # Analysis parameters (always visible, at the bottom)
        st.markdown("---")
        
        with st.expander("⚙️ Analysis Settings", expanded=False):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.slider(
                    "Number of points", 
                    min_value=20, 
                    max_value=200, 
                    value=st.session_state.mkappa_n_points, 
                    step=10,
                    key='mkappa_n_points_slider'
                )
            
            with col2:
                st.number_input(
                    "Force tolerance [kN]", 
                    min_value=0.001, 
                    max_value=1.0, 
                    value=st.session_state.mkappa_N_tol, 
                    step=0.001, 
                    format="%.3f",
                    key='mkappa_N_tol_input'
                )
            
            if st.session_state.mkappa_params_changed:
                st.warning("⚠️ Analysis parameters changed - recalculation needed")
            else:
                st.info("💡 Modify settings to trigger recalculation")
        
        if not ('mkappa_solved' in st.session_state and st.session_state.mkappa_solved):
            st.info("👆 Click 'Solve M-κ Analysis' to start")
    
    except Exception as e:
        st.error(f"⚠️ Error: {str(e)}")
        import traceback
        with st.expander("Details"):
            st.code(traceback.format_exc())


# Standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="M-κ Analysis - SCITE",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("M-κ Analysis")
    render_mkappa_analysis_view()
