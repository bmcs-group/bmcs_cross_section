import numpy as np

########## Ultimate moment capacity data start ##########

mu_Eds_values = np.linspace(0.01, 0.4, 40)
sig_sd = [456.5, 456.5, 456.5, 456.5, 456.5, 456.5, 456.5, 456.5, 456.5, 454.9, 452.4, 450.4, 448.6, 447.1, 445.9, 444.7, 443.7, 442.8, 442, 441.3, 440.6, 440.1, 439.5, 439, 438.5, 438.1, 437.7, 437.3, 437, 436.7, 436.4, 436.1, 435.8, 435.5, 435.3, 435, 434.8]
w1_values = [0.0101
    , 0.0203
    , 0.0306
    , 0.0410
    , 0.0515
    , 0.0621
    , 0.0728
    , 0.0836
    , 0.0946
    , 0.1058
    , 0.1170
    , 0.1285
    , 0.1401
    , 0.1519
    , 0.1638
    , 0.1759
    , 0.1882
    , 0.2007
    , 0.2134
    , 0.2263
    , 0.2395
    , 0.2529
    , 0.2665
    , 0.2804
    , 0.2946
    , 0.3091
    , 0.3239
    , 0.3391
    , 0.3546
    , 0.3706
    , 0.3869
    , 0.4038
    , 0.4211
    , 0.4391
    , 0.4576
    , 0.4768
    , 0.4968
    , 0.5177
    , 0.5396
    , 0.5627]
xi_values = [0.030
    , 0.044
    , 0.055
    , 0.066
    , 0.076
    , 0.086
    , 0.097
    , 0.107
    , 0.118
    , 0.131
    , 0.145
    , 0.159
    , 0.173
    , 0.188
    , 0.202
    , 0.217
    , 0.233
    , 0.248
    , 0.264
    , 0.280
    , 0.296
    , 0.312
    , 0.329
    , 0.346
    , 0.364
    , 0.382
    , 0.400
    , 0.419
    , 0.438
    , 0.458
    , 0.478
    , 0.499
    , 0.520
    , 0.542
    , 0.565
    , 0.589
    , 0.614
    , 0.640
    , 0.667
    , 0.695]
zeta_values = [0.990
    , 0.985
    , 0.980
    , 0.976
    , 0.971
    , 0.967
    , 0.962
    , 0.957
    , 0.951
    , 0.946
    , 0.940
    , 0.934
    , 0.928
    , 0.922
    , 0.916
    , 0.910
    , 0.903
    , 0.897
    , 0.890
    , 0.884
    , 0.877
    , 0.870
    , 0.863
    , 0.856
    , 0.849
    , 0.841
    , 0.834
    , 0.826
    , 0.818
    , 0.810
    , 0.801
    , 0.793
    , 0.784
    , 0.774
    , 0.765
    , 0.755
    , 0.745
    , 0.734
    , 0.723
    , 0.711]
eps_c2_values = [-0.77
    , -1.15
    , -1.46
    , -1.76
    , -2.06
    , -2.37
    , -2.68
    , -3.01
    , -3.35
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5
    , -3.5]
eps_s1_values = [25
    , 25
    , 25
    , 25
    , 25
    , 25
    , 25
    , 25
    , 25
    , 23.29
    , 20.71
    , 18.55
    , 16.73
    , 15.16
    , 13.8
    , 12.61
    , 11.56
    , 10.62
    , 9.78
    , 9.02
    , 8.33
    , 7.71
    , 7.13
    , 6.61
    , 6.12
    , 5.67
    , 5.25
    , 4.86
    , 4.49
    , 4.15
    , 3.82
    , 3.52
    , 3.23
    , 2.95
    , 2.69
    , 2.44
    , 2.2
    , 1.97
    , 1.75
    , 1.54]


########## Ultimate moment capacity data end ##########

class EC2:

    # 1. Concrete strength values according to EC2 - Table 3.1
    # Units: all strength and E-modulus values for input and output are in [N/mm^2]

    @staticmethod
    def get_f_cm(f_ck):
        return f_ck + 8

    @staticmethod
    def get_f_ck_from_f_cm(f_cm):
        return f_cm - 8

    @staticmethod
    def get_f_ctm(f_ck):
        f_cm = f_ck + 8
        return 1 * np.where(f_ck <= 50, 0.3 * f_ck ** (2 / 3), 2.12 * np.log(1 + (f_cm / 10)))

    @staticmethod
    def get_f_ctm_fl(f_ck, h):
        # where h is total cross section height in mm
        f_ctm = EC2.get_f_ctm(f_ck)
        return max((1.6 - h / 1000) * f_ctm, f_ctm)

    @staticmethod
    def get_f_ctk_0_05(f_ck):
        f_ctm = EC2.get_f_ctm(f_ck)
        return 0.7 * f_ctm

    @staticmethod
    def get_f_ctk_0_95(f_ck):
        f_ctm = EC2.get_f_ctm(f_ck)
        return 1.3 * f_ctm

    @staticmethod
    def get_f_ck_from_f_cd(f_cd, factor=0.85 / 1.5):
        return f_cd * 1 / factor

    @staticmethod
    def get_f_cd(f_ck, factor=0.85 / 1.5):
        return f_ck * factor

    @staticmethod
    def get_E_cm(f_ck):
        f_cm = EC2.get_f_cm(f_ck)
        return 22000 * (f_cm / 10) ** 0.3

    @staticmethod
    def get_eps_c1(f_ck):
        f_cm = EC2.get_f_cm(f_ck)
        eps_c1 = 0.7 * f_cm ** 0.31
        eps_c1 = np.where(eps_c1 > 2.8, 2.8, eps_c1)
        return 0.001 * eps_c1

    @staticmethod
    def get_eps_cu1(f_ck):
        f_cm = EC2.get_f_cm(f_ck)
        return 0.001 * np.where(f_ck <= 50, 3.5, 2.8 + 27 * ((98 - f_cm) / 100) ** 4)

    @staticmethod
    def get_eps_c2(f_ck):
        # np.sign(x) * (np.abs(x)) ** 0.53 is a work around for complex numbers warning because of (** 0.53)
        return 0.001 * np.where(f_ck <= 50, 2, 2 + 0.085 * np.sign(f_ck - 50) * (np.abs(f_ck - 50)) ** 0.53)

    @staticmethod
    def get_eps_cu2(f_ck):
        return 0.001 * np.where(f_ck <= 50, 3.5, 2.6 + 35 * ((90 - f_ck) / 100) ** 4)

    @staticmethod
    def get_eps_c3(f_ck):
        return 0.001 * np.where(f_ck <= 50, 1.75, 1.75 + 0.55 * ((f_ck - 50) / 40))

    @staticmethod
    def get_eps_cu3(f_ck):
        return 0.001 * np.where(f_ck <= 50, 3.5, 2.6 + 35 * ((90 - f_ck) / 100) ** 4)

    @staticmethod
    def get_n(f_ck):
        # n is the exponent used in eq. 3.17 and is to be taken from (EC2 - Table 3.1)
        return 1 * np.where(f_ck <= 50, 2, 1.4 + 23.4 * ((90 - f_ck) / 100) ** 4)

    @staticmethod
    def get_mu_Eds(rho, f_ck, f_yk):
        f_yd = f_yk / 1.15
        f_cd = 0.85 * f_ck / 1.5
        w1 = rho * f_yd / f_cd
        return np.interp(w1, w1_values, mu_Eds_values)

    @staticmethod
    def get_mu_Eds_FRP(rho, f_ck, f_uk):
        f_ud = 0.85 * 0.9 * f_uk / 1.3
        f_cd = 0.85 * f_ck / 1.5
        w1 = rho * f_ud / f_cd
        return np.interp(w1, w1_values, mu_Eds_values)

    @staticmethod
    def get_M_Ed(b, d, As, f_ck, f_yk):
        rho = As / (b * d)
        f_yd = f_yk / 1.15
        f_cd = 0.85 * f_ck / 1.5
        w1 = rho * f_yd / f_cd
        mu_Eds = EC2.get_mu_Eds(rho, f_ck, f_yk)
        xi = np.interp(w1, w1_values, xi_values)
        M_Ed = mu_Eds * b * d ** 2 * f_cd

        compression_reinf_needed = False
        if f_ck <= 50:
            if xi > 0.45:
                compression_reinf_needed = True
        else:
            if xi > 0.35:
                compression_reinf_needed = True

        return M_Ed, compression_reinf_needed

    # @staticmethod
    # def get_w_elg(rho, L, f_ck=30, b=1000, h=300, d=270, E_r=200000, sls_uls_ratio=0.51, reinf='steel', creep=True,
    #               shrinkage=True):
    #     def get_k_xI(rho_s1, rho_s2, d, d_2, h, E_s, E_cm_eff):
    #         # rho_s2: is compression reinf. ratio
    #         alpha_e = E_s / E_cm_eff
    #         # TODO: check B_I
    #         B_I = (alpha_e - 1) * (rho_s1 + rho_s2)
    #         A_I = (B_I / h) * (d + d_2)
    #         return (0.5 + A_I) / (1 + B_I)
    #
    #     def get_k_I(rho_s1, rho_s2, d, d_2, h, E_s, E_cm_eff):
    #         alpha_e = E_s / E_cm_eff
    #         k_xI = get_k_xI(rho_s1, rho_s2, d, d_2, h, E_s, E_cm_eff)
    #         tmp1 = 12 * (0.5 - k_xI) ** 2
    #         tmp2 = 12 * (alpha_e - 1) * rho_s1 * (d / h - k_xI) ** 2
    #         tmp3 = 12 * (alpha_e - 1) * rho_s1 * (rho_s2 / rho_s1) * (k_xI - d_2 / h) ** 2
    #         return 1 + tmp1 + tmp2 + tmp3
    #
    #     def get_k_xII(rho_s1, rho_s2, d, d_2, E_s, E_cm_eff):
    #         # rho_s2: is compression reinf. ratio
    #         # d_2: is the distance from top to compression reinf. (set to zero when no comp. reinf. available)
    #         alpha_e = E_s / E_cm_eff
    #         A_II = alpha_e * (rho_s1 + rho_s2)
    #         return - A_II + (A_II ** 2 + 2 * alpha_e * (rho_s1 + rho_s2 * d_2 / d)) ** 0.5
    #
    #     def get_k_II(rho_s1, rho_s2, d, d_2, E_s, E_cm_eff):
    #         alpha_e = E_s / E_cm_eff
    #         k_xII = get_k_xII(rho_s1, rho_s2, d, d_2, E_s, E_cm_eff)
    #         tmp1 = 12 * alpha_e * rho_s1 * (1 - k_xII) ** 2
    #         tmp2 = 12 * alpha_e * rho_s1 * (rho_s2 / rho_s1) * (k_xII - d_2 / d) ** 2
    #         return 4 * k_xII ** 3 + tmp1 + tmp2
    #
    #     eta = sls_uls_ratio
    #
    #     f_ctm = EC2.get_f_ctm(f_ck)
    #     f_cd = EC2.get_f_cd(f_ck)
    #     A_c = b * h
    #
    #     f_yk = 500
    #     if reinf == 'steel':
    #         mu_Ed = EC2.get_mu_Eds(rho, f_ck, f_yk)
    #     else:
    #         f_uk = 2000 * 0.85
    #         mu_Ed = EC2.get_mu_Eds_FRP(rho, f_ck, f_uk)
    #     E_cm = EC2.get_E_cm(f_ck)
    #     RH = 70
    #
    #     g_k = 0.36
    #     delta_g_k = 0.24
    #     q_k = 0.4
    #     psi_2 = 0.3
    #     u = 2 * b + 2 * h
    #     phi_inf_t_0 = EC2CreepShrinkage.get_creep_coefficient(f_ck, A_c, u, 10, RH=RH)
    #     phi_inf_t_1 = EC2CreepShrinkage.get_creep_coefficient(f_ck, A_c, u, 60, RH=RH)
    #     phi_inf_t_2 = EC2CreepShrinkage.get_creep_coefficient(f_ck, A_c, u, 365, RH=RH)
    #     phi_eq = (phi_inf_t_0 * g_k + phi_inf_t_1 * delta_g_k + phi_inf_t_2 * psi_2 * q_k) / (
    #                 g_k + delta_g_k + psi_2 * q_k)
    #
    #     if creep:
    #         E_c_eff = E_cm / (1 + phi_eq)
    #     else:
    #         E_c_eff = E_cm
    #     #     print(E_cm)
    #     #     print(E_c_eff)
    #     #     omega_eff = mu_Ed * f_cd / (eps_f * z * E_c_eff / d)
    #     #     print('omega_eff = ', omega_eff)
    #
    #     A_f = rho * b * d
    #     E_f = E_r
    #     omega_eff = E_f * A_f / (E_c_eff * A_c)
    #     #     print('omega_eff = ', omega_eff)
    #
    #     eps_cs = EC2CreepShrinkage.get_eps_cs_shrinkage(f_ck, A_c, u, RH=RH)
    #
    #     d_2 = 0
    #     k_xI = get_k_xI(rho, 0, d, d_2, h, E_f, E_c_eff)
    #     k_I = get_k_I(rho, 0, d, d_2, h, E_f, E_c_eff)
    #     k_II = get_k_II(rho, 0, d, d_2, E_f, E_c_eff)
    #
    #     zeta = 1 - ((((h / d) ** 2) * (f_ctm / (6 * E_c_eff))) / (
    #             (eta * mu_Ed * f_cd / E_c_eff) + eps_cs * omega_eff * (1 - k_xI * h / d))) ** 2
    #     xi_sls = omega_eff * ((1 + 2 / omega_eff) ** 0.5 - 1)
    #
    #     w_last = L * (
    #             (5 / 4) * (eta * mu_Ed * f_cd / E_c_eff) * (L / d) * (zeta / k_II + (1 - zeta) / (k_I * (h / d) ** 3)))
    #     w_schwinden = L * ((5 / 4) * eps_cs * omega_eff * (L / d) * (
    #             zeta * (1 - xi_sls) / k_II + (1 - zeta) * (1 - k_xI * h / d) / (k_I * (h / d) ** 3)))
    #
    #     if shrinkage:
    #         return w_last
    #     else:
    #         return w_last + w_schwinden


if __name__ == '__main__':
    print(EC2.get_n(100))
