'''
Created on Aug 23, 2012

@author: rch
'''

from mxn.constitutive_law import CLBase
from mxn.mxn_class_extension import \
    MxNClassExt
from mxn.mxn_tree_node import \
    MxNLeafNode
from traits.api import \
    List

from mxn.matresdev.db.simdb import \
    SimDBClass, SimDBClassExt


class ReinfLawBase(CLBase, MxNLeafNode, SimDBClass):
    '''Base class for Effective Crack Bridge Laws.'''

    u0 = List([0.0, 0.0])
    node_name = 'Constitutive law'

ReinfLawBase.db = MxNClassExt(
    klass=ReinfLawBase,
    verbose='io',
    node_name='Reinforcement law database'
)

if __name__ == '__main__':
    ReinfLawBase.db.configure_traits()
