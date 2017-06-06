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
    if element.size == 1:
        return 'std_logic'
    
    fmt = {
        'bits' : 'std_logic_vector',
        'signed' : 'signed',
        'unsigned' : 'unsigned'
    }[element.format]
    
    if index:
        return '{0}({1} downto 0)'.format(basetype, element.size-1)
    else:
        return basetype

class RegisterAddresses(Visitor):
    """Outputs register addresses for a PackageHeader."""
    
    addresstype = 't_addr'
    
    def constant(self, name, val):
        self.printf('constant {}: {} := 16#{:03X}#;',
            name, self.addresstype, val
        )
    
    def begin(self, startnode):
        self.print('-' * 20, 'Register Addresses', '-' * 20)
        self.printf('subtype {} is integer range 0 to {};',
            self.addresstype, startnode.size-1
        )
        
    def visit_Component(self, node):
        for obj, start, size in node.space.items():
            self.visit(obj)
            
    def visit_Register(self, node):
        self.constant(node.name, node.offset)
        
    def visit_RegisterArray(self, node):
        self.constant(node.name+'_BASEADDR', node.offset)
        self.constant(node.name+'_LASTADDR', node.offset+node.size-1)
        self.constant(node.name+'_FRAMESIZE', node.framesize)
        for obj, start, size in node.space.items():
            self.visit(obj)
            
class RegisterTypeComments(Visitor):
    """Output register type comments for a RegisterTypes"""
    
    def visit_Register(self, node):
        # Start by commenting on the register.
        self.print(comment.fill(node.name))
        for d in node.description:
            self.print(comment.fill(d))
            
        if node.space:
            self.print(comment.fill('Defined fields:'))
            self.print(comment.fill('---------------'))
            items = reversed(list(node.space.items()))
            for obj, start, size in items:
                self.visit(obj)
                
    def visit_Field(self, node):
        if len(node.description) == 0:
            self.print(comment.fill(node.name))
            return

        graf = copy(comment)
        graf.subsequent_indent = '--   ' + ' ' * len(node.name)
        it = iter(node.description)
        first = '{} = {}'.format(node.name, next(it))
        self.print(graf.fill(first))
        
        graf.first_indent = graf.subsequent_indent
        for d in it:
            self.print(graf.fill(d))
            
class RegisterTypeTypes(Visitor):
    """Output register types for a RegisterTypes"""
    
    def visit_Register(self, node):
        self.typename = 't_' + node.name
        
        if node.space:
            # This register has fields.  Implement it as a record.
            self.printf('type {} is record', self.typename)
            self.visitchildren(node)
            self.printf('end record {};', self.typename)
    
    def visit_Field(self, node):
        regtype = register_format(node)
        self.printf('    {}: {};'.format(node.name, regtype))
            
class RegisterTypes(Visitor):
    """Output register type section for a PackageHeader"""
    
    def begin(self, startnode):
        self.regtypes = {}
        self.print('-' * 20, 'Register Types', '-' * 20)
        
    def visit_Component(self, node):
        for obj, start, size in node.space.items():
            self.visit(obj)
            
    def visit_Register(self, node):
        RegisterTypeComments(self.output, node)
        RegisterTypeTypes(self.output, node)
        
    def visit_RegisterArray(self, node):
        
        # If there's only type of register in the array we can cheat on all
        # the type making.
        if len(register_types) == 1:
            basetype = register_types[0]
        else:
            basetype = 'tb_' + node.name
            self.printf('type {} is record', basetype)
            self.visitchildren(node)
            self.printf('end record {};', typename)
        
class PackageHeader(Visitor):

    def visit_Component(self, node):
        self.pkgname = 'pkg_' + node.name.lower()
        
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
        
        self.print(header.format(
            name = node.name,
            desc = '\n\n'.join(wrapper.fill(d) for d in node.description),
            source = node.sourcefile,
            time = datetime.datetime.now(),
            pkg = self.pkgname,
            bar = CBAR
        ))
        
        RegisterAddresses(self.output, node)
        RegisterTypes(self.output, node)
        
class old(Visitor):
    
    def visit_Component(self, node):
        PackageHeader(self.output, node)
        
    def visit_MemoryMap(self, node):
        pass
    
