import tempfile
import numpy as np
from netCDF4 import Dataset, date2num
from datetime import datetime

from PyFVCOM.ll2utm import utm_from_lonlat
from PyFVCOM.read_results import nodes2elems


class StubFile():
    """ Create an FVCOM-formatted netCDF Dataset object. """

    def __init__(self, start, end, interval, lon, lat, triangles, zone='30N'):
        """
        Create a netCDF Dataset object which replicates FVCOM model output.

        This is handy for testing various utilities within PyFVCOM.

        Parameters
        ----------
        start, end : datetime.datetime
            Datetime objects describing the start and end of the netCDF time series.
        interval : float
            Interval (in days) for the netCDF time series.
        lon, lat : list-like
            Arrays of the spherical node positions (element centres will be automatically calculated). Cartesian 
            coordinates for the given `zone' (default: 30N) will be calculated automatically. 
        triangles : list-like
            Triangulation table for the nodes in `lon' and `lat'. Must be zero-indexed.

        """

        self.grid = type('grid', (object,), {})()
        self.grid.lon = lon
        self.grid.lat = lat
        self.grid.nv = triangles + 1  # back to 1-based indexing.
        self.grid.lonc = nodes2elems(lon, triangles)
        self.grid.latc = nodes2elems(lat, triangles)
        self.grid.x, self.grid.y, _ = utm_from_lonlat(self.grid.lon, self.grid.lat, zone=zone)
        self.grid.xc, self.grid.yc, _ = utm_from_lonlat(self.grid.lonc, self.grid.latc, zone=zone)

        # Make up some bathymetry: distance from corner coordinate scaled to 100m maximum.
        self.grid.h = np.hypot(self.grid.x - self.grid.x.min(), self.grid.y - self.grid.y.min())
        self.grid.h = (self.grid.h / self.grid.h.max()) * 100.0
        self.grid.h_center = nodes2elems(self.grid.h, triangles)

        self.grid.siglev = np.tile(np.arange(0, 1.1, 0.1), [len(self.grid.lon), 1]).T
        self.grid.siglay = np.diff(self.grid.siglev, axis=0)
        self.grid.siglev_center = nodes2elems(self.grid.siglev, triangles)
        self.grid.siglay_center = nodes2elems(self.grid.siglay, triangles)

        # Create the all the times we need.
        self.time = type('time', (object,), {})()
        self.time.datetime = self._make_time(start, end, interval)
        self.time.time = date2num(self.time.datetime, units='days since 1858-11-17 00:00:00')
        self.time.Times = np.array([datetime.strftime(d, '%Y-%m-%dT%H:%M:%S.%f') for d in self.time.datetime])
        self.time.Itime = np.floor(self.time.time)
        self.time.Itime2 = (self.time.time - np.floor(self.time.time)) * 1000 * 60 * 60  # microseconds since midnight

        # Our dimension sizes.
        self.dims = type('dims', (object,), {})()
        self.dims.node = len(self.grid.lon)
        self.dims.nele = len(self.grid.lonc)
        self.dims.siglev = self.grid.siglev.shape[0]
        self.dims.siglay = self.dims.siglev - 1
        self.dims.three = 3
        self.dims.time = 0
        self.dims.actual_time = len(self.time.datetime)
        self.dims.DateStrLen = 26
        self.dims.maxnode = 11
        self.dims.maxelem = 9
        self.dims.four = 4

        # Make the stub netCDF object (self.ds)
        self._make_netCDF()

    def _make_netCDF(self):
        self.ncfile = tempfile.NamedTemporaryFile(mode='w', delete=False)
        ncopts = {'zlib': True, 'complevel': 7}
        self.ds = Dataset(self.ncfile.name, 'w', format='NETCDF4')

        # Create the relevant dimensions.
        self.ds.createDimension('node', self.dims.node)
        self.ds.createDimension('nele', self.dims.nele)
        self.ds.createDimension('siglay', self.dims.siglay)
        self.ds.createDimension('siglev', self.dims.siglev)
        self.ds.createDimension('three', self.dims.three)
        self.ds.createDimension('time', self.dims.time)
        self.ds.createDimension('DateStrLen', self.dims.DateStrLen)
        self.ds.createDimension('maxnode', self.dims.maxnode)
        self.ds.createDimension('maxelem', self.dims.maxelem)
        self.ds.createDimension('four', self.dims.four)

        # Make some global attributes.
        self.ds.setncattr('title', 'Stub FVCOM netCDF for PyFVCOM')
        self.ds.setncattr('institution', 'School for Marine Science and Technology')
        self.ds.setncattr('source', 'FVCOM_3.0')
        self.ds.setncattr('history', 'model started at: 02/08/2017   02:35')
        self.ds.setncattr('references', 'http://fvcom.smast.umassd.edu, http://codfish.smast.umassd.edu')
        self.ds.setncattr('Conventions', 'CF-1.0')
        self.ds.setncattr('CoordinateSystem', 'Cartesian')
        self.ds.setncattr('CoordinateProjection', 'proj=utm +ellps=WGS84 +zone=30')
        self.ds.setncattr('Tidal_Forcing', 'TIDAL ELEVATION FORCING IS OFF!')
        self.ds.setncattr('River_Forcing', 'THERE ARE NO RIVERS IN THIS MODEL')
        self.ds.setncattr('GroundWater_Forcing', 'GROUND WATER FORCING IS OFF!')
        self.ds.setncattr('Surface_Heat_Forcing',
                          'FVCOM variable surface heat forcing file:\nFILE NAME:casename_wnd.nc\nSOURCE:wrf2fvcom version 0.14 (2015-10-26) (Bulk method: COARE 2.6SN)\nMET DATA START DATE:2015-06-26_18:00:00')
        self.ds.setncattr('Surface_Wind_Forcing',
                          'FVCOM variable surface Wind forcing:\nFILE NAME:casename_wnd.nc\nSOURCE:wrf2fvcom version 0.14 (2015-10-26) (Bulk method: COARE 2.6SN)\nMET DATA START DATE:2015-06-26_18:00:00')
        self.ds.setncattr('Surface_PrecipEvap_Forcing',
                          'FVCOM periodic surface precip forcing:\nFILE NAME:casename_wnd.nc\nSOURCE:wrf2fvcom version 0.14 (2015-10-26) (Bulk method: COARE 2.6SN)\nMET DATA START DATE:2015-06-26_18:00:00')

        # Make the combinations of dimensions we're likely to get.
        siglay_node = ['siglay', 'node']
        siglev_node = ['siglev', 'node']
        siglay_nele = ['siglay', 'nele']
        siglev_nele = ['siglev', 'nele']
        nele_three = ['three', 'nele']
        time_nele = ['time', 'nele']
        time_siglay_nele = ['time', 'siglay', 'nele']
        time_siglay_node = ['time', 'siglay', 'node']
        time_siglev_node = ['time', 'siglev', 'node']
        time_node = ['time', 'node']

        # Create our data variables.
        lon = self.ds.createVariable('lon', 'f4', ['node'], **ncopts)
        lon.setncattr('units', 'degrees_east')
        lon.setncattr('long_name', 'nodal longitude')
        lon.setncattr('standard_name', 'longitude')

        lat = self.ds.createVariable('lat', 'f4', ['node'], **ncopts)
        lat.setncattr('units', 'degrees_north')
        lat.setncattr('long_name', 'nodal longitude')
        lat.setncattr('standard_name', 'longitude')

        lonc = self.ds.createVariable('lonc', 'f4', ['nele'], **ncopts)
        lonc.setncattr('units', 'degrees_east')
        lonc.setncattr('long_name', 'zonal longitude')
        lonc.setncattr('standard_name', 'longitude')

        latc = self.ds.createVariable('latc', 'f4', ['nele'], **ncopts)
        latc.setncattr('units', 'degrees_north')
        latc.setncattr('long_name', 'zonal longitude')
        latc.setncattr('standard_name', 'longitude')

        siglay = self.ds.createVariable('siglay', 'f4', siglay_node, **ncopts)
        siglay.setncattr('long_name', 'Sigma Layers')
        siglay.setncattr('standard_name', 'ocean_sigma/general_coordinate')
        siglay.setncattr('positive', 'up')
        siglay.setncattr('valid_min', -1.0)
        siglay.setncattr('valid_max', 0.0)
        siglay.setncattr('formula_terms', 'sigma: siglay eta: zeta depth: h')

        siglev = self.ds.createVariable('siglev', 'f4', siglev_node, **ncopts)
        siglev.setncattr('long_name', 'Sigma Levels')
        siglev.setncattr('standard_name', 'ocean_sigma/general_coordinate')
        siglev.setncattr('positive', 'up')
        siglev.setncattr('valid_min', -1.0)
        siglev.setncattr('valid_max', 0.0)
        siglev.setncattr('formula_terms', 'sigma: siglay eta: zeta depth: h')

        siglay_center = self.ds.createVariable('siglay_center', 'f4', siglay_nele, **ncopts)
        siglay_center.setncattr('long_name', 'Sigma Layers')
        siglay_center.setncattr('standard_name', 'ocean_sigma/general_coordinate')
        siglay_center.setncattr('positive', 'up')
        siglay_center.setncattr('valid_min', -1.0)
        siglay_center.setncattr('valid_max', 0.0)
        siglay_center.setncattr('formula_terms', 'sigma:siglay_center eta: zeta_center depth: h_center')

        siglev_center = self.ds.createVariable('siglev_center', 'f4', siglev_nele, **ncopts)
        siglev_center.setncattr('long_name', 'Sigma Levels')
        siglev_center.setncattr('standard_name', 'ocean_sigma/general_coordinate')
        siglev_center.setncattr('positive', 'up')
        siglev_center.setncattr('valid_min', -1.0)
        siglev_center.setncattr('valid_max', 0.0)
        siglev_center.setncattr('formula_terms', 'sigma:siglay_center eta: zeta_center depth: h_center')

        h_center = self.ds.createVariable('h_center', 'f4', ['nele'], **ncopts)
        h_center.setncattr('long_name', 'Bathymetry')
        h_center.setncattr('standard_name', 'sea_floor_depth_below_geoid')
        h_center.setncattr('units', 'm')
        h_center.setncattr('positive', 'down')
        h_center.setncattr('grid', 'grid1 grid3')
        h_center.setncattr('coordinates', 'latc lonc')
        h_center.setncattr('grid_location', 'center')

        h = self.ds.createVariable('h', 'f4', ['node'], **ncopts)
        h.setncattr('long_name', 'Bathymetry')
        h.setncattr('standard_name', 'sea_floor_depth_below_geoid')
        h.setncattr('units', 'm')
        h.setncattr('positive', 'down')
        h.setncattr('grid', 'Bathymetry_Mesh')
        h.setncattr('coordinates', 'x y')
        h.setncattr('type', 'data')

        nv = self.ds.createVariable('nv', 'f4', nele_three, **ncopts)
        nv.setncattr('long_name', 'nodes surrounding element')

        time = self.ds.createVariable('time', 'f4', ['time'], **ncopts)
        time.setncattr('long_name', 'time')
        time.setncattr('units', 'days since 1858-11-17 00:00:00')
        time.setncattr('format', 'modified julian day (MJD)')
        time.setncattr('time_zone', 'UTC')

        Itime = self.ds.createVariable('Itime', int, ['time'], **ncopts)
        Itime.setncattr('units', 'days since 1858-11-17 00:00:00')
        Itime.setncattr('format', 'modified julian day (MJD)')
        Itime.setncattr('time_zone', 'UTC')

        Itime2 = self.ds.createVariable('Itime2', int, ['time'], **ncopts)
        Itime2.setncattr('units', 'msec since 00:00:00')
        Itime2.setncattr('time_zone', 'UTC')

        Times = self.ds.createVariable('Times', 'c', ['time', 'DateStrLen'], **ncopts)
        Times.setncattr('time_zone', 'UTC')

        # Add a single variable of each size commonly found in FVCOM (2D and 3D time series). It should be possible
        # to use create_variable() here, but I'm not sure I like the idea of spamming self with load of arrays.
        # Perhaps making a self.data would be a nice compromise.

        # 3D nodes siglev
        omega = self.ds.createVariable('omega', 'f4', time_siglev_node)
        omega.setncattr('long_name', 'Vertical Sigma Coordinate Velocity')
        omega.setncattr('units', 's-1')
        omega.setncattr('grid', 'fvcom_grid')
        omega.setncattr('type', 'data')
        # 3D nodes siglay
        temp = self.ds.createVariable('temp', 'f4', time_siglay_node)
        temp.setncattr('long_name', 'temperature')
        temp.setncattr('standard_name', 'sea_water_temperature')
        temp.setncattr('units', 'degrees_C')
        temp.setncattr('grid', 'fvcom_grid')
        temp.setncattr('coordinates', 'time siglay lat lon')
        temp.setncattr('type', 'data')
        temp.setncattr('mesh', 'fvcom_mesh')
        temp.setncattr('location', 'node')
        # 3D elements siglay
        ww = self.ds.createVariable('ww', 'f4', time_siglay_nele)
        ww.setncattr('long_name', 'Upward Water Velocity')
        ww.setncattr('units', 'meters s-1')
        ww.setncattr('grid', 'fvcom_grid')
        ww.setncattr('type', 'data')
        u = self.ds.createVariable('u', 'f4', time_siglay_nele)
        u.setncattr('long_name', 'Eastward Water Velocity')
        u.setncattr('standard_name', 'eastward_sea_water_velocity')
        u.setncattr('units', 'meters s-1')
        u.setncattr('grid', 'fvcom_grid')
        u.setncattr('type', 'data')
        u.setncattr('coordinates', 'time siglay latc lonc')
        u.setncattr('mesh', 'fvcom_mesh')
        u.setncattr('location', 'face')
        v = self.ds.createVariable('v', 'f4', time_siglay_nele)
        v.setncattr('long_name', 'Northward Water Velocity')
        v.setncattr('standard_name', 'Northward_sea_water_velocity')
        v.setncattr('units', 'meters s-1')
        v.setncattr('grid', 'fvcom_grid')
        v.setncattr('type', 'data')
        v.setncattr('coordinates', 'time siglay latc lonc')
        v.setncattr('mesh', 'fvcom_mesh')
        v.setncattr('location', 'face')
        # 2D elements
        ua = self.ds.createVariable('ua', 'f4', time_nele)
        ua.setncattr('long_name', 'Vertically Averaged x-velocity')
        ua.setncattr('units', 'meters s-1')
        ua.setncattr('grid', 'fvcom_grid')
        ua.setncattr('type', 'data')
        # 2D nodes
        zeta = self.ds.createVariable('zeta', 'f4', time_node)
        zeta.setncattr('long_name', 'Water Surface Elevation')
        zeta.setncattr('units', 'meters')
        zeta.setncattr('positive', 'up')
        zeta.setncattr('standard_name', 'sea_surface_height_above_geoid')
        zeta.setncattr('grid', 'Bathymetry_Mesh')
        zeta.setncattr('coordinates', 'time lat lon')
        zeta.setncattr('type', 'data')
        zeta.setncattr('location', 'node')

        # Add our 'data'.
        lon[:] = self.grid.lon
        lat[:] = self.grid.lat
        lonc[:] = self.grid.lonc
        latc[:] = self.grid.latc
        siglay[:] = self.grid.siglay
        siglay_center[:] = self.grid.siglay_center
        siglev[:] = self.grid.siglev
        siglev_center[:] = self.grid.siglev_center
        h[:] = self.grid.h
        h_center[:] = self.grid.h_center
        nv[:] = self.grid.nv.T  # need to fix shape
        time[:] = self.time.time
        Times[:] = [list(t) for t in self.time.Times]  # 2D array of characters
        Itime[:] = self.time.Itime
        Itime2[:] = self.time.Itime2

        # Make up something not totally simple.
        period = (1.0 / (12 + (25 / 60))) * 24  # approximate M2 tidal period in days
        amplitude = 1.5
        phase = 0
        _omega = self._make_tide(amplitude / 100, phase + 90, period)
        _temp = np.linspace(9, 15, self.dims.actual_time)
        _ww = self._make_tide(amplitude / 150, phase + 90, period)
        _ua = self._make_tide(amplitude / 10, phase + 45, period / 2)
        _zeta = self._make_tide(amplitude, phase, period)
        omega[:] = np.tile(_omega, (self.dims.node, self.dims.siglev, 1)).T * (1 - self.grid.siglev)
        temp[:] = np.tile(_temp, (self.dims.node, self.dims.siglay, 1)).T * (1 - self.grid.siglev[1:, :])
        ww[:] = np.tile(_ww, (self.dims.nele, self.dims.siglay, 1)).T * (1 - self.grid.siglev_center[1:, :])
        u[:] = np.tile(_ua, (self.dims.nele, self.dims.siglay, 1)).T * (1 - self.grid.siglev_center[1:, :])
        v[:] = np.tile(_ua, (self.dims.nele, self.dims.siglay, 1)).T * (1 - self.grid.siglev_center[1:, :])
        ua[:] = np.tile(_ua * 0.9, (self.dims.nele, 1)).T
        zeta[:] = np.tile(_zeta, (self.dims.node, 1)).T

        self.ds.close()

    def create_variable(self, name, dimensions, type='f4', attributes=None):
        """ 
        Add a variable to the current netCDF object. 

        Parameters
        ----------
        name : str
            Variable name.
        dimensions : list
            List of strings describing the dimensions of the data.
        type : str
            Variable data type (defaults to 'f4').
        attributes: dict, optional
            Dictionary of attributes to add.
            
        """
        array = self.ds.createVariable(name, type, dimensions)
        if attributes:
            for attribute in attributes:
                setattr(array, attribute, attributes[attribute])

        setattr(self.data, name, array)

    def _make_time(self, start, end, inc=1):
        """
        Make a list of datetimes between two dates.

        Parameters
        ----------
        start_time, end_time : datetime
            Start and end time as datetime objects.
        inc : float, optional
            Specify a time increment for the list of dates in days. If omitted,
            defaults to 1 day.

        Returns
        -------
        dates : list
            List of datetimes.

        """

        start_seconds = int(start.strftime('%s'))
        end_seconds = int(end.strftime('%s'))

        inc *= 86400  # seconds
        dates = np.arange(start_seconds, end_seconds + inc, inc)
        dates = np.asarray([datetime.utcfromtimestamp(d) for d in dates])

        return dates

    def _make_tide(self, amplitude, phase, period):
        """ Create a sinusoid of given amplitude, phase and period. """

        tide = amplitude * np.sin((2 * np.pi * period * (self.time.time - np.min(self.time.time))) + np.deg2rad(phase))

        return tide
