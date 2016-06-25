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
from strongmotionfetch.geonet import GeonetAsciiReader,readgeonet,readheader,GeoNetRetriever

def test_fileread():
    testfile = os.path.join('data','geonet_testfile.V1A')
    traces,headers = readgeonet(testfile)
    sums = [-0.0064000000000005164,-0.021799999999999875,-0.012700000000000544]
    print('Testing that the sums of the traces from test data file are consistent...')
    for trace,sum in zip(traces,sums):
        np.testing.assert_almost_equal(sum,trace.data.sum())
    print('Passed sum test.')

def test_fetch():
    lat = -37.6478
    lon = 179.6621
    mag = 6.7
    dtime = datetime(2014,11,16,22,33,20)
    rawfolder = tempfile.mkdtemp()
    try:
        print('Testing fetch for geonet...')
        geonet = GeoNetRetriever(rawfolder,rawfolder)
        geonet.fetch(dtime,lat,lon,limit=1)
        datafiles = geonet.getDataFiles()
        if len(datafiles) == 1:
            print('Passed fetch test for geonet.')
        else:
            print('Failed fetch test for geonet.')
    except:
        print('Failed fetch test for geonet.')
    finally:
        shutil.rmtree(rawfolder)

def test_getamps():
    rawfolder = tempfile.mkdtemp()
    lat = -37.6478
    lon = 179.6621
    depth = 22.0
    mag = 6.7
    eid = 'abcd'
    network = 'nz'
    locstring = ''
    dtime = datetime(2014,11,16,22,33,20)
    eventinfo = {'id':eid,
                 'time':dtime,
                 'lat':lat,
                 'lon':lon,
                 'depth':depth,
                 'mag':mag,
                 'network':network,
                 'location':locstring}
    
    retriever = GeoNetRetriever(rawfolder,rawfolder)
    retriever.setEventInfo(eventinfo)
    testfiles = glob.glob(os.path.join('data','20141116*.V1A'))
    retriever.setDataFiles(testfiles)
    traces = retriever.readFiles()
    amps = retriever.traceToAmps(traces=traces)
    xmlfile = retriever.ampsToXML(amps=amps)

if __name__ == '__main__':
    test_fileread()
    test_getamps()
    test_fetch()
    # network = sys.argv[1]
    # time = sys.argv[2]
    # lat = float(sys.argv[3])
    # lon = float(sys.argv[4])

    # #user/password for those that require it, like knet
    # if len(sys.argv) == 7:
    #     user = sys.argv[5]
    #     password = sys.argv[6]
        
    # rawfolder = os.getcwd()
    # inputfolder = os.getcwd()
    # timewindow = 60 #seconds
    # distwindow = 50 #kilometers to search around
    # retrievers = {'newzealand':GeoNetRetriever,
    #               'japan':KnetRetriever,
    #               'iris':IRISRetriever,
    #               'taiwan':TaiwanRetriever,
    #               'europe':EuropeRetriever}
    # retriever = retrievers[network)(rawfolder,inputfolder)
    # retriever.getData(time,lat,lon,timewindow,distwindow)
