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

from redhawk.codegen.lang import python

from redhawk.codegen.jinja.mapping import PropertyMapper

class PythonPropertyMapper(PropertyMapper):
    def __init__(self, legacy_structs=True):
        super(PythonPropertyMapper, self).__init__()
        self.legacy_structs = legacy_structs

    def mapProperty(self, prop):
        pyprop = {}
        if prop.hasName():
            name = prop.name()
        else:
            name = prop.identifier()
        pyprop['pyname'] = python.identifier(prop.name())
        return pyprop

    def mapSimpleProperty(self, simple):
        pyprop = self.mapProperty(simple)
        pyprop['isComplex'] = simple.isComplex()
        if simple.hasValue():
            pyprop['pyvalue'] = python.literal(simple.value(), 
                                               simple.type(), 
                                               simple.isComplex())
        return pyprop

    def mapSimpleSequenceProperty(self, simplesequence):
        pyprop = self.mapProperty(simplesequence)
        pyprop['isComplex'] = simplesequence.isComplex()
        if simplesequence.hasValue():
            pyprop['pyvalue'] = python.sequenceValue(simplesequence.value(), 
                                                     simplesequence.type(), 
                                                     simplesequence.isComplex())
        return pyprop

    def mapStructProperty(self, struct, fields):
        pyprop = self.mapProperty(struct)
        pyprop['pyclass'] = self._structName(struct.name())
        return pyprop

    def mapStructSequenceProperty(self, structsequence, structdef):
        pyprop = self.mapProperty(structsequence)
        if structsequence.hasValue():
            pyprop['pyvalues'] = [self._mapStructValue(v, structdef) for v in structsequence.value()]
        return pyprop

    def _mapStructValue(self, value, structdef):
        args= []
        for f in structdef['fields']:
            if f['type'] == 'string' or f['type'] == 'char':
                args.append('\''+value[f['identifier']]+'\'')
            elif f['type'] == 'boolean':
                args.append(value[f['identifier']].capitalize())
            else:
                args.append(value[f['identifier']])
        return '%s(%s)' % (structdef['pyclass'], ','.join(args))

    def _structName(self, name):
        if self.legacy_structs:
            return self._legacyStructName(name)
        else:
            return python.identifier(name) + '_struct'

    def _legacyStructName(self, name):
        # Remove trailing "Struct" from name.
        if name.endswith('Struct'):
            name = name[:-6]
        name = python.identifier(name)
        # Perform a quasi-camel casing, with words separated on underscores.
        def _upcase(s):
            if s:
                return s[0].upper() + s[1:]
            else:
                return s
        return ''.join([_upcase(part) for part in name.split('_')])
