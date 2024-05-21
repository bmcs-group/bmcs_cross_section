import numpy as np

from bmcs_cross_section.norms.ec2 import EC2

class EC2CreepShrinkage:

    @staticmethod
    def _get_h_0(A_c, u):
        return 2 * A_c / u

    @staticmethod
    def _get_k_h(h_0):
        h_0_ = [100, 200, 300, 500, 800]
        k_h_ = [1, 0.85, 0.75, 0.7, 0.7]
        k_h = np.interp(h_0, h_0_, k_h_)
        return k_h

    @staticmethod
    def get_creep_coefficient(f_ck, A_c, u, t_0, t=999999999, T=20, RH=70, cement_type='N', log=False):
        """
        See Eurocode 2 Appendix B
        This function returns creep coefficient φ(t,t0) (or φ(∞,t0) in case t = ∞)
        Params:
        t: time in days, for φ(∞,t0) set t=999999999
        fck: concrete characteristic strength
        Ac: concrete cross-sectional area
        u: perimeter of the member in contact with the atmosphere
        t0: age of concrete at loading
        T = 20 °C: ambient temperature
        RH [%]: relative humidity of ambient environment
        cement_type: (e.g. 'N' for Class N)
        """
        f_cm = EC2.get_f_cm(f_ck)
        h_0 = EC2CreepShrinkage._get_h_0(A_c, u)
        k_h = EC2CreepShrinkage._get_k_h(h_0)

        alpha_1 = (35 / f_cm) ** 0.7
        alpha_2 = (35 / f_cm) ** 0.2
        alpha_3 = (35 / f_cm) ** 0.5

        if f_cm <= 35:
            beta_H = min(1.5 * (1 + (0.012 * RH) ** 18) * h_0 + 250, 1500)
            phi_RH = 1 + (1 - RH / 100) / (0.1 * h_0 ** (1 / 3))
        else:
            beta_H = min(1.5 * (1 + (0.012 * RH) ** 18) * h_0 + 250 * alpha_3, 1500 * alpha_3)
            phi_RH = (1 + (1 - RH / 100) / (0.1 * h_0 ** (1 / 3)) * alpha_1) * alpha_2

        if cement_type == 'N':
            alpha = 0
        elif cement_type == 'R':
            alpha = 1
        elif cement_type == 'S':
            alpha = -1
        else:
            raise ValueError('"cement_type" parameter is not valid!')

        # Taking type of cement into account by modifying t_0
        T_delta_t = T
        delta_t = t_0
        t_0_T = np.exp(-(4000 / (273 + T_delta_t) - 13.65)) * delta_t
        t_0 = max(t_0_T * (9 / (2 + t_0_T ** 1.2) + 1) ** alpha, 0.5)

        beta_f_cm = 16.8 / np.sqrt(f_cm)
        beta_t_0 = 1 / (0.1 + t_0 ** 0.2)
        beta_c_t_t_0 = ((t - t_0) / (beta_H + t - t_0)) ** 0.3

        phi_0 = phi_RH * beta_f_cm * beta_t_0

        phi_t_t_0 = phi_0 * beta_c_t_t_0

        if log:
            print('beta_H =', beta_H)
            print('phi_RH =', phi_RH)
            print('h_0 =', h_0)
            print('k_h =', k_h)
            print('t_0 =', t_0)
            print('beta_f_cm =', beta_f_cm)
            print('beta_t_0 =', beta_t_0)
            print('beta_c_t_t_0 =', beta_c_t_t_0)
            print('phi_0 =', phi_0)
            print('-> phi_t_t_0 =', phi_t_t_0)
        return phi_t_t_0

    @staticmethod
    def get_eps_cs_shrinkage(f_ck, A_c, u, t=999999999, t_s=3, RH=70, cement_type='N', log=False):
        """
        See Eurocode 2 (3.1.4) and Appendix B
        This function returns shrinkage strain eps_cs
        Params:
        t: time in days, for φ(∞,t0) set t=999999999
        fck: concrete characteristic strength
        Ac: concrete cross-sectional area
        u: perimeter of the member in contact with the atmosphere
        t0: age of concrete at loading
        T = 20 °C: ambient temperature
        RH [%]: relative humidity of ambient environment
        cement_type: (e.g. 'N' for Class N)
        ts = (3 days): age of concrete at end of curing
        """

        f_cm = f_ck + 8
        h_0 = EC2CreepShrinkage._get_h_0(A_c, u)

        if cement_type == 'N':
            alpha_ds1 = 4
            alpha_ds2 = 0.12
        elif cement_type == 'S':
            alpha_ds1 = 3
            alpha_ds2 = 0.13
        elif cement_type == 'R':
            alpha_ds1 = 6
            alpha_ds2 = 0.11
        else:
            raise ValueError('"cement_type" parameter is not valid!')

        RH_0 = 100
        beta_RH = 1.55 * (1 - (RH / RH_0) ** 3)

        f_cmo = 10
        beta_ds_t_t_s = (t - t_s) / ((t - t_s) + 0.04 * h_0 ** (3 / 2))
        eps_cd0 = 0.85 * ((220 + 110 * alpha_ds1) * np.exp(-alpha_ds2 * f_cm / f_cmo)) * 1e-6 * beta_RH
        k_h = EC2CreepShrinkage._get_k_h(h_0)
        eps_cd = beta_ds_t_t_s * k_h * eps_cd0

        eps_ca_inf = 2.5 * (f_ck - 10) * 1e-6
        beta_as_t = 1 - np.exp(- 0.2 * t ** 0.5)
        eps_ca = beta_as_t * eps_ca_inf

        eps_cs = eps_cd + eps_ca
        if log:
            print('beta_RH =', beta_RH)
            print('beta_ds_t_t_s =', beta_ds_t_t_s)
            print('eps_cd0 =', eps_cd0)
            print('eps_cd =', eps_cd)
            print('beta_as_t =', beta_as_t)
            print('eps_ca =', eps_ca)
            print('-> eps_cs =', eps_cs)
        return eps_cs


if __name__ == '__main__':
    f_ck = 30
    A_c = 300 * 1000
    u = 2600
    t_0 = 10
    t = 9999999999
    RH = 70
    T = 20
    cement_type = 'N'
    # The following must return phi_inf_t_0 = 2.3266
    phi_inf_t_0 = EC2CreepShrinkage.get_creep_coefficient(f_ck, A_c, u, t_0, t=t, T=T, RH=RH, cement_type=cement_type,
                                                          log=True)

    # The following must return eps_cs = 0.0003466
    t_s = 3
    eps_cs = EC2CreepShrinkage.get_eps_cs_shrinkage(f_ck, A_c, u, t=t, t_s=t_s, RH=RH, cement_type=cement_type, log=True)
