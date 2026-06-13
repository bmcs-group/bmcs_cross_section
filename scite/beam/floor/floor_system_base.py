"""
scite.beam.floor.floor_system_base
=====================================

FloorSystemBase — lightweight mixin providing shared assessment methods
for all floor system dataclasses (FlatSlab, CRCFlatSlab, SRCRibbedSlab,
CRCRibbedSlab).

Subclasses implement
--------------------
  g_k              (property)  → float               structural self-weight [kN/m²]
  _beam_elements() (method)    → list[tuple]          (FloorAnalysisPair, w_trib_m, label)
  volumes()        (method)    → dict                 material / GWP / cost breakdown

All other methods are derived from those three.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .floor_analysis import FloorAnalysisPair
    from .load_model import LoadModel


class FloorSystemBase(ABC):
    """Mixin providing shared structural assessment for floor system dataclasses.

    Concrete subclasses are pure Python dataclasses — this mixin adds no
    dataclass fields.  The three abstract-like hooks are:

    ``g_k``
        Property returning structural self-weight [kN/m²].

    ``_beam_elements()``
        Returns a list of ``(FloorAnalysisPair, w_trib_m, label)`` tuples,
        one per assessable element (e.g. rib + bay slab for ribbed floors).

    ``volumes()``
        Returns a dict with at least the normalised keys:
        ``A_ref``, ``gwp_per_m2``, ``cost_per_m2``.
    """

    # ── Abstract hooks (subclasses must implement) ───────────────────────────

    @property
    @abstractmethod
    def g_k(self) -> float:
        """Structural self-weight [kN/m²]."""

    @abstractmethod
    def _beam_elements(self) -> list:
        """Return list of (FloorAnalysisPair, w_trib_m, label) tuples."""

    @abstractmethod
    def volumes(self) -> dict:
        """Return material volumes, masses, GWP and cost per reference unit."""

    # ── Shared assessment ─────────────────────────────────────────────────────

    def assess(self, lm: 'LoadModel') -> dict:
        """Return SLS/ULS utilisation ratios for all beam elements.

        Parameters
        ----------
        lm : LoadModel

        Returns
        -------
        dict
            Keyed by element label.  Each value contains::

                {
                    'p_R_sls' : float,   # SLS capacity [kN/m²]
                    'p_R_uls' : float,   # ULS capacity [kN/m²]
                    'eta_SLS' : float,   # p_Ed,qp / p_R_sls
                    'eta_ULS' : float,   # p_Ed,u  / p_R_uls
                }
        """
        s = lm.surface_loads(self.g_k)
        result = {}
        for beam, w_trib, label in self._beam_elements():
            p_R_sls = (beam.sls.bda.F_R / w_trib) if w_trib > 0 else float('inf')
            p_R_uls = (beam.uls.bda.F_R / w_trib) if w_trib > 0 else float('inf')
            result[label] = dict(
                p_R_sls=p_R_sls,
                p_R_uls=p_R_uls,
                eta_SLS=s['p_Ed_qp'] / p_R_sls if p_R_sls > 0 else float('inf'),
                eta_ULS=s['p_Ed_u']  / p_R_uls if p_R_uls > 0 else float('inf'),
            )
        return result

    def print_assessment(self, lm: 'LoadModel') -> None:
        """Print a concise utilisation table."""
        a = self.assess(lm)
        print(f"{'Element':<20} {'p_R_SLS':>9} {'p_R_ULS':>9} {'eta_SLS':>8} {'eta_ULS':>8}")
        print('-' * 60)
        for label, d in a.items():
            print(f"{label:<20} {d['p_R_sls']:>9.2f} {d['p_R_uls']:>9.2f} "
                  f"{d['eta_SLS']:>8.3f} {d['eta_ULS']:>8.3f}")
