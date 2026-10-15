from bmcs_utils.parametric_study import ParametricStudy


class MKappaParamsStudy(ParametricStudy):
    """Peform a parametric study using the MKappa model"""
    def __init__(self, mc):
        self.mc = mc

    def plot(self, ax, param_name, value):
        ax.plot(self.mc.kappa_t, self.mc.M_t / self.mc.M_scale, label=param_name + '=' + str(value), lw=2)
        ax.set_ylabel('Moment [kNm]')
        ax.set_xlabel('Curvature [mm$^{-1}$]')
        ax.set_title(param_name)
        ax.legend()
