# Importing required modules and classes
from .cs_layout_dict import CrossSectionLayout
from .cs_shape import Rectangle, Circle, TShape, CustomShape, ICrossSectionShape, IShape
from bmcs_utils.api import Model, Item, View, Float, EitherType, Instance
from bmcs_cross_section.matmod import PWLConcreteMatMod, EC2PlateauConcreteMatMod, EC2ConcreteMatMod
import traits.api as tr

class CrossSectionDesign(Model):
    name = 'Cross Section Design' # Name of the instance

    matrix = EitherType(
        options=[
            ('EC2', EC2ConcreteMatMod),
            ('EC2 with plateau', EC2PlateauConcreteMatMod),
            ('piecewise linear', PWLConcreteMatMod),
        ], MAT=True)

    cross_section_layout = Instance(CrossSectionLayout)
    depends_on = ['matrix', 'cross_section_layout', 'cross_section_shape']
    tree = ['matrix','cross_section_layout','cross_section_shape']

    csl = tr.Property(lambda self: self.cross_section_layout)

    H = tr.Property(Float, lambda self: self.cross_section_shape_.H, 
                    lambda self, value: setattr(self.cross_section_shape_, "H", value))

    cross_section_shape = EitherType(
        options=[
            ('rectangle', Rectangle),
            ('I-shape', IShape),
            ('T-shape', TShape),
            ('custom', CustomShape)
        ], CS=True, tree=True)

    ipw_view = View(
        Item('matrix', latex=r'\mathrm{Conc.~law}', editor=EitherType(show_properties=False)),
        Item('cross_section_shape', latex=r'\mathrm{CS~shape}', editor=EitherType(show_properties=False)),
    )

    def subplots(self, fig):
        return fig.subplots(1, 1)

    def update_plot(self, ax):
        self.cross_section_shape_.update_plot(ax)
        self.cross_section_layout.update_plot(ax)