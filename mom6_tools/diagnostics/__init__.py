"""Object-oriented core for mom6-tools (the ongoing refactor).

This subpackage holds the new building blocks that sit underneath the diagnostic
scripts:

* :class:`~mom6_tools.diagnostics.datasource.DataSource` - resolves a model-output
  *source* (a ``diag_config.yml``, a MOM6 ``diag_table``, or explicit files) to a
  uniform ``{stream -> dataset}`` interface, so diagnostics don't each re-implement
  path resolution and preprocessing.
* :class:`~mom6_tools.diagnostics.cluster.Cluster` - a small context manager around
  ``m6toolbox.request_workers`` for dask parallelism.

On top of these sit the :class:`Case` facade and the :class:`Diagnostic` base class:
``Case.from_config(...).moc(...)`` returns a mutable ``xarray`` result and auto-plots when
run non-interactively.  Nothing here changes the behaviour of the existing scripts; they
keep working as-is (each becomes a thin shim over the matching diagnostic as it migrates).
"""

from .base import Diagnostic
from .case import Case
from .cluster import Cluster
from .datasource import DataSource

__all__ = ["Case", "Diagnostic", "DataSource", "Cluster"]
