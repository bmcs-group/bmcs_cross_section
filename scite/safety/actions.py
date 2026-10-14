"""
scite.safety.actions — actions and their combinations according to EN 1990.

Combination rules (EN 1990 §6.4.3 and §6.5.3), with the leading variable action
chosen as the one that maximises the combined effect:

    ULS fundamental (6.10)   E_d = Σ γ_G G_k + γ_P P + γ_Q Q_k,1 + Σ γ_Q ψ_0,i Q_k,i
    ULS (6.10a)              E_d = Σ γ_G G_k + γ_P P + Σ γ_Q ψ_0,i Q_k,i
    ULS (6.10b)              E_d = Σ ξ γ_G G_k + γ_P P + γ_Q Q_k,1 + Σ γ_Q ψ_0,i Q_k,i
    SLS characteristic       E_d = Σ G_k + P + Q_k,1 + Σ ψ_0,i Q_k,i
    SLS frequent             E_d = Σ G_k + P + ψ_1,1 Q_k,1 + Σ ψ_2,i Q_k,i
    SLS quasi-permanent      E_d = Σ G_k + P + Σ ψ_2,i Q_k,i

All actions are scalar effects in one unit (e.g. kN/m² on a floor, or kNm of a
section); the combination is linear, so the unit is the caller's.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from pydantic import Field

from scite.core import BMCSModel, ui_field

# EN 1990 Table A1.2(B), persistent and transient design situations (STR/GEO)
PARTIAL_FACTORS: Dict[str, float] = dict(
    gamma_G_sup=1.35,   # permanent, unfavourable
    gamma_G_inf=1.00,   # permanent, favourable
    gamma_Q=1.50,       # variable, unfavourable (0 when favourable)
    gamma_P=1.00,       # prestress
    xi=0.85,            # reduction of unfavourable permanent actions in 6.10b
)

# EN 1990 Table A1.1 — ψ_0, ψ_1, ψ_2 per category of variable action
PSI_FACTORS: Dict[str, Tuple[float, float, float]] = {
    "imposed_A_B":  (0.7, 0.5, 0.3),   # domestic, residential, office
    "imposed_C_D":  (0.7, 0.7, 0.6),   # congregation, shopping
    "imposed_E":    (1.0, 0.9, 0.8),   # storage
    "snow":         (0.5, 0.2, 0.0),   # sites below 1000 m (CEN members except FIN, IS, NO, SE)
    "wind":         (0.6, 0.2, 0.0),
    "temperature":  (0.6, 0.5, 0.0),
}


class PermanentAction(BMCSModel):
    """A permanent action G_k (self-weight, finishes, …)."""

    name: str = "G"
    G_k: float = ui_field(4.5, label="G_k", unit="kN/m²", range=(0.0, 50.0), step=0.1,
                          description="Characteristic value")
    favourable: bool = Field(False, description="Favourable effect: γ_G,inf applies")


class VariableAction(BMCSModel):
    """A variable action Q_k with its combination factors ψ_0, ψ_1, ψ_2."""

    name: str = "Q"
    Q_k: float = ui_field(3.0, label="Q_k", unit="kN/m²", range=(0.0, 50.0), step=0.1,
                          description="Characteristic value")
    psi_0: float = ui_field(0.7, label="ψ_0", unit="-", range=(0.0, 1.0), step=0.05)
    psi_1: float = ui_field(0.5, label="ψ_1", unit="-", range=(0.0, 1.0), step=0.05)
    psi_2: float = ui_field(0.3, label="ψ_2", unit="-", range=(0.0, 1.0), step=0.05)

    @classmethod
    def from_category(cls, name: str, Q_k: float, category: str) -> "VariableAction":
        """Variable action with the ψ factors of an EN 1990 Table A1.1 category."""
        psi_0, psi_1, psi_2 = PSI_FACTORS[category]
        return cls(name=name, Q_k=Q_k, psi_0=psi_0, psi_1=psi_1, psi_2=psi_2)


class CombinationResult(BMCSModel):
    """One evaluated combination: the total and how it is composed."""

    rule: str
    formula: str
    E_d: float
    permanent: float
    prestress: float
    leading: Optional[str] = None
    leading_value: float = 0.0
    accompanying: float = 0.0
    terms: List[Tuple[str, float]] = Field(default_factory=list)   # (label, contribution)


class LoadCombination(BMCSModel):
    """Actions on one structural element and their EN 1990 combinations."""

    permanent: List[PermanentAction] = Field(default_factory=list)
    variable: List[VariableAction] = Field(default_factory=list)
    P: float = ui_field(0.0, label="P", unit="kN/m²", range=(-50.0, 50.0), step=0.1,
                        description="Prestress effect (characteristic)")
    gamma_G_sup: float = ui_field(PARTIAL_FACTORS["gamma_G_sup"], label="γ_G,sup", unit="-",
                                  range=(1.0, 1.5), step=0.05)
    gamma_G_inf: float = ui_field(PARTIAL_FACTORS["gamma_G_inf"], label="γ_G,inf", unit="-",
                                  range=(0.9, 1.1), step=0.05)
    gamma_Q: float = ui_field(PARTIAL_FACTORS["gamma_Q"], label="γ_Q", unit="-",
                              range=(1.0, 1.6), step=0.05)
    gamma_P: float = ui_field(PARTIAL_FACTORS["gamma_P"], label="γ_P", unit="-",
                              range=(0.9, 1.2), step=0.05)
    xi: float = ui_field(PARTIAL_FACTORS["xi"], label="ξ", unit="-", range=(0.8, 1.0), step=0.05)

    # ── building blocks ───────────────────────────────────────────────────────
    def _permanent(self, factored: bool, xi: float = 1.0) -> Tuple[float, List[Tuple[str, float]]]:
        total, terms = 0.0, []
        for g in self.permanent:
            if factored:
                gamma = self.gamma_G_inf if g.favourable else xi * self.gamma_G_sup
            else:
                gamma = 1.0
            v = gamma * g.G_k
            total += v
            terms.append((f"{gamma:.3g}·{g.name}" if factored else g.name, v))
        return total, terms

    def _prestress(self, factored: bool) -> Tuple[float, List[Tuple[str, float]]]:
        if self.P == 0.0:
            return 0.0, []
        gamma = self.gamma_P if factored else 1.0
        return gamma * self.P, [(f"{gamma:.3g}·P" if factored else "P", gamma * self.P)]

    def _with_leading(self, gamma_Q: float, lead_psi: str | None, acc_psi: str):
        """Best (max) choice of the leading variable action.

        ``lead_psi``: None → leading enters with its full value, else the ψ attribute
        it is multiplied with; ``acc_psi``: ψ attribute of the accompanying actions.
        Returns (leading name, leading contribution, accompanying total, terms).
        """
        if not self.variable:
            return None, 0.0, 0.0, []
        best = None
        for lead in self.variable:
            f_lead = 1.0 if lead_psi is None else getattr(lead, lead_psi)
            v_lead = gamma_Q * f_lead * lead.Q_k
            acc, terms = 0.0, []
            for q in self.variable:
                if q is lead:
                    continue
                v = gamma_Q * getattr(q, acc_psi) * q.Q_k
                acc += v
                terms.append((f"{gamma_Q:.3g}·{getattr(q, acc_psi):.2g}·{q.name}".replace("1·", "", 1)
                              if gamma_Q != 1.0 else f"{getattr(q, acc_psi):.2g}·{q.name}", v))
            cand = (v_lead + acc, lead.name, v_lead, acc,
                    [((f"{gamma_Q:.3g}·" if gamma_Q != 1.0 else "")
                      + (f"{f_lead:.2g}·" if lead_psi is not None else "") + lead.name, v_lead)] + terms)
            if best is None or cand[0] > best[0]:
                best = cand
        _, name, v_lead, acc, terms = best
        return name, v_lead, acc, terms

    def _all_reduced(self, gamma_Q: float, psi: str) -> Tuple[float, List[Tuple[str, float]]]:
        total, terms = 0.0, []
        for q in self.variable:
            v = gamma_Q * getattr(q, psi) * q.Q_k
            total += v
            terms.append(((f"{gamma_Q:.3g}·" if gamma_Q != 1.0 else "") + f"{getattr(q, psi):.2g}·{q.name}", v))
        return total, terms

    # ── ULS ───────────────────────────────────────────────────────────────────
    def uls_fundamental(self) -> CombinationResult:
        """EN 1990 eq. 6.10."""
        G, tG = self._permanent(True)
        Pv, tP = self._prestress(True)
        lead, vl, acc, tQ = self._with_leading(self.gamma_Q, None, "psi_0")
        return CombinationResult(rule="ULS 6.10",
                                 formula="Σ γ_G G_k + γ_P P + γ_Q Q_k,1 + Σ γ_Q ψ_0,i Q_k,i",
                                 E_d=G + Pv + vl + acc, permanent=G, prestress=Pv,
                                 leading=lead, leading_value=vl, accompanying=acc,
                                 terms=tG + tP + tQ)

    def uls_610a(self) -> CombinationResult:
        """EN 1990 eq. 6.10a (all variable actions with ψ_0)."""
        G, tG = self._permanent(True)
        Pv, tP = self._prestress(True)
        Q, tQ = self._all_reduced(self.gamma_Q, "psi_0")
        return CombinationResult(rule="ULS 6.10a",
                                 formula="Σ γ_G G_k + γ_P P + Σ γ_Q ψ_0,i Q_k,i",
                                 E_d=G + Pv + Q, permanent=G, prestress=Pv,
                                 accompanying=Q, terms=tG + tP + tQ)

    def uls_610b(self) -> CombinationResult:
        """EN 1990 eq. 6.10b (unfavourable permanent actions reduced by ξ)."""
        G, tG = self._permanent(True, xi=self.xi)
        Pv, tP = self._prestress(True)
        lead, vl, acc, tQ = self._with_leading(self.gamma_Q, None, "psi_0")
        return CombinationResult(rule="ULS 6.10b",
                                 formula="Σ ξ γ_G G_k + γ_P P + γ_Q Q_k,1 + Σ γ_Q ψ_0,i Q_k,i",
                                 E_d=G + Pv + vl + acc, permanent=G, prestress=Pv,
                                 leading=lead, leading_value=vl, accompanying=acc,
                                 terms=tG + tP + tQ)

    def uls_governing(self) -> CombinationResult:
        """The less favourable of 6.10a and 6.10b (the alternative to 6.10)."""
        a, b = self.uls_610a(), self.uls_610b()
        return a if a.E_d >= b.E_d else b

    # ── SLS ───────────────────────────────────────────────────────────────────
    def sls_characteristic(self) -> CombinationResult:
        G, tG = self._permanent(False)
        Pv, tP = self._prestress(False)
        lead, vl, acc, tQ = self._with_leading(1.0, None, "psi_0")
        return CombinationResult(rule="SLS characteristic",
                                 formula="Σ G_k + P + Q_k,1 + Σ ψ_0,i Q_k,i",
                                 E_d=G + Pv + vl + acc, permanent=G, prestress=Pv,
                                 leading=lead, leading_value=vl, accompanying=acc,
                                 terms=tG + tP + tQ)

    def sls_frequent(self) -> CombinationResult:
        G, tG = self._permanent(False)
        Pv, tP = self._prestress(False)
        lead, vl, acc, tQ = self._with_leading(1.0, "psi_1", "psi_2")
        return CombinationResult(rule="SLS frequent",
                                 formula="Σ G_k + P + ψ_1,1 Q_k,1 + Σ ψ_2,i Q_k,i",
                                 E_d=G + Pv + vl + acc, permanent=G, prestress=Pv,
                                 leading=lead, leading_value=vl, accompanying=acc,
                                 terms=tG + tP + tQ)

    def sls_quasi_permanent(self) -> CombinationResult:
        G, tG = self._permanent(False)
        Pv, tP = self._prestress(False)
        Q, tQ = self._all_reduced(1.0, "psi_2")
        return CombinationResult(rule="SLS quasi-permanent",
                                 formula="Σ G_k + P + Σ ψ_2,i Q_k,i",
                                 E_d=G + Pv + Q, permanent=G, prestress=Pv,
                                 accompanying=Q, terms=tG + tP + tQ)

    def all_combinations(self) -> Dict[str, CombinationResult]:
        """Every rule, keyed by its short name."""
        return {
            "6.10": self.uls_fundamental(),
            "6.10a": self.uls_610a(),
            "6.10b": self.uls_610b(),
            "char": self.sls_characteristic(),
            "freq": self.sls_frequent(),
            "qp": self.sls_quasi_permanent(),
        }


def office_example() -> LoadCombination:
    """The office-floor example of the GdT course: G 4.5, imposed 3.0, wind 1.2, snow 0.8 kN/m²."""
    return LoadCombination(
        permanent=[PermanentAction(name="G", G_k=4.5)],
        variable=[
            VariableAction.from_category("Q_imp", 3.0, "imposed_A_B"),
            VariableAction.from_category("Q_w", 1.2, "wind"),
            VariableAction.from_category("Q_s", 0.8, "snow"),
        ],
    )
