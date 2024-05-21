from .matmod import MatMod
import bmcs_utils.api as bu
import sympy as sp
import numpy as np
import traits.api as tr

class ReinfMatMod(MatMod):

    # TODO: replace factor with safety_format
    # safety_format = tr.Enum('mean', 'characteristic', 'design')
    factor = bu.Float(1, MAT=True) # 1. / 1.15
    '''Factor to embed a EC2 based safety factors.
    This multiplication qualitatively modifies the material
    behavior which is not correct. No distinction between
    the scatter of strength and stiffness parameters.
    '''

    def get_f_ult(self):
        raise NotImplementedError

    def get_eps_ult(self):
        raise NotImplementedError

class SteelReinfMatModSymbExpr(bu.SymbExpr):
    """Piecewise linear concrete material law
    """
    eps = sp.Symbol('eps', real=True)

    eps_sy, eps_ud = sp.symbols(r'varepsilon_sy, varepsilon_ud', real=True, nonnegative=True)
    E_s, f_st_scaled, f_sy_scaled = sp.symbols(r'E_s, f_st_scaled, f_sy_scaled', real=True, nonnegative=True)

    ext = 0.7  # extension percentage after failure to avoid numerical solution instability
    f_sy = f_sy_scaled
    f_st = f_st_scaled
    eps_sy = f_sy / E_s
    sig = sp.Piecewise(
        (0, eps < -eps_ud - ext * eps_sy),
        (-f_st + f_st * (-eps - eps_ud) / (ext * eps_sy), eps < -eps_ud),
        (-f_sy - (f_st - f_sy) * ((-eps - eps_sy) / (eps_ud - eps_sy)), eps < -eps_sy),
        (E_s * eps, eps < eps_sy),
        (f_sy + (f_st - f_sy) * ((eps - eps_sy) / (eps_ud - eps_sy)), eps < eps_ud),
        (f_st - f_st * (eps - eps_ud) / (ext * eps_sy), eps < eps_ud + ext * eps_sy),
        (0, True),
    )

    symb_model_params = ('E_s', 'eps_ud', 'f_sy_scaled', 'f_st_scaled')

    symb_expressions = [
        ('sig', ('eps',)),
    ]


class SteelReinfMatMod(ReinfMatMod, bu.InjectSymbExpr):
    name = 'Steel'

    symb_class = SteelReinfMatModSymbExpr

    E_s = bu.Float(200000, MAT=True, desc='E modulus of steel')
    f_sy = bu.Float(500, MAT=True, desc='steel yield stress') # f_sy,m= 550
    f_st = bu.Float(525, MAT=True, desc='steel failure stress = k * f_sy; where k is ductility factor (k=1.05, k=1.08 '
                                        'for A, B steel, respectively') # f_st,m = 578
    eps_ud = bu.Float(0.025, MAT=True, desc='steel failure strain')

    eps_sy = tr.Property(bu.Float, depends_on='+MAT')
    @tr.cached_property
    def _get_eps_sy(self):
        return self.f_sy_scaled / self.E_s

    ipw_view = bu.View(
        bu.Item('factor'),
        bu.Item('E_s', latex=r'E_\mathrm{s} \mathrm{[N/mm^{2}]}'),
        bu.Item('f_sy', latex=r'f_\mathrm{sy} \mathrm{[N/mm^{2}]}'),
        bu.Item('f_st', latex=r'f_\mathrm{st} \mathrm{[N/mm^{2}]}'),
        bu.Item('eps_ud', latex=r'\varepsilon_\mathrm{ud} \mathrm{[-]}'),
        bu.Item('eps_sy', latex=r'\varepsilon_\mathrm{sy} \mathrm{[-]}', readonly=True),
    )

    def get_eps_plot_range(self):
        return np.linspace(- 1.1*self.eps_ud, 1.1*self.eps_ud, 300)

    f_sy_scaled = tr.Property
    def _get_f_sy_scaled(self):
        return self.factor * self.f_sy

    f_st_scaled = tr.Property
    def _get_f_st_scaled(self):
        return self.factor * self.f_st

    def get_sig(self, eps):
        return self.symb.get_sig(eps)

    def get_f_ult(self):
        return self.f_st

    def get_eps_ult(self):
        return self.eps_ud

class CarbonReinfMatModSymbExpr(bu.SymbExpr):
    """Piecewise linear concrete material law
    """
    eps = sp.Symbol('eps', real=True)

    f_t_scaled, E = sp.symbols('f_t_scaled, E', real=True, nonnegative=True)
    # post_peak_factor defines the steepness of post peak part (1 is equal to pre-peak part, 10 is 10 times steeper)
    post_peak_factor = 2.5
    sig = sp.Piecewise(
        (0, eps < 0),
        (E * eps, eps < f_t_scaled/E),
        (f_t_scaled - post_peak_factor * E * (eps - f_t_scaled / E), eps < (1 + 1. / post_peak_factor) * f_t_scaled / E),
        (0, True)
    )

    symb_model_params = ('E', 'f_t_scaled')

    symb_expressions = [
        ('sig', ('eps',)),
    ]


class CarbonReinfMatMod(ReinfMatMod, bu.InjectSymbExpr):

    name = 'Carbon'

    symb_class = CarbonReinfMatModSymbExpr

    E = bu.Float(200000, MAT=True, desc='E modulus of carbon')
    f_t = bu.Float(2000, MAT=True, desc='carbon breaking stress')

    eps_cr = tr.Property(bu.Float, depends_on='+MAT')
    @tr.cached_property
    def _get_eps_cr(self):
        return self.f_t / self.E

    ipw_view = bu.View(
        bu.Item('factor'),
        bu.Item('E', latex=r'E \mathrm{[N/mm^{2}]}'),
        bu.Item('f_t', latex=r'f_\mathrm{t} \mathrm{[N/mm^{2}]}'),
        bu.Item('eps_cr', latex=r'\varepsilon_\mathrm{cr} \mathrm{[-]}'),
    )

    def get_eps_plot_range(self):
        return np.linspace(- 0.1*self.eps_cr, 1.1*self.eps_cr,300)

    f_t_scaled = tr.Property
    def _get_f_t_scaled(self):
        return self.factor * self.f_t

    def get_sig(self, eps):
        return self.symb.get_sig(eps)

    def get_f_ult(self):
        return self.f_t

    def get_eps_ult(self):
        return self.eps_cr