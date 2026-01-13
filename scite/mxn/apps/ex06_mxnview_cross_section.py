'''
Created on 26. 2. 2014

@author: Vancikv

Cross section from ex01 shown in a tree view.

Note that you can pass any tree node as root to the MxNTreeView
object. However, the standard case that allows for the whole
functionality to be used is the case when an instance of
UseCaseContainer is passed as root - as shown in examples 07-10.
'''

from mxn.cross_section import \
    CrossSection

from mxn.view import \
    MxNTreeView

from mxn.matrix_cross_section import \
    MatrixCrossSection, MCSGeoRect

from mxn.reinf_layout import \
    RLCBar

bar = RLCBar(x=0.1, z=0.05, material='bar_d10')
'''Single steel reinforcement bar
'''

ge = MCSGeoRect(height=0.5, width=0.3)
'''Cross section geometry
'''

mcs = MatrixCrossSection(geo=ge,
                         n_cj=20,
                         material='default_mixture',
                         material_law='constant')
'''Matrix cross section
'''

cs = CrossSection(reinf=[bar],
                  matrix_cs=mcs,
                  eps_lo=0.002,
                  eps_up=-0.0033
                  )

csw = MxNTreeView(root=cs)
csw.configure_traits()
