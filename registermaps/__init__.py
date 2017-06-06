import importlib

def import_module(module):
	"""Import a local module dynamically by name."""
	return importlib.import_module('.' + module, __name__)

def import_object(module, name):
	"""Import an object from a local module dynamically by name."""
	return getattr(import_module(module), name)
