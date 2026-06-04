"""Object-oriented core for mom6-tools (the ongoing refactor).

This subpackage holds the new building blocks that sit underneath the diagnostic
scripts:

* :class:`~mom6_tools.diagnostics.datasource.DataSource` - resolves a model-output
  *source* (a ``diag_config.yml``, a MOM6 ``diag_table``, or explicit files) to a
  uniform ``{stream -> dataset}`` interface, so diagnostics don't each re-implement
  path resolution and preprocessing.
* :class:`~mom6_tools.diagnostics.cluster.Cluster` - a small context manager around
  ``m6toolbox.request_workers`` for dask parallelism.

Later phases add a ``Case`` facade and a ``Diagnostic`` base class on top of these.
Nothing here changes the behaviour of the existing scripts; they keep working as-is.
"""

from .cluster import Cluster
from .datasource import DataSource

__all__ = ["DataSource", "Cluster"]
