=====================
registermaps Concepts
=====================

Summary
=======

The registermaps package works based on a fairly straightforward two-part 
transformation to get from the XML source to the requested output.  First, a 
:py:class:`xml_parser.XmlParser`, assisted by :py:mod:`lxml`, turns the 
entire collection of source XML files into an internal tree based on subclasses 
of HtiElement.  That tree is then passed to a output class derived from 
:py:class:`visitor.Visitor` to generate output in the requested format.

Parsing the Input
=================

Each element in the XML is transformed one-to-one into an 
:py:class:`HtiElement` object in this tree, ``<component>`` to 
:py:class:`Component`, ``<field>`` to :py:class:`Field` and so on.  These 
elements perform the attribute validation, assign default values as necessary, 
and have a ``space`` element which is a :py:class:`Space`, a representation of 
a finite amount of space with finite blocks of it taken up by "stuff".  The 
``space`` element of each :py:class:`HtiElement` node holds all the children of 
that node.

Attributes that are provided explicitly or have default values that are either 
constant or inherited from their parent are assigned before the element's 
children are filled in.  Then children with explicit offsets are added into 
``space``, then children without explicit offsets are placed in the ``space`` 
and given their new offset.  Then if the ``size`` of the node was not 
explicitly given, it is taken from the size of ``space``, and this is 
communicated back up to the parent node.  In this way the creation of the 
HtiElement tree fills in all missing values in the design.

All of these trees will have a top-level element that is a Component or a 
MemoryMap, and they are grouped as such into the ``components`` and 
``memorymaps`` attributes.  Components are parsed first so that when parsing 
MemoryMaps, each Instance can be given a special attribute called ``binding`` 
which ties it back to a Component.

Generating the Output
=====================

Each tree is then passed to the appropriate output class, derived from 
:py:class:`visitor.Visitor`, to generate the outputs.  These subclasses attempt 
to call methods named things like ``visit_Register`` and ``visit_MemoryMap`` 
based on the type of the node being visited.  If the appropriate method has not 
been defined for this subclass it will fall back to ``defaultvisit``, which for 
the base class simply raises an error.

Often these visitation methods will call ``visitchildren(node)``, which iterates
down through the children of this node in much the same manner.

Visitors can work in different ways based on what is appropriate for the type
of document being generated.  For unstructured documents like source code, they
will generally write their data to their open ``output`` filehandle using
print-like methods ``print`` and ``printf``.  For structured documents like
HTML and XML, it makes more sense for these visitors to pass their results
back up as nodes in a new tree, which is then cooked into a string by the
automatically-called ``finish`` method of the class.
