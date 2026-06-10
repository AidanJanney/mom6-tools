#!/usr/bin/env python
"""Run the surface diagnostic through the Case API (sfc-stream fields, no obs).

This is the object-oriented entry point: it builds a Case from a diag_config.yml and runs
the registered `surface` diagnostic, which computes the day-weighted time mean and monthly
climatology of the sfc-stream fields (tos, SSU, SSV, speed, and sea-surface height when
present as SSH or zos), writes a NetCDF to ncfiles/, and saves maps to PNG/SFC/.

Examples
--------
    # carib12 regional example (defaults to the config next to this script), serial:
    python run_surface.py

    # explicit config, date window, and 6 dask-jobqueue workers (needs PBS_ACCOUNT set):
    python run_surface.py /path/diag_config.yml -sd 0001-01-01 -ed 0025-12-31 -nw 6

Outputs land in the current working directory (PNG/, ncfiles/).
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")  # headless: save figures, never open a window

from mom6_tools import Case

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "diag_config.yml")


def main():
    parser = argparse.ArgumentParser(description="Run the surface diagnostic via Case.")
    parser.add_argument("config", nargs="?", default=DEFAULT_CONFIG,
                        help="Path to a diag_config.yml (default: the carib12 example "
                             "config next to this script).")
    parser.add_argument("-sd", "--start_date", default=None,
                        help="Start date (default: the Avg block in the config).")
    parser.add_argument("-ed", "--end_date", default=None,
                        help="End date (default: the Avg block in the config).")
    parser.add_argument("-nw", "--number_of_workers", type=int, default=0,
                        help="dask-jobqueue workers (default 0 = serial). For nw>0, set a "
                             "project account via the PBS_ACCOUNT environment variable.")
    parser.add_argument("--no-plot", action="store_true", help="Skip plotting.")
    parser.add_argument("--no-save", action="store_true", help="Skip writing NetCDF.")
    args = parser.parse_args()

    case = Case.from_config(args.config, start_date=args.start_date, end_date=args.end_date)
    case.summary()
    ds = case.surface(
        start_date=args.start_date,
        end_date=args.end_date,
        nw=args.number_of_workers,
        plot=not args.no_plot,
        save=not args.no_save,
    )
    print("\nResult:")
    print(ds)


if __name__ == "__main__":
    main()
