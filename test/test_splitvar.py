#!/usr/bin/env python


"""
Copyright 2015 ARC Centre of Excellence for Climate Systems Science

author: Aidan Heerdegen <aidan.heerdegen@anu.edu.au>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""


from __future__ import print_function

import pytest
import sys
import os
import shutil
import subprocess
import shlex
import copy
import netCDF4 as nc
import xarray as xr
import pandas as pd
import numpy as np

from pandas.tseries.frequencies import to_offset

# Find the python libraries we're testing
sys.path.append('..')
sys.path.append('.')

from splitvar import *

verbose = True

def test_totimedelta():

    ## print(to_timedelta('1D'),pd.Timedelta('1 days'))
    ## print(to_timedelta('1MS'),pd.Timedelta('31 days'))
    ## print(to_timedelta('1M'),pd.Timedelta('28 days'))
    ## print(to_timedelta('1AS'),pd.Timedelta('365 days'))
    ## print(to_timedelta('1A'),pd.Timedelta('365 days'))

    assert(to_timedelta('1D') == pd.Timedelta('1 days'))
    # Because this routine calculates a times series from the
    # beginning of 1970, the result changes if the frequency
    # paramter is defined at the beginning or the end of the
    # month
    assert(to_timedelta('1MS') == pd.Timedelta('31 days'))
    assert(to_timedelta('1M') == pd.Timedelta('28 days'))
    assert(to_timedelta('1M') == pd.Timedelta('28 days'))
    # But there is no difference between 1A and 1AS, as there
    # is no difference in the number of days in 1970 and 1971
    assert(to_timedelta('1AS') == pd.Timedelta('365 days'))
    assert(to_timedelta('1A') == pd.Timedelta('365 days'))

    # Other frequencies like 1M and 1A don't convery to offsets
    # cleanly, which is why I wrote a local version of to_timedelta
    for freq in ['1D']:
        assert(pd.to_timedelta(to_offset(freq)) == to_timedelta(freq))

def test_splitbytime():

    testfile = 'test/ocean_scalar.nc'
    ds = xr.open_dataset(testfile,decode_times=False)
    ds['time'] = nc.num2date(ds.time, 'days since 1678-01-01 00:00:00', 'noleap')

    # for var in splitbytime(ds['ke_tot'],'12MS'):
    #     print(var.shape[0])
    #     print(var)

    np.random.seed(123)

    times = pd.date_range('2000-02-23', '2003-09-13 18:00:00', name='time', freq='1D')
    annual_cycle = np.sin(2 * np.pi * (times.dayofyear / 365.25 - 0.28))
    
    base = np.array(np.reshape(np.repeat(10 * 15 * annual_cycle, 3),(-1, 3)))
    # base = np.repeat(np.array(10 + 15 * np.repeat(annual_cycle)),3,axis=1)
    tmin_values = base + 3 * np.random.randn(annual_cycle.size, 3)
    tmax_values = base + 10 + 3 * np.random.randn(annual_cycle.size, 3)
    
    ds = xr.Dataset({'tmin': (('time', 'location'), tmin_values),
                    'tmax': (('time', 'location'), tmax_values)},
                    {'time': times, 'location': ['IA', 'IN', 'IL']})

    # Annual
    groupsizes = [344, 365, 365, 225]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in zip(splitbytime(ds['tmin'],'12MS'),groupsizes):
        assert(var.shape[0] == size)

    # Bi-annual
    groupsizes = [709, 590]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in zip(splitbytime(ds['tmin'],'24MS'),groupsizes):
        assert(var.shape[0] == size)

    # Monthly
    groupsizes = [7, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 13]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in zip(splitbytime(ds['tmin'],'1MS'),groupsizes):
        assert(var.shape[0] == size)

    # 6 monthly
    groupsizes = [160, 184, 181, 184, 181, 184, 181, 44]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in zip(splitbytime(ds['tmin'],'6MS'),groupsizes):
        assert(var.shape[0] == size)

    # 5 daily
    groupsizes = 5*np.ones(ds.tmin.shape[0]//5,np.int)
    groupsizes = np.append(groupsizes,int(ds.tmin.shape[0] - 5*len(groupsizes)))
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in zip(splitbytime(ds['tmin'],'5D'),groupsizes):
        assert(var.shape[0] == size)

    # Check exception is raised if frequency is higher than that in the data
    with pytest.raises(ValueError):
        for var in splitbytime(ds['tmin'],'H'):
            pass


    # Test sub-daily frequency

    times = pd.date_range('2000-02-23', '2003-09-13 18:00:00', name='time', freq='6H')
    annual_cycle = np.sin(2 * np.pi * (times.dayofyear / 365.25 - 0.28))
    
    # base = np.array(10 + 15 * np.reshape(annual_cycle,(-1, 1)))
    base = np.array(np.reshape(np.repeat(10 * 15 * annual_cycle, 3),(-1, 3)))
    tmin_values = base + 3 * np.random.randn(annual_cycle.size, 3)
    tmax_values = base + 10 + 3 * np.random.randn(annual_cycle.size, 3)
    
    ds = xr.Dataset({'tmin': (('time', 'location'), tmin_values),
                    'tmax': (('time', 'location'), tmax_values)},
                    {'time': times, 'location': ['IA', 'IN', 'IL']})

    # Annual
    groupsizes = np.array([344, 365, 365, 225]) * 4
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in zip(splitbytime(ds['tmin'],'12MS'),groupsizes):
        assert(var.shape[0] == size)

    # Monthly
    groupsizes = np.array([7, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 13]) * 4
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in zip(splitbytime(ds['tmin'],'1MS'),groupsizes):
        assert(var.shape[0] == size)
        # print(var.shape[0],size)

def test_splitbyvariable():

    testfile = 'test/ocean_scalar.nc'
    ds = xr.open_dataset(testfile,decode_times=False)
    ds['time'] = nc.num2date(ds.time, 'days since 1678-01-01 00:00:00', 'noleap')

    ds2 = ds['temp_global_ave']

    i = 0
    for var in splitbyvar(ds,['salt_global_ave','temp_global_ave']):
        print(var)
        for varbytime in splitbytime(ds[var],'24MS'):
            i += 1
            fname = "{}_{}.nc".format(var,i)
            print(varbytime.shape,fname)
            writevar(varbytime,fname)

def test_findmatchingvars():

    testfile = 'test/ocean_scalar.nc'
    ds = xr.open_dataset(testfile,decode_times=False)

    assert(sorted(findmatchingvars(ds, matchstrings=[' since ']))
                     == ['average_T1', 'average_T2', 'time'])


def test_getdependents():

    testfile = 'test/ocean_scalar.nc'
    ds = xr.open_dataset(testfile)

    depvars = getdependents(ds)
    is_dependent = dependentlookup(depvars)

    for k,v in depvars.items():
        if k in is_dependent:
            if k == 'time_bounds':
                assert(sorted(v) == ['nv', 'time'])
            else:
                assert(sorted(v) == ['nv', 'time', 'time_bounds'])
        else:
            # Non dependent vars should all have the same dependencies
            assert(sorted(v) == ['average_DT', 'average_T1', 'average_T2', 'nv', 'scalar_axis', 'time', 'time_bounds'])

