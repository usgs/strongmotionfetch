import urllib.request as request
    
def get_emsc(etime,lat,lon,radius=100,timewindow=20):
    """Return the emsc event information most closely matching (in time and space) input event information.

    :param etime:
      Datetime containing earthquake hypocentral time.
    :param lat:
      Hypocentral latitude.
    :param lon:
      Hypocentral longitude.
    :param radius:
      EMSC catalog search radius, in km.
    :param timewindow:
      Time search window (seconds).  Events will be searched from etime+/-timewindow.
    :returns:
      Dictionary containing fields:
       - id EMSC id.
       - time Datetime of EMSC time.
       - lat EMSC hypocentral latitude.
       - lon EMSC hypocentral longitude.
       - depth EMSC hypocentral depth. 
       - mag EMSC magnitude.
    """
    URL = 'http://www.seismicportal.eu/fdsnws/event/1/query?limit=10&start=[START]&end=[END]&lat=[LAT]&lon=[LON]&maxradius=[RADIUS]&format=json'
    tstart = (etime - datetime.timedelta(seconds=20)).strftime('%Y-%m-%dT%H:%M:%S')
    tend = (etime + datetime.timedelta(seconds=20)).strftime('%Y-%m-%dT%H:%M:%S')
    dmin = max(0,depth-DDEPTH)
    dmax = depth+DDEPTH
    mmin = max(0,magnitude - DMAG)
    mmax = min(9.9,magnitude + DMAG)
    url = URL.replace('[START]',str(tstart))
    url = url.replace('[END]',str(tend))
    url = url.replace('[LAT]',str(lat))
    url = url.replace('[LON]',str(lon))
    maxradius = radius/111.1191
    url = url.replace('[LAT]',str(lat))
    url = url.replace('[LON]',str(lon))
    url = url.replace('[RADIUS]',str(maxradius))
    fh = request.urlopen(url)
    data = fh.read().decode('utf-8')
    fh.close()
    if not len(data.strip()):
        return None
    jdict = json.loads(data)
    if len(jdict['features']) == 1:
        event = jdict['features'][0]
        elon,elat,edepth = event['geometry']['coordinates']
        edepth = edepth * -1 #emsc depths seem to be negative down...
        eid = event['properties']['source_id']
        if event['properties']['source_catalog'].lower().find('emsc') > -1:
            eid = 'emsc'+eid
        eetime = datetime.datetime.strptime(event['properties']['time'][0:19],'%Y-%m-%dT%H:%M:%S')
        emag = event['properties']['mag']
        edict = {'time':eetime,
                 'lat':elat,
                 'lon':elon,
                 'depth':edepth,
                 'mag':emag,
                 'id':eid}
        return edict
    else:
        dtimes = []
        ddist = []
        events = []
        for event in jdict['features']:
            elon,elat,edepth = event['geometry']['coordinates']
            edepth = edepth * -1 #emsc depths seem to be negative down...
            eid = event['properties']['source_id']
            if event['properties']['source_catalog'].lower().find('emsc') > -1:
                eid = 'emsc'+eid
            eetime = datetime.datetime.strptime(event['properties']['time'][0:19],'%Y-%m-%dT%H:%M:%S')
            emag = event['properties']['mag']
            dd = gps2dist_azimuth(lat,lon,elat,elon)[0] #meters
            if etime >= eetime:
                dt = (etime - eetime).seconds
            else:
                dt = (eetime - etime).seconds
            dtimes.append(dt)
            ddist.append(dd)
            events.append({'time':eetime,
                           'lat':elat,
                           'lon':elon,
                           'depth':edepth,
                           'mag':emag,
                           'id':eid})
        dtimes = np.array(dtimes)
        ddist = np.array(ddist)
        dtimes = dtimes/max(dtimes)
        ddist = ddist/max(ddist)
        dsq = np.sqrt(dtimes**2 + ddist**2)
        imin = dsq.argmin()
        return events[imin]
    return None

class EuropeRetriever(Retriever):
    def fetch(self,time,lat,lon,timewindow=20,radius=100):
        """Retrieve ShakeMap XML file data from RRSM repository and hold in a local string.

        :param time:
          Datetime indicating time of earthquake origin (UTC).
        :param lat:
          Latitude of earthquake origin.
        :param lon:
          Longitude of earthquake origin.
        :param timewindow:
          Time search window (seconds).  Events will be searched from etime+/-timewindow.
        :param radius:
          EMSC catalog search radius, in km.
        """
        emscinfo = get_emsc(etime,lat,lon,radius=radius,timewindow=timewindow)
        if emscinfo is None:
            return
        topurl = 'ftp://www.orfeus-eu.org/pub/data/shakemaps/'
        #append emscinfo['id'] to url, then 'input/filename.xml', then grab it with urllib
        #save the data from the file in self._xmlstr
        #to open a url, and read in the data, do the following:
        #fh = request.urlopen(url)
        #data = fh.read().decode('utf-8')

    def readFiles(self):
        #do nothing
        pass

    def traceToAmps(self,traces=None):
        #do nothing
        pass
    
    def ampsToXML(self,amps=None):
        return self._xmlstr
