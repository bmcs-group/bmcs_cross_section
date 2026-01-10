"""
Jupyter notebook UI adapter using ipywidgets.
"""

from typing import Any, Callable, Optional
import numpy as np

try:
    import ipywidgets as widgets
    from IPython.display import display
    import matplotlib.pyplot as plt
    JUPYTER_AVAILABLE = True
except ImportError:
    JUPYTER_AVAILABLE = False
    widgets = None
    display = None
    plt = None

from bmcs_cross_section.core.ui.base import UIAdapter, get_ui_metadata, get_all_ui_fields


class JupyterAdapter(UIAdapter):
    """
    Adapter for creating Jupyter widgets from model fields.
    """
    
    def create_widget(self, model: Any, field_name: str) -> Any:
        """
        Create an ipywidget for a model field.
        
        Args:
            model: BMCSModel instance
            field_name: Field name
            
        Returns:
            ipywidget (FloatSlider, FloatText, etc.)
        """
        if not JUPYTER_AVAILABLE:
            raise ImportError("ipywidgets not available. Install with: pip install ipywidgets")
        
        metadata = get_ui_metadata(model, field_name)
        current_value = getattr(model, field_name)
        
        # Handle None values for Optional fields
        if current_value is None:
            # Try to get computed variant (e.g., E_cc -> E_cc_computed)
            computed_attr = f"{field_name}_computed"
            if hasattr(model, computed_attr):
                current_value = getattr(model, computed_attr)
            else:
                # Skip fields with None that don't have computed variants
                return None
        
        if metadata is None:
            # No UI metadata, create simple text input
            return widgets.FloatText(
                value=float(current_value),
                description=field_name,
            )
        
        # Create appropriate widget based on type and metadata
        if metadata.widget_type == "slider" and metadata.range:
            widget = widgets.FloatSlider(
                value=float(current_value),
                min=metadata.range[0],
                max=metadata.range[1],
                step=metadata.step or (metadata.range[1] - metadata.range[0]) / 100,
                description=metadata.label,
                continuous_update=False,  # Only update on release to avoid flickering
                readout_format=metadata.format_string or '.3g'
            )
        elif metadata.widget_type == "input":
            widget = widgets.FloatText(
                value=float(current_value),
                description=metadata.label,
                step=metadata.step,
            )
        elif metadata.widget_type == "checkbox":
            widget = widgets.Checkbox(
                value=bool(current_value),
                description=metadata.label,
            )
        else:
            # Default to text input
            widget = widgets.FloatText(
                value=float(current_value),
                description=metadata.label,
            )
        
        # Add tooltip if description available
        if metadata.description:
            widget.tooltip = metadata.description
        
        # Add unit to description if provided
        if metadata.unit and widget.description:
            widget.description = f"{widget.description} [{metadata.unit}]"
        
        return widget
    
    def create_layout(self, model: Any, fields: Optional[list[str]] = None) -> Any:
        """
        Create a layout with widgets for multiple fields.
        
        Args:
            model: BMCSModel instance
            fields: List of field names (None = all UI fields)
            
        Returns:
            ipywidgets VBox or HBox
        """
        if not JUPYTER_AVAILABLE:
            raise ImportError("ipywidgets not available")
        
        if fields is None:
            # Get all fields with UI metadata
            ui_fields = get_all_ui_fields(model)
            fields = list(ui_fields.keys())
        
        # Create widgets for each field
        widget_dict = {}
        for field_name in fields:
            widget = self.create_widget(model, field_name)
            # Only add non-None widgets
            if widget is not None:
                widget_dict[field_name] = widget
        
        # Create layout
        widget_list = list(widget_dict.values())
        layout = widgets.VBox(widget_list)
        
        return layout, widget_dict


def create_interactive_plot(
    model: Any,
    plot_func: Callable,
    update_func: Optional[Callable] = None,
    fields: Optional[list[str]] = None,
    figsize: tuple = (10, 6),
    **plot_kwargs
):
    """
    Create an interactive plot with parameter controls.
    
    Supports two modes:
    1. Full redraw mode (default): plot_func recreates the entire plot on each update
    2. Efficient update mode: plot_func sets up axes once, update_func updates only data
    
    Args:
        model: BMCSModel instance
        plot_func: Function(model, ax) that creates/sets up the plot
        update_func: Optional function(model, ax) that updates only the data (more efficient)
        fields: Fields to create controls for (None = all)
        figsize: Figure size
        **plot_kwargs: Additional arguments for plot_func/update_func
        
    Returns:
        Interactive widget with plot and controls
        
    Example (efficient mode):
        ```python
        def setup_plot(model, ax):
            ax.set_xlabel('Strain ε [-]')
            ax.set_ylabel('Stress σ [MPa]')
            ax.set_title('Steel Stress-Strain')
            ax.grid(True, alpha=0.3)
            # Return line objects for updating
            line, = ax.plot([], [], 'b-', linewidth=2)
            points, = ax.plot([], [], 'ro', markersize=8)
            return {'line': line, 'points': points}
        
        def update_plot(model, ax, artists):
            eps = np.linspace(-model.eps_max, model.eps_max, 200)
            sig = model.get_sig(eps)
            artists['line'].set_data(eps, sig)
            artists['points'].set_data([-model.eps_y, model.eps_y], 
                                       [-model.f_y, model.f_y])
            ax.set_xlim(-model.eps_max, model.eps_max)
            ax.relim()
            ax.autoscale_view()
        
        create_interactive_plot(steel, setup_plot, update_plot)
        ```
    """
    if not JUPYTER_AVAILABLE:
        raise ImportError("ipywidgets and matplotlib not available")
    
    # Create adapter
    adapter = JupyterAdapter()
    
    # Create widgets
    layout, widget_dict = adapter.create_layout(model, fields)
    
    # Create output widget for plot
    output = widgets.Output()
    
    # Track if we're currently updating to prevent cascading updates
    _updating = {'flag': False}
    
    # Storage for figure, axes, and artists (for efficient update mode)
    _plot_state = {'fig': None, 'ax': None, 'artists': None, 'initialized': False}
    
    def update_plot(*args):
        """Update plot when parameters change"""
        # Prevent recursive updates
        if _updating['flag']:
            return
        
        _updating['flag'] = True
        try:
            # Update model parameters directly (don't use update_params to avoid triggering observers)
            for field_name, widget in widget_dict.items():
                object.__setattr__(model, field_name, widget.value)
            
            # Invalidate caches
            if hasattr(model, 'invalidate_caches'):
                model.invalidate_caches()
            
            # Update plot
            with output:
                if update_func is not None:
                    # Efficient update mode: only update data, not axes
                    if not _plot_state['initialized']:
                        # First time: create figure and setup axes
                        output.clear_output(wait=True)
                        fig, ax = plt.subplots(figsize=figsize)
                        _plot_state['fig'] = fig
                        _plot_state['ax'] = ax
                        # Setup plot and get artist handles
                        _plot_state['artists'] = plot_func(model, ax, **plot_kwargs)
                        _plot_state['initialized'] = True
                        # Populate initial data
                        update_func(model, _plot_state['ax'], _plot_state['artists'], **plot_kwargs)
                        plt.tight_layout()
                        plt.show()
                    else:
                        # Subsequent updates: only update data
                        output.clear_output(wait=True)
                        update_func(model, _plot_state['ax'], _plot_state['artists'], **plot_kwargs)
                        _plot_state['fig'].canvas.draw()
                        display(_plot_state['fig'])
                else:
                    # Full redraw mode (backward compatible)
                    output.clear_output(wait=True)
                    fig, ax = plt.subplots(figsize=figsize)
                    plot_func(model, ax, **plot_kwargs)
                    plt.tight_layout()
                    plt.show()
        finally:
            _updating['flag'] = False
    
    # Connect widgets to update function
    for widget in widget_dict.values():
        widget.observe(update_plot, names='value')
    
    # Initial plot
    update_plot()
    
    # Display everything
    full_layout = widgets.VBox([layout, output])
    display(full_layout)
    
    return full_layout


def create_widget(model: Any, on_change: Optional[Callable] = None):
    """
    Create a simple widget panel for a model.
    
    Args:
        model: BMCSModel instance
        on_change: Callback function(model) called when parameters change
        
    Returns:
        Widget layout
        
    Example:
        ```python
        def on_param_change(model):
            print(f"f_cm = {model.f_cm}")
        
        widget = create_widget(concrete_model, on_change=on_param_change)
        display(widget)
        ```
    """
    if not JUPYTER_AVAILABLE:
        raise ImportError("ipywidgets not available")
    
    adapter = JupyterAdapter()
    layout, widget_dict = adapter.create_layout(model)
    
    if on_change:
        # Track if we're currently updating to prevent cascading updates
        _updating = {'flag': False}
        
        def update(*args):
            # Prevent recursive updates
            if _updating['flag']:
                return
            
            _updating['flag'] = True
            try:
                # Update model directly
                for field_name, widget in widget_dict.items():
                    object.__setattr__(model, field_name, widget.value)
                
                # Invalidate caches
                if hasattr(model, 'invalidate_caches'):
                    model.invalidate_caches()
                
                # Call callback
                on_change(model)
            finally:
                _updating['flag'] = False
        
        # Connect widgets
        for widget in widget_dict.values():
            widget.observe(update, names='value')
    
    display(layout)
    return layout


__all__ = [
    'JupyterAdapter',
    'create_interactive_plot',
    'create_widget',
]
