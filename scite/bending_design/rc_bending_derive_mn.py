"""
RC Bending and Normal Force - Symbolic Derivation Module

This module provides symbolic derivation of closed-form solutions for reinforced
concrete cross-section analysis under combined bending and normal force.

Uses sympy to derive and lambdify analytical expressions according to Eurocode 2.

Author: Rostislav Chudoba
Course: Grundlagen der Tragwerke (Fundamentals of Structural Design)
Institution: IMB Institute, RWTH Aachen University
"""

import sympy as sp
import numpy as np
from typing import Callable, Tuple


class RCBendingDeriveMN:
    """
    Symbolic derivation engine for RC bending analysis.
    
    This class derives closed-form solutions using sympy and creates
    fast numerical evaluation functions via lambdification.
    """
    
    def __init__(self):
        """Initialize and perform symbolic derivation."""
        self._setup_symbolic_variables()
        self._define_constitutive_laws()
        self._derive_equilibrium_solutions()
        self._create_lambdified_functions()
        
    def _setup_symbolic_variables(self):
        """Define all symbolic variables and parameters."""
        # Material parameters - Concrete
        self.f_cd_sym = sp.symbols('f_cd', positive=True)
        self.epsilon_cx2_sym = sp.symbols('epsilon_cx2', negative=True)
        self.epsilon_cu2_sym = sp.symbols('epsilon_cu2', negative=True)
        
        # Material parameters - Steel
        self.sigma_yd_sym = sp.symbols('sigma_yd', positive=True)
        self.E_s_sym = sp.symbols('E_s', positive=True)
        
        # Geometry parameters
        self.d_sym = sp.symbols('d', positive=True)
        self.b_sym = sp.symbols('b', positive=True)
        self.c_nom_sym = sp.symbols('c_nom', positive=True)
        
        # Integration parameters (EC2 stress block)
        self.k_a_sym = sp.symbols('k_a', positive=True)
        self.alpha_r_sym = sp.symbols('alpha_r', positive=True)
        
        # State variables (unknowns)
        self.epsilon_s1_sym = sp.symbols('epsilon_s1', nonnegative=True)
        self.epsilon_c2_sym = sp.symbols('epsilon_c2', nonpositive=True)
        
        # Loading
        self.M_Ed_sym = sp.symbols('M_Ed', positive=True)
        self.N_Ed_sym = sp.symbols('N_Ed')
        
    def _define_constitutive_laws(self):
        """Define EC2 constitutive laws symbolically."""
        # Concrete stress-strain (EC2 parabola-rectangle)
        epsilon_c = sp.symbols('epsilon_c', nonpositive=True)
        sigma_c1 = -self.f_cd_sym * (1 - (1 - epsilon_c / self.epsilon_cx2_sym)**2)
        self.sigma_c_sym = sp.Piecewise(
            (0, epsilon_c < self.epsilon_cu2_sym),
            (-self.f_cd_sym, epsilon_c < self.epsilon_cx2_sym),
            (sigma_c1, epsilon_c < 0),
            (0, True)
        )
        
    def _derive_equilibrium_solutions(self):
        """Derive closed-form solutions for cross-section analysis."""
        # Neutral axis position (from linear strain distribution)
        self.x_sym = self.epsilon_c2_sym / (self.epsilon_c2_sym - self.epsilon_s1_sym) * self.d_sym
        
        # Compression zone center of gravity distance from top
        self.a_sym = self.k_a_sym * self.x_sym
        
        # Lever arm
        self.z_sym = self.d_sym - self.a_sym
        
        # Concrete compression force
        self.F_cd_sym = self.b_sym * self.x_sym * self.f_cd_sym * self.alpha_r_sym
        
        # Resisting moment
        self.M_Rds_sym = self.F_cd_sym * self.z_sym
        
        # Reinforcement position from section center
        self.z_s1_sym = (self.d_sym + self.c_nom_sym) / 2 - self.c_nom_sym
        
        # Applied moment with normal force eccentricity
        self.M_Eds_sym = self.M_Ed_sym - self.N_Ed_sym * self.z_s1_sym
        
        # Solve moment equilibrium for epsilon_s1
        M_eq = sp.Eq(self.M_Rds_sym, self.M_Eds_sym)
        epsilon_s1_solutions = sp.solve(M_eq, self.epsilon_s1_sym)
        self.epsilon_s1_solved_sym = sp.simplify(epsilon_s1_solutions[0])
        
        # Steel force from force equilibrium
        F_cd_solved = sp.simplify(
            self.F_cd_sym.subs({self.epsilon_s1_sym: self.epsilon_s1_solved_sym})
        )
        self.F_sd_solved_sym = F_cd_solved + self.N_Ed_sym
        
        # Required reinforcement area
        self.A_s_sym = sp.simplify(self.F_sd_solved_sym / self.sigma_yd_sym)
        
    def _create_lambdified_functions(self):
        """Convert symbolic expressions to fast numerical functions."""
        # Primary unknown: reinforcement strain
        self.get_epsilon_s1 = sp.lambdify(
            (self.M_Ed_sym, self.N_Ed_sym, self.d_sym, self.b_sym, self.c_nom_sym,
             self.f_cd_sym, self.k_a_sym, self.alpha_r_sym, self.epsilon_c2_sym),
            self.epsilon_s1_solved_sym, 'numpy'
        )
        
        # Geometric properties
        self.get_x = sp.lambdify(
            (self.d_sym, self.epsilon_c2_sym, self.epsilon_s1_sym),
            self.x_sym, 'numpy'
        )
        
        self.get_a = sp.lambdify(
            (self.d_sym, self.k_a_sym, self.epsilon_c2_sym, self.epsilon_s1_sym),
            self.a_sym, 'numpy'
        )
        
        self.get_z = sp.lambdify(
            (self.d_sym, self.k_a_sym, self.epsilon_c2_sym, self.epsilon_s1_sym),
            self.z_sym, 'numpy'
        )
        
        # Force resultants
        self.get_F_cd = sp.lambdify(
            (self.d_sym, self.b_sym, self.alpha_r_sym, self.f_cd_sym,
             self.epsilon_s1_sym, self.epsilon_c2_sym),
            self.F_cd_sym, 'numpy'
        )
        
        self.get_M_Rds = sp.lambdify(
            (self.d_sym, self.b_sym, self.f_cd_sym, self.k_a_sym, self.alpha_r_sym,
             self.epsilon_c2_sym, self.epsilon_s1_sym),
            self.M_Rds_sym, 'numpy'
        )
        
        # Required reinforcement
        self.get_A_s = sp.lambdify(
            (self.M_Ed_sym, self.N_Ed_sym, self.d_sym, self.k_a_sym, self.c_nom_sym,
             self.b_sym, self.sigma_yd_sym, self.f_cd_sym, self.alpha_r_sym),
            self.A_s_sym, 'numpy'
        )
        
        # Concrete stress-strain relationship
        epsilon_c = sp.symbols('epsilon_c', nonpositive=True)
        self.get_sigma_c = sp.lambdify(
            (epsilon_c, self.f_cd_sym, self.epsilon_cx2_sym, self.epsilon_cu2_sym),
            self.sigma_c_sym, 'numpy'
        )
        
    def calculate_integration_parameters(self, epsilon_c2: float, epsilon_cx2: float,
                                        epsilon_cu2: float, f_cd: float) -> Tuple[float, float]:
        """
        Calculate EC2 stress block integration parameters k_a and alpha_r.
        
        Parameters:
        -----------
        epsilon_c2 : float
            Top fiber strain (typically epsilon_cu2) [-]
        epsilon_cx2 : float
            Parabola-rectangle transition strain [-]
        epsilon_cu2 : float
            Ultimate concrete strain [-]
        f_cd : float
            Design concrete strength [MPa]
            
        Returns:
        --------
        Tuple[float, float]
            k_a: center of gravity factor, alpha_r: stress block factor
        """
        if epsilon_c2 == 0:
            return 0.0, 0.0
        
        # Define symbolic variable
        epsilon_c = sp.symbols('epsilon_c', nonpositive=True)
        
        # EC2 stress-strain
        sigma_c1 = -f_cd * (1 - (1 - epsilon_c / epsilon_cx2)**2)
        sigma_c = sp.Piecewise(
            (0, epsilon_c < epsilon_cu2),
            (-f_cd, epsilon_c < epsilon_cx2),
            (sigma_c1, epsilon_c < 0),
            (0, True)
        )
        
        # Integrate for force and moment
        f_cd_eps = sp.integrate(sigma_c, (epsilon_c, 0, epsilon_c2))
        m_cd_eps = sp.integrate(sigma_c * epsilon_c, (epsilon_c, 0, epsilon_c2))
        
        # Solve for k_a
        k_a_sym = sp.symbols('k_a')
        k_a_eq = sp.Eq(f_cd_eps * (1 - k_a_sym) * epsilon_c2, m_cd_eps)
        k_a_solved = sp.solve(k_a_eq, k_a_sym)[0]
        k_a = float(k_a_solved)
        
        # Solve for alpha_r
        alpha_r_sym = sp.symbols('alpha_r')
        alpha_r_eq = sp.Eq(-alpha_r_sym * f_cd * epsilon_c2, f_cd_eps)
        alpha_r_solved = sp.solve(alpha_r_eq, alpha_r_sym)[0]
        alpha_r = float(alpha_r_solved)
        
        return k_a, alpha_r
    
    def get_integration_parameter_profiles(self, epsilon_cx2: float, epsilon_cu2: float,
                                          f_cd: float, n_points: int = 100) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate k_a and alpha_r profiles for a range of strain values.
        
        Parameters:
        -----------
        epsilon_cx2 : float
            Parabola-rectangle transition strain [-]
        epsilon_cu2 : float
            Ultimate concrete strain [-]
        f_cd : float
            Design concrete strength [MPa]
        n_points : int
            Number of points for the profile
            
        Returns:
        --------
        Tuple[np.ndarray, np.ndarray, np.ndarray]
            epsilon_c_range, k_a_values, alpha_r_values
        """
        epsilon_c_range = np.linspace(-0.0035, -0.00001, n_points)
        k_a_values = np.zeros(n_points)
        alpha_r_values = np.zeros(n_points)
        
        for i, eps_c in enumerate(epsilon_c_range):
            k_a_values[i], alpha_r_values[i] = self.calculate_integration_parameters(
                eps_c, epsilon_cx2, epsilon_cu2, f_cd
            )
        
        return epsilon_c_range, k_a_values, alpha_r_values
