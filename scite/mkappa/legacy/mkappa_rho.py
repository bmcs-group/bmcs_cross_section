import numpy as np
from matplotlib import pyplot as plt
from matplotlib.ticker import PercentFormatter

from .mkappa import MKappa
from ..norms.ec2 import EC2


class MKappaRho(MKappa):
    """Dimensionless evaluation of moment-curvature relation
    
    Here are the methods originally included in MKappa. They 
    represent postprocessing with already solved eps_bot_t values.
    Moreover, they are related to reinforcement ratio which are 
    more design specific. Further classification needs to be conducted next. 
    """

    def get_bd(self, upper_reinforcement=False):
        if self.cross_section_shape != 'rectangle':
            return self.cross_section_shape_.get_cs_area()

        z = self.cross_section_layout.items[0].z
        h = self.cross_section_shape_.H
        b = self.cross_section_shape_.B
        if upper_reinforcement:
            d = z
        else:
            d = h - z
        return b * d

    def _get_stresses_at_maxium_moment(self):
        kappa_by_M_max = self.kappa_t[np.argmax(self.M_t)]
        idx = self.get_idx_matching_kappa_value(kappa_by_M_max)
        reinf_max_stress = self.N_s_tj[idx, :] / self.A_j
        sig_tm = self.sig_tm[idx, :]
        concr_max_stress_t = np.max(sig_tm[sig_tm > 0]) if sig_tm[sig_tm > 0].size != 0 else 0
        concr_max_stress_c = np.min(sig_tm[sig_tm <= 0]) if sig_tm[sig_tm <= 0].size != 0 else 0
        return reinf_max_stress, concr_max_stress_c, concr_max_stress_t

    def _get_strains_at_maxium_moment(self):
        kappa_by_M_max = self.kappa_t[np.argmax(self.M_t)]
        idx = self.get_idx_matching_kappa_value(kappa_by_M_max)
        reinf_max_strain = []
        # get it for all reinf layers
        for reinf_item in self.cross_section_layout.items:
            z = reinf_item.z
            reinf_max_strain.append(np.interp(z, self.z_m, self.eps_tm[idx, :]))
        concr_max_strain_t = np.max(self.eps_tm[idx, :])
        concr_max_strain_c = np.min(self.eps_tm[idx, :])
        return np.array(reinf_max_strain), concr_max_strain_c, concr_max_strain_t

    def get_M_n_ACI(self):
        """
        According to ACI 440.1R-15

        RC - concrete must specify mean strength

        TODO - seems to be specific plotting function which does
        not belong into the core module of the package
        """
        matmod = self.cross_section_layout.items[0].matmod
        reinf_layers_num = len(self.cross_section_layout.items)
        if matmod != 'carbon' or reinf_layers_num > 1:
            print('This approach is valid only for FRP reinf. with 1 reinf. layer!')
            return
        ##### CHECK - only possible in SIM mode
        f_cm = self.matrix.compression_.f_c
        f_fu = self.cross_section_layout.items[0].matmod_.f_t
        E_f = self.cross_section_layout.items[0].matmod_.E
        A_f = self.cross_section_layout.items[0].A
        z = self.cross_section_layout.items[0].z
        d = self.cross_section_shape_.H - z
        b = self.cross_section_shape_.B
        rho = A_f / (b * d)

        # Balanced reinf ratio:
        eps_cu = EC2.get_eps_cu1(f_cm - 8)
        beta_1 = 0.85 if f_cm <= 28 else max((0.85 - 0.05 * (f_cm - 28) / 7), 0.65)
        rho_fb = 0.85 * beta_1 * (f_cm / f_fu) * (E_f * eps_cu / (E_f * eps_cu + f_fu))

        # Get_M_n for rho < rho_fb
        if rho < rho_fb:
            eps_fu = f_fu / E_f
            c_b = (eps_cu / (eps_cu + eps_fu)) * d
            M_n = A_f * f_fu * (d - beta_1 * c_b / 2) / 1e6
        else:
            rho_f = A_f / (b * d)
            f_f = np.minimum(
                np.sqrt(((E_f * eps_cu) ** 2) / 4 + 0.85 * beta_1 * f_cm * E_f * eps_cu / rho_f) - 0.5 * E_f * eps_cu,
                f_fu)
            a = A_f * f_f / (0.85 * f_cm * b)
            M_n = A_f * f_f * (d - a / 2) / 1e6
        return M_n

    def plot_M_rho_to_M_rho_for_other_mc(self, mc, rho_list=None, ax=None, n_rho=50, mc_reinf_layers_rho_factors=[1]):
        rho_list, M_max = self.plot_M_rho_and_util_factors(type='stress',
                                                           rho_list=rho_list,
                                                           n_rho=n_rho,
                                                           reinf_layers_rho_factors=mc_reinf_layers_rho_factors,
                                                           return_rho_list_M_max=True)
        rho_list, mc_M_max = mc.plot_M_rho_and_util_factors(type='stress',
                                                              rho_list=rho_list,
                                                              n_rho=n_rho,
                                                              reinf_layers_rho_factors=mc_reinf_layers_rho_factors,
                                                              return_rho_list_M_max=True)
        fig = None
        if ax is None:
            fig, ax = plt.subplots()
            fig.set_size_inches(5.5, 3.4)

        M_max_ratio = np.array(mc_M_max) / np.array(M_max)
        ratio_max = np.max(M_max_ratio)
        ax.axhline(y=ratio_max, color='r')
        ax.annotate(r'max= ' + str(ratio_max), xy=(0, 1.04 * ratio_max), color='r')

        ax.plot(rho_list, M_max_ratio, c='black')
        ax.set_ylabel(r'$M_\mathrm{max2}/M_\mathrm{max1}$')
        ax.set_xlabel(r'Reinforcement ratio $\rho$')
        ax.set_ylim(ymin=0)
        ax.set_xlim(xmin=0)
        ax.grid(color='#e6e6e6', linewidth=0.7)

        if fig is not None:
            return fig, ax

    def plot_M_rho_and_util_factors(self, type='stress', rho_list=None, axes=None, n_rho=50,
                                    reinf_layers_rho_factors=[1], return_rho_list_M_max=False):
        """
            :param reinf_layers_rho_factors: for two reinf layers setting this to [0.5, 0.5] will assign
            rho value of 0.5 * rho to each reinf layer
            """
        if rho_list is None:
            n_1 = int(0.35 * n_rho)
            n_2 = int(0.25 * n_rho)
            n_3 = n_rho - n_1 - n_2
            rho_list = np.concatenate((np.linspace(0.0002, 0.004, n_1, endpoint=False),
                                       np.linspace(0.004, 0.006, n_2, endpoint=False),
                                       np.linspace(0.006, 0.025, n_3)))
            print('Non regular rho_list was created (denser up to rho = 0.4%).')
        M_max = []
        reinf_st = []
        concrete_st_c = []

        for rho in rho_list:
            for i, factor in enumerate(reinf_layers_rho_factors):
                self.cross_section_layout.items[i].A = factor * rho * self.get_bd()
            self.state_changed = True
            M = self.M_t / self.M_scale
            M_max.append(np.max(M))

            if type == 'stress':
                reinf_max_st, concr_max_st_c, _ = self._get_stresses_at_maxium_moment()
            elif type == 'strain':
                reinf_max_st, concr_max_st_c, _ = self._get_strains_at_maxium_moment()
            reinf_st.append(reinf_max_st)
            concrete_st_c.append(concr_max_st_c)

        if return_rho_list_M_max:
            return rho_list, M_max

        if axes is None:
            fig, (ax_M, ax_util_conc) = plt.subplots(2, 1)
            fig.set_size_inches(5.5, 6.8)
        else:
            ax_M, ax_util_conc = axes
        ax_M.plot(rho_list, M_max, c='black')
        last_M_max = M_max[-1]

        # Normalize stresses as an approximation to get the value (sigma_c,max/f_cm)
        if type == 'stress':
            concrete_st_c = -np.array(concrete_st_c)
            max_c = np.max(np.abs(concrete_st_c))
            concrete_st_c = concrete_st_c / max_c
            print('Conc. normalized by max_c = ', max_c)
        elif type == 'strain':
            concrete_st_c = np.abs(concrete_st_c / self.matrix.compression_.eps_cu)
            concrete_st_c = np.where(concrete_st_c > 1, 1, concrete_st_c)

        reinf_st_lr = np.array(reinf_st).T  # where l is index for reinf layer and r for rho

        c1 = 'black'
        ax_util_conc.plot(rho_list, concrete_st_c, '--', color=c1,
                       label='Concrete utilization ratio $\psi_c$')  # = \sigma_{cc, max}/f_{\mathrm{cm}}

        c2 = 'red'
        ax_util_reinf = ax_util_conc.twinx()
        for i, reinf_st in enumerate(reinf_st_lr):
            reinf_item = self.cross_section_layout.items[i]
            matmod = reinf_item.matmod
            z = reinf_item.z
            if type == 'stress':
                f_ult = reinf_item.matmod_.get_f_ult() # where f_ult is f_t (carbon) or f_st (steel)
                reinf_st = reinf_st / f_ult
            elif type == 'strain':
                eps_ult = reinf_item.matmod_.get_eps_ult()
                reinf_st = reinf_st / eps_ult

            if matmod == 'carbon' and i < 2:
                color = '#00569eff'
            elif matmod == 'steel' and i < 2:
                color = c2
            else:
                color = np.random.rand(3, )
            ax_util_reinf.plot(rho_list, reinf_st, '--', color=color,
                            label='Reinf. util. ratio $\psi_r$, ' + matmod + ', z=' + str(z))

        # Formatting plots:
        ax_M.axhline(y=last_M_max, color='r')
        ax_M.annotate(r'$M_{\mathrm{max, ' + str(rho_list[-1]) + '}} = ' + str(round(last_M_max, 2)) + '$ kNm',
                          xy=(0, 1.04 * last_M_max), color='r')
        ax_M.set_ylabel(r'$M_\mathrm{u}$ [kNm]')
        ax_M.set_xlabel(r'Reinforcement ratio $\rho$')
        ax_M.set_ylim(ymin=0)
        ax_M.set_xlim(xmin=0)
        ax_M.grid(color='#e6e6e6', linewidth=0.7)
        # ax_m_rho.legend()
        ax_util_conc.xaxis.set_major_formatter(PercentFormatter(xmax=1))
        ax_util_conc.set_xlabel(r'Reinforcement ratio $\rho$')
        ax_util_conc.set_ylabel('Concrete utilization ratio $\psi_c$') # $\psi_c = \sigma_{cc, max}/f_{\mathrm{cm}}$
        ax_util_conc.grid(color='#e6e6e6', linewidth=0.7)
        ax_util_conc.set_xlim(xmin=0)
        ax_util_conc.set_ylim(0, 1.07)
        ax_util_conc.legend()
        ax_util_reinf.tick_params(axis='y', labelcolor=c2)
        ax_util_reinf.set_ylabel('Reinf. utilization ratio $\psi_r$',
                              color=c2) # $\psi_r = \sigma_{r, max} / f_{\mathrm{ult}}$
        ax_util_reinf.set_xlim(xmin=0)
        ax_util_reinf.set_ylim(0, 1.07)
        ax_util_reinf.legend()

        if axes is None:
            return fig, (ax_M, ax_util_conc)

    def plot_M_rho_and_stress_rho(self, rho_list=None, axes=None, n_rho=50, reinf_layers_rho_factors=[1],
                                  return_rho_list_M_max=False):
        return self.plot_M_rho_and_util_factors(type='stress', rho_list=rho_list, axes=axes, n_rho=n_rho,
                                                reinf_layers_rho_factors=reinf_layers_rho_factors,
                                                return_rho_list_M_max=return_rho_list_M_max)

    def plot_M_rho_and_strain_rho(self, rho_list=None, axes=None, n_rho=50, reinf_layers_rho_factors=[1],
                                  return_rho_list_M_max=False):
        return self.plot_M_rho_and_util_factors(type='strain', rho_list=rho_list, axes=axes, n_rho=n_rho,
                                                reinf_layers_rho_factors=reinf_layers_rho_factors,
                                                return_rho_list_M_max=return_rho_list_M_max)

    def plot_mk_for_rho(self, rho, ax=None):
        """ TODO: This works for one reinf layer """
        A_old = self.cross_section_layout.items[0].A
        self.cross_section_layout.items[0].A = rho * self.get_bd()
        self.state_changed = True

        if ax is None:
            fig, ax = plt.subplots()
        self.plot_mk(ax)

        # Reassign the old value
        self.cross_section_layout.items[0].A = A_old
        self.state_changed = True

        if ax is None:
            return fig

