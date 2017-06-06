"""Defines a base Visitor class for all the outputs."""

import sys
import os.path

class Visitor:
    binary = False
    encoding = None
    extension = ''
    
    def __init__(self, outputdir, startnode):
        """Create and execute this visitor on an outputdir and startnode.
        
        If outputdir is '-', output will be written to stdout instead.  This
        is probably a poor idea with binary mode outputs.
        """
        
        mode = 'wb' if self.binary else 'w'
        if outputdir == '-':
            self.output = sys.stdout
        else:
            name = self.makefilename(outputdir, startnode)
            self.output = open(name, mode, encoding=self.encoding)
        self.begin(startnode)
        self.visit(startnode)
        self.finish()
                
    def makefilename(self, outputdir, node):
        """Make a filename for this node."""
        filename = os.path.join(outputdir, node.name + self.extension)
    
    def visit(self, node):
        """Base visit operation.  This shouldn't need overloading."""
        visitname = 'visit_' + type(node).__name__
        fn = getattr(self, visitname, None)
        if fn is None:
            fn = self.defaultvisit
        fn(node)
        
    def defaultvisit(self, node):
        raise AttributeError('{} has no method for {}'.format(
            type(self).__name__,
            type(node).__name__
        ))

    def begin(self, startnode):
        """Things to do before we begin visiting the first node."""
        pass

    def finish(self):
        """Things to do after we have visited the entire tree."""
        pass
