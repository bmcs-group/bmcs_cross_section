"""
Normal Force - Moment Assessment State
=======================================

State holder for N-M assessment with manual strain control.

Unlike M-κ analysis which solves equilibrium automatically, this module
allows manual exploration of strain states to understand equilibrium behavior.

Pattern follows rc_bending_unbalanced_model - user adjusts strains manually
to explore equilibrium with imposed design loads (N_Ed, M_Ed).

The user iteratively adjusts eps_top and eps_bot to find a state where:
- N_actual ≈ N_Ed (force equilibrium)
- M_actual ≥ M_Ed (moment capacity)
"""

from typing import Tuple

import numpy as np

from scite.core import BMCSModel, ui_field
from scite.cs_design import CrossSection
from scite.cs_design.cs_stress_strain_profile import StressStrainProfile


class NMAssessment(BMCSModel):
    """
    N-M assessment state holder for manual strain exploration.
    
    Represents a single strain state with imposed design loads.
    User manually adjusts eps_top and eps_bot to explore equilibrium.
    
    State parameters (adjustable):
    - eps_top: Top fiber strain [-]
    - eps_bot: Bottom fiber strain [-]
    
    Design loads (imposed):
    - N_Ed: Design axial force [kN] (positive = tension)
    - M_Ed: Design bending moment [kNm]
    
    Computed values:
    - N_actual: Actual axial force from current strain state [kN]
    - M_actual: Actual moment from current strain state [kNm]
    - Equilibrium errors: ΔN = N_actual - N_Ed, ΔM = M_actual - M_Ed
    
    Attributes:
        cs: CrossSection with geometry, concrete, and reinforcement
        eps_top: Top fiber strain (adjustable) [-]
        eps_bot: Bottom fiber strain (adjustable) [-]
        N_Ed: Design axial force (imposed) [kN]
        M_Ed: Design bending moment (imposed) [kNm]
    """
    
    cs: CrossSection
    
    # Strain state (adjustable by user)
    eps_top: float = ui_field(
        -0.0035,
        label=r"$\varepsilon_{top}$",
        unit="-",
        range=(-0.010, 0.005),
        description="Top fiber strain (typically compression)"
    )
    
    eps_bot: float = ui_field(
        0.0025,
        label=r"$\varepsilon_{bot}$",
        unit="-",
        range=(-0.005, 0.020),
        description="Bottom fiber strain (tension or compression)"
    )
    
    # Design loads (imposed)
    N_Ed: float = ui_field(
        0.0,
        label="N_Ed",
        unit="kN",
        range=(-5000.0, 5000.0),
        description="Design axial force (positive = tension)"
    )
    
    M_Ed: float = ui_field(
        200.0,
        label="M_Ed",
        unit="kN·m",
        range=(0.0, 2000.0),
        description="Design bending moment"
    )
    
    @property
    def kappa(self) -> float:
        """
        Curvature from plane section kinematics [1/mm].
        
        Strain distribution: ε(z) = eps_bot - κ×z
        At top (z=h): eps_top = eps_bot - κ×h
        Therefore: κ = (eps_bot - eps_top) / h
        """
        return (self.eps_bot - self.eps_top) / self.cs.h_total
    
    @property
    def profile(self) -> StressStrainProfile:
        """
        Stress-strain profile for current strain state.
        
        Returns:
            StressStrainProfile instance
        """
        return StressStrainProfile(
            cs=self.cs,
            kappa=self.kappa,
            eps_bottom=self.eps_bot
        )
    
    def get_forces(self) -> Tuple[float, float, float, float]:
        """
        Compute force resultants for current strain state.
        
        Returns:
            (F_c, F_s, N_actual, M_actual): Concrete force, steel force, 
                                             total axial force [kN], moment [kNm]
        """
        F_c, F_s, N_total, M_total = self.profile.get_force_resultants()
        
        # Convert from N to kN, N·mm to kN·m
        N_actual = N_total / 1000.0
        M_actual = M_total / 1e6
        
        return F_c, F_s, N_actual, M_actual
    
    @property
    def N_actual(self) -> float:
        """Actual axial force from current strain state [kN]."""
        _, _, N, _ = self.get_forces()
        return N
    
    @property
    def M_actual(self) -> float:
        """Actual moment from current strain state [kNm]."""
        _, _, _, M = self.get_forces()
        return M
    
    @property
    def N_error(self) -> float:
        """
        Axial force equilibrium error [kN].
        
        ΔN = N_actual - N_Ed
        
        Target: ΔN ≈ 0 for equilibrium
        """
        return self.N_actual - self.N_Ed
    
    @property
    def M_error(self) -> float:
        """
        Moment equilibrium error [kNm].
        
        ΔM = M_actual - M_Ed
        
        Target: ΔM ≥ 0 (M_actual ≥ M_Ed) for safety
        """
        return self.M_actual - self.M_Ed
    
    @property
    def utilization(self) -> float:
        """
        Utilization ratio: M_Ed / M_actual.
        
        Returns:
            Utilization [-] (< 1.0 = safe, > 1.0 = overstressed)
        """
        if abs(self.M_actual) < 1e-6:
            return np.inf
        return self.M_Ed / self.M_actual
    
    @property
    def is_equilibrium(self) -> bool:
        """
        Check if current state satisfies equilibrium.
        
        Criteria:
        - |N_error| < 1.0 kN (force equilibrium)
        - M_error ≥ 0 (moment capacity)
        
        Returns:
            True if equilibrium is satisfied
        """
        return abs(self.N_error) < 1.0 and self.M_error >= 0
    
    @property
    def is_safe(self) -> bool:
        """
        Check if cross-section is safe.
        
        Returns:
            True if utilization ≤ 1.0 and equilibrium is satisfied
        """
        return self.is_equilibrium and self.utilization <= 1.0
    
    def summary(self) -> dict:
        """
        Get assessment summary.
        
        Returns:
            Dictionary with all state information
        """
        return {
            # Strain state
            'eps_top': self.eps_top,
            'eps_bot': self.eps_bot,
            'kappa': self.kappa,
            # Design loads
            'N_Ed': self.N_Ed,
            'M_Ed': self.M_Ed,
            # Actual forces
            'N_actual': self.N_actual,
            'M_actual': self.M_actual,
            # Equilibrium errors
            'N_error': self.N_error,
            'M_error': self.M_error,
            'utilization': self.utilization,
            # Status
            'is_equilibrium': self.is_equilibrium,
            'is_safe': self.is_safe,
            # Cross-section
            'b': self.cs.shape.b if hasattr(self.cs.shape, 'b') else None,
            'h': self.cs.h_total,
            'f_ck': self.cs.concrete.f_ck if hasattr(self.cs.concrete, 'f_ck') else None,
        }


def create_default_nm_assessment() -> NMAssessment:
    """
    Create a default NM assessment for testing.
    
    Returns:
        NMAssessment with rectangular section and standard reinforcement
    """
    from scite.cs_design.reinforcement import (ReinforcementLayer,
                                               ReinforcementLayout)
    from scite.cs_design.shapes import RectangularShape
    from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
    from scite.matmod.steel_reinforcement import SteelReinforcement

    # Create rectangular section 300x500 mm
    shape = RectangularShape(b=300.0, h=500.0)
    
    # C30/37 concrete (design values)
    concrete = EC2ParabolaRectangle(f_ck=30.0, alpha_cc=0.85, gamma_c=1.5)
    
    # Steel reinforcement: 4Ø20 at bottom (z=50mm), 2Ø16 at top (z=450mm)
    steel_mat = SteelReinforcement(f_sy=500.0)
    
    layer_bottom = ReinforcementLayer(
        z=50.0,
        A_s=1256.6,  # 4Ø20 = 4×π×10²
        material=steel_mat
    )
    
    layer_top = ReinforcementLayer(
        z=450.0,
        A_s=402.1,   # 2Ø16 = 2×π×8²
        material=steel_mat
    )
    
    reinforcement = ReinforcementLayout(layers=[layer_bottom, layer_top])
    
    # Assemble cross-section
    cs = CrossSection(
        shape=shape,
        concrete=concrete,
        reinforcement=reinforcement
    )
    
    # Create assessment with default state
    return NMAssessment(
        cs=cs,
        eps_top=-0.0035,  # EC2 ultimate compressive strain
        eps_bot=0.0025,   # Typical steel yielding strain
        N_Ed=0.0,         # Pure bending
        M_Ed=200.0        # 200 kNm design moment
    )
