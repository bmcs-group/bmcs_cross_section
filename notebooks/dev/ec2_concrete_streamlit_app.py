"""
EC2 Concrete Model - Streamlit Web Application

Run with:
    streamlit run ec2_concrete_streamlit_app.py

Or from the terminal:
    cd notebooks/dev
    streamlit run ec2_concrete_streamlit_app.py
"""

import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from bmcs_cross_section.matmod.ec2_concrete import EC2Concrete
from bmcs_cross_section.core.ui.streamlit import StreamlitAdapter


# Page configuration
st.set_page_config(
    page_title="EC2 Concrete Model",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def main():
    """Main application"""
    
    # Title and description
    st.title("🏗️ EC2 Concrete Material Model")
    st.markdown("""
    Interactive web application for exploring the **Eurocode 2 (EC2) concrete constitutive model**.
    
    - Adjust parameters in the sidebar to see real-time updates
    - Based on EN 1992-1-1:2004 (Eurocode 2)
    - Uses modern `BMCSModel` architecture with Pydantic validation
    """)
    
    # Sidebar controls
    with st.sidebar:
        st.header("Model Parameters")
        
        st.markdown("### Primary Parameters")
        
        # Create concrete model with default values
        if 'concrete_model' not in st.session_state:
            st.session_state.concrete_model = EC2Concrete(f_cm=38.0, mu=0.2, factor=1.0)
        
        model = st.session_state.concrete_model
        
        # Create parameter controls
        f_cm = st.slider(
            "Compressive Strength f_cm [MPa]",
            min_value=20.0,
            max_value=100.0,
            value=float(model.f_cm),
            step=1.0,
            help="Mean compressive strength of concrete"
        )
        
        mu = st.slider(
            "Fiber Effect μ [-]",
            min_value=0.0,
            max_value=1.0,
            value=float(model.mu),
            step=0.05,
            help="Post-crack tensile strength retention (0=plain, 1=full retention)"
        )
        
        factor = st.slider(
            "Stress Factor [-]",
            min_value=0.5,
            max_value=1.5,
            value=float(model.factor),
            step=0.05,
            help="Global stress scaling factor (e.g., safety factor)"
        )
        
        # Update model
        model.update_params(f_cm=f_cm, mu=mu, factor=factor)
        
        st.markdown("---")
        st.markdown("### Derived Properties")
        st.metric("f_ck [MPa]", f"{model.f_ck:.1f}", help="Characteristic compressive strength")
        st.metric("E_cm [MPa]", f"{model.E_cm:.0f}", help="Secant modulus of elasticity")
        st.metric("f_ctm [MPa]", f"{model.f_ctm:.2f}", help="Mean tensile strength")
        st.metric("ε_c1 [-]", f"{model.eps_c1:.4f}", help="Strain at peak stress")
        st.metric("ε_cu1 [-]", f"{model.eps_cu1:.4f}", help="Ultimate compressive strain")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Stress-Strain Curve")
        
        # Create plot
        fig, ax = plt.subplots(figsize=(12, 7))
        model.plot_stress_strain(ax, n_points=500)
        
        # Enhance plot
        ax.set_title(f'EC2 Concrete Model: f_cm={model.f_cm:.1f} MPa, μ={model.mu:.2f}', 
                     fontsize=14, fontweight='bold')
        
        st.pyplot(fig)
        plt.close()
    
    with col2:
        st.header("Model Information")
        
        # Concrete grade estimation
        st.markdown("### Concrete Grade")
        f_ck = model.f_ck
        if f_ck >= 90:
            grade = f"C90/105 (Ultra-High Strength)"
        elif f_ck >= 70:
            grade = f"C70/85 (Very High Strength)"
        elif f_ck >= 50:
            grade = f"C50/60 (High Strength)"
        elif f_ck >= 40:
            grade = f"C40/50 (Medium Strength)"
        elif f_ck >= 30:
            grade = f"C30/37 (Standard)"
        elif f_ck >= 20:
            grade = f"C20/25 (Low Strength)"
        else:
            grade = f"< C20/25"
        
        st.info(f"**Estimated Grade:** {grade}")
        
        # EC2 parameters
        st.markdown("### EC2 Parameters")
        st.markdown(f"""
        - **k**: {model.k:.3f}
        - **ε_c1**: {model.eps_c1:.4f}
        - **ε_cu1**: {model.eps_cu1:.4f}
        - **ε_cr**: {model.eps_cr_computed:.6f}
        - **ε_tu**: {model.eps_tu_computed:.6f}
        """)
        
        # Fiber reinforcement info
        st.markdown("### Fiber Reinforcement")
        if model.mu == 0.0:
            st.warning("⚠️ Plain concrete (no fibers)")
        elif model.mu == 1.0:
            st.success("✅ Full tensile strength retention")
        else:
            st.info(f"📊 {model.mu*100:.0f}% post-crack strength retention")
    
    # Additional plots
    st.header("Detailed Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Compression Branch", "Tension Branch", "Tangent Modulus"])
    
    with tab1:
        st.subheader("Compression Branch Detail")
        
        # Generate compression data
        eps_comp = np.linspace(1.5 * model.eps_cu1, 0, 300)
        sig_comp = model.get_sig(eps_comp)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(eps_comp, sig_comp, 'b-', linewidth=2)
        ax.plot([model.eps_c1], [-model.factor * model.f_cm], 'ro', 
                markersize=10, label=f'Peak: ε={model.eps_c1:.4f}')
        ax.plot([model.eps_cu1], [model.get_sig(np.array([model.eps_cu1]))[0]], 
                'rs', markersize=10, label=f'Ultimate: ε={model.eps_cu1:.4f}')
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]', fontsize=12)
        ax.set_ylabel('Stress σ [MPa]', fontsize=12)
        ax.set_title('EC2 Parabolic-Rectangular Compression Branch', fontsize=13)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        st.pyplot(fig)
        plt.close()
        
        st.markdown(f"""
        **Key Points:**
        - Peak stress occurs at ε_c1 = {model.eps_c1:.4f}
        - Parabolic curve up to peak, then plateau
        - Ultimate strain ε_cu1 = {model.eps_cu1:.4f}
        - Follows EC2 formula: σ = f_cm · [k·η - η²] / [1 + (k-2)·η]
        """)
    
    with tab2:
        st.subheader("Tension Branch and Fiber Effects")
        
        # Compare different mu values
        fig, ax = plt.subplots(figsize=(10, 6))
        
        mu_values = [0.0, 0.3, 0.6, 1.0]
        colors = ['red', 'orange', 'green', 'blue']
        
        for mu_val, color in zip(mu_values, colors):
            temp_model = EC2Concrete(f_cm=model.f_cm, mu=mu_val, factor=model.factor)
            eps_tens = np.linspace(-0.0001, 0.001, 300)
            sig_tens = temp_model.get_sig(eps_tens)
            
            label = f'μ = {mu_val:.1f}'
            if mu_val == 0.0:
                label += ' (no fibers)'
            elif mu_val == 1.0:
                label += ' (full retention)'
            
            linestyle = '-' if mu_val == model.mu else '--'
            linewidth = 2.5 if mu_val == model.mu else 1.5
            
            ax.plot(eps_tens, sig_tens, color=color, linestyle=linestyle, 
                   linewidth=linewidth, label=label)
        
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax.set_xlabel('Strain ε [-]', fontsize=12)
        ax.set_ylabel('Stress σ [MPa]', fontsize=12)
        ax.set_title('Effect of Fiber Reinforcement on Tension Branch', fontsize=13)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        st.pyplot(fig)
        plt.close()
        
        st.markdown(f"""
        **Current Model:** μ = {model.mu:.2f} (shown as solid line)
        
        **Interpretation:**
        - μ = 0.0: Plain concrete, no post-crack strength
        - μ = 1.0: Ideal fiber reinforcement, full strength retention
        - 0 < μ < 1: Partial post-crack strength (realistic FRC)
        """)
    
    with tab3:
        st.subheader("Tangent Modulus Evolution")
        
        # Generate full range data
        eps_min, eps_max = model.get_plot_range()
        eps = np.linspace(eps_min, eps_max, 500)
        sig = model.get_sig(eps)
        E_t = model.get_E_t(eps)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
        
        # Stress-strain
        ax1.plot(eps, sig, 'b-', linewidth=2)
        ax1.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax1.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax1.set_xlabel('Strain ε [-]', fontsize=12)
        ax1.set_ylabel('Stress σ [MPa]', fontsize=12)
        ax1.set_title('Stress-Strain Curve', fontsize=13)
        ax1.grid(True, alpha=0.3)
        
        # Tangent modulus
        ax2.plot(eps, E_t, 'g-', linewidth=2)
        ax2.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax2.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        ax2.axhline(y=model.E_cm, color='r', linestyle='--', linewidth=1,
                   label=f'E_cm = {model.E_cm:.0f} MPa')
        ax2.set_xlabel('Strain ε [-]', fontsize=12)
        ax2.set_ylabel('Tangent Modulus E_t [MPa]', fontsize=12)
        ax2.set_title('Tangent Modulus (Numerical Derivative)', fontsize=13)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        st.markdown(f"""
        **Tangent Modulus:**
        - Initial elastic modulus E_cm = {model.E_cm:.0f} MPa
        - Decreases with increasing compression strain
        - Computed numerically: E_t = dσ/dε
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    **About this application:**
    - Built with Streamlit and bmcs_cross_section package
    - EC2 formulas based on EN 1992-1-1:2004
    - Modern architecture using BMCSModel base class
    - Pydantic validation for parameter constraints
    
    **Controls:**
    - Use sliders in sidebar to adjust parameters
    - All plots update automatically
    - Hover over metrics for descriptions
    """)


if __name__ == "__main__":
    main()
