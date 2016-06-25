#stdlib imports
import ftplib
import os.path
from datetime import datetime,timedelta
import urllib
import sys

#local imports
from .retriever import Retriever
from .reader import TraceReader
from .exception import StrongMotionFetcherException

#third party imports
import numpy as np
from obspy.core.utcdatetime import UTCDateTime
from obspy.core.trace import Stats
from obspy.core.trace import Trace
from obspy.geodetics.base import gps2dist_azimuth

CATBASE = 'http://quakesearch.geonet.org.nz/services/1.0.0/csv?startdate=[START]&enddate=[END]'
GEOBASE = 'ftp://ftp.geonet.org.nz/strong/processed/Proc/[YEAR]/[MONTH]/'
TIMEFMT = '%Y-%m-%dT%H:%M:%S'
NZTIMEDELTA = 2 #number of seconds allowed between GeoNet catalog time and event timestamp on FTP site
NZCATWINDOW = 5*60 #number of seconds to search around in GeoNet EQ catalog

def get_comp_name(compstr):
    """Get a component name (one of '--N','--E', or '--Z') from GeoNet component names.

    component angles are defined like this:
    S00W and S90E
    N33E and N57W

    I interpret these to mean the following:
    S00W Starts at 180 degrees, and swings 0 degrees to the west.  Direction: 180 degrees
    S90E starts at 180 degrees, and swings 90 degrees to the east.  Direction: 90 degrees
    N33E starts at 0 degrees, and swings 33 degrees to the east.  Direction: 33 degrees
    N57W starts at 0 degrees, and swings 57 degrees to the west.  Direction: 303 degrees

    I will define any angle between 315 and 360,0 and 45, 135 to 225 as North-South component
    everything else is East-West
    
    :param compstr:
      String, something like S00W or N33E.
    :returns:
      component name (one of '--N','--E', or '--Z')
    """
    if compstr.lower().strip() == 'up':
        return '--Z'
    compass = {'N':360,'S':180}
    angle = int(compstr[1:-1])
    if compstr[0] == 'N' and compstr[-1] == 'E':
        newangle = angle
    if compstr[0] == 'N' and compstr[-1] == 'W':
        newangle = 360 - angle
    if compstr[0] == 'S' and compstr[-1] == 'E':
        newangle = 180 - angle
    if compstr[0] == 'S' and compstr[-1] == 'W':
        newangle = 180 + angle

    compname = '--E'
    if newangle >= 270 or newangle < 45 or (newangle > 135 and newangle <= 225):
        compname = '--N'
    return compname
    
def _readheader(lines):
    """Internal method Given list of lines from Geonet strong motion header, return a dictionary of parameters.

    :param lines:
      List of lines containing header data.
    :returns:
      Header dictionary, containing fields:
        - station
        - channel
        - instrument
        - location
        - npts
        - starttime
        - sampling_rate
        - delta
        - calib
        - lat
        - lon
        - height
        - duration
        - endtime
        - maxacc
        - network
        - units
    """
    hdrdict = {}
    #input list of 26 lines of header
    #station and channel
    line = lines[5]
    parts = line.strip().split()
    fname = parts[1]
    fparts = fname.split('_')
    hdrdict['station'] = fparts[-2]+'_'+fparts[-1]

    #the "Component" lines look like either: Component S00W, Component S90E, Component Up
    compstr = lines[12].strip().split()[1]
    hdrdict['channel'] = get_comp_name(compstr)

    #instrument
    hdrdict['instrument'] = lines[3].split()[1].strip()
    
    #location string
    line = lines[6]
    hdrdict['location'] = line.strip()
    #event origin, buffer start year/month
    line = lines[16]
    parts = line.strip().split()
    bufyear = int(parts[8])
    bufmonth = int(parts[9])
    #epicentral location, buffer start day/hour
    line = lines[17]
    parts = line.strip().split()
    bufday = int(parts[8])
    bufhour = int(parts[9])
    #numpoints, buffer start min/sec
    line = lines[19]
    parts = line.strip().split()
    hdrdict['npts'] = int(parts[0])
    bufmin = int(parts[8])
    millisec = int(parts[9])
    bufsec = int(millisec/1000)
    bufmicrosec = int(np.round(millisec/1000.0 - bufsec))
    hdrdict['starttime'] = UTCDateTime(datetime(bufyear,bufmonth,bufday,bufhour,bufmin,bufsec,bufmicrosec))
    #part C
    #frequency, calibration value and some other stuff we don't care about
    line = lines[20]
    parts = line.strip().split()
    hdrdict['sampling_rate'] = float(parts[0])
    hdrdict['delta'] = 1.0/hdrdict['sampling_rate']
    hdrdict['calib'] = float(parts[7])
    #site location info, this time in dd
    line = lines[21]
    parts = line.strip().split()
    hdrdict['lat'] = float(parts[0]) * -1
    hdrdict['lon'] = float(parts[1])
    hdrdict['height'] = 0.0
    #duration
    line = lines[22]
    parts = line.strip().split()
    hdrdict['duration'] = float(parts[0])
    hdrdict['endtime'] = hdrdict['starttime'] + hdrdict['duration']
    #max acceleration - good for sanity check
    line = lines[23]
    parts = line.strip().split()
    hdrdict['maxacc'] = float(parts[0])
    hdrdict['network'] = 'NZ'
    hdrdict['units'] = 'acc'
    return hdrdict
    

def _readheaderlines(f):
    """Internal method to read 26 lines of header from Geonet ASCII file.
    """
    hdrlines = []
    for i in range(0,26):
        hdrlines.append(f.readline())
    return hdrlines

def readgeonet(geonetfile):
    """
    Read strong motion data from a GeoNet data file
    :param geonetfile: 
      Path to a valid GeoNet data file.
    :returns: 
      List of ObsPy Trace objects, containing accelerometer data in m/s.
    """
    f = open(geonetfile,'rt')
    tracelist = []
    headerlist = []
    try:
        hdrlines = _readheaderlines(f)
    except:
        pass
    while len(hdrlines[-1]):
        hdrdict = _readheader(hdrlines)
        numlines = int(np.ceil(hdrdict['npts']/10.0))
        data = []
        for i in range(0,numlines):
            line = f.readline()
            parts = line.strip().split()
            mdata = [float(p) for p in parts]
            data = data + mdata
        data = np.array(data)
        header = hdrdict.copy()
        stats = Stats(hdrdict)
        trace = Trace(data,header=stats)
        #apply the calibration and convert from mm/s^2 to m/s^2
        trace.data = trace.data * trace.stats['calib'] * 0.001 #convert to m/s^2
        tracelist.append(trace.copy())
        headerlist.append(header.copy())
        hdrlines = _readheaderlines(f)

    f.close()
    return (tracelist,headerlist)

class GeonetAsciiReader(TraceReader):
    def processFiles(self,datafiles):
        #this will be implemented here
        pass

class GeoNetRetriever(Retriever):
    """Subclass of Retriever to retrieve/process GeoNet ASCII strong motion data files. 
    """
    def fetch(self,etime,lat,lon,timewindow=20,radius=100,limit=None):
        """Retrieve GeoNet strong motion data files from GeoNet.

        :param etime:
          Datetime of origin.
        :param lat:
          Latitude of origin.
        :param lon:
          Longitude of origin.
        :param timewindow:
          Time search window (seconds).  Events will be searched from etime+/-timewindow.
        :param radius:
          Search radius, in km.
        :param limit:
          Number of files to retrieve (used mostly for debugging.)
        """
        utctime = etime
        #get the most likely event time and ID for the event we input
        eid,gtime = self._check_catalog(etime,lat,lon,timewindow,radius)
        if eid is None:
            msg = 'Could not find this event in the GeoNet earthquake catalog.  Returning.'
            raise StrongMotionFetcherException(msg)

        #set up the ftp url for this day and month
        #[MONTH] should be in the format mm_Mon (04_Apr, 05_May, etc.)
        neturl = GEOBASE.replace('[YEAR]',str(utctime.year))
        monthstr = utctime.strftime('%m_%b')
        neturl = neturl.replace('[MONTH]',monthstr)
        urlparts = urllib.parse.urlparse(neturl)
        ftp = ftplib.FTP(urlparts.netloc)
        ftp.login() #anonymous
        ftp.cwd(urlparts.path)

        
        #get the current local directory, then cd to the desired raw folder
        cwd = os.getcwd()
        os.chdir(self._rawfolder)
        self._datafiles = []

        #create the event folder name from the time we got above
        fname = gtime.strftime('%Y-%m-%d_%H%M%S')
        try:
            ftp.cwd(fname)
        except:
            msg = 'Could not find an FTP data folder called "%s". Returning.' % (urllib.parse.urljoin(neturl,fname))
            raise StrongMotionFetcherException(msg)

        try:
            #actually retrieve the data files
            volumes = []
            dirlist = ftp.nlst()
            for volume in dirlist:
                if volume.startswith('Vol'):
                    ftp.cwd(volume)
                    if 'data' not in ftp.nlst():
                        ftp.cwd('..')
                        continue

                    ftp.cwd('data')
                    flist = ftp.nlst()
                    for ftpfile in flist:
                        if not ftpfile.endswith('V1A'):
                            continue
                        localfile = os.path.join(os.getcwd(),ftpfile)
                        if localfile in self._datafiles:
                            continue
                        self._datafiles.append(localfile)
                        f = open(localfile,'wb')
                        sys.stderr.write('Retrieving remote file %s...\n' % ftpfile)
                        ftp.retrbinary('RETR %s' % ftpfile,f.write)
                        f.close()
                        if limit is not None and len(self._datafiles) >= limit:
                            break
                    ftp.cwd('..')
                    ftp.cwd('..')
                if limit is not None and len(self._datafiles) >= limit:
                    break
        except Exception as e:
            pass
        finally:
            ftp.quit()
            os.chdir(cwd)
        return

    def _check_catalog(self,time,lat,lon,timewindow,distwindow):
        """Check the GeoNet website to find the GeoNet ID for our event.

        :param etime:
          Datetime of origin.
        :param lat:
          Latitude of origin.
        :param lon:
          Longitude of origin.
        :param timewindow:
          Time search window (seconds).  Events will be searched from etime+/-timewindow.
        :param distwindow:
          Search radius, in km.
        :returns:
          Tuple of Event ID, Event Time.
        """
        stime = time - timedelta(seconds=NZCATWINDOW)
        etime = time + timedelta(seconds=NZCATWINDOW)
        url = CATBASE.replace('[START]',stime.strftime(TIMEFMT))
        url = url.replace('[END]',etime.strftime(TIMEFMT))
        try:
            fh = urllib.request.urlopen(url)
            data = fh.read().decode('utf-8')
            fh.close()
            lines = data.split('\n')
            vectors = []
            eidlist = []
            etimelist = []
            for line in lines[1:]:
                if not len(line.strip()):
                    break
                #time is column 2, longitude is column 4, latitude is column 5
                parts = line.split(',')
                eid = parts[0]
                etime = datetime.strptime(parts[2][0:19],TIMEFMT)
                elat = float(parts[5])
                elon = float(parts[4])
                if etime > time:
                    dt = etime - time
                else:
                    dt = time - etime
                nsecs = dt.days*86400 + dt.seconds
                dd,az1,az2 = gps2dist_azimuth(lat,lon,elat,elon)
                dd = dd/1000.0
                if nsecs <= timewindow and dd < distwindow:
                    vectors.append(np.sqrt(nsecs**2+dd**2))
                    eidlist.append(eid)
                    etimelist.append(etime)
            if len(vectors):
                idx = vectors.index(min(vectors))
                return (eidlist[idx],etimelist[idx])
        except Exception as msg:
            raise Exception('Could not access the GeoNet website - got error "%s"' % str(msg))
        return (None,None)

    def readFiles(self):
        """Parse GeoNet ASCII strong motion data into Obspy traces.

        :returns:
          List of obspy Trace objects.
        """
        #return a list of traces
        alltraces = []
        for dfile in self._datafiles:
            traces,headers = readgeonet(dfile)
            alltraces += traces
        return alltraces

    

    
