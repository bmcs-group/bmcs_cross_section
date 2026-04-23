"""
Legacy Material Model Base Class

This is a legacy base class for old traits-based material models.
Modern implementations should inherit from scite.core.BMCSModel instead.
"""


class MatMod:
    """Legacy base class for material models (deprecated)
    
    Note: New material models should inherit from scite.core.BMCSModel
    instead of this legacy class.
    """

    def get_eps_plot_range(self):
        raise NotImplementedError

    def get_sig(self, eps):
        raise NotImplementedError

    def update_plot(self, ax):
        eps_range = self.get_eps_plot_range()
        sig_range = self.get_sig(eps_range)
        ax.plot(eps_range, sig_range, color='blue')
        ax.fill_between(eps_range, sig_range, 0, color='blue', alpha=0.1)
        ax.set_xlabel(r'$\varepsilon$ [-]')
        ax.set_ylabel(r'$\sigma$ [MPa]')
