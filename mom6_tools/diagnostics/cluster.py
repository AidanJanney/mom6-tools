"""A small context manager around the shared dask-cluster helper.

The existing scripts call :func:`mom6_tools.m6toolbox.request_workers` directly and then
remember to tear the cluster down at the end of ``main()``.  :class:`Cluster` wraps that
same helper so the setup/teardown can be expressed as a ``with`` block instead, which is
easier to use correctly from the new object-oriented code and from notebooks::

    from mom6_tools.diagnostics import Cluster

    with Cluster(nw=6) as cl:
        ds = source.open("z", variables=["vmo"], parallel=cl.parallel)
        ...  # compute while the workers are alive

The behaviour for each ``nw`` value is identical to ``request_workers``: ``nw > 0``
requests an ``NCARCluster`` (and degrades gracefully to serial if the cluster modules are
unavailable), while ``nw <= 0`` runs serially.
"""

from mom6_tools.m6toolbox import request_workers

__all__ = ["Cluster"]


class Cluster:
    """Context manager that requests dask workers and cleans them up on exit.

    Parameters
    ----------
    nw : int
        Number of workers to request.  ``nw <= 0`` runs serially (no cluster).

    Attributes
    ----------
    parallel : bool
        ``True`` if a cluster was started; pass this to
        :meth:`DataSource.open(..., parallel=...) <mom6_tools.diagnostics.datasource.DataSource.open>`.
    cluster, client
        The ``NCARCluster`` and ``Client`` objects, or ``None`` when running serially.
    """

    def __init__(self, nw: int = 0):
        self.nw = nw
        self.parallel = False
        self.cluster = None
        self.client = None

    def start(self) -> "Cluster":
        """Request the workers.  Returns ``self`` so it can be chained."""
        self.parallel, self.cluster, self.client = request_workers(self.nw)
        return self

    def close(self) -> None:
        """Close the client and cluster if they were started.  Safe to call twice."""
        if self.client is not None:
            self.client.close()
            self.client = None
        if self.cluster is not None:
            self.cluster.close()
            self.cluster = None
        self.parallel = False

    def __enter__(self) -> "Cluster":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
