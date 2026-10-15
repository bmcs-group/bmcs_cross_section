import bmcs_utils.api as bu
import sympy as sp
import numpy as np
import traits.api as tr
from .ec2_concrete_matmod_base import EC2ConcreteMatModBase
from .ec2 import EC2


class EC2PlateauConcreteMatModSymbExpr(bu.SymbExpr):
    """Piecewise linear concrete material law
    """
    eps = sp.Symbol('eps', real=True)

    # -------------------------------------------------------------------------
    # Model parameters
    # -------------------------------------------------------------------------
    E_ct, E_cc, eps_cr, eps_tu, mu = sp.symbols(
        r'E_ct, E_cc, varepsilon_cr, varepsilon_tu, mu', real=True,
        nonnegative=True
    )
    eps_cy, eps_cu = sp.symbols(
        r'varepsilon_cy, varepsilon_cu',
        real=True, nonpositive=True
    )
    # -------------- Concrete material law according to EC2 Eq. (3.14) ------------------
    # f_cm = sp.Symbol('f_cm', real=True)
    f_cd = sp.Symbol('f_cd', real=True)
    n = sp.Symbol('n', real=True)

    # k = 1.05 * E_cc * sp.Abs(eps_cy) / f_cm
    # eta = eps / eps_cy
    # sig_c = f_cm * (k * eta - eta ** 2) / (1 + eta * (k - 2))

    # with continuous curve until sig_c = 0
    # eps_at_sig_0 = sp.solve(sig_c, self.eps)[1]
    # sig_c_eps = -sp.Piecewise(
    #     (0, self.eps < eps_at_sig_0),
    #     (sig_c, self.eps <= 0),  # use eps <= 0),
    #
    #     # Tension branch
    #     (-self.E_ct * self.eps, self.eps < self.eps_cr),
    #
    #     (0, True)
    # )

    # with extra line
    # eps_extra = 0.005
    # sig_c_cu = sig_c.subs(self.eps, self.eps_cu)
    # extra_line = sig_c_cu + sig_c_cu * (self.eps - self.eps_cu) / eps_extra
    # eps_at_sig_0 = sp.solve(extra_line, self.eps)[0]
    # sig_c_eps = -sp.Piecewise(
    #     (0, self.eps < eps_at_sig_0),
    #     (extra_line, self.eps < self.eps_cu),
    #     (sig_c, self.eps <= 0),
    #     (0, True)
    # )

    # with direct drop exactly like EC2 drawing
    # sig_c_eps = - sp.Piecewise(
    #     (0, self.eps < self.eps_cu),
    #     (sig_c, self.eps <= 0),
    #     (0, True)
    # )

    # EC2 eq. (3.17-3.18)
    sig_c = f_cd * (1 - (1 - eps / eps_cy) ** n)
    sig = -sp.Piecewise(
        (0, eps < eps_cu),
        (f_cd, eps < eps_cy),
        (sig_c, eps < 0),
        # Tension branch
        (-E_ct * eps, eps < eps_cr),
        # Tension branch, adding post-peak branch
        (-mu * E_ct * eps_cr, eps < eps_tu),
        (0, True)
    )

    symb_model_params = ('E_ct', 'E_cc', 'eps_cr', 'eps_cy', 'eps_cu',
                         'mu', 'eps_tu', 'f_cd', 'n')

    symb_expressions = [
        ('sig', ('eps',)),
    ]

class EC2PlateauConcreteMatMod(EC2ConcreteMatModBase, bu.InjectSymbExpr):
    name = 'EC2 Concrete with Plateau'

    symb_class = EC2PlateauConcreteMatModSymbExpr

    f_cm = bu.Float(28)

    f_cd = tr.Property(desc='Design compressive strength of concrete', MAT=True)
    def _get_f_cd(self):
        if self.factor == 1:
            return self.f_cm
        else:
            return EC2.get_f_cd(self.f_ck, factor=self.factor)

    f_ck = tr.Property(desc='Characteristic compressive strength of concrete', MAT=True)
    def _get_f_ck(self):
        return EC2.get_f_ck_from_f_cm(self.f_cm)

    n = tr.Property(desc='Exponent used in EC2, eq. 3.17', MAT=True)
    def _get_n(self):
        return EC2.get_n(self.f_ck)

    eps_cy = tr.Property(desc='Matrix compressive yield strain', MAT=True)
    def _get_eps_cy(self):
        return -EC2.get_eps_c2(self.f_ck)

    eps_cu = tr.Property(desc='Ultimate concrete compressive strain', MAT=True)
    def _get_eps_cu(self):
        return -EC2.get_eps_cu2(self.f_ck)

    def get_sig(self, eps):
        sig = self.symb.get_sig(eps)
        # Compression branch is scaled when defining f_cd
        sig_with_scaled_tension_branch = np.where(sig > 0, self.factor * sig, sig)
        return sig_with_scaled_tension_branch

    ipw_view = bu.View(
        *EC2ConcreteMatModBase.ipw_view.content,
    )
