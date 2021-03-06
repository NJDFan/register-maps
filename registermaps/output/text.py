"""Output formatters in the text class."""

import textwrap
from ..visitor import Visitor
from ..util import Outputs

@Outputs.register
class tree(Visitor):
    
    outputname = 'tree'
    extension = '.txt'
    indentper = '    '
    
    def begin(self, startnode):
        self.indent = ''
        
    def headline(self, line, node):
        """Output text:
        
        line
           node.desc
           various children of node
        """
        
        oldindent = self.indent
        self.print(oldindent + line)
        self.indent = newindent = oldindent + self.indentper
        
        wrapper = textwrap.TextWrapper(
            width = 100,
            initial_indent = self.indent,
            subsequent_indent = self.indent
        )
        for d in node.description:
            for line in wrapper.wrap(d):
                self.print(line)        
        self.visitchildren(node)

        self.indent = oldindent
        
    def defaultvisit(self, node):
        skipattrs = ['name', 'readOnly', 'writeOnly']
        line = '{} {} ({}{})'.format(
            type(node).__name__, node.name,
            ','.join('{}={}'.format(k, v) for k, v in node._attrib.items() if k not in skipattrs),
            self.rostat(node)
        )
        self.headline(line, node)
        
    def visit_Component(self, node):
        line = 'component {} (size={}{})'.format(node.name, node.size, self.rostat(node))
        self.headline(line, node)
        
    def visit_Register(self, node):
        line = '({}) {} (reset={}{})'.format(
            node.offset, node.name, node.reset, self.rostat(node)
        )
        self.headline(line, node)
        
    def visit_Instance(self, node):
        line = '({}) {} {}'.format(node.offset, node.extern, node.name)
        self.headline(line, node)
        
    def visit_Enum(self, node):
        line = '{} = {}'.format(node.name, node.value)
        self.headline(line, node)
        
    def rostat(self, node):
        """Return a note for readOnly or writeOnly."""
        return ' RO' if node.readOnly else ' WO' if node.writeOnly else ''
