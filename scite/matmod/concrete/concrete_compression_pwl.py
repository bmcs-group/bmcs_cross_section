import bmcs_utils.api as bu
import sympy as sp
import numpy as np
import traits.api as tr
from bmcs_cross_section.matmod import MatMod

class ConcreteCompressionPWLSymbExpr(bu.SymbExpr):
    """Piecewise linear concrete material law for compression
    """
    eps = sp.Symbol('eps', real=True)
    # -------------------------------------------------------------------------
    # Model parameters
    # -------------------------------------------------------------------------
    E_cc = sp.symbols(
        r'E_cc', real=True,
        nonnegative=True
    )
    eps_cy, eps_cu = sp.symbols(
        r'varepsilon_cy, varepsilon_cu',
        real=True, nonpositive=True
    )

    ext = 0.15  # extension percentage after failure to avoid numerical solution instability
    sig = sp.Piecewise(
        (0, eps < eps_cu + ext * eps_cy),
        ((E_cc / ext) * (eps_cu + ext * eps_cy - eps), eps < eps_cu),
        (E_cc * eps_cy, eps < eps_cy),
        (E_cc * eps, eps < 0),
        (0, True)
    )

    symb_model_params = ('E_cc', 'eps_cy', 'eps_cu')

    symb_expressions = [
        ('sig', ('eps',)),
    ]


class ConcreteCompressionPWL(MatMod, bu.InjectSymbExpr):
    name = 'Concrete PWL'

    symb_class = ConcreteCompressionPWLSymbExpr

    E_cc = bu.Float(25000, MAT=True, desc='E modulus of concrete on compression')
    eps_cy = bu.Float(-0.003, MAT=True)
    eps_cu = bu.Float(-0.01, MAT=True)

    ipw_view = bu.View(
        bu.Item('E_cc', latex=r'E_\mathrm{cc} \mathrm{[MPa]}'),
        bu.Item('eps_cy', latex=r'\varepsilon_{cy}', editor=bu.FloatEditor()),
        bu.Item('eps_cu', latex=r'\varepsilon_{cu}', editor=bu.FloatEditor()),
    )

    eps_min = tr.Property
    def _get_eps_min(self):
        return 1.1 * self.eps_cu

    def get_eps_plot_range(self):
        return np.linspace(self.eps_min, 0.5 * -self.eps_min, 300)

    def get_sig(self,eps):
        return self.symb.get_sig(eps)

