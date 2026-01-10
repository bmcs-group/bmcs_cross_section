"""
Symbolic mathematics integration using SymPy with NumPy lambdification.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple, Union, Any
import sympy as sp
import numpy as np


@dataclass
class SymbolicExpression:
    """
    Container for a symbolic expression with lambdification.
    
    Attributes:
        name: Expression name
        expression: SymPy expression
        parameters: Tuple of parameter names (in order)
        
    Example:
        ```python
        import sympy as sp
        
        # Define symbols
        x = sp.Symbol('x', real=True)
        a = sp.Symbol('a', real=True)
        
        # Create expression
        expr = SymbolicExpression(
            name='linear',
            expression=a * x,
            parameters=('x', 'a')
        )
        
        # Evaluate numerically
        result = expr(2.0, 3.0)  # 6.0
        ```
    """
    
    name: str
    expression: sp.Expr
    parameters: Tuple[str, ...]
    _lambdified: Optional[Callable] = field(default=None, init=False, repr=False)
    
    def lambdify(self, use_numpy: bool = True) -> Callable:
        """
        Create a numerical function from the symbolic expression.
        
        Args:
            use_numpy: Use numpy for array operations
            
        Returns:
            Numerical function that can be called with parameter values
        """
        if self._lambdified is None:
            # Get the actual symbols in order
            symbols = [sp.Symbol(param) for param in self.parameters]
            
            # Choose modules for evaluation
            modules = ['numpy'] if use_numpy else ['math']
            
            # Lambdify the expression
            self._lambdified = sp.lambdify(
                symbols,
                self.expression,
                modules=modules
            )
        
        return self._lambdified
    
    def __call__(self, *args, **kwargs):
        """
        Evaluate the expression numerically.
        
        Args:
            *args: Positional arguments matching parameters
            **kwargs: Keyword arguments (parameter names)
            
        Returns:
            Numerical result (scalar or array)
        """
        func = self.lambdify()
        return func(*args, **kwargs)
    
    def derivative(self, wrt: str) -> 'SymbolicExpression':
        """
        Compute derivative with respect to a parameter.
        
        Args:
            wrt: Parameter name to differentiate with respect to
            
        Returns:
            New SymbolicExpression for the derivative
        """
        if wrt not in self.parameters:
            raise ValueError(f"Parameter '{wrt}' not in expression parameters")
        
        # Get the symbol
        param_symbol = sp.Symbol(wrt)
        
        # Compute derivative
        derivative_expr = sp.diff(self.expression, param_symbol)
        
        # Create new expression
        return SymbolicExpression(
            name=f"d_{self.name}_d_{wrt}",
            expression=derivative_expr,
            parameters=self.parameters
        )


class SymbolicModel:
    """
    Registry for symbolic expressions and symbols.
    
    Manages symbols and expressions, providing convenient methods
    for defining and accessing symbolic mathematics.
    
    Example:
        ```python
        from bmcs_cross_section.core.symbolic import SymbolicModel
        
        # Create model
        symb = SymbolicModel()
        
        # Define symbols
        eps = symb.symbol('varepsilon', real=True)
        E = symb.symbol('E', positive=True)
        
        # Define expression
        sig = symb.expression('sigma', E * eps, ('varepsilon', 'E'))
        
        # Use it
        stress = sig(0.001, 200000)  # 200.0
        ```
    """
    
    def __init__(self):
        self.symbols: Dict[str, sp.Symbol] = {}
        self.expressions: Dict[str, SymbolicExpression] = {}
    
    def symbol(self, name: str, **assumptions) -> sp.Symbol:
        """
        Define or retrieve a symbolic variable.
        
        Args:
            name: Symbol name (can use LaTeX: 'varepsilon', 'sigma', etc.)
            **assumptions: SymPy assumptions (real=True, positive=True, etc.)
            
        Returns:
            SymPy Symbol
            
        Example:
            ```python
            eps = symb.symbol('varepsilon', real=True)
            f_c = symb.symbol('f_c', positive=True)
            ```
        """
        if name not in self.symbols:
            self.symbols[name] = sp.Symbol(name, **assumptions)
        return self.symbols[name]
    
    def expression(
        self,
        name: str,
        expr: sp.Expr,
        params: Tuple[str, ...]
    ) -> SymbolicExpression:
        """
        Register a symbolic expression.
        
        Args:
            name: Expression name
            expr: SymPy expression
            params: Tuple of parameter names (in evaluation order)
            
        Returns:
            SymbolicExpression that can be evaluated numerically
            
        Example:
            ```python
            # Linear stress-strain
            sig = symb.expression(
                'sigma',
                symb.symbols['E'] * symb.symbols['varepsilon'],
                ('varepsilon', 'E')
            )
            ```
        """
        symb_expr = SymbolicExpression(name, expr, params)
        self.expressions[name] = symb_expr
        return symb_expr
    
    def get_expression(self, name: str) -> SymbolicExpression:
        """
        Retrieve a registered expression.
        
        Args:
            name: Expression name
            
        Returns:
            SymbolicExpression
            
        Raises:
            KeyError: If expression not found
        """
        return self.expressions[name]
    
    def __getitem__(self, name: str) -> SymbolicExpression:
        """Convenient access to expressions"""
        return self.get_expression(name)
    
    def __repr__(self) -> str:
        return (
            f"SymbolicModel("
            f"symbols={list(self.symbols.keys())}, "
            f"expressions={list(self.expressions.keys())})"
        )


def create_symbolic_function(
    expr: sp.Expr,
    params: Tuple[str, ...],
    name: Optional[str] = None
) -> Callable:
    """
    Convenience function to create a numerical function from a SymPy expression.
    
    Args:
        expr: SymPy expression
        params: Parameter names in order
        name: Optional function name
        
    Returns:
        Numerical function
        
    Example:
        ```python
        import sympy as sp
        
        x, y = sp.symbols('x y')
        f = create_symbolic_function(x**2 + y**2, ('x', 'y'))
        
        result = f(3.0, 4.0)  # 25.0
        ```
    """
    symbols = [sp.Symbol(p) for p in params]
    return sp.lambdify(symbols, expr, modules=['numpy'])


# Common mathematical utilities
def piecewise_function(
    conditions: list[Tuple[sp.Expr, sp.Expr]]
) -> sp.Piecewise:
    """
    Create a piecewise function.
    
    Args:
        conditions: List of (expression, condition) tuples
        
    Returns:
        SymPy Piecewise expression
        
    Example:
        ```python
        import sympy as sp
        
        x = sp.Symbol('x')
        
        # f(x) = x² if x > 0, else 0
        f = piecewise_function([
            (x**2, x > 0),
            (0, True)
        ])
        ```
    """
    return sp.Piecewise(*conditions)
