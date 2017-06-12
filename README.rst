=============
register-maps
=============

Use XML files to describe register maps; auto-generate C, VHDL, Python, and HTML.

Execution
=========

After installing the package, the main executable is a program called
registermap.

Given source XML files in ./data/src you would run::

    registermap vhdl.basic data/src --output output/vhdl
    registermap html.basic data/src --output output/html
    
And so on.


XML Elements
============

Additionally, all elements other than Description have required name attribute.

Component
---------

- Required

    
    name
        Component name.
        
    width
        number of bits per word (required)
        
- Optional

    size
        number of words in the component (default = auto)
        
    readOnly
        Component default is read-only (default false)
        
    writeOnly
        Component default is write-only (default false)

Register
--------

- Required
    
    name
        Register name
        
- Optional:

    offset
        Word offset into component or array (default = auto)
        
    size
        number of words (default = 1)
        
    width
        number of bits (default = inherit).
        Used only when creating a register with a single, smaller field,
        such as a 24-bit register in a 32-bit component
        
    readOnly
        Register is read-only (default = inherit)
        
    writeOnly
        Register is write-only (default = inherit)
        
    format
        Format if Register has no fields
        (from “signed, unsigned, bits”, default = bits)

Field
-----

- Required

    name
        Name of the field
        
- Optional

    offset
        index of the LSB of the field (default = auto)
        
    size
        number of bits (default = 1)
        
    readOnly
        Field is read-only (default = inherit)
        
    writeOnly
        Field is write-only (default = inherit)
        
    format
        Format of the field
        (from “signed, unsigned, bits”, default = bits)

Enum
----

- Required

    name
        Name of the enumeration value
    
- Optional

    value
        Integer value of the enumeration (default = auto)

MemoryMap
---------

- Required

    name
        Name of the map
        
    base
        address of the start of the memory map (typically “0x80000000”)

Instance
--------

- Required

    name
        name of this instance
        
    extern
        name of the Component to bind here on the map
        
- Optional

    offset
        offset from start of MemoryMap in bytes (default = auto)
    
All types may also have as many Description elements as they would like.
Each Description element encloses one paragraph of plain text that
provides descriptive information about the enclosing element.

Components contain Registers contain Fields contain Enums.
MemoryMaps contain Instances, which bind to Components through their extern attribute.

Registers, Fields, and Instances may also be displaced by a RegisterArray,
FieldArray, or InstanceArray, respectively.  In all cases:

(Register|Field|Instance)Array
------------------------------

- Required
    
    count
        number of times to repeat the contents
    
- Optional

    name
        Array name
        (can be skipped if only one element is contained)
        
    offset
        offset of the first element contained, default = auto
        
    framesize
        The difference, in words, between duplications of a given
        register.  (default = auto)
