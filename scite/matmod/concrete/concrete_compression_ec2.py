import bmcs_utils.api as bu
import sympy as sp
import traits.api as tr
import numpy as np
from bmcs_cross_section.matmod import MatMod

class ConcreteCompressionEC2SymbExpr(bu.SymbExpr):
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
    f_c = sp.Symbol('f_c', real=True)

    # EC2 eq. (3.14) -----------
    k = 1.05 * E_cc * sp.Abs(eps_cy) / f_c
    eta = eps / eps_cy
    sig_c = f_c * (k * eta - eta ** 2) / (1 + eta * (k - 2))
    sig = -sp.Piecewise(
        (0, eps < sp.solve(sig_c, eps)[1]), # instead of (0, eps < eps_cu), to avoid extension when f_cm = 50
        (sig_c, eps < 0),
        (0, True)
    )


    symb_model_params = ('E_cc', 'eps_cy', 'eps_cu', 'f_c')

    symb_expressions = [
        ('sig', ('eps',)),
    ]

class ConcreteCompressionEC2(MatMod, bu.InjectSymbExpr):
    name = 'EC2'

    symb_class = ConcreteCompressionEC2SymbExpr

    # Required attributes
    E_cc = bu.Float(25000, MAT=True, desc='E modulus of concrete in compression')
    f_c = bu.Float(25, MAT=True, desc='Compressive strength of concrete')
    eps_cy = bu.Float(-0.003, MAT=True)
    eps_cu = bu.Float(-0.01, MAT=True)

    ipw_view = bu.View(
        bu.Item('E_cc', latex=r'E_\mathrm{cc} \mathrm{[MPa]}'),
        bu.Item('f_c', latex=r'f_\mathrm{c} \mathrm{[MPa]}'),
        bu.Item('eps_cy', latex=r'\varepsilon_{cy}'),
        bu.Item('eps_cu', latex=r'\varepsilon_{cu}'),
    )

    eps_min = tr.Property
    def _get_eps_min(self):
        return 1.1 * self.eps_cu

    def get_eps_plot_range(self):
        return np.linspace(self.eps_min, 0.5 * -self.eps_min, 300)

    def get_sig(self, eps):
        return self.symb.get_sig(eps)
