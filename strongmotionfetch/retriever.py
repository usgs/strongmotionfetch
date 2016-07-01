
#stdlib imports
import time
import os.path
from xml.dom import minidom

#third party
import pandas as pd
from obspy.geodetics.base import gps2dist_azimuth
from obspy.signal.invsim import simulate_seismometer, corn_freq_2_paz
from matplotlib import dates
from neicio.tag import Tag

FILTER_FREQ = 0.02
CORNERS = 4

def get_period_name(period):
    """Turn a spectral period float (0.1,1.0, etc.) into a string ('psa01','psa10', etc.).

    :param period:
      Float spectral period.
    :returns:
      String representation of period.
    """
    pstr = 'psa'+str(period).replace('.','')
    return pstr

def get_peak_spectrals(data, samp_rate,periods):
    """Calculate peak pseudo-spectral parameters.

    Compute 5% damped PSA at input periods seconds.

    Data must be an acceleration Trace.

    :param data:
      Obspy Trace object, containing acceleration data to convolve with pendulum at freq.
    :param delta: 
      sample rate (samples per sec).
    :returns: 
      Dictionary containing keys of input periods, and values of corresponding spectral accelerations.
    """

    D = 0.05	# 5% damping

    psadict = {}
    for T in periods:
        freq = 1.0 / T
        omega = (2 * 3.14159 * freq) ** 2

        paz_sa = corn_freq_2_paz(freq, damp=D)
        paz_sa['sensitivity'] = omega
        paz_sa['zeros'] = []
        dd = simulate_seismometer(data.data, samp_rate, paz_remove=None, paz_simulate=paz_sa,
                     taper=True, simulate_sensitivity=True, taper_fraction=0.05)

        if abs(max(dd)) >= abs(min(dd)):
            psa = abs(max(dd))
        else:
            psa = abs(min(dd))
        psadict[T] = psa

    return psadict

class Retriever(object):
    """Parent class for all objects that retrieve strong motion waveform or peak data.
    """
    def __init__(self,rawfolder,inputfolder,seed_files=None,resp_files=None):
        """Initialize Retriever object.

        :param rawfolder:
          Directory where raw waveform data (if existing) should be written.
        :param inputfolder:
          Directory where peak amplitude data in XML or spreadsheet form should be written.
        :param seed_files:
          List of dataless SEED files to be used for data calibration.
        :param resp_files:
          List of response files to be used for data calibration.
        """
        self._inputfolder = inputfolder
        self._rawfolder = rawfolder
        self.setCalibration(seed_files,resp_files)
        self._datafiles = []
        self.source = None

    def getData(self,eventinfo,timewindow,radius,format='xml'):
        """Retrieve (possibly waveform) data from online source, process to peaks, save as desired output format.

        :param eventinfo:
          Dictionary containing fields:
           - time Datetime of origin.
           - lat  Latitude of origin.
           - lon  Longitude of origin.
           - depth Depth of origin.
           - mag Earthquake magnitude.
           - location String describing earthquake origin.
           - id Event ID.
           - network Event source network.
        :param timewindow:
          Time search window (seconds).  Events will be searched from etime+/-timewindow.
        :param radius:
          Search radius, in km.
        :param format:
          Desired peak ground motion output format, either 'xml' or 'excel'.
        """
        time,lat,lon,depth = eventinfo['time'],eventinfo['lat'],eventinfo['lon'],eventinfo['depth']
        self.setEventInfo(eventinfo)
        self.fetch(time,lat,lon,timewindow,radius) #find files online, download to raw folder
        traces = self.readFiles() #read any files downloaded into raw folder, turn into list of ObsPy Trace objects
        amps = self.traceToAmps(traces) #pull out peak amplitudes, return as data structure
        if format == 'xml':
            xmlstr = self.ampsToXML(amps) #convert these amps to an xml string
            self.saveToXML(xmlstr) #write that xml string to a file in the input folder
        else:
            excelfile = os.path.join(self._inputfolder,'%s_dat.xlsx' % self._source)
            amps.to_excel(excelfile)

    def setEventInfo(self,eventinfo):
        """Set the event information.

        :param eventinfo:
          Dictionary containing fields:
           - time Datetime of origin.
           - lat  Latitude of origin.
           - lon  Longitude of origin.
           - depth Depth of origin.
           - mag Earthquake magnitude.
           - location String describing earthquake origin.
           - id Event ID.
           - network Event source network.
        """
        self._id = eventinfo['id']
        self._mag = eventinfo['mag']
        self._source = eventinfo['network']
        self._location = eventinfo['location']
        self._origin = {'time':eventinfo['time'],'lat':eventinfo['lat'],'lon':eventinfo['lon'],'depth':eventinfo['depth']}

    def getDataFiles(self):
        """Get list of raw data files (if any) downloaded from online source.
        :returns:
          List of raw data files (if any) downloaded from online source.
        """
        return self._datafiles
        
    def fetch(self,time,lat,lon,timewindow,radius):
        """Retrieve online data.

        This is to be implemented in child classes.
        """
        pass

    def readFiles(self):
        """Read waveform files.

        This is to be implemented in child classes.
        """
        #this is implemented in child classes
        pass

    def setCalibration(self,seed_files=None,resp_files=None):
        """Set calibration files.

        This is to be implemented in child classes.
        """
        #this is implemented in child classes
        self._parser = None
        self._resp = None

    def getCalibration(self):
        """Get the ObsPy Parser, and RESP-file generated from a dataless SEED volume.

        :returns:
          Tuple of ObsPy Parser object and seedresp.
        """
        return (self._parser,self._resp)

    def setDataFiles(self,datafiles):
        """Provide the Retriever object with pre-retrieved data files.

        :param datafiles:
          List of data files that can be parsed by this retriever.
        """
        self._datafiles = datafiles

    def traceToAmps(self,traces=None,periods=[0.3,1.0,3.0]):
        """Convert a set of traces to peak ground motions, return as a DataFrame.

        :param traces:
          List of Obspy Trace objects.  Can be velocity or acceleration data.
        :param periods:
          Sequence of spectral periods at which pseudo-spectral peaks should be computed.
        :returns:
          DataFrame containing the following columns:
            - netid
            - name
            - code
            - loc
            - lat
            - lon
            - dist
            - source
            - insttype
            - commtype
            - intensity
            and then a number of intensity measure types, typically including:
            - pga
            - pgv
            - psa03
            - psa10
            - psa30
            and possibly a number of other pseudo-spectral periods.
        """
        pcolumns = [get_period_name(p) for p in periods]
        columns = ['netid','name','code','loc','lat','lon','dist','source','insttype','commtype','intensity','pga','pgv'] + pcolumns
        df = pd.DataFrame(data=None,columns=columns)
        for trace in traces:
            row = {}
            stationdict = self._getStationMetadata(trace)
            trace = self._calibrateTrace(trace)
            peaks = self._get_peaks(trace,periods)
            row['netid'] = stationdict['netid']
            row['name'] = stationdict['name']
            row['code'] = stationdict['code']
            row['channel'] = stationdict['channel']
            row['loc'] = stationdict['loc']
            row['lat'] = stationdict['lat']
            row['lon'] = stationdict['lon']
            row['dist'] = gps2dist_azimuth(self._origin['lat'],self._origin['lon'],row['lat'],row['lon'])[0]/1000.0
            row['source'] = stationdict['source']
            row['insttype'] = stationdict['insttype']
            row['commtype'] = stationdict['commtype']
            row['intensity'] = ''
            for key,value in peaks.items():
                row[key] = value
            df = df.append(row,ignore_index=True)
        return df
    
    def ampsToXML(self,amps=None,save=True):
        """Save a DataFrame of peak amplitudes to a ShakeMap compatible XML station data file.

        :param amps:
          DataFrame containing the following columns:
            - netid
            - name
            - code
            - loc
            - lat
            - lon
            - dist
            - source
            - insttype
            - commtype
            - intensity
            and then a number of intensity measure types, typically including:
            - pga
            - pgv
            - psa03
            - psa10
            - psa30
            and possibly a number of other pseudo-spectral periods.
        :param save:
          Boolean indicating whether XML representation of amps data should be saved to a file.
        :returns:
          String containing XML representation of amps data.
        """
        codes = amps['code'].unique()
        psacols = amps.columns[amps.columns.str.startswith('psa')].tolist()
        imts = ['pga','pgv'] + psacols
        shakemap_data_tag = Tag('shakemap-data')
        atts = {'id':self._id,
                'lat':self._origin['lat'],
                'lon':self._origin['lon'],
                'depth':self._origin['depth'],
                'mag':self._mag,
                'year':self._origin['time'].year,
                'month':self._origin['time'].month,
                'day':self._origin['time'].day,
                'hour':self._origin['time'].hour,
                'minute':self._origin['time'].minute,
                'second':self._origin['time'].second,
                'locstring':self._location,
                'created':int(time.time())}
        earthquake_tag = Tag('earthquake',attributes=atts)
        shakemap_data_tag.addChild(earthquake_tag)
        stationlist_tag = Tag('stationlist',attributes={'created':int(time.time())})
        for code in codes: #each code is a station
            rows = amps[amps['code'] == code]
            atts = {'code':rows.iloc[0]['code'],
                    'name':rows.iloc[0]['name'],
                    'insttype':rows.iloc[0]['insttype'],
                    'lat':rows.iloc[0]['lat'],
                    'lon':rows.iloc[0]['lon'],
                    'dist':rows.iloc[0]['dist'],
                    'source':rows.iloc[0]['source'],
                    'netid':rows.iloc[0]['netid'],
                    'commtype':rows.iloc[0]['commtype'],
                    'loc':rows.iloc[0]['loc'],
                    'intensity':rows.iloc[0]['intensity']}
            station_tag = Tag('station',attributes=atts)
            for index, row in rows.iterrows():
                for imt in imts:
                    if imt not in row:
                        continue
                    comptag = Tag('comp',attributes={'name':imt})
                    imt_tag = Tag(imt,attributes={'value':row[imt],'flag':'0'})
                    comptag.addChild(imt_tag)
                    station_tag.addChild(comptag)
            stationlist_tag.addChild(station_tag)
        earthquake_tag.addChild(stationlist_tag)
        outfile = os.path.join(self._inputfolder,'%s_dat.xml' % self._source)
        if save:
            xmlstr = earthquake_tag.renderToXML(outfile)
        return xmlstr
        
    def xmlToAmps(self,xmlstr=None):
        """Turn a ShakeMap XML file into a pandas DataFrame.

        :param xmlstr:
          String containing XML from a ShakeMap stationlist data file.
        :returns:
          DataFrame containing peak amplitudes - see return from traceToAmps().
        """
        if xmlstr is None:
            return None
        root = minidom.parseString(xmlstr)
        comps = root.getElementsByTagName('comp')
        imts = []
        for comp in comps:
            for child in comp.childNodes:
                if child.nodeType != child.ELEMENT_NODE:
                    continue
                if child.nodeName not in imts:
                    imts.append(child.nodeName)
        imts.sort()
        columns = ['netid','name','code','loc','lat','lon','dist','source','insttype','commtype','intensity'] + imts
        amps = pd.DataFrame(data=None,columns=columns)
        stations = root.getElementsByTagName('station')
        row = {}
        for station in stations:
            strings = ['netid','name','code','loc','source','insttype','commtype']
            floats = ['lat','lon','dist','intensity']
            for string in strings:
                row[string] = station.getAttribute(string)
            for flt in floats:
                try:
                    row[flt] = float(station.getAttribute(flt))
                except:
                    row[flt] = np.nan
            
            comps = station.getElementsByTagName('comp')
            for comp in comps:
                for child in comp.childNodes:
                    if child.nodeType != child.ELEMENT_NODE:
                        continue
                    if child.nodeName in imts:
                        row[child.nodeName] = float(child.getAttribute('value'))
            amps = amps.append(row,ignore_index=True)
        root.unlink()
        
        return amps    
        
        
    def _getStationMetadata(self,trace):
        """Internal method to extract station metadata from a Trace object.

        :param trace:
          Obspy Trace object.
        :returns:
          Dictionary of station metadata:
            - netid
            - name
            - code
            - loc
            - channel
            - lat
            - lon
            - insttype
            - source
            - commtype
        """
        net = trace.stats['network']
        station = trace.stats['station']
        location = trace.stats['location']
        channel = trace.stats['channel']
        instrument = trace.stats['instrument']
        source = trace.stats['network']
        channel_id = '%s.%s.%s.%s' % (net,station,location,channel)
        parser,response = self.getCalibration()
        if parser is not None:
            paz = parser.getPAZ(channel_id)
            coordinates = parser.getCoordinates(channel_id)
        else:
            try:
                coordinates = {'latitude':trace.stats['lat'],
                               'longitude':trace.stats['lon'],
                               'elevation':trace.stats['height']}
            except:
                try:
                    coordinates = {'latitude':trace.stats['coordinates']['latitude'],
                                   'longitude':trace.stats['coordinates']['longitude'],
                                   'elevation':trace.stats['coordinates']['elevation']}
                except:
                    raise StrongMotionException('Could not get station coordinates from trace object of station %s\n' % station)

        if parser is not None:
            vdict = parser.getInventory()
        else:
            vdict = None
        code = '%s.%s' % (net,station)
        station_name = 'UNK'
        if vdict is not None:
            for sta in vdict['stations']:
                if sta['station_id'] == '%s.%s' % (net,station):
                    station_name = sta['station_name']
                    break
            instrument = 'UNK'
            for cha in vdict['channels']:
                if cha['channel_id'] == channel_id:
                    instrument = cha['instrument']
                    break
            source = ''
            for netw in vdict['networks']:
                if netw['network_code'] == net:
                    source = netw['network_name']
                    break
        else:
            station_name = trace.stats['station']

        lat = coordinates['latitude']
        lon = coordinates['longitude']
        sdict = {'netid':net,'name':location,'code':code,'loc':station_name,'channel':channel,
                 'lat':lat,'lon':lon,'insttype':instrument,'source':source,'commtype':'DIG'}
        return sdict

    def _calibrateTrace(self,trace):
        """Internal method to apply parser and seedresp objects to calibrate Trace data.

        :param trace:
          Uncorrected Obspy Trace object.
        :returns:
          Corrected Obspy Trace object.
        """
        parser,respose = self.getCalibration()
        #If we have separate calibration data, apply it here
        if parser is not None:
            trace.simulate(paz_remove=paz,remove_sensitivity=True,simulate_sensitivity=False)
            trace.stats['units'] = 'acc' #ASSUMING THAT ANY SAC DATA IS ACCELERATION!
        else:
            if trace.stats['units'] != 'acc':
                if seedresp is None:
                    raise Exception('Must have a PolesAndZeros data structure (i.e., from dataless SEED) or a RESP file.')
                else:
                    pre_filt = (0.01, 0.02, 20, 30)
                    try:
                        trace.simulate(paz_remove=None, pre_filt=pre_filt, seedresp=seedresp)
                    except Exception as error:
                        pass
        return trace

    def _get_peaks(self,trace,periods):
        """Internal method to return peak values for all desired ground motion parameters.

        :param trace:
          Obspy Trace object containing either 
        """
        peaks = {}
        if trace.stats['units'] == 'acc':
            delta = trace.stats['sampling_rate']

            #apply a bunch of signal processing routines
            #these may have already been applied to the data, but it doesn't seem to do any harm here.
            #feel free to disagree.
            trace.detrend('linear')
            trace.detrend('demean')
            trace.taper(max_percentage=0.05, type='cosine')
            trace.filter('highpass',freq=FILTER_FREQ,zerophase=True,corners=CORNERS)

            trace.detrend('linear')
            trace.detrend('demean')

            # Get the Peak Ground Acceleration
            pga = abs(trace.max())

            #get the spectral accelerations for input periods
            spectrals = get_peak_spectrals(trace, delta,periods)

            #convert all accelerations to %g
            pga = pga/0.0981
            for key,value in spectrals.items():
                spectrals[key] = value/0.0981

            #get the peak pgv value
            pgv = self._get_pgv(trace)
            peaks['pga'] = pga
            peaks['pgv'] = pgv
            for period,peak in spectrals.items():
                strperiod = get_period_name(period)
                peaks[strperiod] = peak
        else:
            pgv = self._get_pgv(trace)
            peaks[pga] = None
            peaks[pgv] = None
            for period in periods:
                strperiod = get_period_name(period)
                peaks[strperiod] = None
        return peaks

    def _get_pgv(self,trace):
        if trace.stats['units'] == 'vel': #don't integrate the broadband
            vtimes = trace.times()
            vtimes = [(trace.stats['starttime'] + t).datetime for t in vtimes]
            mvtimes = dates.date2num(vtimes)
            vtrace = trace.copy()
        else:
            vtrace = trace.copy()
            vtrace.integrate() # vtrace now has velocity
            vtimes = vtrace.times()
            vtimes = [(vtrace.stats['starttime'] + t).datetime for t in vtimes]
            mvtimes = dates.date2num(vtimes)

        # Get the Peak Ground Velocity
        pgv = abs(vtrace.max())
        return pgv
    
    
