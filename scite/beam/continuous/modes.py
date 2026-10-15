"""
scite.beam.continuous.modes
============================

ContinuousBeamModes — design / characteristic / mean triple for a two-span
RC continuous beam, analogous to FloorAnalysisPair for floor cross-sections.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Tuple

from scite.beam.bending.beam_deflection import BeamDeflectionAnalysis
from scite.beam.continuous.continuous_beam import ContinuousBeamAnalysis
from scite.cs_design import (
    CrossSection,
    RectangularShape,
    ReinforcementLayer,
    ReinforcementLayout,
)
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.matmod.ec2_concrete import EC2Concrete
from scite.matmod.steel_reinforcement import SteelReinforcement


@dataclass
class ContinuousBeamModes:
    """Design / characteristic / mean triple for a two-span RC continuous beam.

    Fields
    ------
    design         : γ_c=1.5, γ_s=1.15, α_cc=0.85  — ULS capacity
    characteristic : γ_c=1.0, γ_s=1.0,  α_cc=1.0   — code SLS / characteristic
    mean           : EC2Concrete (f_cm), γ_s=1.0    — realistic prediction

    Example
    -------
    triple = ContinuousBeamModes.for_rc(
        b=300, h=700,
        A_s_bot=1257, z_s_bot=50,
        A_s_top=1610, z_s_top=650,
        f_ck=30, f_yk=500,
        L_a=6000, L_b=6000,
    )
    fig, (ax_q, ax_m) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for cba, color, suffix in triple.iter_modes():
        cba.plot_q_kappa(ax_q, color=color, label_suffix=suffix, show_annotations=False)
        cba.plot_M_kappa(ax_m, color=color, label_suffix=suffix, show_annotations=False)
    ax_q.legend(); ax_m.legend(); plt.tight_layout()
    """

    design: ContinuousBeamAnalysis
    characteristic: ContinuousBeamAnalysis
    mean: ContinuousBeamAnalysis

    COLORS = {
        'design':         '#d62728',   # red
        'characteristic': '#1f77b4',   # blue
        'mean':           '#2ca02c',   # green
    }

    def iter_modes(self) -> Iterator[Tuple[ContinuousBeamAnalysis, str, str]]:
        """Yield ``(cba, color, label_suffix)`` for each mode in display order.

        Intended for overlay loops::

            for cba, color, suffix in triple.iter_modes():
                cba.plot_q_kappa(ax, color=color, label_suffix=suffix,
                                 show_annotations=False)
        """
        for name, cba in [
            ('design',         self.design),
            ('characteristic', self.characteristic),
            ('mean',           self.mean),
        ]:
            yield cba, self.COLORS[name], f'  ({name})'

    @classmethod
    def for_rc(
        cls,
        b: float,
        h: float,
        A_s_bot: float,
        z_s_bot: float,
        A_s_top: float,
        z_s_top: float,
        f_ck: float,
        f_yk: float,
        L_a: float,
        L_b: float,
        *,
        gamma_c: float = 1.5,
        gamma_s: float = 1.15,
        alpha_cc: float = 0.85,
        n_kappa: int = 150,
        n_load_steps: int = 41,
    ) -> 'ContinuousBeamModes':
        """Build design / characteristic / mean triple for a rectangular RC section.

        Parameters
        ----------
        b, h            : section width and height [mm]
        A_s_bot, z_s_bot: bottom reinforcement area [mm²] and centroid height [mm]
        A_s_top, z_s_top: top reinforcement area [mm²] and centroid height [mm]
        f_ck            : concrete characteristic strength [MPa]
        f_yk            : steel characteristic yield strength [MPa]
        L_a, L_b        : left and right span lengths [mm]
        gamma_c         : design concrete partial factor (default 1.5)
        gamma_s         : design steel partial factor (default 1.15)
        alpha_cc        : design concrete effectiveness factor (default 0.85)
        n_kappa         : number of curvature steps for the M-κ sweep
        n_load_steps    : number of load steps for BeamDeflectionAnalysis
        """

        def _cs(concrete, steel_mat: SteelReinforcement) -> CrossSection:
            return CrossSection(
                shape=RectangularShape(b=b, h=h),
                concrete=concrete,
                reinforcement=ReinforcementLayout(layers=[
                    ReinforcementLayer(z=z_s_bot, A_s=A_s_bot, material=steel_mat),
                    ReinforcementLayer(z=z_s_top, A_s=A_s_top, material=steel_mat),
                ]),
            )

        def _bda(cs: CrossSection, L: float) -> BeamDeflectionAnalysis:
            return BeamDeflectionAnalysis(
                cs=cs, L=L, load_type='dist',
                n_kappa=n_kappa, n_load_steps=n_load_steps,
                solve_mode='both',
            )

        def _cba(cs: CrossSection) -> ContinuousBeamAnalysis:
            bda_a = _bda(cs, L_a)
            bda_b = bda_a if L_a == L_b else _bda(cs, L_b)
            return ContinuousBeamAnalysis(span_left=bda_a, span_right=bda_b, q=1.0)

        # B500B mean values per EC2 §5.7(NA.10): f_yR = 1.1·f_yk, f_tR = 1.08·f_yR
        k_ductility = SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s).f_tk / f_yk
        f_yk_mean   = 1.1 * f_yk
        f_tk_mean   = k_ductility * f_yk_mean

        steel_d    = SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s)
        steel_char = SteelReinforcement(f_yk=f_yk, gamma_s=1.0)
        steel_mean = SteelReinforcement(f_yk=f_yk_mean, f_tk=f_tk_mean, gamma_s=1.0)

        cs_d    = _cs(EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c),
                      steel_d)
        cs_char = _cs(EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=1.0, gamma_c=1.0), steel_char)
        cs_mean = _cs(EC2Concrete(f_ck=f_ck, factor=1.0), steel_mean)

        return cls(
            design=_cba(cs_d),
            characteristic=_cba(cs_char),
            mean=_cba(cs_mean),
        )
