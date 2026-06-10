#!/usr/bin/env python
'''
mom6-tools is a collection of scripts for working with CESM/MOM6 output.
It relies on the following python packages:
 - matplotlib
 - xarray
 - etc
'''

from importlib.metadata import version, PackageNotFoundError

# Object-oriented entry point (the ongoing refactor).  Importing Case pulls in the data
# layer, which depends on xarray/numpy (the scientific stack is a hard dependency of this
# package anyway).  What stays deferred is the *per-diagnostic* machinery: each diagnostic's
# heavy/optional imports (plotting, intake, the dask cluster) load on first use via the
# registry, not at import time.
from mom6_tools.diagnostics import Case

#from MOM6grid import *
#from section_transports import *
#from latlon_analysis import *
#from poleward_heat_transport import *

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    # package is not installed
    __version__ = None
    pass
