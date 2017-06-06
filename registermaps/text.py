"""Output formatters in the text class."""

import textwrap
from .visitor import Visitor

class tree(Visitor):
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
        print(oldindent + line, file=self.output)
        self.indent = newindent = oldindent + self.indentper
        
        wrapper = textwrap.TextWrapper(
            width = 100,
            initial_indent = self.indent,
            subsequent_indent = self.indent
        )
        for d in node.description:
            for line in wrapper.wrap(d):
                print(line, file=self.output)
        
        for po in node.space.items():
            self.visit(po.obj)
        
        self.indent = oldindent
        
    def defaultvisit(self, node):
        line = '{}? {}'.format(type(node).__name__, node.name)
        self.headline(line, node)
        
    def visit_Component(self, node):
        line = 'component {} (size={})'.format(node.name, node.size)
        self.headline(line, node)
        
    def visit_Register(self, node):
        line = '({}) {}'.format(node.offset, node.name)
        self.headline(line, node)
        
    def visit_Instance(self, node):
        line = '({}) {} {}'.format(node.offset, node.extern, node.name)
        self.headline(line, node)
        
