import bmcs_utils.api as bu
import sympy as sp
import numpy as np
import traits.api as tr
from bmcs_cross_section.matmod import MatMod

class ConcreteTensionPWLSymbExpr(bu.SymbExpr):
    """Concrete tension -- piecewice linear
    """
    eps = sp.Symbol('eps', real=True)
    # -------------------------------------------------------------------------
    # Model parameters
    # -------------------------------------------------------------------------
    E_ct, eps_cr, eps_tu, mu = sp.symbols(
        r'E_ct, varepsilon_cr, varepsilon_tu, mu', real=True,
        nonnegative=True
    )

    sig = sp.Piecewise(
        (0, eps < 0),
        (E_ct * eps, eps < eps_cr),
        (mu * E_ct * eps_cr, eps < eps_tu),
        (0, True)
    )

    symb_model_params = ('E_ct', 'eps_cr', 'mu', 'eps_tu')

    symb_expressions = [
        ('sig', ('eps',)),
    ]


class ConcreteTensionPWL(MatMod, bu.InjectSymbExpr):
    """Concrete tension -- piecewice linear
    """
    name = 'piecewise linear'

    symb_class = ConcreteTensionPWLSymbExpr

    E_ct = bu.Float(24000, MAT=True, desc='E modulus of concrete on tension')
    eps_cr = bu.Float(0.00015, MAT=True, desc='Matrix cracking strain')
    eps_tu = bu.Float(0.0004, MAT=True, desc='Ultimate concrete tensile strain')
    mu = bu.Float(0.33, MAT=True,
                  desc='Post crack tensile strength ratio (represents how much strength is left after \
                        the crack because of short steel fibers in the mixture)')

    ipw_view = bu.View(
        bu.Item('E_ct', latex=r'E_\mathrm{ct} \mathrm{[MPa]}'),
        bu.Item('eps_cr', latex=r'\varepsilon_{cr}'),
        bu.Item('eps_tu', latex=r'\varepsilon_{tu}'),
        bu.Item('mu', latex=r'\mu')
    )

    eps_max = tr.Property
    def _get_eps_max(self):
        return 1.1 * self.eps_tu

    def get_eps_plot_range(self):
        return np.linspace(-0.5 * self.eps_max, self.eps_max, 300)

    def get_sig(self,eps):
        return self.symb.get_sig(eps)

