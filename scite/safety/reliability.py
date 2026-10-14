"""
scite.safety.reliability — the safety margin of two independent normal variables.

Action effect E ~ N(μ_E, σ_E²) and resistance R ~ N(μ_R, σ_R²) give the margin
M = R − E ~ N(μ_R − μ_E, σ_E² + σ_R²) (the central-limit argument of the course):

    β   = (μ_R − μ_E) / sqrt(σ_E² + σ_R²)        reliability index
    p_f = P(M < 0) = Φ(−β)                        probability of failure

and, with the FORM sensitivity factors of EN 1990 Annex C (α_E = −0.7, α_R = 0.8),
the design values behind the partial-factor format:

    E_d = μ_E + 0.7 β_t σ_E        R_d = μ_R − 0.8 β_t σ_R
    E_k = μ_E + k σ_E              R_k = μ_R − k σ_R      (k = 1.645: 95 % / 5 % fractiles)
    γ_E = E_d / E_k                γ_R = R_k / R_d
"""
from __future__ import annotations

from functools import cached_property

import numpy as np
from scipy.stats import norm

from scite.core import BMCSModel, ui_field

ALPHA_E = -0.7      # EN 1990 C.7: sensitivity factor of the action side
ALPHA_R = 0.8       # EN 1990 C.7: sensitivity factor of the resistance side
K_FRACTILE = 1.645  # 5 % / 95 % fractile of the standard normal distribution

# EN 1990 Table C2 — target β for the ultimate limit state, reference period 50 years
BETA_TARGET = {"RC1": 3.3, "RC2": 3.8, "RC3": 4.3}


class SafetyMargin(BMCSModel):
    """Margin M = R − E of independent normal action effect and resistance."""

    mu_E: float = ui_field(30.0, label="μ_E", unit="MPa", range=(0.0, 100.0), step=0.5,
                           description="Mean of the action effect")
    sigma_E: float = ui_field(3.0, label="σ_E", unit="MPa", range=(0.1, 30.0), step=0.1,
                              description="Standard deviation of the action effect")
    mu_R: float = ui_field(40.0, label="μ_R", unit="MPa", range=(0.0, 150.0), step=0.5,
                           description="Mean of the resistance")
    sigma_R: float = ui_field(4.0, label="σ_R", unit="MPa", range=(0.1, 30.0), step=0.1,
                              description="Standard deviation of the resistance")
    beta_target: float = ui_field(BETA_TARGET["RC2"], label="β_t", unit="-", range=(1.0, 6.0),
                                  step=0.1, description="Target reliability index")

    # ── margin ────────────────────────────────────────────────────────────────
    @property
    def mu_M(self) -> float:
        return self.mu_R - self.mu_E

    @property
    def sigma_M(self) -> float:
        return float(np.sqrt(self.sigma_E ** 2 + self.sigma_R ** 2))

    @property
    def beta(self) -> float:
        """Reliability index β = μ_M / σ_M."""
        return self.mu_M / self.sigma_M

    @property
    def p_f(self) -> float:
        """Probability of failure P(R − E < 0) = Φ(−β)."""
        return float(norm.cdf(-self.beta))

    @staticmethod
    def beta_from_pf(p_f: float) -> float:
        return float(-norm.ppf(p_f))

    @staticmethod
    def pf_from_beta(beta: float) -> float:
        return float(norm.cdf(-beta))

    # ── densities ─────────────────────────────────────────────────────────────
    def pdf_E(self, x):
        return norm.pdf(x, self.mu_E, self.sigma_E)

    def pdf_R(self, x):
        return norm.pdf(x, self.mu_R, self.sigma_R)

    def pdf_M(self, x):
        return norm.pdf(x, self.mu_M, self.sigma_M)

    # ── semi-probabilistic design values ───────────────────────────────────────
    @property
    def E_d(self) -> float:
        """Design value of the action effect at β_t (E_d = μ_E − α_E β_t σ_E)."""
        return self.mu_E - ALPHA_E * self.beta_target * self.sigma_E

    @property
    def R_d(self) -> float:
        """Design value of the resistance at β_t (R_d = μ_R − α_R β_t σ_R)."""
        return self.mu_R - ALPHA_R * self.beta_target * self.sigma_R

    @property
    def E_k(self) -> float:
        """Characteristic action effect: 95 % fractile."""
        return self.mu_E + K_FRACTILE * self.sigma_E

    @property
    def R_k(self) -> float:
        """Characteristic resistance: 5 % fractile."""
        return self.mu_R - K_FRACTILE * self.sigma_R

    @property
    def gamma_E(self) -> float:
        return self.E_d / self.E_k

    @property
    def gamma_R(self) -> float:
        return self.R_k / self.R_d

    @property
    def verified(self) -> bool:
        """Semi-probabilistic check E_d ≤ R_d at the target reliability."""
        return self.E_d <= self.R_d

    def summary(self) -> dict:
        return dict(mu_M=self.mu_M, sigma_M=self.sigma_M, beta=self.beta, p_f=self.p_f,
                    E_k=self.E_k, E_d=self.E_d, R_k=self.R_k, R_d=self.R_d,
                    gamma_E=self.gamma_E, gamma_R=self.gamma_R, verified=self.verified)

    # ── plot adapter (data in, figure out) ────────────────────────────────────
    def plot_pdfs(self, ax, show_margin: bool = True, show_design_values: bool = False,
                  unit: str = "MPa") -> None:
        """Densities of E, R and the margin R − E with the failure region shaded."""
        x_lo = min(self.mu_E - 4 * self.sigma_E, self.mu_M - 4 * self.sigma_M, 0.0)
        x_hi = max(self.mu_R + 4 * self.sigma_R, self.mu_M + 4 * self.sigma_M)
        x = np.linspace(x_lo, x_hi, 600)
        ax.fill_between(x, self.pdf_E(x), alpha=0.30, color="#1976d2", label="action effect E")
        ax.fill_between(x, self.pdf_R(x), alpha=0.30, color="#e53935", label="resistance R")
        ax.plot([self.mu_E] * 2, [0, self.pdf_E(self.mu_E)], color="#1976d2", lw=1)
        ax.plot([self.mu_R] * 2, [0, self.pdf_R(self.mu_R)], color="#e53935", lw=1)
        if show_margin:
            pdf_m = self.pdf_M(x)
            ax.plot(x, pdf_m, color="#2e7d32", lw=2, label="margin M = R − E")
            ax.fill_between(x, 0, pdf_m, where=x < 0, color="#c62828", alpha=0.6,
                            label=f"failure M < 0, p_f = {self.p_f:.2e}")
            ax.axvline(0.0, color="black", ls="--", lw=1)
        if show_design_values:
            for v, c, lab in ((self.E_k, "#1976d2", "E_k"), (self.E_d, "#1976d2", "E_d"),
                              (self.R_k, "#e53935", "R_k"), (self.R_d, "#e53935", "R_d")):
                ax.axvline(v, color=c, ls=":", lw=1.2)
                ax.text(v, ax.get_ylim()[1] * 0.98, lab, color=c, fontsize=8, ha="center", va="top")
        ax.set_xlabel(f"value [{unit}]")
        ax.set_ylabel("probability density")
        ax.set_xlim(x_lo, x_hi)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="upper right")
