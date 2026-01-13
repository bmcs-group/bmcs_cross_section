"""
RC Bending Analysis - Interactive Application
==============================================

This module provides a student-friendly interface for exploring reinforced concrete
bending behavior through interactive widgets.

Author: RC Bending Team
"""

import ipywidgets as widgets
from IPython.display import display
from gdt.concrete.rc_bending_unbalanced_model import RCBendingUnbalancedModel
from gdt.concrete.rc_bending_widget_mn import (
    StressStrainProfileSubWidget,
    LoadingWidget,
    GeometryWidget,
    MaterialsWidget,
    AssessmentResultWidget
)


def create_rc_bending_app():
    """
    Create and display the complete RC bending analysis application.
    
    This function sets up an interactive widget with sections:
    1. Loading (design actions)
    2. Geometry (cross-section dimensions)
    3. Materials (characteristic and design values)
    4. Stress-Strain Visualization (with strain adjustment slider)
    5. Assessment Results (required reinforcement and capacity check)
    
    Returns:
    --------
    tuple
        (model, loading_widget, geometry_widget, materials_widget, assessment_widget, visualization_widget)
    """
    
    # Create unbalanced model with default values
    model = RCBendingUnbalancedModel()
    
    # Set initial design parameters (typical values from lecture examples)
    model.d = 0.45      # Effective depth [m]
    model.b = 0.30      # Width [m]
    model.f_ck = 25     # Concrete characteristic strength [MPa]
    model.f_yk = 500    # Steel characteristic yield strength [MPa]
    model.M_Ed = 0.2    # Design bending moment [MN·m]
    model.N_Ed = -0.05  # Design axial force [MN] (negative = compression)
    
    # Set initial trial strain state
    model.epsilon_c_top = -0.0035      # Compression strain at top
    model.epsilon_s_bottom = 0.0025    # Tension strain at bottom
    # Note: A_s is now calculated from equilibrium (F_sd / sigma_s1)
    
    # Create visualization widget (center)
    viz_widget = StressStrainProfileSubWidget(model)
    
    # Create design widgets (top) - loading, geometry, and materials
    loading_widget = LoadingWidget(model, viz_widget)
    geometry_widget = GeometryWidget(model, viz_widget, loading_widget=loading_widget)
    materials_widget = MaterialsWidget(model, viz_widget)
    assessment_widget = AssessmentResultWidget(model, viz_widget)
    
    # Link assessment widget to visualization widget for slider updates
    viz_widget.set_assessment_widget(assessment_widget)
    
    # Display the complete application with styled headers
    display(widgets.HTML('''
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #2c3e50; margin-bottom: 5px;">Reinforced Concrete Bending Analysis</h1>
            <p style="color: #7f8c8d; font-size: 14px;">
                Interactive tool for exploring stress-strain behavior and equilibrium
            </p>
        </div>
    '''))
    
    display(widgets.HTML('<h3 style="color: #e67e22; border-bottom: 2px solid #e67e22; padding-bottom: 5px;">Loading</h3>'))
    display(loading_widget.layout)
    
    display(widgets.HTML('<h3 style="color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 20px;">Geometry</h3>'))
    display(geometry_widget.layout)
    
    display(widgets.HTML('<h3 style="color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 20px;">Materials</h3>'))
    display(materials_widget.layout)
    
    display(widgets.HTML('<h3 style="color: #27ae60; border-bottom: 2px solid #27ae60; padding-bottom: 5px; margin-top: 25px;">Stress-Strain Profiles</h3>'))
    display(viz_widget.layout)
    
    # Display assessment results last
    display(widgets.HTML('<h3 style="color: #27ae60; border-bottom: 2px solid #27ae60; padding-bottom: 5px; margin-top: 25px;">Assessment Result</h3>'))
    display(assessment_widget.layout)
    
    display(widgets.HTML('''
        <div style="margin-top: 30px; padding: 15px; background-color: #ecf0f1; border-radius: 5px;">
            <h4 style="color: #2c3e50; margin-top: 0;">How to Use This Tool:</h4>
            <ol style="color: #34495e; line-height: 1.8;">
                <li><strong>Loading:</strong> Set design actions (M_Ed, N_Ed)</li>
                <li><strong>Geometry:</strong> Set cross-section dimensions (d, b, c_nom)</li>
                <li><strong>Materials:</strong> Choose material strengths and observe design values with safety factors</li>
                <li><strong>Stress-Strain Profiles:</strong> Adjust bottom strain (ε_s,bottom) using slider to explore different strain states</li>
                <li><strong>Assessment Result:</strong> Review required reinforcement, capacity check, and equilibrium state variables</li>
            </ol>
            <p style="color: #7f8c8d; font-size: 12px; margin-bottom: 0;">
                <strong>Tip:</strong> The top strain (ε_c,top) is fixed at the ultimate concrete strain (-3.5‰)
            </p>
        </div>
    '''))
    
    return model, loading_widget, geometry_widget, materials_widget, assessment_widget, viz_widget


def create_balanced_model_app():
    """
    Create a simplified app for balanced (automatic equilibrium) model.
    
    This version only shows design parameters and visualization,
    as equilibrium is calculated automatically.
    
    Returns:
    --------
    tuple
        (model, design_widget, visualization_widget)
    """
    from gdt.concrete.rc_bending_model_mn import RCBendingModelMN
    from gdt.concrete.rc_bending_widget_mn import DesignWidget
    
    # Create balanced model with default values
    model = RCBendingModelMN()
    
    # Set initial design parameters
    model.d = 0.45      # Effective depth [m]
    model.b = 0.30      # Width [m]
    model.f_ck = 25     # Concrete characteristic strength [MPa]
    model.f_yk = 500    # Steel characteristic yield strength [MPa]
    model.M_Ed = 0.2    # Design bending moment [MN·m]
    model.N_Ed = 0.0    # Design axial force [MN]
    
    # Create visualization widget
    viz_widget = StressStrainProfileSubWidget(model)
    
    # Create design widget with loading parameters
    design_widget = DesignWidget(model, viz_widget, include_loading=True)
    
    # Display the complete application
    display(widgets.HTML('''
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #2c3e50; margin-bottom: 5px;">RC Bending Analysis (Balanced Model)</h1>
            <p style="color: #7f8c8d; font-size: 14px;">
                Automatic equilibrium calculation - adjust parameters and observe results
            </p>
        </div>
    '''))
    
    display(widgets.HTML('<h3 style="color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 5px;">Design Parameters</h3>'))
    display(design_widget.layout)
    
    display(widgets.HTML('<h3 style="color: #27ae60; border-bottom: 2px solid #27ae60; padding-bottom: 5px; margin-top: 25px;">Stress-Strain Profiles</h3>'))
    display(viz_widget.output)
    
    display(widgets.HTML('''
        <div style="margin-top: 30px; padding: 15px; background-color: #e8f5e9; border-radius: 5px;">
            <h4 style="color: #2c3e50; margin-top: 0;">About This Tool:</h4>
            <p style="color: #34495e; line-height: 1.8;">
                This version uses a <strong>balanced model</strong> that automatically calculates
                the required reinforcement and equilibrium state based on your input parameters.
                Simply adjust the sliders to explore different design scenarios!
            </p>
        </div>
    '''))
    
    return model, design_widget, viz_widget
