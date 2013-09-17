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
            self.bitSize = struct.calcsize('${portgen.elementType()}') * 8
            self.historyWindow = 10
            self.receivedStatistics = {}
            self.port_ref = port_ref
            self.receivedStatistics_idx = {}

        def setEnabled(self, enableStats):
            self.enabled = enableStats

        def update(self, elementsReceived, queueSize, streamID, connectionId):
            if not self.enabled:
                return

            if self.receivedStatistics.has_key(connectionId):
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].elements = elementsReceived
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].queueSize = queueSize
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].secs = time.time()
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].streamID = streamID
                self.receivedStatistics_idx[connectionId] += 1
                self.receivedStatistics_idx[connectionId] = self.receivedStatistics_idx[connectionId]%self.historyWindow
            else:
                self.receivedStatistics[connectionId] = []
                self.receivedStatistics_idx[connectionId] = 0
                for i in range(self.historyWindow):
                    self.receivedStatistics[connectionId].append(self.statPoint())
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].elements = elementsReceived
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].queueSize = queueSize
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].secs = time.time()
                self.receivedStatistics[connectionId][self.receivedStatistics_idx[connectionId]].streamID = streamID
                self.receivedStatistics_idx[connectionId] += 1
                self.receivedStatistics_idx[connectionId] = self.receivedStatistics_idx[connectionId] % self.historyWindow

        def retrieve(self):
            if not self.enabled:
                return

            retVal = []
            for entry in self.receivedStatistics:
                runningStats = BULKIO.PortStatistics(portName=self.port_ref.name,averageQueueDepth=-1,elementsPerSecond=-1,bitsPerSecond=-1,callsPerSecond=-1,streamIDs=[],timeSinceLastCall=-1,keywords=[])

                listPtr = (self.receivedStatistics_idx[entry] + 1) % self.historyWindow    # don't count the first set of data, since we're looking at change in time rather than absolute time
                frontTime = self.receivedStatistics[entry][(self.receivedStatistics_idx[entry] - 1) % self.historyWindow].secs
                backTime = self.receivedStatistics[entry][self.receivedStatistics_idx[entry]].secs
                totalData = 0.0
                queueSize = 0.0
                streamIDs = []
                while (listPtr != self.receivedStatistics_idx[entry]):
                    totalData += self.receivedStatistics[entry][listPtr].elements
                    queueSize += self.receivedStatistics[entry][listPtr].queueSize
                    streamIDptr = 0
                    foundstreamID = False
                    while (streamIDptr != len(streamIDs)):
                        if (streamIDs[streamIDptr] == self.receivedStatistics[entry][listPtr].streamID):
                            foundstreamID = True
                            break
                        streamIDptr += 1
                    if (not foundstreamID):
                        streamIDs.append(self.receivedStatistics[entry][listPtr].streamID)
                    listPtr += 1
                    listPtr = listPtr % self.historyWindow

                currentTime = time.time()
                totalTime = currentTime - backTime
                if totalTime == 0:
                    totalTime = 1e6
                receivedSize = len(self.receivedStatistics[entry])
                runningStats.bitsPerSecond = (totalData * self.bitSize) / totalTime
                runningStats.elementsPerSecond = totalData/totalTime
                runningStats.averageQueueDepth = queueSize / receivedSize
                runningStats.callsPerSecond = float((receivedSize - 1)) / totalTime
                runningStats.streamIDs = streamIDs
                runningStats.timeSinceLastCall = currentTime - frontTime
                usesPortStat = BULKIO.UsesPortStatistics(connectionId=entry, statistics=runningStats)
                retVal.append(usesPortStat)
            return retVal

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name
        self.outConnections = {} # key=connectionId,  value=port
        self.refreshSRI = False
        self.stats = self.linkStatistics(self)
        self.port_lock = threading.Lock()
        self.sriDict = {} # key=streamID  value=StreamSRI

    def connectPort(self, connection, connectionId):
        self.port_lock.acquire()
        try:
            port = connection._narrow(${portgen.corbaClass()})
            self.outConnections[str(connectionId)] = port
            self.refreshSRI = True
        finally:
            self.port_lock.release()

    def disconnectPort(self, connectionId):
        self.port_lock.acquire()
        try:
            self.outConnections.pop(str(connectionId), None)
        finally:
            self.port_lock.release()

    def enableStats(self, enabled):
        self.stats.setEnabled(enabled)
        
    def _get_connections(self):
        currentConnections = []
        self.port_lock.acquire()
        for id_, port in self.outConnections.items():
            currentConnections.append(ExtendedCF.UsesConnection(id_, port))
        self.port_lock.release()
        return currentConnections

    def _get_statistics(self):
        self.port_lock.acquire()
        recStat = self.stats.retrieve()
        self.port_lock.release()
        return recStat

    def _get_state(self):
        self.port_lock.acquire()
        numberOutgoingConnections = len(self.outConnections)
        self.port_lock.release()
        if numberOutgoingConnections == 0:
            return BULKIO.IDLE
        else:
            return BULKIO.ACTIVE
        return BULKIO.BUSY

    def _get_activeSRIs(self):
        self.port_lock.acquire()
        sris = []
        for entry in self.sriDict:
            sris.append(copy.deepcopy(self.sriDict[entry]))
        self.port_lock.release()
        return sris

    def pushSRI(self, H):
        self.port_lock.acquire()
        self.sriDict[H.streamID] = copy.deepcopy(H)
        try:
            for connId, port in self.outConnections.items():
                if port != None:
                    try:
                        port.pushSRI(H)
                    except Exception:
                        self.parent._log.exception("The call to pushSRI failed on port %s connection %s instance %s", self.name, connId, port)
        finally:
            self.refreshSRI = False
            self.port_lock.release()

#{% set dataparam = portgen.dataParameterName() %}
#{% if portgen.interface == 'dataXML' %}
#{%   set xdelta = 0.0 %}
    def pushPacket(self, ${dataparam}, EOS, streamID):
#{% else %}
#{%   set xdelta = 1.0 %}
    def pushPacket(self, ${dataparam}, T, EOS, streamID):
#{% endif %}
        if self.refreshSRI:
            if not self.sriDict.has_key(streamID):
                sri = BULKIO.StreamSRI(1, 0.0, ${xdelta}, BULKIO.UNITS_TIME, 0, 0.0, 0.0, BULKIO.UNITS_NONE, 0, streamID, True, []) 
                self.sriDict[streamID] = copy.deepcopy(sri)
            self.pushSRI(self.sriDict[streamID])

        self.port_lock.acquire()

        try:    
            for connId, port in self.outConnections.items():
                if port != None:
                    try:
#{% if portgen.interface == 'dataXML' %}
                        port.pushPacket(${dataparam}, EOS, streamID)
#{% else %}
                        port.pushPacket(${dataparam}, T, EOS, streamID)
#{% endif %}
#{% if portgen.interface == 'dataFile' %}
                        self.stats.update(1, 0, streamID, connId)
#{% else %}
                        self.stats.update(len(${dataparam}), 0, streamID, connId)
#{% endif %}
                    except Exception:
                        self.parent._log.exception("The call to pushPacket failed on port %s connection %s instance %s", self.name, connId, port)
            if EOS==True:
                if self.sriDict.has_key(streamID):
                    tmp = self.sriDict.pop(streamID)
        finally:
            self.port_lock.release()
 
