import pickle
import json
import os
import pickle

import bmcs_utils.api as bu
import matplotlib.pyplot as plt
import numpy as np
import traits.api as tr
from scite.beam.api import BoundaryConfig, DeflectionProfile
from scite.api import MKappa, EC2, ReinfLayer
from matplotlib.ticker import PercentFormatter
import math
import copy

plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["font.size"] = 15
# To have math like LaTeX
plt.rcParams['mathtext.fontset'] = 'cm'
plt.rcParams['mathtext.rm'] = 'serif'

class BeamSLSCurve(bu.Model):
    name = 'Beam SLS Curve'

    '''
    - link to data cache identifying the directory where to store the
    interim results
    - dictionary based storage of the individual runs of the study
      which makes it introspective.
    '''

    sls_to_uls_ratio = bu.Float(0.51)
    slenderness_min = bu.Int(3)
    slenderness_max = bu.Int(50)
    rho_min = bu.Float(0.0002)
    rho_max = bu.Float(0.025)
    b = bu.Float(1000)
    h = bu.Float(300)
    high_kappa = bu.Float(0.00007)
    n_kappa = bu.Int(250)

    dp = bu.Instance(DeflectionProfile)

    def _dp_default(self):
        return self._get_dp_and_update_dp_design()

    dp_design = bu.Instance(DeflectionProfile)
    def _dp_design_default(self):
        return self.dp_design

    tree = ['dp', 'dp_design']
    # tree = ['dp']

    n_i = bu.Int(3)
    dense_quarter = bu.Bool(False)

    rho_range = tr.Property(depends_on='rho_max, rho_max, n_i, dense_quarter')

    @tr.cached_property
    def _get_rho_range(self):
        if self.dense_quarter:
            return self._get_range_with_dense_part(self.rho_min, self.rho_max)
        else:
            return np.linspace(self.rho_min, self.rho_max, self.n_i)

    slenderness_range = tr.Property(depends_on='slenderness_min, slenderness_max, n_i, dense_quarter')

    @tr.cached_property
    def _get_slenderness_range(self):
        if self.dense_quarter:
            return self._get_range_with_dense_part(self.slenderness_min, self.slenderness_max)
        else:
            return np.linspace(self.slenderness_min, self.slenderness_max, self.n_i)

    def _get_range_with_dense_part(self, min, max, part=0.25, weight=0.5):
        n_i = self.n_i
        dense_until = min + (max - min) * part
        first_quarter = np.linspace(min, dense_until, int(n_i * weight) + 1)
        rest = np.linspace(dense_until, max, math.ceil(n_i * (1 - weight)))[1:]
        return np.concatenate((first_quarter, rest))

    # pseudo time vars
    interrupt = bu.Bool(False)
    n_seg = bu.Int(5, TIME=True)
    seg = bu.Int(0)

    # dp properties:
    apply_material_factors = bu.Bool(False)
    system_type = bu.Str('dist')  # system_type can be '4pb' or '3pb' or 'dist'
    concrete_law = bu.Str('EC2')  # or 'piecewise linear' or 'EC2 with plateau'
    f_ck = bu.Float(103-8) # Concrete C3, f_cm = 103
    rein_type = bu.Str('steel') # can be 'carbon_grid', 'carbon_rebars', 'carbon_elg'
    use_f_ctm_fl = bu.Bool(False)

    rho = [] # final rho array (corresponds to contour on level 0)
    sl = [] # final slenderness array (corresponds to contour on level 0)
    rho_slider = bu.Float(0.01)
    ld_slider = bu.Float(10)
    indicator_corresponds_to_ld_slider = True

    @tr.observe('rho_slider')
    def _update_dp_according_to_rho(self, event):
        if len(self.rho) != 0:
            self._update_dp_according_to_slider(self.dp)
            self._update_dp_according_to_slider(self.dp_design)
        else:
            print('Generate l/d curves first!')
        self.indicator_corresponds_to_ld_slider = True

    @tr.observe('ld_slider')
    def _update_dp_according_to_ld(self, event):
        d = self.dp.mc.cross_section_shape_.H - list(self.dp.mc.cross_section_layout.items.values())[0].z
        self.dp.beam_design.system_.L = self.ld_slider * d
        self.dp_design.beam_design.system_.L = self.ld_slider * d
        self.indicator_corresponds_to_ld_slider = False

    def _update_dp_according_to_slider(self, dp):
        bd = dp.mc.get_bd()
        A_s = self.rho_slider * bd
        list(dp.mc.cross_section_layout.items.values())[0].A = A_s

        sl = np.interp(self.rho_slider, self.rho, self.sl)
        # TODO, this works only if we have one reinf layer AT THE BOTTOM!
        d = dp.mc.cross_section_shape_.H - list(dp.mc.cross_section_layout.items.values())[0].z
        dp.beam_design.system_.L = sl * d
        dp.mc.state_changed = True

    @tr.observe('apply_material_factors')
    @tr.observe('system_type')
    @tr.observe('concrete_law')
    @tr.observe('f_ck')
    @tr.observe('f_ctm') # Changes on f_ctm (a Property) are not triggering this!
    @tr.observe('rein_type')
    @tr.observe('use_f_ctm_fl')
    def _update_dp(self, event):
        self.dp = self._get_dp_and_update_dp_design()

    ipw_view = bu.View(
        bu.Item('rho_slider',
                editor=bu.FloatRangeEditor(label=r'$\rho$', low=0, high=0.025, n_steps=100, continuous_update=False)),
        bu.Item('ld_slider',
                editor=bu.FloatRangeEditor(label=r'$l/d$', low=1, high=50, n_steps=101, continuous_update=False)),
        bu.Item('slenderness_min', latex=r'{l/d}_\mathrm{min}'),
        bu.Item('slenderness_max', latex=r'{l/d}_\mathrm{max}'),
        bu.Item('rho_min', latex=r'\rho_\mathrm{min}'),
        bu.Item('rho_max', latex=r'\rho_\mathrm{max}'),
        bu.Item('n_i', latex='n_i'),
        bu.Item('dense_quarter', latex=r'\mathrm{Dense~quarter}'),
        bu.Item('apply_material_factors', latex=r'\mathrm{Apply}~\gamma'),
        bu.Item('sls_to_uls_ratio', latex=r'F_\mathrm{SLS}/F_\mathrm{ULS}'),
        bu.Item('system_type', latex=r'\mathrm{System}'),
        bu.Item('concrete_law', latex=r'\mathrm{concrete~law}'),
        bu.Item('f_ck', latex=r'f_{ck}'),
        bu.Item('f_ctm', latex=r'f_{ctm}', editor=bu.FloatEditor()),
        bu.Item('rein_type', latex=r'\mathrm{Rein~type}'),
        # bu.Item('slenderness_range', latex='l/d', editor=bu.IntRangeEditor(value=(10, 35), low_name='slenderness_low', high_name='slenderness_high', n_steps_name='')),
        time_editor=bu.ProgressEditor(
            run_method='run',
            reset_method='reset',
            interrupt_var='interrupt',
            time_var='seg',
            time_max='n_seg'
        )
    )

    _f_ctm = None
    f_ctm = tr.Property(desc='Concrete tensile strength')
    def _set_f_ctm(self, value):
        self._f_ctm = value

        # TODO: this update is a quick fix! tr.observe for f_ctm is not working to update dp
        self.dp = self._get_dp_and_update_dp_design()

    def _get_f_ctm(self):
        if self._f_ctm is not None:
            return self._f_ctm
        else:
            return EC2.get_f_ctm(self.f_ck)

    def _get_dp(self):
        print('dp updated!')
        b = self.b
        h = self.h
        d = 0.9 * h
        f_ck = self.f_ck
        rein_type = self.rein_type

        E = EC2.get_E_cm(f_ck)
        f_ctm_fl = EC2.get_f_ctm_fl(f_ck, h)

        f_ct = f_ctm_fl if self.use_f_ctm_fl else self.f_ctm
        # Unfactor tensile strength (like El-Gha, where f_ctm is used)
        # eps_cr = (1.5/0.85) * f_ct / E if self.apply_material_factors else f_ct / E

        # TODO: check this, it might give bigger f_ctm due to using E_cm
        eps_cr = f_ct / E

        mc = MKappa(low_kappa=0, high_kappa=self.high_kappa, n_kappa=self.n_kappa)
        mc.cs_design.concrete = self.concrete_law
        mc.cs_design.concrete_.trait_set(
            factor=0.85 / 1.5 if self.apply_material_factors else 1,
            eps_cr=eps_cr,
            eps_tu=eps_cr,
            mu=0.0,
        )

        if self.concrete_law == 'EC2 with plateau' or self.concrete_law == 'EC2':
            mc.cs_design.concrete_.trait_set(f_cm=EC2.get_f_cm(f_ck))
        elif self.concrete_law == 'piecewise linear':
            mc.cs_design.concrete_.trait_set(
                E_cc=E,
                E_ct=E,
                eps_cy=EC2.get_eps_c3(f_ck),
                eps_cu=EC2.get_eps_cu3(f_ck),
            )

        # # The default uses f_ctm. Here, I will use f_ctm_fl (in EC2, they tested with both)
        # mc.cs_design.concrete_.eps_cr = (EC2.get_f_ctm_fl(f_ck, h) * 1.5 / 0.85) / mc.cs_design.concrete_.E_ct
        # mc.cs_design.concrete_.eps_tu = (EC2.get_f_ctm_fl(f_ck, h) * 1.5 / 0.85) / mc.cs_design.concrete_.E_ct

        mc.cross_section_shape_.B = b
        mc.cross_section_shape_.H = h

        # T-section
        # mc.cross_section_shape = 'I-shape'
        # mc.cross_section_shape_.H = 200
        # mc.cross_section_shape_.B_w = 50
        # mc.cross_section_shape_.B_f_bot = 50
        # mc.cross_section_shape_.B_f_top = 150
        # mc.cross_section_shape_.H_f_bot = 50
        # mc.cross_section_shape_.H_f_top = 50

        rho = 0.01
        A_s = rho * b * d

        if rein_type == 'steel':
            bl1 = ReinfLayer(name=rein_type, z=h - d, A=A_s, matmod=rein_type)
            bl1.matmod_.trait_set(E_s=200000, f_sy=550, factor=1 / 1.15 if self.apply_material_factors else 1)
        elif rein_type == 'carbon_grid':
            bl1 = ReinfLayer(name=rein_type, z=h - d, A=A_s, matmod='carbon')
            # carbon material factors :
            # alpha_ft * alpha_f_eff / gamma_frp (see El-Ghadioui2020_PhD P. 122) # factor = (char->design) * (mean->char)
            bl1.matmod_.trait_set(E=230000, f_t=3300, factor=(0.85 * 0.9 / 1.3) * (0.85) if self.apply_material_factors else 1)
        elif rein_type == 'carbon_elg':
            bl1 = ReinfLayer(name=rein_type, z=h - d, A=A_s, matmod='carbon')
            # carbon material factors :
            # alpha_ft * alpha_f_eff / gamma_frp (see El-Ghadioui2020_PhD P. 122) # factor = (char->design) * (mean->char)
            f_tm = 1000 * 1.3 / (0.85 * 0.85 * 0.9)
            bl1.matmod_.trait_set(E=100000, f_t= f_tm, factor=(0.85 * 0.9 / 1.3) * (0.85) if self.apply_material_factors else 1)
        elif rein_type == 'carbon_rebars':
            bl1 = ReinfLayer(name=rein_type, z=h - d, A=A_s, matmod='carbon')
            # carbon material factors :
            # alpha_ft * alpha_f_eff / gamma_frp (see El-Ghadioui2020_PhD P. 122)
            bl1.matmod_.trait_set(E=158000, f_t=2500, factor=0.85 * 0.9 / 1.3 if self.apply_material_factors else 1)
        mc.cross_section_layout.add_layer(bl1)
        # mc.state_changed = True

        dp = DeflectionProfile(mc=mc, n_load_steps=100)
        if self.system_type == '4pb':
            dp.beam_design.system = '4pb'
        elif self.system_type == '3pb':
            dp.beam_design.system = '3pb'
        elif self.system_type == 'dist':
            dp.beam_design.system = 'simple_beam_dist_load'

        dp.beam_design.system_.L = 8 * d

        return dp

    def _get_dp_and_update_dp_design(self):
        dp1 = self._get_dp()
        dp2 = self._get_dp()
        self._update_dp_design(dp2)
        return dp1

    def _update_dp_design(self, dp_design):
        f_ck = self.f_ck

        E_k = f_ck / EC2.get_eps_c3(f_ck)

        if f_ck < 100:
            dp_design.mc.cs_design.concrete = 'EC2 with plateau'
            dp_design.mc.cs_design.concrete_.factor = 0.85 / 1.5
            dp_design.mc.cs_design.concrete_.f_cm = f_ck + 8
        else:
            dp_design.mc.cs_design.concrete = 'piecewise linear'
            dp_design.mc.cs_design.concrete_.trait_set(
                factor=0.85 / 1.5,
                E_cc=E_k,
                E_ct=E_k,
                eps_cy=EC2.get_eps_c3(f_ck),
                eps_cu=EC2.get_eps_cu3(f_ck),
            )

        # f_ctm_fl = EC2.get_f_ctm_fl(f_ck, dp_design.mc.cross_section_shape_.H)
        # f_ctm = f_ctm_fl if self.use_f_ctm_fl else self.f_ctm
        # f_ctk = EC2.get_f_ctk_0_05(f_ck)
        # eps_cr = f_ctk / E
        # dp_design.mc.cs_design.concrete_.trait_set(
        #     eps_cr=eps_cr,
        #     eps_tu=eps_cr,
        #     mu=0.0,
        # )

        for reinf_layer in list(dp_design.mc.cross_section_layout.items.values()):
            reinf_type = reinf_layer.name
            if reinf_type == 'steel':
                reinf_layer.matmod_.factor = (1 / 1.15) * (1 / 1.1) # (char->design) * (mean->char)
            else:
                # carbon material factors :
                # alpha_ft * alpha_f_eff / gamma_frp (see El-Ghadioui2020_PhD P. 122)
                reinf_layer.matmod_.factor = (0.85 * 0.9 / 1.3) * (0.85) # (char->design) * (mean->char)

        self.dp_design = dp_design

    def run(self, update_progress=lambda t: t):
        print('run started...')
        F_u_grid, F_s_grid, rho_grid, sl_grid = self.get_Fu_and_Fs()
        self.plot_with_ec2_curves(F_u_grid, F_s_grid, rho_grid, sl_grid,
                                  self.ax1 if hasattr(self, 'ax1') else None)
        print('run finished...')

    def reset(self):
        # reset everything to default values
        pass

    def subplots(self, fig):
        self.ax1, self.ax2 = fig.subplots(2, 1)
        return self.ax1, self.ax2

    def update_plot(self, axes):
        sl_curve_ax, ld_ax = axes
        if len(self.rho) != 0:
            if self.indicator_corresponds_to_ld_slider:
                sl = np.interp(self.rho_slider, self.rho, self.sl)
                sl_curve_ax.plot(self.rho_slider, sl, color='orange', marker='o')
            else:
                sl_curve_ax.plot(self.rho_slider, self.ld_slider, color='orange', marker='o')
        if hasattr(self, 'F_u_grid'):
            if len(self.F_u_grid) != 0:
                self.plot_with_ec2_curves(self.F_u_grid, self.F_s_grid, self.rho_grid, self.sl_grid, sl_curve_ax)
        self.plot_ld_curves(ld_ax)

    def plot_ld_curves(self, ax):
        eta = self.sls_to_uls_ratio
        self.dp.w_SLS = True

        self.dp.plot_fw_with_fmax(ax, f_max_label=r'$F_\mathrm{mean, u}$', f_max_color='black')
        self.dp_design.plot_fw_with_fmax(ax, f_max_label=r'$F_\mathrm{design, u}$')
        F_ULS_design = abs(self.dp_design.final_plot_F_scale * self.dp_design.beam_design.system_.F)
        F_SLS_design = eta * F_ULS_design

        ax.axhline(y=F_SLS_design, linestyle='--', color='r')
        ax.annotate(r'$F_{\mathrm{design,~SLS,~qp}} = $' + str(round(F_SLS_design, 2)), xy=(0, 1.06 * F_SLS_design),
                    color='r')

    # not used
    def save(self):
        out_dir = os.path.join(bu.data_cache.dir, self.__class__.__name__)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        with open(os.path.join(out_dir, 'class'), 'wb') as out_file:
            """ Giving TypeError: cannot pickle 'weakref' object"""
            pickle.dump(self, out_file)

    # not used
    def save_data_vars_in_json(self, f_ck, dp, path):
        mc = dp.mc
        rein = list(mc.cross_section_layout.items.values())
        output_data = {'mc.n_m': mc.n_m,
                       'mc.n_kappa': mc.n_kappa,
                       'mc.low_kappa': mc.low_kappa,
                       'mc.high_kappa': mc.high_kappa,
                       'mc.E_cc': mc.cs_design.concrete_.E_cc,
                       'mc.E_ct': mc.cs_design.concrete_.E_ct,
                       'mc.eps_tu': mc.cs_design.concrete_.eps_tu,
                       'mc.eps_cr': mc.cs_design.concrete_.eps_cr,
                       'mc.eps_cy': mc.cs_design.concrete_.eps_cy,
                       'mc.eps_cu': mc.cs_design.concrete_.eps_cu,
                       'mc.mu': mc.cs_design.concrete_.mu,
                       'f_ck': f_ck,
                       'rein[0].E': rein[0].matmod_.E,
                       'rein[0].z': rein[0].z,
                       'rein[0].A': rein[0].A,
                       'dp.beam_design.system_.L': dp.beam_design.system_.L, }
        with open(path, 'w') as outfile:
            json.dump(output_data, outfile, sort_keys=True, indent=4)

    def get_Fu_and_Fs(self, upper_reinforcement=False, plot=False):
        self.F_u_design_grid, self.F_s_design_grid, _, _, _, _ = self._get_grids(self.dp_design, calc_shear=False, mean=False)
        self.F_SLS_qp_design_grid = self.sls_to_uls_ratio * self.F_u_design_grid
        dp_grids = self._get_grids(self.dp, calc_shear=True, mean=True)
        self.F_u_grid, self.F_s_grid, self.rho_grid, self.sl_grid, self.F_u_shear_grid, self.w_SLS_qp_grid = dp_grids

        self.F_u_design_to_mean_grid = self.F_u_design_grid / self.F_u_grid
        return self.F_u_grid, self.F_s_grid, self.rho_grid, self.sl_grid


    def _get_grids(self, dp, upper_reinforcement=False, plot=False, calc_shear=False, mean=True):

        slenderness_range = self.slenderness_range
        rho_range = self.rho_range

        if upper_reinforcement:
            d = list(dp.mc.cross_section_layout.items.values())[0].z
        else:
            d = dp.mc.cross_section_shape_.H - list(dp.mc.cross_section_layout.items.values())[0].z

        bd = dp.mc.get_bd(upper_reinforcement = upper_reinforcement)

        rho_grid, sl_grid = np.meshgrid(rho_range, slenderness_range)
        F_u_grid = np.zeros_like(rho_grid)
        F_s_grid = np.zeros_like(rho_grid)
        w_SLS_qp_grid = np.zeros_like(rho_grid)
        F_u_shear_grid = np.zeros_like(rho_grid)

        if plot:
            _, ax = plt.subplots()
            ax.set_xlabel(r'$w$ [mm]')
            ax.set_ylabel(r'$F$ [KN]')

        for sl_idx in range(len(slenderness_range)):
            for rho_idx in range(len(rho_range)):
                if self.interrupt:
                    return

                rho = rho_grid[rho_idx, sl_idx]
                sl = sl_grid[rho_idx, sl_idx]

                print('parameter combination', rho, sl)

                # assigning the grid area (area_g) to the reinforcement area variable
                A_j_g = rho * bd
                list(dp.mc.cross_section_layout.items.values())[0].A = A_j_g

                # assigning the grid length (L_g) to the beam length variable
                L_g = sl * d
                dp.beam_design.system_.L = L_g

                dp.mc.state_changed = True

                # running the deflection analysis
                F_data, w_data = dp.get_Fw()
                F_data = F_data * dp.final_plot_F_scale

                # plotting, post-processing & saving the data
                if plot:
                    ax.plot(w_data, F_data, label="rho={}%-sl={} ".format(rho * 100, sl))

                w_s = dp.beam_design.system_.L / 250
                F_u = max(F_data)
                F_s = np.interp(w_s, w_data, F_data, right=F_u * 2)

                if calc_shear and dp.shear_force_can_be_calculated():
                    F_u_shear_grid[rho_idx, sl_idx] = dp.get_nm_shear_force_capacity()
                F_u_grid[rho_idx, sl_idx] = F_u
                F_s_grid[rho_idx, sl_idx] = F_s

                if mean:
                    F_SLS = self.sls_to_uls_ratio * self.F_u_design_grid[rho_idx, sl_idx]
                    w_SLS_qp_grid[rho_idx, sl_idx] = np.interp(F_SLS, F_data, w_data, right=max(w_data) * 2)

        return F_u_grid, F_s_grid, rho_grid, sl_grid, F_u_shear_grid, w_SLS_qp_grid

    def plot_with_ec2_curves(self, F_u_grid, F_s_grid, rho_grid, sl_grid, ax=None, label=None):
        if not ax:
            fig, ax = plt.subplots()

        color = np.random.rand(3, )

        z = F_u_grid / F_s_grid - 1. / (self.sls_to_uls_ratio * self.F_u_design_to_mean_grid)
        cs = ax.contour(rho_grid, sl_grid, z, levels=[0], colors=[color])
        if label:
            cs.collections[0].set_label(label)

        # Put values on lines
        # ax.clabel(cs, inline=True, fontsize=10)

        p = cs.collections[0].get_paths()[0]
        v = p.vertices
        self.rho = v[:, 0]
        self.sl = v[:, 1]

        # Draw EC2 curve
        self.plot_steel_sls_curves(ax, f_cks=[self.f_ck],
                                   axes_start_from_zero=True,
                                   color=color)

    def plot_steel_sls_curves(self, ax=None,
                              rho_range=np.linspace(0.0025, 0.025, 1000),
                              f_cks=np.arange(20, 110, 10),
                              rho_p=0,
                              K=1,
                              axes_start_from_zero=False,
                              color=None):
        if not ax:
            fig, ax = plt.subplots()

        slenderness = []
        for f_ck in f_cks:
            for rho in rho_range:
                slenderness.append(BeamSLSCurve.get_slenderness_limit(rho, f_ck, rho_p, K))
            ax.plot(rho_range, slenderness, label=r'$f_{ck} = $' + str(f_ck) + ' MPa (Steel - EC2)', ls='--', c=color)

            slenderness = []

        if axes_start_from_zero:
            ax.set_ylim(0, self.slenderness_max)
            ax.set_xlim(0, rho_range[-1])
        else:
            ax.set_ylim(10, self.slenderness_max)
            ax.set_xlim(rho_range[0], rho_range[-1])

        ax.xaxis.set_major_formatter(PercentFormatter(xmax=1))
        ax.set_ylabel(r'$l/(K \cdot d$)')
        ax.set_xlabel(r'Tensile reinforcement ratio $\rho$ [%]')
        ax.set_title(r'$l/d$ limits according to EC2 eqs. 7.16a & 7.16b')
        ax.grid(color='#e6e6e6', linewidth=0.7)
        ax.legend()

        if not ax:
            fig.show()

    @staticmethod
    def get_slenderness_limit(rho, f_ck, rho_p=0, K=1):
        # see EC2, see eqs 7.16
        rho_0 = 0.001 * np.sqrt(f_ck)
        if rho <= rho_0:
            return K * (11 + 1.5 * ((f_ck) ** 0.5) * (rho_0 / rho) + 3.2 * ((f_ck) ** 0.5) * (
                    (rho_0 / rho - 1) ** (3 / 2)))
        else:
            return K * (11 + 1.5 * ((f_ck) ** 0.5) * (rho_0 / (rho - rho_p)) + (1 / 12) * (f_ck ** 0.5) * (
                    (rho_p / rho_0) ** 0.5))

    def plot_F_u(self, load='bending', bending_shear_diff=False, scale=1, levels=None, sls=None):
        fig, ax = plt.subplots()
        fig.set_size_inches(5.5, 4.5)

        if sls is not None:
            z = self.F_u_grid/sls.F_u_grid
            levels = np.linspace(0, 5, 11)
            # z = self.F_u_grid - sls.F_u_grid
        elif bending_shear_diff:
            z = self.F_u_shear_grid - self.F_u_grid
        else:
            z = self.F_u_grid * scale if load == 'bending' else self.F_u_shear_grid * scale
        if levels is None:
            levels = [0, 10, 20, 30, 40, 60, 80, 100, 150, 300, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, -10,
                      -20, -30, -40, -60, -80, -100, -150, -300, -1000, -2000, -3000, -4000, -5000, -6000, -7000,
                      -8000]
            levels = np.array(levels) * scale
        levels.sort()
        cs = ax.contour(self.rho_grid, self.sl_grid, z, levels=levels) #cmap='RdYlBu_r', cmap='turbo', cmap='rainbow'
        cs_shade = ax.contourf(self.rho_grid, self.sl_grid, z, levels=[-1e6, 0], colors=['lightgray', 'white'])
        ax.clabel(cs, inline=True, fontsize=14)
        # sls.sls_to_uls_ratio = 0.59
        # sls._plot_with_ec2_curves(0.3*sls.F_u_grid, sls.F_s_grid, sls.rho_grid, sls.sl_grid, ax=ax)

        ax.xaxis.set_major_formatter(PercentFormatter(xmax=1))
        ax.set_ylabel(r'$L/d$')
        ax.set_xlabel(r'Reinforcement ratio $\rho$')
        ax.set_title(r'Contour lines of maximum load $F_\mathrm{max}$ [kN]') # where F_max = ql
        ax.grid(color='#e6e6e6', linewidth=0.7)
        ax.set_ylim(ymin=0)
        ax.set_xlim(xmin=0)
        # ax.legend()

        # fig.show()

        return fig


class SLSParamStudy(bu.ParametricStudy):
    def __init__(self, b_sls):
        self.b_sls = b_sls

    def plot(self, ax, plot_title, param_name_value):
        ax.set_xlabel(r'$w_\mathrm{max}$ [mm]')
        ax.set_ylabel(r'$F$ [kN]')

        self.b_sls.dp.mc.state_changed = True

        F_u_grid, F_s_grid, rho_grid, sl_grid = self.b_sls.get_Fu_and_Fs()
        self.b_sls.plot_with_ec2_curves(F_u_grid, F_s_grid, rho_grid, sl_grid, ax, label=param_name_value)
        ax.set_title(plot_title + ' effect')
        ax.legend()

        out_dir = self.get_output_dir()
        np.save(os.path.join(out_dir, 'F_u_grid' + '_' + self.b_sls.rein_type + '__' + param_name_value + '.npy'),
                F_u_grid)
        np.save(os.path.join(out_dir, 'F_s_grid' + '_' + self.b_sls.rein_type + '__' + param_name_value + '.npy'),
                F_s_grid)
        np.save(os.path.join(out_dir, 'rho_grid' + '_' + self.b_sls.rein_type + '__' + param_name_value + '.npy'),
                rho_grid)
        np.save(os.path.join(out_dir, 'sl_grid' + '_' + self.b_sls.rein_type + '__' + param_name_value + '.npy'),
                sl_grid)

    # # to be updated
    # def plot_all_curves(self):
    #     f_cks = [50]
    #     F_u_grids = []
    #     F_s_grids = []
    #     rho_grids = []
    #     sl_grids = []
    #     reinforcement = 'carbon'
    #     for f_ck in f_cks:
    #         f_ck = str(f_ck)
    #         F_u_grids.append(
    #             np.load('exported_data/F_u_grid_carbon_EC2_eq2_tension_E230_ft_3000_c' + str(f_ck) + '.npy'))
    #         F_s_grids.append(
    #             np.load('exported_data/F_s_grid_carbon_EC2_eq2_tension_E230_ft_3000_c' + str(f_ck) + '.npy'))
    #         rho_grids.append(
    #             np.load('exported_data/rho_grid_carbon_EC2_eq2_tension_E230_ft_3000_c' + str(f_ck) + '.npy'))
    #         sl_grids.append(np.load('exported_data/sl_grid_carbon_EC2_eq2_tension_E230_ft_3000_c' + str(f_ck) + '.npy'))
    #
    #     _, ax = plt.subplots(1, 1)
    #
    #     ax.set_ylabel('L/d')
    #     ax.set_xlabel(r'$\rho$ %')
    #     ax.set_ylim(0, self.slenderness_max)
    #     ax.set_xlim(0.0, self.rho_max)
    #
    #     for f_ck, F_u_grid, F_s_grid, rho_grid, sl_grid in zip(f_cks, F_u_grids, F_s_grids, rho_grids, sl_grids):
    #         z = 0.5 * F_u_grid / F_s_grid - 1. / self.b_sls.sls_to_uls_ratio
    #         CS = ax.contour(rho_grid, sl_grid, z, colors=[np.random.rand(3, )], levels=[0])
    #         CS.collections[0].set_label('C' + str(f_ck))
    #         #     ax.clabel(CS, inline=1, fontsize=10)
    #
    #         BeamSLSCurve().plot_steel_sls_curves(ax=ax, f_cks=[50], axes_start_from_zero=True)
    #
    #     ax.legend()
