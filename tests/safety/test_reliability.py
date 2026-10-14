"""Safety margin of two normal variables: β, p_f, and the semi-probabilistic values."""
import numpy as np
import pytest

from scite.safety import SafetyMargin


def test_course_example_beta_and_pf():
    m = SafetyMargin(mu_E=30.0, sigma_E=3.0, mu_R=40.0, sigma_R=4.0)
    assert m.mu_M == pytest.approx(10.0)
    assert m.sigma_M == pytest.approx(5.0)
    assert m.beta == pytest.approx(2.0)
    assert m.p_f == pytest.approx(0.02275, rel=1e-3)


def test_target_beta_rc2():
    assert SafetyMargin.pf_from_beta(3.8) == pytest.approx(7.2e-5, rel=0.02)
    assert SafetyMargin.beta_from_pf(SafetyMargin.pf_from_beta(3.8)) == pytest.approx(3.8)


def test_densities_integrate_to_one():
    m = SafetyMargin()
    x = np.linspace(-100, 200, 20001)
    for pdf in (m.pdf_E, m.pdf_R, m.pdf_M):
        assert np.trapezoid(pdf(x), x) == pytest.approx(1.0, abs=1e-6)


def test_design_values_bracket_characteristic_values():
    m = SafetyMargin(mu_E=30.0, sigma_E=3.0, mu_R=40.0, sigma_R=4.0, beta_target=3.8)
    assert m.E_k < m.E_d                      # action: design above characteristic
    assert m.R_d < m.R_k < m.mu_R             # resistance: design below characteristic
    assert m.gamma_E > 1.0 and m.gamma_R > 1.0
    assert m.E_d == pytest.approx(30.0 + 0.7 * 3.8 * 3.0)
    assert m.R_d == pytest.approx(40.0 - 0.8 * 3.8 * 4.0)
    assert not m.verified                    # β = 2.0 < 3.8: E_d > R_d


def test_verification_matches_beta_target_order():
    """E_d ≤ R_d at β_t holds roughly iff β ≥ β_t (α_E² + α_R² = 1.13 > 1 makes it slightly conservative)."""
    m = SafetyMargin(mu_E=30.0, sigma_E=3.0, mu_R=52.0, sigma_R=4.0, beta_target=3.8)
    assert m.beta > 3.8 and m.verified


def test_plot_adapter_draws(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    SafetyMargin().plot_pdfs(ax, show_design_values=True)
    assert len(ax.lines) >= 4
    plt.close(fig)
