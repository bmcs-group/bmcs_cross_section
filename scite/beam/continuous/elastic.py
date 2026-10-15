"""
scite.beam.continuous.elastic — linear-elastic continuous beam on rigid supports.
==================================================================================

``ElasticContinuousBeam`` — n spans l_1 … l_n, hinged at all supports, constant EI,
loaded span by span with uniform loads q and point loads P. It is the structure
behind the table values for continuous beams (e.g. Schneider, Bautabellen; GdT
script Table 3.7) and the only statically indeterminate system of the GdT course.

Algorithm
---------
The degree of indeterminacy is n − 1: the interior support moments. Each span is
a simply supported beam carrying its loads and the two end moments; rotation
continuity over every interior support i gives the three-moment equation
(Clapeyron), for constant EI:

    l_i M_{i−1} + 2 (l_i + l_{i+1}) M_i + l_{i+1} M_{i+1} = −(l_i R_i + l_{i+1} L_{i+1})

with the load terms of the span (Belastungsglieder) at its left (L) and right (R) end:

    uniform load q:            L = R = q l² / 4
    point load P at a, b=l−a:  L = P a b (l + b) / l²,   R = P a b (l + a) / l²

and M_0 = M_n = 0 at the end supports. Superposition then gives every span as the
simple-beam diagram plus the closing line through the support moments:

    M(x) = M₀(x) + M_{i−1} (1 − x/l) + M_i x/l        V(x) = V₀(x) + (M_i − M_{i−1}) / l

Sign convention
---------------
M > 0 sagging (tension at the bottom, the dashed fibre of the course), V = dM/dx,
reactions positive upward, deflection w positive downward with EI w'' = −M.
Units: any consistent set; the GdT node uses kN and m.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import numpy as np
from pydantic import Field, model_validator
from scipy.integrate import cumulative_trapezoid

from scite.core import BMCSModel

SUPPORT_LABELS = "ABCDEFGHIJ"


class UniformLoad(BMCSModel):
    """Uniform load q over the whole span ``span`` (0-based)."""

    span: int = Field(ge=0)
    q: float


class PointLoad(BMCSModel):
    """Point load P at distance ``a`` from the left support of span ``span`` (0-based).

    ``a`` lies strictly inside the span; a load on a support goes straight into the
    reaction and causes no internal forces.
    """

    span: int = Field(ge=0)
    P: float
    a: float = Field(gt=0.0)


Load = Union[UniformLoad, PointLoad]


@dataclass(frozen=True)
class BeamProfiles:
    """Internal-force profiles along the whole beam.

    ``x`` repeats a coordinate where V jumps (supports, point loads), so that a
    plot draws the jump vertically. ``M0`` is the simple-beam part, ``M_line`` the
    closing line through the support moments; ``M = M0 + M_line``.
    """

    x: np.ndarray
    M: np.ndarray
    V: np.ndarray
    M0: np.ndarray
    M_line: np.ndarray
    span: np.ndarray


@dataclass(frozen=True)
class FieldMoment:
    """Extreme moment of one span and where it occurs (global x)."""

    span: int
    x_max: float
    M_max: float
    x_min: float
    M_min: float


class ElasticContinuousBeam(BMCSModel):
    """Continuous beam with hinged supports, constant EI, uniform and point loads."""

    L: list[float] = Field(default_factory=lambda: [3.0, 3.0], min_length=1)
    loads: list[Load] = Field(default_factory=list)
    EI: float = Field(1.0, gt=0.0)

    @model_validator(mode="after")
    def _check(self) -> "ElasticContinuousBeam":
        if any(l <= 0.0 for l in self.L):
            raise ValueError("all span lengths must be positive")
        for ld in self.loads:
            if ld.span >= len(self.L):
                raise ValueError(f"load on span {ld.span} but the beam has {len(self.L)} spans")
            if isinstance(ld, PointLoad) and not 0.0 < ld.a < self.L[ld.span]:
                raise ValueError(f"point load at a = {ld.a} is not inside span {ld.span}")
        return self

    # ── geometry and loads ────────────────────────────────────────────────────
    @property
    def n_spans(self) -> int:
        return len(self.L)

    @property
    def x_supports(self) -> np.ndarray:
        """Global x of the n + 1 supports."""
        return np.concatenate([[0.0], np.cumsum(self.L)])

    @property
    def support_labels(self) -> list[str]:
        return list(SUPPORT_LABELS[: self.n_spans + 1])

    def _q(self, i: int) -> float:
        return sum(ld.q for ld in self.loads if isinstance(ld, UniformLoad) and ld.span == i)

    def _points(self, i: int) -> list[tuple[float, float]]:
        return sorted((ld.a, ld.P) for ld in self.loads if isinstance(ld, PointLoad) and ld.span == i)

    def span_load(self, i: int) -> float:
        """Resultant load on span i."""
        return self._q(i) * self.L[i] + sum(P for _, P in self._points(i))

    @property
    def total_load(self) -> float:
        return sum(self.span_load(i) for i in range(self.n_spans))

    # ── statically indeterminate part: support moments ────────────────────────
    def _load_terms(self, i: int) -> tuple[float, float]:
        """Load terms (L, R) of span i for the three-moment equation."""
        l, q = self.L[i], self._q(i)
        tL = tR = q * l**2 / 4.0
        for a, P in self._points(i):
            b = l - a
            tL += P * a * b * (l + b) / l**2
            tR += P * a * b * (l + a) / l**2
        return tL, tR

    @property
    def support_moments(self) -> np.ndarray:
        """Moments M_0 … M_n over the supports (end supports zero)."""
        n, L = self.n_spans, self.L
        Ms = np.zeros(n + 1)
        if n == 1:
            return Ms
        terms = [self._load_terms(i) for i in range(n)]
        K = np.zeros((n - 1, n - 1))
        r = np.zeros(n - 1)
        for k in range(n - 1):            # interior support k + 1, between spans k and k + 1
            K[k, k] = 2.0 * (L[k] + L[k + 1])
            if k > 0:
                K[k, k - 1] = L[k]
            if k < n - 2:
                K[k, k + 1] = L[k + 1]
            r[k] = -(L[k] * terms[k][1] + L[k + 1] * terms[k + 1][0])
        Ms[1:-1] = np.linalg.solve(K, r)
        return Ms

    # ── one span: simple beam + closing line ──────────────────────────────────
    def _span_eval(self, i: int, x: np.ndarray, passed: np.ndarray):
        """M, V, M0, M_line at local x of span i; ``passed[j]`` marks point loads left of x."""
        l, q, pts = self.L[i], self._q(i), self._points(i)
        Ms = self.support_moments
        Ml, Mr = Ms[i], Ms[i + 1]
        A0 = q * l / 2.0 + sum(P * (l - a) / l for a, P in pts)
        M0 = A0 * x - q * x**2 / 2.0
        V0 = A0 - q * x
        for j, (a, P) in enumerate(pts):
            M0 = M0 - P * np.clip(x - a, 0.0, None)
            V0 = V0 - P * passed[:, j]
        M_line = Ml * (1.0 - x / l) + Mr * x / l
        return M0 + M_line, V0 + (Mr - Ml) / l, M0, M_line

    def _span_grid(self, i: int, n_seg: int):
        """Local x of span i split at the point loads, with the 'load passed' flags."""
        l, pts = self.L[i], self._points(i)
        cuts = sorted({0.0, l, *(a for a, _ in pts)})
        xs, flags = [], []
        for s0, s1 in zip(cuts[:-1], cuts[1:]):
            xseg = np.linspace(s0, s1, max(n_seg, 2))
            xs.append(xseg)
            # on [s0, s1] the loads at a <= s0 are passed; the load at s1 is not yet
            flags.append(np.broadcast_to(np.array([a <= s0 for a, _ in pts], dtype=float),
                                         (len(xseg), len(pts))))
        return np.concatenate(xs), np.vstack(flags)

    def profiles(self, n_per_span: int = 201) -> BeamProfiles:
        """M, V and their two parts along the whole beam."""
        xs, Ms_, Vs, M0s, Mls, sp = [], [], [], [], [], []
        x0 = self.x_supports
        for i in range(self.n_spans):
            n_seg = max(int(n_per_span / (len(self._points(i)) + 1)), 3)
            x, passed = self._span_grid(i, n_seg)
            M, V, M0, Ml = self._span_eval(i, x, passed)
            xs.append(x + x0[i]); Ms_.append(M); Vs.append(V); M0s.append(M0); Mls.append(Ml)
            sp.append(np.full(len(x), i))
        return BeamProfiles(np.concatenate(xs), np.concatenate(Ms_), np.concatenate(Vs),
                            np.concatenate(M0s), np.concatenate(Mls), np.concatenate(sp))

    # ── characteristic values ─────────────────────────────────────────────────
    def end_shears(self, i: int) -> tuple[float, float]:
        """V just right of the left support and just left of the right support of span i."""
        x = np.array([0.0, self.L[i]])
        passed = np.array([[0.0], [1.0]]) * np.ones((1, len(self._points(i))))
        _, V, _, _ = self._span_eval(i, x, passed)
        return float(V[0]), float(V[1])

    @property
    def shear_left(self) -> np.ndarray:
        """V just left of each support (0 at the first)."""
        return np.array([0.0] + [self.end_shears(i)[1] for i in range(self.n_spans)])

    @property
    def shear_right(self) -> np.ndarray:
        """V just right of each support (0 at the last)."""
        return np.array([self.end_shears(i)[0] for i in range(self.n_spans)] + [0.0])

    @property
    def reactions(self) -> np.ndarray:
        """Support reactions (upward positive): the jump of V over each support."""
        return self.shear_right - self.shear_left

    def field_moments(self) -> list[FieldMoment]:
        """Exact extreme moments of each span: at the ends, at point loads, or where V = 0."""
        out, x0 = [], self.x_supports
        for i in range(self.n_spans):
            l, q, pts = self.L[i], self._q(i), self._points(i)
            cuts = sorted({0.0, l, *(a for a, _ in pts)})
            cand = list(cuts)
            if q != 0.0:   # V is linear between the cuts: its zero is a candidate
                for s0, s1 in zip(cuts[:-1], cuts[1:]):
                    passed = np.array([a <= s0 for a, _ in pts], dtype=float).reshape(1, len(pts))
                    _, V, _, _ = self._span_eval(i, np.array([s0]), passed)
                    xz = s0 + V[0] / q
                    if s0 < xz < s1:
                        cand.append(float(xz))
            xc = np.array(sorted(cand))
            M = np.array([self.moment_at(x0[i] + x) for x in xc])
            jmax, jmin = int(np.argmax(M)), int(np.argmin(M))
            out.append(FieldMoment(i, float(x0[i] + xc[jmax]), float(M[jmax]),
                                   float(x0[i] + xc[jmin]), float(M[jmin])))
        return out

    def moment_at(self, x_global: float) -> float:
        """M at a global x (M is continuous, so no side needs to be chosen)."""
        x0 = self.x_supports
        i = int(np.clip(np.searchsorted(x0, x_global, side="right") - 1, 0, self.n_spans - 1))
        pts = self._points(i)
        x = np.array([x_global - x0[i]])
        M, _, _, _ = self._span_eval(i, x, np.zeros((1, len(pts))))
        return float(M[0])

    # ── deflection ────────────────────────────────────────────────────────────
    def deflection(self, n_per_span: int = 201) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """x, w(x), w'(x) from EI w'' = −M with w = 0 at every support."""
        p = self.profiles(n_per_span)
        xs, ws, ts = [], [], []
        for i in range(self.n_spans):
            m = p.span == i
            x, M = p.x[m], p.M[m]
            g = cumulative_trapezoid(-M / self.EI, x, initial=0.0)
            h = cumulative_trapezoid(g, x, initial=0.0)
            c = -h[-1] / (x[-1] - x[0])
            xs.append(x); ws.append(h + c * (x - x[0])); ts.append(g + c)
        return np.concatenate(xs), np.concatenate(ws), np.concatenate(ts)

    # ── plot adapters (data in, axes out) ─────────────────────────────────────
    def plot_scheme(self, ax, *, q_label: str = "q", P_label: str = "P", unit_q: str = "kN/m",
                    unit_P: str = "kN", show_deflection: bool = False, fs: float = 8.0) -> None:
        """Beam line, hinged supports A, B, …, span numbers, loads and the deflected shape."""
        import matplotlib.patches as mp

        Ltot = float(sum(self.L))
        h = 0.06 * Ltot                       # drawing unit
        xs = self.x_supports
        ax.plot([0, Ltot], [0, 0], color="black", lw=3, solid_capstyle="butt", zorder=4)
        for k, xk in enumerate(xs):
            ax.add_patch(mp.Polygon([[xk, 0], [xk - 0.35 * h, -0.6 * h], [xk + 0.35 * h, -0.6 * h]],
                                    closed=True, fc="white", ec="black", lw=1.2, zorder=5))
            y_ground = -0.6 * h if k == 0 else -0.8 * h
            ax.plot([xk - 0.5 * h, xk + 0.5 * h], [y_ground, y_ground], color="black", lw=1.2)
            ax.text(xk, -1.0 * h, self.support_labels[k], ha="center", va="top",
                    fontsize=fs + 2, fontweight="bold")
        for i, l in enumerate(self.L):
            xm = xs[i] + l / 2
            ax.text(xm, -1.75 * h, f"span {i + 1}:  l$_{i + 1}$ = {l:.2f} m", ha="center",
                    va="top", fontsize=fs)
        # loads
        q_max = max([abs(self._q(i)) for i in range(self.n_spans)] + [1e-12])
        for i in range(self.n_spans):
            q = self._q(i)
            if q != 0.0:
                top = 0.25 * h + 1.1 * h * abs(q) / q_max
                ax.add_patch(mp.Rectangle((xs[i], 0.25 * h), self.L[i], top - 0.25 * h,
                                          fc="#1976d2", alpha=0.15, ec="#1976d2", lw=1.0))
                for xa in np.linspace(xs[i], xs[i + 1], max(int(self.L[i] / Ltot * 40), 4)):
                    ax.annotate("", xy=(xa, 0.12 * h), xytext=(xa, top),
                                arrowprops=dict(arrowstyle="-|>", color="#1976d2", lw=0.8,
                                                mutation_scale=6))
                ax.text(xs[i] + self.L[i] / 2, top + 0.1 * h, f"{q_label} = {q:g} {unit_q}",
                        ha="center", va="bottom", fontsize=fs, color="#1976d2")
            for a, P in self._points(i):
                ax.annotate("", xy=(xs[i] + a, 0.12 * h), xytext=(xs[i] + a, 2.2 * h),
                            arrowprops=dict(arrowstyle="-|>", color="#c62828", lw=1.6,
                                            mutation_scale=10))
                ax.text(xs[i] + a, 2.3 * h, f"{P_label} = {P:g} {unit_P}", ha="center",
                        va="bottom", fontsize=fs, color="#c62828")
        if show_deflection:
            x, w, _ = self.deflection()
            s = 1.0 * h / max(np.abs(w).max(), 1e-12)
            ax.plot(x, -w * s, color="0.25", lw=1.2, ls="--", zorder=6)
            ax.text(1.0, 1.0, "- - deflected shape (exaggerated)", transform=ax.transAxes,
                    ha="right", va="top", fontsize=fs - 1, color="0.25")
        ax.set_xlim(-0.05 * Ltot, 1.05 * Ltot)
        ax.set_ylim(-2.6 * h, 3.0 * h)
        ax.axis("off")

    def plot_M(self, ax, *, unit: str = "kNm", annotate: bool = True,
               show_decomposition: bool = False, color: str = "#2ca02c", fs: float = 8.0) -> None:
        """Bending moment diagram, positive (sagging) drawn downward."""
        p = self.profiles()
        if show_decomposition:
            ax.fill_between(p.x, 0, -p.M_line, color="#e53935", alpha=0.18, lw=0)
            ax.fill_between(p.x, -p.M_line, -p.M, color="#ffb300", alpha=0.25, lw=0)
            ax.plot(p.x, -p.M_line, color="#e53935", lw=1.2, ls="--")
            for i in range(self.n_spans):         # M0 at midspan, hung from the closing line
                if self.span_load(i) == 0.0:
                    continue
                m = p.span == i
                xm = self.x_supports[i] + self.L[i] / 2
                j = int(np.argmin(np.abs(p.x[m] - xm)))
                top, bot, m0 = -p.M_line[m][j], -p.M[m][j], p.M0[m][j]
                ax.annotate("", xy=(xm, bot), xytext=(xm, top),
                            arrowprops=dict(arrowstyle="<->", color="#e65100", lw=1.0))
                ax.text(xm + 0.01 * self.x_supports[-1], (top + bot) / 2, f"M$_0$ = {m0:.2f}",
                        fontsize=fs - 0.5, color="#e65100", va="center")
        else:
            ax.fill_between(p.x, 0, -p.M, color=color, alpha=0.15, lw=0)
        ax.plot(p.x, -p.M, color=color, lw=2.0, label="M")
        ax.axhline(0, color="black", lw=0.8)
        for xk in self.x_supports:
            ax.axvline(xk, color="0.75", lw=0.6, ls=":")
        if annotate:
            Ms = self.support_moments
            for k in range(1, self.n_spans):
                ax.annotate(f"{Ms[k]:.2f}", (self.x_supports[k], -Ms[k]), textcoords="offset points",
                            xytext=(0, 0.75 * fs if Ms[k] < 0 else -1.5 * fs), ha="center", fontsize=fs,
                            fontweight="bold")
            for fm in self.field_moments():
                if fm.M_max > 1e-9 * max(1.0, abs(Ms).max()):
                    ax.plot(fm.x_max, -fm.M_max, "o", color=color, ms=3.5)
                    ax.annotate(f"{fm.M_max:.2f}", (fm.x_max, -fm.M_max), textcoords="offset points",
                                xytext=(0, -1.5 * fs), ha="center", fontsize=fs, color=color,
                                fontweight="bold")
        lim = 1.4 * max(np.abs(p.M).max(), 1e-12)
        ax.set_ylim(-lim, lim)
        ax.set_ylabel(f"M [{unit}]  (+ ↓)", fontsize=fs)
        ax.tick_params(labelsize=fs - 1)
        ax.yaxis.set_major_formatter(_neg_formatter())
        ax.grid(True, alpha=0.25, ls="--")

    def plot_V(self, ax, *, unit: str = "kN", annotate: bool = True,
               color: str = "#1f77b4", fs: float = 8.0) -> None:
        """Shear force diagram, positive upward; jumps at supports and point loads."""
        p = self.profiles()
        ax.fill_between(p.x, 0, p.V, color=color, alpha=0.12, lw=0)
        ax.plot(p.x, p.V, color=color, lw=1.8)
        ax.axhline(0, color="black", lw=0.8)
        for xk in self.x_supports:
            ax.axvline(xk, color="0.75", lw=0.6, ls=":")
        if annotate:
            Vl, Vr = self.shear_left, self.shear_right
            for k, xk in enumerate(self.x_supports):
                if k > 0:
                    ax.annotate(f"{Vl[k]:.2f}", (xk, Vl[k]), textcoords="offset points",
                                xytext=(-4, -1.4 * fs if Vl[k] < 0 else 4), ha="right", fontsize=fs - 0.5,
                                color=color)
                if k < self.n_spans:
                    ax.annotate(f"{Vr[k]:.2f}", (xk, Vr[k]), textcoords="offset points",
                                xytext=(4, 4 if Vr[k] > 0 else -1.4 * fs), ha="left", fontsize=fs - 0.5,
                                color=color)
        lim = 1.4 * max(np.abs(p.V).max(), 1e-12)
        ax.set_ylim(-lim, lim)
        ax.set_ylabel(f"V [{unit}]", fontsize=fs)
        ax.tick_params(labelsize=fs - 1)
        ax.grid(True, alpha=0.25, ls="--")


def _neg_formatter():
    """Tick labels showing −y, for diagrams drawn with positive values downward."""
    import matplotlib.ticker as mticker

    return mticker.FuncFormatter(lambda v, _: f"{-v + 0.0:g}")
