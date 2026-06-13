import numpy as np
import traits.api as tr


class AnaFRPBending(tr.HasStrictTraits):
    b = tr.Float(400.)
    d = tr.Float(180.)
    f_fu = tr.Float(2500.)
    E_f = tr.Float(200000.)
    A_f = tr.Float(250.)
    f_cm = tr.Float(50.)

    debug = tr.Bool(False)

    mc = tr.Property()

    def _set_mc(self, mc):
        reinf_layer = list(mc.cross_section_layout.items.values())[0]
        z = reinf_layer.z
        self.A_f = reinf_layer.A
        self.f_fu = reinf_layer.matmod_.f_t
        self.E_f = reinf_layer.matmod_.E
        self.b = mc.cross_section_shape_.B
        self.d = mc.cross_section_shape_.H - z
        self.f_cm = mc.cs_design.matrix_.f_cm

    rho_f = tr.Property()

    def _get_rho_f(self):
        return self.A_f / (self.b * self.d)

    m1 = tr.Property()

    def _get_m1(self):
        return np.sqrt(self.E_f) * self.b * self.d * self.sigma_cy

    m2 = tr.Property()

    def _get_m2(self):
        E_f = self.E_f
        A_f = self.A_f
        eps_cy = self.eps_cy
        return E_f * (
                    np.sqrt(A_f * eps_cy * (A_f * E_f * eps_cy + 2 * self.m1 / np.sqrt(E_f))) + A_f * eps_cy * np.sqrt(
                E_f))

    m0 = tr.Property()

    def _get_m0(self):
        delta_eps = self.eps_cu - self.eps_cy
        return delta_eps * self.sigma_cu + delta_eps * self.sigma_cy + self.sigma_cy * self.eps_cy

    eps_cy = tr.Property()

    def _get_eps_cy(self):
        return 0.001 * np.min((2.8, 0.7 * self.f_cm ** 0.31))

    eps_cu = tr.Property()

    def _get_eps_cu(self):
        f_cm = self.f_cm
        if f_cm <= 58:
            return 0.001 * 3.5
        elif f_cm <= 98:
            return 0.001 * (2.8 + 27 * ((98 - f_cm) / 100) ** 4)
        else:
            return 0.001 * 2.8

    sigma_cy = tr.Property()

    def _get_sigma_cy(self):
        return 1e-3 * self.f_cm * (1437.6204 - 2.7858 * self.f_cm)

    sigma_cu = tr.Property()

    def _get_sigma_cu(self):
        return 1e-3 * self.f_cm * (8.2275 * self.f_cm + 95.5314)

    sigma_f = tr.Property()

    def _get_sigma_f(self):
        eps_cy = self.eps_cy
        eps_cu = self.eps_cu
        E_f = self.E_f
        rho_f = self.rho_f
        num = E_f * (E_f * rho_f * eps_cu ** 2 + 2 * self.sigma_cu * (eps_cu - eps_cy) + 2 * self.sigma_cy * eps_cu)
        return np.min((self.f_fu, 0.5 * (np.sqrt(num / rho_f) - E_f * eps_cu)))

    rho_f_cy = tr.Property()
    def _get_rho_f_cy(self):
        return (self.E_f * self.sigma_cy * self.eps_cy) / (2. * self.f_fu * (self.E_f * self.eps_cy + self.f_fu))

    def _get_Mu_cy(self):
        m1 = self.m1
        m2 = self.m2
        return (self.A_f * self.d * self.f_fu * (3 * m1 + 2 * m2)) / (3 * (m1 + m2))

    def _get_Mu_cu(self):
        eps_cy = self.eps_cy
        eps_cu = self.eps_cu
        sigma_f = self.sigma_f
        sigma_cu = self.sigma_cu
        sigma_cy = self.sigma_cy
        delta_eps = eps_cu - eps_cy
        d = self.d
        E_f = self.E_f
        A_f = self.A_f
        m0 = self.m0
        num = 3 * m0 * (E_f * eps_cu + sigma_f) \
              - E_f * (delta_eps ** 2 * (2 * sigma_cy + sigma_cu) + sigma_cy * eps_cy * (
                      3 * eps_cu - 2 * eps_cy))
        den = 3 * m0 * (E_f * eps_cu + sigma_f)
        return (A_f * d * sigma_f * num) / den

    M_u = tr.Property()
    def _get_M_u(self):
        if self.rho_f <= self.rho_f_cy:
            print('rho_f <= rho_f_cy') if self.debug else None
            return self._get_Mu_cy() / 1e6
        else:
            print('rho_f > rho_f_cy') if self.debug else None
            return self._get_Mu_cu() / 1e6

    rho_fb = tr.Property()
    def _get_rho_fb(self):
        """Calculates the balanced reinforcement ratio of a beam at failure (rho_fb).
        """
        eps_cu = self.eps_cu
        tmp1 = self.E_f * (self.sigma_cu * eps_cu - self.sigma_cu * self.eps_cy + self.sigma_cy * eps_cu)
        tmp2 = 2. * self.f_fu * (self.E_f * eps_cu + self.f_fu)
        return tmp1 / tmp2

    psi_c = tr.Property()
    def _get_psi_c(self):
        f_cm = self.f_cm
        rho_f = self.rho_f
        f_fu = self.f_fu
        E_f = self.E_f
        rho_f_cy = self.rho_f_cy
        eps_cy = self.eps_cy
        sigma_cy = self.sigma_cy
        if rho_f < rho_f_cy:
            sig_c_max = f_fu * (rho_f + np.sqrt((rho_f * (rho_f * E_f * eps_cy + 2 * sigma_cy)) / (E_f * eps_cy)))
            psi_c = np.min((1., sig_c_max / self.sigma_cy))
            # Note: dividing by self.sigma_cy instead of f_cm results in less utilization than reality
            #  for sig_c_max values near f_cm, but insures the full utilization not reached until rho_f_cy
        else:
            psi_c = 1.
        return psi_c

    psi_f = tr.Property()
    def _get_psi_f(self):
        if self.rho_f > self.rho_fb:
            psi_f = self.sigma_f / self.f_fu
        else:
            psi_f = 1.
        return psi_f

    kappa_u = tr.Property()

    def _get_kappa_u(self):
        f_fu = self.f_fu
        E_f = self.E_f
        A_f = self.A_f
        sigma_cy = self.sigma_cy
        b = self.b
        d = self.d
        eps_cy = self.eps_cy

        if self.rho_f < self.rho_f_cy:
            kappa_u_f_cy = (f_fu / E_f + f_fu * (
                    np.sqrt(A_f) * np.sqrt(eps_cy) * np.sqrt(A_f * E_f * eps_cy + 2 * sigma_cy * b * d) + A_f * np.sqrt(
                E_f) * eps_cy) / (np.sqrt(E_f) * sigma_cy * b * d)) / d
            return kappa_u_f_cy
        elif self.rho_f < self.rho_fb:
            pass
        elif self.rho_f >= self.rho_fb:
            kappa_u_fb = (self.eps_cu + self.sigma_f / E_f) / d
            return kappa_u_fb
