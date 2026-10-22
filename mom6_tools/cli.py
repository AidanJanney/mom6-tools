"""Shared argparse setup for the mom6_tools command-line scripts.

get_parser() returns a parser with the options most scripts have in common;
each script then adds its own arguments and calls parse_args().
"""

import argparse
from mom6_tools.jobqueue import add_jobqueue_args


def get_parser(description, epilog=None, config=True, dates=True, workers=True):
  '''Return an ArgumentParser with the shared mom6_tools options.

  Parameters
  ----------
  description, epilog : str
    Passed to argparse.ArgumentParser.
  config : bool
    Add the diag_config_yml_path positional argument.
  dates : bool
    Add -sd/--start_date and -ed/--end_date.
  workers : bool
    Add -nw/--number_of_workers and the dask-jobqueue flags from
    jobqueue.add_jobqueue_args().

  -debug is always added.
  '''
  parser = argparse.ArgumentParser(description=description, epilog=epilog)
  if config:
    parser.add_argument('diag_config_yml_path', type=str,
                        help='''Full path to the yaml file describing the run and diagnostics to be performed.''')
  if dates:
    parser.add_argument('-sd', '--start_date', type=str, default='',
                        help='''Start date to compute averages. Default is to use value set in the yaml file.''')
    parser.add_argument('-ed', '--end_date', type=str, default='',
                        help='''End date to compute averages. Default is to use value set in the yaml file.''')
  parser.add_argument('-debug', action='store_true',
                      help='''Add printing statements for debugging purposes.''')
  if workers:
    parser.add_argument('-nw', '--number_of_workers', type=int, default=0,
                        help='''Number of workers to use (default=0; 0 or 1 runs in serial).''')
    add_jobqueue_args(parser)
  return parser
