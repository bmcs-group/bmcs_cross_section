"""
ContinuousBeamVarCS / ContinuousBeamVarCSModes
================================================

Factory classes for a two-span RC continuous beam with segmented longitudinal
reinforcement (variable cross-section along the span).

Purpose
-------
Reproduces EC2's assumption of a singly-reinforced hogging section by assigning
different cross-sections to each zone of each span:

  Left span (0 → L_a):
    [0,      2/3·L_a)  → cs_lower  — bottom bars only (sagging zone)
    [2/3·L_a, 5/6·L_a) → cs_both  — both layers (anchorage/transition zone)
    [5/6·L_a, L_a]    → cs_upper  — top bars only (hogging zone)

  Right span (0 → L_b):
    [0,      1/6·L_b)  → cs_upper  — top bars only (hogging zone at interior support)
    [1/6·L_b, 1/3·L_b) → cs_both  — anchorage/transition zone
    [1/3·L_b, L_b]    → cs_lower  — bottom bars only (sagging zone)

Usage — single mode
-------------------
>>> factory = ContinuousBeamVarCS(
...     b=300, h=700,
...     A_s_bot=1257, z_s_bot=50,
...     A_s_top=1610, z_s_top=650,
...     f_ck=30, f_yk=500,
...     L_a=6000, L_b=6000,
... )
>>> cba = factory.cba      # ContinuousBeamAnalysis instance (design factors by default)

Usage — design / characteristic / mean triple
---------------------------------------------
>>> triple = ContinuousBeamVarCSModes.for_rc(
...     b=300, h=700,
...     A_s_bot=1257, z_s_bot=50,
...     A_s_top=1610, z_s_top=650,
...     f_ck=30, f_yk=500,
...     L_a=6000, L_b=6000,
... )
>>> cba_d = triple.design
>>> cba_m = triple.mean
>>> for cba, color, suffix in triple.iter_modes():
...     cba.plot_kappa_profile_at_step(ax, color=color, label_suffix=suffix)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Iterator, Tuple

from scite.beam.bending.beam_deflection_var_cs import BeamDeflectionVarCS
from scite.beam.continuous.continuous_beam import ContinuousBeamAnalysis
from scite.cs_design import (
    CrossSection,
    RectangularShape,
    ReinforcementLayer,
    ReinforcementLayout,
)
from scite.matmod.ec2_concrete import EC2Concrete
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.matmod.steel_reinforcement import SteelReinforcement


def _build_var_cs_cba(
    b: float,
    h: float,
    A_s_bot: float,
    z_s_bot: float,
    A_s_top: float,
    z_s_top: float,
    concrete,
    steel: SteelReinforcement,
    L_a: float,
    L_b: float,
    n_kappa: int = 150,
    n_load_steps: int = 41,
) -> Tuple[ContinuousBeamAnalysis, CrossSection, CrossSection, CrossSection]:
    """
    Build a variable-CS ContinuousBeamAnalysis from material objects.

    Returns
    -------
    cba        : ContinuousBeamAnalysis
    cs_lower   : bottom-bars-only CrossSection
    cs_both    : doubly-reinforced CrossSection
    cs_upper   : top-bars-only CrossSection
    """
    shape = RectangularShape(b=b, h=h)
    layer_bot = ReinforcementLayer(z=z_s_bot, A_s=A_s_bot, material=steel)
    layer_top = ReinforcementLayer(z=z_s_top, A_s=A_s_top, material=steel)

    cs_lower = CrossSection(
        shape=shape, concrete=concrete,
        reinforcement=ReinforcementLayout(layers=[layer_bot]),
    )
    cs_both = CrossSection(
        shape=shape, concrete=concrete,
        reinforcement=ReinforcementLayout(layers=[layer_bot, layer_top]),
    )
    cs_upper = CrossSection(
        shape=shape, concrete=concrete,
        reinforcement=ReinforcementLayout(layers=[layer_top]),
    )

    kw = dict(n_kappa=n_kappa, n_load_steps=n_load_steps, solve_mode='both')
    shared_mk_cache: dict = {}

    segs_a = [
        (0.0,          2 / 3 * L_a,  cs_lower),
        (2 / 3 * L_a,  5 / 6 * L_a,  cs_both),
        (5 / 6 * L_a,  L_a,           cs_upper),
    ]
    segs_b = [
        (0.0,          1 / 6 * L_b,  cs_upper),
        (1 / 6 * L_b,  1 / 3 * L_b,  cs_both),
        (1 / 3 * L_b,  L_b,           cs_lower),
    ]

    span_left = BeamDeflectionVarCS.from_segments(
        segs_a, L=L_a, mk_cache=shared_mk_cache, **kw)
    span_right = BeamDeflectionVarCS.from_segments(
        segs_b, L=L_b, mk_cache=shared_mk_cache, **kw)

    cba = ContinuousBeamAnalysis(span_left=span_left, span_right=span_right, q=1.0)
    return cba, cs_lower, cs_both, cs_upper


class ContinuousBeamVarCS:
    """
    Factory: two-span RC continuous beam with segmented longitudinal reinforcement.

    Parameters
    ----------
    b, h : float
        Section width and height [mm].
    A_s_bot, z_s_bot : float
        Bottom reinforcement area [mm²] and centroid position from bottom [mm].
    A_s_top, z_s_top : float
        Top reinforcement area [mm²] and centroid position from bottom [mm].
    f_ck : float
        Characteristic concrete compressive strength [MPa].
    f_yk : float
        Characteristic steel yield strength [MPa].
    L_a, L_b : float
        Left and right span lengths [mm].
    gamma_c, gamma_s, alpha_cc : float
        EC2 partial factors and effectiveness factor (design mode defaults).
    n_kappa : int
        Curvature steps for each M-κ solver.
    n_load_steps : int
        Load increments for the sweep.
    """

    def __init__(
        self,
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
        gamma_c: float = 1.5,
        gamma_s: float = 1.15,
        alpha_cc: float = 0.85,
        n_kappa: int = 150,
        n_load_steps: int = 41,
    ) -> None:
        concrete = EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c)
        steel = SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s)

        self._cba, self.cs_lower, self.cs_both, self.cs_upper = _build_var_cs_cba(
            b, h, A_s_bot, z_s_bot, A_s_top, z_s_top,
            concrete, steel, L_a, L_b, n_kappa, n_load_steps,
        )
        self.span_left = self._cba.span_left
        self.span_right = self._cba.span_right

    @cached_property
    def cba(self) -> ContinuousBeamAnalysis:
        """ContinuousBeamAnalysis wrapping the two variable-CS spans."""
        return self._cba


@dataclass
class ContinuousBeamVarCSModes:
    """Design / characteristic / mean triple for a two-span RC continuous beam
    with segmented longitudinal reinforcement.

    Fields
    ------
    design         : γ_c=1.5, γ_s=1.15, α_cc=0.85  — ULS capacity
    characteristic : γ_c=1.0, γ_s=1.0,  α_cc=1.0   — code SLS / characteristic
    mean           : EC2Concrete (f_cm), γ_s=1.0    — realistic prediction

    Example
    -------
    triple = ContinuousBeamVarCSModes.for_rc(
        b=300, h=700,
        A_s_bot=1257, z_s_bot=50,
        A_s_top=1610, z_s_top=650,
        f_ck=30, f_yk=500,
        L_a=6000, L_b=6000,
    )
    cba_d = triple.design
    cba_m = triple.mean
    for cba, color, suffix in triple.iter_modes():
        cba.plot_kappa_profile_at_step(ax, color=color, label_suffix=suffix,
                                       show_annotations=False)
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
        """Yield ``(cba, color, label_suffix)`` for each mode in display order."""
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
    ) -> 'ContinuousBeamVarCSModes':
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
        n_kappa         : curvature steps for each M-κ solver
        n_load_steps    : load steps for the CBA sweep
        """
        geom = dict(b=b, h=h, A_s_bot=A_s_bot, z_s_bot=z_s_bot,
                    A_s_top=A_s_top, z_s_top=z_s_top, L_a=L_a, L_b=L_b,
                    n_kappa=n_kappa, n_load_steps=n_load_steps)

        # B500B mean values per EC2 §5.7(NA.10): f_yR = 1.1·f_yk
        k_ductility = SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s).f_tk / f_yk
        f_yk_mean   = 1.1 * f_yk
        f_tk_mean   = k_ductility * f_yk_mean

        cba_d, *_    = _build_var_cs_cba(
            concrete=EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c),
            steel=SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s),
            **geom,
        )
        cba_char, *_ = _build_var_cs_cba(
            concrete=EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=1.0, gamma_c=1.0),
            steel=SteelReinforcement(f_yk=f_yk, gamma_s=1.0),
            **geom,
        )
        cba_mean, *_ = _build_var_cs_cba(
            concrete=EC2Concrete(f_ck=f_ck, factor=1.0),
            steel=SteelReinforcement(f_yk=f_yk_mean, f_tk=f_tk_mean, gamma_s=1.0),
            **geom,
        )

        return cls(design=cba_d, characteristic=cba_char, mean=cba_mean)
