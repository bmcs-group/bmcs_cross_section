import numpy as np
import sympy as sp
import traits.api as tr

from bmcs_cross_section.cs_design import CrossSectionDesign
from scipy.optimize import root
from bmcs_utils.api import \
    Model, Instance, Item, View, mpl_align_xaxis, SymbExpr, \
    InjectSymbExpr, Float, Int, Bool, HistoryEditor


class SolutionNotFoundError(ValueError):
    pass


class MKappaSymbolic(SymbExpr):
    """This class handles all the symbolic calculations
    so that the class MomentCurvature doesn't use sympy ever
    """
    # -------------------------------------------------------------------------
    # Symbolic derivation of expressions
    # -------------------------------------------------------------------------
    kappa = sp.Symbol('kappa', real=True)
    eps_top = sp.symbols('varepsilon_top', real=True)
    eps_bot = sp.symbols('varepsilon_bot', real=True)
    b, h, z = sp.symbols('b, h, z', real=True, nonnegative=True)
    eps = sp.Symbol('varepsilon', real=True)

    # -------------------------------------------------------------------------
    # Symbolic derivation of expressions
    # -------------------------------------------------------------------------
    # Linear profile of strain over the cross section height
    eps_z_ = eps_bot + z * (eps_top - eps_bot) / h
    eps_top_solved = {eps_top: sp.solve(kappa + eps_z_.diff(z), eps_top)[0]}
    eps_z = eps_z_.subs(eps_top_solved)

    # ----------------------------------------------------------------
    # SymbExpr protocol: Parameter names to be fetched from the model
    # ----------------------------------------------------------------
    symb_model_params = ()

    symb_expressions = [
        ('eps_z', ('kappa', 'eps_bot', 'z')),
    ]


class MKappa(Model, InjectSymbExpr):
    """Class returning the moment curvature relationship."""
    name = 'Moment-Curvature'

    symb_class = MKappaSymbolic
    cs_design = Instance(CrossSectionDesign, ())

    depends_on = ['cs_design']
    ipw_tree = ['cs_design']
    # Use PrototypedFrom only when the prototyped object is a class
    # (The prototyped attribute behaves similarly
    # to a delegated attribute, until it is explicitly
    # changed; from that point forward, the prototyped attribute
    # changes independently from its prototype.)
    # (it's kind of like tr.DelegatesTo('cs_design.cross_section_shape'))
    cross_section_shape = tr.DelegatesTo('cs_design')
    cross_section_shape_ = tr.DelegatesTo('cs_design')
    cross_section_layout = tr.DelegatesTo('cs_design')
    matrix = tr.DelegatesTo('cs_design', 'concrete')

    # Geometry
    H = tr.DelegatesTo('cross_section_shape_')

    DEPSTR = 'state_changed'

    n_m = Int(100, DSC=True, desc='Number of discretization points along the height of the cross-section')

    # @todo: fix the dependency - `H` should be replaced by _GEO
    z_m = tr.Property(depends_on=DEPSTR)

    @tr.cached_property
    def _get_z_m(self):
        return np.linspace(0, self.H, self.n_m)

    low_kappa = Float(0.0, BC=True, GEO=True)
    high_kappa = Float(0.00002, BC=True, GEO=True)
    n_kappa = Int(100, BC=True)
    step_kappa = tr.Property(Float, depends_on='low_kappa, high_kappa')
    @tr.cached_property
    def _get_step_kappa(self):
        return float((self.high_kappa-self.low_kappa)/self.n_kappa)

    kappa_slider = Float(0.0000001)

    ipw_view = View(
        Item('low_kappa', latex=r'\text{Low}~\kappa'), #, editor=FloatEditor(step=0.00001)),
        Item('high_kappa', latex=r'\text{High}~\kappa'), # , editor=FloatEditor(step=0.00001)),
        Item('n_kappa', latex='n_{\kappa}'),
        Item('n_m', latex='n_m'),
        Item('plot_mk_inverse', latex=r'\text{Plot}~\kappa\text{-M}'),
        # Item('solve_for_eps_bot_pointwise'),
        Item('kappa_slider', latex='\kappa', readonly=True),
             # editor=FloatRangeEditor(low_name='low_kappa',
             #                         high_name='high_kappa',
             #                         n_steps_name='n_kappa')
             # ),
        time_editor=HistoryEditor(label='κ slider',
                                  var='kappa_slider',
                                  min_var='low_kappa',
                                  max_var='high_kappa',
                                  step_value=0.001
                                  ),
    )

    idx = tr.Property(depends_on='kappa_slider')

    apply_material_safety_factors = tr.Bool(False)

    @tr.cached_property
    def _get_idx(self):
        return self.get_idx_matching_kappa_value()

    def get_idx_matching_kappa_value(self, kappa_value=None):
        ks = self.kappa_slider if kappa_value is None else kappa_value
        idx = np.argmax(ks <= self.kappa_t)
        return idx

    kappa_t = tr.Property(tr.Array(np.float64), depends_on=DEPSTR)
    '''Curvature values for which the bending moment must be found
    '''

    @tr.cached_property
    def _get_kappa_t(self):
        n_kappa = self.n_kappa
        low_kappa = self.low_kappa
        high_kappa = self.high_kappa
        if low_kappa >= 0:
            # Make kappa list denser up to (0.15 * the kappa range) to capture cracking moment properly, otherwise
            # deflections in SLS might be inaccurate
            n_1 = int(0.4 * n_kappa)
            n_2 = n_kappa - n_1
            return np.concatenate((np.linspace(low_kappa, 0.15 * high_kappa, n_1, endpoint=False),
                                       np.linspace(0.15 * high_kappa, high_kappa, n_2)))
        else:
            return np.linspace(low_kappa, high_kappa, n_kappa)

    z_j = tr.Property
    def _get_z_j(self):
        return self.cross_section_layout.z_j

    A_j = tr.Property
    def _get_A_j(self):
        return self.cross_section_layout.A_j

    def get_eps_z_tj(self, kappa_t, eps_bot_t):
        """strains in all reinforcement layers
        """
        return self.symb.get_eps_z(
            kappa_t[:, np.newaxis], eps_bot_t[:, np.newaxis],
            self.z_j[np.newaxis, :]
        )

    # Normal force in steel (tension and compression)
    def get_N_s_tj(self, kappa_t, eps_bot_t):
        # get the strain at the height of the reinforcement
        # Get the crack bridging force in each reinforcement layer
        # given the corresponding crack-bridge law.
        eps_z_tj = self.get_eps_z_tj(kappa_t, eps_bot_t)
        N_s_tj = self.cross_section_layout.get_N_tj(eps_z_tj)
        return N_s_tj

    # TODO - [RC] avoid repeated evaluations of stress profile in
    #            N and M calculations for the same inputs as it
    #            is the case now.
    def get_sig_c_z(self, kappa_t, eps_bot_t, z_tm):
        """Get the stress profile over the height"""
        eps_z = self.symb.get_eps_z(kappa_t[:, np.newaxis], eps_bot_t[:, np.newaxis], z_tm)
        sig_c_z = self.matrix.get_sig(eps_z)
        return sig_c_z

    # Normal force in concrete (tension and compression)
    def get_N_c_t(self, kappa_t, eps_bot_t):
        z_tm = self.z_m[np.newaxis, :]
        b_z_m = self.cross_section_shape_.get_b(z_tm)
        N_z_tm2 = b_z_m * self.get_sig_c_z(kappa_t, eps_bot_t, z_tm)
        return np.trapz(N_z_tm2, x=z_tm, axis=-1)
        # Slightly faster option but first and last value will be slightly higher here
        # return np.sum(N_z_tm2 * self.cross_section_shape_.H/self.n_kappa, axis=1)

    def get_N_t(self, kappa_t, eps_bot_t):
        N_s_t = np.sum(self.get_N_s_tj(kappa_t, eps_bot_t), axis=-1)
        N_c_t = self.get_N_c_t(kappa_t, eps_bot_t)
        return N_c_t + N_s_t

    # SOLVER: Get eps_bot to render zero force

    eps_bot_sol_t = tr.Property(depends_on=DEPSTR)
    r'''Resolve the tensile strain to get zero normal force for the prescribed curvature'''

    solve_for_eps_bot_pointwise = Bool(True, BC=True, GEO=True)

    @tr.cached_property
    def _get_eps_bot_sol_t(self):
        if self.solve_for_eps_bot_pointwise:
            """ INFO: Instability in eps_bot solutions was caused by unsuitable init_guess value causing a convergence 
            to non-desired solutions. Solving the whole kappa_t array improved the init_guess after each
            calculated value, however, instability still there. The best results were obtained by taking the last 
            solution as the init_guess for the next solution like in the following.. """
            # One by one solution for kappa values
            eps_bot_sol_for_pos_kappa = self._get_eps_bot_piecewise_sol(kappa_pos=True)
            eps_bot_sol_for_neg_kappa = self._get_eps_bot_piecewise_sol(kappa_pos=False)
            res = np.concatenate([eps_bot_sol_for_neg_kappa, eps_bot_sol_for_pos_kappa])
            return res
        else:
            # Array solution for the whole kappa_t
            res = root(lambda eps_bot_t: self.get_N_t(self.kappa_t, eps_bot_t),
                       0.0000001 + np.zeros_like(self.kappa_t), tol=1e-6)
            if not res.success:
                print('No solution', res.message)
            return res.x

    def _get_eps_bot_piecewise_sol(self, kappa_pos=True):
        if kappa_pos:
            kappas = self.kappa_t[np.where(self.kappa_t >= 0)]
        else:
            kappas = self.kappa_t[np.where(self.kappa_t < 0)]

        res = []
        if kappa_pos:
            init_guess = 0.00001
            kappa_loop_list = kappas
        else:
            init_guess = -0.00001
            kappa_loop_list = reversed(kappas)

        for kappa in kappa_loop_list:
            eps_bot_sol = root(lambda eps_bot: self.get_N_t(np.array([kappa]), eps_bot),
                               np.array([init_guess]),
                               tol=1e-6).x[0]

            # This condition is to avoid having init_guess≈0 which causes no convergence
            if abs(eps_bot_sol) > 1e-5:
                init_guess = eps_bot_sol
            res.append(eps_bot_sol)

        return res if kappa_pos else list(reversed(res))

    # POSTPROCESSING

    eps_z_sol_tj = tr.Property(depends_on='state_changed')
    @tr.cached_property
    def _get_eps_z_sol_tj(self):
        return self.symb.get_eps_z(
            self.kappa_t[:, np.newaxis], self.eps_bot_sol_t[:, np.newaxis],
            self.z_j[np.newaxis, :]
        )

    kappa_cr = tr.Property(depends_on=DEPSTR)
    '''Curvature at which a critical strain is attained at the eps_bot'''

    @tr.cached_property
    def _get_kappa_cr(self):
        res = root(lambda kappa: self.get_N_t(kappa, self.eps_cr),
                   0.0000001 + np.zeros_like(self.eps_cr), tol=1e-10)
        if not res.success:
            print('No kappa_cr solution (for plot_norm() function)', res.message)
        return res.x

    M_s_t = tr.Property(depends_on=DEPSTR)
    '''Bending moment (steel)
    '''

    @tr.cached_property
    def _get_M_s_t(self):
        if len(self.z_j) == 0:
            return np.zeros_like(self.kappa_t)

        eps_z_tj = self.eps_z_sol_tj

        # Get the crack bridging force in each reinforcement layer
        # given the corresponding crack-bridge law.
        N_tj = self.cross_section_layout.get_N_tj(eps_z_tj)
        return np.einsum('tj,j->t', N_tj, self.z_j)

    M_c_t = tr.Property(depends_on=DEPSTR)
    '''Bending moment (concrete)
    '''

    @tr.cached_property
    def _get_M_c_t(self):
        z_tm = self.z_m[np.newaxis, :]
        b_z_m = self.cross_section_shape_.get_b(z_tm)
        N_z_tm2 = b_z_m * self.get_sig_c_z(self.kappa_t, self.eps_bot_sol_t, z_tm)
        return np.trapz(N_z_tm2 * z_tm, x=z_tm, axis=-1)
        # Slightly faster option but first and last value will be slightly higher here
        # return np.sum(N_z_tm2 * z_tm * self.cross_section_shape_.H/self.n_kappa, axis=1)

    M_t = tr.Property(depends_on=DEPSTR)
    '''Bending moment
    '''
    @tr.cached_property
    def _get_M_t(self):
        # Multiplied with (-1) to have positive moments when simply supported beam and negative moments when cantilever
        # print('M - k recalculated')
        eta_factor = 1.
        return - eta_factor * (self.M_c_t + self.M_s_t)

    N_s_tj = tr.Property(depends_on=DEPSTR)
    '''Normal forces (steel)
    '''

    @tr.cached_property
    def _get_N_s_tj(self):
        return self.get_N_s_tj(self.kappa_t, self.eps_bot_sol_t)

    eps_tm = tr.Property(depends_on=DEPSTR)
    '''strain profiles
    '''

    @tr.cached_property
    def _get_eps_tm(self):
        return self.symb.get_eps_z(self.kappa_t[:, np.newaxis],
                              self.eps_bot_sol_t[:, np.newaxis], self.z_m[np.newaxis, :])

    sig_tm = tr.Property(depends_on=DEPSTR)
    '''stress profiles
    '''

    @tr.cached_property
    def _get_sig_tm(self):
        return self.get_sig_c_z(
            self.kappa_t, self.eps_bot_sol_t, self.z_m[np.newaxis, :]
        )

    M_norm = tr.Property(depends_on=DEPSTR)
    '''
    '''
    @tr.cached_property
    def _get_M_norm(self):
        # Section modulus @TODO optimize W for var b
        W = (self.b * self.H ** 2) / 6
        sig_cr = self.E_ct * self.eps_cr
        return W * sig_cr

    kappa_norm = tr.Property()

    def _get_kappa_norm(self):
        return self.kappa_cr

    inv_M_kappa = tr.Property(depends_on=DEPSTR)
    '''Return the inverted data points
    '''
    @tr.cached_property
    def _get_inv_M_kappa(self):
        try:
            """cut off the descending tails"""
            M_t = self.M_t
            kappa_t = self.kappa_t
            I_max = np.argmax(M_t)
            if np.any(kappa_t < 0):
                I_min = np.argmin(M_t)
                if I_min < I_max:
                    M_I = np.copy(M_t[I_min:I_max + 1])
                    kappa_I = np.copy(kappa_t[I_min:I_max + 1])
                    # find the index corresponding to zero kappa
                    idx = np.argmax(0 <= kappa_I)
                else:
                    raise Exception("Index of M_I min is larger than M_I max!")
            else:
                M_I = np.copy(M_t[0:I_max + 1])
                kappa_I = np.copy(kappa_t[0:I_max + 1])
                idx = 0
            # and modify the values such that the
            # Values of moment are non-descending
            M_plus = M_I[idx:]
            M_diff = M_plus[:, np.newaxis] - M_plus[np.newaxis, :]
            n_ij = len(M_plus)
            ij = np.mgrid[0:n_ij:1, 0:n_ij:1]
            M_diff[np.where(ij[1] >= ij[0])] = 0
            i_x = np.argmin(M_diff, axis=1)
            M_I[idx:] = M_plus[i_x]
            return M_I, kappa_I
        except ValueError:
            print('M inverse has not succeeded, the M-Kappa solution may have failed due to '
                  'a wrong kappa range or not suitable material law!')
            return np.array([0]), np.array([0])


    def get_kappa_M(self, M):
        M_I, kappa_I = self.inv_M_kappa
        return np.interp(M, M_I, kappa_I)

    def plot_norm(self, ax1, ax2):
        idx = self.idx
        ax1.plot(self.kappa_t / self.kappa_norm, self.M_t / self.M_norm)
        ax1.plot(self.kappa_t[idx] / self.kappa_norm, self.M_t[idx] / self.M_norm, marker='o')
        ax2.barh(self.z_j, self.N_s_tj[idx, :], height=2, color='red', align='center')
        # ax2.fill_between(eps_z_arr[idx,:], z_arr, 0, alpha=0.1);
        ax3 = ax2.twiny()
        #  ax3.plot(self.eps_tm[idx, :], self.z_m, color='k', linewidth=0.8)
        ax3.plot(self.sig_tm[idx, :], self.z_m)
        ax3.axvline(0, linewidth=0.8, color='k')
        ax3.fill_betweenx(self.z_m, self.sig_tm[idx, :], 0, alpha=0.1)
        mpl_align_xaxis(ax2, ax3)

    M_scale = Float(1e+6)
    plot_mk_inverse = Bool(False)

    def plot(self, ax1, ax2, ax22, ax3):
        self.plot_mk_and_stress_profile(ax1, ax2, ax22)
        if self.plot_mk_inverse:
            self.plot_mk_inv(ax3)
        else:
            self.plot_strain_profile(ax3)

    @staticmethod
    def subplots(fig):
        ax1, ax2, ax3 = fig.subplots(1, 3)
        ax22 = ax2.twiny()
        return ax1, ax2, ax22, ax3

    def update_plot(self, axes):
        print('in update plot', self.kappa_slider)
        self.plot(*axes)

    def plot_mk_inv(self, ax3):
        try:
            M, kappa = self.inv_M_kappa
            ax3.plot(M / self.M_scale, kappa)
        except ValueError:
            print('M inverse has not succeeded, the M-Kappa solution may have failed due to a wrong kappa range!')

        ax3.set_xlabel('Moment [kNm]')
        ax3.set_ylabel('Curvature[mm$^{-1}$]')

    def plot_mk_and_stress_profile(self, ax1, ax2, ax22):
        self.plot_mk(ax1)
        idx = self.idx
        ax1.plot(self.kappa_t[idx], self.M_t[idx] / self.M_scale, color='orange', marker='o')

        if len(self.z_j):
            ax2.barh(self.z_j, self.N_s_tj[idx, :]/self.A_j, height=4, color='red', align='center')
            ax2.set_ylabel('z [mm]')
            ax2.set_xlabel('$\sigma_r$ [MPa]')

        ax22.set_xlabel('$\sigma_c$ [MPa]')
        ax22.plot(self.sig_tm[idx, :], self.z_m)
        ax22.axvline(0, linewidth=0.8, color='k')
        ax22.fill_betweenx(self.z_m, self.sig_tm[idx, :], 0, alpha=0.1)
        mpl_align_xaxis(ax2, ax22)

    def plot_mk(self, ax1, dashed=False, color='#1f77b4'):
        ax1.plot(self.kappa_t, self.M_t / self.M_scale, '--' if dashed else '-', c=color, label='Sim.')
        ax1.set_ylabel('Moment [kNm]')
        ax1.set_xlabel('Curvature [mm$^{-1}$]')
        ax1.legend()


    def plot_strain_profile(self, ax):
        ax.set_ylabel('z [mm]')
        ax.set_xlabel(r'$\varepsilon$ [-]')
        ax.plot(self.eps_tm[self.idx, :], self.z_m)
        ax.axvline(0, linewidth=0.8, color='k')
        ax.fill_betweenx(self.z_m, self.eps_tm[self.idx, :], 0, alpha=0.1)

        eps_z_j = self.eps_z_sol_tj[self.idx]
        ax.barh(self.z_j, eps_z_j,
                height=4, color='red', align='center')
        ax.barh(self.z_j, self.cross_section_layout.eps_0_j, left=eps_z_j,
                height=2, color='blue', align='center')

    def get_mk(self):
        return self.M_t / self.M_scale, self.kappa_t

    def get_bd(self, upper_reinforcement=False):
        if self.cross_section_shape != 'rectangle':
            return self.cross_section_shape_.get_cs_area()

        z = list(self.cross_section_layout.items.values())[0].z
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
        for reinf_item in list(self.cross_section_layout.items.values()):
            z = reinf_item.z
            reinf_max_strain.append(np.interp(z, self.z_m, self.eps_tm[idx, :]))
        concr_max_strain_t = np.max(self.eps_tm[idx, :])
        concr_max_strain_c = np.min(self.eps_tm[idx, :])
        return np.array(reinf_max_strain), concr_max_strain_c, concr_max_strain_t

    def get_M_n_ACI(self):
        """
        According to ACI 440.1R-15
        """
        matmod = list(self.cross_section_layout.items.values())[0].matmod
        reinf_layers_num = len(list(self.cross_section_layout.items.values()))
        if matmod != 'carbon' or reinf_layers_num > 1:
            print('This approach is valid only for FRP reinf. with 1 reinf. layer!')
            return
        f_cm = self.matrix_.f_cm
        f_fu = list(self.cross_section_layout.items.values())[0].matmod_.f_t
        E_f = list(self.cross_section_layout.items.values())[0].matmod_.E
        A_f = list(self.cross_section_layout.items.values())[0].A
        z = list(self.cross_section_layout.items.values())[0].z
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

    # def plot_M_rho_to_M_rho_for_other_mc(self, mc, rho_list=None, ax=None, n_rho=50, mc_reinf_layers_rho_factors=[1]):
    #     fig = None
    #     if ax is None:
    #         fig, ax = plt.subplots()
    #         fig.set_size_inches(5.5, 3.4)
    #     if rho_list is None:
    #         n_1 = int(0.35 * n_rho)
    #         n_2 = int(0.25 * n_rho)
    #         n_3 = n_rho - n_1 - n_2
    #         rho_list = np.concatenate((np.linspace(0.0, 0.004, n_1, endpoint=False),
    #                                    np.linspace(0.004, 0.006, n_2, endpoint=False),
    #                                    np.linspace(0.006, 0.025, n_3)))
    #         print('Non regular rho_list was created (denser up to rho = 0.4%).')
    #     M_max = []
    #     mc_M_max = []
    #     for rho in rho_list:
    #         list(self.cross_section_layout.items.values())[0].A = rho * self.get_bd()
    #         self.state_changed = True
    #         M = self.M_t / self.M_scale
    #         M_max.append(np.max(M))
    #
    #         for i, factor in enumerate(mc_reinf_layers_rho_factors):
    #             mc.cross_section_layout.items[i].A = factor * rho * mc.get_bd()
    #         mc.state_changed = True
    #         M = mc.M_t / mc.M_scale
    #         mc_M_max.append(np.max(M))
    #
    #     M_max_ratio = np.array(mc_M_max) / np.array(M_max)
    #     ratio_max = np.max(M_max_ratio)
    #     ax.axhline(y=ratio_max, color='r')
    #     ax.annotate(r'max= ' + str(ratio_max), xy=(0, 1.04 * ratio_max), color='r')
    #
    #     ax.plot(rho_list, M_max_ratio, c='black')
    #     ax.set_ylabel(r'$M_\mathrm{max2}/M_\mathrm{max1}$')
    #     ax.set_xlabel(r'Reinforcement ratio $\rho$')
    #     ax.set_ylim(ymin=0)
    #     ax.set_xlim(xmin=0)
    #     ax.grid(color='#e6e6e6', linewidth=0.7)
    #
    #     if fig is not None:
    #         return fig, ax

    # Backward compatibility
    def plot_M_rho_and_stress_rho(self, rho_list=None, axes=None, n_rho=50, reinf_layers_rho_factors=[1],
                                  return_rho_list_M_max=False):
        return self.plot_M_rho_and_util_factors(type='stress', rho_list=rho_list, axes=axes, n_rho=n_rho,
                                                reinf_layers_rho_factors=reinf_layers_rho_factors,
                                                return_rho_list_M_max=return_rho_list_M_max)

    # Backward compatibility
    def plot_M_rho_and_strain_rho(self, rho_list=None, axes=None, n_rho=50, reinf_layers_rho_factors=[1],
                                  return_rho_list_M_max=False):
        return self.plot_M_rho_and_util_factors(type='strain', rho_list=rho_list, axes=axes, n_rho=n_rho,
                                                reinf_layers_rho_factors=reinf_layers_rho_factors,
                                                return_rho_list_M_max=return_rho_list_M_max)

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
            rho_list = np.concatenate((np.linspace(0.0, 0.004, n_1, endpoint=False),
                                       np.linspace(0.004, 0.006, n_2, endpoint=False),
                                       np.linspace(0.006, 0.025, n_3)))
            print('Non regular rho_list was created (denser up to rho = 0.4%).')
        M_max = []
        reinf_st = []
        concrete_st_c = []

        for rho in rho_list:
            for i, factor in enumerate(reinf_layers_rho_factors):
                list(self.cross_section_layout.items.values())[i].A = factor * rho * self.get_bd()
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
            concrete_st_c = np.abs(concrete_st_c / self.matrix_.eps_cu)
            concrete_st_c = np.where(concrete_st_c > 1, 1, concrete_st_c)

        reinf_st_lr = np.array(reinf_st).T  # where l is index for reinf layer and r for rho

        c1 = 'black'
        ax_util_conc.plot(rho_list, concrete_st_c, '--', color=c1,
                       label='Concrete utilization ratio $\psi_c$')  # = \sigma_{cc, max}/f_{\mathrm{cm}}

        c2 = 'red'
        ax_util_reinf = ax_util_conc.twinx()
        for i, reinf_st in enumerate(reinf_st_lr):
            reinf_item = list(self.cross_section_layout.items.values())[i]
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

    def plot_mk_for_rho(self, rho, ax=None):
        """ TODO: This works for one reinf layer """
        A_old = list(self.cross_section_layout.items.values())[0].A
        list(self.cross_section_layout.items.values())[0].A = rho * self.get_bd()
        self.state_changed = True

        if ax is None:
            fig, ax = plt.subplots()
        self.plot_mk(ax)

        # Reassign the old value
        list(self.cross_section_layout.items.values())[0].A = A_old
        self.state_changed = True

        if ax is None:
            return fig

