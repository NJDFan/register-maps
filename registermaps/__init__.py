import importlib
import io
import sys
import pkg_resources

__version__ = pkg_resources.get_distribution(__name__).version

def import_module(module):
    """Import a local module dynamically by name."""
    return importlib.import_module('.' + module, __name__)

def import_object(module, name):
    """Import an object from a local module dynamically by name."""
    return getattr(import_module(module), name)

def resource_bytes(resourcename):
    """Get a package resource as binary data.
    
    resourcename starts with 'resource/' if the file is in the resource
    directory.
    """
    
    return pkg_resources.resource_string(__name__, resourcename)
    
def resource_stream(resourcename):
    """Get a package resource as a readable binary file-like object.
    
    resourcename starts with 'resource/' if the file is in the resource
    directory.
    """
    return pkg_resources.resource_stream(__name__, resourcename)
    
def resource_textstream(resourcename,
     encoding=None, errors=None, newline=None,
     line_buffering=False, write_through=False):
    """Get a package resource as a readable text file-like object.
    
    resourcename starts with 'resource/' if the file is in the resource
    directory.
    """
    
    return io.TextIOWrapper(resource_stream(resourcename),
        encoding, errors, newline, line_buffering, write_through)
        
def resource_text(resourcename, encoding='utf-8', errors='strict'):
    """Get a package resource as a text string.
    
    resourcename starts with 'resource/' if the file is in the resource
    directory.
    """
    return resource_bytes(resourcename).decode(encoding, errors)
    
ProgramGlobals = {
    'verbose' : False
}

def printverbose(*args, **kwargs):
    """Print to stderr if ProgramGlobals['verbose']."""
    
    if ProgramGlobals['verbose']:
        kwargs.setdefault('file', sys.stderr)
        print(*args, **kwargs)
    
