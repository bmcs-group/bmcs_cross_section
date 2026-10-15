"""
BeamDeflectionVarCS
===================

Subclass of BeamDeflectionAnalysis supporting beams with segmented longitudinal
reinforcement (variable cross-section along the span).

Motivation
----------
A uniformly doubly-reinforced section used in ``ContinuousBeamAnalysis`` produces
an x/d at the hogging support that is smaller than EC2's singly-reinforced formula
predicts, because the compression (bottom) bars reduce the neutral-axis depth.
This class models the actual reinforcement detailing so that the hogging section
uses only the top bars — restoring the EC2-consistent x/d.

Construction
------------
Use the classmethod ``from_segments`` rather than calling the constructor directly.

Segments are defined as a list of ``(x_left, x_right, CrossSection)`` tuples,
ordered from 0 to L, covering the full span.  The **last segment** supplies the
hogging-zone cross-section, which is passed as ``cs`` to the parent so that the
inherited ``mk`` property (and all ``span.mk.*`` usages in
``ContinuousBeamAnalysis``) automatically use the correct hogging M-κ curve.
The **first segment** supplies the sagging-zone cross-section, which determines
``M_R`` (the sagging capacity checked by ``q_sag_a_u``).

Known limitation
----------------
The sweep in ``ContinuousBeamAnalysis`` tracks sagging curvatures via
``span.mk.kappa_from_M(M_sag)``, which uses the hogging mk.  The sagging
curvature values in the sweep dict are therefore slightly incorrect — this is a
cosmetic artefact and does not affect any structural calculation.
"""

from __future__ import annotations

from functools import cached_property
from typing import List, Tuple

import numpy as np
from pydantic import PrivateAttr

from scite.beam.bending.beam_deflection import BeamDeflectionAnalysis
from scite.cs_design.cross_section import CrossSection
from scite.mkappa.mkappa import MKappaAnalysis


class BeamDeflectionVarCS(BeamDeflectionAnalysis):
    """
    Beam deflection analysis with segment-wise M-κ curves.

    Use ``from_segments`` to construct.
    """

    _segments: List[Tuple[float, float, CrossSection]] = PrivateAttr(default_factory=list)
    _mk_cache: dict = PrivateAttr(default_factory=dict)

    @classmethod
    def from_segments(
        cls,
        segments: List[Tuple[float, float, CrossSection]],
        L: float,
        n_x: int = 200,
        n_kappa: int = 150,
        n_load_steps: int = 41,
        solve_mode: str = 'both',
        mk_cache: dict = None,
    ) -> 'BeamDeflectionVarCS':
        """
        Construct a BeamDeflectionVarCS from a list of (x_left, x_right, cs) segments.

        Parameters
        ----------
        segments : list of (x_left [mm], x_right [mm], CrossSection)
            Must be ordered and contiguous, covering [0, L].
            Last segment is the hogging zone; first segment is the sagging zone.
        L : float
            Total span length [mm].
        mk_cache : dict, optional
            External cache dict keyed by ``id(cs)``.  Pass the same dict to both
            spans of a continuous beam so that shared CrossSection objects are
            solved only once.  A fresh dict is created when omitted.
        """
        cs_hog = segments[-1][2]
        obj = cls(
            cs=cs_hog, L=L, load_type='dist',
            n_x=n_x, n_kappa=n_kappa,
            n_load_steps=n_load_steps, solve_mode=solve_mode,
        )
        obj._segments = list(segments)
        if mk_cache is not None:
            obj._mk_cache = mk_cache
        return obj

    def _get_mk(self, cs: CrossSection) -> MKappaAnalysis:
        """Return a solved MKappaAnalysis for *cs*, building and caching if needed."""
        key = id(cs)
        if key not in self._mk_cache:
            mk = MKappaAnalysis(
                cs=cs, n_kappa=self.n_kappa,
                N_Ed=self.N_Ed, solve_mode=self.solve_mode,
            )
            mk.solve()
            self._mk_cache[key] = mk
        return self._mk_cache[key]

    @cached_property
    def mk(self) -> MKappaAnalysis:
        """Hogging-zone M-κ — routed through the shared cache (no duplicate solve)."""
        return self._get_mk(self.cs)

    @cached_property
    def M_R(self) -> float:
        """Peak sagging moment capacity [kN·m] — from the midspan segment.

        Using the midspan segment works correctly for both span orientations:
        left spans have cs_lower at [0, 2/3·L) and right spans have cs_lower
        at [1/3·L, L], so L/2 always falls in the sagging zone.
        """
        mid_x = self.L / 2
        for x_l, x_r, cs in self._segments:
            if x_l <= mid_x <= x_r:
                return float(np.max(self._get_mk(cs).M_values))
        return float(np.max(self._get_mk(self._segments[-1][2]).M_values))

    def get_kappa_x_from_M(self, M_x: np.ndarray) -> np.ndarray:
        """
        Segment-aware M→κ inversion.

        Each x-point is dispatched to the M-κ curve of its segment's
        cross-section.  Points on segment boundaries go to the left segment
        (except the very last point, which goes to the last segment).
        """
        M_x = np.asarray(M_x, dtype=float)
        kappa = np.zeros_like(M_x)
        x = self.x
        for i, (x_l, x_r, cs) in enumerate(self._segments):
            if i < len(self._segments) - 1:
                mask = (x >= x_l) & (x < x_r)
            else:
                mask = (x >= x_l) & (x <= x_r)
            if mask.any():
                kappa[mask] = self._get_mk(cs).kappa_from_M(M_x[mask])
        return kappa
