# Generates plots (and animations) to quickly review boundary interactions and behavior

import numpy as np
import matplotlib.pyplot as plt
from mom6_tools.MOM6grid import MOM6grid
from mom6_tools.m6plot import chooseColorLevels,chooseColorMap,boundaryStats,myStats,label
from cartopy import crs as ccrs, feature as cfeature
import cartopy
import warnings
import os

def latlon_proj_plot(
  field, grid, area_var = None,
  xlabel=None, xunits=None, ylabel=None, yunits=None,
  title='', suptitle='',
  clim=None, colormap=None, extend=None, centerlabels=False,
  nbins=None, axis=None, add_cbar=True,
  figsize=[16,9], dpi=150, sigma=2., annotate=True,
  ignore=None, save=None, debug=False, show=False, logscale=False,
  projection=None, coastlines = True, res = None, 
  coastcolor = [0,0,0], landcolor=[.75,.75,.75],
):
        
    # Mask ignored values
    if ignore is not None: maskedField = np.ma.masked_array(field, mask=[field==ignore])
    else: maskedField = np.ma.masked_array(field, mask=np.isnan(field)) # maskedField = field.copy()
    
    # Diagnose statistics
    if area_cell is None:
      area_cell = grid['areacello']#.to_numpy()
    sMin, sMax, sMean, sStd, sRMS = myStats(maskedField, area_cell, debug=debug)
    
    # Choose colormap
    if nbins is None and (clim is None or len(clim)==2): nbins=35
    if colormap is None: colormap = chooseColorMap(sMin, sMax)
    if clim is None and sStd is not None:
      cmap, norm, extend = chooseColorLevels(sMean-sigma*sStd, sMean+sigma*sStd, colormap, clim=clim, nbins=nbins, extend=extend, logscale=logscale)
    else:
      cmap, norm, extend = chooseColorLevels(sMin, sMax, colormap, clim=clim, nbins=nbins, extend=extend, logscale=logscale)
    
    ## Set up figure and axis
    if projection is None:
      central_longitude = grid['geolon'].median(dim=['xh','yh']).values
      projection = ccrs.Robinson(central_longitude=central_longitude)
    if axis is None:
      fig = plt.figure(dpi=dpi, figsize=figsize)
      axis = fig.add_subplot(1,1,1, projection = projection)
    
    ## Plot Color Mesh
    pm = axis.pcolormesh(grid.geolon, grid.geolat, field, cmap=cmap, norm=norm, transform=ccrs.PlateCarree())
    
    ## Add Land and Coastlines
    if res is None:
      res = '50m' # can be adjusted to estimate a best res between 10m, 50m, and 110m, also use other methods
    if coastlines:
      coasts = axis.coastlines(resolution=res, color = coastcolor)
    axis.set_facecolor(landcolor)
    
    ## Add the fancy bits
    if add_cbar: cb = plt.colorbar(pm, ax=axis, fraction=0.08, pad=0.02, extend=extend)
    if centerlabels and len(clim)>2: 
      if not add_cbar: raise ValueError("Argument Mismatch: add_cbar must be true if you also specify centerlabels to be true.")
      cb.set_ticks(  0.5*(clim[:-1]+clim[1:]) )
    
    ## Finish Up
    axis.set_facecolor(landcolor)
    # axis.set_xlim( xLims )
    # axis.set_ylim( yLims )
    
    if annotate:
      axis.annotate('max=%.5g\nmin=%.5g'%(sMax,sMin), xy=(0.0,1.01), xycoords='axes fraction', verticalalignment='bottom', fontsize=10)
      if area_cell is not None:
        axis.annotate('mean=%.5g\nrms=%.5g'%(sMean,sRMS), xy=(1.0,1.01), xycoords='axes fraction', verticalalignment='bottom', horizontalalignment='right', fontsize=10)
        axis.annotate(' sd=%.5g\n'%(sStd), xy=(1.0,1.01), xycoords='axes fraction', verticalalignment='bottom', horizontalalignment='left', fontsize=10)
    
    #if len(xlabel+xunits)>0: axis.set_xlabel(label(xlabel, xunits), fontsize=14)
    #if len(ylabel+yunits)>0: axis.set_ylabel(label(ylabel, yunits), fontsize=14)
    if len(title)>0: axis.set_title(title)
    if len(suptitle)>0: plt.suptitle(suptitle)
  
    if show: plt.show(block=False)
    if not show: plt.show(block=True)
    if save is not None: plt.savefig(save); plt.close()

    return pm
    







    