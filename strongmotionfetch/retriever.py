class Retriever(object):
    def __init__(self,rawfolder,inputfolder):
        self._inputfolder = inputfolder
        self._rawfolder = rawfolder

    def getData(self,time,lat,lon,timewindow,radius):
        self.fetch(time,lat,lon,timewindow,radius) #find files online, download to raw folder
        traces = self.readFiles() #read any files downloaded into raw folder, turn into list of ObsPy Trace objects
        amps = self.traceToAmps(traces) #pull out peak amplitudes, return as data structure
        xmlstr = self.ampsToXML(amps) #convert these amps to an xml string
        self.saveToXML(xmlstr) #write that xml string to a file in the input folder

    def fetch(self,time,lat,lon,timewindow,radius):
        #this is implemented in child classes
        pass

    def readFiles(self):
        #this is implemented in child classes
        pass

    def traceToAmps(traces=None):
        #this is implemented here
        pass

    def ampsToXML(amps=None):
        #this is implemented here
        pass
