#!/usr/bin/env python

if __name__ == '__main__':
    network = sys.argv[1]
    time = sys.argv[2]
    lat = float(sys.argv[3])
    lon = float(sys.argv[4])

    #user/password for those that require it, like knet
    if len(sys.argv) == 7:
        user = sys.argv[5]
        password = sys.argv[6]
        
    rawfolder = os.getcwd()
    inputfolder = os.getcwd()
    timewindow = 60 #seconds
    distwindow = 50 #kilometers to search around
    retrievers = {'newzealand':GeoNetRetriever,
                  'japan':KnetRetriever,
                  'iris':IRISRetriever,
                  'taiwan':TaiwanRetriever,
                  'europe':EuropeRetriever}
    retriever = retrievers[network)(rawfolder,inputfolder)
    retriever.getData(time,lat,lon,timewindow,distwindow)
