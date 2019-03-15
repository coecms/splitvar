'''
Copyright 2019 ARC Centre of Excellence for Climate Extremes

author: Aidan Heerdegen <aidan.heerdegen@anu.edu.au>

Licensed under the Apache License, Version 2.0 (the 'License');
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an 'AS IS' BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import argparse
import numpy as np
import sys
import xarray

from splitvar import *

def parse_args(args):

    parser = argparse.ArgumentParser(description='Split multiple netCDF files by time and variable')

    # parser.add_argument('-v','--verbose', help='Verbose output', action='store_true')
    parser.add_argument('-f','--frequency', 
                        help='Time frequency for output', 
                        default='time.year', 
                        action='store')
    parser.add_argument('-v','--variables', 
                        help='Only extract specified variables', 
                        action='append')
    parser.add_argument('-x','--x-variables', 
                        dest='skipvars',
                        help='Exclude specified variables', 
                        action='append')
    parser.add_argument('-d','--delattr', 
                        help='Delete specified global attributes', 
                        default=['filename'], 
                        action='append')
    parser.add_argument('-a','--add', 
                        help='Read in additional variables from these files', 
                        default=[], 
                        action='append')
    parser.add_argument('-s','--skipvars', 
                        help='Do not extract these variables', 
                        default=['time'], 
                        action='append')
    parser.add_argument('-t','--title', 
                        help='Title of the simulation, included in metadata', 
                        action='store')
    parser.add_argument('--simname', 
                        help='Simulation name to include in the filename', 
                        action='store')
    parser.add_argument('--model-type', 
                        dest='modeltype',
                        help='Model type to include in the filename', 
                        default='',
                        action='store')
    parser.add_argument('--timeformat', 
                        help='strftime format string for date fields in filename', 
                        default='%Y%m', 
                        action='store')
    parser.add_argument('-o','--outputdir', 
                        help='Output directory in which to store the data', 
                        default='.', 
                        action='store')
    parser.add_argument('inputs', help='netCDF files', nargs='+')

    return parser.parse_args(args)

def main_parse_args(args):
    '''
    Call main with list of arguments. Callable from tests
    '''
    # Must return so that check command return value is passed back to calling routine
    # otherwise py.test will fail
    return main(parse_args(args))

def main_argv():
    '''
    Call main and pass command line arguments. This is required for setup.py entry_points
    '''
    main_parse_args(sys.argv[1:])

def sanitise(string, replacements={'_' : '-'}):
    """
    Substitute characters that are used as separators in the pathname and other
    special characters if required
    """
    for c in replacements:
        string = string.replace(c, replacements[c])

    return string

def main(args):

    ds = open_files(args.inputs, freq=args.frequency)

    if args.simname:
        ds.attrs['simname'] = args.simname

    if 'simname' not in ds.attrs:
        ds.attrs['simname'] = 'simname'

    ds.attrs['simname'] = sanitise(ds.attrs['simname'])

    if args.title:
        ds.attrs['title'] = args.title

    if 'title' in ds.attrs:
        if ds.attrs['title'] is None:
            ds.attrs['title'] = ds.attrs['title']
        ds.attrs['title'] = sanitise(ds.attrs['title'])

    for fname in args.add:
        print('Adding {}'.format(fname))
        add_ds = xarray.open_dataset(fname, decode_cf=False)
        ds.update(add_ds)

    ds = xarray.decode_cf(ds)

    for var in splitbyvar(ds, args.variables, args.skipvars):
        i = 0
        print('Splitting {var} by time'.format(var=var))
        name = sanitise(var)
        outpath = os.path.normpath(os.path.join(args.outputdir, ds.simname, args.modeltype, name))
        try:
            os.makedirs(outpath)
        except FileExistsError:
            pass
        varlist = [var,] + getdependentvars(ds, var)
        dsbyvar = ds[varlist]
        for dsbytime in groupbytime(dsbyvar, args.frequency):
            i += 1
            # TODO: Do something a bit cleverer to identify time variable
            timevar = dsbytime.time
            startdate=timevar.values[0].strftime(args.timeformat)
            enddate=timevar.values[-1].strftime(args.timeformat)
            fname = '{name}_{simulation}_{fromdate}_{todate}.nc'.format(
                        name=name,
                        simulation=ds.attrs['simname'],
                        fromdate=startdate,
                        todate=enddate,
                     )
            dsbytime.attrs['time_coverage_start'] = startdate
            dsbytime.attrs['time_coverage_end'] = enddate

            dsbytime.attrs['geospatial_lat_min'] =  99999.
            dsbytime.attrs['geospatial_lat_max'] = -99999.
            for var in findmatchingvars(dsbytime, matchstrings=['degrees_N', 'degrees_north']):
                if var in dsbytime:
                    dsbytime.attrs['geospatial_lat_min'] = min(
                        dsbytime[var].min().values, dsbytime.attrs['geospatial_lat_min'])
                    dsbytime.attrs['geospatial_lat_max'] = max(
                        dsbytime[var].max().values, dsbytime.attrs['geospatial_lat_max'])

            dsbytime.attrs['geospatial_lon_min'] = 99999.
            dsbytime.attrs['geospatial_lon_max'] = -99999.
            for var in findmatchingvars(dsbytime, matchstrings=['degrees_E','degrees_east']):
                if var in dsbytime:
                    dsbytime.attrs['geospatial_lon_min'] = min(
                        dsbytime[var].min().values, dsbytime.attrs['geospatial_lon_min'])
                    dsbytime.attrs['geospatial_lon_max'] = max(
                        dsbytime[var].max().values, dsbytime.attrs['geospatial_lon_max'])

            for attr in list(dsbytime.attrs):
                try:
                    if abs(float(dsbytime.attrs[attr])) == 99999. :
                        del(dsbytime.attrs[attr])
                except:
                    pass

            for attr in args.delattr:
                try:
                    del(dsbytime.attrs[attr])
                except KeyError:
                    pass

            fpath = os.path.join(outpath, fname)
            writevar(dsbytime, fpath)
        if i == 0:
            # No data written, delete empty output directory
            os.rmdir(outpath)

if __name__ == '__main__':

    main_argv()
