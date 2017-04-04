#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import argparse
import xarray
import pandas as pd
import itertools as it
import netCDF4 as nc

def nested_groupby(dataarray, groupby):
    """From https://github.com/pydata/xarray/issues/324#issuecomment-265462343"""
    if len(groupby) == 1:
        return dataarray.groupby(groupby[0])
    else:
        return dataarray.groupby(groupby[0]).apply(nested_groupby_apply, groupby = groupby[1:], apply_fn = apply_fn)

def to_timedelta(freq,start="01/01/1970"):
    """Hacky method to retrieve the delta associated with a frequency
    Can't use inbuilt pandas to_timedelta. Really only works for delta < 1 day
    We assume a start date of 1 Jan 1970, which is a non-leap year
    """
    tmprange = pd.date_range(start=start,periods=2,freq=freq)
    
    return tmprange[1]-tmprange[0]

def to_freq(delta):
    """Hacky method """
    pass

def splitbytime(var, freq, timedim='time'):
    """Given an xarray variable, split into periods of time defined by freq
    """

    # Check freq is greater than or equal to the frequency of the variable
    # (so delta is <)
    freq_delta = to_timedelta(freq) 
    varvals = var.indexes[timedim].values
    vardelta = pd.Timedelta(min(varvals[1:-1]-varvals[0:-2]))
    if (freq_delta < vardelta):
        # raise ValueError("Split frequency ({}) is higher than data frequency ({}): not supported".format(freq,strfdelta(vardelta,"{D}d {H}h {M}m {S}s")))
        raise ValueError("Split frequency ({}) is higher than data frequency ({}): not supported".format(freq,vardelta))

    if (type(var.indexes[timedim][0]) == nc.netcdftime._netcdftime.DatetimeNoLeap):
        # Variable is using a non-standard noleap calendar
        # Create a temporary pandas data frame with the start and end extracted time dimension
        # and the same frequency, but this has leap years (not an issue for what we will use this)
        pdtime = pd.DataFrame(index=pd.date_range(start=varvals[0]._to_real_datetime(),end=varvals[-1]._to_real_datetime(),freq=vardelta))
        # Change the time dimension to datetime so it can be sliced correctly
        var[timedim] = [d._to_real_datetime() for d in var.indexes[timedim].values]
    else:
        pdtime = pd.DataFrame(index=var.indexes[timedim])

    # Use pandas time grouping to cycle through at freq, grabbing out
    # the start and end points to select out data
    for k, v in pdtime.groupby(pd.TimeGrouper(freq=freq)):
        s, e = v.index.values[[0,-1]]
        yield var.sel(time=slice(pd.Timestamp(s),pd.Timestamp(e)))

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
    
