# Importing required modules and classes
from .cs_layout_dict import CrossSectionLayout
from .cs_shape import Rectangle, Circle, TShape, CustomShape, ICrossSectionShape, IShape
from bmcs_utils.api import Model, Item, View, Float, EitherType, Instance
import traits.api as tr
import bmcs_utils.api as bu
from bmcs_cross_section.matmod import ConcreteMatMod

class CrossSectionDesign(Model):
    name = 'Cross Section Design'

    matrix = bu.Instance(ConcreteMatMod)
    def _matrix_default(self):
        return ConcreteMatMod()

    concrete = tr.Property
    def _get_concrete(self):
        """Alias attribute for matrix"""
        return self.matrix

    def _set_concrete(self, value):
        """Alias attribute for matrix"""
        self.matrix = value

    cross_section_layout = bu.Instance(CrossSectionLayout)

    def _cross_section_layout_default(self):
        return CrossSectionLayout(cs_design=self)

    depends_on = ['matrix', 'cross_section_layout', 'cross_section_shape']
    tree = ['matrix','cross_section_layout','cross_section_shape']

    csl = tr.Property(lambda self: self.cross_section_layout)

    H = tr.Property(bu.Float)
    def _get_H(self):
        return self.cross_section_shape_.H
    def _set_H(self,value):
        self.cross_section_shape_.H = value

    cross_section_shape = bu.EitherType(options=[
        ('rectangle', Rectangle),
        ('I-shape', IShape),
        ('T-shape', TShape),
        ('custom', CustomShape)],
    CS=True, tree=True)

    ipw_view = View(
        Item('matrix', latex=r'\mathrm{Conc.~law}'),
        Item('cross_section_shape', latex=r'\mathrm{CS~shape}', 
             editor=bu.EitherTypeEditor(show_properties=False)),
    )

    def subplots(self, fig):
        return fig.subplots(1, 1)

    def update_plot(self, ax):
        self.cross_section_shape_.update_plot(ax)
        self.cross_section_layout.update_plot(ax)