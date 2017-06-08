"""Defines a base Visitor class for all the outputs."""

from io import IOBase
from collections import ChainMap
import sys
from os import makedirs
import os.path
import contextlib

class Visitor:
    """An abstract Visitor for working with HtiComponent trees.
    
    Subclasses work by overloading some combination of defaultvisit and
    visit_Component, visit_Register, etc.  These functions are all called on
    a single node of the tree.  They do not recurse by default; overloaded
    functions must explicitly call either self.visit(node) on child nodes or
    self.visitchildren(node) on the current node.
    
    Visitor functions are allowed to return values, but this can get
    complicated quickly.  It's probably better to have them directly manipulate
    states, either storing them in the class instance or writing results
    directly to self.output.
    
    Subclasses can also overload begin and finish, which are called before
    tree parsing starts and after it is completed respectively.  These are
    generally places to put initialization and cleanup code.
    """
    
    binary = False
    encoding = None
    extension = ''
    
    def __init__(self, output, startnode):
        """Create and execute this visitor on an output and startnode.
        
        Output can be:
            '-'
                Output to standard output
            an open File object
                Output to that file
            None
                Allow no output
            a directory name
                Output to files in that directory
        """
        self.printoptions = {}
        
        mode = 'wb' if self.binary else 'w'
        if output == '-':
            self.output = sys.stdout
        elif isinstance(output, IOBase) or output is None:
            self.output = output
        else:
            makedirs(output, exist_ok=True)
            self.outputdir = output
            name = self.makefilename(output, startnode)
            self.output = open(name, mode, encoding=self.encoding)
        self.begin(startnode)
        self.visit(startnode)
        self.finish()
                
    def makefilename(self, outputdir, node):
        """Make a filename for this node."""
        return os.path.join(outputdir, node.name + self.extension)
    
    def visit(self, node):
        """Base visit operation.  This shouldn't need overloading."""
        visitname = 'visit_' + type(node).__name__
        fn = getattr(self, visitname, None)
        if fn is None:
            fn = self.defaultvisit
        return fn(node)
        
    def visitchildren(self, node, reverse=False):
        """Visit all the children of this node.
        
        Shouldn't need overloading, but this must be called explicitly.
        
        Returns a list of all return values from all child nodes.
        """
        
        if reverse:
            it = reversed(list(node.space.items()))
        else:
            it = node.space.items()
        return [self.visit(obj) for obj, start, size in it]
        
    def defaultvisit(self, node):
        """Called when there is no explicit visitor for this node type."""
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

    # Convenience output methods.
    def print(self, *args, **kwargs):
        """Prints to self.output
        
        kwargs are as passed to the print statement.  They override arguments
        registered in self.printoptions (default is empty).
        """
        
        options = ChainMap(kwargs, self.printoptions, {'file' : self.output})
        print(*args, **options)
        
    def printf(self, formatstr, *args, printargs={}, **kwargs):
        """Prints to self.output using a format string.
        
        All args and kwargs are passed to format, not print.  printargs can
        be explicitly provided, but are an indication you've overcomplicated
        things.
        """
        text = formatstr.format(*args, **kwargs)
        self.print(text, **printargs)
        
    def write(self, data):
        """Write binary data to self.output."""
        self.output.write(data)

    @contextlib.contextmanager
    def tempvars(self, **kwargs):
        """Stores kwargs as attributes of the class during the context.
        
        This is extremely useful for dealing with information which must
        be temporarily passed down to recursive calls while making sure
        to clean them back up on the way out.
        
        Overwriting existing attributes will restore them after the context.
        """
        
        deleteattrs = []
        restoreattrs = []
        
        for k, v in kwargs.items():
            try:
                restoreattrs.append( (k, getattr(self, k)) )
            except AttributeError:
                deleteattrs.append(k)
            setattr(self, k, v)
            
        yield
        
        for k, v in restoreattrs:
            setattr(self, k, v)
        for k in deleteattrs:
            delattr(self, k)
