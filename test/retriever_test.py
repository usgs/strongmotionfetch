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
import pandas as pd

#local imports
from strongmotionfetch.retriever import Retriever


def test_ampstoxml():
    data = {'netid':['sisfrance'],
            'code':[1],
            'name':['m1'],
            'loc':['somewhere'],
            'lat':[32.7],
            'lon':[-145.6],
            'dist':[23.6],
            'source':['sisfrance'],
            'insttype':['OBSERVED'],
            'commtype':['UNK'],
            'intensity':[4.7]}
    df = pd.DataFrame(data=data)    
    ret = Retriever(os.path.expanduser('~'),os.path.expanduser('~'))
    eventinfo = {'id':'usp0007m27',
            'time':datetime.utcnow(),
            'lat':46.015,
            'lon':5.977,
            'depth':5.0,
            'mag':4.5,
            'location':'France',
            'time':datetime(1996,7,15,0,13,28),
            'network':'us'}
    ret.setEventInfo(eventinfo)
    xmlstr = ret.ampsToXML(amps=df)
    df2 = ret.xmlToAmps(xmlstr)
    w = pd.get_option("display.max_columns")
    pd.set_option("display.max_columns",200)
    w2 = pd.get_option("display.max_columns")
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.expand_frame_repr', False)
    print(df)
    print()
    print(df2[df.columns])

if __name__ == '__main__':
    test_ampstoxml()
