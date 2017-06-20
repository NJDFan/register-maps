=================
Basic VHDL Output
=================
    
This output makes no assumptions about what the bus type is, and expects
no support packages to be available.  Words below encased in <angle brackets>
are meant to represent a fill-in-the-blank of the name of that thing, so a
``tb_<REGISTERARRAY>`` would be ``tb_BUFFER`` for a RegisterArray named BUFFER.

Depending on the choice of names of things in the XML, it may be necessary to
change the names of things to avoid either illegal characters or VHDL reserved
words.  Check the header comments of the generated VHDL files for information
about changed elements.

Changed **names** indicate characters that were not legal VHDL, and will be
different in all contexts, illegal characters will be replaced with _ characters.

Changed **identifiers** mean only that they cannot be bare words, which means
they are only different in the context of something.*identifier*, such as 
registers in components or fields in registers.  Changed identifiers will get
an "_0" extension.

Types
=====

* subtype ``t_addr`` of integer
* subtype ``t_busdata`` of std_logic_vector, component width wide
* ``t_<REGISTER>``

  * subtype of std_logic_vector, unsigned, or signed OR
  * record if the register has fields
  
* record ``tb_<REGISTERARRAY>`` if the registerarray has multiple registers
* array ``ta_<REGISTERARRAY>`` of ``tb_<REGISTERARRAY>`` or ``t_<REGISTER>``
* record ``t_<COMPONENT>_regfile`` to hold the entire register file

Constants
=========

* ``<REGISTER>_ADDR`` word offsets from 0 for freestanding registers
* ``<REGISTER>_ADDR`` word offsets from array start in a registerarray
* ``<REGISTERARRAY>_BASEADDR`` offsets the same way REGISTER_ADDR does
* ``<REGISTERARRAY>_FRAMESIZE`` is the number of words in each array element
* ``<REGISTERARRAY>_FRAMECOUNT`` is the number of FRAMESIZE element in the array
* ``<REGISTERARRAY>_LASTADDR`` is the offset for the last word in the array
* ``<REGISTER>_<FIELD>_<ENUM>`` is a value for field <REGISTER>.<FIELD>
* ``RESET_t_<REGISTER>`` is the reset value constant for a ``t_<REGISTER>``
* ``RESET_ta_<REGISTERARRAY>`` is the reset value constant for a ``t_<REGISTERARRAY>``
* ``RESET_t_<COMPONENT>_REGFILE`` is the reset value for a ``t_<COMPONENT>_regfile``

Subprograms
===========

Addresses
---------

GET_ADDR rips the appropriate number of LSBs to make a word address from the
word address on the bus:

.. code:: vhdl

    function GET_ADDR(address: std_logic_vector) return t_addr;
    function GET_ADDR(address: unsigned) return t_addr;
  

Component
---------

Component level subprograms manipulate the entire ``t_<COMPONENT>_regfile``.  For
register files that will be implemented entirely on flip-flops this is probably
viable; to use block RAM as part or all of the storage will require 
some special casing around these functions.  Note that these functions are
unconditional; read-enable and write-enable functions should be implemented
by selectively calling or not calling them:

.. code:: vhdl

    procedure UPDATE_REGFILE(
        dat: in t_busdata; byteen : in std_logic_vector;
        offset: in t_addr;
        variable reg: inout t_<COMPONENT>_regfile;
        success: out boolean);
    procedure UPDATESIG_REGFILE(
        dat: in t_busdata; byteen : in std_logic_vector;
        offset: in t_addr;
        signal reg: inout t_<COMPONENT>_regfile;
        success: out boolean);
    procedure READ_REGFILE(
        offset: in t_addr;
        reg: in t_<COMPONENT>_regfile;
        dat: out t_busdata;
        success: out boolean);

UPDATE_REGFILE and UPDATESIG_REGFILE will update a single register based on the
address in *offset*.  The new data will be taken from *dat* on the byte lanes
selected by *byteen*, which should be 1/8 as long as dat.  Use UPDATE_REGFILE
if the register are stored in a variable, or UPDATESIG_REGFILE if they are
stored in a variable.  There probably aren't circumstances that warrant the 
use of both in the same design.  In either case, *success* is set true if the
write targeted a writeable register or false if not.

READ_REG gets the data from a single register based on the address in *offset*
and returns it in a proper format for the data bus.  *dat* is set with the data
that has been read and *success* is set true if the read targeted a readable
register or false if not.

RegisterArray
-------------

RegisterArray programs manipulate registers inside of a RegisterArray similarly
to those in a Component.  They're a bit of an odd duck in terms of high-level
vs. low-level accesses.  Primarily they exist to be called by the _REGFILE
routines; user use of them is mostly limited to knocking out a section of the
register map to be implemented separately on BRAMs.

For each registerarray in the design there are procedures:

.. code:: vhdl

    procedure UPDATE_<registerarray>(
        dat: in t_busdata; byteen : in std_logic_vector;
        offset: in t_addr;
        variable ra: inout ta_<registerarray>;
        success: out boolean);
    procedure UPDATESIG_<registerarray>(
        dat: in t_busdata; byteen : in std_logic_vector;
        offset: in t_addr;
        signal ra: inout ta_<registerarray>;
        success: out boolean);
    procedure READ_registerarray(
        offset: in t_addr;
        ra: in ta_<registerarray>;
        dat: out t_busdata;
        success: out boolean);

For all these procedures the *offset* parameter is relative to the baseaddress
of that registerarray, available as <REGISTERARRAY>_BASEADDR, not to the start
of the component.

Register
--------

The functions available for Registers are low-level access functions.  These
are usable directly by users either to supplement or entirely circumvent the
generated register decoding functions.  For each register there are subprograms:


.. code:: vhdl

    function DAT_TO_<register>(dat: t_busdata) return t_<register>;
    function <register>_TO_DAT(reg: t_<register>) return t_busdata;
    procedure UPDATE_<register>(
        dat: in t_busdata; byteen: in std_logic_vector;
        variable reg: inout t_<register>);
    procedure UPDATESIG_<register>(
        dat: in t_busdata; byteen: in std_logic_vector;
        signal reg: inout t_<register>);

DAT_TO_<REGISTER> turns the abstract data on the bus into the register data
type, which may be a simple type like a signed, unsigned, or std_logic_vector,
or may be a record of such types, in which case the bits will be translated to
the appropriate fields.  <REGISTER>_TO_DAT reverses this operation, filling
unused bits with '0'.

UPDATE_<REGISTER> and UPDATESIG_<REGISTER> update those bits of the register
data specified by the byte enable mask.  Bits where byteen='0' are unaltered.
Again, UPDATE_<REGISTER> is used if the register storage is a VHDL variable, 
and UPDATESIG_<REGISTER> if it is a signal.
