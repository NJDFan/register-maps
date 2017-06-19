"""
Generate Python header files from HTI XML register description documents.

The header files are based around ctypes and our bitfield module.

This program parses two different types of XML description file.
First, a file documenting a single component, and all of the
registers that it may contain.  Second, a file documenting an
overall memory map, which instantiates and calls out various
components.
"""

import textwrap
import datetime
import os
from ..visitor import Visitor
from ..util import Outputs

dedent = textwrap.dedent
wrapper = textwrap.TextWrapper(
    expand_tabs=False, replace_whitespace=True, drop_whitespace=True
)
wrapper4in = textwrap.TextWrapper(
    expand_tabs=False, replace_whitespace=True, drop_whitespace=True,
    initial_indent="    ", subsequent_indent="    "
)

@Outputs.register
class basic(Visitor):
    """Write out a Python file for a registermap.
    
    Data members
    ------------
    field_format
        dict indexed on HtiComponents that returns the named type of that
        field
    
    """
     
    outputname = 'python'
    extension = '.py'
    structurebase = "LittleEndianStructure"
    
    component_fileheader = dedent("""
    ##########################################################################
    {name} Register Map
    Defines the registers in the {name} component.
    
    {desc}
    
    Generated automatically from {source} on {time:%d %b %Y %H:%M}
    Do not modify this file directly.
    ##########################################################################
    """)
    
    memorymap_fileheader = dedent("""
    ##########################################################################
    {name} Peripheral Map
    Defines the registers in the {name} device.
    
    {desc}
    
    Generated automatically from {source} on {time:%d %b %Y %H:%M}
    Do not modify this file directly.
    ##########################################################################
    """)
    
    imports = dedent("""
    from ctypes import *
    from bitfield import *
    """)
    
    structtemplate = dedent('''
        class {name}({base}):
            """
        {docstring}
            """
            _pack_ = 1
        
        {name}._fields_ = ['''
    )
    
    def begin(self, startnode):
        self.field_format = {}
    
    def printheader(self, node, template):
        header = template.strip().format(
            name = node.name,
            desc = '\n\n'.join(wrapper.fill(d) for d in node.description),
            source = node.sourcefile,
            time = datetime.datetime.now(),
        )
        for line in header.splitlines():
            preamble = '##' if line.startswith('#') else '# '
            self.print(preamble, line, sep='')
            
    def printstruct(self, node, name=None):
        if name is None:
            name = node.name
            
        # Boilerplate first
        self.printf(self.structtemplate,
            name = name,
            docstring = '\n\n'.join(wrapper4in.fill(d) for d in node.description),
            base = self.structurebase
        )
        # Then fields
        for obj, start, size in node.space:
            if obj:
                fmt = self.field_format[obj]
                self.printf('    ("{}", {}),', obj.name, fmt)
            else:
                self.printf('    ("_dummy{}", {}*{}),', start, self.filltype, size)
        # And finish up
        self.print(']')
        
    def visit_Component(self, node):
        """Print out a file for a Component."""
        self.printheader(node, self.component_fileheader)
        self.print(self.imports)
        
        filltype = 'c_uint{}'.format(node.width)
        
        with self.tempvars(filltype = filltype, regwidth=node.width):
            self.visitchildren(node)
            self.printstruct(node)
        self.printf('assert sizeof({})=={}', node.name, node.size * node.width // 8)
    
    def visit_RegisterArray(self, node):
        """Print out the definition for a RegisterArray."""
        
        # Generate all of the subtypes
        self.visitchildren(node)
        
        mytype = '_ta_' + node.name
        
        if (node.space.itemcount == 1):
            # Save a type by not creating a new structure
            child, _, _ = next(node.space.items())
            basetype = self.field_format[child]
        else:
            # Need a structure.  Start with the boilerplace.
            basetype = '_tb_' + node.name
            self.printstruct(node, name=basetype)
            self.printf('assert sizeof({})=={}', basetype, node.framesize * node.width // 8)
            
        self.printf('{} = {}*{}'.format(mytype, basetype, node.count))
        self.field_format[node] = mytype
        
    def visit_Register(self, node):
        """Print out the bitfield definitions for a Register."""
        
        if node.space:
            # There are fields in this, so we need to generate a Bitfield
            mytype = '_t_' + node.name
            self.field_format[node] = mytype
            
            self.printf('# {} Bitfield', mytype)
            self.print('_fields=[', end='')
            for child, start, size in node.space:
                if child:
                    if size == 1:
                        fmt = 'c_bool'
                    elif child.format == 'signed':
                        fmt = 'c_int'
                    else:
                        fmt = 'c_uint'
                    self.print('("{}", {}, {}),'.format(child.name, fmt, size), end='')
                else:
                    self.print('("_dummy{}", c_uint, {}),'.format(start, size), end='')
            self.print(']')
                
            self.print('_docstring=(r"""')
            for d in node.description:
                self.print(d)
            self.print('""").strip()')
            self.printf('{name}=make_bf("{name}", _fields, {base}, _docstring)',
                name = mytype, base=self.filltype
            )
            
            with self.tempvars(register=mytype):
                self.visitchildren(node)
                
        else:
            # No fields, just note what is is.
            if node.format == 'signed':
                self.field_format[node] = 'c_int{}'.format(self.regwidth)
            else:
                self.field_format[node] = 'c_uint{}'.format(self.regwidth)

    def visit_Field(self, node):
        """Push down to the enums."""
        with self.tempvars(field=node.name):
            self.visitchildren(node)
        
    def visit_Enum(self, node):
        """Print enumeration values."""
        
        self.printf("{}.{}_{}={}", self.register, self.field, node.name, node.value)

    def visit_MemoryMap(self, node):
        """Create a struct representing the entire memory map."""
        self.printheader(node, self.memorymap_fileheader)
        self.print(self.imports)
        
        # We need additional imports for all of the components here.
        collector = ImportCollector(output=self.output)
        collector.execute(node)
        
        # Go fetch me some field names.
        with self.tempvars(filltype = 'c_uint8', regwidth=1):
            self.visitchildren(node)
            self.printstruct(node)
        self.printf('assert sizeof({})=={}', node.name, node.size)
        
    def visit_Instance(self, node):
        self.field_format[node] = node.extern
        
class ImportCollector(Visitor):
    """Collect imports of other local modules for a MemoryMap."""
    
    def begin(self, startnode):
        self.seen = set()
    
    def visit_MemoryMap(self, node):
        self.visitchildren(node)
        
    def visit_Instance(self, node):
        component = node.extern 
        if component not in self.seen:
            self.seen.add(component)
            self.printf("from .{0} import {0}", component)
