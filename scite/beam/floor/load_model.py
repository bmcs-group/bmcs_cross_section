"""
scite.beam.floor.load_model
============================

LoadModel — EN 1990 surface load combination for floor systems.

A pure Python dataclass: no CFrame, no Pydantic — usable in notebooks and
standalone scripts without any widget framework.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BLUE = '#1f77b4'
RED  = '#d62728'


@dataclass
class LoadModel:
    """EN 1990 surface load combination model for floor systems.

    Parameters
    ----------
    delta_g_k : additional permanent load (finishes, partitions) [kN/m²]
    q_k       : characteristic variable service load [kN/m²]
    psi_2     : quasi-permanent combination factor ψ₂  (EN 1990 Table A1.1)
    gamma_G   : permanent load factor γ_G  (ULS, EN 1990 Table A1.2)
    gamma_Q   : variable load factor  γ_Q  (ULS, EN 1990 Table A1.2)
    gamma_c   : concrete partial safety factor (EC2, default 1.50)
    gamma_s   : steel partial safety factor    (EC2, default 1.15)
    gamma_f   : CFRP partial safety factor     (fib TR, default 1.25)
    """

    delta_g_k: float = 2.0
    q_k:       float = 5.0
    psi_2:     float = 0.30
    gamma_G:   float = 1.35
    gamma_Q:   float = 1.50
    gamma_c:   float = 1.50
    gamma_s:   float = 1.15
    gamma_f:   float = 1.25

    # ── Core combination ──────────────────────────────────────────────────────

    def surface_loads(self, g_k: float) -> dict:
        """Return all load levels in kN/m².

        Parameters
        ----------
        g_k : structural self-weight [kN/m²]

        Returns
        -------
        dict with keys:
          g_k, delta_g_k, g_perm, q_k, p_k  — characteristic levels
          p_Ed_qp                            — SLS quasi-permanent combination
          p_Ed_u                             — ULS design value
        """
        g_perm  = g_k + self.delta_g_k
        p_k     = g_perm + self.q_k
        p_Ed_qp = g_perm + self.psi_2 * self.q_k
        p_Ed_u  = self.gamma_G * g_perm + self.gamma_Q * self.q_k
        return dict(
            g_k=g_k,
            delta_g_k=self.delta_g_k,
            g_perm=g_perm,
            q_k=self.q_k,
            p_k=p_k,
            p_Ed_qp=p_Ed_qp,
            p_Ed_u=p_Ed_u,
        )

    # ── Matplotlib visualisation ──────────────────────────────────────────────

    def plot_breakdown(self, ax, g_k: float) -> None:
        """Stacked bar chart of load components with p_Ed demand lines.

        Parameters
        ----------
        ax  : matplotlib Axes
        g_k : structural self-weight [kN/m²]
        """
        s = self.surface_loads(g_k)
        bars = [
            (r'$g_k$',         s['g_k'],       '#aec7e8'),
            (r'$\Delta g_k$',  s['delta_g_k'], '#c8c8c8'),
            (r'$q_k$',         s['q_k'],       '#ffbb78'),
        ]
        bottom = 0.0
        for lbl, val, color in bars:
            ax.bar(['Load'], val, bottom=bottom,
                   color=color, edgecolor='k', linewidth=0.8)
            ax.text(0, bottom + val / 2,
                    f'{lbl} = {val:.2f}',
                    ha='center', va='center', fontsize=9)
            bottom += val

        ax.axhline(s['p_Ed_qp'], color=BLUE, lw=1.8,
                   label=fr"$p_{{Ed,qp}}$ = {s['p_Ed_qp']:.2f} kN/m²")
        ax.axhline(s['p_Ed_u'],  color=RED,  lw=1.8,
                   label=fr"$p_{{Ed,u}}$  = {s['p_Ed_u']:.2f} kN/m²")

        ax.set_ylabel('p [kN/m²]')
        ax.set_title(f"Load  ($p_k$ = {s['p_k']:.2f} kN/m²)", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    def print_summary(self, g_k: float) -> None:
        """Print a formatted table of load levels."""
        s = self.surface_loads(g_k)
        rows = [
            ('g_k',          s['g_k'],       'structural self-weight'),
            ('Δg_k',         s['delta_g_k'], 'finishes / partitions'),
            ('g_perm',       s['g_perm'],    'g_k + Δg_k'),
            ('q_k',          s['q_k'],       'variable service load'),
            ('p_k',          s['p_k'],       'g_perm + q_k'),
            ('p_Ed,qp',      s['p_Ed_qp'],  'g_perm + ψ₂·q_k'),
            ('p_Ed,u',       s['p_Ed_u'],   'γ_G·g_perm + γ_Q·q_k'),
        ]
        print(f"{'Load level':<12} {'[kN/m²]':>9}  Formula")
        print('-' * 48)
        for lbl, val, formula in rows:
            print(f'{lbl:<12} {val:>9.2f}  {formula}')

    def beam_loads(self, g_k: float, w_trib_m: float) -> dict:
        """Surface loads plus equivalent beam line loads.

        Parameters
        ----------
        g_k      : structural self-weight [kN/m²]
        w_trib_m : tributary width [m]

        Returns
        -------
        dict
            All keys from ``surface_loads()`` plus:
            ``q_Ed_qp`` and ``q_Ed_u`` — beam line loads [kN/m],
            ``w_trib_m`` — the tributary width used.
        """
        s = self.surface_loads(g_k)
        s['q_Ed_qp'] = s['p_Ed_qp'] * w_trib_m
        s['q_Ed_u']  = s['p_Ed_u']  * w_trib_m
        s['w_trib_m'] = w_trib_m
        return s

    def material_safety_factors(self) -> tuple:
        """Return (gamma_c, gamma_s) as a tuple."""
        return self.gamma_c, self.gamma_s
