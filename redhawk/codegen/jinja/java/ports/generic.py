import jinja2
from omniORB import CORBA

from redhawk.codegen.lang import java
from redhawk.codegen.jinja.ports import PortFactory
from redhawk.codegen.jinja.java import JavaTemplate

from generator import JavaPortGenerator

_baseMap = {
    CORBA.tk_short:     java.Types.SHORT,
    CORBA.tk_long:      java.Types.INT,
    CORBA.tk_ushort:    java.Types.SHORT,
    CORBA.tk_ulong:     java.Types.INT,
    CORBA.tk_float:     java.Types.FLOAT,
    CORBA.tk_double:    java.Types.DOUBLE,
    CORBA.tk_boolean:   java.Types.BOOLEAN,
    CORBA.tk_char:      java.Types.CHAR,
    CORBA.tk_octet:     java.Types.BYTE,
    CORBA.tk_longlong:  java.Types.LONG,
    CORBA.tk_ulonglong: java.Types.LONG
}

def packageName(scopedName):
    # Identifier is always the last element of the scoped name; the namespace
    # is everything leading up to it.
    identifier = scopedName[-1]
    namespace = scopedName[:-1]
    # Assume the first element of the namespace (if any) is a module, and any
    # subsequenct elements are interfaces; this is not a safe assumption in the
    # general sense, but is true within REDHAWK.
    namespace = namespace[:1] + [ns+'Package' for ns in namespace[1:]]
    return '.'.join(namespace+[identifier])

def baseType(typeobj):
    kind = typeobj.kind()
    if kind in _baseMap:
        return _baseMap[kind]
    elif kind == CORBA.tk_void:
        return 'void'
    elif kind == CORBA.tk_string:
        return 'String'
    elif kind == CORBA.tk_any:
        return 'org.omg.CORBA.Any'
    elif kind == CORBA.tk_sequence:
        return baseType(typeobj.sequenceType()) + '[]'
    elif kind == CORBA.tk_alias:
        return baseType(typeobj.aliasType())
    else:
        name = packageName(typeobj.scopedName())
        if name.startswith('CORBA'):
            return 'org.omg.'+name
        else:
            return name

def outType(typeobj):
    kind = typeobj.kind()
    if kind in _baseMap:
        name = _baseMap[kind].capitalize()
    elif kind == CORBA.tk_alias:
        name = packageName(typeobj.scopedName())
    else:
        name = baseType(typeobj)
    return name + 'Holder'

def paramType(param):
    if param.direction == 'in':
        return baseType(param.paramType)
    else:
        return outType(param.paramType)

class GenericPortFactory(PortFactory):
    def match(cls, port):
        return True

    def generator(cls, port):
        if port.isProvides():
            return GenericProvidesPortGenerator(port)
        else:
            return GenericUsesPortGenerator(port)

class GenericPortGenerator(JavaPortGenerator):
    def loader(self):
        return jinja2.PackageLoader(__package__)

    def operations(self):
        for op in self.idl.operations():
            yield {'name': op.name,
                   'arglist': ', '.join('%s %s' % (paramType(p), p.name) for p in op.params),
                   'argnames': [p.name for p in op.params],
                   'throws': ', '.join(baseType(r) for r in op.raises),
                   'returns': baseType(op.returnType)}
        for attr in self.idl.attributes():
            yield {'name': attr.name,
                   'arglist': '',
                   'argnames': tuple(),
                   'returns': baseType(attr.attrType)}
            if not attr.readonly:
                yield {'name': attr.name,
                       'arglist': baseType(attr.attrType)+ ' data',
                       'argnames': ('data',),
                       'returns': 'void'}
        

class GenericProvidesPortGenerator(GenericPortGenerator):
    def _implementation(self):
        return JavaTemplate('generic.provides.java')

    def _ctorArgs(self, name):
        return ('this', java.stringLiteral(name))

class GenericUsesPortGenerator(GenericPortGenerator):
    def _implementation(self):
        return JavaTemplate('generic.uses.java')

    def _ctorArgs(self, name):
        return (java.stringLiteral(name),)
