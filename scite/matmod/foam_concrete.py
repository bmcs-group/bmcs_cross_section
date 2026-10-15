"""
Foam concrete / lightweight fill — compression-only law with low stiffness.

Material of a ballast or insulation fill co-acting in a composite cross-section
(e.g. the fill between and above the ribs of a Pi slab).  The law reuses the
two EC2 concrete curves, re-parametrised by the fill's own stiffness E and
strength f_c:

``law='sargin'`` (default)
    EC2 Eq. 3.14 form  σ = f_cd·(k·η − η²) / (1 + (k − 2)·η),  η = ε/ε_c1,
    k = E·|ε_c1| / f_c, with its descending (softening) branch up to the end
    strain, then a residual stress ``sig_res·f_cd``.

``law='parabola'``
    EC2 3.1.7 parabola–rectangle (n = 2) with peak strain ε_c1 and ultimate
    strain ε_cu; beyond ε_cu the residual stress.

Default ε_c1 = −2·f_c/E, so the initial tangent of the characteristic curve
equals E for both laws (k = 2 makes the Sargin form a parabola that softens
to zero at 2·ε_c1).  Tension carries no stress (zero tensile stiffness and
strength) — an unbound granulate is modelled by a very small f_c and E, so the
fill acts as mass only.

Convention: compression is negative strain and negative stress.
"""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np

from scite.core import BMCSModel, ui_field


class FoamConcrete(BMCSModel):
    """Compression-only foam-concrete / fill law (Sargin softening or parabola)."""

    rho: float = ui_field(
        600.0,
        label=r"$\rho$",
        unit="kg/m³",
        range=(100.0, 1600.0),
        step=50.0,
        description="Dry density (self-weight and resource accounting)",
        gt=0,
    )

    f_c: float = ui_field(
        2.0,
        label=r"$f_c$",
        unit="MPa",
        range=(0.05, 20.0),
        step=0.1,
        description="Compressive strength",
        gt=0,
    )

    E: float = ui_field(
        1250.0,
        label=r"$E$",
        unit="MPa",
        range=(1.0, 15000.0),
        step=50.0,
        description="Initial modulus of the characteristic curve",
        gt=0,
    )

    eps_c1: Optional[float] = ui_field(
        None,
        label=r"$\varepsilon_{c1}$",
        unit="-",
        description="Strain at peak stress, negative (None = -2·f_c/E)",
    )

    eps_cu: Optional[float] = ui_field(
        None,
        label=r"$\varepsilon_{cu}$",
        unit="-",
        description=("Limit (end) strain, negative (None = k·ε_c1, the zero of the "
                     "Sargin branch, or 1.75·ε_c1 for the parabola)"),
    )

    sig_res: float = ui_field(
        0.0,
        label=r"$\sigma_{res}/f_c$",
        unit="-",
        range=(0.0, 1.0),
        step=0.05,
        description="Residual stress ratio beyond the limit strain",
        ge=0.0,
        le=1.0,
    )

    gamma: float = ui_field(
        1.5,
        label=r"$\gamma$",
        unit="-",
        range=(1.0, 2.0),
        step=0.05,
        description="Partial safety factor (1.0 for characteristic / SLS curves)",
        ge=1.0,
    )

    law: Literal['sargin', 'parabola'] = ui_field(
        'sargin',
        label="Law",
        description="'sargin' = EC2 Eq. 3.14 with softening; 'parabola' = parabola-rectangle",
    )

    def model_post_init(self, __context) -> None:
        if self.eps_c1 is not None and self.eps_c1 >= 0:
            raise ValueError(f"eps_c1 must be negative, got {self.eps_c1}")
        if self.eps_cu is not None and self.eps_cu >= 0:
            raise ValueError(f"eps_cu must be negative, got {self.eps_cu}")
        if self.law == 'sargin' and self.k <= 1.0:
            raise ValueError(
                f"Sargin law needs k = E·|eps_c1|/f_c > 1 (peak at eps_c1), got k={self.k:.3f}")

    # ── Derived parameters ────────────────────────────────────────────────────

    @property
    def f_cd(self) -> float:
        """Design compressive strength f_c/γ [MPa]."""
        return self.f_c / self.gamma

    @property
    def f_ck(self) -> float:
        """Characteristic strength (alias of f_c, concrete duck-type) [MPa]."""
        return self.f_c

    @property
    def f_cm(self) -> float:
        """Mean strength (alias of f_c, concrete duck-type) [MPa]."""
        return self.f_c

    @property
    def f_ctm(self) -> float:
        """Tensile strength — none [MPa]."""
        return 0.0

    @property
    def E_cm(self) -> float:
        """Modulus (alias of E) [MPa]."""
        return self.E

    @property
    def E_ct_computed(self) -> float:
        """Initial modulus used for transformed-section stiffness [MPa]."""
        return self.E

    @property
    def eps_cr_computed(self) -> float:
        """Cracking strain — no tensile capacity."""
        return 0.0

    @property
    def eps_c1_computed(self) -> float:
        """Strain at peak stress (negative) [-]."""
        return self.eps_c1 if self.eps_c1 is not None else -2.0 * self.f_c / self.E

    @property
    def k(self) -> float:
        """Sargin plasticity number k = E·|ε_c1|/f_c [-] (k = 2 → parabola)."""
        return self.E * abs(self.eps_c1_computed) / self.f_c

    @property
    def eps_cu2_computed(self) -> float:
        """Limit strain (negative) — end of the softening branch / plateau [-].

        This is the strain at which the component's failure marker is placed.
        For the Sargin law it never exceeds the zero of the branch, k·ε_c1.
        """
        eps_c1 = self.eps_c1_computed
        if self.law == 'sargin':
            eps_zero = self.k * eps_c1
            return eps_zero if self.eps_cu is None else max(self.eps_cu, eps_zero)
        return 1.75 * eps_c1 if self.eps_cu is None else self.eps_cu

    @property
    def strain_breakpoints(self) -> tuple[float, ...]:
        """Strains where the law changes branch (used by the section integrator)."""
        return (0.0, self.eps_c1_computed, self.eps_cu2_computed)

    # ── Numerical evaluation ──────────────────────────────────────────────────

    def get_sig(self, eps: np.ndarray) -> np.ndarray:
        """Stress [MPa] for strain(s) eps (negative = compression)."""
        eps = np.asarray(eps, dtype=float)
        eps_c1 = self.eps_c1_computed
        eps_end = self.eps_cu2_computed
        eta = eps / eps_c1                       # ≥ 0 in compression
        if self.law == 'sargin':
            k = self.k
            mag = (k * eta - eta ** 2) / (1.0 + (k - 2.0) * eta)
        else:
            mag = np.where(eta < 1.0, 1.0 - (1.0 - eta) ** 2, 1.0)
        mag = np.clip(mag, 0.0, None)
        sig = np.where(eps >= 0.0, 0.0,
                       np.where(eps >= eps_end, -self.f_cd * mag,
                                -self.sig_res * self.f_cd))
        return sig

    def get_E_t(self, eps: np.ndarray) -> np.ndarray:
        """Tangent modulus [MPa] (central difference)."""
        eps = np.asarray(eps, dtype=float)
        h = 1e-8
        return (self.get_sig(eps + h) - self.get_sig(eps - h)) / (2 * h)

    # ── Plotting ──────────────────────────────────────────────────────────────

    def get_plot_range(self) -> tuple[float, float]:
        """Recommended strain range for plotting."""
        return (1.3 * self.eps_cu2_computed, 0.1 * abs(self.eps_c1_computed))

    def plot_stress_strain(self, ax, n_points: int = 500, color: str = '#b8860b',
                           label: Optional[str] = None):
        """Plot the stress-strain curve on *ax* (does not clear the axes)."""
        eps = np.linspace(*self.get_plot_range(), n_points)
        ax.plot(eps * 1e3, self.get_sig(eps), color=color, lw=2,
                label=label or f'Foam ({self.law}) f_cd={self.f_cd:.2f} MPa')
        ax.plot([self.eps_c1_computed * 1e3], [-self.f_cd], 'o', color=color, ms=6)
        ax.plot([self.eps_cu2_computed * 1e3],
                [float(self.get_sig(np.array([self.eps_cu2_computed]))[0])],
                's', color=color, ms=6)
        ax.axhline(0, color='k', lw=0.5)
        ax.axvline(0, color='k', lw=0.5)
        ax.set_xlabel('Strain ε [‰]')
        ax.set_ylabel('Stress σ [MPa]')
        ax.grid(True, alpha=0.3)

    def plotly_figure(self):
        """Plotly figure of the stress-strain curve."""
        import plotly.graph_objects as go

        eps = np.linspace(*self.get_plot_range(), 500)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=(eps * 1e3).tolist(), y=self.get_sig(eps).tolist(),
                                 mode='lines', name=f'Foam concrete ({self.law})',
                                 line=dict(color='#b8860b', width=2)))
        fig.add_trace(go.Scatter(
            x=[self.eps_c1_computed * 1e3, self.eps_cu2_computed * 1e3],
            y=[-self.f_cd, float(self.get_sig(np.array([self.eps_cu2_computed]))[0])],
            mode='markers', name='peak / limit',
            marker=dict(color='#b8860b', size=9, symbol=['circle', 'square'])))
        fig.add_hline(y=0, line=dict(color='black', width=0.5))
        fig.add_vline(x=0, line=dict(color='black', width=0.5))
        fig.update_layout(
            title=(f'Foam concrete  ρ = {self.rho:.0f} kg/m³,  f_cd = {self.f_cd:.2f} MPa,  '
                   f'E = {self.E:.0f} MPa'),
            xaxis_title='Strain ε [‰]', yaxis_title='Stress σ [MPa]',
            margin=dict(l=60, r=20, t=50, b=50))
        return fig

    def summary(self) -> dict:
        """Summary of material properties."""
        return {
            'rho': f'{self.rho:.0f} kg/m³',
            'f_c': f'{self.f_c:.2f} MPa',
            'f_cd': f'{self.f_cd:.2f} MPa',
            'E': f'{self.E:.0f} MPa',
            'k': f'{self.k:.2f}',
            'eps_c1': f'{self.eps_c1_computed:.5f}',
            'eps_cu': f'{self.eps_cu2_computed:.5f}',
            'law': self.law,
        }
