#!/usr/bin/env python

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import warnings, os, yaml, argparse
import pandas as pd
import dask, intake
from datetime import datetime, date
from mom6_tools.m6toolbox import get_cluster
from dask.distributed import Client
from mom6_tools.m6toolbox import add_global_attrs, cime_xmlquery
from mom6_tools.m6toolbox import weighted_temporal_mean
from mom6_tools.m6plot import xycompare, xyplot
from mom6_tools.MOM6grid import MOM6grid
from distributed import Client
from mom6_tools.core import Cluster, Diagnostic
from mom6_tools.core.interactive import resolve

# Surface-stream fields the OO diagnostic always needs (present in both regional and
# global MOM6 output).  Sea-surface height is named differently across configurations
# (regional runs write ``SSH``; global runs write ``zos``), so it is picked up
# opportunistically rather than required.
_SFC_FIELDS = ['tos', 'SSU', 'SSV', 'speed']
_SSH_NAMES = ['SSH', 'zos']


class Surface(Diagnostic):
  """Time-mean and monthly climatology of ``sfc``-stream surface fields.

  For ``tos`` / ``SSU`` / ``SSV`` / ``speed`` (and sea-surface height when present, named
  either ``SSH`` or ``zos``) this computes the day-weighted time mean over the averaging
  window and a monthly climatology, returning them in one ``xarray.Dataset``.  The
  tracer-point scalars (tos, speed, height) are map-plotted; the staggered velocity
  components are saved but not plotted.  No observational comparison (that lived in the
  legacy ``surface.py`` and may return later).

  This is a fused diagnostic (compute and plot share one engine, :func:`_compute_surface`),
  so it overrides ``run``; ``compute`` runs the engine with plotting/saving off.
  """

  name = 'surface'
  requires = {'sfc': _SFC_FIELDS, 'static': None}

  def run(self, *, start_date=None, end_date=None, nw=0,
          plot='auto', save='auto', outdir='PNG/SFC/', ncdir='ncfiles', debug=False):
    do_plot = resolve(plot)
    do_save = resolve(save)
    sd = start_date if start_date else self.case.source.start_date
    ed = end_date if end_date else self.case.source.end_date
    if do_plot:
      os.makedirs(outdir, exist_ok=True)
    print('Casename is:', self.case.casename)
    print('Number of workers to be used:', nw)
    with Cluster(nw) as cl:
      ds_out = _compute_surface(self.case, sd, ed, parallel=cl.parallel,
                                savefigs=do_plot, outdir=outdir, debug=debug)
    if do_save:
      os.makedirs(ncdir, exist_ok=True)
      casename = self.case.casename if self.case.casename else ''
      fname = os.path.join(ncdir, str(casename) + '_surface.nc')
      print('Saving netCDF file:', fname)
      ds_out.to_netcdf(fname)
    return ds_out

  def compute(self, *, start_date=None, end_date=None, nw=0, debug=False):
    """Compute the surface dataset without plotting or saving (notebook-friendly)."""
    return self.run(start_date=start_date, end_date=end_date, nw=nw,
                    plot=False, save=False, debug=debug)


def _compute_surface(case, start_date, end_date, *, parallel=False, savefigs=True,
                     outdir='PNG/SFC/', debug=False):
  """Shared surface engine for both ``Case.surface`` and (future) the CLI.

  Returns an ``xarray.Dataset`` with ``mean_<var>`` (day-weighted time mean over
  ``[start_date, end_date]``) and ``<var>_climatology`` (monthly climatology) for each
  available field.  Data access goes through the Case's :class:`DataSource`; the
  matplotlib block is gated by ``savefigs`` so the dataset can be produced without side
  effects.
  """
  casename = case.casename if case.casename else ''
  grd = case.source.grid()

  print('Reading surface dataset...')
  startTime = datetime.now()
  ds = case.source.open('sfc', parallel=parallel)
  # The required fields are guaranteed present (enforced by requires); add sea-surface
  # height under whichever name this run used.
  fields = [v for v in _SFC_FIELDS if v in ds.variables]
  ssh_name = next((n for n in _SSH_NAMES if n in ds.variables), None)
  if ssh_name:
    fields.append(ssh_name)
  ds = ds.sel(time=slice(start_date, end_date))
  print('Time elapsed: ', datetime.now() - startTime)

  print('Computing time mean and monthly climatology for: {}'.format(fields))
  startTime = datetime.now()
  data = {}
  for var in fields:
    data['mean_' + var] = weighted_temporal_mean(ds, var).mean('time')
    data[var + '_climatology'] = ds[var].groupby('time.month').mean('time')
  ds_out = xr.Dataset(data).compute()
  print('Time elapsed: ', datetime.now() - startTime)

  attrs = {'start_date': start_date,
           'end_date': end_date,
           'casename': casename,
           'description': 'Surface-field time means and monthly climatologies',
           'module': os.path.basename(__file__)}
  add_global_attrs(ds_out, attrs)

  if savefigs:
    print('\n Plotting...')
    try:
      area = grd.area_t
    except AttributeError:
      area = grd.areacello
    # pcolormesh rejects non-finite coordinates, which land-block elimination leaves in
    # geolon/geolat; fill them from neighbours so plotting still works (the field stays
    # masked at those cells, so they are not drawn misleadingly).
    glon = _finite_coord(grd.geolon)
    glat = _finite_coord(grd.geolat)
    # Plot only the tracer-point scalar fields (velocities live on staggered points).
    plot_fields = [v for v in ['tos', 'speed'] + ([ssh_name] if ssh_name else [])
                   if 'mean_' + v in ds_out]
    for var in plot_fields:
      field = np.ma.masked_invalid(ds_out['mean_' + var].values)
      xyplot(field, glon, glat, area=area,
             save=outdir + str(casename) + '_' + var + '_mean.png',
             suptitle='{} mean'.format(var),
             title='{} {} to {}'.format(casename, start_date, end_date))

  return ds_out


def _finite_coord(a):
  """Return ``a`` with any NaNs filled from nearest neighbours (for plotting only).

  Grid coordinate arrays (geolon/geolat) can contain NaNs where land blocks were
  eliminated.  matplotlib's ``pcolormesh`` refuses non-finite coordinates, so we
  forward/back-fill along both axes.  Filled cells coincide with masked field values, so
  they do not appear in the figure; this only makes the coordinate mesh well-defined.
  """
  arr = np.asarray(a, dtype=float)
  if np.isfinite(arr).all():
    return arr
  df = pd.DataFrame(arr)
  df = df.ffill(axis=1).bfill(axis=1).ffill(axis=0).bfill(axis=0)
  return df.values


def parseCommandLine():
  """
  Parse the command line positional and optional arguments.
  This is the highest level procedure invoked from the very end of the script.
  """
  parser = argparse.ArgumentParser(description=
      '''
      Compute time-averages of surface variables (SST, SSS, SSU, SSV and MLD), and (when possible)
      compare results against observational datasets.
      ''',
  epilog='Written by Gustavo Marques (gmarques@ucar.edu).')
  parser.add_argument('diag_config_yml_path', type=str, help='''Full path to the yaml file  \
    describing the run and diagnostics to be performed.''')
  parser.add_argument('-sd','--start_date', type=str, default='',
                      help='''Start year to compute averages. Default is to use value set in diag_config_yml_path''')
  parser.add_argument('-ed','--end_date', type=str, default='',
                      help='''End year to compute averages. Default is to use value set in diag_config_yml_path''')
  parser.add_argument('-mld_obs','--mld_obs', type=str, default='mld-deboyer-2023-tx2_3v2',
                      help='''Name of the observation-based MLD dataset in the oce-catalog. Default is mld-deboyer-2023-tx2_3v2''')
  parser.add_argument('-nw','--number_of_workers',  type=int, default=0,
                      help='''Number of workers to use (default=0, serial job).''')
  parser.add_argument('-debug',   help='''Add priting statements for debugging purposes''', action="store_true")
  optCmdLineArgs = parser.parse_args()
  driver(optCmdLineArgs)

#-- This is where all the action happends, i.e., functions for each diagnostic are called.

def driver(args):
  nw = args.number_of_workers
  if not os.path.isdir('ncfiles'):
    print('Creating a directory to place netCDF files (ncfiles)... \n')
    os.system('mkdir ncfiles')

  # Read in the yaml file
  diag_config_yml = yaml.load(open(args.diag_config_yml_path,'r'), Loader=yaml.Loader)

  caseroot = diag_config_yml['Case']['CASEROOT']
  args.casename = cime_xmlquery(caseroot, 'CASE')
  DOUT_S = cime_xmlquery(caseroot, 'DOUT_S')
  if DOUT_S:
    OUTDIR = cime_xmlquery(caseroot, 'DOUT_S_ROOT')+'/ocn/hist/'
  else:
    OUTDIR = cime_xmlquery(caseroot, 'RUNDIR')

  args.savefigs = True; args.outdir = 'PNG/MOC/'
  print('Output directory is:', OUTDIR)
  print('Casename is:', args.casename)
  print('Number of workers: ', nw)

  # set avg dates + other params
  avg = diag_config_yml['Avg']
  if not args.start_date : args.start_date = avg['start_date']
  if not args.end_date : args.end_date = avg['end_date']
  args.sfc = args.casename+diag_config_yml['Fnames']['sfc']
  args.native = args.casename+diag_config_yml['Fnames']['native']
  args.static = args.casename+diag_config_yml['Fnames']['static']
  args.geom = args.casename+diag_config_yml['Fnames']['geom']
  args.label = diag_config_yml['Case']['SNAME']
  args.savefigs = True

  # read grid info
  geom_file = OUTDIR+'/'+args.geom
  if os.path.exists(geom_file):
    grd = MOM6grid(OUTDIR+'/'+args.static, geom_file)
  else:
    grd = MOM6grid(OUTDIR+'/'+args.static)

  parallel = False
  if nw > 1:
    parallel = True
    cluster = get_cluster()
    cluster.scale(args.number_of_workers)
    client = Client(cluster)

  print('Reading surface dataset...')
  startTime = datetime.now()

  def preprocess(ds):
    ''' Compute montly averages and return the dataset with variables'''
    variables = ['oml','mlotst','tos','SSH', 'SSU', 'SSV', 'speed']
    if 'time_bounds' in ds.variables:
      variables.append('time_bounds')
    elif 'time_bnds' in ds.variables:
      variables.append('time_bnds')
    for v in variables:
      if v not in ds.variables:
        ds[v] = xr.zeros_like(ds.SSH)
    return ds[variables]

  # load monthly means
  ds1 = xr.open_mfdataset(OUTDIR+'/'+args.native, parallel=parallel)
  # load daily means
  ds_daily = xr.open_mfdataset(OUTDIR+'/'+args.sfc, parallel=parallel)
  ds = preprocess(ds1)
  print('Time elasped: ', datetime.now() - startTime)

  print('Selecting data between {} and {}...'.format(args.start_date, args.end_date))
  startTime = datetime.now()
  ds = ds.sel(time=slice(args.start_date, args.end_date))
  ds_daily = ds_daily.sel(time=slice(args.start_date, args.end_date))
  print('Time elasped: ', datetime.now() - startTime)

  # load obs-based mld from oce-catalog
  catalog = intake.open_catalog(diag_config_yml['oce_cat'])
  mld_obs = catalog[args.mld_obs].to_dask()

  # MLD
  get_MLD(ds, 'mlotst', mld_obs, grd, args)

  # BLD
  get_BLD(ds, 'oml', grd, args)

  # SSH
  get_SSH(ds, ds_daily, 'SSH', grd, args)

  # Speed
  get_speed(ds, 'speed', grd, args)

  if parallel:
    print('\n Releasing workers...')
    client.close(); cluster.close()

  print('{} was run successfully!'.format(os.path.basename(__file__)))

  return

def get_speed(ds, var, grd, args):
  '''
  Compute sea surface speed climatology.
  '''

  #if args.savefigs:
  #  if not os.path.isdir('PNG/SPEED'):
  #    print('Creating a directory to place figures (PNG/SPEED)... \n')
  #    os.system('mkdir -p PNG/SPEED')

  print('Computing yearly means...')
  startTime = datetime.now()
  ds_ann =  weighted_temporal_mean(ds,var)
  print('Time elasped: ', datetime.now() - startTime)

  print('Computing time mean...')
  startTime = datetime.now()
  ds_mean = ds_ann.mean('time').compute()
  print('Time elasped: ', datetime.now() - startTime)

  print('Computing mean sea level climatology...')
  startTime = datetime.now()
  speed_month_clima = ds[var].groupby("time.month").mean('time').compute()
  print('Time elasped: ', datetime.now() - startTime)

  # Combine into a Dataset
  ds_out = xr.Dataset(
    {
        "mean_speed": ds_mean,
        "speed_climatology": speed_month_clima
    }
  )
  attrs = {'start_date': args.start_date,
           'end_date': args.end_date,
           'casename': args.casename,
           'description': 'Surface speed mean and climatology ',
           'module': os.path.basename(__file__)}
  add_global_attrs(ds_out,attrs)
  ds_out.to_netcdf('ncfiles/'+str(args.casename)+'_sfc_speed.nc')
  return

def get_SSH(ds1, ds2, var, grd, args):
  '''
  Compute sea surface height mean and variance climatology.
  ds1 is the monthly dataset and ds2 is the daily dataset
  '''
  print('Computing yearly means...')
  startTime = datetime.now()
  ds_ann =  weighted_temporal_mean(ds1,var)
  print('Time elasped: ', datetime.now() - startTime)

  print('Computing time mean...')
  startTime = datetime.now()
  ds_mean = ds_ann.mean('time').compute()
  print('Time elasped: ', datetime.now() - startTime)

  print('Computing mean sea level climatology...')
  startTime = datetime.now()
  ssh_month_clima = ds1[var].groupby("time.month").mean('time').compute()
  print('Time elasped: ', datetime.now() - startTime)

  print('Computing variance...')
  startTime = datetime.now()
  nt=int(np.size(ds2.time.values)/5.)
  # TODO: replace hard-coded zos below
  ssh_5day = ds2['zos'][:nt,:,:].resample(time="5D").mean(dim='time')
  ssh_bar=ssh_5day.mean('time')
  ssh_prime = ssh_5day - ssh_bar
  ssh_v=(ssh_prime**2).mean('time')
  print('Time elasped: ', datetime.now() - startTime)

  # Combine into a Dataset
  ds_out = xr.Dataset(
    {
        "mean_ssh": ds_mean,
        "ssh_variance": ssh_v,
        "ssh_climatology": ssh_month_clima
    }
  )

  attrs = {'start_date': args.start_date,
           'end_date': args.end_date,
           'casename': args.casename,
           'description': 'SSH mean, variance and mean climatology ',
           #'obs': 'AVISO',
           'module': os.path.basename(__file__)}
  add_global_attrs(ds_out,attrs)
  ds_out.to_netcdf('ncfiles/'+str(args.casename)+'_SSH.nc')


  return

def get_MLD(ds, var, mld_obs, grd, args):
  '''
  Calculate the monthly and seasonal (winter and summer) climatologies for
  Mixed Layer Depth (MLD) and compare the results with observational datasets.
  '''

  if args.savefigs:
    if not os.path.isdir('PNG/MLD'):
      print('Creating a directory to place figures (PNG/MLD)... \n')
      os.system('mkdir -p PNG/MLD')

  print('Computing monthly MLD climatology...')
  startTime = datetime.now()
  mld_model = ds[var].groupby("time.month").mean('time').compute()
  print('Time elasped: ', datetime.now() - startTime)

  # add lat/lon
  mld_model = mld_model.assign_coords({
    "latitude": (("yh", "xh"), grd.geolat),
    "longitude": (("yh", "xh"), grd.geolon)
  })

  attrs = {'start_date': args.start_date,
           'end_date': args.end_date,
           'casename': args.casename,
           'description': 'MLD monthly climatology (m)',
           'module': os.path.basename(__file__)}
  add_global_attrs(mld_model,attrs)
  mld_model.to_netcdf('ncfiles/'+str(args.casename)+'_MLD_monthly_clima.nc')

  try:
    area = grd.area_t
  except:
    area = grd.areacello

  fname = None
  if args.savefigs:
    print('\n Plotting...')

    # MLD monthly climatology
    fig = plt.figure(figsize=(15, 10))
    plot = mld_model.plot(
        x="longitude",
        y="latitude",
        col="month",
        col_wrap=4,
        cmap="viridis",
        robust=True,
        cbar_kwargs={
            "orientation": "horizontal",
            "pad": 0.05,
            "aspect": 40,
            "shrink": 0.8,
            "label": "MLD monthly climatology (m)"
        }
    )
    plt.suptitle('{}, from {} to {}'.format(args.label, args.start_date,
                args.end_date), fontsize=16, fontweight='bold')
    plt.subplots_adjust(top=0.93, bottom=0.26)
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_monthly_clima.png'
    plt.savefig(fname)

    # MLD monthly bias (model - obs)
    # Add a 'month' coordinate to 'reference'
    mld_obs_with_month = mld_obs.assign_coords(month=mld_model.month)
    mld_obs_monthly = mld_obs_with_month.groupby("month").mean(dim="time")
    bias = mld_model - mld_obs_monthly.mld
    # plot bias
    fig = plt.figure(figsize=(15, 10))
    plot = bias.plot(
        x="longitude",
        y="latitude",
        col="month",
        col_wrap=4,
        cmap="bwr",
        robust=True,
        cbar_kwargs={
            "orientation": "horizontal",
            "pad": 0.05,
            "aspect": 40,
            "shrink": 0.8,
            "label": "MLD monthly climatology bias [model - {}] (m)".format(args.mld_obs)
        }
    )
    plt.suptitle('{}, from {} to {}'.format(args.label, args.start_date,
                args.end_date), fontsize=16, fontweight='bold')
    plt.subplots_adjust(top=0.93, bottom=0.26)
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_monthly_clima_bias.png'
    plt.savefig(fname)

  # JFM, starting from 0
  months = [0,1,2]
  model_JFM = np.ma.masked_invalid(mld_model.isel(month=months).mean('month').values)
  obs_JFM = np.ma.masked_invalid(mld_obs.mld.isel(time=months).mean('time').values)
  obs_JFM = np.ma.masked_where(grd.wet == 0, obs_JFM)
  month = 'JFM'
  if args.savefigs:
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_'+str(month)+'.png'
    xycompare(model_JFM , obs_JFM, grd.geolon, grd.geolat, area=area,
            title1 = 'model, '+str(month),
            title2 = 'obs (deBoyer), '+str(month),
            suptitle=args.casename +', ' + str(args.start_date) + ' to ' + str(args.end_date),
            colormap=plt.cm.Spectral_r, dcolormap=plt.cm.bwr, clim = (0,1500), extend='max',
            save = fname)

  # JAS, starting from 0
  months = [6,7,8]
  model_JAS = np.ma.masked_invalid(mld_model.isel(month=months).mean('month').values)
  obs_JAS = np.ma.masked_invalid(mld_obs.mld.isel(time=months).mean('time').values)
  obs_JAS = np.ma.masked_where(grd.wet == 0, obs_JAS)
  month = 'JAS'
  if args.savefigs:
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_'+str(month)+'.png'
    xycompare(model_JAS , obs_JAS, grd.geolon, grd.geolat, area=area,
            title1 = 'model, '+str(month),
            title2 = 'obs (deBoyer), '+str(month),
            suptitle=args.casename +', ' + str(args.start_date) + ' to ' + str(args.end_date),
            colormap=plt.cm.Spectral_r, dcolormap=plt.cm.bwr, clim = (0,1500), extend='max',
            save = fname)

  # Winter, JFM (NH) and JAS (SH)
  model_winter = model_JAS.copy(); obs_winter = obs_JAS.copy()
  # find point closest to eq. and select data
  j = np.abs( grd.geolat[:,0] - 0. ).argmin()
  model_winter[j::,:] = model_JFM[j::,:]; obs_winter[j::,:] = obs_JFM[j::,:]
  # create dataarays
  model_winter_da = xr.DataArray(model_winter, dims=['yh','xh'],
                           coords={'yh' : grd.yh, 'xh' : grd.xh}).rename('MLD_winter')

  month = 'winter'
  attrs = {'start_date': args.start_date,
           'end_date': args.end_date,
           'casename': args.casename,
           'description': 'Winter MLD (m)',
           'module': os.path.basename(__file__)}
  add_global_attrs(model_winter_da,attrs)
  model_winter_da.to_netcdf('ncfiles/'+str(args.casename)+'_MLD_'+month+'.nc')
  if args.savefigs:
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_'+str(month)+'.png'
    xycompare(model_winter , obs_winter, grd.geolon, grd.geolat, area=area,
            title1 = 'model, JFM (NH), JAS (SH)',
            title2 = 'obs (deBoyer), JFM (NH), JAS (SH)',
            suptitle=args.casename +', ' + str(args.start_date) + ' to ' + str(args.end_date),
            colormap=plt.cm.Spectral_r, dcolormap=plt.cm.bwr, clim = (0,1500), extend='max',
            save = fname)

  if args.savefigs:
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_model_'+str(month)+'.png'
    xyplot(model_winter, grd.geolon, grd.geolat, area=area,
         save=fname,
         suptitle=ds[var].attrs['long_name'] +' ['+ ds[var].attrs['units']+']', clim=(0,1500),
         title=str(args.casename) + ' ' +str(args.start_date) + ' to '+ str(args.end_date) + \
              ' JFM (NH), JAS (SH)')

  # Summer, JFM (SH) and JAS (NH)
  model_summer = model_JAS.copy(); obs_summer = obs_JAS.copy()
  model_summer[0:j,:] = model_JFM[0:j,:]; obs_summer[0:j,:] = obs_JFM[0:j,:]
  # create dataarays
  model_summer_da = xr.DataArray(model_summer, dims=['yh','xh'],
                           coords={'yh' : grd.yh, 'xh' : grd.xh}).rename('MLD_summer')

  month = 'summer'
  attrs['description'] = 'Summer MLD (m)'
  add_global_attrs(model_summer_da,attrs)
  model_summer_da.to_netcdf('ncfiles/'+str(args.casename)+'_MLD_'+month+'.nc')
  if args.savefigs:
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_'+str(month)+'.png'
    xycompare(model_summer , obs_summer, grd.geolon, grd.geolat, area=area,
            title1 = 'model, JFM (SH), JAS (NH)',
            title2 = 'obs (deBoyer), JFM (SH), JAS (NH)',
            suptitle=args.casename +', ' + str(args.start_date) + ' to ' + str(args.end_date),
            colormap=plt.cm.Spectral_r, dcolormap=plt.cm.bwr, clim = (0,150), extend='max',
            save = fname)

  if args.savefigs:
    fname = 'PNG/MLD/'+str(args.casename)+'_MLD_model_'+str(month)+'.png'
    xyplot(model_summer, grd.geolon, grd.geolat, area=area,
         save=fname,
         suptitle=ds[var].attrs['long_name'] +' ['+ ds[var].attrs['units']+']', clim=(0,150),
         title=str(args.casename) + ' ' +str(args.start_date) + ' to '+ str(args.end_date) + \
              ' JFM (SH), JAS (NH)')
  return

def get_BLD(ds, var, grd, args):
  '''
  Compute and save surface BLD climatology.
  '''
  if args.savefigs:
    if not os.path.isdir('PNG/BLD'):
      print('Creating a directory to place figures (PNG/BLD)... \n')
      os.system('mkdir -p PNG/BLD')

  print('Computing monthly BLD climatology...')
  startTime = datetime.now()
  bld_model = ds[var].groupby("time.month").mean('time').compute()
  print('Time elasped: ', datetime.now() - startTime)

  # fix month values using pandas. We just want something that xarray understands
  #bld_model['month'] = pd.date_range('2000-01-15', '2001-01-01',  freq='2SMS')

  # add lat/lon
  bld_model = bld_model.assign_coords({
    "latitude": (("yh", "xh"), grd.geolat),
    "longitude": (("yh", "xh"), grd.geolon)
  })

  attrs = {'start_date': args.start_date,
           'end_date': args.end_date,
           'casename': args.casename,
           'description': 'BLD monthly climatology (m)',
           'module': os.path.basename(__file__)}
  add_global_attrs(bld_model,attrs)
  bld_model.to_netcdf('ncfiles/'+str(args.casename)+'_BLD_monthly_clima.nc')

  try:
    area = grd.area_t
  except:
    area = grd.areacello

  fname = None
  if args.savefigs:
    print('\n Plotting...')

    # BLD monthly climatology
    fig = plt.figure(figsize=(15, 10))
    plot = bld_model.plot(
        x="longitude",
        y="latitude",
        col="month",
        col_wrap=4,
        cmap="viridis",
        robust=True,
        cbar_kwargs={
            "orientation": "horizontal",
            "pad": 0.05,
            "aspect": 40,
            "shrink": 0.8,
            "label": "BLD monthly climatology (m)"
        }
    )
    plt.suptitle('{}, from {} to {}'.format(args.label, args.start_date,
                args.end_date), fontsize=16, fontweight='bold')
    plt.subplots_adjust(top=0.93, bottom=0.26)
    fname = 'PNG/BLD/'+str(args.casename)+'_BLD_monthly_clima.png'
    plt.savefig(fname)

  # March and Sep, noticed starting from 0
  months = [2,8]
  fname = None
  for t in months:
    month = date(1900, t+1, 1).strftime('%B')
    if args.savefigs:
      fname = 'PNG/BLD/'+str(args.casename)+'_BLD_model_'+str(month)+'.png'
    model = np.ma.masked_invalid(bld_model[t,:].values)
    xyplot(model, grd.geolon, grd.geolat, area=area,
           save=fname,
           suptitle=ds[var].attrs['long_name'] +' ['+ ds[var].attrs['units']+']', clim=(0,1500),
           title=str(args.casename) + ' ' +str(args.start_date) + ' to '+ str(args.end_date))

  # JFM, starting from 0
  months = [0,1,2]
  model_JFM = np.ma.masked_invalid(bld_model.isel(month=months).mean('month').values)
  month = 'JFM'
  # JAS, starting from 0
  months = [6,7,8]
  model_JAS = np.ma.masked_invalid(bld_model.isel(month=months).mean('month').values)
  month = 'JAS'

  # Winter, JFM (NH) and JAS (SH)
  model_winter = model_JAS.copy()
  # find point closest to eq. and select data
  j = np.abs( grd.geolat[:,0] - 0. ).argmin()
  model_winter[j::,:] = model_JFM[j::,:]
  # create dataarays
  model_winter_da = xr.DataArray(model_winter, dims=['yh','xh'],
                           coords={'yh' : grd.yh, 'xh' : grd.xh}).rename('BLD_winter')

  month = 'winter'
  attrs = {'start_date': args.start_date,
           'end_date': args.end_date,
           'casename': args.casename,
           'description': 'Winter MLD (m)',
           'module': os.path.basename(__file__)}
  add_global_attrs(model_winter_da,attrs)
  model_winter_da.to_netcdf('ncfiles/'+str(args.casename)+'_BLD_'+month+'.nc')

  if args.savefigs:
    fname = 'PNG/BLD/'+str(args.casename)+'_BLD_model_'+str(month)+'.png'
  xyplot(model_winter, grd.geolon, grd.geolat, area=area,
         save=fname,
         suptitle=ds[var].attrs['long_name'] +' ['+ ds[var].attrs['units']+']', clim=(0,1500),
         title=str(args.casename) + ' ' +str(args.start_date) + ' to '+ str(args.end_date) + \
              ' JFM (NH), JAS (SH)')

  # Summer, JFM (SH) and JAS (NH)
  model_summer = model_JAS.copy()
  model_summer[0:j,:] = model_JFM[0:j,:]
  # create dataarays
  model_summer_da = xr.DataArray(model_summer, dims=['yh','xh'],
                           coords={'yh' : grd.yh, 'xh' : grd.xh}).rename('BLD_summer')

  month = 'summer'
  attrs['description'] = 'Summer BLD (m)'
  add_global_attrs(model_summer_da,attrs)
  model_summer_da.to_netcdf('ncfiles/'+str(args.casename)+'_BLD_'+month+'.nc')

  if args.savefigs:
    fname = 'PNG/BLD/'+str(args.casename)+'_BLD_model_'+str(month)+'.png'
  xyplot(model_summer, grd.geolon, grd.geolat, area=area,
         save='PNG/BLD/'+str(args.casename)+'_BLD_model_'+str(month)+'.png',
         suptitle=ds[var].attrs['long_name'] +' ['+ ds[var].attrs['units']+']', clim=(0,150),
         title=str(args.casename) + ' ' +str(args.start_date) + ' to '+ str(args.end_date) + \
              ' JFM (SH), JAS (NH)')
  return
# Invoke parseCommandLine(), the top-level prodedure
if __name__ == '__main__': parseCommandLine()

