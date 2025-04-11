# Generates plots (and animations) to quickly review boundary interactions and behavior

import numpy as np
import matplotlib.pyplot as plt
from mom6_tools.MOM6grid import MOM6grid
from mom6_tools.m6plot import chooseColorLevels,chooseColorMap,boundaryStats,myStats
from cartopy import crs as ccrs, feature as cfeature
import cartopy
import warnings
import os

def latlon_proj_plot(
  field, grid, ax=None,
  xlabel=None, xunits=None, ylabel=None, yunits=None,
  title='', suptitle='',
  clim=None, colormap=None, extend=None, centerlabels=False,
  nbins=None, landcolor=[.5,.5,.5], axis=None, add_cbar=True,
  figsize=[16,9], dpi=150, sigma=2., annotate=True,
  ignore=None, save=None, debug=False, show=False, logscale=False
):
        
    # Mask ignored values
    if ignore is not None: maskedField = np.ma.masked_array(field, mask=[field==ignore])
    else: maskedField = field.copy()
    
    # Diagnose statistics
    area_cell = grid['areacello']
    sMin, sMax, sMean, sStd, sRMS = myStats(maskedField, area_cell, debug=debug)
    
    # Choose colormap
    if nbins is None and (clim is None or len(clim)==2): nbins=35
    if colormap is None: colormap = chooseColorMap(sMin, sMax)
    if clim is None and sStd is not None:
      cmap, norm, extend = chooseColorLevels(sMean-sigma*sStd, sMean+sigma*sStd, colormap, clim=clim, nbins=nbins, extend=extend, logscale=logscale)
    else:
      cmap, norm, extend = chooseColorLevels(sMin, sMax, colormap, clim=clim, nbins=nbins, extend=extend, logscale=logscale)
    
    ## Set up figure and axis
    central_longitude = grid['geolon'].median(dim=['xh','yh']).values
    if ax is None:
        fig = plt.figure(dpi=dpi, figsize=figsize)
        ax = fig.add_subplot(1,1,1, projection = ccrs.Robinson(central_longitude=central_longitude))
    
    pm = ax.pcolormesh(grid.geolon, grid.geolat)
    
    
    







    