"""
Common type definitions for BMCS cross section package.
"""

from typing import Union, Protocol, runtime_checkable
import numpy as np
import numpy.typing as npt

# Type aliases
ArrayLike = Union[list, tuple, npt.NDArray]
FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int_]


@runtime_checkable
class StressStrainCurve(Protocol):
    """Protocol for stress-strain relationships"""
    
    def get_sig(self, eps: FloatArray) -> FloatArray:
        """Compute stress from strain"""
        ...
    
    def get_eps_plot_range(self) -> FloatArray:
        """Get strain range for plotting"""
        ...


@runtime_checkable
class IMaterialModel(Protocol):
    """Protocol for material constitutive models"""
    
    def get_sig(self, eps: FloatArray) -> FloatArray:
        """
        Compute stress from strain.
        
        Args:
            eps: Strain values (dimensionless)
            
        Returns:
            Stress values [MPa]
        """
        ...
    
    def get_eps_plot_range(self) -> FloatArray:
        """
        Get typical strain range for visualization.
        
        Returns:
            Strain array for plotting
        """
        ...
    
    def update_plot(self, ax) -> None:
        """
        Update matplotlib axes with stress-strain curve.
        
        Args:
            ax: Matplotlib axes object
        """
        ...


@runtime_checkable
class ICrossSection(Protocol):
    """Protocol for cross-section geometry"""
    
    @property
    def H(self) -> float:
        """Total height of cross-section [mm]"""
        ...
    
    def get_b(self, z: FloatArray) -> FloatArray:
        """
        Get width at height z.
        
        Args:
            z: Height coordinate(s) [mm]
            
        Returns:
            Width(es) at given height(s) [mm]
        """
        ...
    
    def get_A(self) -> float:
        """Get total cross-sectional area [mm²]"""
        ...


@runtime_checkable
class IReinforcementLayout(Protocol):
    """Protocol for reinforcement layout"""
    
    @property
    def z_j(self) -> FloatArray:
        """Heights of reinforcement layers [mm]"""
        ...
    
    @property
    def A_j(self) -> FloatArray:
        """Areas of reinforcement layers [mm²]"""
        ...
    
    def get_N_tj(self, eps_tj: FloatArray) -> FloatArray:
        """
        Get normal forces in reinforcement layers.
        
        Args:
            eps_tj: Strains in each layer (time x layers)
            
        Returns:
            Normal forces (time x layers) [N]
        """
        ...
