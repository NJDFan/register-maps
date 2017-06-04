"""Defines a base Visitor class for all the outputs."""

import textwrap

class Visitor:
    def visit(self, node):
        visitfn = 'visit' + type(node).__name__
        getattr(self, visitfn)(node)
        
    def __getattr__(self, key):
        raise AttributeError('{} has no attribute {}'.format(
            type(self).__name__,
            key
        ))
        
class TreePrinter(Visitor):
    indentper = '    '
    
    def __init__(self):
        self.indent = ''
        
    def visit(self, node):
        displayfn = 'display' + type(node).__name__
        print(getattr(self, displayfn)(node))
        self.indent += self.indentper
        wrapper = textwrap.TextWrapper(
            width = 100,
            initial_indent = self.indent,
            subsequent_indent = self.indent
        )
        for d in node.description:
            for line in wrapper.wrap(d):
                print(line)
        
        for po in node.space.items():
            self.visit(po.obj)
        
        self.indent = self.indent[:-len(self.indentper)]
        
    def __getattr__(self, key):
        if key.startswith('visit'):
            return self.displayDefault
        raise AttributeError(key)
        
    def displayDefault(self, node):
        return self.indent + type(node).__name__ + ' ' + node.name
        
    def displayComponent(self, node):
        return '{}component {} (size={})'.format(
            self.indent, node.name, node.size
        )
        
    def displayRegister(self, node):
        return '{}({}) {}'.format(
            self.indent, node.offset, node.name
        )
