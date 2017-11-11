import importlib
import io
import sys
import pkg_resources
import jinja2
from functools import lru_cache

from . import textfn

######################################################################
# Resource management

__version__ = pkg_resources.get_distribution(__package__).version

@lru_cache(64)
def resource_bytes(resourcename):
    """Get a package resource as binary data.
    
    resourcename starts with 'resource/' if the file is in the resource
    directory.
    """
    
    return pkg_resources.resource_string(__package__, resourcename)
        
@lru_cache(64)
def resource_text(resourcename, encoding='utf-8', errors='strict'):
    """Get a package resource as a text string.
    
    resourcename starts with 'resource/' if the file is in the resource
    directory.
    """
    
    bindata = pkg_resources.resource_string(__package__, resourcename)
    return bindata.decode(encoding, errors)

# Create a jinja2 template environment
jinja = jinja2.Environment(
    loader = jinja2.PackageLoader('registermaps', 'resource'),
    trim_blocks = True,
    lstrip_blocks = True
)
jinja.filters['reflow'] = textfn.reflow

######################################################################
# Package-wide global variables.
    
ProgramGlobals = {
    'verbose' : False
}

def printverbose(*args, **kwargs):
    """Print to stderr if ProgramGlobals['verbose']."""
    
    if ProgramGlobals['verbose']:
        kwargs.setdefault('file', sys.stderr)
        print(*args, **kwargs)

######################################################################
# Output class registration.
    
class _Outputs:
    def __init__(self):
        self._outputs = {}
        
    def register(self, kls):
        """Register an output class for the command-line tool.
        
        Arguments
        ---------
            kls: The class of an object to use.
                The registered name will be taken from the 
                ``outputname`` member.
                
        Return
        ------
            kls, so this can be used as a class decorator.
            
        """
        self._outputs[kls.outputname] = kls
    
    def __iter__(self):
        """Iterate over all the registered outputs."""
        return iter(self._outputs.keys())
        
    def docs(self, output):
        """Get the documentation for an output by name.
        
        Arguments
        ---------
            output (str): Name of a registered output.
        
        Returns
        -------
            Long multi-line str of reSTructuredText.
        """
        return resource_text('resource/{}/README.rst'.format(output))
        
    def output(self, output):
        """Get the output class for an output by name.
        
        Arguments
        ---------
            output (str): Name of a registered output.
        
        Returns
        -------
            Class that can iterate an HtiElement tree.
        """
        return self._outputs[output]
Outputs = _Outputs()

__all__ = [
    'Outputs',
    'printverbose', 'ProgramGlobals',
    'resource_bytes', 'resource_text',
    '__version__'
]
