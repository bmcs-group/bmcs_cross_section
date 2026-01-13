"""
RC Bending and Normal Force - Computational Model Module

This module provides a computational model with cached properties for efficient
calculation and visualization of reinforced concrete cross-section analysis.

The model stores input parameters as attributes and computes derived quantities
on-demand with caching to optimize performance.

Author: Rostislav Chudoba
Course: Grundlagen der Tragwerke (Fundamentals of Structural Design)
Institution: IMB Institute, RWTH Aachen University
"""

import numpy as np
from functools import cached_property
from typing import Tuple
from .rc_bending_derive_mn import RCBendingDeriveMN


class RCBendingModelMN:
    """
    Computational model for RC cross-section analysis with cached properties.
    
    This class manages input parameters and provides efficient access to
    calculated results through Python's cached_property mechanism.
    """
    
    def __init__(self):
        """Initialize the model with default values."""
        # Create derivation engine
        self._derive = RCBendingDeriveMN()
        
        # Material properties - Concrete
        self._f_ck = 25.0  # MPa
        self._epsilon_cx2 = -0.002
        self._epsilon_cu2 = -0.0035
        
        # Material properties - Steel
        self._f_yk = 500.0  # MPa
        self._E_s = 200000.0  # MPa
        
        # Geometry
        self._d = 0.45  # m
        self._b = 0.30  # m
        self._c_nom = 0.05  # m
        
        # Loading
        self._M_Ed = 0.2  # MN·m
        self._N_Ed = 0.05  # MN
        
        # Safety factors (EC2)
        self._gamma_c = 1.5
        self._gamma_s = 1.15
        
    def _clear_cache(self):
        """Clear all cached properties when parameters change."""
        cached_props = [
            'f_cd', 'sigma_yd', 'epsilon_yd', 'k_a', 'alpha_r',
            'epsilon_s1', 'x', 'a', 'z', 'F_cd', 'F_sd', 'M_Rds',
            'A_s', 'A_s_cm2', 'd_s1', 'sigma_s1'
        ]
        for prop in cached_props:
            self.__dict__.pop(prop, None)
    
    # ===== Input Properties with Setters =====
    
    @property
    def f_ck(self) -> float:
        """Characteristic concrete compressive strength [MPa]."""
        return self._f_ck
    
    @f_ck.setter
    def f_ck(self, value: float):
        self._f_ck = value
        self._clear_cache()
    
    @property
    def epsilon_cx2(self) -> float:
        """Strain at parabola-rectangle transition [-]."""
        return self._epsilon_cx2
    
    @epsilon_cx2.setter
    def epsilon_cx2(self, value: float):
        self._epsilon_cx2 = value
        self._clear_cache()
    
    @property
    def epsilon_cu2(self) -> float:
        """Ultimate concrete compressive strain [-]."""
        return self._epsilon_cu2
    
    @epsilon_cu2.setter
    def epsilon_cu2(self, value: float):
        self._epsilon_cu2 = value
        self._clear_cache()
    
    @property
    def f_yk(self) -> float:
        """Characteristic yield strength of reinforcement [MPa]."""
        return self._f_yk
    
    @f_yk.setter
    def f_yk(self, value: float):
        self._f_yk = value
        self._clear_cache()
    
    @property
    def E_s(self) -> float:
        """Young's modulus of steel [MPa]."""
        return self._E_s
    
    @E_s.setter
    def E_s(self, value: float):
        self._E_s = value
        self._clear_cache()
    
    @property
    def d(self) -> float:
        """Effective depth [m]."""
        return self._d
    
    @d.setter
    def d(self, value: float):
        self._d = value
        self._clear_cache()
    
    @property
    def b(self) -> float:
        """Width of cross-section [m]."""
        return self._b
    
    @b.setter
    def b(self, value: float):
        self._b = value
        self._clear_cache()
    
    @property
    def c_nom(self) -> float:
        """Nominal concrete cover [m]."""
        return self._c_nom
    
    @c_nom.setter
    def c_nom(self, value: float):
        self._c_nom = value
        self._clear_cache()
    
    @property
    def M_Ed(self) -> float:
        """Design bending moment [MN·m]."""
        return self._M_Ed
    
    @M_Ed.setter
    def M_Ed(self, value: float):
        self._M_Ed = value
        self._clear_cache()
    
    @property
    def N_Ed(self) -> float:
        """Design normal force [MN] (positive = tension)."""
        return self._N_Ed
    
    @N_Ed.setter
    def N_Ed(self, value: float):
        self._N_Ed = value
        self._clear_cache()
    
    @property
    def h(self) -> float:
        """Total height of cross-section [m]."""
        return self._d + self._c_nom
    
    # ===== Cached Design Properties =====
    
    @cached_property
    def f_cd(self) -> float:
        """Design concrete compressive strength [MPa]."""
        return 0.85 * self._f_ck / self._gamma_c
    
    @cached_property
    def sigma_yd(self) -> float:
        """Design yield strength of reinforcement [MPa]."""
        return self._f_yk / self._gamma_s
    
    @cached_property
    def epsilon_yd(self) -> float:
        """Yield strain of reinforcement [-]."""
        return self.sigma_yd / self._E_s
    
    @cached_property
    def k_a(self) -> float:
        """Center of gravity factor for compression zone [-]."""
        k_a, _ = self._derive.calculate_integration_parameters(
            self.epsilon_cu2, self.epsilon_cx2, self.epsilon_cu2, self.f_cd
        )
        return k_a
    
    @cached_property
    def alpha_r(self) -> float:
        """Stress block factor for compression zone [-]."""
        _, alpha_r = self._derive.calculate_integration_parameters(
            self.epsilon_cu2, self.epsilon_cx2, self.epsilon_cu2, self.f_cd
        )
        return alpha_r
    
    # ===== Cached Analysis Results =====
    
    @cached_property
    def epsilon_s1(self) -> float:
        """Reinforcement strain [-]."""
        return float(self._derive.get_epsilon_s1(
            self.M_Ed, self.N_Ed, self.d, self.b, self.c_nom,
            self.f_cd, self.k_a, self.alpha_r, self.epsilon_cu2
        ))
    
    @cached_property
    def x(self) -> float:
        """Neutral axis position from top [m]."""
        return float(self._derive.get_x(
            self.d, self.epsilon_cu2, self.epsilon_s1
        ))
    
    @cached_property
    def a(self) -> float:
        """Distance of compression resultant from top [m]."""
        return float(self._derive.get_a(
            self.d, self.k_a, self.epsilon_cu2, self.epsilon_s1
        ))
    
    @cached_property
    def z(self) -> float:
        """Lever arm [m]."""
        return float(self._derive.get_z(
            self.d, self.k_a, self.epsilon_cu2, self.epsilon_s1
        ))
    
    @cached_property
    def F_cd(self) -> float:
        """Concrete compression force [MN]."""
        return float(self._derive.get_F_cd(
            self.d, self.b, self.alpha_r, self.f_cd,
            self.epsilon_s1, self.epsilon_cu2
        ))
    
    @cached_property
    def F_sd(self) -> float:
        """Steel tension force [MN]."""
        return self.F_cd + self.N_Ed
    
    @cached_property
    def M_Rds(self) -> float:
        """Design resisting moment [MN·m]."""
        return float(self._derive.get_M_Rds(
            self.d, self.b, self.f_cd, self.k_a, self.alpha_r,
            self.epsilon_cu2, self.epsilon_s1
        ))
    
    @cached_property
    def A_s(self) -> float:
        """Required reinforcement area [m²]."""
        return float(self._derive.get_A_s(
            self.M_Ed, self.N_Ed, self.d, self.k_a, self.c_nom,
            self.b, self.sigma_yd, self.f_cd, self.alpha_r
        ))
    
    @cached_property
    def A_s_cm2(self) -> float:
        """Required reinforcement area [cm²]."""
        return self.A_s * 1e4
    
    @cached_property
    def d_s1(self) -> float:
        """Reinforcement position from bottom [m]."""
        return self.c_nom
    
    @cached_property
    def sigma_s1(self) -> float:
        """Steel stress [MPa]."""
        if self.epsilon_s1 <= self.epsilon_yd:
            return self.E_s * self.epsilon_s1  # Elastic
        else:
            return self.sigma_yd  # Yielded
    
    # ===== Methods for Visualization Data =====
    
    def get_concrete_stress_strain(self, epsilon_c_range: np.ndarray) -> np.ndarray:
        """
        Get concrete stress-strain curve for plotting.
        
        Parameters:
        -----------
        epsilon_c_range : np.ndarray
            Array of strain values [-]
            
        Returns:
        --------
        np.ndarray
            Corresponding stress values [MPa]
        """
        return self._derive.get_sigma_c(
            epsilon_c_range, self.f_cd, self.epsilon_cx2, self.epsilon_cu2
        )
    
    def get_steel_stress_strain(self, epsilon_s_range: np.ndarray) -> np.ndarray:
        """
        Get steel stress-strain curve for plotting (bilinear).
        
        Parameters:
        -----------
        epsilon_s_range : np.ndarray
            Array of strain values [-]
            
        Returns:
        --------
        np.ndarray
            Corresponding stress values [MPa]
        """
        return np.where(
            epsilon_s_range <= self.epsilon_yd,
            self.E_s * epsilon_s_range,
            self.sigma_yd
        )
    
    def get_strain_profile(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get strain distribution over cross-sectional height.
        
        Returns:
        --------
        Tuple[np.ndarray, np.ndarray]
            heights [m] (from bottom), strains [-]
            
        Note: x is measured from TOP, so neutral axis is at height (h - x) from bottom
        """
        heights = np.array([self.h, self.h - self.x, self.c_nom])
        strains = np.array([self.epsilon_cu2, 0.0, self.epsilon_s1])
        return heights, strains
    
    def get_stress_profile(self, n_points: int = 50) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Get stress distribution over cross-sectional height.
        
        Parameters:
        -----------
        n_points : int
            Number of points for concrete stress profile
            
        Returns:
        --------
        Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
            heights_concrete [m], stresses_concrete [MPa], heights_steel [m], stresses_steel [MPa]
        """
        # Concrete stress profile (compression zone)
        # x is from TOP, so compression zone is from h down to (h-x) when measured from bottom
        if self.x > 0:
            heights_c = np.linspace(self.h, self.h - self.x, n_points)
            # Distance from top for each point: y_top = h - height_from_bottom
            y_top = self.h - heights_c
            # Strain at distance y_top from top: epsilon = epsilon_cu2 * (1 - y_top/x)
            strains_c = self.epsilon_cu2 * (1 - y_top / self.x)
            stresses_c = self.get_concrete_stress_strain(strains_c)
        else:
            heights_c = np.array([])
            stresses_c = np.array([])
        
        # Steel stress (at reinforcement level = c_nom from bottom)
        heights_s = np.array([self.c_nom])
        stresses_s = np.array([self.sigma_s1])
        
        return heights_c, stresses_c, heights_s, stresses_s
    
    def get_integration_parameter_profiles(self, n_points: int = 100) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get k_a and alpha_r profiles vs. strain.
        
        Parameters:
        -----------
        n_points : int
            Number of points
            
        Returns:
        --------
        Tuple[np.ndarray, np.ndarray, np.ndarray]
            epsilon_c_range [-], k_a_values [-], alpha_r_values [-]
        """
        return self._derive.get_integration_parameter_profiles(
            self.epsilon_cx2, self.epsilon_cu2, self.f_cd, n_points
        )
    
    def summary(self) -> dict:
        """
        Get a summary of all calculated values.
        
        Returns:
        --------
        dict
            Dictionary with all results
        """
        return {
            # Input
            'f_ck': self.f_ck,
            'f_yk': self.f_yk,
            'd': self.d,
            'b': self.b,
            'h': self.h,
            'c_nom': self.c_nom,
            'M_Ed': self.M_Ed,
            'N_Ed': self.N_Ed,
            # Design values
            'f_cd': self.f_cd,
            'sigma_yd': self.sigma_yd,
            'k_a': self.k_a,
            'alpha_r': self.alpha_r,
            # Results
            'epsilon_c2': self.epsilon_cu2,
            'epsilon_s1': self.epsilon_s1,
            'x': self.x,
            'a': self.a,
            'z': self.z,
            'F_cd': self.F_cd,
            'F_sd': self.F_sd,
            'M_Rds': self.M_Rds,
            'A_s': self.A_s,
            'A_s_cm2': self.A_s_cm2,
        }
