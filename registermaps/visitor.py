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
    
    Create an instance of the Visitor, then call .execute on the start node.
    Return value is the return value of Visitor.finish, which will usually
    be None.
    """
    
    binary = False
    encoding = None
    extension = ''
    
    def __init__(self, output=None, directory=None, verbose=True):
        """Create this visitor bound to an output.
        
        Parameters
        ----------
        output
            None for no output, '-' for stdout, the name of a file, or an
            open file-like object.
            
        directory
            If provided, a directory in which to put files named after the
            root nodes of the XML files, plus the .extension data member.  So
            if extension='.html' and the XML file starts with
            <component name="DIO">, the resulting file will be
            directory/DIO.html
            
            Overrides output if present.
            
        verbose
            Write filenames to sys.stderr if True.
            
        Basic data members
        ------------------
        printoptions
            A dict of options to pass by default to the print command when
            calling the print and printf methods.
        
        binary
            Set to True if files should be opened in binary mode.
            
        encoding
            Set to dictate how files are opened in text mode.
            
        extension
            File extension when using directory to create files.  Include
            the leading '.'
            
        Data members created by execute
        -------------------------------
        output
            File-like object that is the default target for print, printf, and
            write operations.
            
        filename
            The file basename of the output file, or None if not applicable.
            
        path
            The path of the output file, or None if not applicable.
        
        """
        self.printoptions = {}
        self._output = output
        self._directory = directory
        self.path = self.filename = self.output = None
        self.verbose = verbose
    
    def _openfile(self):
        """Open the file specified by self.path and self.filename as
        self.output.
        
        Creates directories as needed.
        """
        mode = 'wb' if self.binary else 'w'
        makedirs(self.path, exist_ok = True)
        fn = os.path.join(self.path, self.filename)
        self.output = open(fn, mode, encoding=self.encoding)
        if self.verbose:
            print(os.path.join(self.path, self.filename), file=sys.stderr)
            
    def execute(self, startnode):
        # Figure out what our actual output is going to be
        if self._directory is not None:
            self.path = self._directory
            self.filename = startnode.name + self.extension
            self._openfile()
        
        elif isinstance(self._output, str):
            if self._output == '-':
                self.output = sys.stdout
            else:
                self.filename = os.path.basename(self._output)
                self.path = os.path.dirname(self._output)
                self._openfile()
                
        else:
            # This handles None, io.IOBase, and anything else we didn't
            # cover.  If it misbehaves in the role, it's the user's problem.
            self.output = self._output

        # Now execute against the node.
        self.begin(startnode)
        return self.finish(self.visit(startnode))
    
    def visit(self, node):
        """Base visit operation.  This shouldn't need overloading."""
        visitname = 'visit_' + type(node).__name__
        fn = getattr(self, visitname, self.defaultvisit)
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
        """Things to do before we begin visiting the first node.
        
        startnode is the top-level node of the tree.
        """
        pass

    def finish(self, lastvalue):
        """Things to do after we have visited the entire tree.
        
        lastvalue is the return of the top-level visit call.
        """
        return lastvalue

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
