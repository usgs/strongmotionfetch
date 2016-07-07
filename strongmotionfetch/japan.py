class KnetAsciiReader(TraceReader):
    def processFiles(self,datafiles):
        #this will be implemented here
        pass


class KnetRetriever(Retriever):
    #Retrieve knet/kiknet data online, unpack, and download files to the raw folder 
    #(specified in the Retriever class __init__() method).
    def fetch(self,time,lat,lon,timewindow=20,radius=100,user=None,password=None):
        #this is implemented here
        pass

    #Parse raw knet/kiknet files into Trace objects
    def readFiles(self):
        #this is implemented here
        pass
