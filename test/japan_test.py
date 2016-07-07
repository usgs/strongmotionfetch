#!/usr/bin/env python

#stdlib imports
import os.path
import sys
import tempfile
import shutil
from datetime import datetime
import glob

#hack the path so that I can debug these functions if I need to
homedir = os.path.dirname(os.path.abspath(__file__)) #where is this script?
strongdir = os.path.abspath(os.path.join(homedir,'..'))
sys.path.insert(0,strongdir) #put this at the front of the system path, ignoring any installed strongmotionfetch stuff

#third party imports
import numpy as np

#local imports
from strongmotionfetch.japan import read_knet,KNetRetriever

def test_fileread():
    testfile = os.path.join('data','knet_example_file.EW')
    trace,header = read_knet(testfile)
    mysum = np.nan #figure out what this should be
    print('Testing that the sum of the trace from test data file is consistent...')
    np.testing.assert_almost_equal(mysum,trace.data.sum())
    print('Passed sum test.')

def test_fetch(user,password):
    #fill in these values with a small Japanese event with not a lot of strong motion data. 
    lat = None
    lon = None
    mag = None
    dtime = None
    nfiles = None #this should be the number of raw data files (both knet and kiknet) belonging to this event.
    rawfolder = tempfile.mkdtemp()
    try:
        print('Testing fetch for geonet...')
        knet = KNetRetriever(rawfolder,rawfolder)
        knet.fetch(dtime,lat,lon,user=user,password=password)
        datafiles = knet.getDataFiles()
        if len(datafiles) == 1:
            print('Passed fetch test for geonet.')
        else:
            print('Failed fetch test for geonet.')
    except:
        print('Failed fetch test for geonet.')
    finally:
        shutil.rmtree(rawfolder)

def test_getamps():
    #test parsing local files into peak amplitudes
    rawfolder = tempfile.mkdtemp()

    #fill in these values with a small Japanese event.
    lat = None
    lon = None
    depth = None
    mag = None
    eid = 'abcd'
    network = 'jp'
    locstring = ''
    dtime = None
    
    eventinfo = {'id':eid,
                 'time':dtime,
                 'lat':lat,
                 'lon':lon,
                 'depth':depth,
                 'mag':mag,
                 'network':network,
                 'location':locstring}
    
    retriever = KNetRetriever(rawfolder,rawfolder)
    retriever.setEventInfo(eventinfo)
    testfiles = glob.glob(os.path.join('data','20141116*.V1A'))
    retriever.setDataFiles(testfiles)

    traces = retriever.readFiles()
    amps = retriever.traceToAmps(traces=traces)
    xmlfile = retriever.ampsToXML(amps=amps)

if __name__ == '__main__':
    if len(sys.argv) > 2:
        user = sys.argv[1]
        password = sys.argv[2]
        test_fetch(user,password)
    test_fileread()
    test_getamps()

