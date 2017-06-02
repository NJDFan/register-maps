#!/usr/bin/env python3

from registermaps import space
import unittest

class TestRegisterSpace(unittest.TestCase):
	initial_items = (
		('A', 4, 0),
		('B', 1, 4),
		('C', 2, 16),
		('D', 2, 20)
	)
	
	def setUp(self):
		sp = space.Space(size=32, placer=space.LinearPlacer)
		for obj, size, start in self.initial_items:
			sp.add(obj, size, start)
		self.space = sp
		
	def testInitialItems(self):
		for po, (obj, size, start) in zip(self.space.items(), self.initial_items):
			self.assertTrue(po)
			self.assertEqual(po.obj, obj)
			self.assertEqual(po.size, size)
			self.assertEqual(po.start, start)
	
	def testInitialGaps(self):
		gaps = (
			(5, 16),
			(18, 20),
			(22, 32)
		)
		for po, (start, end) in zip(self.space.gaps(), gaps):
			self.assertFalse(po)
			self.assertEqual(po.start, start)
			self.assertEqual(po.end, end)

if __name__ == '__main__':
	unittest.main()
