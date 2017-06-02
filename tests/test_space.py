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
			
	def testStr(self):
		s = str(self.space)
		self.assertEqual(s, "A(4),B(1),None(11),C(2),None(2),D(2),None(10)")
		
	def testFreeAdd(self):
		s = self.space
		po = s.add('E', 10)
		self.assertEqual(po.start, 5)
		po = s.add('F', 10)
		self.assertEqual(po.start, 22)
		with self.assertRaises(IndexError):
			po = s.add('G', 10)
		po = s.add('G', 1)
		self.assertEqual(po.start, 15)
		
		# Make sure we got everything inserted in the right order
		ordered = ''.join(po.obj for po in s.items())
		self.assertEqual(ordered, 'ABEGCDF')
		
		# Should be only one gap left
		gaps = list(s.gaps())
		self.assertEqual(len(gaps), 1)
		self.assertEqual(gaps[0].start, 18)
		self.assertEqual(gaps[0].size, 2)
		
	def testLast(self):
		last = self.space.last()
		self.assertEqual(list(last), [None, 22, 10])
		self.space.add('G', 10, 22)
		last = self.space.last()
		self.assertEqual(list(last), ['G', 22, 10])

if __name__ == '__main__':
	unittest.main()
