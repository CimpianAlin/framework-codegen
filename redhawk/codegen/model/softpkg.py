#
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
#

import os
import ossie.parsers

from redhawk.codegen.utils import strenum

import properties
from softwarecomponent import SoftwareComponent, ComponentTypes

class Implementation(object):
    def __init__(self, impl):
        self.__impl = impl

    def prfFile(self):
        if self.__impl.propertyfile:
            return self.__impl.propertyfile.localfile.name
        else:
            return None

    def identifier(self):
        return self.__impl.id_

    def entrypoint(self):
        return self.__impl.code.entrypoint

    def programminglanguage(self):
        return self.__impl.programminglanguage.name

def softPkgRef(name, localfile):
    try:
        spd = ossie.parsers.spd.parse(os.getenv('SDRROOT')+'/dom/'+localfile)
    except:
        spd = None
    return {'name':name, 'localfile':localfile, 'spd':spd}

def resolveSoftPkgDeps(spd=None):
    softpkgdeps = []
    if spd == None:
        return softpkgdeps
    for impl in spd.get_implementation():
        for dep in impl.get_dependency():
            if dep.get_softpkgref() != None:
                localfile = dep.get_softpkgref().get_localfile().name
                pkg_name = localfile.split('/')[-1].split('.')[0]
                softpkgdeps.append(softPkgRef(pkg_name, localfile))
                softpkgdeps += resolveSoftPkgDeps(softpkgdeps[-1]['spd'])
    return softpkgdeps

class mFunctionParameters:
    """
    A simple struct for storing off inputs, output, and function mame
    of an m function.

    """
    def __init__(self, outputs, inputs, functionName, defaults={}):
        self.outputs      = outputs
        self.inputs       = inputs
        self.functionName = functionName
        self.defaults     = defaults

def stringToList(stringInput):
    """
    Convert a string of the form:

        "[1,2,3]"

    To:

        ["1", "2", "3"]

    """

    stringInput = stringInput[1:-1]
    stringInput = stringInput.replace(" ", "")  # remove whitespace
    return stringInput.split(",")

def parseDefaults(inputs):
    """
    Parse out default values that have been specified in the input parameters
    of the function declaration.

    Example:

        inputs = ["var1", "var2=5"]

    will return:

        inputs = ["var1", "var2"]
        defaults = {"var2" = "5"}

    """

    defaults = {}
    for index in range(len(inputs)):
        if inputs[index].find("=") != -1:
            splits = inputs[index].split("=")
            inputs[index] = splits[0]
            defaults[inputs[index]] = splits[1]
            if defaults[inputs[index]].find("[") != -1:
                defaults[inputs[index]] = stringToList(defaults[inputs[index]])

    return inputs, defaults

def getArguments(inputString, openDelimiter, closeDelimiter):
    """
    Get arguments within a string.  For example, if openDelimiter="(", 
    closeDelimiter=")", and inputString = "function [a] = foo(b, c, d)",
    this function will return ["b","c","d"].

    """
    args = inputString[inputString.find(openDelimiter)+1: 
                       inputString.find(closeDelimiter)]
    if args.find(",") != -1:
        args = args.split(',')
    else:
        args = args.split()

    args = [x.replace(" ","") for x in args] # get rid of extra whitespace

    # TODO: remove comments from strings
    return args

def parseMFile(filename):
    """
    Parse file specified by filename to get inputs, outputs, and function
    name of the first function defined in the m file.

    """
    # Get the contents of the file as a single string
    file  = open(filename)
    fileString = file.read()
    file.close()

    # the declaration consists of all content up to the first ")"
    declaration  = fileString[0:fileString.find(")")+1]

    # get output arguments
    bracket1 = declaration.find("[")
    if declaration.find("=") == -1 or declaration.find("=") > declaration.find("("):
        # no output arguments, either because no equals sign was found or
        # because no equals sign was found before the input arguments.
        outputs = []
    elif bracket1 != -1 and declaration.find("=") > bracket1:
        # if a bracket is found before the first equals sign, parse
        # the output argument that are between the first set of brackets
        outputs = getArguments(declaration, "[", "]")
    else:
        # list of output arguments without brackets
        outputs = getArguments(declaration, " ", "=")

    # get input arguments
    inputs = getArguments(declaration, "(", ")")
    inputs, defaults = parseDefaults(inputs)

    # get function name
    if declaration.find("=") == -1 or declaration.find("=") > declaration.find("("):
        # if there are no outputs
        functionName = getArguments(declaration, "function", "(")[0]
    else:
        # If there are output arguments (output variables present)
        functionName = getArguments(declaration, "=", "(")[0]

    # store off outputs, inputs and function name in a struct
    return mFunctionParameters(outputs      = outputs, 
                               inputs       = inputs, 
                               functionName = functionName,
                               defaults     = defaults)

class SoftPkg(object):
    def __init__(self, spdFile):
        self.__spdFile = os.path.basename(spdFile)
        self.__spd = ossie.parsers.spd.parse(spdFile)
        self.__softpkgdeps = resolveSoftPkgDeps(self.__spd)
        self.__impls = dict((impl.id_, Implementation(impl)) for impl in self.__spd.implementation)

        self.__path = os.path.dirname(spdFile)

        self.__scdFile = self.__spd.descriptor.localfile.name
        self.__desc = SoftwareComponent(os.path.join(self.__path, self.__scdFile))

        if self.__spd.get_propertyfile():
            self.__prfFile = self.__spd.propertyfile.localfile.name
            if os.path.exists(os.path.join(self.__path, self.__prfFile)):
                self.__props = properties.parse(os.path.join(self.__path, self.__prfFile))
            else:
                self.__props = []
        else:
            self.__props = []
            self.__prfFile = None

        self.__mFunctionParameters = mFunctionParameters(outputs      = [],
                                                         inputs       = [],
                                                         functionName = "")
        for prop in self.__props:
            if str(prop.identifier()) == "__mFunction":
                # m function support only enabled for cpp
                # point towards the m file that has been copied
                # to the cpp directory
                self.__mFunctionParameters = parseMFile(os.path.join(self.__path, "cpp/"+prop.value()+".m"))

    def mFileFunctionName(self):
        return self.__mFunctionParameters.functionName

    def mFileOutputs(self):
        return self.__mFunctionParameters.outputs

    def mFileInputs(self):
        return self.__mFunctionParameters.inputs
 
    def spdFile(self):
        return self.__spdFile

    def prfFile(self):
        return self.__prfFile

    def scdFile(self):
        return self.__scdFile

    def type(self):
        return self.__desc.type()

    def isDevice(self):
        return self.type() == ComponentTypes.DEVICE

    def descriptor(self):
        return self.__desc

    def name(self):
        return self.__spd.name

    def version(self):
        if not self.__spd.version:
            return '1.0.0'
        else:
            return self.__spd.version

    def hasDescription(self):
        return self.description() is not None

    def description(self):
        return self.__spd.description

    def usesPorts(self):
        return self.__desc.uses()

    def providesPorts(self):
        return self.__desc.provides()

    def ports(self):
        return self.__desc.ports()

    def properties(self):
        return self.__props

    def implementations(self):
        return self.__impls.values()

    def getImplementation(self, implId):
        return self.__impls[implId]

    def hasPorts(self):
        return len(self.ports()) > 0

    def hasProperties(self):
        return len(self.__props) > 0

    def hasStructProps(self):
        for prop in self.__props:
            if prop.isStruct():
                return True
        return False

    def getSoftPkgDeps(self):
        return self.__softpkgdeps

    def getStructDefinitions(self):
        structdefs = [s for s in self.getStructProperties()]
        structdefs += [s.struct() for s in self.getStructSequenceProperties()]
        return structdefs

    def getSimpleProperties(self):
        return [p for p in self.__props if not p.isStruct() and not p.isSequence()]

    def getSimpleSequenceProperties(self):
        return [p for p in self.__props if not p.isStruct() and p.isSequence()]

    def getStructProperties(self):
        return [p for p in self.__props if p.isStruct() and not p.isSequence()]

    def getStructSequenceProperties(self):
        return [p for p in self.__props if p.isStruct() and p.isSequence()]

    def hasSDDSPort(self):
        for port in self.ports():
            if port.repid().find('BULKIO/dataSDDS'):
                return True
        return False

    def getSdrPath(self):
        comptype = self.type()
        if comptype == ComponentTypes.RESOURCE:
            return 'dom/components'
        elif comptype == ComponentTypes.DEVICE or comptype == ComponentTypes.LOADABLEDEVICE or comptype == ComponentTypes.EXECUTABLEDEVICE:
            return 'dev/devices'            
        elif comptype == ComponentTypes.SERVICE:
            return 'dev/services'
        raise ValueError, 'Unsupported software component type', comptype
