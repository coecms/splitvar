#!/usr/bin/env python3

from __future__ import print_function

import argparse
from collections import defaultdict
import os
import re

import cftime
import networkx
import numpy as np
import pandas as pd
import sys
import xarray

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

def groupbytime(var, freq, timedim='time'):
    """
    Given an xarray variable, split into periods of time defined by freq
    """
    try:
        for k, v in var.resample({timedim: freq}):
            # copyattr(var,v)
            v.attrs.update(var.attrs)
            yield v
    except KeyError:
        return

def find_bounds(var, dim=None, **kwargs):
    """
    Return a bounds variable that encompasses the bounds of entire var. 
    Used after resample to return bounds of a resampled variable.  
    """

    if len(var.shape) > 1:
        try:
            # Grab the first bounds and replace the end of the bounds with the
            # second value in the last bounds
            boundingvar = var[0]
            boundingvar[1] = var[-1][1]
        except:
            boundingvar = var
    else:
        try:
            # Grab the first bounds and replace the end of the bounds with the
            # second value in the last bounds
            boundingvar = var[-1]
        except:
            boundingvar = var

    return boundingvar

def sum_timedelta(var, dim=None, **kwargs):
    """
    When resampling a time delta need to sum all the individual periods
    """
    if dim is not None:
        axis = var.get_axis_num(dim)
        return var.sum(axis=axis)

    return var.sum()

def get_time_type(var):
    """
    Inspect a variable and return it's time type, which can be either
    None: not a time variable
    'datetime': is a date/time variable
    'delta': is a timedelta variable
    """
    vartype = str(type(var.values.ravel()[0]))
    if 'time' in vartype:
        if 'delta' in vartype:
            return 'delta'
        else:
            return 'datetime'
    else:
        return None

def resamplebytime(ds, var, freq, timedim='time', function=np.mean, copyattrs=True):
    """
    Given an xarray dataset, split into periods of time defined by freq
    Major variable is var, others are dependent variables which will be
    inspected for appropriate reduction methods
    """

    # applied = (funcs[i](v) for i, v in enumerate(resampler._iter_grouped()))
    all = []
    for  v in ds:
        # Inspect variables to determine most appropriate function
        timetype = get_time_type(ds[v])
        if timetype == 'delta':
            func = sum_timedelta
        elif timetype == 'datetime':
            func = find_bounds 
        else:
            func = function

        print(v,func)
        # resampler = ds[v].resample({timedim: freq})
        applied = []
        for dsg in ds[v].resample({timedim: freq}).reduce(func,dim=timedim):
            print(dsg)
            applied.append(dsg)
        all.append(xarray.concat(applied, dim=timedim))

    combined = xarray.merge(all)

    if copyattrs:
        for v in list(combined.data_vars) + list(combined.coords):
            combined[v].attrs.update(ds[v].attrs)
            combined[v].encoding.update(ds[v].encoding)

    return combined

def splitbyvar(ds, vars=None, skipvars=['time'], verbose=False):
    """
    Given an xarray variable, split into separate variables
    """
    if vars is None:
        vars = set(ds.data_vars)
    newvars = set(vars).intersection(set(ds.data_vars))

    if skipvars is not None:
        for varname in skipvars:
            newvars.discard(varname)
            newvars.discard(varname.upper)
            newvars.discard(varname.lower)

    if verbose: 
        print("Splitting by variable, skipping: {}".format(newvars.difference(vars)))

    for var in newvars:
        yield var

def getdependents(ds, skip_attrs=['long_name', 'standard_name', 'name', 'description']):
    """
    Find all dependencies in dataset. Return dict with varnames as keys and dependent 
    variable names in value array
    """
    depends = {}
    skipset = set(skip_attrs)

    G = networkx.DiGraph()

    G.add_nodes_from(ds.variables)

    r = re.compile('|'.join([r"\b{}\b".format(v) for v in ds.variables]), flags=re.I | re.X)

    for var in ds.variables:
        for attr in ds[var].attrs:
            if attr in skipset: continue
            try:
                match = r.findall(ds[var].attrs[attr])
                if match:
                    for vmatch in match:
                        G.add_edge(var,vmatch)
            except:
                pass

        for coord in ds[var].coords:
            G.add_edge(var,coord)

    for var in ds.data_vars:
        # depends[var] = getdependentvars(ds, var, skip_attrs)
        depends[var] = []
        for (node, deps) in networkx.algorithms.traversal.breadth_first_search.bfs_successors(G, var):
            depends[var].extend(deps)

    return depends

def dependentlookup(depends):
    """
    Generate a mapping from dependent variables back to variables on which they depend
    """
    lookup = defaultdict(list)
    for k, v in depends.items():
        for var in v:
            lookup[var].append(k)
    return lookup
        
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
        for attvar in list(ds.data_vars) + list(ds.coords):
            if attvar == var: 
                continue
            # Need to use a proper regex to search on word boundaries
            # to stop spurious matching with variables like "u" and "v"
            try:
                if re.search(r'\b'+attvar+r'\b', ds[var].attrs[attr]):
                    # Variable is mentioned in an attribute
                    # so should also be copied 
                    depvars.add(attvar)
            except TypeError:
                # Probably trying to match a number, so ignore
                pass

    depdepvars = set()
    for var in depvars:
        # One level of recursion to make sure we get all the 
        # dependencies of the variables/coordindates we just
        # found 
        depdepvars = depdepvars.union(getdependentvars(ds, var, skip_attrs))

    return list(depvars.union(depdepvars))

def genfilepath(var):
    """
    Generate a file "path" from the name of the variable 
    and it's frequency
    """

def writevar(var, filename, unlimited=None, engine='netcdf4'):
    """
    Save variable to netcdf file
    """
    print('Saving data to {fname}'.format(fname=filename))
    if unlimited is not None:
        if type(unlimited) is str:
            unlimited = [unlimited]
        var.to_netcdf(path=filename,format="NETCDF4", unlimited_dims=unlimited, engine=engine)
    else:
        var.to_netcdf(path=filename,format="NETCDF4", engine=engine)


def open_files(file_paths, concat_dim, delvars=None, verbose=False, encoding={}):

    def dropvars(ds):
        nonlocal delvars
        if delvars:
            delvars = set(delvars)
            # Select out only variables that are in the dataset
            delvars.intersection_update(set(ds.variables))
            try:
                ds = ds.drop_vars(delvars)
            except AttributeError:
                ds = ds.drop(delvars)
        return(ds)

    ds = xarray.open_mfdataset(file_paths, 
                               decode_cf=False, 
                               engine='netcdf4', 
                               data_vars='minimal',
                               preprocess=dropvars,
                               parallel=True,
                               concat_dim=concat_dim)

    if verbose and delvars is not None: 
        print('Deleted {} from dataset'.format(delvars))

    for v in ds:
        if 'chunksizes' in ds[v].encoding:
            ds[v] = ds[v].chunk(ds[v].encoding['chunksizes'])
        ds[v].encoding.update(encoding)

    return ds

def findmatchingvars(ds, att='units', matchstrings=[], ignorecase=True, coords_only=False):
    """
    Find variables with matching attributes
    """
    matchvars = []

    if ignorecase:
        transcase = lambda x: x
    else:
        transcase = lambda x: x.lower()

    vars = list(ds.coords)
    if not coords_only:
        vars = vars + list(ds.data_vars)

    for var in vars:
        if att in ds[var].attrs:
            for matchstring in matchstrings:
                if transcase(matchstring) in transcase(ds[var].attrs[att]):
                    matchvars.append(var)

    return matchvars

def add_vars(ds, fnames, timevar):

    for fname in fnames:
        print('Adding {}'.format(fname))
        add_ds = xarray.open_dataset(fname, decode_cf=False)
        if timevar in add_ds.coords:
            delvars = [timevar]
            for var in add_ds:
                if timevar in add_ds[var].dims:
                    delvars.append(var)
            print('Deleting following variables with a time dimension from {}: {}'.format(fname, delvars))
            add_ds = add_ds.drop(delvars)

        # Updating the additional dataset means vars from
        # ds take precedence. Definitely don't want time var
        # overwritten for example
        ds = xarray.merge([ds,add_ds])
    
    return ds

def make_added_ds(fnames, timevar):

    ds = xarray.Dataset()

    for fname in fnames:
        print('Adding {}'.format(fname))
        add_ds = xarray.open_dataset(fname, decode_cf=False)
        if timevar in add_ds.coords:
            delvars = [timevar]
            for var in add_ds:
                if timevar in add_ds[var].dims:
                    delvars.append(var)
            print('Deleting following variables with a time dimension from {}: {}'.format(fname, delvars))
            add_ds = add_ds.drop(delvars)

        # Updating the additional dataset means vars from
        # ds take precedence. Definitely don't want time var
        # overwritten for example
        ds = ds.combine_first(add_ds)

    return ds