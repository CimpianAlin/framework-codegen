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

from redhawk.codegen.model.softwarecomponent import ComponentTypes
from redhawk.codegen.lang.idl import IDLInterface

from redhawk.codegen.jinja.cpp.component.base import BaseComponentMapper

class PullComponentMapper(BaseComponentMapper):
    def _mapComponent(self, softpkg):
        cppcomp = {}
        cppcomp['baseclass'] = self.baseClass(softpkg)
        cppcomp['userclass'] = self.userClass(softpkg)
        cppcomp['superclasses'] = self.superClasses(softpkg)
        cppcomp['interfacedeps'] = tuple(self.getInterfaceDependencies(softpkg))
        cppcomp['softpkgdeps'] = self.softPkgDeps(softpkg, format='deps')
        cppcomp['pkgconfigsoftpkgdeps'] = self.softPkgDeps(softpkg, format='pkgconfig')
        cppcomp['hasmultioutport'] = self.hasMultioutPort(softpkg)
        return cppcomp

    @staticmethod
    def userClass(softpkg):
        return {'name'  : softpkg.name()+'_i',
                'header': softpkg.name()+'.h',
                'file'  : softpkg.name()+'.cpp'}

    @staticmethod
    def baseClass(softpkg):
        baseclass = softpkg.name() + '_base'
        return {'name'  : baseclass,
                'header': baseclass+'.h',
                'file'  : baseclass+'.cpp'}

    @staticmethod
    def superClasses(softpkg):
        if softpkg.type() == ComponentTypes.RESOURCE:
            name = 'Resource_impl'
        elif softpkg.type() == ComponentTypes.DEVICE:
            name = 'Device_impl'
            aggregate = 'virtual POA_CF::AggregatePlainDevice'
        elif softpkg.type() == ComponentTypes.LOADABLEDEVICE:
            name = 'LoadableDevice_impl'
            aggregate = 'virtual POA_CF::AggregateLoadableDevice'
        elif softpkg.type() == ComponentTypes.EXECUTABLEDEVICE:
            name = 'ExecutableDevice_impl'
            aggregate = 'virtual POA_CF::AggregateExecutableDevice'
        else:
            raise ValueError, 'Unsupported software component type', softpkg.type()
        classes = [{'name': name, 'header': '<ossie/'+name+'.h>'}]
        if softpkg.descriptor().supports('IDL:CF/AggregateDevice:1.0'):
            classes.append({'name': aggregate, 'header': '<CF/AggregateDevices.h>'})
            classes.append({'name': 'AggregateDevice_impl', 'header': '<ossie/AggregateDevice_impl.h>'})
        return classes

    def hasMultioutPort(self, softpkg):
        for prop in softpkg.getStructSequenceProperties():
            if prop.name() == "connectionTable" and  \
               prop.struct().name() == "connection_descriptor":
                foundConnectionName = False
                foundStreamId = False
                foundPortName = False
                for field in prop.struct().fields():
                    if field.name() == "connection_id":
                        foundConnectionName = True 
                    elif field.name() == "stream_id":
                        foundStreamId = True 
                    elif field.name() == "port_name":
                        foundPortName = True 
                if foundConnectionName == True and \
                   foundStreamId == True and \
                   foundPortName == True:
                    return True
        return False
