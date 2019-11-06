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
                        default=[],
                        dest='delvars',
                        help='Delete specified variables from input data', 
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
                        help='Title of the simulation, included in metadata')
    parser.add_argument('--simname', 
                        help='Simulation name to include in the filename')
    parser.add_argument('--model-type', 
                        dest='modeltype',
                        help='Model type to include in the filename', 
                        default='')
    parser.add_argument('--timeformat', 
                        help='strftime format string for date fields in filename', 
                        default='%Y%m')
    parser.add_argument('--timeshift', 
                        help='Shift time axis by specified amount (in whatever units are used in the file). Default is to automatically shift current start date to time origin', 
                        const='auto', 
                        nargs='?')
    parser.add_argument('--usebounds', 
                        help='Use mid point of time bounds for time axis', 
                        action='store_true')
    parser.add_argument('--datefrombounds', 
                        help='Use time bounds for filename datestamp', 
                        action='store_true')
    parser.add_argument('--calendar', 
                        help='Specify calendar: will replace value of calendar attribute whereever it is found')
    parser.add_argument('-o','--outputdir', 
                        help='Output directory in which to store the data', 
                        default='.')
    parser.add_argument('--overwrite', 
                        help='Overwrite output file if it already exists', 
                        action='store_true')
    parser.add_argument('-cp','--copytimeunits', 
                        help='Copy time units from time variable to bounds', 
                        action='store_true')
    parser.add_argument('--makecoords', 
                        help='Create variable for any dimension without corresponding coordinate variable as per CF convention',
                        action='store_true')
    parser.add_argument('--engine', 
                        help='Back-end used to write output files (options are netcdf4 and h5netcdf)', 
                        default='netcdf4')
    parser.add_argument('--deflate', 
                        help='Deflate compression level', 
                        default=5, 
                        choices=range(0, 10))
    parser.add_argument('--filecachesize', 
                        help='Number of files xarray keeps in cache. For large datasets this may need to be set to a lower value to avoid excessive memory use (default=128)', 
                        type=int)
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

    if args.filecachesize:
        xarray.set_options(file_cache_maxsize=args.filecachesize)

    # Open first file in series to determine dependencies and variables
    # needed to load the full dataset. Don't specify delvars on open,
    # delete after
    ds = open_files(args.inputs[0], None, args.delvars)

    # Find the time coordinate. Will return the first one. Code doesn't
    # support multiple time axes
    try:
        timevar = findmatchingvars(ds, matchstrings=[' since '], coords_only=True)[0]
    except IndexError:
        print('No time coordinate found! Aborting')
        raise
    if verbose: print('Found time coordinate: {}'.format(timevar))

    # Add additional variables, such as grid information. Need to add
    # at this stage to properly determing dependencies
    ds = add_vars(ds, args.add, timevar)

    # Create a dictionary we can use to find dependent vars
    # for a given variable
    depvars = getdependents(ds)

    # Mapping from dependent variables back to variables which
    # depend on them
    is_dependent = dependentlookup(depvars)

    # Grab the list of variables required for output default to all 
    # data variables in the dataset if none specified
    variables = args.variables
    if variables is None:
        variables = set(ds.variables)
    else:
        variables = set(variables).intersection(set(ds.variables))
        # Add back in dependent variables. Loop over list(variables) as
        # variables is being modified
        for var in list(variables):
            variables.update(depvars[var])
    
    # Remove variables specified to be deleted. Useful for removing
    # variables which can then be updated globally, e.g. grid variables
    # that change during a run, but should be defined to be one value
    variables.difference_update(args.delvars)

    # Check encoding options
    if args.deflate > 0:
        encoding = { 'zlib': True, 'shuffle': True, 'complevel': args.deflate }
    else:
        encoding = {}

    # Open full dataset and exclude all variables that aren't
    # in vars
    ds = open_files(args.inputs, timevar, set(ds.variables).difference(variables), verbose, encoding)

    # Add auxiliary data
    ds = add_vars(ds, args.add, timevar)

    if verbose: 
        print('Opened source data:\n')
        print(ds)

    if args.simname:
        ds.attrs['simname'] = args.simname
    if 'simname' not in ds.attrs:
        ds.attrs['simname'] = 'simname'
    ds.attrs['simname'] = sanitise(ds.attrs['simname'])

    if args.title:
        ds.attrs['title'] = args.title
    if 'title' in ds.attrs:
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

    if args.timeshift:
        # Apply a timeshift to all variables with a time axis
        if args.timeshift == 'auto':
            if boundsvar is not None:
                shift = ds[boundsvar].values[0][0]
            else:
                shift = ds[timevar].values[0]
        else:
            shift = float(args.timeshift)
        for var in findmatchingvars(ds, matchstrings=[' since ']):
            ds[var] = ds[var].copy(data = (ds[var].values[:] - shift))
            
    if args.usebounds:
        # Replace time variable with the average of the time bounds. Useful
        # for time variables that are defined at the end of a month, rather
        # than the middle 
        if 'bounds' in ds[timevar].attrs:
            boundsvar = ds[timevar].attrs['bounds']
            newtime = [(e.values - b.values)//2 + b.values for (b,e) in ds[boundsvar]]
            ds[timevar] = ds[timevar].copy(data = newtime)

    if args.makecoords:
        # Loop over all dimensions without coordinates and make a
        # variable that is the dimension indexed by itself
        for var in set(ds.dims.keys()).difference(set(ds.coords.keys())):
            ds[var] = xr.DataArray(ds[var], coords={var:ds[var]})   

    ds = xarray.decode_cf(ds)

    # Add all dependent variables to the skipvar list
    skipvars = set(args.skipvars + list(is_dependent.keys()))

    for var in splitbyvar(ds, args.variables, skipvars, verbose):
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
        # Drop any variables xarray has automatically added that are not
        # superfluous. Especially important to not get spurious/confusing 
        # coordinates
        dsbyvar = dsbyvar.drop(set(dsbyvar.variables).difference(varlist))
        if args.aggregate:
            dsbyvar = resamplebytime(dsbyvar, var, args.aggregate, timedim=timevar)
        for dsbytime in groupbytime(dsbyvar, freq=args.frequency, timedim=timevar):
            i += 1
            startdate = format_date(dsbytime[timevar].values[0], args.timeformat)
            enddate = format_date(dsbytime[timevar].values[-1], args.timeformat)
            if 'bounds' in dsbytime[timevar].attrs and args.datefrombounds:
                boundsvar = ds[timevar].attrs['bounds']
                startdate = format_date(dsbytime[boundsvar].values[0][0], args.timeformat)
                enddate = format_date(dsbytime[boundsvar].values[-1][1], args.timeformat)
            fname = '{name}_{simulation}_{fromdate}_{todate}.nc'.format(
                        name=name,
                        simulation=ds.attrs['simname'],
                        fromdate=startdate,
                        todate=enddate,
                     )
            fpath = os.path.join(outpath, fname)
            if os.path.exists(fpath) and not args.overwrite:
                print("Output file {} already exists, and --overwrite not enabled. Skipping".format(fpath))
                continue

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

            print(dsbytime)

            writevar(dsbytime, fpath, unlimited=timevar, engine=args.engine)
        if i == 0:
            # No data written, delete empty output directory
            os.rmdir(outpath)

if __name__ == '__main__':

    main_argv()
