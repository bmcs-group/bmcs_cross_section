import numpy as np
import traits.api as tr
from bmcs_utils.api import ModelDict, View, Item, Button, ButtonEditor, Str
from .cs_reinf_layer import ReinfLayer

class CrossSectionLayout(ModelDict):
    name = 'Cross Section Layout'
    cs_design = tr.WeakRef
    add_reinf_layer_btn = Button()
    remove_reinf_layer_btn = Button()
    reinf_layer_name = Str('Layer 1')

    @tr.observe('add_reinf_layer_btn')
    def _add_reinf_layer(self, _=None):
        if self.reinf_layer_name not in self.items:
            self.add_layer(ReinfLayer(name=self.reinf_layer_name))
        else:
            print(f'Layer "{self.reinf_layer_name}" is already added!')

    @tr.observe('remove_reinf_layer_btn')
    def _remove_reinf_layer(self, _=None):
        if self.reinf_layer_name in self.items:
            del self[self.reinf_layer_name]
            print(f'Reinf layer "{self.reinf_layer_name}" is removed!')
        else:
            print(f'Reinf layer "{self.reinf_layer_name}" doesn\'t exist to remove!')

    def add_layer(self, rl):
        self[rl.name] = rl
        rl.cs_layout = self

    @tr.Property
    def z_j(self):
        return np.array([r.z for r in self.values()], dtype=np.float_)

    @tr.Property
    def p_j(self):
        return np.array([r.p for r in self.values()], dtype=np.float_)

    @tr.Property
    def A_j(self):
        return np.array([r.A for r in self.values()], dtype=np.float_)

    def get_N_tj(self, eps_tj):
        return np.array([r.get_N(eps_t) for r, eps_t in zip(self.values(), eps_tj.T)],
                        dtype=np.float_).T

    ipw_view = View(
        Item('add_reinf_layer_btn', editor=ButtonEditor(icon='plus', label='Add reinf. layer')),
        Item('remove_reinf_layer_btn', editor=ButtonEditor(icon='minus', label='Remove reinf. layer')),
        Item('reinf_layer_name', latex='Layer name'),
    )

    def subplots(self, fig):
        return fig.subplots(1, 1)