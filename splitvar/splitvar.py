#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import argparse
import xarray
import pandas as pd
import netCDF4 as nc
import cftime
from copy import deepcopy

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

def oldsplitbytime(var, freq, timedim='time'):
    """Given an xarray variable, split into periods of time defined by freq
    """

    import pdb; pdb.set_trace()
    # Check freq is greater than or equal to the frequency of the variable
    # (so delta is <)
    freq_delta = to_timedelta(freq) 
    varvals = var.indexes[timedim].values
    vardelta = pd.Timedelta(min(varvals[1:-1]-varvals[0:-2]))
    if (freq_delta < vardelta):
        # raise ValueError("Split frequency ({}) is higher than data frequency ({}): not supported".format(freq,strfdelta(vardelta,"{D}d {H}h {M}m {S}s")))
        raise ValueError("Split frequency ({}) is higher than data frequency ({}): not supported".format(freq,vardelta))

    if (type(var.indexes[timedim][0]) == cftime.DatetimeNoLeap):
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
    for k, v in pdtime.groupby(pd.Grouper(freq=freq)):
        s, e = v.index.values[[0,-1]]
        yield var.sel(time=slice(pd.Timestamp(s),pd.Timestamp(e)))

def splitbytime(var, freq, timedim='time'):
    """
    Given an xarray variable, split into periods of time defined by freq
    """
    for k, v in var.groupby(freq):
        yield v

def splitbyvar(ds,vars=None,skipvars=['time']):
    """
    Given an xarray variable, split into separate variables
    """
    if vars is None:
        vars = set(ds.data_vars)
    else:
        vars = set(vars).intersection(set(ds.data_vars))

    if skipvars is not None:
        for varname in skipvars:
            vars.discard(varname)
            vars.discard(varname.upper)
            vars.discard(varname.lower)


    for var in vars:
        yield var

def getdependentvars(ds, var, skip_attrs=['long_name', 'standard_name', 'name', 'description']):
    """
    Find other variables upon which var depends
    """
    depvars = set()
    # Cycle through all the variables to be selected
    # and check if they depend on any other variables
    for attr in ds[var].attrs:
        if attr in skip_attrs:
            continue
        for attvar in ds.data_vars:
            if attvar == var: 
                continue
            # print(var,attvar,attr,ds[var].attrs[attr])
            if attvar in ds[var].attrs[attr]:
                # Variable is mentioned in an attribute
                # so should also be copied 
                depvars.add(attvar)

    return list(depvars)

def genfilepath(var):
    """
    Generate a file "path" from the name of the variable 
    and it's frequency
    """

def writevar(var,filename):
    """
    Save variable to netcdf file
    """
    print('Saving data to {fname}'.format(fname=filename))
    var.to_netcdf(path=filename,format="NETCDF4_CLASSIC")

def open_files(file_paths, freq):

    # try and catch decode_times issues
    ds = xarray.open_mfdataset(file_paths, decode_cf=False, engine='netcdf4', mask_and_scale=True)

    for v in ds:
        if 'chunksizes' in ds[v].encoding:
            ds[v].chunk(ds[v].encoding['chunksizes'])

    return ds