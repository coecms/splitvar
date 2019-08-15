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

    parser.add_argument('--verbose', 
                        help='Verbose output', 
                        action='store_true')
    parser.add_argument('-f','--frequency', 
                        help='Time period to group for output', 
                        default='Y', 
                        action='store')
    parser.add_argument('--aggregate', 
                        help='Apply mean in time, using pandas frequency notation e.g Y, 6M, 2Y', 
                        default=None,
                        action='store')
    # parser.add_argument('--function', 
    #                     help='Function to apply to aggregation', 
    #                     default='mean',
    #                     action='store')
    parser.add_argument('-v','--variables', 
                        help='Only extract specified variables', 
                        action='append')
    parser.add_argument('-x','--x-variables', 
                        dest='skipvars',
                        default=[],
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
    parser.add_argument('--timeshift', 
                        help='Shift time axis by specified amount (in whatever units are used in the file). Default is to automatically shift current start date to time origin', 
                        const='auto', 
                        nargs='?',
                        action='store')
    parser.add_argument('--usebounds', 
                        help='Use mid point of time bounds for time axis', 
                        action='store_true')
    parser.add_argument('--calendar', 
                        help='Specify calendar: will replace value of calendar attribute whereever it is found', 
                        action='store')
    parser.add_argument('-o','--outputdir', 
                        help='Output directory in which to store the data', 
                        default='.', 
                        action='store')
    parser.add_argument('-cp','--copytimeunits', 
                        help='Copy time units from time variable to bounds', 
                        action='store_true')
    parser.add_argument('--engine', 
                        help='Back-end used to write output files (options are netcdf4 and h5netcdf)', 
                        default='netcdf4', 
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

def main(args):

    verbose = args.verbose

    ds = open_files(args.inputs)

    if verbose: 
        print('Opened source data:\n')
        print(ds)

    # Find the time coordinate. Will return the first one. Code doesn't
    # support multiple time axes
    timevar = findmatchingvars(ds, matchstrings=[' since '], coords_only=True)[0]
    print('Found time coordinate: {}'.format(timevar))

    for fname in args.add:
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

    # Create a dictionary we can use to find dependent vars
    # for a given variable
    depvars = getdependents(ds)

    # Mapping from dependent variables back to variables which
    # depend on them
    is_dependent = dependentlookup(depvars)

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

    for attr in ['calendar', 'calendar_type']:
        if args.calendar:
            ds[timevar].attrs[attr] = args.calendar
        try:
            ds[timevar].attrs[attr] = ds[timevar].attrs[attr].lower()
        except:
            pass

    # In some cases the units in the time bounds is just 'days'
    # which leads to them being decoded as timedelta. Setting
    # this command line option will copy the units from time
    # into the bounds variable
    boundsvar = None
    if args.copytimeunits:
        if 'bounds' in ds[timevar].attrs:
            boundsvar = ds[timevar].attrs['bounds']
            ds[boundsvar].attrs['units'] = ds[timevar].attrs['units']

    alltimevars = findmatchingvars(ds, matchstrings=[' since '])

    if args.timeshift:
        if args.timeshift == 'auto':
            if boundsvar is not None:
                shift = ds[boundsvar].values[0][0]
            else:
                shift = ds[timevar].values[0]
        else:
            shift = float(args.timeshift)
        for var in alltimevars:
            ds[var] = ds[var].copy(data = (ds[var].values[:] - shift))
            
    if args.usebounds:
        if 'bounds' in ds[timevar].attrs:
            boundsvar = ds[timevar].attrs['bounds']
            newtime = [(e.values - b.values)//2 + b.values for (b,e) in ds[boundsvar]]
            ds[timevar] = ds[timevar].copy(data = newtime)

    ds = xarray.decode_cf(ds)

    # Add all dependent variables to the skipvar list
    skipvars = set(args.skipvars + list(is_dependent.keys()))

    for var in splitbyvar(ds, args.variables, skipvars):
        i = 0
        print('Splitting {var} by time'.format(var=var))
        name = sanitise(var)
        outpath = os.path.normpath(os.path.join(args.outputdir, ds.simname, args.modeltype, name))
        try:
            os.makedirs(outpath)
        except FileExistsError:
            pass
        varlist = [var,] + depvars[var]
        dsbyvar = ds[varlist]
        if args.aggregate:
            dsbyvar = resamplebytime(dsbyvar, var, args.aggregate, timedim=timevar)
        for dsbytime in groupbytime(dsbyvar, freq=args.frequency, timedim=timevar):
            i += 1
            startdate = format_date(dsbytime[timevar].values[0], args.timeformat)
            enddate = format_date(dsbytime[timevar].values[-1], args.timeformat)
            if 'bounds' in dsbytime[timevar].attrs:
                boundsvar = ds[timevar].attrs['bounds']
                startdate = format_date(dsbytime[boundsvar].values[0][0], args.timeformat)
                enddate = format_date(dsbytime[boundsvar].values[-1][1], args.timeformat)
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

            dsbytime.chunk({timevar: 1})

            print(dsbytime)

            fpath = os.path.join(outpath, fname)
            writevar(dsbytime, fpath, unlimited=timevar, engine=args.engine)
        if i == 0:
            # No data written, delete empty output directory
            os.rmdir(outpath)

if __name__ == '__main__':

    main_argv()
