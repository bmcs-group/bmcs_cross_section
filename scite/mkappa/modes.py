"""
scite.mkappa.modes
==================

MKappaModes — design / characteristic / mean triple for a rectangular RC
cross-section, parallel to ContinuousBeamModes but at the M-κ level.

Mode control lives entirely in the CrossSection (concrete + steel material
objects).  MKappaAnalysis itself is mode-agnostic.

Example
-------
triple = MKappaModes.for_rc(
    b=300, h=600,
    A_s_bot=1257, z_s_bot=50,
    A_s_top=1257, z_s_top=550,
    f_ck=30, f_yk=500,
)
fig, ax = plt.subplots(figsize=(10, 5))
for mk, color, label in triple.iter_modes():
    mk.plot_mk(ax=ax, color=color, label=label,
               show_failure_marker=True, show_full_range=True)
ax.legend(); plt.tight_layout(); plt.show()
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Tuple

from scite.cs_design import (
    CrossSection,
    RectangularShape,
    ReinforcementLayer,
    ReinforcementLayout,
)
from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
from scite.matmod.steel_reinforcement import SteelReinforcement

from .mkappa import MKappaAnalysis


@dataclass
class MKappaModes:
    """Design / characteristic / mean M-κ triple for a rectangular RC section.

    Fields
    ------
    All three modes use EC2ParabolaRectangle; only partial factors differ.

    design         : f_ck,  α_cc=0.85, γ_c=1.5, γ_s=1.15  — ULS capacity
    characteristic : f_ck,  α_cc=1.0,  γ_c=1.0, γ_s=1.0   — code characteristic
    mean           : f_cm=f_ck+8, α_cc=1.0, γ_c=1.0, γ_s=1.0 — realistic prediction
                     Steel per EC2 §5.7(NA.10): f_yR=1.1·f_yk (B500B)
    """

    design: MKappaAnalysis
    characteristic: MKappaAnalysis
    mean: MKappaAnalysis

    COLORS = {
        'design':         '#d62728',   # red
        'characteristic': '#1f77b4',   # blue
        'mean':           '#2ca02c',   # green
    }

    def iter_modes(self) -> Iterator[Tuple[MKappaAnalysis, str, str]]:
        """Yield ``(mk, color, label)`` for each mode in display order.

        Intended for overlay loops::

            for mk, color, label in triple.iter_modes():
                mk.plot_mk(ax, color=color, label=label,
                           show_full_range=True, show_failure_marker=True)
        """
        for name, mk in [
            ('design',         self.design),
            ('characteristic', self.characteristic),
            ('mean',           self.mean),
        ]:
            yield mk, self.COLORS[name], f'M-κ  ({name})'

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
        *,
        gamma_c: float = 1.5,
        gamma_s: float = 1.15,
        alpha_cc: float = 0.85,
        n_kappa: int = 150,
        solve_mode: str = 'both',
        N_Ed: float = 0.0,
    ) -> 'MKappaModes':
        """Build design / characteristic / mean M-κ triple.

        Parameters
        ----------
        b, h            : section width and height [mm]
        A_s_bot, z_s_bot: bottom reinforcement area [mm²] and centroid [mm]
        A_s_top, z_s_top: top reinforcement area [mm²] and centroid [mm]
        f_ck            : concrete characteristic strength [MPa]
        f_yk            : steel characteristic yield strength [MPa]
        gamma_c         : design concrete partial factor (default 1.5)
        gamma_s         : design steel partial factor (default 1.15)
        alpha_cc        : design concrete effectiveness factor (default 0.85)
        n_kappa         : curvature resolution (default 150)
        solve_mode      : 'positive', 'negative', or 'both' (default 'both')
        N_Ed            : design axial force [kN] (default 0)
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

        def _mk(cs: CrossSection) -> MKappaAnalysis:
            mk = MKappaAnalysis(cs=cs, n_kappa=n_kappa, N_Ed=N_Ed, solve_mode=solve_mode)
            mk.solve()
            return mk

        # B500B mean per EC2 §5.7(NA.10): f_yR = 1.1·f_yk, k = f_tk/f_yk preserved
        k_ductility = SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s).f_tk / f_yk
        f_yk_mean   = 1.1 * f_yk
        f_tk_mean   = k_ductility * f_yk_mean

        steel_d    = SteelReinforcement(f_yk=f_yk, gamma_s=gamma_s)
        steel_char = SteelReinforcement(f_yk=f_yk, gamma_s=1.0)
        steel_mean = SteelReinforcement(f_yk=f_yk_mean, f_tk=f_tk_mean, gamma_s=1.0)

        f_cm    = f_ck + 8.0   # mean compressive strength [MPa]

        cs_d    = _cs(EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=alpha_cc, gamma_c=gamma_c), steel_d)
        cs_char = _cs(EC2ParabolaRectangle(f_ck=f_ck, alpha_cc=1.0,      gamma_c=1.0),    steel_char)
        cs_mean = _cs(EC2ParabolaRectangle(f_ck=f_cm,  alpha_cc=1.0,      gamma_c=1.0),    steel_mean)

        return cls(
            design=_mk(cs_d),
            characteristic=_mk(cs_char),
            mean=_mk(cs_mean),
        )
