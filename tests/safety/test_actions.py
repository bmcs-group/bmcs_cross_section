"""EN 1990 combinations on the GdT office-floor example and edge cases."""
import pytest

from scite.safety import (LoadCombination, PermanentAction, VariableAction,
                          office_example)


def test_office_example_fundamental_610():
    # 1.35·4.5 + 1.5·3.0 + 1.5·(0.6·1.2 + 0.5·0.8) = 6.075 + 4.5 + 1.68
    r = office_example().uls_fundamental()
    assert r.leading == "Q_imp"
    assert r.permanent == pytest.approx(6.075)
    assert r.leading_value == pytest.approx(4.5)
    assert r.accompanying == pytest.approx(1.68)
    assert r.E_d == pytest.approx(12.255)
    assert sum(v for _, v in r.terms) == pytest.approx(r.E_d)


def test_office_example_sls_rules():
    lc = office_example()
    assert lc.sls_characteristic().E_d == pytest.approx(4.5 + 3.0 + 0.6 * 1.2 + 0.5 * 0.8)
    # frequent: ψ1 of the leading (imposed 0.5) + ψ2 of the others (wind 0, snow 0)
    assert lc.sls_frequent().E_d == pytest.approx(4.5 + 0.5 * 3.0)
    assert lc.sls_quasi_permanent().E_d == pytest.approx(4.5 + 0.3 * 3.0)


def test_610a_and_610b_bracket_610():
    lc = office_example()
    a, b, f = lc.uls_610a(), lc.uls_610b(), lc.uls_fundamental()
    assert a.E_d == pytest.approx(6.075 + 1.5 * (0.7 * 3.0 + 0.6 * 1.2 + 0.5 * 0.8))
    assert b.E_d == pytest.approx(0.85 * 6.075 + 4.5 + 1.68)
    assert max(a.E_d, b.E_d) <= f.E_d
    assert lc.uls_governing().E_d == pytest.approx(max(a.E_d, b.E_d))


def test_leading_action_maximises_the_effect():
    """A smaller action with ψ_0 = 0 can govern as leading because the big one
    keeps most of its value as accompanying action."""
    lc = LoadCombination(
        permanent=[PermanentAction(G_k=0.0)],
        variable=[VariableAction(name="big", Q_k=10.0, psi_0=1.0, psi_1=1.0, psi_2=1.0),
                  VariableAction(name="small", Q_k=9.0, psi_0=0.0, psi_1=0.0, psi_2=0.0)],
    )
    r = lc.uls_fundamental()
    assert r.leading == "small"            # 9 + 1.0·10 > 10 + 0·9
    assert r.E_d == pytest.approx(1.5 * (9.0 + 10.0))


def test_favourable_permanent_and_prestress():
    lc = LoadCombination(permanent=[PermanentAction(name="G1", G_k=2.0),
                                    PermanentAction(name="G2", G_k=1.0, favourable=True)],
                         P=-0.5)
    r = lc.uls_fundamental()
    assert r.permanent == pytest.approx(1.35 * 2.0 + 1.0 * 1.0)
    assert r.prestress == pytest.approx(-0.5)
    assert r.leading is None and r.E_d == pytest.approx(2.7 + 1.0 - 0.5)


def test_from_category_uses_table_a11():
    q = VariableAction.from_category("Q", 1.0, "snow")
    assert (q.psi_0, q.psi_1, q.psi_2) == (0.5, 0.2, 0.0)
    with pytest.raises(KeyError):
        VariableAction.from_category("Q", 1.0, "earthquake")


def test_results_serialise():
    """Node contract: a combination result round-trips through JSON."""
    r = office_example().uls_fundamental()
    assert type(r).model_validate_json(r.model_dump_json()).E_d == pytest.approx(r.E_d)
