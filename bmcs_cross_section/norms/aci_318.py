import numpy as np

from bmcs_cross_section.norms.ec2 import EC2


class ACI318:
    """
    The American steel reinforced concrete code
    """
    @staticmethod
    def get_beta_1(f_c):
        return 0.85 if f_c <= 28 else max((0.85 - 0.05 * (f_c - 28) / 7), 0.65)

    @staticmethod
    def get_M_n(A_s=50, f_y=500, f_c=48, b=200, d=280):
        a = A_s * f_y / (0.85 * f_c * b)
        return A_s * f_y * (d - a / 2) / 1e6

    @staticmethod
    def get_w(A_s=50, E_s=158000, M_a=1e6, f_c=48, h=300, b=200, d=280,
              l=3000, l_a=None, load_type='dist',
              f_ct=None, E_c=None
              ):
        """ Calculate deflections for a service moment M_a, see PDF page 66 in ACI-440 for an example
        with load combinations.
        See last page in Bischoff2007 (I_cr) and ACI 318 deflection calculation for more details..
        all attributes in N and mm
        l_a: relevant only for 4pb which is the distance from support to load
        f_ct, E_c: are optional, if not provided ACI formulas are used
        """
        rho_f = A_s / (b * d)
        E_c = 4700 * np.sqrt(f_c) if E_c is None else E_c
        n_f = E_s / E_c
        k = np.sqrt(2 * rho_f * n_f + (rho_f * n_f) ** 2) - rho_f * n_f
        I_cr = (b * d ** 3 / 3) * k ** 3 + n_f * A_s * d ** 2 * (1 - k) ** 2

        I_g = b * h ** 3 / 12
        lambda_ = 1 # for normal (not light-weight) concrete accord. ACI 318 (Table 19.2.4.1(a))
        y_t = 0.5 * h
        f_ct = 0.62 * lambda_ * np.sqrt(f_c) if f_ct is None else f_ct
        M_cr = f_ct * I_g / y_t

        if M_a <= (2/3) * M_cr:
            I_e = I_g
        else:
            I_e = min(I_g, I_cr / (1 - ((2/3) * M_cr / M_a) ** 2 * (1 - I_cr / I_g)))

        if load_type == 'dist':
            w = 5 * M_a * l ** 2 / (48 * E_c * I_e)
        elif load_type == '3pb':
            w = M_a * l ** 2 / (12 * E_c * I_e)
        elif load_type == '4pb':
            w = M_a * (3 * l ** 2 - 4 * l_a ** 2) / (24 * E_c * I_e)
        else:
            raise ValueError('the provided load_type is not supported!')
        return w, (I_g, I_e, I_cr, M_cr)

