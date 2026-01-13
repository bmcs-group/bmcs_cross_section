"""
SCITE - Structural Concrete Interactive Teaching Environment
====================================================

Main Streamlit application integrating all workflow steps:
1. Components - Browse material catalogs
2. Cross-Section - Define geometry and reinforcement
3. Bending Analysis - Perform moment-curvature analysis
4. Summary - View complete design documentation

Run with: streamlit run scite_app.py
"""

import streamlit as st
from pathlib import Path

from bmcs_cross_section.streamlit_app import (
    render_components_view,
    render_cross_section_view,
    render_state_profiles_view,
    render_summary_view,
)


def initialize_session_state():
    """Initialize session state variables with default testing cross-section"""
    if 'workflow_step' not in st.session_state:
        st.session_state.workflow_step = 'Components'
    
    # Initialize default cross-section for testing: 300x500mm with 4xD20 at z=50mm
    if 'cs_shape_params' not in st.session_state:
        st.session_state.cs_shape_params = {
            'type': 'Rectangular',
            'b': 300.0,
            'h': 500.0
        }
    
    if 'cs_concrete_selected' not in st.session_state:
        st.session_state.cs_concrete_selected = 'C30/37'
    
    if 'cs_layers' not in st.session_state:
        # Default reinforcement: 4 bars D20 at 50mm from bottom
        st.session_state.cs_layers = [
            {
                'id': 1,
                'type': 'Bar',
                'z': 50.0,  # 50mm from bottom
                'name': 'Bottom reinforcement',
                'catalog_type': 'steel',
                'product_id': 'REBAR-B500B-D20',
                'count': 4
            }
        ]
    
    if 'cs_layer_counter' not in st.session_state:
        st.session_state.cs_layer_counter = 1


def main():
    # Page config
    st.set_page_config(
        page_title="SCITE - Structural Concrete Interative Teaching Environment",
        page_icon="📐",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_session_state()
    
    # Custom CSS for header and sidebar
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
            content: SCITE — Structural Concrete Interative Teaching Environment";
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
            width: calc(var(--sidebar-width, 21rem) - 2rem) !important;
            max-width: calc(var(--sidebar-width, 21rem) - 2rem) !important;
        }
        
        section[data-testid="stSidebar"] [data-testid="stImage"]:last-of-type img {
            max-width: 100% !important;
            height: auto !important;
        }
        
        /* Force sidebar content to top */
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        
        section[data-testid="stSidebar"] .block-container {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            padding-top: 0 !important;
            margin-top: 0 !important;
            gap: 0 !important;
        }
        
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:first-child {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ========================================
    # SIDEBAR - Workflow Navigation
    # ========================================
    
    with st.sidebar:
        # Workflow menu using buttons with matching font styling
        menu_items = ["Components", "Cross-Section", "State Profiles", "M-κ Analysis", "NM-Assessment", "Summary"]
        
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
        
        workflow_step = st.session_state.workflow_step
        
        # Logo at bottom (positioned by CSS)
        st.markdown("---")
        
        # Load and display logo (CSS will position it at bottom)
        logo_path = Path(__file__).parent / "rwth_cscp_bild_rgb.png"
        if logo_path.exists():
            st.image(str(logo_path))
    
    # ========================================
    # MAIN CONTENT - Workflow-based
    # ========================================
    
    # Parse workflow step and render appropriate view
    step_map = {
        "Components": "components",
        "Cross-Section": "cross_section",
        "State Profiles": "state_profiles",
        "M-κ Analysis": "mkappa",
        "NM-Assessment": "nm_assessment",
        "Summary": "summary"
    }
    current_step = step_map[workflow_step]
    
    if current_step == "components":
        render_components_view()
    elif current_step == "cross_section":
        render_cross_section_view()
    elif current_step == "state_profiles":
        render_state_profiles_view()
    elif current_step == "mkappa":
        from bmcs_cross_section.streamlit_app.mkappa_analysis_view import render_mkappa_analysis_view
        render_mkappa_analysis_view()
    elif current_step == "nm_assessment":
        from bmcs_cross_section.streamlit_app.nm_assessment_view import render_nm_assessment_view
        render_nm_assessment_view()
    elif current_step == "summary":
        render_summary_view()


if __name__ == "__main__":
    main()
