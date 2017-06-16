===============================
XML Register Description Format
===============================

Summary
=======

The registermap tools operate off of a Highland proprietary register 
description format.  ipXACT_ was considered and rejected for this.  If the 
tools had materialized around it, the fact that it's deeply non-hierarchical 
and highly complex would have been tolerable.  As an XML format that someone 
would have to write by hand it's a bear.

.. _ipXACT: http://www.eda.org/downloads/standards/ip-xact

So we have the HtiCompoment format, which is based on hierarchical XML which
itself is organized into files.  Files take one of two forms (shown here streamlined)::

    component
      register
      register
        field
      registerarray
        register
      register
      register
        field
          enum
          enum
          enum
        field
        field
          enum
          enum
          
    memorymap
      instance
      instance
      instance
      instance
      
Instances are of components.  So an extremely trivial use of the tools might
look like:

.. code-block:: xml
    :caption: DIO.xml

    <?xml version="1.0" encoding="iso-8859-1"?>
    <component name="DIO" width="16">
        Digital I/O peripheral.  I/O port is 1 byte wide, all registers use
        bits 7-0 to control I/Os 7-0 respectively.
        
        <register name="DRIVE" width=8>
            <desc>Current output value of the port if it is outputting.</desc>
            <desc>The OUT register determines whether it does anything.</desc>
        </register>
        
        <register name="READ" width=8>
            Current value read from the port.  This is valid whether or not
            the port is driving that value.
        </register>
        
        <register name="OUT" width=8>
            Set bits to 1 to drive from the value in DRIVE.  Clear to 0 to use
            as inputs.
        </register>
    </component>
        
.. code-block:: xml
    :caption: DESIGN.xml

    <?xml version="1.0" encoding="iso-8859-1"?>
    <memorymap name="DESIGN" width="16" base="0xE0000000">
        Peripheral system.
        <instance name="PORT0" extern="DIO"/>
        <instance name="PORT1" extern="DIO"/>
        <instance name="PORT2" extern="DIO"/>
    </memorymap>
    
Using the Tools
===============

Because of the connection between memorymaps and components, the tools are
designed to work on an entire collection of source files at once, and generate
an entire directory of output.

One of the many things the tools do is automatically size and place the objects
called out.  Sizes and offsets can be provided explicitly, but if they are not
the tools will make a best-faith effort to get things placed.  The placing
algorithm is stable; running the tools multiple times on the same source
files will yield the same autoplacements.

XML Specification
=================

General
-------

In addition to what is explicitly listed below, elements can contain either
free text (which will be treated as a single description element) or one or
more description elements.  ``desc`` is an alias for description.

description
+++++++++++

Contains:
  
    - One paragraph of descriptive text.  Whitespace is ignored.
  

Component Definition
--------------------

component
+++++++++

Required attributes:

    :name:  name of the component
    :width: number of bits per word, must be a power of 2 greater than or equal
            to 8.
  
Optional attributes:

    :readOnly:  Component default is read-only (default=false)
    :size:      number of words in the component (default = auto)
    :writeOnly: Component default is write-only (default=false)

Contains:

    - register
    - registerarray
    
registerarray
+++++++++++++

Required attributes:

    :count: number of copies of the contents
    
Optional attributes:

    :framesize: number of words in each copy of the array (default=auto)
    :name:      name of the registerarray.  Defaults to the name of the contained
                element if only one element is contained; required otherwise.
    :offset:    word offset of the start of the array (default=auto)
    :readOnly:  registerarray is read-only (default=inherit from parent)
    :size:      number of words in the registerarray.  If provided must equal
                framesize * count (default=auto)
    :writeOnly: registerarray is write-only (default=inherit from parent)

Contains:

    - register
    - registerarray

register
++++++++

Required attributes:

    :name: register name
    
Optional attributes:
    
    :format:    register data format, from "bits", "signed", "unsigned"
                (default="bits")
    :offset:    word offset of the start of the register (default=auto)
    :readOnly:  register is read-only (default=inherit from parent)
    :size:      number of words in the register.  Currently only 1 is allowed.
                (default=1)
    :width:     number of bits in the register, if the register has no fields.
                Values must be less than or equal to the component word with.
                (default=component word width)
    :writeOnly: register is write-only (default=inherit from parent)
    
Contains:

    - field
    
field
+++++

Required attributes:

    :name: field name
        
Optional attributes:
    
    :format:    field data format, from "bits", "signed", "unsigned"
                (default="bits")
    :offset:    bit offset of the LSB of the field (default=auto)
    :readOnly:  register is read-only (default=inherit from parent)
    :size:      number of bits in the field (default=1)
    :width:     alias for *size*
    :writeOnly: register is write-only (default=inherit from parent)
    
Contains:

    - enum

enum
++++

Required attributes:

    :name: enumeration name
    
Optional attributes:
    
    :offset:    integer value of the enumeration (default=auto)
    :value:     alias for *offset*
    
MemoryMap Definition
--------------------
    
memorymap
+++++++++

Required attributes:

    :name: memorymap name
    
Optional attributes:
    
    :base: Base address of the entire map (default=0x80000000)
    
Contains:

    - instance
    
instance
++++++++

Required attributes:

    :name: instance name

Optional attributes:

    :extern: name of the component this is an instance of (default=instance name)
    :offset: offset from start of MemoryMap in bytes (default=auto)
