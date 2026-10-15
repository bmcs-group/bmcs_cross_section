"""
Steel Reinforcement Model - Streamlit Web Application

Run with:
    streamlit run steel_reinforcement_streamlit_app.py

Or from the terminal:
    cd notebooks/dev
    streamlit run steel_reinforcement_streamlit_app.py
"""

import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from bmcs_cross_section.matmod.steel_reinforcement import SteelReinforcement, create_steel


# Page configuration
st.set_page_config(
    page_title="Steel Reinforcement Model",
    page_icon="🔩",
    layout="wide",
    initial_sidebar_state="expanded"
)


def main():
    """Main application"""
    
    # Title and description
    st.title("🔩 Steel Reinforcement Material Model")
    st.markdown("""
    Interactive web application for exploring **steel reinforcement constitutive behavior**.
    
    - Adjust parameters in the sidebar to see real-time updates
    - Bilinear elastic-plastic model with strain hardening
    - Based on European steel grades (EN 10080)
    - Uses modern `BMCSModel` architecture with Pydantic validation
    """)
    
    # Sidebar controls
    with st.sidebar:
        st.header("Model Parameters")
        
        # Steel grade selector
        st.markdown("### Steel Grade")
        
        use_predefined = st.checkbox("Use predefined grade", value=True)
        
        if use_predefined:
            grade = st.selectbox(
                "European Steel Grade (EN 10080)",
                options=['B500A', 'B500B', 'B500C', 'B600A', 'B600B'],
                index=1,  # Default to B500B
                help="Select standard European steel grade"
            )
            
            factor = st.slider(
                "Safety Factor γ_s",
                min_value=0.5,
                max_value=1.5,
                value=1.0,
                step=0.05,
                help="Mean: 1.0, Characteristic: 1/1.15, Design: 1/1.50"
            )
            
            # Create model from grade
            if 'steel_model' not in st.session_state or \
               st.session_state.get('last_grade') != grade or \
               st.session_state.get('last_factor') != factor:
                st.session_state.steel_model = create_steel(grade, factor=factor)
                st.session_state.last_grade = grade
                st.session_state.last_factor = factor
            
            model = st.session_state.steel_model
            
            # Display grade properties
            st.markdown("### Grade Properties")
            st.info(f"""
            **{grade}**
            - f_sy = {model.f_sy:.0f} MPa
            - f_st = {model.f_st:.0f} MPa
            - k = {model.ductility_ratio:.3f}
            - ε_ud = {model.eps_ud:.3f}
            """)
            
        else:
            st.markdown("### Custom Parameters")
            
            # Create model with custom parameters
            if 'steel_model' not in st.session_state:
                st.session_state.steel_model = SteelReinforcement()
            
            model = st.session_state.steel_model
            
            E_s = st.slider(
                "Young's Modulus E_s [MPa]",
                min_value=150000.0,
                max_value=250000.0,
                value=float(model.E_s),
                step=1000.0,
                help="Elastic modulus of steel"
            )
            
            f_sy = st.slider(
                "Yield Strength f_sy [MPa]",
                min_value=300.0,
                max_value=700.0,
                value=float(model.f_sy),
                step=10.0,
                help="Yield strength of steel"
            )
            
            f_st = st.slider(
                "Ultimate Strength f_st [MPa]",
                min_value=400.0,
                max_value=800.0,
                value=float(model.f_st),
                step=10.0,
                help="Ultimate tensile strength (f_st ≥ f_sy)"
            )
            
            eps_ud = st.slider(
                "Ultimate Strain ε_ud [-]",
                min_value=0.01,
                max_value=0.15,
                value=float(model.eps_ud),
                step=0.005,
                help="Strain at ultimate stress"
            )
            
            factor = st.slider(
                "Stress Factor [-]",
                min_value=0.5,
                max_value=1.5,
                value=float(model.factor),
                step=0.05,
                help="Global stress scaling factor"
            )
            
            # Update model
            model.update_params(E_s=E_s, f_sy=f_sy, f_st=f_st, eps_ud=eps_ud, factor=factor)
        
        st.markdown("---")
        st.markdown("### Derived Properties")
        st.metric("ε_sy [-]", f"{model.eps_sy:.6f}", help="Yield strain")
        st.metric("E_s [MPa]", f"{model.E_s:.0f}", help="Young's modulus")
        st.metric("k [-]", f"{model.ductility_ratio:.3f}", help="Ductility ratio f_st/f_sy")
        st.metric("f_sy,scaled [MPa]", f"{model.f_sy_scaled:.1f}", help="Scaled yield strength")
        st.metric("f_st,scaled [MPa]", f"{model.f_st_scaled:.1f}", help="Scaled ultimate strength")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Stress-Strain Curve")
        
        # Create plot
        fig, ax = plt.subplots(figsize=(12, 7))
        model.plot_stress_strain(ax, n_points=500)
        
        # Enhance plot
        if use_predefined:
            ax.set_title(f'Steel {grade}: E_s={model.E_s:.0f} MPa, f_sy={model.f_sy:.0f} MPa', 
                        fontsize=14, fontweight='bold')
        else:
            ax.set_title(f'Custom Steel: E_s={model.E_s:.0f} MPa, f_sy={model.f_sy:.0f} MPa', 
                        fontsize=14, fontweight='bold')
        
        st.pyplot(fig)
        plt.close()
    
    with col2:
        st.header("Model Information")
        
        # Ductility class
        st.markdown("### Ductility Class")
        k = model.ductility_ratio
        if k >= 1.15:
            ductility = "Class C (High Ductility)"
            color = "green"
        elif k >= 1.08:
            ductility = "Class B (Medium Ductility)"
            color = "blue"
        elif k >= 1.05:
            ductility = "Class A (Normal Ductility)"
            color = "orange"
        else:
            ductility = "Below Class A"
            color = "red"
        
        st.markdown(f":{color}[**{ductility}**]")
        st.markdown(f"Ductility ratio: k = {k:.3f}")
        
        # Key parameters
        st.markdown("### Key Parameters")
        st.markdown(f"""
        - **E_s**: {model.E_s:.0f} MPa
        - **f_sy**: {model.f_sy:.1f} MPa
        - **f_st**: {model.f_st:.1f} MPa
        - **ε_sy**: {model.eps_sy:.6f}
        - **ε_ud**: {model.eps_ud:.4f}
        - **Factor**: {model.factor:.2f}
        """)
        
        # Safety factor info
        st.markdown("### EC2 Safety Factors")
        if abs(model.factor - 1.0) < 0.01:
            st.success("✅ Mean strength (testing)")
        elif abs(model.factor - 1/1.15) < 0.01:
            st.info("📊 Characteristic strength")
        elif abs(model.factor - 1/1.50) < 0.01:
            st.warning("⚠️ Design strength (ULS)")
        else:
            st.markdown(f"Custom factor: γ_s = {1/model.factor:.3f}")
        
        # Behavior regions
        st.markdown("### Behavior Regions")
        st.markdown(f"""
        1. **Elastic**: |ε| < {model.eps_sy:.6f}
           - Linear: σ = E_s × ε
           - E_s = {model.E_s:.0f} MPa
        
        2. **Hardening**: {model.eps_sy:.6f} < |ε| < {model.eps_ud:.4f}
           - Strain hardening
           - Hardening modulus ≈ {(model.f_st - model.f_sy)/(model.eps_ud - model.eps_sy):.0f} MPa
        
        3. **Softening**: |ε| > {model.eps_ud:.4f}
           - Post-ultimate softening
           - Avoids numerical instabilities
        """)
    
    # Additional plots
    st.header("Detailed Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Elastic-Plastic Behavior", "Tangent Modulus", "Grade Comparison"])
    
    with tab1:
        st.subheader("Elastic-Plastic Regions")
        
        # Generate data
        eps_range = np.linspace(-model.eps_ud*1.1, model.eps_ud*1.1, 500)
        sig_range = model.get_sig(eps_range)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot with shaded regions
        ax.plot(eps_range, sig_range, 'b-', linewidth=2)
        
        # Elastic region
        ax.axvspan(-model.eps_sy, model.eps_sy, alpha=0.2, color='green', label='Elastic')
        # Hardening regions
        ax.axvspan(model.eps_sy, model.eps_ud, alpha=0.2, color='orange', label='Hardening')
        ax.axvspan(-model.eps_ud, -model.eps_sy, alpha=0.2, color='orange')
        
        # Mark key points
        ax.plot([model.eps_sy, -model.eps_sy], [model.f_sy_scaled, -model.f_sy_scaled],
               'ro', markersize=10, label=f'Yield: ε_sy={model.eps_sy:.6f}')
        ax.plot([model.eps_ud, -model.eps_ud], [model.f_st_scaled, -model.f_st_scaled],
               'rs', markersize=10, label=f'Ultimate: ε_ud={model.eps_ud:.4f}')
        
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]', fontsize=12)
        ax.set_ylabel('Stress σ [MPa]', fontsize=12)
        ax.set_title('Elastic-Plastic Behavior with Strain Hardening', fontsize=13)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        st.pyplot(fig)
        plt.close()
        
        st.markdown(f"""
        **Behavior description:**
        - **Green region**: Linear elastic behavior (σ = E_s × ε)
        - **Orange regions**: Strain hardening (plastic deformation)
        - **Yield points** (red circles): Transition to plastic behavior
        - **Ultimate points** (red squares): Maximum stress capacity
        - **Beyond ultimate**: Softening to avoid numerical issues
        """)
    
    with tab2:
        st.subheader("Tangent Modulus Evolution")
        
        # Generate data
        eps_range = np.linspace(-model.eps_ud*1.1, model.eps_ud*1.1, 500)
        sig_range = model.get_sig(eps_range)
        E_t_range = model.get_E_t(eps_range)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Stress-strain
        ax1.plot(eps_range, sig_range, 'b-', linewidth=2)
        ax1.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax1.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax1.set_xlabel('Strain ε [-]', fontsize=12)
        ax1.set_ylabel('Stress σ [MPa]', fontsize=12)
        ax1.set_title('Stress-Strain Curve', fontsize=13)
        ax1.grid(True, alpha=0.3)
        
        # Tangent modulus
        ax2.plot(eps_range, E_t_range, 'g-', linewidth=2)
        ax2.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax2.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax2.axhline(y=model.E_s, color='r', linestyle='--', linewidth=1,
                   label=f'E_s = {model.E_s:.0f} MPa')
        hardening_E = (model.f_st - model.f_sy)/(model.eps_ud - model.eps_sy)
        ax2.axhline(y=hardening_E, color='orange', linestyle='--', linewidth=1,
                   label=f'E_hardening ≈ {hardening_E:.0f} MPa')
        ax2.set_xlabel('Strain ε [-]', fontsize=12)
        ax2.set_ylabel('Tangent Modulus E_t [MPa]', fontsize=12)
        ax2.set_title('Tangent Modulus (dσ/dε)', fontsize=13)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(-model.E_s*0.1, model.E_s*1.3)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        st.markdown(f"""
        **Tangent modulus:**
        - **Elastic region**: E_t = E_s = {model.E_s:.0f} MPa (constant)
        - **Hardening region**: E_t ≈ {hardening_E:.0f} MPa (reduced stiffness)
        - **Softening region**: E_t < 0 (negative stiffness)
        - Computed numerically: E_t = dσ/dε
        """)
    
    with tab3:
        st.subheader("European Steel Grades Comparison")
        
        # Compare all grades
        grades = ['B500A', 'B500B', 'B500C']
        colors = ['blue', 'green', 'red']
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        for grade_name, color in zip(grades, colors):
            grade_model = create_steel(grade_name, factor=model.factor)
            eps = np.linspace(-grade_model.eps_ud*1.1, grade_model.eps_ud*1.1, 500)
            sig = grade_model.get_sig(eps)
            
            linestyle = '-' if (use_predefined and grade == grade_name) else '--'
            linewidth = 2.5 if (use_predefined and grade == grade_name) else 1.5
            
            ax.plot(eps, sig, color=color, linestyle=linestyle, linewidth=linewidth,
                   label=f'{grade_name}: k={grade_model.ductility_ratio:.3f}, ε_ud={grade_model.eps_ud:.3f}')
        
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]', fontsize=12)
        ax.set_ylabel('Stress σ [MPa]', fontsize=12)
        ax.set_title('European Steel Grades (EN 10080)', fontsize=13)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        st.pyplot(fig)
        plt.close()
        
        # Comparison table
        st.markdown("### Grade Specifications")
        
        import pandas as pd
        
        data = {
            'Grade': ['B500A', 'B500B', 'B500C'],
            'f_sy [MPa]': [500, 500, 500],
            'f_st [MPa]': [525, 540, 575],
            'k [-]': [1.05, 1.08, 1.15],
            'ε_ud [%]': [2.5, 5.0, 7.5],
            'Ductility': ['Normal', 'Medium', 'High']
        }
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        st.markdown("""
        **Key differences:**
        - All grades have same E_s and f_sy
        - Higher class → higher ultimate strength f_st
        - Higher class → larger ultimate strain ε_ud
        - Class C: Best for seismic applications
        - Class A: Sufficient for normal structures
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    **About this application:**
    - Built with Streamlit and bmcs_cross_section package
    - Bilinear elastic-plastic model with strain hardening
    - European steel grades based on EN 10080
    - Modern architecture using BMCSModel base class
    - Pydantic validation for parameter constraints
    
    **Controls:**
    - Toggle between predefined grades and custom parameters
    - Use sliders to adjust material properties
    - All plots update automatically in real-time
    - Explore different tabs for detailed analysis
    """)


if __name__ == "__main__":
    main()
