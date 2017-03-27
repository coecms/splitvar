#!/usr/bin/env python

import os
import sys
import argparse
import xarray

def splitbytime(var, timescale):
    pass

def splitbyvar(var, timescale):
    pass

def open_files(file_paths, timescale):

    # try and catch decode_times issues
    ds = xarray.open_mfdataset(file_paths, engine='netcdf4', decode_times=False, mask_and_scale=True)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Split multiple netCDF files by time and variable")

    parser.add_argument("-v","--verbose", help="Verbose output", action='store_true')

    parser.add_argument("inputs", help="netCDF files or directories", nargs='+')
    args = parser.parse_args()

    open_files(args, timescale='year')
    
