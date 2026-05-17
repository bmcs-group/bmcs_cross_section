import bmcs_utils.api as bu
import sympy as sp
import traits.api as tr
from .ec2_concrete_matmod_base import EC2ConcreteMatModBase
from .ec2 import EC2

class EC2ConcreteMatModSymbExpr(bu.SymbExpr):
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
    f_cm = sp.Symbol('f_cm', real=True)

    # EC2 eq. (3.14) -----------
    k = 1.05 * E_cc * sp.Abs(eps_cy) / f_cm
    eta = eps / eps_cy
    sig_c = f_cm * (k * eta - eta ** 2) / (1 + eta * (k - 2))
    sig = -sp.Piecewise(
        (0, eps < sp.solve(sig_c, eps)[1]), # instead of (0, eps < eps_cu), to avoid extension when f_cm = 50
        (sig_c, eps < 0),
        # Tension branch
        (-E_ct * eps, eps < eps_cr),
        # Tension branch, adding post-peak branch
        (-mu * E_ct * eps_cr, eps < eps_tu),
        (0, True)
    )

    # # EC2 with Softening tensile branch -----------
    # L_cb = 200  # [mm] finite length of the softening zone
    # G_F = 0.073 * f_cm ** 0.18  # [N/mm] f_cm must be in MPa (fib Model Code 2010)
    # # G_F = 0.028 * f_cm ** 0.18 * d_ag ** 0.32 # [N/mm] d_ag aggregate diameter (Mari & Cladera)
    # f_ctm = eps_cr * E_ct # temporiarly until I include it directly instead in terms of eps_cr
    # w1 = G_F / f_ctm
    # eps_crack = f_ctm / E_ct
    # w = (eps - eps_crack) * L_cb
    # sig_ct_softening = f_ctm * sp.exp(-w / w1)
    # # EC2 eq. (3.14)
    # k = 1.05 * E_cc * sp.Abs(eps_cy) / f_cm
    # eta = eps / eps_cy
    # sig_c = f_cm * (k * eta - eta ** 2) / (1 + eta * (k - 2))
    # sig = -sp.Piecewise(
    #     (0, eps < sp.solve(sig_c, eps)[1]), # instead of (0, eps < eps_cu), to avoid extension when f_cm = 50
    #     (sig_c, eps < 0),
    #     # Tension branch
    #     (-E_ct * eps, eps < eps_cr),
    #     # Tension branch, adding post-peak branch
    #     (-sig_ct_softening, True)
    # )

    symb_model_params = ('E_ct', 'E_cc', 'eps_cr', 'eps_cy', 'eps_cu',
                         'mu', 'eps_tu', 'f_cm')

    symb_expressions = [
        ('sig', ('eps',)),
    ]

class EC2ConcreteMatMod(EC2ConcreteMatModBase, bu.InjectSymbExpr):
    name = 'EC2 Concrete'

    symb_class = EC2ConcreteMatModSymbExpr

    # Required attributes
    f_cm = bu.Float(28)

    f_ck = tr.Property(desc='Characteristic compressive strength of concrete', MAT=True)
    def _get_f_ck(self):
        return EC2.get_f_ck_from_f_cm(self.f_cm)

    eps_cy = tr.Property(desc='Matrix compressive yield strain', MAT=True)
    def _get_eps_cy(self):
        return -EC2.get_eps_c1(self.f_ck)

    eps_cu = tr.Property(desc='Ultimate concrete compressive strain', MAT=True)
    def _get_eps_cu(self):
        return -EC2.get_eps_cu1(self.f_ck)

    ipw_view = bu.View(
        *EC2ConcreteMatModBase.ipw_view.content,
    )

    def get_sig(self, eps):
        return self.factor * self.symb.get_sig(eps)
