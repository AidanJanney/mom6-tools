"""The :class:`Diagnostic` base class.

A diagnostic is a small object bound to a :class:`~mom6_tools.core.case.Case`.  It
declares which model streams/variables it needs (``requires``) and implements its science
in ``compute``; the base class adds a uniform ``run`` that applies the plot/save policy
(see :mod:`mom6_tools.core.interactive`) and returns a mutable ``xarray`` result.

Two patterns are supported:

* **Separable diagnostics** implement ``compute`` / ``plot`` / ``save`` and inherit the
  default ``run``, which calls them in order while honouring the policy.
* **Fused diagnostics** (where computation and plotting are intertwined, like the
  meridional overturning) override ``run`` directly.  ``compute`` should still return the
  data-only result so notebook users can get an ``xarray`` object without side effects.

This stays deliberately small; the goal is a shared shape for the scripts, not a framework.
"""

from .interactive import resolve

__all__ = ["Diagnostic"]


class Diagnostic:
    """Base class for a single diagnostic.

    Attributes
    ----------
    name : str
        Short registry name (e.g. ``"moc"``).
    requires : dict
        Maps stream name -> list of variables (or ``None`` for "the whole stream"),
        documenting what the diagnostic opens from the :class:`DataSource`.
    """

    name: str = None
    requires: dict = {}

    def __init__(self, case):
        self.case = case

    # -- to be implemented by subclasses ----------------------------------------

    def compute(self, **kwargs):
        """Compute the diagnostic and return a mutable ``xarray`` result."""
        raise NotImplementedError(f"{type(self).__name__}.compute() is not implemented")

    def plot(self, result, **kwargs):
        """Render figures for ``result`` (and save them)."""
        raise NotImplementedError(f"{type(self).__name__}.plot() is not implemented")

    def save(self, result, **kwargs):
        """Write ``result`` to disk (typically NetCDF under ``ncfiles/``)."""
        raise NotImplementedError(f"{type(self).__name__}.save() is not implemented")

    # -- default orchestration --------------------------------------------------

    def run(self, *, plot="auto", save="auto", **kwargs):
        """Compute, then optionally plot and save, returning the result.

        ``plot`` and ``save`` accept ``True``/``False``/``"auto"`` (see
        :func:`mom6_tools.core.interactive.resolve`).
        """
        result = self.compute(**kwargs)
        if resolve(plot):
            self.plot(result)
        if resolve(save):
            self.save(result)
        return result
