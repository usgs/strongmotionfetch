#stdlib imports
import ftplib
import os.path
from datetime import datetime,timedelta

#local imports
from .retriever import Retriever
from .reader import TraceReader
from .exception import StrongMotionFetcherException

CATBASE = 'http://quakesearch.geonet.org.nz/services/1.0.0/csv?startdate=[START]&enddate=[END]'
GEOBASE = 'ftp://ftp.geonet.org.nz/strong/processed/Proc/[YEAR]/[MONTH]/'
TIMEFMT = '%Y-%m-%dT%H:%M:%S'
NZTIMEDELTA = 2 #number of seconds allowed between GeoNet catalog time and event timestamp on FTP site
NZCATWINDOW = 5*60 #number of seconds to search around in GeoNet EQ catalog

class GeonetAcsciiReader(TraceReader):
    def processFiles(self,datafiles):
        #this will be implemented here
        pass

class GeoNetRetriever(Retriever):
    def fetch(self,time,lat,lon,timewindow,radius):
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

        #cd to the desired output folder
        os.chdir(self._rawfolder)
        self._datafiles = []

        #create the event folder name from the time we got above
        fname = gtime.strftime('%Y-%m-%d_%H%M%S')
        try:
            ftp.cwd(fname)
        except:
            msg = 'Could not find an FTP data folder called "%s". Returning.' % (urllib.parse.urljoin(neturl,fname))
            raise StrongMotionFetcherException(msg)

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
                    if localfile in datafiles:
                        continue
                    self._datafiles.append(localfile)
                    f = open(localfile,'wb')
                    sys.stderr.write('Retrieving remote file %s...\n' % ftpfile)
                    ftp.retrbinary('RETR %s' % ftpfile,f.write)
                    f.close()
                ftp.cwd('..')
                ftp.cwd('..')

        ftp.quit()
        return

    def _check_catalog(self,time,lat,lon,timewindow,distwindow):
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
                dd,az1,az2 = gps2DistAzimuth(lat,lon,elat,elon)
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
        #this is implemented here
        pass
