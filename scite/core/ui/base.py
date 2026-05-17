"""
UI abstraction layer for multiple frontends.

Supports:
- Jupyter notebooks (ipywidgets)
- Streamlit
- Gradio (future)

Provides decorators and utilities to add UI metadata to model fields
without coupling computation to UI framework.
"""

from dataclasses import dataclass
from typing import Any, Optional, Tuple, Callable, Literal, Union
from pydantic import Field as PydanticField
from functools import wraps

# Type alias for supported UI frameworks
UIFramework = Literal["jupyter", "streamlit", "gradio"]


@dataclass
class UIMetadata:
    """
    Metadata for automatic UI widget generation.
    
    Attributes:
        label: Display label (can use LaTeX: r"$f_{cm}$")
        unit: Physical unit (e.g., "MPa", "mm", "kN")
        range: Min/max values for slider (min, max)
        step: Step size for numeric input
        description: Tooltip/help text
        widget_type: Type of widget to create
        
    Example:
        ```python
        meta = UIMetadata(
            label=r"$f_{cm}$",
            unit="MPa",
            range=(20.0, 100.0),
            step=1.0,
            description="Mean compressive strength of concrete"
        )
        ```
    """
    label: str
    unit: Optional[str] = None
    range: Optional[Tuple[float, float]] = None
    step: Optional[float] = None
    description: Optional[str] = None
    widget_type: str = "slider"  # slider, input, dropdown, checkbox, etc.
    format_string: Optional[str] = None  # e.g., "%.2f"


def ui_field(
    default: Any,
    *,
    label: str,
    unit: Optional[str] = None,
    range: Optional[Tuple[float, float]] = None,
    step: Optional[float] = None,
    description: Optional[str] = None,
    widget_type: str = "slider",
    format_string: Optional[str] = None,
    **pydantic_kwargs
):
    """
    Create a Pydantic field with UI metadata.
    
    This allows models to be UI-agnostic while still providing
    information for automatic UI generation.
    
    Args:
        default: Default value
        label: Display label (LaTeX supported)
        unit: Physical unit string
        range: (min, max) for sliders
        step: Step size for numeric inputs
        description: Help text
        widget_type: Type of widget
        format_string: Format string for display
        **pydantic_kwargs: Additional Pydantic field arguments
        
    Returns:
        Pydantic Field with UI metadata
        
    Example:
        ```python
        from scite.core import BMCSModel, ui_field
        
        class ConcreteModel(BMCSModel):
            f_cm: float = ui_field(
                30.0,
                label=r"$f_{cm}$",
                unit="MPa",
                range=(20.0, 100.0),
                step=1.0,
                description="Mean compressive strength",
                gt=0  # Pydantic validation
            )
        ```
    """
    metadata = UIMetadata(
        label=label,
        unit=unit,
        range=range,
        step=step,
        description=description,
        widget_type=widget_type,
        format_string=format_string
    )
    
    # Add UI metadata to Pydantic field
    return PydanticField(
        default=default,
        json_schema_extra={'ui_metadata': metadata.__dict__},
        **pydantic_kwargs
    )


class UIAdapter:
    """
    Base class for UI framework adapters.
    
    Subclasses implement specific widget creation for different frameworks.
    """
    
    def create_widget(self, model: Any, field_name: str) -> Any:
        """
        Create a widget for a model field.
        
        Args:
            model: BMCSModel instance
            field_name: Name of field to create widget for
            
        Returns:
            Framework-specific widget
        """
        raise NotImplementedError
    
    def create_layout(self, model: Any, fields: list[str]) -> Any:
        """
        Create a layout containing multiple widgets.
        
        Args:
            model: BMCSModel instance
            fields: List of field names
            
        Returns:
            Framework-specific layout container
        """
        raise NotImplementedError
    
    def render_plot(self, model: Any, plot_func: Callable) -> Any:
        """
        Render a plot for the model.
        
        Args:
            model: BMCSModel instance
            plot_func: Function that creates the plot
            
        Returns:
            Framework-specific plot container
        """
        raise NotImplementedError


def interactive(plot_function: Optional[Callable] = None):
    """
    Decorator to make a plotting function interactive.
    
    Automatically creates UI widgets for model parameters and
    updates plot when parameters change.
    
    Args:
        plot_function: Optional plot function to wrap
        
    Returns:
        Decorated function
        
    Example:
        ```python
        from scite.core.ui import interactive
        
        class ConcreteModel(BMCSModel):
            f_cm: float = ui_field(30.0, label="f_cm", range=(20, 100))
            
            @interactive
            def plot_stress_strain(self, ax):
                eps = np.linspace(0, 0.004, 100)
                sig = self.get_sig(eps)
                ax.plot(eps, sig)
                ax.set_xlabel("Strain")
                ax.set_ylabel("Stress [MPa]")
        
        # Usage in notebook:
        model = ConcreteModel()
        model.plot_stress_strain()  # Creates interactive widget
        ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Check if we're in an interactive environment
            try:
                # Try Jupyter first
                from IPython import get_ipython
                if get_ipython() is not None:
                    from scite.core.ui.jupyter import create_interactive_plot
                    return create_interactive_plot(self, func, *args, **kwargs)
            except (ImportError, AttributeError):
                pass
            
            # Fallback to direct call (non-interactive)
            return func(self, *args, **kwargs)
        
        return wrapper
    
    # Handle both @interactive and @interactive()
    if plot_function is not None:
        return decorator(plot_function)
    return decorator


# Utility functions for extracting UI metadata
def get_ui_metadata(model: Any, field_name: str) -> Optional[UIMetadata]:
    """
    Extract UI metadata from a model field.
    
    Args:
        model: BMCSModel instance or class
        field_name: Field name
        
    Returns:
        UIMetadata if available, None otherwise
    """
    model_class = model if isinstance(model, type) else type(model)
    
    if hasattr(model_class, 'model_fields'):
        field_info = model_class.model_fields.get(field_name)
        if field_info:
            extra = field_info.json_schema_extra
            if extra is not None and isinstance(extra, dict) and 'ui_metadata' in extra:
                meta_dict = extra['ui_metadata']
                return UIMetadata(**meta_dict)
    
    return None


def get_all_ui_fields(model: Any) -> dict[str, UIMetadata]:
    """
    Get all fields with UI metadata from a model.
    
    Args:
        model: BMCSModel instance or class
        
    Returns:
        Dictionary mapping field names to UIMetadata
    """
    model_class = model if isinstance(model, type) else type(model)
    result = {}
    
    if hasattr(model_class, 'model_fields'):
        for field_name, field_info in model_class.model_fields.items():
            extra = field_info.json_schema_extra
            if extra is not None and isinstance(extra, dict) and 'ui_metadata' in extra:
                meta_dict = extra['ui_metadata']
                result[field_name] = UIMetadata(**meta_dict)
    
    return result


def format_value(value: float, metadata: UIMetadata) -> str:
    """
    Format a value for display using UI metadata.
    
    Args:
        value: Numeric value
        metadata: UI metadata with format info
        
    Returns:
        Formatted string
    """
    if metadata.format_string:
        formatted = metadata.format_string % value
    else:
        formatted = f"{value:.3g}"
    
    if metadata.unit:
        return f"{formatted} {metadata.unit}"
    return formatted


__all__ = [
    'UIMetadata',
    'ui_field',
    'UIAdapter',
    'interactive',
    'get_ui_metadata',
    'get_all_ui_fields',
    'format_value',
    'UIFramework',
]
