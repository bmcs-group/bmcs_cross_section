import numpy as np
from bmcs_utils.api import Float, Int, Item, Model, View

from scite.beam.beam_config.system.beam_system import BeamSystem


class SimpleDistLoadSystem(BeamSystem):

    name = 'SimpleDistLoadSystem'

    F = Float(-5, SYSTEM=True)
    n_x = 2

    tree = []

    ipw_view = View(
        *BeamSystem.ipw_view.content,
        Item('F', latex=r'F \mathrm{[kN/m]}', readonly=True), # kN/m = N/mm
    )

    def update_struct(self):
        self.struct = self.get_new_struct()
        self.struct.add_multiple_elements([[0, 0], [self.L, 0]], self.n_x)
        self.struct.add_support_hinged(1)
        self.struct.add_support_roll(self.n_x + 1)
        elements = list(range(1, self.n_x + 1))
        self.struct.q_load(q=self.F, element_id=elements)
        self.struct.solve()

    def get_max_force(self, M_I):
        # This should be done numerically, but here for efficiency and
        # because this is a known case it's given directly
        return 8 * np.max(M_I) / self.L ** 2

    def get_plot_force_scale_and_unit(self):
        """ Scale which should be applied on the force when plotting """
        # Total load
        return 1 * self.L/1000, 'kN'
        # kN/m load
        # return 1, 'kN/m'
