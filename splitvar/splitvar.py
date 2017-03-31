#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import argparse
import xarray
import pandas as pd
import itertools as it

def nested_groupby(dataarray, groupby):
    """From https://github.com/pydata/xarray/issues/324#issuecomment-265462343"""
    if len(groupby) == 1:
        return dataarray.groupby(groupby[0])
    else:
        return dataarray.groupby(groupby[0]).apply(nested_groupby_apply, groupby = groupby[1:], apply_fn = apply_fn)

def splitbytime(var, freq, timedim='time'):
    """Given an xarray variable, split into periods of time defined by freq
    """

    try:
        if pd.infer_freq(var.indexes[timedim]) < freq:
            raise ValueError("Frequency ({}) is higher than data ({}): not supported".format(freq,pd.infer_freq(var.indexes[timedim]) ))
    except:
        pass

    # Create a temporary pandas data frame with the extracted time dimension
    pdtime = pd.DataFrame(index=var.indexes[timedim])

    print(pdtime.index)
    print(pd.infer_freq(pdtime.index))

    # Use pandas time grouping to cycle through at freq, grabbing out
    # the start and end points to select out data we want
    for k, v in pdtime.groupby(pd.TimeGrouper(freq=freq)):
        print(k)
        s, e = [pdtime.index.get_loc(date) for date in v.index.values[[0,-1]]]
        yield var[s:e+1]

def splitbyvar(ds, freq):
    pass

def open_files(file_paths, freq):

    # try and catch decode_times issues
    ds = xarray.open_mfdataset(file_paths, engine='netcdf4', decode_times=False, mask_and_scale=True)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Split multiple netCDF files by time and variable")

    parser.add_argument("-v","--verbose", help="Verbose output", action='store_true')

    parser.add_argument("inputs", help="netCDF files or directories", nargs='+')
    args = parser.parse_args()

    open_files(args, freq='year')
    
