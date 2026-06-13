"""
UI adapters for Jupyter notebooks and Streamlit.
"""

# Import base classes first
from scite.core.ui.base import (
    UIMetadata,
    UIAdapter,
    ui_field,
    get_ui_metadata,
    get_all_ui_fields,
    interactive,
)

# Then import framework-specific adapters
from scite.core.ui.jupyter import (
    JupyterAdapter,
    create_interactive_plot,
    create_widget,
)

from scite.core.ui.streamlit import (
    StreamlitAdapter,
    StreamlitApp,
)

__all__ = [
    'UIMetadata',
    'UIAdapter',
    'ui_field',
    'get_ui_metadata',
    'get_all_ui_fields',
    'interactive',
    'JupyterAdapter',
    'create_interactive_plot',
    'create_widget',
    'StreamlitAdapter',
    'StreamlitApp',
]
