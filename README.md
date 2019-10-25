# splitvar

[![Build Status](https://travis-ci.org/coecms/splitvar.svg?branch=master)](https://travis-ci.org/coecms/splitvar)
[![codecov.io](http://codecov.io/github/coecms/splitvar/coverage.svg?branch=master)](http://codecov.io/github/coecms/splitvar?branch=master)

Split netCDF file into individual variables and by time, as defined by the user

## Install

A conda package is available in the coecms channel

    conda -c coecms install splitvar

Install directly from source

    git checkout git+https://github.com/coecms/splitvar
    cd splitvar
    pip install .

## Introduction

The data output from earth system models is usually not suitable for publication
as-is. Often this is because multiple variables are stored in a single file of a
long time span. When publishing data it is desirable to store a single model
diagnostic variable per file, and to limit the temporal span. This is so users of
the data can easily select only the data they need for the required time span. 
The servers responsible for web publishing have limits on the size and number of files
they are capable of serving.

`splitvar` is a python program which can be used in a publishing pipeline to split
aggregated model output into separate files by variale and time span. It examines
attributes to find any dependent variables.  

## Program Invocation

### Usage

`splitvar` is  a command line program. Invoking with `-h` prints the help output
explaining all the command line options:

    splitvar -h
    usage: splitvar [-h] [--verbose] [-f FREQUENCY] [--aggregate AGGREGATE]
                    [-v VARIABLES] [-x DELVARS] [-d DELATTR] [-a ADD]
                    [-s SKIPVARS] [-t TITLE] [--simname SIMNAME]
                    [--model-type MODELTYPE] [--timeformat TIMEFORMAT]
                    [--timeshift [TIMESHIFT]] [--usebounds] [--datefrombounds]
                    [--calendar CALENDAR] [-o OUTPUTDIR] [--overwrite] [-cp]
                    [--engine ENGINE] [--deflate {0,1,2,3,4,5,6,7,8,9}]
                    [--filecachesize FILECACHESIZE]
                    inputs [inputs ...]

    Split multiple netCDF files by time and variable

    positional arguments:
    inputs                netCDF files

    optional arguments:
    -h, --help            show this help message and exit
    --verbose             Verbose output
    -f FREQUENCY, --frequency FREQUENCY
                            Time period to group for output
    --aggregate AGGREGATE
                            Apply mean in time, using pandas frequency notation
                            e.g Y, 6M, 2Y
    -v VARIABLES, --variables VARIABLES
                            Only extract specified variables
    -x DELVARS, --x-variables DELVARS
                            Delete specified variables from input data
    -d DELATTR, --delattr DELATTR
                            Delete specified global attributes
    -a ADD, --add ADD     Read in additional variables from these files
    -s SKIPVARS, --skipvars SKIPVARS
                            Do not extract these variables
    -t TITLE, --title TITLE
                            Title of the simulation, included in metadata
    --simname SIMNAME     Simulation name to include in the filename
    --model-type MODELTYPE
                            Model type to include in the filename
    --timeformat TIMEFORMAT
                            strftime format string for date fields in filename
    --timeshift [TIMESHIFT]
                            Shift time axis by specified amount (in whatever units
                            are used in the file). Default is to automatically
                            shift current start date to time origin
    --usebounds           Use mid point of time bounds for time axis
    --datefrombounds      Use time bounds for filename datestamp
    --calendar CALENDAR   Specify calendar: will replace value of calendar
                            attribute whereever it is found
    -o OUTPUTDIR, --outputdir OUTPUTDIR
                            Output directory in which to store the data
    --overwrite           Overwrite output file if it already exists
    -cp, --copytimeunits  Copy time units from time variable to bounds
    --engine ENGINE       Back-end used to write output files (options are
                            netcdf4 and h5netcdf)
    --deflate {0,1,2,3,4,5,6,7,8,9}
                            Deflate compression level
    --filecachesize FILECACHESIZE
                            Number of files xarray keeps in cache. For large
                            datasets this may need to be set to a lower value to
                            avoid excessive memory use (default=128)

### Simple example

As an example, the file `ocean_daily.nc` contains 5 years of daily data from a 
1 degree global MOM5 ocean for the following variables

    ocean_daily.nc
    Time steps:  1826  x  1.0 days
    eta_t        :: (1826, 300, 360) :: surface height on T cells
    surface_temp :: (1826, 300, 360) :: Conservative temperature
    mld          :: (1826, 300, 360) :: mixed layer depth determined by density criteria

The following invocation of `splitvar`

    $ splitvar -cp -d title --calendar proleptic_gregorian --simname ACCESS-OM2 ocean_daily.nc

creates a directory called `ACCESS-OM2` (because the simulation name was specified with
the `--simname` option) and inside that directory are subdirectories named for all the
non-coordinate variables in the original file

    $ ls ACCESS-OM2/
    eta-t  mld  surface-temp

and within each subdirectory are files containing a single year of data for the respective
variable because the default frequency by which to group the data is by year, `Y`: 

    $ ls ACCESS-OM2/surface-temp/
    surface-temp_ACCESS-OM2_225301_225312.nc  surface-temp_ACCESS-OM2_225601_225612.nc
    surface-temp_ACCESS-OM2_225401_225412.nc  surface-temp_ACCESS-OM2_225701_225712.nc
    surface-temp_ACCESS-OM2_225501_225512.nc

`splitvar` has put the simulation name, start date and end date in the file name. This 
is to conform to standard naming procedures for published data.

The global attribute `title` was deleted using the `-d` option. The calendar for the 
time variable was also changed to `proleptic_gregorian`.

### Choosing variables

Specific variables can be extracted with the `-v` option. Use it multiple times to
specify more than one variable. To change the grouping frequency use the `-f` option,
and specify a pandas [date offset frequency string](https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#dateoffset-objects).

    $ splitvar -cp -d title --calendar proleptic_gregorian --simname ACCESS-OM2 -f 6MS -v     
      surface_temp -v mld ocean_daily.nc 

In this case only files for the two specified variables are produced:

    $ ls ACCESS-OM2/
    mld  surface-temp

and for each variable there are now ten files

    $ ls ACCESS-OM2/surface-temp/
    surface-temp_ACCESS-OM2_225301_225306.nc  surface-temp_ACCESS-OM2_225507_225512.nc
    surface-temp_ACCESS-OM2_225307_225312.nc  surface-temp_ACCESS-OM2_225601_225606.nc
    surface-temp_ACCESS-OM2_225401_225406.nc  surface-temp_ACCESS-OM2_225607_225612.nc
    surface-temp_ACCESS-OM2_225407_225412.nc  surface-temp_ACCESS-OM2_225701_225706.nc
    surface-temp_ACCESS-OM2_225501_225506.nc  surface-temp_ACCESS-OM2_225707_225712.nc

each containing six months of daily data

    ACCESS-OM2/surface-temp/surface-temp_ACCESS-OM2_225301_225306.nc
    Time steps:  181  x  1.0 days
    surface_temp :: (181, 300, 360) :: Conservative temperature

If there are a large number of variables to be extracted and only a few are *not* required
then it can be easier to specify the variables to skip, with the `-s` option, rather than 
all the variables to process.

### Aggregation

`splitvar` can also aggregate data on a specified time frequency by specifying an aggregate
frequency. For example, using the same command as above, but specifying monthly
aggregation

    $ splitvar -cp -d title --calendar proleptic_gregorian --simname ACCESS-OM2 -f 6MS -v surface_temp --aggregate M ocean_daily.nc

results in the same number of tiles, but each now only has six records, which is the
monthly average temperature

    ACCESS-OM2/surface-temp/surface-temp_ACCESS-OM2_225301_225306.nc
    Time steps:  6  x  28.0 days
    surface_temp :: (6, 300, 360) :: Conservative temperature

currently the only aggregation function available is mean.

### Multiple inputs

If multiple input files are specified on the command line they are concatenated together
and treated as a single dataset.

For example, from the same ACCESS-OM2 simulation the ice model outputs each month of monthly
data to a separate file

    iceh.2253-01.nc  iceh.2253-11.nc  iceh.2254-09.nc  iceh.2255-07.nc  iceh.2256-05.nc  iceh.2257-03.nc
    iceh.2253-02.nc  iceh.2253-12.nc  iceh.2254-10.nc  iceh.2255-08.nc  iceh.2256-06.nc  iceh.2257-04.nc
    iceh.2253-03.nc  iceh.2254-01.nc  iceh.2254-11.nc  iceh.2255-09.nc  iceh.2256-07.nc  iceh.2257-05.nc
    iceh.2253-04.nc  iceh.2254-02.nc  iceh.2254-12.nc  iceh.2255-10.nc  iceh.2256-08.nc  iceh.2257-06.nc
    iceh.2253-05.nc  iceh.2254-03.nc  iceh.2255-01.nc  iceh.2255-11.nc  iceh.2256-09.nc  iceh.2257-07.nc
    iceh.2253-06.nc  iceh.2254-04.nc  iceh.2255-02.nc  iceh.2255-12.nc  iceh.2256-10.nc  iceh.2257-08.nc
    iceh.2253-07.nc  iceh.2254-05.nc  iceh.2255-03.nc  iceh.2256-01.nc  iceh.2256-11.nc  iceh.2257-09.nc
    iceh.2253-08.nc  iceh.2254-06.nc  iceh.2255-04.nc  iceh.2256-02.nc  iceh.2256-12.nc  iceh.2257-10.nc
    iceh.2253-09.nc  iceh.2254-07.nc  iceh.2255-05.nc  iceh.2256-03.nc  iceh.2257-01.nc  iceh.2257-11.nc
    iceh.2253-10.nc  iceh.2254-08.nc  iceh.2255-06.nc  iceh.2256-04.nc  iceh.2257-02.nc  iceh.2257-12.nc

By using a pattern matching `glob` all the files can be passed to `splitvar`

    $ splitvar --simname ACCESS-OM2 --usebounds -v aice_m iceh.225*.nc

The dates in the time coordinate in the ice data file are the value of end time bound 
of the month, which is actually the beginning of the next month! The resampling
method doesn't give the desired result in this case. Specifying the `--usebounds` 
option creates a new time axis that is the midpoint of the time bounds variable.
This can be resampled correctly. As only the ice area variable, `aice_m`, was 
specified the result is five files 

    $ ls ACCESS-OM2/aice-m/
    aice-m_ACCESS-OM2_225301_225312.nc  aice-m_ACCESS-OM2_225601_225612.nc  
    aice-m_ACCESS-OM2_225401_225412.nc  aice-m_ACCESS-OM2_225701_225712.nc
    aice-m_ACCESS-OM2_225501_225512.nc

with a year of monthly data in each

    ACCESS-OM2/aice-m/aice-m_ACCESS-OM2_225301_225312.nc
    Time steps:  12  x  30.0 days
    aice_m :: (12, 300, 360) :: ice area  (aggregate)
    TLON   :: (300, 360)     :: T grid center longitude
    TLAT   :: (300, 360)     :: T grid center latitude
    tarea  :: (300, 360)     :: area of T grid cells

So in this case the output files have longer time spans than the input. In 
this way splitvar is flexible, it can take short spans and make them longer,
or long spans and make them shorter. Any number of files can be specified
as input, within memory limits. The files have to contain the same variables
and time axis, but can themselves contain different time spans. This can
occur when models are run for different lengths of time.

### Output path options

For multi-model simulations the convention is to store data by model type.
`splitvar` has the `--model-type` option to support this. If this is specified
the string supplied to the option is inserted into the path for saving the
variable. There is also a `-o` option for specifying an output path to prepend.
For example

    $ splitvar -o outputs/models --model-type ice --simname ACCESS-OM2 --usebounds 
      -v aice_m iceh.225*.nc

creates the following files and directory structure

    $ tree outputs
    outputs
    `-- models
        `-- ACCESS-OM2
            `-- ice
                `-- aice-m
                    |-- aice-m_ACCESS-OM2_225301_225312.nc
                    |-- aice-m_ACCESS-OM2_225401_225412.nc
                    |-- aice-m_ACCESS-OM2_225501_225512.nc
                    |-- aice-m_ACCESS-OM2_225601_225612.nc
                    `-- aice-m_ACCESS-OM2_225701_225712.nc

    4 directories, 5 files

### Compression

By default `splitvar` will use the same compression settings as the input data
sets. In cases where the input data is not compressed, or the deflate level
needs to be changed, this can be overidden with the `--deflate` option.

### Adding and deleting variables

It may be that extra variables need to be added to every output file. For
example, in some cases full model grid information is not included in every output file
in order to save space. Variables from another file can be added to all of the generated
output files using the `-a` option. The argument to the option is a path to a netCDF file.
All variables from that file, except time coordinates, will be added to each output file.

In some cases it may be necessary to delete variables from the input files. For example,
if grid information is included in the model output files, but is not **identical** for
across all input files, the variable will be converted into a time varying variable. This
may be considered undesirable. In this case the grid variables can be deleted with the
`-x` option, and a time invariant grid added back using `-a`.

## Conclusion

`skipvar` relies almost exclusively on the excellent [xarray](http://xarray.pydata.org/en/stable/) python library. For very large data sets memory
limitations imposed by the architecture of the underlying libraries can mean `splitvar`
cannot be used naively. For example the input data sets may need to be processed in small 
groupings, processed one variable at atime.

A [real-world example](https://github.com/aidanheerdegen/publish_cosima_data) of processing 
a suite of model ouputs from three different resolutions, 1, 0.25 and 0.1 degree, gives an 
example of some of the approaches required. 