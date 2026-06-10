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
requests a dask-jobqueue cluster (and degrades gracefully to serial if dask is
unavailable), while ``nw <= 0`` runs serially.  ``scheduler`` selects the dask-jobqueue
cluster type ('pbs' by default); any extra keyword arguments are forwarded to
:func:`mom6_tools.m6toolbox.get_cluster`.
"""

from mom6_tools.m6toolbox import request_workers

__all__ = ["Cluster"]


class Cluster:
    """Context manager that requests dask workers and cleans them up on exit.

    Parameters
    ----------
    nw : int
        Number of workers to request.  ``nw <= 0`` runs serially (no cluster).
    scheduler : str, optional
        dask-jobqueue cluster type: ``'pbs'`` (default), ``'slurm'``, ``'sge'`` or
        ``'lsf'``.
    **cluster_kwargs
        Forwarded to :func:`mom6_tools.m6toolbox.get_cluster` (e.g. ``account=``,
        ``memory=``, ``walltime=``).

    Attributes
    ----------
    parallel : bool
        ``True`` if a cluster was started; pass this to
        :meth:`DataSource.open(..., parallel=...) <mom6_tools.diagnostics.datasource.DataSource.open>`.
    cluster, client
        The dask-jobqueue cluster and ``Client`` objects, or ``None`` when running serially.
    """

    def __init__(self, nw: int = 0, scheduler: str = "pbs", **cluster_kwargs):
        self.nw = nw
        self.scheduler = scheduler
        self.cluster_kwargs = cluster_kwargs
        self.parallel = False
        self.cluster = None
        self.client = None

    def start(self) -> "Cluster":
        """Request the workers.  Returns ``self`` so it can be chained."""
        self.parallel, self.cluster, self.client = request_workers(
            self.nw, scheduler=self.scheduler, **self.cluster_kwargs)
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
