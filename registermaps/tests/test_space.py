#!/usr/bin/env python3

from registermaps import space
import unittest

class BaseSpaceTest(unittest.TestCase):
	size = None
	placer = space.NoPlacer
	resizer = space.NoResizer
	
	initial_items = ()
	gaps = tuple()
	
	def setUp(self):
		sp = space.Space(
			size=self.size,
			placer=self.placer,
			resizer=self.resizer
		)
		for obj, size, start in self.initial_items:
			sp.add(obj, size, start)
		self.space = sp
		
	def testInitialItems(self):
		items = list(self.space.items())
		self.assertEqual(len(items), len(self.initial_items))
		for po, (obj, size, start) in zip(items, self.initial_items):
			self.assertTrue(po)
			self.assertEqual(po.obj, obj)
			self.assertEqual(po.size, size)
			self.assertEqual(po.start, start)
	
	def testInitialGaps(self):
		gaps = list(self.space.gaps())
		self.assertEqual(len(gaps), len(self.gaps))
		for po, (start, end) in zip(gaps, self.gaps):
			self.assertFalse(po)
			self.assertEqual(po.start, start)
			self.assertEqual(po.end, end)
			

class TestSpaceBoolean(BaseSpaceTest):
	
	placer = space.LinearPlacer
	resizer = space.LinearResizer
	
	def testEmpty(self):
		self.assertFalse(self.space)
		
	def testNonEmpty(self):
		sp = self.space
		sp.add('A', 4)
		self.assertTrue(sp)
		self.assertEqual(sp.size, 4)
		self.assertListEqual(list(list(s) for s in sp), [['A', 0, 4]])

class TestRegisterSpace(BaseSpaceTest):
	"""Test a space that looks like Fields in a Register."""
	
	size = 32
	placer = space.LinearPlacer
	initial_items = (
		('A', 4, 0),
		('B', 1, 4),
		('C', 2, 16),
		('D', 2, 20)
	)
	gaps = (
		(5, 16),
		(18, 20),
		(22, 32)
	)
	
	def testStr(self):
		s = str(self.space)
		self.assertEqual(s, "A(4),B(1),None(11),C(2),None(2),D(2),None(10)")
		
	def testFreeAdd(self):
		s = self.space
		po = s.add('E', 10)
		self.assertEqual(po.start, 5)
		po = s.add('F', 10)
		self.assertEqual(po.start, 22)
		with self.assertRaises(ValueError):
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
		
class TestMMSpace(BaseSpaceTest):
	"""Test a space that looks like Components in a MemoryMap."""
	
	initial_items = (
		('A', 32, 0),
		('B', 32, 32),
		('C', 64, 64),
		('D', 4, 128)
	)
	gaps = (
		(132, 256),
	)
	
	placer = space.BinaryPlacer
	resizer = space.BinaryResizer
	
	def testInitialSize(self):
		self.assertEqual(self.space.size, 256)
		
	def testSubspace(self):
		# Start midway through C, end after D.
		sp = self.space[120:140]
		shouldbe = [
			('C', 120, 8),
			('D', 128, 4),
			(None, 132, 8)
		]
		self.assertEqual(len(sp), len(shouldbe))
		for a, b in zip(sp, shouldbe):
			self.assertTupleEqual(tuple(a), b)
	
	def testFreeAdd(self):
		s = self.space
		po = s.add('E', 16)
		self.assertEqual(po.start, 128+16)
		po = s.add('F', 64)
		self.assertEqual(po.start, 128+64)
		po = s.add('G', 16)
		self.assertEqual(po.start, 128+32)
		
		po = s.add('H', 64)
		self.assertEqual(po.start, 256)
		self.assertEqual(s.size, 512)
		
		# Make sure we got everything inserted in the right order
		ordered = ''.join(po.obj for po in s.items())
		self.assertEqual(ordered, 'ABCDEGFH')
		
	def testLast(self):
		last = list(self.space.last())
		self.assertListEqual(last, [None, 132, 256-132])
		self.space.add('H', 64)
		last = list(self.space.last())
		self.assertListEqual(last, ['H', 128+64, 64])
		
	def testStartLegality(self):
		self.space.enforce_rules_on_fixed = True
		with self.assertRaises(ValueError):
			self.space.add('E', 32, 128+48)
		self.space.add('E', 32, 128+64)
		
class TestLinearResizer(BaseSpaceTest):
	"""We have no use for this, but the LinearResizer shouldn't go
	completely untested."""
	
	size = 32
	placer = space.LinearPlacer
	resizer = space.LinearResizer
	initial_items = (
		('A', 4, 0),
		('B', 1, 4),
		('C', 2, 16),
		('D', 2, 20)
	)
	gaps = (
		(5, 16),
		(18, 20),
		(22, 32)
	)
	
	def testFreeAdd(self):
		self.space.add('E', 100)
		self.assertEqual(self.space.size, 122)
		self.assertListEqual(list(self.space.last()), ['E', 22, 100])
		
if __name__ == '__main__':
	unittest.main()
