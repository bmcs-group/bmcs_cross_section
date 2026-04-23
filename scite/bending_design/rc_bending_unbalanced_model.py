"""
RC Bending and Normal Force - Unbalanced Model Module

This module provides a trial-and-error model for reinforced concrete cross-section
analysis. Unlike the balanced model, this allows free variation of the bottom strain
to explore the equilibrium iteratively.

The model is designed for interactive learning, allowing students to understand
the iterative dimensioning procedure by manually adjusting strains and observing
the resulting force imbalance.

Author: Rostislav Chudoba
Course: Grundlagen der Tragwerke (Fundamentals of Structural Design)
Institution: IMB Institute, RWTH Aachen University
"""

import numpy as np
from typing import Tuple
from .rc_bending_derive_mn import RCBendingDeriveMN


class RCBendingUnbalancedModel:
    """
    Unbalanced model for trial-and-error exploration of RC cross-section analysis.
    
    This model allows independent specification of top and bottom strains,
    enabling interactive exploration of the equilibrium conditions.
    """
    
    def __init__(self):
        """Initialize the unbalanced model with default values."""
        # Create derivation engine for symbolic expressions
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
        
        # Loading (for reference and equilibrium check)
        self._M_Ed = 0.2  # MN·m
        self._N_Ed = 0.0  # MN
        
        # Safety factors (EC2)
        self._gamma_c = 1.5
        self._gamma_s = 1.15
        
        # Strain state (USER CONTROLLED - not calculated)
        self._epsilon_c_top = -0.0035  # Top fiber strain (compression)
        self._epsilon_s_bottom = 0.0025  # Bottom fiber strain (tension)
    
    # ===== Input Properties with Setters =====
    
    @property
    def f_ck(self) -> float:
        """Characteristic concrete compressive strength [MPa]."""
        return self._f_ck
    
    @f_ck.setter
    def f_ck(self, value: float):
        self._f_ck = value
    
    @property
    def epsilon_cx2(self) -> float:
        """Strain at parabola-rectangle transition [-]."""
        return self._epsilon_cx2
    
    @epsilon_cx2.setter
    def epsilon_cx2(self, value: float):
        self._epsilon_cx2 = value
    
    @property
    def epsilon_cu2(self) -> float:
        """Ultimate concrete compressive strain [-]."""
        return self._epsilon_cu2
    
    @epsilon_cu2.setter
    def epsilon_cu2(self, value: float):
        self._epsilon_cu2 = value
    
    @property
    def f_yk(self) -> float:
        """Characteristic yield strength of reinforcement [MPa]."""
        return self._f_yk
    
    @f_yk.setter
    def f_yk(self, value: float):
        self._f_yk = value
    
    @property
    def E_s(self) -> float:
        """Young's modulus of steel [MPa]."""
        return self._E_s
    
    @E_s.setter
    def E_s(self, value: float):
        self._E_s = value
    
    @property
    def d(self) -> float:
        """Effective depth [m]."""
        return self._d
    
    @d.setter
    def d(self, value: float):
        self._d = value
    
    @property
    def b(self) -> float:
        """Width of cross-section [m]."""
        return self._b
    
    @b.setter
    def b(self, value: float):
        self._b = value
    
    @property
    def c_nom(self) -> float:
        """Nominal concrete cover [m]."""
        return self._c_nom
    
    @c_nom.setter
    def c_nom(self, value: float):
        self._c_nom = value
    
    @property
    def M_Ed(self) -> float:
        """Design bending moment (reference) [MN·m]."""
        return self._M_Ed
    
    @M_Ed.setter
    def M_Ed(self, value: float):
        self._M_Ed = value
    
    @property
    def N_Ed(self) -> float:
        """Design normal force (reference) [MN] (positive = tension)."""
        return self._N_Ed
    
    @N_Ed.setter
    def N_Ed(self, value: float):
        self._N_Ed = value
    
    @property
    def h(self) -> float:
        """Total height of cross-section [m]."""
        return self._d + self._c_nom
    
    @property
    def A_s(self) -> float:
        """Steel reinforcement area calculated from equilibrium [m²]."""
        if abs(self.sigma_s1) < 1e-6:
            return 0.0
        return self.F_sd / self.sigma_s1
    
    @property
    def A_s_cm2(self) -> float:
        """Steel reinforcement area [cm²]."""
        return self.A_s * 1e4
    
    # ===== Strain State Properties (USER CONTROLLED) =====
    
    @property
    def epsilon_c_top(self) -> float:
        """Top fiber concrete strain (compression) [-]."""
        return self._epsilon_c_top
    
    @epsilon_c_top.setter
    def epsilon_c_top(self, value: float):
        self._epsilon_c_top = value
    
    @property
    def epsilon_s_bottom(self) -> float:
        """Bottom fiber steel strain (tension) [-]."""
        return self._epsilon_s_bottom
    
    @epsilon_s_bottom.setter
    def epsilon_s_bottom(self, value: float):
        self._epsilon_s_bottom = value
    
    # Aliases for consistency with balanced model
    @property
    def epsilon_cu2(self) -> float:
        """Alias for epsilon_c_top (top fiber strain)."""
        return self._epsilon_c_top
    
    @property
    def epsilon_s1(self) -> float:
        """Alias for epsilon_s_bottom (steel strain)."""
        return self._epsilon_s_bottom
    
    # ===== Design Properties =====
    
    @property
    def f_cd(self) -> float:
        """Design concrete compressive strength [MPa]."""
        return 0.85 * self._f_ck / self._gamma_c
    
    @property
    def sigma_yd(self) -> float:
        """Design yield strength of reinforcement [MPa]."""
        return self._f_yk / self._gamma_s
    
    @property
    def epsilon_yd(self) -> float:
        """Yield strain of reinforcement [-]."""
        return self.sigma_yd / self._E_s
    
    # ===== Calculated State Properties =====
    
    @property
    def x(self) -> float:
        """Neutral axis position from top [m]."""
        if self.epsilon_c_top == self.epsilon_s_bottom:
            return 0.0  # Avoid division by zero
        # Linear strain profile from top to steel level (not to bottom of section)
        # Distance from top to steel: (h - c_nom) = d
        return abs(self.epsilon_c_top) / (abs(self.epsilon_c_top) + abs(self.epsilon_s_bottom)) * (self.h - self.c_nom)
    
    @property
    def k_a(self) -> float:
        """Center of gravity factor for compression zone [-]."""
        if self.epsilon_c_top == 0:
            return 0.0
        k_a, _ = self._derive.calculate_integration_parameters(
            self.epsilon_c_top, self._epsilon_cx2, self._epsilon_cu2, self.f_cd
        )
        return k_a
    
    @property
    def alpha_r(self) -> float:
        """Stress block factor for compression zone [-]."""
        if self.epsilon_c_top == 0:
            return 0.0
        _, alpha_r = self._derive.calculate_integration_parameters(
            self.epsilon_c_top, self._epsilon_cx2, self._epsilon_cu2, self.f_cd
        )
        return alpha_r
    
    @property
    def a(self) -> float:
        """Distance of compression resultant from top [m]."""
        return self.k_a * self.x
    
    @property
    def z(self) -> float:
        """Lever arm [m]."""
        return self.d - self.a
    
    @property
    def sigma_s1(self) -> float:
        """Steel stress [MPa]."""
        if self.epsilon_s_bottom <= self.epsilon_yd:
            return self.E_s * self.epsilon_s_bottom  # Elastic
        else:
            return self.sigma_yd  # Yielded
    
    @property
    def F_cd(self) -> float:
        """Concrete compression force [MN]."""
        if self.x <= 0:
            return 0.0
        return self.b * self.x * self.f_cd * self.alpha_r
    
    @property
    def F_sd(self) -> float:
        """Steel tension force from equilibrium [MN]."""
        return self.F_cd - self.N_Ed
    
    @property
    def M_Rd(self) -> float:
        """Resisting moment from current state [MN·m]."""
        return self.F_cd * self.z
    
    @property
    def M_Rds(self) -> float:
        """Alias for M_Rd for consistency."""
        return self.M_Rd
    
    @property
    def z_s1(self) -> float:
        """Distance between mid-axis and steel position [m]."""
        return self.h / 2 - self.c_nom
    
    @property
    def M_Eds(self) -> float:
        """Design moment at steel level [MN·m]."""
        return self.M_Ed + self.N_Ed * self.z_s1
    
    # ===== Equilibrium Check =====
    
    @property
    def force_imbalance(self) -> float:
        """Force equilibrium imbalance: F_cd - F_sd - N_Ed [MN]."""
        return self.F_cd - self.F_sd - self.N_Ed
    
    @property
    def moment_imbalance(self) -> float:
        """Moment equilibrium imbalance: M_Rd - M_Ed [MN·m]."""
        return self.M_Rd - self.M_Ed
    
    @property
    def is_force_balanced(self) -> bool:
        """Check if force equilibrium is satisfied (within tolerance)."""
        return abs(self.force_imbalance) < 1e-6  # 1 N tolerance
    
    @property
    def is_moment_balanced(self) -> bool:
        """Check if moment equilibrium is satisfied (within tolerance)."""
        return abs(self.moment_imbalance) < 1e-6  # 1 kNm tolerance
    
    # ===== Visualization Data Methods =====
    
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
            epsilon_c_range, self.f_cd, self._epsilon_cx2, self._epsilon_cu2
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
        """
        heights = np.array([self.h, self.h - self.x, self.c_nom])
        strains = np.array([self.epsilon_c_top, 0.0, self.epsilon_s_bottom])
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
        if self.x > 0:
            heights_c = np.linspace(self.h, self.h - self.x, n_points)
            # Distance from top for each point
            y_top = self.h - heights_c
            # Linear strain distribution
            strains_c = self.epsilon_c_top * (1 - y_top / self.x)
            stresses_c = self.get_concrete_stress_strain(strains_c)
        else:
            heights_c = np.array([])
            stresses_c = np.array([])
        
        # Steel stress (at reinforcement level = c_nom from bottom)
        heights_s = np.array([self.c_nom])
        stresses_s = np.array([self.sigma_s1])
        
        return heights_c, stresses_c, heights_s, stresses_s
    
    def summary(self) -> dict:
        """
        Get a summary of all state values.
        
        Returns:
        --------
        dict
            Dictionary with all current state values
        """
        return {
            # Geometry
            'b': self.b,
            'd': self.d,
            'h': self.h,
            'c_nom': self.c_nom,
            # Materials
            'f_ck': self.f_ck,
            'f_cd': self.f_cd,
            'f_yk': self.f_yk,
            'sigma_yd': self.sigma_yd,
            # Strain state (USER INPUT)
            'epsilon_c_top': self.epsilon_c_top,
            'epsilon_s_bottom': self.epsilon_s_bottom,
            # Steel area (CALCULATED from equilibrium)
            'A_s_cm2': self.A_s_cm2,
            # Calculated state
            'x': self.x,
            'k_a': self.k_a,
            'alpha_r': self.alpha_r,
            'a': self.a,
            'z': self.z,
            'sigma_s1': self.sigma_s1,
            # Forces
            'F_cd': self.F_cd,
            'F_sd': self.F_sd,
            'M_Rd': self.M_Rd,
            # Equilibrium check
            'N_Ed': self.N_Ed,
            'M_Ed': self.M_Ed,
            'force_imbalance': self.force_imbalance,
            'moment_imbalance': self.moment_imbalance,
            'is_force_balanced': self.is_force_balanced,
            'is_moment_balanced': self.is_moment_balanced,
        }
