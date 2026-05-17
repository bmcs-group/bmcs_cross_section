"""
Interactive Cross-Section Design Application
============================================

Streamlit app for designing and analyzing reinforced concrete cross-sections.

Run with: streamlit run cross_section_design_app.py
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

from bmcs_cross_section.cs_design import (
    RectangularShape, TShape, IShape,
    ReinforcementLayer, ReinforcementLayout,
    CrossSection,
    create_symmetric_reinforcement
)
from bmcs_cross_section.matmod.ec2_concrete import EC2Concrete
from bmcs_cross_section.matmod.steel_reinforcement import create_steel

# Page configuration
st.set_page_config(
    page_title="Cross-Section Design",
    page_icon="🏗️",
    layout="wide"
)

st.title("🏗️ Reinforced Concrete Cross-Section Design")
st.markdown("""
Design and analyze reinforced concrete cross-sections with different geometries,
materials, and reinforcement layouts. The app computes internal forces (N, M) for
any strain distribution.
""")

# Sidebar for inputs
st.sidebar.header("⚙️ Design Parameters")

# Shape selection
shape_type = st.sidebar.selectbox(
    "Cross-Section Shape",
    ["Rectangular", "T-Section", "I-Section"],
    help="Select the geometric shape of the cross-section"
)

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📐 Geometry", 
    "🔩 Reinforcement", 
    "📊 Analysis", 
    "📋 Summary"
])

# ===========================
# TAB 1: Geometry Definition
# ===========================
with tab1:
    st.header("Cross-Section Geometry")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Dimensions")
        
        if shape_type == "Rectangular":
            b = st.number_input(
                "Width b [mm]",
                min_value=100.0,
                max_value=2000.0,
                value=300.0,
                step=10.0,
                help="Cross-section width"
            )
            h = st.number_input(
                "Height h [mm]",
                min_value=100.0,
                max_value=3000.0,
                value=500.0,
                step=10.0,
                help="Cross-section height"
            )
            shape = RectangularShape(b=b, h=h)
            
        elif shape_type == "T-Section":
            b_f = st.number_input(
                "Flange width b_f [mm]",
                min_value=100.0,
                max_value=3000.0,
                value=600.0,
                step=10.0,
                help="Width of top flange"
            )
            h_f = st.number_input(
                "Flange height h_f [mm]",
                min_value=50.0,
                max_value=500.0,
                value=150.0,
                step=10.0,
                help="Height of top flange"
            )
            b_w = st.number_input(
                "Web width b_w [mm]",
                min_value=100.0,
                max_value=1000.0,
                value=200.0,
                step=10.0,
                help="Width of web"
            )
            h_w = st.number_input(
                "Web height h_w [mm]",
                min_value=100.0,
                max_value=2000.0,
                value=400.0,
                step=10.0,
                help="Height of web"
            )
            shape = TShape(b_f=b_f, h_f=h_f, b_w=b_w, h_w=h_w)
            
        else:  # I-Section
            b_f = st.number_input(
                "Flange width b_f [mm]",
                min_value=100.0,
                max_value=2000.0,
                value=400.0,
                step=10.0,
                help="Width of flanges"
            )
            h_f = st.number_input(
                "Flange height h_f [mm]",
                min_value=50.0,
                max_value=300.0,
                value=100.0,
                step=10.0,
                help="Height of each flange"
            )
            b_w = st.number_input(
                "Web width b_w [mm]",
                min_value=50.0,
                max_value=800.0,
                value=150.0,
                step=10.0,
                help="Width of web"
            )
            h_w = st.number_input(
                "Web height h_w [mm]",
                min_value=100.0,
                max_value=1500.0,
                value=300.0,
                step=10.0,
                help="Height of web (between flanges)"
            )
            shape = IShape(b_f=b_f, h_f=h_f, b_w=b_w, h_w=h_w)
        
        # Geometric properties
        h_display = shape.h_total if hasattr(shape, 'h_total') else shape.h
        st.info(f"""
        **Geometric Properties:**
        - Total height: {h_display:.0f} mm
        - Concrete area: {shape.area:,.0f} mm²
        - Centroid: {shape.centroid_y:.1f} mm from bottom
        - I_y: {shape.I_y:.2e} mm⁴
        """)
    
    with col2:
        st.subheader("Visualization")
        fig, ax = plt.subplots(figsize=(6, 8))
        
        # Use object-oriented plotting via CrossSection
        from bmcs_cross_section.cs_design.reinforcement import ReinforcementLayout
        h_display = shape.h if shape_type == "Rectangular" else shape.h_total
        empty_reinf = ReinforcementLayout()  # Empty reinforcement for geometry display
        # Create default concrete for plotting (not used for calculations in this tab)
        default_concrete = EC2Concrete(f_cm=38.0)
        cs = CrossSection(shape=shape, concrete=default_concrete, reinforcement=empty_reinf)
        cs.plot_cross_section(ax=ax, show_dimensions=False, show_reinforcement=False)
        
        # Mark centroid on centered plot
        xlim = ax.get_xlim()
        ax.plot(xlim, [shape.centroid_y, shape.centroid_y], 
               'g--', linewidth=1, alpha=0.5, label='Centroid')
        
        ax.set_title(f'{shape_type} (Horizontally Centered)')
        ax.legend()
        
        st.pyplot(fig)
        plt.close()

# ===========================
# TAB 2: Reinforcement
# ===========================
with tab2:
    st.header("Reinforcement Layout")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Material Properties")
        
        # Concrete
        st.markdown("**Concrete:**")
        f_cm = st.number_input(
            "Mean compressive strength f_cm [MPa]",
            min_value=20.0,
            max_value=90.0,
            value=38.0,
            step=1.0,
            help="Mean cylindrical compressive strength (f_cm = f_ck + 8 MPa)"
        )
        concrete = EC2Concrete(f_cm=f_cm)
        st.info(f"f_ck = {concrete.f_ck:.1f} MPa | E_cm = {concrete.E_cm:.0f} MPa")
        
        # Steel
        st.markdown("**Reinforcement Steel:**")
        steel_grade = st.selectbox(
            "Steel grade",
            ["B500A", "B500B", "B500C"],
            index=1,
            help="Steel grade according to EC2"
        )
        steel = create_steel(steel_grade)
        st.info(f"f_yk = {steel.f_sy:.0f} MPa | E_s = {steel.E_s:.0f} MPa")
        
        st.markdown("---")
        st.subheader("Reinforcement Layers")
        
        # Symmetric reinforcement option
        use_symmetric = st.checkbox("Use symmetric reinforcement", value=True)
        
        if use_symmetric:
            cover = st.number_input(
                "Concrete cover [mm]",
                min_value=20.0,
                max_value=100.0,
                value=50.0,
                step=5.0,
                help="Distance from surface to reinforcement center"
            )
            A_s_top = st.number_input(
                "Top steel area A_s,top [mm²]",
                min_value=0.0,
                max_value=10000.0,
                value=402.0,
                step=50.0,
                help="Total steel area in top layer (e.g., 2Ø16 = 402 mm²)"
            )
            A_s_bottom = st.number_input(
                "Bottom steel area A_s,bottom [mm²]",
                min_value=0.0,
                max_value=10000.0,
                value=603.0,
                step=50.0,
                help="Total steel area in bottom layer (e.g., 3Ø16 = 603 mm²)"
            )
            
            h_total = shape.h_total if hasattr(shape, 'h_total') else shape.h
            reinf = create_symmetric_reinforcement(
                h=h_total,
                cover=cover,
                A_s_top=A_s_top,
                A_s_bottom=A_s_bottom,
                material_top=steel,
                material_bottom=steel
            )
        else:
            st.info("Custom layer input not yet implemented. Use symmetric for now.")
            cover = 50.0
            A_s_top = 402.0
            A_s_bottom = 603.0
            h_total = shape.h_total if hasattr(shape, 'h_total') else shape.h
            reinf = create_symmetric_reinforcement(
                h=h_total,
                cover=cover,
                A_s_top=A_s_top,
                A_s_bottom=A_s_bottom,
                material_top=steel,
                material_bottom=steel
            )
    
    with col2:
        st.subheader("Cross-Section with Reinforcement")
        
        # Create cross-section
        cs = CrossSection(
            shape=shape,
            concrete=concrete,
            reinforcement=reinf
        )
        
        # Plot
        fig, ax = plt.subplots(figsize=(6, 8))
        cs.plot_cross_section(ax=ax, show_dimensions=True, show_reinforcement=True)
        st.pyplot(fig)
        plt.close()
        
        # Summary
        st.info(f"""
        **Reinforcement Summary:**
        - Number of layers: {cs.reinforcement.n_layers}
        - Total steel area: {cs.A_s:.0f} mm²
        - Reinforcement ratio: ρ = {cs.reinforcement_ratio:.4f}
        - Mechanical ratio: ω = {cs.reinforcement_ratio * steel.f_sy / concrete.f_ck:.4f}
        """)

# ===========================
# TAB 3: Analysis
# ===========================
with tab3:
    st.header("Strain Distribution Analysis")
    
    st.markdown("""
    Analyze the cross-section for a given strain distribution defined by:
    - **Curvature κ**: Rate of strain change with height
    - **Bottom strain ε_bottom**: Strain at bottom fiber (y=0)
    
    The strain at any height y is: **ε(y) = ε_bottom - κ×y**
    """)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Strain State")
        
        # Curvature
        kappa = st.number_input(
            "Curvature κ [1/mm]",
            min_value=-0.0001,
            max_value=0.0001,
            value=0.00002,
            step=0.000001,
            format="%.6f",
            help="Positive κ → compression at top, tension at bottom"
        )
        
        # Top strain (user-friendly input)
        eps_top_desired = st.number_input(
            "Desired top strain ε_top [-]",
            min_value=-0.01,
            max_value=0.01,
            value=-0.002,
            step=0.0001,
            format="%.6f",
            help="Negative = compression, Positive = tension"
        )
        
        # Convert to eps_bottom
        eps_bottom = eps_top_desired + kappa * cs.h_total
        
        st.info(f"""
        **Computed values:**
        - ε_bottom = {eps_bottom:.6f}
        - ε_top = {eps_top_desired:.6f}
        - Δε = {kappa * cs.h_total:.6f}
        """)
        
        # Compute forces
        N, M = cs.get_N_M(kappa, eps_bottom)
        
        st.markdown("---")
        st.subheader("Internal Forces")
        
        st.metric("Axial Force N", f"{N/1000:.1f} kN", 
                 help="Negative = compression")
        st.metric("Moment M", f"{M/1e6:.1f} kNm",
                 help="About bottom fiber (y=0)")
        
        # Neutral axis
        if abs(kappa) > 1e-12:
            y_na = -eps_bottom / kappa
            if 0 <= y_na <= cs.h_total:
                st.success(f"✓ Neutral axis at y = {y_na:.1f} mm")
            else:
                st.warning(f"⚠ Neutral axis outside section (y = {y_na:.1f} mm)")
    
    with col2:
        st.subheader("Distributions")
        
        # Create figure with strain and stress distributions
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Strain distribution
        cs.plot_strain_distribution(kappa, eps_bottom, ax=ax1)
        
        # Stress distribution
        cs.plot_stress_distribution(kappa, eps_bottom, ax=ax2)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        # Get stress values
        y_vals, eps_vals, sig_vals = cs.get_stress_distribution(kappa, eps_bottom)
        
        st.markdown("**Key Values:**")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Top stress σ_top", f"{sig_vals[-1]:.2f} MPa")
            st.metric("Bottom stress σ_bottom", f"{sig_vals[0]:.2f} MPa")
        with col_b:
            st.metric("Max compression", f"{np.min(sig_vals):.2f} MPa")
            st.metric("Max tension", f"{np.max(sig_vals):.2f} MPa")

# ===========================
# TAB 4: Summary
# ===========================
with tab4:
    st.header("Complete Cross-Section Summary")
    
    summary = cs.get_summary()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📐 Geometry")
        for key, value in summary['geometry'].items():
            st.text(f"{key}: {value}")
    
    with col2:
        st.subheader("🔨 Concrete")
        for key, value in summary['concrete'].items():
            if isinstance(value, float):
                st.text(f"{key}: {value:.1f} MPa")
            else:
                st.text(f"{key}: {value}")
    
    with col3:
        st.subheader("🔩 Reinforcement")
        for key, value in summary['reinforcement'].items():
            if isinstance(value, float):
                st.text(f"{key}: {value:.2f}")
            else:
                st.text(f"{key}: {value}")
    
    st.markdown("---")
    st.subheader("📊 Combined Visualization")
    
    # Combined plot
    fig = plt.figure(figsize=(18, 6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1])
    
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])
    
    cs.plot_cross_section(ax=ax1, show_dimensions=True, show_reinforcement=True)
    cs.plot_strain_distribution(kappa, eps_bottom, ax=ax2)
    cs.plot_stress_distribution(kappa, eps_bottom, ax=ax3)
    
    fig.suptitle(f'Complete Analysis (κ={kappa*1000:.3f} 1/m, N={N/1000:.1f} kN, M={M/1e6:.1f} kNm)', 
                 fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

# Footer
st.markdown("---")
st.markdown("""
**About this app:**
- Built with the modern `bmcs_cross_section.cs_design` module
- Uses EC2 material models for concrete and steel
- Standard coordinate system: y=0 at bottom, positive upward
- Strain distribution: ε(y) = ε_bottom - κ×y
- Ready for Phase 3 integration with mkappa solver
""")
