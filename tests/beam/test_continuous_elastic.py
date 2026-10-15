"""Linear-elastic continuous beam: table values, the GdT lecture example, equilibrium, compatibility."""
import numpy as np
import pytest

from scite.beam.continuous import ElasticContinuousBeam, PointLoad, UniformLoad

# Table values for continuous beams with equal spans l (Schneider, Bautabellen; GdT
# script Table 3.7). Moments × q l² resp. × P l, forces × q l resp. × P, for the load
# types 1 (uniform q), 5 (P at midspan) and 6 (P at both third points).
# Rows: (number of spans, loaded spans, {quantity: (type 1, type 5, type 6)}).
# M1, M2: largest field moment of span 1, 2 (most negative if the span is unloaded);
# Mb, Mc: support moments; A, B, C: reactions; Qbl/Qbr/Qcl: shear left/right of B, left of C.
TABLE_3_7 = [
    (2, [1, 1], {"M1": (0.070, 0.156, 0.222), "Mb": (-0.125, -0.188, -0.333),
                 "A": (0.375, 0.313, 0.667), "B": (1.250, 1.375, 2.667),
                 "Qbl": (-0.625, -0.688, -1.333)}),
    (2, [1, 0], {"M1": (0.096, 0.203, 0.278), "Mb": (-0.063, -0.094, -0.167),
                 "A": (0.438, 0.406, 0.833), "C": (-0.063, -0.094, -0.167)}),
    (3, [1, 1, 1], {"M1": (0.080, 0.175, 0.244), "M2": (0.025, 0.100, 0.067),
                    "Mb": (-0.100, -0.150, -0.267), "A": (0.400, 0.350, 0.733),
                    "B": (1.100, 1.150, 2.267), "Qbl": (-0.600, -0.650, -1.267),
                    "Qbr": (0.500, 0.500, 1.000)}),
    (3, [1, 0, 1], {"M1": (0.101, 0.213, 0.289), "M2": (-0.050, -0.075, -0.133),
                    "Mb": (-0.050, -0.075, -0.133), "A": (0.450, 0.425, 0.867)}),
    (3, [0, 1, 0], {"M2": (0.075, 0.175, 0.200), "Mb": (-0.050, -0.075, -0.133),
                    "A": (-0.050, -0.075, -0.133)}),
    (3, [1, 1, 0], {"Mb": (-0.117, -0.175, -0.311), "Mc": (-0.033, -0.050, -0.089),
                    "B": (1.200, 1.300, 2.533), "Qbl": (-0.617, -0.675, -1.311),
                    "Qbr": (0.583, 0.625, 1.222)}),
    (3, [0, 0, 1], {"Mb": (0.017, 0.025, 0.044), "Mc": (-0.067, -0.100, -0.178),
                    "Qbl": (0.017, 0.025, 0.044), "Qbr": (-0.083, -0.125, -0.222)}),
    (4, [1, 1, 1, 1], {"M1": (0.077, 0.170, 0.238), "M2": (0.036, 0.116, 0.111),
                       "Mb": (-0.107, -0.161, -0.286), "Mc": (-0.071, -0.107, -0.190),
                       "A": (0.393, 0.339, 0.714), "B": (1.143, 1.214, 2.381),
                       "C": (0.929, 0.892, 1.810), "Qbl": (-0.607, -0.661, -1.286),
                       "Qbr": (0.536, 0.554, 1.095), "Qcl": (-0.464, -0.446, -0.905)}),
    (4, [1, 0, 1, 0], {"M1": (0.100, 0.210, 0.286), "Mb": (-0.054, -0.080, -0.143),
                       "Mc": (-0.036, -0.054, -0.095), "A": (0.446, 0.420, 0.857)}),
    (4, [0, 1, 0, 1], {"M2": (0.080, 0.183, 0.222), "Mb": (-0.054, -0.080, -0.143),
                       "Mc": (-0.036, -0.054, -0.095), "A": (-0.054, -0.080, -0.143)}),
]


def _loads(n, loaded, kind, l=1.0):
    out = []
    for i in range(n):
        if not loaded[i]:
            continue
        if kind == 0:
            out.append(UniformLoad(span=i, q=1.0))
        elif kind == 1:
            out.append(PointLoad(span=i, P=1.0, a=l / 2))
        else:
            out += [PointLoad(span=i, P=1.0, a=l / 3), PointLoad(span=i, P=1.0, a=2 * l / 3)]
    return out


def _quantities(b: ElasticContinuousBeam, loaded) -> dict:
    fm = b.field_moments()
    field = [f.M_max if loaded[f.span] else f.M_min for f in fm]
    Ms, R, Vl, Vr = b.support_moments, b.reactions, b.shear_left, b.shear_right
    q = {"M1": field[0], "Mb": Ms[1], "A": R[0], "B": R[1], "C": R[2], "Qbl": Vl[1], "Qbr": Vr[1]}
    if b.n_spans > 1:
        q["M2"] = field[1]
    if b.n_spans > 2:
        q.update(Mc=Ms[2], Qcl=Vl[2])
    return q


@pytest.mark.parametrize("kind", [0, 1, 2], ids=["uniform", "P_mid", "P_thirds"])
@pytest.mark.parametrize("row", TABLE_3_7, ids=lambda r: f"{r[0]}span-{''.join(map(str, r[1]))}")
def test_table_3_7(row, kind):
    n, loaded, values = row
    b = ElasticContinuousBeam(L=[1.0] * n, loads=_loads(n, loaded, kind))
    got = _quantities(b, loaded)
    for name, v in values.items():
        # the table is rounded to three decimals (and 0.892 for C, type 5, is 0.8929)
        assert got[name] == pytest.approx(v[kind], abs=1e-3), name


def test_lecture_example_two_spans():
    """GdT lecture 1: two spans of 3 m, q = 2 kN/m."""
    b = ElasticContinuousBeam(L=[3.0, 3.0], loads=[UniformLoad(span=0, q=2.0),
                                                   UniformLoad(span=1, q=2.0)])
    assert b.support_moments[1] == pytest.approx(-2.25)           # −q l²/8
    assert b.reactions == pytest.approx([2.25, 7.5, 2.25])          # 0.375, 1.25 q l
    assert b.shear_left[1] == pytest.approx(-3.75)                  # −0.625 q l
    f1 = b.field_moments()[0]
    assert f1.M_max == pytest.approx(9.0 / 128.0 * 2.0 * 9.0)      # 0.0703 q l² = 1.266
    assert f1.x_max == pytest.approx(0.375 * 3.0)                   # where V = 0


def test_single_span_is_the_simple_beam():
    b = ElasticContinuousBeam(L=[4.0], loads=[UniformLoad(span=0, q=5.0),
                                              PointLoad(span=0, P=8.0, a=1.0)])
    assert b.support_moments == pytest.approx([0.0, 0.0])
    assert b.reactions == pytest.approx([5 * 4 / 2 + 8 * 3 / 4, 5 * 4 / 2 + 8 * 1 / 4])
    x = 1.0
    assert b.moment_at(x) == pytest.approx(b.reactions[0] * x - 5 * x**2 / 2)


def test_unequal_two_spans_clapeyron_closed_form():
    """M_B = −q (l₁³ + l₂³) / (8 (l₁ + l₂)) for a uniform load on both spans."""
    l1, l2, q = 4.0, 6.0, 3.0
    b = ElasticContinuousBeam(L=[l1, l2], loads=[UniformLoad(span=0, q=q), UniformLoad(span=1, q=q)])
    assert b.support_moments[1] == pytest.approx(-q * (l1**3 + l2**3) / (8 * (l1 + l2)))


@pytest.mark.parametrize("n", [2, 3, 4])
def test_equilibrium_and_compatibility(n):
    rng = np.random.default_rng(n)
    L = list(rng.uniform(2.0, 6.0, n))
    loads = [UniformLoad(span=i, q=float(rng.uniform(0.5, 4.0))) for i in range(n)]
    loads += [PointLoad(span=i, P=float(rng.uniform(1, 10)), a=L[i] * 0.3) for i in range(0, n, 2)]
    b = ElasticContinuousBeam(L=L, loads=loads)
    # vertical equilibrium and moment equilibrium about A
    assert b.reactions.sum() == pytest.approx(b.total_load)
    xs = b.x_supports
    m_loads = sum(ld.q * b.L[ld.span] * (xs[ld.span] + b.L[ld.span] / 2) for ld in loads
                  if isinstance(ld, UniformLoad))
    m_loads += sum(ld.P * (xs[ld.span] + ld.a) for ld in loads if isinstance(ld, PointLoad))
    assert (b.reactions * xs).sum() == pytest.approx(m_loads)
    # rotation continuity over the interior supports (what the support moments enforce)
    x, w, t = b.deflection(n_per_span=4001)
    for xk in xs[1:-1]:
        left = t[np.flatnonzero(np.isclose(x, xk))[0]]
        right = t[np.flatnonzero(np.isclose(x, xk))[-1]]
        assert left == pytest.approx(right, rel=1e-3, abs=1e-6 * np.abs(t).max())
    assert w[np.isin(x, xs)] == pytest.approx(0.0, abs=1e-12)


def test_profiles_decompose_into_simple_beam_and_closing_line():
    b = ElasticContinuousBeam(L=[3.0, 4.0, 3.0], loads=[UniformLoad(span=i, q=2.0) for i in range(3)])
    p = b.profiles()
    assert p.M == pytest.approx(p.M0 + p.M_line)
    assert np.abs(p.M0[np.isin(p.x, b.x_supports)]).max() == pytest.approx(0.0, abs=1e-12)
    # dM/dx = V between the jumps
    i = (p.span == 1)
    dMdx = np.gradient(p.M[i], p.x[i])
    assert dMdx[5:-5] == pytest.approx(p.V[i][5:-5], abs=1e-2)


def test_field_moment_at_point_load_and_shear_jump():
    b = ElasticContinuousBeam(L=[2.0, 2.0], loads=[PointLoad(span=0, P=10.0, a=1.0)])
    f1 = b.field_moments()[0]
    assert f1.x_max == pytest.approx(1.0)
    assert f1.M_max == pytest.approx(0.203 * 10 * 2.0, abs=0.01)   # table row (2, [1, 0]), type 5
    p = b.profiles()
    at_P = np.flatnonzero(np.isclose(p.x, 1.0))
    assert p.V[at_P[0]] - p.V[at_P[-1]] == pytest.approx(10.0)      # V drops by P under the load


def test_invalid_input():
    with pytest.raises(ValueError):
        ElasticContinuousBeam(L=[3.0], loads=[UniformLoad(span=1, q=1.0)])
    with pytest.raises(ValueError):
        ElasticContinuousBeam(L=[3.0], loads=[PointLoad(span=0, P=1.0, a=3.0)])
    with pytest.raises(ValueError):
        ElasticContinuousBeam(L=[3.0, -1.0])
