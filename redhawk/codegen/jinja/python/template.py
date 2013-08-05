from redhawk.codegen.lang import python

from redhawk.codegen.jinja.template import TemplateFile

class PythonTemplate(TemplateFile):
    def options(self):
        return {
            'trim_blocks':           True,
            'line_statement_prefix': '#%',
            'variable_start_string': '${',
            'variable_end_string':   '}',
            'block_start_string':    '#{%',
            'block_end_string':      '%}'
        }

    def filters(self):
        import filters
        return {
            'tuple': filters.do_tuple
        }

    def context(self):
        return {
            'python': python
        }
