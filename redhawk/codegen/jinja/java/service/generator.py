from redhawk.codegen.jinja.loader import CodegenLoader
from redhawk.codegen.jinja.common import ShellTemplate, AutomakeTemplate, AutoconfTemplate
from redhawk.codegen.jinja.java import JavaCodeGenerator, JavaTemplate
from redhawk.codegen.jinja.java.properties import JavaPropertyMapper
from redhawk.codegen.jinja.java.ports import JavaPortMapper
from redhawk.codegen.jinja.java.ports.generic import GenericPortFactory

from redhawk.codegen import utils
import os

from mapping import ServiceMapper

loader = CodegenLoader(__package__,
                       {'common': 'redhawk.codegen.jinja.common',
                       'pull': 'redhawk.codegen.jinja.java.component.pull'})

class ServiceGenerator(JavaCodeGenerator):
    def parseopts (self, java_package='', use_jni=True):
        self.package = java_package
        self.usejni = utils.parseBoolean(use_jni)

    def loader(self, service):
        return loader

    def componentMapper(self):
        return ServiceMapper(self.package)

    def propertyMapper(self):
        return JavaPropertyMapper()

    def portMapper(self):
        return JavaPortMapper()

    def portFactory(self):
        return JavaPortMapper()

    def templates(self, service):
        # Put generated Java files in "src" subdirectory, followed by their
        # package path.
        pkgpath = os.path.join('src', *service['package'].split('.'))
        mainfile = service['userclass']['file']
        templates = [
            JavaTemplate('service.java', os.path.join(pkgpath, mainfile)),
            AutomakeTemplate('pull/Makefile.am'),
            AutoconfTemplate('pull/configure.ac'),
            ShellTemplate('pull/startJava.sh'),
            ShellTemplate('common/reconf')
        ]

        return templates

