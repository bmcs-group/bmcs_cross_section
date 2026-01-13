"""
Base model class using Pydantic for validation and type safety.
"""

from typing import Any, ClassVar, Optional, get_type_hints
from functools import cached_property
from pydantic import BaseModel, ConfigDict
import numpy as np


class BMCSModel(BaseModel):
    """
    Base model for all BMCS computational components.
    
    Features:
    - Pydantic validation with type safety
    - Support for numpy arrays
    - Cached property management
    - UI metadata support
    - Update/invalidate pattern
    
    Example:
        ```python
        from bmcs_cross_section.core import BMCSModel, ui_field
        
        class ConcreteModel(BMCSModel):
            f_cm: float = ui_field(
                30.0,
                label="f_{cm}",
                unit="MPa",
                range=(20, 100),
                description="Mean compressive strength"
            )
            
            @cached_property
            def f_ck(self) -> float:
                '''Characteristic strength'''
                return self.f_cm - 8.0
        
        model = ConcreteModel(f_cm=35.0)
        print(model.f_ck)  # 27.0
        
        model.update_params(f_cm=40.0)
        print(model.f_ck)  # 32.0 (cache invalidated)
        ```
    """
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow numpy arrays
        validate_assignment=True,       # Validate on attribute assignment
        extra='forbid',                 # Raise error on extra fields
        frozen=False,                   # Allow mutation
    )
    
    # Class-level metadata (can be populated by subclasses)
    _ui_fields: ClassVar[dict[str, dict]] = {}
    
    def update_params(self, **kwargs) -> None:
        """
        Update multiple parameters and invalidate caches.
        
        Args:
            **kwargs: Parameter name-value pairs
            
        Example:
            ```python
            model.update_params(f_cm=35.0, eps_c1=0.0022)
            ```
        """
        # Update each parameter
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"Model has no parameter '{key}'")
        
        # Invalidate caches after all updates
        self.invalidate_caches()
    
    def invalidate_caches(self) -> None:
        """
        Clear all cached properties.
        
        Call this after parameter updates to ensure cached values are recomputed.
        """
        # Find all cached_property attributes
        for attr_name in dir(type(self)):
            attr = getattr(type(self), attr_name, None)
            if isinstance(attr, cached_property):
                # Remove from instance dict to force recomputation
                self.__dict__.pop(attr_name, None)
    
    def model_post_init(self, __context: Any) -> None:
        """
        Hook called after model initialization.
        
        Override in subclasses for custom initialization logic.
        """
        pass
    
    @classmethod
    def get_ui_metadata(cls) -> dict[str, dict]:
        """
        Get UI metadata for all fields.
        
        Returns:
            Dictionary mapping field names to UI metadata
        """
        metadata = {}
        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra
            if extra is not None and isinstance(extra, dict) and 'ui_metadata' in extra:
                metadata[field_name] = extra['ui_metadata']
        return metadata
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary.
        
        Returns:
            Dictionary with field names and values
        """
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BMCSModel':
        """
        Create model from dictionary.
        
        Args:
            data: Dictionary with field values
            
        Returns:
            New model instance
        """
        return cls(**data)
    
    def __repr__(self) -> str:
        """Pretty representation showing parameter values"""
        fields = []
        for name, value in self.model_dump().items():
            if isinstance(value, np.ndarray):
                fields.append(f"{name}=array(shape={value.shape})")
            elif isinstance(value, float):
                fields.append(f"{name}={value:.3g}")
            else:
                fields.append(f"{name}={value}")
        return f"{self.__class__.__name__}({', '.join(fields)})"


class BMCSModelWithSymbolic(BMCSModel):
    """
    Base model with symbolic expression support.
    
    Subclasses should define a `_symbolic` class variable
    containing a SymbolicModel instance.
    
    Example:
        ```python
        from bmcs_cross_section.core import BMCSModelWithSymbolic
        from bmcs_cross_section.core.symbolic import SymbolicModel
        
        class MyModel(BMCSModelWithSymbolic):
            # Define symbolic expressions at class level
            _symbolic: ClassVar[SymbolicModel] = SymbolicModel()
            
            a: float = 1.0
            b: float = 2.0
            
            @classmethod
            def _init_symbolic(cls):
                if not cls._symbolic.expressions:
                    # Define symbols
                    x = cls._symbolic.symbol('x', real=True)
                    a = cls._symbolic.symbol('a', real=True)
                    b = cls._symbolic.symbol('b', real=True)
                    
                    # Define expressions
                    cls._symbolic.expression(
                        'f',
                        a * x + b,
                        ('x', 'a', 'b')
                    )
            
            def __post_init__(self):
                self._init_symbolic()
                super().__post_init__()
            
            def compute_f(self, x):
                return self._symbolic.expressions['f'](x, self.a, self.b)
        ```
    """
    
    _symbolic: ClassVar[Optional[Any]] = None  # Will be SymbolicModel
    
    @classmethod
    def _init_symbolic(cls) -> None:
        """
        Initialize symbolic expressions.
        
        Override in subclasses to define symbolic expressions.
        """
        pass
    
    def model_post_init(self, __context: Any) -> None:
        """Initialize symbolic expressions if not done"""
        if self._symbolic is not None:
            self._init_symbolic()
        super().model_post_init(__context)
