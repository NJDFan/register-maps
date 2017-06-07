"""Translate XML register definitions into VHDL."""

from copy import copy
import textwrap
import datetime
from .visitor import Visitor

dedent = textwrap.dedent
wrapper = textwrap.TextWrapper(
    expand_tabs=False, replace_whitespace=True, drop_whitespace=True
)
comment = textwrap.TextWrapper(
    expand_tabs=False, replace_whitespace=True, drop_whitespace=True,
    initial_indent = '--  ', subsequent_indent = '--  '
)
   
CBAR = '-' * 78

def register_format(element, index=True):
    if element.width == 1:
        return 'std_logic'
    
    fmt = {
        'bits' : 'std_logic_vector',
        'signed' : 'signed',
        'unsigned' : 'unsigned'
    }[element.format]
    
    if index:
        return '{0}({1} downto 0)'.format(fmt, element.width-1)
    else:
        return fmt
        
class Record:
    """Represents a VHDL record type."""
    
    def __init__(self, name):
        self.name = name
        self.fields = []
    
    def add(self, field, typename):
        self.fields.append((field, typename))
        
    def lines(self):
        yield 'type {} is record'.format(self.name)
        for field, typename in self.fields:
            yield '    {}: {};'.format(field, typename)
        yield 'end record {};'.format(self.name)
        
    def __str__(self):
        return '\n'.join(self.lines())
        
class Subtype:
    """Represents a VHDL subtype."""
    
    def __init__(self, subtypename, actual):
        self.name = subtypename
        self.actual = actual
        
    def __str__(self):
        return 'subtype {} is {};'.format(self.name, self.actual)
        
class Array:
    """Represents a VHDL array type."""
    
    def __init__(self, typename, basetype, left, right):
        self.name = typename
        self.base = basetype
        self.left = left
        self.right = right

    def __str__(self):
        return 'type {} is array({} {} {}) of {};'.format(
            self.name,
            self.left, 'downto' if self.left > self.right else 'to', self.right,
            self.base
        )
     
class AddressConstant:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        
    def __str__(self):
        return 'constant {}: t_addr := {};'.format(self.name, self.value)
        
class VhdlStructures(Visitor):
    """Turn the register map document into a set of abstract VHDL structures."""
    
    def begin(self, startnode):
        self.constants = []
        self.types = []
        
        self.recordstack = []
        
    @property
    def activerecord(self):
        if self.recordstack:
            return self.recordstack[-1]
        return None
        
    def visit_Component(self, node):
        self.visitchildren(node)
        
    def visit_Register(self, node):
        self.constants.append(AddressConstant(node.name, node.offset))
        
        # TODO: Handle registers of size > 1
        if node.size > 1:
            raise ValueError("unable to handle registers greater than 1 word")
        
        typename = 't_' + node.name
        
        # Handle possible record types for this register.
        if node.space:
            self.recordstack.append(Record(typename))
            self.visitchildren(node)
            self.types.append(self.recordstack.pop())
            
        else:
            fmt = register_format(node)
            self.types.append(Subtype(typename, fmt))
            
        # Handle the record this might be in
        if self.activerecord:
            self.activerecord.add(node.name, typename)
            
    def visit_RegisterArray(self, node):
        consts = (
            ('_BASEADDR', node.offset),
            ('_LASTADDR', node.offset+node.size-1),
            ('_FRAMESIZE', node.framesize)
        )
        for suffix, val in consts:
            self.constants.append(AddressConstant(node.name+suffix, val))
        
        items = list(node.space.items())
        if len(items) == 1:
            # Shortcut the types
            obj = items[0].obj
            basetype = 't_' + items[0].obj.name
            self.visit(obj)
        else:
            # Have to build a record for the array type
            basetype = 'tb_' + node.name
            self.recordstack.append(Record(basetype))
            self.visitchildren(node)
            self.types.append(self.recordstack.pop())
            
        typename = 'ta_' + node.name
        self.types.append(Array(typename, basetype, node.count-1, 0))
        
    def visit_Field(self, node):
        pass
        
class old(Visitor):
    
    def visit_Component(self, node):
        structures = VhdlStructures(self.output, node)
        
        header = dedent("""
        {bar}
        {name} Register Map
        Defines the registers in the {name} component.
        
        {desc}
        
        Generated automatically from {source} on {time:%d %b %Y %H:%M}
        Do not modify this file directly.
        {bar}
        
        library IEEE;
        use IEEE.STD_LOGIC_1164.all;
        use IEEE.NUMERIC_STD.all;
        use IEEE.STD_LOGIC_MISC.all;
            
        use work.pkg_global.all;

        package {pkg} is
        """)
        
        pkgname = 'pkg_' + node.name
        self.printf(header,
            name = node.name,
            desc = '\n\n'.join(wrapper.fill(d) for d in node.description),
            source = node.sourcefile,
            time = datetime.datetime.now(),
            pkg = pkgname,
            bar = CBAR
        )
        
        self.print('-' * 20, 'Register Addresses', '-' * 20)
        for c in structures.constants:
            print(c)
        
        self.print()
        self.print('-' * 20, 'Register Types', '-' * 20)
        for c in structures.types:
            print(c)
        
        self.print()
        self.printf('end package {}', pkgname)
        
    def visit_MemoryMap(self, node):
        pass
    
