import bmcs_utils.api as bu
import sympy as sp
import numpy as np
import traits.api as tr

from bmcs_cross_section.norms.ec2 import EC2
from bmcs_cross_section.matmod.matmod import MatMod

class ConcreteMatMod(MatMod):

    # TODO: replace factor with safety_format
    # safety_format = tr.Enum('mean', 'characteristic', 'design')

    factor = bu.Float(1, MAT=True) # 0.85 / 1.5
    '''Factor to embed a EC2 based safety factors.
    This multiplication qualitatively modifies the material
    behavior which is not correct. No distinction between
    the scatter of strength and stiffness parameters.
    '''

class PWLConcreteMatModSymbExpr(bu.SymbExpr):
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

    sig = sp.Piecewise(
        (0, eps < eps_cu),
        (E_cc * eps_cy, eps < eps_cy),
        (E_cc * eps, eps < 0),
        (E_ct * eps, eps < eps_cr),
        (mu * E_ct * eps_cr, eps < eps_tu),
        (0, True)
    )

    # # If using the following ext instead of (0, eps < eps_cu), better numerical instability (BUT HIGHER MOMENT VALUES in
    # # case of concrete failure!)
    # # ext = 0.15
    # sig = sp.Piecewise(
    #     (0, eps < eps_cu + ext * eps_cy),
    #     ((E_cc / ext) * (eps_cu + ext * eps_cy - eps), eps < eps_cu),
    #     (E_cc * eps_cy, eps < eps_cy),
    #     (E_cc * eps, eps < 0),
    #     (E_ct * eps, eps < eps_cr),
    #     (mu * E_ct * eps_cr, eps < eps_tu),
    #     (0, True)
    # )

    symb_model_params = ('E_ct', 'E_cc', 'eps_cr', 'eps_cy', 'eps_cu',
                         'mu', 'eps_tu')

    symb_expressions = [
        ('sig', ('eps',)),
    ]


class PWLConcreteMatMod(ConcreteMatMod, bu.InjectSymbExpr):
    name = 'Concrete PWL'

    symb_class = PWLConcreteMatModSymbExpr

    E_ct = bu.Float(24000, MAT=True, desc='E modulus of matrix on tension')
    E_cc = bu.Float(25000, MAT=True, desc='E modulus of matrix on compression')
    eps_cr = bu.Float(0.00015, MAT=True, desc='Matrix cracking strain')
    _eps_cy = bu.Float(-0.003, MAT=True)
    _eps_cu = bu.Float(-0.01, MAT=True)

    # Enforcing negative values for eps_cu and eps_cy
    eps_cy = tr.Property(desc='Matrix compressive yield strain')
    def _set_eps_cy(self, value):
        self._eps_cy = value
    def _get_eps_cy(self):
        return -np.fabs(self._eps_cy)

    eps_cu = tr.Property(desc='Ultimate matrix compressive strain')
    def _set_eps_cu(self, value):
        self._eps_cu = value
    def _get_eps_cu(self):
        return -np.fabs(self._eps_cu)

    f_cm = tr.Property(desc='Mean compressive strength')
    def _get_f_cm(self):
        return self.E_cc * self.eps_cy

    eps_tu = bu.Float(0.0004, MAT=True, desc='Ultimate matrix tensile strain')

    mu = bu.Float(0.33, MAT=True,
                  desc='Post crack tensile strength ratio (represents how much strength is left after \
                        the crack because of short steel fibers in the mixture)')

    ipw_view = bu.View(
        bu.Item('factor'),
        bu.Item('E_ct', latex=r'E_\mathrm{ct} \mathrm{[MPa]}'),
        bu.Item('E_cc', latex=r'E_\mathrm{cc} \mathrm{[MPa]}'),
        bu.Item('eps_cr', latex=r'\varepsilon_{cr}'),
        bu.Item('eps_cy', latex=r'\varepsilon_{cy}', editor=bu.FloatEditor()),
        bu.Item('eps_cu', latex=r'\varepsilon_{cu}', editor=bu.FloatEditor()),
        bu.Item('eps_tu', latex=r'\varepsilon_{tu}'),
        bu.Item('mu', latex=r'\mu')
    )

    def get_eps_plot_range(self):
        return np.linspace(1.1 * self.eps_cu, 1.1 * self.eps_tu, 300)

    def get_sig(self,eps):
        return self.factor * self.symb.get_sig(eps)


class EC2ConcreteMatModBase(ConcreteMatMod):
    # Optional attributes
    # mu must be between 0 and 1
    mu = bu.Float(0.0, MAT=True, desc='Post crack tensile strength ratio (represents how much strength is left after \
                                    the crack because of short steel fibers in the mixture)')

    _eps_cr = None
    eps_cr = tr.Property(desc='Matrix cracking strain', MAT=True)
    def _set_eps_cr(self, value):
        self._eps_cr = value
    def _get_eps_cr(self):
        if self._eps_cr is not None:
            return self._eps_cr
        else:
            if self.factor == 1:
                return EC2.get_f_ctm(self.f_ck) / self.E_ct
            else:
                f_ctk = EC2.get_f_ctk_0_05(self.f_ck)
                E_k = self.f_ck / EC2.get_eps_c3(self.f_ck)
                return f_ctk / E_k

    _eps_tu = None
    eps_tu = tr.Property(desc='Ultimate matrix tensile strain', MAT=True)
    def _set_eps_tu(self, value):
        self._eps_tu = value
    def _get_eps_tu(self):
        if self._eps_tu is not None:
            return self._eps_tu
        else:
            return self.eps_cr

    _E_cc = None
    E_cc = tr.Property(desc='E modulus of matrix on compression', MAT=True)
    def _set_E_cc(self, value):
        self._E_cc = value
    def _get_E_cc(self):
        if self._E_cc is not None:
            return self._E_cc
        else:
            if self.factor == 1:
                return EC2.get_E_cm(self.f_ck)
            else:
                E_k = self.f_ck / EC2.get_eps_c3(self.f_ck)
                return E_k

    _E_ct = None
    E_ct = tr.Property(desc='E modulus of matrix on tension', MAT=True)
    def _set_E_ct(self, value):
        self._E_ct = value
    def _get_E_ct(self):
        if self._E_ct is not None:
            return self._E_ct
        else:
            if self.factor == 1:
                return EC2.get_E_cm(self.f_ck)
            else:
                E_k = self.f_ck / EC2.get_eps_c3(self.f_ck)
                return E_k


    _f_ctm = None
    f_ctm = tr.Property(desc='Axial tensile strength of concrete', MAT=True)
    def _set_f_ctm(self, value):
        self._f_ctm = value

    def _get_f_ctm(self):
        if self._f_ctm is not None:
            return self._f_ctm
        else:
            return EC2.get_f_ctm(self.f_ck)

    ipw_view = bu.View(
        bu.Item('f_cm', latex=r'^*f_\mathrm{cm}~\mathrm{[MPa]}', editor=bu.FloatEditor()),
        bu.Item('eps_cr', latex=r'\varepsilon_{cr}', editor=bu.FloatEditor()),
        bu.Item('eps_tu', latex=r'\varepsilon_{tu}', editor=bu.FloatEditor()),
        bu.Item('mu', latex=r'\mu'),
        bu.Item('E_ct', latex=r'E_\mathrm{ct}~\mathrm{[MPa]}', editor=bu.FloatEditor()),
        bu.Item('E_cc', latex=r'E_\mathrm{cc}~\mathrm{[MPa]}', editor=bu.FloatEditor()),
        bu.Item('factor'),
    )

    def get_eps_plot_range(self):
        return np.linspace(1.5 * self.eps_cu, 5 * self.eps_tu, 600)


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

    eps_cu = tr.Property(desc='Ultimate matrix compressive strain', MAT=True)
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
        # sp.solve instead of (0, eps < eps_cu), in case of numerical instability (BUT HIGHER MOMENT VALUES in
        # case of concrete failure!)
        # (0, eps < sp.solve(sig_c, eps)[1]),
        (0, eps < eps_cu),
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

    eps_cu = tr.Property(desc='Ultimate matrix compressive strain', MAT=True)
    def _get_eps_cu(self):
        return -EC2.get_eps_cu1(self.f_ck)

    ipw_view = bu.View(
        *EC2ConcreteMatModBase.ipw_view.content,
    )

    def get_sig(self, eps):
        return self.factor * self.symb.get_sig(eps)
