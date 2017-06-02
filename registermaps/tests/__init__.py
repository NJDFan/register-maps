import unittest

def all_tests(): 
	return unittest.TestLoader().discover(__name__)
