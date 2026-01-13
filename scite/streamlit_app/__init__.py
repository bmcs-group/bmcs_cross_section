"""
Streamlit Application for SCADT
================================

Modular Streamlit interface for Structural Concrete Analysis and Design Tool.

Modules:
- components_view: Component catalog browser
- cross_section_view: Cross-section geometry and reinforcement definition
- state_profiles_view: State profiles visualization
- mkappa_analysis_view: Moment-curvature analysis
- summary_view: Design summary and documentation
"""

from .components_view import render_components_view
from .cross_section_view import render_cross_section_view
from .state_profiles_view import render_state_profiles_view
from .summary_view import render_summary_view

__all__ = [
    'render_components_view',
    'render_cross_section_view',
    'render_state_profiles_view',
    'render_summary_view',
]
