import bmcs_utils.api as bu
import sympy as sp
import numpy as np
import traits.api as tr
from .ec2 import EC2
from .concrete_matmod import ConcreteMatMod

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
            return EC2.get_f_ctm(self.f_ck) / self.E_ct

    _eps_tu = None
    eps_tu = tr.Property(desc='Ultimate concrete tensile strain', MAT=True)
    def _set_eps_tu(self, value):
        self._eps_tu = value
    def _get_eps_tu(self):
        if self._eps_tu is not None:
            return self._eps_tu
        else:
            return self.eps_cr

    _E_cc = None
    E_cc = tr.Property(desc='E modulus of concrete on compression', MAT=True)
    def _set_E_cc(self, value):
        self._E_cc = value
    def _get_E_cc(self):
        if self._E_cc is not None:
            return self._E_cc
        else:
            return EC2.get_E_cm(self.f_ck)

    _E_ct = None
    E_ct = tr.Property(desc='E modulus of concrete on tension', MAT=True)
    def _set_E_ct(self, value):
        self._E_ct = value
    def _get_E_ct(self):
        if self._E_ct is not None:
            return self._E_ct
        else:
            return EC2.get_E_cm(self.f_ck)


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
