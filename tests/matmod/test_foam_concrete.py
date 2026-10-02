"""FoamConcrete: tangent, peak, softening, residual, zero tension, parabola ≡ EC2."""
import numpy as np
import pytest

from scite.matmod import EC2ParabolaRectangle, FoamConcrete


def test_defaults_initial_tangent_equals_E():
    for law in ('sargin', 'parabola'):
        m = FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0, law=law)
        assert m.eps_c1_computed == pytest.approx(-2 * 2.0 / 1250.0)
        assert m.get_E_t(np.array([-1e-6]))[0] == pytest.approx(1250.0, rel=1e-3)


def test_design_curve_scales_by_gamma():
    m1 = FoamConcrete(gamma=1.0)
    m15 = FoamConcrete(gamma=1.5)
    eps = np.linspace(-0.008, 0.0, 41)
    np.testing.assert_allclose(m15.get_sig(eps), m1.get_sig(eps) / 1.5)


@pytest.mark.parametrize("law", ['sargin', 'parabola'])
def test_peak_and_zero_tension(law):
    m = FoamConcrete(f_c=4.0, E=2500.0, gamma=1.0, law=law)
    assert m.get_sig(np.array([m.eps_c1_computed]))[0] == pytest.approx(-4.0)
    assert np.all(m.get_sig(np.array([0.0, 1e-4, 0.01])) == 0.0)
    eps = np.linspace(m.eps_cu2_computed * 0.999, 0.0, 400)
    assert np.all(m.get_sig(eps) <= 0.0)
    assert np.min(m.get_sig(eps)) == pytest.approx(-4.0, rel=1e-3)


def test_sargin_softens_to_zero_at_k_eps_c1():
    m = FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0)       # k = 2
    assert m.k == pytest.approx(2.0)
    assert m.eps_cu2_computed == pytest.approx(2 * m.eps_c1_computed)
    eta = np.array([1.2, 1.5, 1.9])
    sig = m.get_sig(eta * m.eps_c1_computed)
    assert np.all(np.diff(-sig) < 0), "descending branch must soften monotonically"
    # σ = f·(2η − η²) → 2·(1 − 0.9999²)… ≈ 4e-4 MPa just before the zero at η = 2
    assert m.get_sig(np.array([1.9999 * m.eps_c1_computed]))[0] == pytest.approx(-4e-4, rel=1e-3)
    assert m.get_sig(np.array([2.0001 * m.eps_c1_computed]))[0] == 0.0


def test_explicit_limit_and_residual():
    m = FoamConcrete(f_c=2.0, E=1250.0, gamma=1.0, eps_cu=-0.005, sig_res=0.2)
    assert m.eps_cu2_computed == pytest.approx(-0.005)
    assert m.get_sig(np.array([-0.0051]))[0] == pytest.approx(-0.4)
    assert m.get_sig(np.array([-0.0049]))[0] < -0.4          # still on the branch
    # an eps_cu beyond the Sargin zero is capped at the zero
    assert FoamConcrete(f_c=2.0, E=1250.0, eps_cu=-0.02).eps_cu2_computed \
        == pytest.approx(-0.0064)


def test_parabola_equals_ec2_parabola_rectangle():
    m = FoamConcrete(f_c=3.0, E=1500.0, gamma=1.3, law='parabola', eps_cu=-0.007)
    ec2 = EC2ParabolaRectangle(f_ck=3.0, alpha_cc=1.0, gamma_c=1.3, n=2.0,
                               eps_c2=m.eps_c1_computed, eps_cu2=m.eps_cu2_computed)
    eps = np.linspace(-0.0069, 0.002, 301)
    np.testing.assert_allclose(m.get_sig(eps), ec2.get_sig(eps), atol=1e-12)


def test_validation():
    with pytest.raises(ValueError):
        FoamConcrete(eps_c1=0.002)
    with pytest.raises(ValueError):
        FoamConcrete(f_c=2.0, E=1000.0, eps_c1=-0.001)       # k = 0.5 ≤ 1
