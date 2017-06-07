"""Translate XML register definitions into VHDL."""

# There's a real challenge in all this code in making it all clean.  Ideally
# everything we do in here could be implemented by Visitors calling Visitors
# endlessly all the way down the line, and no ancillary data structures.  This
# is conceptually clean, but in practice means
#   a) a LOT of walks through the same tree; and
#   b) that the code is never linear, it all winds up scattered through a
#       hundred small classes doing small things.
#
# Ancillary structures help with this, but make everything ad-hoc where they're
# used.  So I've tried to strike a balance here of using ad-hoc structures to
# do simple things while allowing Visitors to do the more complex work, but
# that balance is definitely more art than science.

import textwrap
import datetime
from . import xml_parser
from .visitor import Visitor

dedent = textwrap.dedent
wrapper = textwrap.TextWrapper(
    expand_tabs=False, replace_whitespace=True, drop_whitespace=True
)

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

class basic(Visitor):
    
    extension = '.vhd'
    
    component_fileheader = dedent("""
    ------------------------------------------------------------------------
    {name} Register Map
    Defines the registers in the {name} component.
    
    {desc}
    
    Generated automatically from {source} on {time:%d %b %Y %H:%M}
    Do not modify this file directly.
    ----------------------------------------------------------------------
    """)
    
    use_packages = [
        'ieee.std_logic_1164.all',
        'ieee.numeric_std.all'
    ]

    package_header = "package {pkg} is"
    
    package_split = dedent("""
    end package {pkg};
    ------------------------------------------------------------------------
    package body {pkg} is
    """)
    
    package_footer = "end package body {pkg};\n"
    
    def printheader(self, node, template):
        header = template.strip().format(
            name = node.name,
            desc = '\n\n'.join(wrapper.fill(d) for d in node.description),
            source = node.sourcefile,
            time = datetime.datetime.now(),
            pkg = self.pkgname
        )
        for line in header.splitlines():
            preamble = '----' if line.startswith('-') else '--  '
            self.print(preamble, line, sep='')
        
    def printlibraries(self):
        packages = sorted(self.use_packages)
        lib = None
        for p in packages:
            newlib = p.split('.', maxsplit=1)[0]
            if newlib != lib:
                lib = newlib
                if lib != 'work':
                    self.printf('library {};', lib)
            self.printf('use {};', p)
    
    def visit_Component(self, node):
        self.pkgname = 'pkg_' + node.name
        self.printheader(node, self.component_fileheader)
        self.print()
        self.printlibraries()
        self.print()
        
        self.printf(self.package_header, pkg=self.pkgname)
        
        addr = GenerateAddresses(self.output, node)
        types = GenerateTypes(self.output, node)
        
        self.printf(self.package_split, pkg=self.pkgname)
        
        addr.printbody()
        types.printbody()
        
        self.printf(self.package_footer, pkg=self.pkgname)
        
    def visit_MemoryMap(self, node):
        pass
    
    
class GenerateAddresses(Visitor):
    """Go through the HtiComponent tree generating address constants.
    
    Outputs them immediately for the package declaration.  Keeps track
    of additional information which can be output later by calling printbody()
    """
    
    def begin(self, startnode):
        self.body = []
    
    def visit_Component(self, node):
        at = self.addrtype = 't_addr'
        maxaddr = self.maxaddr = node.size - 1
        self.print('---------- Address Constants ----------')
        self.printf('subtype {} is integer range 0 to {};', at, maxaddr)
        
        self.visitchildren(node)
        self.print('function GET_ADDR(address: std_logic_vector) return t_addr;')
        self.print('function GET_ADDR(address: unsigned) return t_addr;')
        self.print()
        
        addrbits = maxaddr.bit_length()
        high = addrbits - 1;
        self.body.append(dedent("""
            function GET_ADDR(address: std_logic_vector) return addrtype is
                variable normal : std_logic_vector(address'length-1 downto 0);
            begin
                normal := address;
                return TO_INTEGER(UNSIGNED(normal({high} downto 0)));
            end function GET_ADDR;
            
            function GET_ADDR(address: unsigned) return {addrtype} is
            begin
                return TO_INTEGER(address({high} downto 0));
            end function GET_ADDR;
            """).format(addrtype=at, high=high)
        )
    
    def visit_RegisterArray(self, node):
        consts = (
            ('_BASEADDR', node.offset),
            ('_LASTADDR', node.offset+node.size-1),
            ('_FRAMESIZE', node.framesize)
        )
        for name, val in consts:
            self.printaddress(node.name+name, val)
        self.visitchildren(node)
        
    def visit_Register(self, node):
        self.printaddress(node.name+'_ADDR', node.offset)
        
    def visit_MemoryMap(self, node):
        pass
        
    def printaddress(self, name, val):
        self.printf('constant {}: {} := {};', name, self.addrtype, val)
    
    def printbody(self):
        """Output things for the package body."""
        
        for b in self.body:
            self.print(b)

class GenerateTypes(Visitor):
    """Go through the HtiComponent tree generating register types.
    
    Immediately outputs:
    - Register types
    - Register array types
    - Enumeration constants
    - Data/register conversion function headers
    
    Defers to the body:
    - Data/register conversion function bodies
    
    """
    
    def begin(self, startnode):
        self.body = []
    
    def namer(self, node):
        """Returns the appropriate type name for a given node."""
        if isinstance(node, xml_parser.Register):
            return 't_' + node.name
        elif isinstance(node, xml_parser.RegisterArray):
            return 'ta_' + node.name
        else:
            raise TypeError('unable to name {}', type(node).__name__)
    
    def visit_Component(self, node):
        """Provide the header for the component-level file."""
        
        self.print('---------- Register Types ----------')
        self.printf('subtype t_busdata is std_logic_vector({} downto 0);', node.width-1)
        self.visitchildren(node)
        self.print()
        
    def visit_RegisterArray(self, node):
        """Generate the array type and, if necessary, a subsidiary record."""
        
        # First define the register types.
        self.visitchildren(node)
        
        # Now we can define the array type.
        fields = [
            (child.name, self.namer(child))
                for child, _, _ in node.space.items()
        ]
        if len(fields) == 1:
            # Don't make a structured type from this array.
            basename = fields[0][1]
        else:
            basename = 'tb_' + node.name
            self.printf('type {} is record', basename)
            for fn, ft in fields:
                self.printf('    {}: {};'.format(fn, ft))
            self.printf('end record {};', basename)
                    
        self.printf('type {} is array({} downto 0) of {};',
            self.namer(node), node.size-1, basename
        )
        self.print()
        
    def visit_Register(self, node):
        """Generate the register type, enumerations, and access
        function prototypes.
        
        Store access function bodies for later.
        """
        
        with self.tempvars(
            registername=node.name,
            enumlines=[], tolines=[], fromlines=[],
            tofn = 'DAT_TO_{}'.format(node.name),
            fromfn = '{}_TO_DAT'.format(node.name),
            ):
                
            if node.space:
                self.complexRegister(node)
            else:
                self.simpleRegister(node)
            
            params = {
                'to' : self.tofn,
                'from' : self.fromfn,
                'type' : self.namer(node)
            }
            self.printf('pure function {to}(dat : t_busdata) return {type};', **params)
            self.printf('pure function {from}(dat : {type}) return t_busdata;', **params)
            self.print()

    def simpleRegister(self, node):
        """Generate a simple (basetype) register.  node is a Register"""
        
        typename = self.namer(node)
        self.printf('subtype {} is {};', typename, register_format(node))
            
        # Build up access function bodies.
        params = {
            'to' : 'DAT_TO_{}'.format(node.name),
            'from' : '{}_TO_DAT'.format(node.name),
            'type' : typename,
            'name' : node.name,
            'high' : node.width-1
        }
        
        self.body.append(dedent("""
            ---- {name} ----
            pure function {to}(dat : t_busdata) return {type} is
            begin
                return {type}(dat({high} downto 0));
            end function {to};
            
            pure function {from}(dat : {type}) return t_busdata is
                variable ret: t_busdata;
            begin
                ret({high} downto 0) := STD_LOGIC_VECTOR(dat);
                return ret;
            end function {from};"""
            ).format(**params))
                    
    def complexRegister(self, node):
        """Generate a complex (record) register.  node is a Register"""
        
        typename = self.namer(node)
        self.printf('type {} is record', typename)
        self.visitchildren(node)
        self.printf('end record {};', typename)
        
        # Print out constants for any enumerated fields.
        for e in self.enumlines:
            self.print(e)
        
        # Build up access function bodies.
        params = {
            'to' : 'DAT_TO_{}'.format(node.name),
            'from' : '{}_TO_DAT'.format(node.name),
            'type' : typename,
            'name' : node.name,
            'width' : node.width,
            'tolines' : ',\n'.join(self.tolines),
            'fromlines' : '\n'.join(self.fromlines)
        }
        self.body.append(dedent("""
            ---- {name} ----
            pure function {to}(dat : t_busdata) return {type} is
            begin
                return {type}'(
            {tolines}
                );
            end function {to};
            
            pure function {from}(dat : {type}) return t_busdata is
                variable ret: t_busdata;
            begin
            {fromlines}
                return ret;
            end function {from};"""
            ).format(**params))
                    
    def visit_Field(self, node):
        # If we're hitting a Field we must be inside a Register
        # record definition.  We can output for the record now, but must
        # defer the lines for the function bodies until later.
        
        with self.tempvars(field=node, fieldtype=register_format(node)):
            self.printf('    {}: {};', node.name, self.fieldtype)
            
            conversion = register_format(node, index=False).upper()
            params = {
                'fn' : conversion,
                'high' : node.size+node.offset-1,
                'low' : node.offset,
                'field' : node.name
            }
                
            if conversion == 'STD_LOGIC':
                t = '        {field} => dat({high})'
                f = '    ret({high}) := dat.{field};'
            else:
                t = '        {field} => {fn}(dat({high} downto {low}))'
                f = '    ret({high} downto {low}) := STD_LOGIC_VECTOR(dat.{field});'
            self.tolines.append(t.format(**params))
            self.fromlines.append(f.format(**params))
            self.visitchildren(node)
        
    def visit_Enum(self, node):
        # Enumeration values are deferred until later.
        enumname = self.registername + '_' + self.field.name + '_' + node.name
        self.enumlines.append(
            'constant {}: {} := "{:0{}b}";'.format(
                enumname, self.fieldtype, node.value, self.field.width
        ))
            
    def visit_MemoryMap(self, node):
        pass
        
    def printbody(self):
        """Output things for the package body."""
        
        for b in self.body:
            self.print(b)
