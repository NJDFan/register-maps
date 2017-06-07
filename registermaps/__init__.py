import importlib
import pkg_resources

def import_module(module):
	"""Import a local module dynamically by name."""
	return importlib.import_module('.' + module, __name__)

def import_object(module, name):
	"""Import an object from a local module dynamically by name."""
	return getattr(import_module(module), name)

def resource_bytes(resourcename):
	return pkg_resources.resource_string(__name__, 'resource/' + resourcename)
	
	
def resource_stream(resourcename):
	return pkg_resources.resource_stream(__name__, 'resource/' + resourcename)
	
	
	
