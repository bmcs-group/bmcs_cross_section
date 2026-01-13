import bmcs_utils.api as bu
import numpy as np
from bmcs_cross_section.matmod.matmod import MatMod
from .concrete_compression_pwl import  ConcreteCompressionPWL
from .concrete_compression_ec2_plateau import ConcreteCompressionEC2Plateau
from .concrete_compression_ec2 import ConcreteCompressionEC2
from .concrete_tension_pwl import ConcreteTensionPWL

class ConcreteMatMod(MatMod):
    """Composed Concrete Material Model

    The concrete behavior can be combining using different laws for tension
    and compression by choosing the `tension` and `compression` laws.

    Each law must define the reference value of mean strength and the
    corresponding factors to obtain the characteristic and design values
    of strength. The material strength is multiplied by the reduction k_f
    which is activated based on the type of application - SIM, ULS, SLS
    """
    name = 'concrete'

    depends_on = ['compression', 'tension']
    ipw_tree = ['compression', 'tension']

    ipw_view = bu.View(
        bu.Item('compression'),
        bu.Item('tension')
    )

    compression = bu.EitherType(options=[
        ('piecewise-linear', ConcreteCompressionPWL),
        ('EC2 with plateau', ConcreteCompressionEC2Plateau),
        ('EC2', ConcreteCompressionEC2)
    ])

    tension = bu.EitherType(options=[
        ('piecewise-linear', ConcreteTensionPWL)
    ])

    def get_eps_plot_range(self):
        return np.linspace(self.compression_.eps_min, self.tension_.eps_max, 300)

    def get_sig(self, eps):
        """Given the sign of strain choose either the tensile or compressive law
        """
        return np.where(eps>0,
            self.tension_.get_sig(eps),
            self.compression_.get_sig(eps)
        )

pwl_concrete_matmod = ConcreteMatMod(
    compression = 'piecewise-linear',
    tension = 'piecewise-linear'
)

ec2_concrete_matmod = ConcreteMatMod(
    compression = 'EC2',
    tension = 'piecewise-linear'
)

ec2_with_plateau_matmod = ConcreteMatMod(
    compression = 'EC2 with plateau',
    tension = 'piecewise-linear'
)
