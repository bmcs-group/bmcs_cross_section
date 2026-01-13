import bmcs_utils.api as bu
import sympy as sp
import numpy as np
import traits.api as tr
from bmcs_cross_section.matmod import MatMod

class ConcreteCompressionEC2PlateauSymbExpr(bu.SymbExpr):
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
    # -------------- Concrete material law according to EC2 Eq. (3.14) ------------------
    # f_cm = sp.Symbol('f_cm', real=True)
    f_c = sp.Symbol('f_c', real=True)
    n = sp.Symbol('n', real=True)

    # EC2 eq. (3.17-3.18)
    a = (1 - eps / eps_cy)
    sig_c = f_c * (1 - sp.sign(a) * sp.Abs(a) ** n)
    sig = -sp.Piecewise(
        (0, eps < eps_cu),
        (f_c, eps <= eps_cy),
        (sig_c, eps < 0),
        (0, True)
    )

    symb_model_params = ('E_cc', 'f_c', 'eps_cy', 'eps_cu', 'n')

    symb_expressions = [
        ('sig', ('eps',)),
    ]


class ConcreteCompressionEC2Plateau(MatMod, bu.InjectSymbExpr):
    name = 'EC2 with plateau'

    symb_class = ConcreteCompressionEC2PlateauSymbExpr

    E_cc = bu.Float(25000, MAT=True, desc='E modulus of concrete in compression')
    f_c = bu.Float(25, MAT=True, desc='Compressive strength of concrete')
    eps_cy = bu.Float(-0.003, MAT=True)
    eps_cu = bu.Float(-0.01, MAT=True)
    n = bu.Float(2, MAT=True)

    ipw_view = bu.View(
        bu.Item('E_cc', latex=r'E_\mathrm{cc} \mathrm{[MPa]}'),
        bu.Item('f_c', latex=r'f_\mathrm{c} \mathrm{[MPa]}'),
        bu.Item('eps_cy', latex=r'\varepsilon_{cy}'),
        bu.Item('eps_cu', latex=r'\varepsilon_{cu}'),
        bu.Item('n', latex=r'n'),
    )

    eps_min = tr.Property
    def _get_eps_min(self):
        return 1.1 * self.eps_cu

    def get_eps_plot_range(self):
        return np.linspace(self.eps_min, 0.5 * -self.eps_min, 300)

    def get_sig(self,eps):
        return self.symb.get_sig(eps)

