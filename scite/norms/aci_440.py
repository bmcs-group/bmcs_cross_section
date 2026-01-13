import numpy as np

from bmcs_cross_section.norms.ec2 import EC2


class ACI440:
    """
    The American FRP reinforced concrete code
    """
    @staticmethod
    def get_beta_1(f_c):
        return 0.85 if f_c <= 28 else max((0.85 - 0.05 * (f_c - 28) / 7), 0.65)

    @staticmethod
    def get_rho_balanced(f_c, f_fu, E_f):
        """
        :param f_c [MPa]: compressive strength of concrete (typically specified compressive strength f'c = f_ck)
        :param f_fu [MPa]: tensile strength of FRP reinf.
        :param E_f [MPa]: e-modulus of FRP reinf.
        :return: Balanced FRP reinforcement ratio
        """
        eps_cu = ACI440.get_eps_cu()
        beta_1 = ACI440.get_beta_1(f_c)
        rho_fb = 0.85 * beta_1 * (f_c / f_fu) * (E_f * eps_cu / (E_f * eps_cu + f_fu))
        return rho_fb


    @staticmethod
    def get_M_n(A_f=50, f_fu=2500, E_f=158000, f_c=48, b=200, d=280):
        """
        :param f_c [MPa]: compressive strength of concrete (typically specified compressive strength f'c = f_ck)
        :param f_fu [MPa]: tensile strength of FRP reinf.
        :param E_f [MPa]: e-modulus of FRP reinf.
        :return: Balanced FRP reinforcement ratio
        """
        rho = A_f / (b * d)
        rho_balanced = ACI440.get_rho_balanced(f_c, f_fu, E_f)
        eps_cu = ACI440.get_eps_cu()
        beta_1 = ACI440.get_beta_1(f_c)
        if rho <= rho_balanced:
            eps_fu = f_fu / E_f
            c_b = (eps_cu / (eps_cu + eps_fu)) * d
            M_n = A_f * f_fu * (d - beta_1 * c_b / 2) / 1e6
        else:
            f_f = np.minimum(
                np.sqrt(((E_f * eps_cu) ** 2) / 4 + 0.85 * beta_1 * f_c * E_f * eps_cu / rho) - 0.5 * E_f * eps_cu,
                f_fu)
            a = A_f * f_f / (0.85 * f_c * b)
            M_n = A_f * f_f * (d - a / 2) / 1e6
        return M_n


    @staticmethod
    def get_psi_f(rho=0.005, f_fu=2500, E_f=158000, f_c=48):
        rho_balanced = ACI440.get_rho_balanced(f_c, f_fu, E_f)
        eps_cu = ACI440.get_eps_cu()
        beta_1 = ACI440.get_beta_1(f_c)
        if rho <= rho_balanced:
            return 1
        else:
            f_f = np.minimum(
                np.sqrt(((E_f * eps_cu) ** 2) / 4 + 0.85 * beta_1 * f_c * E_f * eps_cu / rho) - 0.5 * E_f * eps_cu,
                f_fu)
            return f_f / f_fu


    @staticmethod
    def get_psi_c(rho=0.005, A_f=50, f_fu=2500, E_f=158000, f_c=48, b=200, d=280):
        rho_balanced = ACI440.get_rho_balanced(f_c, f_fu, E_f)
        eps_cu = ACI440.get_eps_cu()
        beta_1 = ACI440.get_beta_1(f_c)
        if rho <= rho_balanced:
            eps_fu = f_fu / E_f
            c_b = (eps_cu / (eps_cu + eps_fu)) * d
        else:
            return 1

    @staticmethod
    def get_eps_cu():
        return 0.003

    @staticmethod
    def get_w(A_f=50, E_f=158000, M_a=1e6, f_c=48, h=300, b=200, d=280,
              l=3000, l_a=None, load_type='dist',
              f_ct=None, E_c=None
              ):
        """ Calculate deflections for a service moment M_a, see PDF page 66 in ACI-440 for an example
        with load combinations.
        all attributes in N and mm
        l_a: relevant only for 4pb which is the distance from support to load
        f_ct, E_c: are optional, if not provided ACI formulas are used
        """
        rho_f = A_f / (b * d)
        E_c = 4700 * np.sqrt(f_c) if E_c is None else E_c
        n_f = E_f / E_c
        k = np.sqrt(2 * rho_f * n_f + (rho_f * n_f) ** 2) - rho_f * n_f
        I_cr = (b * d ** 3 / 3) * k ** 3 + n_f * A_f * d ** 2 * (1 - k) ** 2

        I_g = b * h ** 3 / 12
        lambda_ = 1 # for normal (not light-weight) concrete accord. ACI 318 (Table 19.2.4.1(a))
        y_t = 0.5 * h
        f_ct = 0.62 * lambda_ * np.sqrt(f_c) if f_ct is None else f_ct
        M_cr = f_ct * I_g / y_t

        if M_a <= M_cr:
            I_e = I_g
        else:
            gamma = 1.72 - 0.72 * (M_cr / M_a)
            I_e = min(I_g, I_cr / (1 - gamma * (M_cr / M_a) ** 2 * (1 - I_cr / I_g)))

        if load_type == 'dist':
            w = 5 * M_a * l ** 2 / (48 * E_c * I_e)
        elif load_type == '3pb':
            w = M_a * l ** 2 / (12 * E_c * I_e)
        elif load_type == '4pb':
            w = M_a * (3 * l ** 2 - 4 * l_a ** 2) / (24 * E_c * I_e)
        else:
            raise ValueError('the provided load_type is not supported!')
        return w, (I_g, I_e, I_cr, M_cr)

