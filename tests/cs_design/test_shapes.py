"""Shapes: InvTShape mirror identities, BandShape closed forms, get_bands()."""
import numpy as np
import pytest

from scite.cs_design.shapes import BandShape, InvTShape, IShape, RectangularShape, TShape

DIMS = dict(b_f=800.0, h_f=50.0, b_w=90.0, h_w=200.0)


def _band_integrals(shape):
    """A, S_0, I_0 about y=0 from the band decomposition (exact for constant widths)."""
    A = S = I = 0.0
    for y0, y1, b in shape.get_bands():
        A += b * (y1 - y0)
        S += b * (y1 ** 2 - y0 ** 2) / 2.0
        I += b * (y1 ** 3 - y0 ** 3) / 3.0
    return A, S, I


def test_invt_mirrors_t():
    t, it = TShape(**DIMS), InvTShape(**DIMS)
    h = t.h_total
    assert it.h_total == h
    assert it.area == pytest.approx(t.area)
    assert it.I_y == pytest.approx(t.I_y)
    assert it.centroid_y == pytest.approx(h - t.centroid_y)
    assert it.W_top == pytest.approx(t.W_bottom)
    assert it.W_bottom == pytest.approx(t.W_top)
    y = np.array([1.0, 30.0, 49.0, 51.0, 120.0, 249.0])
    np.testing.assert_allclose(it.get_width_at_y(y), t.get_width_at_y(h - y))


def test_invt_moments_about_bottom():
    it = InvTShape(**DIMS)
    A, S, I = _band_integrals(it)
    assert it.area == pytest.approx(A)
    assert it.first_moment_of_area_bottom == pytest.approx(S)
    assert it.second_moment_of_area_bottom == pytest.approx(I)
    assert it.centroid_y == pytest.approx(S / A)
    assert it.I_y == pytest.approx(I - S ** 2 / A)


def test_invt_grid_and_polygon():
    it = InvTShape(**DIMS)
    y = it.get_y_coordinates(100)
    assert y[0] == 0.0 and y[-1] == pytest.approx(it.h_total)
    assert np.any(np.isclose(y, it.h_f)), "flange-web junction must be a grid point"
    assert np.all(np.diff(y) > 0)
    poly = it.get_boundary_polygon()
    x, yy = poly[:, 0], poly[:, 1]
    # shoelace area == section area
    area = 0.5 * abs(np.dot(x, np.roll(yy, 1)) - np.dot(yy, np.roll(x, 1)))
    assert area == pytest.approx(it.area)
    assert it.web_span == (it.h_f, it.h_total)
    assert it.flange_span == (0.0, it.h_f)


def test_band_closed_forms():
    bs = BandShape(y0=250.0, y1=330.0, b=710.0)
    assert bs.area == pytest.approx(710.0 * 80.0)
    A, S, I = _band_integrals(bs)
    assert bs.first_moment_of_area_bottom == pytest.approx(S)
    assert bs.second_moment_of_area_bottom == pytest.approx(I)
    assert bs.centroid_y == pytest.approx(290.0)
    assert bs.I_y == pytest.approx(I - S ** 2 / A)
    np.testing.assert_allclose(bs.get_width_at_y(np.array([249.0, 250.0, 300.0, 331.0])),
                               [0.0, 710.0, 710.0, 0.0])


def test_band_gap_polygons():
    bs = BandShape(y0=50.0, y1=250.0, b=710.0, gap=90.0)
    left, right = bs.get_boundary_polygons()
    w = lambda p: p[:, 0].max() - p[:, 0].min()
    assert w(left) + w(right) == pytest.approx(710.0)
    assert right[:, 0].min() - left[:, 0].max() == pytest.approx(90.0)
    assert len(BandShape(y0=0.0, y1=1.0, b=10.0).get_boundary_polygons()) == 1


def test_band_rejects_inverted_extent():
    with pytest.raises(ValueError):
        BandShape(y0=100.0, y1=100.0, b=10.0)


@pytest.mark.parametrize("shape", [
    RectangularShape(b=300.0, h=500.0),
    TShape(**DIMS),
    InvTShape(**DIMS),
    IShape(b_f=400.0, h_f=100.0, b_w=150.0, h_w=300.0),
])
def test_bands_consistent_with_shape(shape):
    A, S, I = _band_integrals(shape)
    assert shape.area == pytest.approx(A)
    assert shape.first_moment_of_area_bottom == pytest.approx(S)
    assert shape.second_moment_of_area_bottom == pytest.approx(I)
    for y0, y1, b in shape.get_bands():
        assert shape.get_width_at_y(np.array([0.5 * (y0 + y1)]))[0] == pytest.approx(b)
