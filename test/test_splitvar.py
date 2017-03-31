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
import six
import itertools as it

# Find the python libraries we're testing
sys.path.append('..')
sys.path.append('.')

from splitvar import splitbytime

verbose = True

def test_splitbytime():

    testfile = 'test/ocean_scalar.nc'
    ds = xr.open_dataset(testfile,decode_times=False)
    ds['time'] = nc.num2date(ds.time, 'days since 1678-01-01 00:00:00', 'noleap')
    
    for var in splitbytime(ds['ke_tot'],'MS'):
        print(var.shape[0])
        print(var)

    
    np.random.seed(123)

    times = pd.date_range('2000-02-23', '2003-09-13', name='time')
    annual_cycle = np.sin(2 * np.pi * (times.dayofyear / 365.25 - 0.28))
    
    base = 10 + 15 * annual_cycle.reshape(-1, 1)
    tmin_values = base + 3 * np.random.randn(annual_cycle.size, 3)
    tmax_values = base + 10 + 3 * np.random.randn(annual_cycle.size, 3)
    
    ds = xr.Dataset({'tmin': (('time', 'location'), tmin_values),
                    'tmax': (('time', 'location'), tmax_values)},
                    {'time': times, 'location': ['IA', 'IN', 'IL']})

    # Annual
    groupsizes = [344, 365, 365, 225]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in it.izip(splitbytime(ds['tmin'],'12MS'),groupsizes):
        assert(var.shape[0] == size)

    # Bi-annual
    groupsizes = [709, 590]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in it.izip(splitbytime(ds['tmin'],'24MS'),groupsizes):
        assert(var.shape[0] == size)

    # Monthly
    groupsizes = [7, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 13]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in it.izip(splitbytime(ds['tmin'],'1MS'),groupsizes):
        assert(var.shape[0] == size)

    # 6 monthly
    groupsizes = [160, 184, 181, 184, 181, 184, 181, 44]
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in it.izip(splitbytime(ds['tmin'],'6MS'),groupsizes):
        assert(var.shape[0] == size)

    # 5 daily
    groupsizes = 5*np.ones(ds.tmin.shape[0]/5,np.int)
    groupsizes = np.append(groupsizes,int(ds.tmin.shape[0] - 5*len(groupsizes)))
    assert(sum(groupsizes) == ds.tmin.shape[0])
    for var, size in it.izip(splitbytime(ds['tmin'],'5D'),groupsizes):
        assert(var.shape[0] == size)

    # Check exception is raised if frequency is higher than that in the data
    with pytest.raises(ValueError):
        for var in splitbytime(ds['tmin'],'H'):
            pass

