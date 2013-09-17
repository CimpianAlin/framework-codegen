#{#
# This file is protected by Copyright. Please refer to the COPYRIGHT file
# distributed with this source distribution.
#
# This file is part of REDHAWK core.
#
# REDHAWK core is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# REDHAWK core is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see http://www.gnu.org/licenses/.
#}
#% set className = portgen.className()
class ${className}(${component.baseclass.name}.${portgen.templateClass()}):
    class linkStatistics:
        class statPoint:
            def __init__(self):
                self.elements = 0
                self.queueSize = 0.0
                self.secs = 0.0
                self.streamID = ""

        def __init__(self, port_ref):
            self.enabled = True
            self.flushTime = None
            self.historyWindow = 10
            self.receivedStatistics = []
            self.port_ref = port_ref
            self.receivedStatistics_idx = 0
            self.bitSize = struct.calcsize('${portgen.elementType()}') * 8
            for i in range(self.historyWindow):
                self.receivedStatistics.append(self.statPoint())

        def setEnabled(self, enableStats):
            self.enabled = enableStats

        def update(self, elementsReceived, queueSize, streamID, flush):
            if not self.enabled:
                return

            self.receivedStatistics[self.receivedStatistics_idx].elements = elementsReceived
            self.receivedStatistics[self.receivedStatistics_idx].queueSize = queueSize
            self.receivedStatistics[self.receivedStatistics_idx].secs = time.time()
            self.receivedStatistics[self.receivedStatistics_idx].streamID = streamID
            self.receivedStatistics_idx += 1
            self.receivedStatistics_idx = self.receivedStatistics_idx%self.historyWindow
            if flush:
                self.flushTime = self.receivedStatistics[self.receivedStatistics_idx].secs

        def retrieve(self):
            if not self.enabled:
                return None

            self.runningStats = BULKIO.PortStatistics(portName=self.port_ref.name, averageQueueDepth=-1, elementsPerSecond=-1, bitsPerSecond=-1, callsPerSecond=-1, streamIDs=[], timeSinceLastCall=-1, keywords=[])

            listPtr = (self.receivedStatistics_idx + 1) % self.historyWindow    # don't count the first set of data, since we're looking at change in time rather than absolute time
            frontTime = self.receivedStatistics[(self.receivedStatistics_idx - 1) % self.historyWindow].secs
            backTime = self.receivedStatistics[self.receivedStatistics_idx].secs
            totalData = 0.0
            queueSize = 0.0
            streamIDs = []
            while (listPtr != self.receivedStatistics_idx):
                totalData += self.receivedStatistics[listPtr].elements
                queueSize += self.receivedStatistics[listPtr].queueSize
                streamIDptr = 0
                foundstreamID = False
                while (streamIDptr != len(streamIDs)):
                    if (streamIDs[streamIDptr] == self.receivedStatistics[listPtr].streamID):
                        foundstreamID = True
                        break
                    streamIDptr += 1
                if (not foundstreamID):
                    streamIDs.append(self.receivedStatistics[listPtr].streamID)
                listPtr += 1
                listPtr = listPtr%self.historyWindow

            receivedSize = len(self.receivedStatistics)
            currentTime = time.time()
            totalTime = currentTime - backTime
            if totalTime == 0:
                totalTime = 1e6
            self.runningStats.bitsPerSecond = (totalData * self.bitSize) / totalTime
            self.runningStats.elementsPerSecond = totalData / totalTime
            self.runningStats.averageQueueDepth = queueSize / receivedSize
            self.runningStats.callsPerSecond = float((receivedSize - 1)) / totalTime
            self.runningStats.streamIDs = streamIDs
            self.runningStats.timeSinceLastCall = currentTime - frontTime
            if not self.flushTime == None:
                flushTotalTime = currentTime - self.flushTime
                self.runningStats.keywords = [CF.DataType(id="timeSinceLastFlush", value=CORBA.Any(CORBA.TC_double, flushTotalTime))]

            return self.runningStats

    def __init__(self, parent, name, maxsize):
        self.parent = parent
        self.name = name
        self.queue = Queue.Queue(maxsize)
        self.port_lock = threading.Lock()
        self.stats = self.linkStatistics(self)
        self.blocking = False
        self.sriDict = {} # key=streamID, value=StreamSRI

    def enableStats(self, enabled):
        self.stats.setEnabled(enabled)

    def _get_statistics(self):
        self.port_lock.acquire()
        recStat = self.stats.retrieve()
        self.port_lock.release()
        return recStat

    def _get_state(self):
        self.port_lock.acquire()
        if self.queue.full():
            self.port_lock.release()
            return BULKIO.BUSY
        elif self.queue.empty():
            self.port_lock.release()
            return BULKIO.IDLE
        else:
            self.port_lock.release()
            return BULKIO.ACTIVE
        self.port_lock.release()
        return BULKIO.BUSY

    def _get_activeSRIs(self):
        self.port_lock.acquire()
        activeSRIs = [self.sriDict[entry][0] for entry in self.sriDict]
        self.port_lock.release()
        return activeSRIs

    def getCurrentQueueDepth(self):
        self.port_lock.acquire()
        depth = self.queue.qsize()
        self.port_lock.release()
        return depth

    def getMaxQueueDepth(self):
        self.port_lock.acquire()
        depth = self.queue.maxsize
        self.port_lock.release()
        return depth
        
    #set to -1 for infinite queue
    def setMaxQueueDepth(self, newDepth):
        self.port_lock.acquire()
        self.queue.maxsize = int(newDepth)
        self.port_lock.release()

    def pushSRI(self, H):
        self.port_lock.acquire()
        if H.streamID not in self.sriDict:
            self.sriDict[H.streamID] = (copy.deepcopy(H), True)
            if H.blocking:
                self.blocking = True
        else:
            sri, sriChanged = self.sriDict[H.streamID]
            if not self.parent.compareSRI(sri, H):
                self.sriDict[H.streamID] = (copy.deepcopy(H), True)
                if H.blocking:
                    self.blocking = True
        self.port_lock.release()

#{% set dataparam = portgen.dataParameterName() %}
#{% if portgen.interface == 'dataXML' %}
#{%   set timestamp = 'None' %}
    def pushPacket(self, ${dataparam}, EOS, streamID):
#{% else %}
#{%   set timestamp = 'T' %}
    def pushPacket(self, ${dataparam}, T, EOS, streamID):
#{% endif %}
        self.port_lock.acquire()
        if self.queue.maxsize == 0:
            self.port_lock.release()
            return
        packet = None
        try:
            sri = BULKIO.StreamSRI(1, 0.0, 1.0, 1, 0, 0.0, 0.0, 0, 0, streamID, False, [])
            sriChanged = False
            if self.sriDict.has_key(streamID):
                sri, sriChanged = self.sriDict[streamID]
                self.sriDict[streamID] = (sri, False)
            else:
                self.sriDict[streamID] = (sri, False)
                sriChanged = True

            if self.blocking:
                packet = (${dataparam}, ${timestamp}, EOS, streamID, copy.deepcopy(sri), sriChanged, False)
                self.stats.update(len(${dataparam}), float(self.queue.qsize()) / float(self.queue.maxsize), streamID, False)
                self.queue.put(packet)
            else:
                if self.queue.full():
                    try:
                        self.queue.mutex.acquire()
                        self.queue.queue.clear()
                        self.queue.mutex.release()
                    except Queue.Empty:
                        pass
                    packet = (${dataparam}, ${timestamp}, EOS, streamID, copy.deepcopy(sri), sriChanged, True)
                    self.stats.update(len(${dataparam}), float(self.queue.qsize()) / float(self.queue.maxsize), streamID, True)
                else:
                    packet = (${dataparam}, ${timestamp}, EOS, streamID, copy.deepcopy(sri), sriChanged, False)
                    self.stats.update(len(${dataparam}), float(self.queue.qsize()) / float(self.queue.maxsize), streamID, False)
                self.queue.put(packet)
        finally:
            self.port_lock.release()
    
    def getPacket(self):
        try:
            data, T, EOS, streamID, sri, sriChanged, inputQueueFlushed = self.queue.get(block=False)
            
            if EOS: 
                if self.sriDict.has_key(streamID):
                    sri, sriChanged = self.sriDict.pop(streamID)
                    if sri.blocking:
                        stillBlock = False
                        for _sri, _sriChanged in self.sriDict.values():
                            if _sri.blocking:
                                stillBlock = True
                                break
                        if not stillBlock:
                            self.blocking = False
            return (data, T, EOS, streamID, sri, sriChanged, inputQueueFlushed)
        except Queue.Empty:
            return None, None, None, None, None, None, None

