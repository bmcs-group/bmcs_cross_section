"""
Streamlit UI adapter for web applications.
"""

from typing import Any, Callable, Optional, Type
import numpy as np

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None

from bmcs_cross_section.core.ui.base import UIAdapter, get_ui_metadata, get_all_ui_fields


class StreamlitAdapter(UIAdapter):
    """
    Adapter for creating Streamlit widgets from model fields.
    """
    
    def create_widget(self, model: Any, field_name: str, key_prefix: str = "") -> Any:
        """
        Create a Streamlit widget for a model field.
        
        Args:
            model: BMCSModel instance
            field_name: Field name
            key_prefix: Prefix for widget key (for uniqueness)
            
        Returns:
            Current widget value
        """
        if not STREAMLIT_AVAILABLE:
            raise ImportError("streamlit not available. Install with: pip install streamlit")
        
        metadata = get_ui_metadata(model, field_name)
        current_value = getattr(model, field_name)
        key = f"{key_prefix}{field_name}"
        
        if metadata is None:
            # No UI metadata, create simple number input
            return st.number_input(
                field_name,
                value=float(current_value),
                key=key
            )
        
        # Create appropriate widget based on type and metadata
        label = metadata.label
        if metadata.unit:
            label = f"{label} [{metadata.unit}]"
        
        if metadata.widget_type == "slider" and metadata.range:
            value = st.slider(
                label,
                min_value=metadata.range[0],
                max_value=metadata.range[1],
                value=float(current_value),
                step=metadata.step or (metadata.range[1] - metadata.range[0]) / 100,
                help=metadata.description,
                key=key
            )
        elif metadata.widget_type == "input":
            value = st.number_input(
                label,
                value=float(current_value),
                step=metadata.step,
                help=metadata.description,
                key=key
            )
        elif metadata.widget_type == "checkbox":
            value = st.checkbox(
                label,
                value=bool(current_value),
                help=metadata.description,
                key=key
            )
        else:
            # Default to number input
            value = st.number_input(
                label,
                value=float(current_value),
                help=metadata.description,
                key=key
            )
        
        return value
    
    def create_layout(
        self,
        model: Any,
        fields: Optional[list[str]] = None,
        columns: int = 1,
        key_prefix: str = ""
    ) -> dict[str, Any]:
        """
        Create Streamlit widgets for multiple fields.
        
        Args:
            model: BMCSModel instance
            fields: List of field names (None = all UI fields)
            columns: Number of columns for layout
            key_prefix: Prefix for widget keys
            
        Returns:
            Dictionary mapping field names to values
        """
        if not STREAMLIT_AVAILABLE:
            raise ImportError("streamlit not available")
        
        if fields is None:
            # Get all fields with UI metadata
            ui_fields = get_all_ui_fields(model)
            fields = list(ui_fields.keys())
        
        # Create columns if requested
        if columns > 1:
            cols = st.columns(columns)
        else:
            cols = [st] * len(fields)
        
        # Create widgets
        values = {}
        for i, field_name in enumerate(fields):
            col = cols[i % columns]
            with col:
                values[field_name] = self.create_widget(model, field_name, key_prefix)
        
        return values


class StreamlitApp:
    """
    Base class for Streamlit applications.
    
    Subclass this to create a Streamlit app for your model.
    
    Example:
        ```python
        from bmcs_cross_section.core.ui.streamlit import StreamlitApp
        
        class ConcreteModelApp(StreamlitApp):
            title = "Concrete Material Model"
            
            def create_model(self):
                return ConcreteModel()
            
            def render_controls(self, model):
                adapter = StreamlitAdapter()
                values = adapter.create_layout(model)
                model.update_params(**values)
                return model
            
            def render_plot(self, model):
                fig, ax = plt.subplots(figsize=(10, 6))
                eps = np.linspace(0, 0.004, 100)
                sig = model.get_sig(eps)
                ax.plot(eps, sig)
                ax.set_xlabel('Strain')
                ax.set_ylabel('Stress [MPa]')
                st.pyplot(fig)
            
            def run(self):
                st.title(self.title)
                model = self.create_model()
                model = self.render_controls(model)
                self.render_plot(model)
        
        # In your streamlit script:
        if __name__ == "__main__":
            app = ConcreteModelApp()
            app.run()
        ```
    """
    
    title: str = "BMCS Application"
    description: str = ""
    
    def create_model(self) -> Any:
        """Create the model instance. Override in subclass."""
        raise NotImplementedError
    
    def render_controls(self, model: Any) -> Any:
        """Render control widgets. Override in subclass."""
        raise NotImplementedError
    
    def render_plot(self, model: Any) -> None:
        """Render plots and results. Override in subclass."""
        raise NotImplementedError
    
    def render_sidebar(self, model: Any) -> None:
        """Render sidebar content. Override if needed."""
        pass
    
    def run(self) -> None:
        """Main app entry point. Can be overridden for custom layout."""
        if not STREAMLIT_AVAILABLE:
            raise ImportError("streamlit not available")
        
        # Title
        if self.title:
            st.title(self.title)
        
        # Description
        if self.description:
            st.markdown(self.description)
        
        # Create model
        model = self.create_model()
        
        # Sidebar
        with st.sidebar:
            st.header("Parameters")
            self.render_sidebar(model)
            model = self.render_controls(model)
        
        # Main content
        self.render_plot(model)


def create_streamlit_app(
    model_class: Type,
    title: str,
    plot_func: Callable,
    description: str = ""
) -> Type[StreamlitApp]:
    """
    Factory function to create a Streamlit app from a model class.
    
    Args:
        model_class: BMCSModel class
        title: App title
        plot_func: Function(model, fig, ax) that creates the plot
        description: App description
        
    Returns:
        StreamlitApp class
        
    Example:
        ```python
        def plot_stress_strain(model, fig, ax):
            eps = np.linspace(0, 0.004, 100)
            sig = model.get_sig(eps)
            ax.plot(eps, sig)
            ax.set_xlabel('Strain')
            ax.set_ylabel('Stress [MPa]')
        
        AppClass = create_streamlit_app(
            ConcreteModel,
            "Concrete Stress-Strain",
            plot_stress_strain
        )
        
        app = AppClass()
        app.run()
        ```
    """
    
    class GeneratedApp(StreamlitApp):
        def __init__(self):
            self.title = title
            self.description = description
            self.model_class = model_class
            self.plot_func = plot_func
        
        def create_model(self):
            return self.model_class()
        
        def render_controls(self, model):
            adapter = StreamlitAdapter()
            values = adapter.create_layout(model)
            model.update_params(**values)
            return model
        
        def render_plot(self, model):
            try:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(10, 6))
                self.plot_func(model, fig, ax)
                st.pyplot(fig)
            except ImportError:
                st.error("matplotlib not available for plotting")
    
    return GeneratedApp


__all__ = [
    'StreamlitAdapter',
    'StreamlitApp',
    'create_streamlit_app',
]
