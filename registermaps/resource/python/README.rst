===================
Basic Python Output
===================

This output makes a directory full of Python files that use the
:py:mod:`ctypes` and :py:mod:`bitfield` libraries in order to create a
memory-mapped structure equivalent to the register map.

This is directly useful with a register map that is
connected directly into PC memory space, such as a PCI or VME card, but can
also serve as a base template for the :py:mod:`remotestruct` library to work
via an arbitrary transport layer.

Types
=====
The Python outputs use the basic :py:mod:`ctypes` types of ``c_uint8``,
``c_int32``, and so forth to represent entire registers.

In order to create structured bitfields in registers, additional types are
created with the naming convention _t_<REGISTER> using the
:py:func:`bitfield.make_bf` function.  These ``Bitfield`` objects allow attribute
access to all of the fields as well, as well as dict-like methods like ``keys()``
and ``items()``.  There is also a ``base`` attribute which represents the 
entire register as its underlying unsigned integer.  So if the component that
the register is in has a data width of 32 bits, the bitfield base will be a
``c_uint32``.

Enumeration Constants
=====================

Classes
=======
For each component, a Python file is written defining the component as a subclass
of :py:class:`ctypes.Structure`.  Fields representing gaps in the contiguous
region will be named ``_dummy`` followed by a positional number.

RegisterArrays in Components are treated as arrays in standard ctypes fashion.

For each memorymap, a Python file is written defining the memorymap as a subclass
of :py:class:`ctypes.Structure`.  Fields representing gaps in the contiguous
region will be named ``_dummy`` followed by a positional number.

Instances in the memorymap will be the classes created by the component-level
Python files, which are imported at the top of the memory map file.
