"""
NM Assessment View
==================

Interactive view for N-M assessment with manual strain control.

User manually adjusts bottom strain (eps_bot) to explore equilibrium
for imposed design loads (N_Ed, M_Ed).

Inherits all visualization from StressStrainProfile - no redundancy.
"""

import matplotlib.pyplot as plt
import streamlit as st

from scite.cs_design import CrossSection
from scite.nm_assess import NMAssessment


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


def get_cross_section_from_state():
    """Build CrossSection from session state (from cross_section_view)"""
    from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
    from scite.streamlit_app.cross_section_view import (
        build_reinforcement_from_layers, create_shape_from_params)
    
    if 'cs_shape_params' not in st.session_state:
        return None
    
    shape = create_shape_from_params()
    
    # Get concrete
    concrete_class = st.session_state.get('cs_concrete_selected', 'C30/37')
    try:
        f_ck = int(concrete_class.split('/')[0][1:])
        concrete = EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=1.0, gamma_c=1.5)
    except:
        concrete = EC2ParabolaRectangle(f_ck=30, alpha_cc=1.0, gamma_c=1.5)
    
    reinforcement = build_reinforcement_from_layers()
    
    return CrossSection(
        shape=shape,
        concrete=concrete,
        reinforcement=reinforcement
    )


def render_nm_assessment_view():
    """Render NM assessment view with interactive strain control"""
    
    st.header("NM Assessment")
    st.markdown("""
    **Normal Force - Moment Assessment**  
    Manually adjust steel strain (ε_s1) to explore equilibrium under combined N-M loading.
    """)
    
    try:
        cs = get_cross_section_from_state()
        
        if cs is None:
            st.warning("⚠️ Please define a cross-section first.")
            return
        
        if len(cs.reinforcement.layers) == 0:
            st.warning("⚠️ No reinforcement defined. Add reinforcement layers first.")
            return
        
        # Find lowest reinforcement layer (index 0 after sorting by z)
        layer_indices_sorted = sorted(range(len(cs.reinforcement.layers)), 
                                     key=lambda i: cs.reinforcement.layers[i].z)
        lowest_layer_idx = layer_indices_sorted[0]  # Lowest z-coordinate
        
        # Check if cross-section has changed - if so, recreate nm_assessment
        current_cs_hash = get_cross_section_hash(cs)
        
        if 'nm_cs_hash' not in st.session_state:
            st.session_state.nm_cs_hash = None
        
        cs_changed = (st.session_state.nm_cs_hash != current_cs_hash)
        
        # Initialize or recreate NM assessment state
        if 'nm_assessment' not in st.session_state or cs_changed:
            # Preserve loads if recreating
            N_Ed_preserved = 0.0
            M_Ed_preserved = 200.0
            eps_s1_preserved = 0.0025
            
            if 'nm_assessment' in st.session_state and cs_changed:
                # Preserve user's load settings when cross-section changes
                N_Ed_preserved = st.session_state.nm_assessment.N_Ed
                M_Ed_preserved = st.session_state.nm_assessment.M_Ed
                if 'nm_eps_s1' in st.session_state:
                    eps_s1_preserved = st.session_state.nm_eps_s1
            
            st.session_state.nm_assessment = NMAssessment(
                cs=cs,
                eps_top=-0.0035,  # EC2 ultimate compressive strain
                eps_bot=0.0025,   # Initial guess
                N_Ed=N_Ed_preserved,
                M_Ed=M_Ed_preserved
            )
            st.session_state.nm_cs_hash = current_cs_hash
            st.session_state.nm_eps_s1 = eps_s1_preserved
            
            if cs_changed:
                st.success("✓ Cross-section updated - NM Assessment refreshed")
        
        # Initialize eps_s1 control if not present
        if 'nm_eps_s1' not in st.session_state:
            st.session_state.nm_eps_s1 = 0.0025  # Initial steel strain (yielding)
        
        # Get assessment from session state
        nm = st.session_state.nm_assessment
        
        # Show cross-section info
        st.info(f"""
        **Cross-Section:** {cs.shape.__class__.__name__} - b={cs.shape.b:.0f}mm × h={cs.h_total:.0f}mm  
        **Concrete:** {cs.concrete.__class__.__name__} - f_ck={cs.concrete.f_ck:.0f} MPa  
        **Reinforcement:** {len(cs.reinforcement.layers)} layer(s)
        """)
        
        # Control section
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Design Loads (Imposed)")
            nm.N_Ed = st.number_input(
                "N_Ed [kN]",
                value=nm.N_Ed,
                step=10.0,
                format="%.1f",
                help="Design axial force (positive = tension, negative = compression)"
            )
            
            nm.M_Ed = st.number_input(
                "M_Ed [kNm]",
                value=nm.M_Ed,
                min_value=0.0,
                step=10.0,
                format="%.1f",
                help="Design bending moment"
            )
        
        with col2:
            st.subheader("Strain Control")
            eps_top_input = st.number_input(
                "ε_top (fixed) [-]",
                value=nm.eps_top,
                min_value=-0.010,
                max_value=0.005,
                step=0.0001,
                format="%.4f",
                help="Top fiber strain (typically concrete ultimate: -0.0035)"
            )
            
            eps_s1_input = st.slider(
                "ε_s1 (adjust) [-]",
                min_value=-0.005,
                max_value=0.020,
                value=st.session_state.nm_eps_s1,
                step=0.0001,
                format="%.4f",
                help="Steel strain at lowest reinforcement layer - adjust to explore equilibrium",
                key="nm_eps_s1_slider"
            )
            
            # Update session state
            st.session_state.nm_eps_s1 = eps_s1_input
            
            # Calculate eps_bot from eps_top and eps_s1 using plane section kinematics
            # This is the same logic as StressStrainProfile.set_state() Mode 4
            z_s = cs.reinforcement.layers[lowest_layer_idx].z
            h = cs.h_total
            kappa_calculated = (eps_s1_input - eps_top_input) / (h - z_s)
            eps_bot_calculated = eps_top_input + kappa_calculated * h
            
            # Update nm state directly - this triggers Streamlit re-render
            nm.eps_top = eps_top_input
            nm.eps_bot = eps_bot_calculated
            
            st.caption(f"**Curvature:** κ = {nm.kappa*1000:.6f} ‰/mm")
        
        # Visualization - REUSE StressStrainProfile.plot_stress_strain_profile()
        st.markdown("---")
        
        # Use profile's built-in plotting - NO REDUNDANCY!
        fig, (ax_strain, ax_stress) = plt.subplots(
            1, 2, figsize=(14, 6),
            gridspec_kw={'width_ratios': [1, 2], 'wspace': 0},
            sharey=True
        )
        
        # Use design strength labels and show N_Ed + M_Ed assessment
        nm.profile.plot_stress_strain_profile(
            ax_strain=ax_strain,
            ax_stress=ax_stress,
            show_resultants=True,
            concrete_label='F_cd',  # Design strength label
            steel_label='F_sd',     # Design strength label
            N_Ed=nm.N_Ed,           # Show external load
            M_Ed=nm.M_Ed,           # For assessment
            show_assessment=True    # Show M_Rd ≥ M_Ed box
        )
        
        st.pyplot(fig, clear_figure=True)
        plt.close()
        
        # Display current state metrics AFTER the plot
        st.markdown("---")
        st.subheader("Current State Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "N_actual",
            f"{nm.N_actual:.2f} kN",
            delta=f"{nm.N_error:+.2f} kN",
            delta_color="inverse",
            help="Axial force at current strain state"
        )
        
        col2.metric(
            "M_actual",
            f"{nm.M_actual:.2f} kNm",
            delta=f"{nm.M_error:+.2f} kNm",
            delta_color="normal",
            help="Moment at current strain state"
        )
        
        col3.metric(
            "Utilization",
            f"{nm.utilization:.3f}",
            help="M_Ed / M_actual (should be ≤ 1.0)"
        )
        
        col4.metric(
            "Status",
            "✅ SAFE" if nm.is_safe else "⚠️ CHECK",
            help="Equilibrium and capacity check"
        )
        
        # Equilibrium status
        if nm.is_equilibrium:
            if nm.is_safe:
                st.success(f"✅ Equilibrium achieved! Cross-section is SAFE (η = {nm.utilization:.3f})")
            else:
                st.warning(f"⚠️ Equilibrium satisfied, but utilization η = {nm.utilization:.3f} > 1.0")
        else:
            if abs(nm.N_error) > 1.0:
                st.info(f"ℹ️ |ΔN| = {abs(nm.N_error):.2f} kN - adjust ε_bot slider to reduce")
            if nm.M_error < 0:
                st.warning(f"⚠️ M_actual < M_Ed: insufficient moment capacity")
        
        # Detailed info
        with st.expander("📊 Detailed State Information", expanded=False):
            summary = nm.summary()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Strains**")
                st.write(f"- ε_top: {summary['eps_top']*1000:.2f}‰")
                st.write(f"- ε_bot: {summary['eps_bot']*1000:.2f}‰")
                st.write(f"- κ: {summary['kappa']*1000:.6f} ‰/mm")
            
            with col2:
                st.markdown("**Forces**")
                F_c, F_s, _, _ = nm.get_forces()
                st.write(f"- F_concrete: {F_c/1000:.2f} kN")
                st.write(f"- F_steel: {F_s/1000:.2f} kN")
                st.write(f"- N_total: {summary['N_actual']:.2f} kN")
            
            with col3:
                st.markdown("**Equilibrium**")
                st.write(f"- ΔN: {summary['N_error']:+.2f} kN")
                st.write(f"- ΔM: {summary['M_error']:+.2f} kNm")
                st.write(f"- η: {summary['utilization']:.3f}")
            
            st.markdown("**Cross-Section**")
            st.write(f"- Width: {summary['b']:.0f} mm")
            st.write(f"- Height: {summary['h']:.0f} mm")
            st.write(f"- Concrete: C{summary['f_ck']:.0f}")
            st.write(f"- Layers: {len(cs.reinforcement.layers)}")
    
    except Exception as e:
        st.error(f"⚠️ Error: {str(e)}")
        import traceback
        with st.expander("Details"):
            st.code(traceback.format_exc())


# Standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="NM Assessment - SCITE",
        page_icon="⚖️",
        layout="wide"
    )
    
    st.title("NM Assessment")
    render_nm_assessment_view()
