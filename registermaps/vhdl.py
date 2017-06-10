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

wrapper = textwrap.TextWrapper(
    expand_tabs=False, replace_whitespace=True, drop_whitespace=True
)

def dedent(text):
    """Unindents a triple quoted string, stripping up to 1 newline from
    each edge."""
    
    if text.startswith('\n'):
        text = text[1:]
    if text.endswith('\n'):
        text = text[:-1].rstrip('\t ')
    return textwrap.dedent(text)

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

#######################################################################
# Helper visitors
#######################################################################
    
class GenerateAddressConstants(Visitor):
    """Print address constants into the package header."""
        
    def begin(self, startnode):
        self.body = []
    
    def visit_Component(self, node):
        maxaddr = node.size - 1
        self.print('---------- Address Constants ----------')
        self.printf('subtype t_addr is integer range 0 to {};', maxaddr)
        
        self.visitchildren(node)
        self.print('function GET_ADDR(address: std_logic_vector) return t_addr;')
        self.print('function GET_ADDR(address: unsigned) return t_addr;')
        
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
        self.printf('constant {}: t_addr := {};', name, val)

class GenerateTypes(Visitor):
    """Go through the HtiComponent tree generating register types.
    
    Immediately outputs:
    - Register types
    - Register array types
    - Enumeration constants
    
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
        
        # First define all the registers and registerarrays
        self.visitchildren(node)
        
        # Now create a gestalt structure for the entire register file.
        self.printf('type t_{}_regfile is record', node.name)
        for child, _, _ in node.space.items():
            self.printf('    {}: {};', child.name, self.namer(child))
        self.printf('end record t_{}_regfile;', node.name)
        
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
        """Generate the register types and enumeration constants."""
        if node.space:
            # We're a complex register
            with self.tempvars(enumlines=[], registername=node.name):
                self.printf('type t_{name} is record', name=node.name)
                self.visitchildren(node)
                self.printf('end record t_{name};', name=node.name)
            
                for line in self.enumlines:
                    self.print(line)
        
        else:
            # We're a simple register
            self.printf('subtype t_{name} is {fmt}({H} downto 0);',
                name=node.name,
                fmt = register_format(node),
                H = node.width-1
            )
                    
    def visit_Field(self, node):
        """Generate record field definitions, and gather enumeration constants."""
        
        with self.tempvars(field=node, fieldtype=register_format(node)):
            self.printf('    {}: {};', node.name, self.fieldtype)
            self.visitchildren(node)
        
    def visit_Enum(self, node):
        """Push enumeration values into the enum list."""
        
        enumname = self.registername + '_' + self.field.name + '_' + node.name
        self.enumlines.append(
            'constant {}: {} := "{:0{}b}";'.format(
                enumname, self.fieldtype, node.value, self.field.width
        ))
            
    def visit_MemoryMap(self, node):
        pass

class GenerateFunctionDeclarations(Visitor):
    """Print function declaration statements for the package header."""
    
    def visit_Component(self, node):
        self.print('---------- Accessor Functions ----------')
        self.visitchildren(node)
            
    def visit_RegisterArray(self, node):
        self.visitchildren(node)
    
    def visit_Register(self, node):
        # Register access functions
        self.printf(dedent("""
            function DAT_TO_{name}(dat: t_busdata) return t_{name};
            function {name}_TO_DAT(reg: t_{name}) return t_busdata;
            procedure UPDATE_{name}(
                dat: in t_busdata; byteen: in std_logic_vector;
                variable reg: inout t_{name}));
            procedure UPDATESIG_{name}(
                dat: in t_busdata; byteen: in std_logic_vector;
                signal reg: inout t_{name}));
            """), name=node.name
        )
        
        
class GenerateFunctionBodies(Visitor):
    def visit_Component(self, node):
        self.print('---------- Accessor Functions ----------')
        self.visitchildren(node)
            
    def visit_RegisterArray(self, node):
        self.visitchildren(node)
        
    def visit_Register(self, node):
        # Register access function bodies.
        self.printf(dedent("""
            ---- {name} ----
            function DAT_TO_{name}(dat: t_busdata) return t_{name} is
            begin"""), name=node.name
        )
        GenerateD2R(self.output).execute(node)
        self.printf(dedent("""
            end function DAT_TO_{name};
            
            function {name}_TO_DAT(reg: t_{name}) return t_busdata is
                variable ret: t_busdata := (others => '0');
            begin"""), name=node.name
        )
        GenerateR2D(self.output).execute(node)
        self.printf(dedent("""
                return ret;
            end function {name}_TO_DAT;
            
            procedure UPDATE_{name}(
                dat: in t_busdata; byteen: in std_logic_vector;
                variable reg: inout t_{name}) is
            begin"""), name=node.name
        )
        GenerateRegUpdate(self.output).execute(node)
        self.printf(dedent("""
            end procedure UPDATESIG_{name};
            
            procedure UPDATESIG_{name}(
                dat: in t_busdata; byteen: in std_logic_vector;
                signal reg: inout t_{name}) is
                
                variable r : t_{name};
            begin
                r := reg;
                UPDATE_{name}(dat, byteen, r);
                reg <= r;
            end procedure UPDATESIG_{name};
            """), name=node.name
        )

class RegisterFunctionGenerator(Visitor):
    """ABC for function body iterator builders."""
    
    def visit_Register(self, node):
        if node.space:
            return self.complexRegister(node)
        else:
            return self.simpleRegister(node)
     
class GenerateD2R(RegisterFunctionGenerator):
    """Iterable of lines for the function body for DAT_TO_register."""
     
    def simpleRegister(self, node):
        if node.width == 1:
            line = '    return {fmt}(dat(0));'
        else:
            line = '    return {fmt}(dat({high} downto 0));'
        self.printf(line,
            name=node.name, fmt=register_format(node, False).upper(),
            high=node.width-1
        )
        
    def complexRegister(self, node):
        childlines = ',\n'.join(
            '        ' + line 
                for line in self.visitchildren(node)
        )
        self.printf(dedent("""
            return (
        {childlines}
            );"""),
            name=node.name, childlines=childlines
        )
        
    def visit_Field(self, node):
        """Return field lines."""
        if node.width == 1:
            line = '{name} => dat({high})'
        else:
            line = '{name} => {fmt}(dat({high} downto {low}))'
        return line.format(
            name=node.name, fmt=register_format(node, False).upper(),
            high=node.offset+node.width-1, low=node.offset
        )
        
class GenerateR2D(RegisterFunctionGenerator):
    """Iterable of lines for the function body for register_TO_DAT."""
    
    def simpleRegister(self, node):
        if node.width == 1:
            line = '    ret(0) := reg.{name};'
        else:
            line = '    ret({high} downto 0) := STD_LOGIC_VECTOR(reg.{name});'
        self.printf(line, name=node.name, high=node.width-1)
        
    def complexRegister(self, node):
        self.visitchildren(node)
    
    def visit_Field(self, node):
        if node.width == 1:
            line = '    ret({high}) := reg.{name};'
        else:
            line = '    ret({high} downto {low}) := STD_LOGIC_VECTOR(reg.{name});'
        self.printf(line,
            name=node.name, high=node.offset+node.width-1, low=node.offset
        )
        
class GenerateRegUpdate(RegisterFunctionGenerator):
    """Iterable of lines for the function body for UPDATE_register."""
    
    def simpleRegister(self, node):
        fmt = register_format(node, False).upper()
        for bit, start in enumerate(range(0, node.width, 8)):
            end = min(start+7, node.width)
            if start == end:
                line = 'reg({L}) := dat({L});'
            else:
                line = 'reg({H} downto {L}) := {fmt}(dat({H} downto {L}));'
            
            self.printf('    if byteen({}) then', (bit))
            self.printf('        ' + line, fmt = fmt, H = end, L = start)
            self.print( '    end if;')
            
    def complexRegister(self, node):
        for bit, start in enumerate(range(0, node.width, 8)):
            subspace = node.space[start:start+8]
            if not any(obj for obj, _, _ in subspace):
                continue
                
            self.printf('    if byteen({}) then', bit)
            for obj, start, size in subspace:
                if not obj:
                    continue
                if size > 1 or obj.size > 1:
                    # This field is indexable.
                    line = 'reg.{name}({fh} downto {fl}) := {fmt}(dat({dh} downto {dl}));'
                else:
                    # This field is a bit.
                    line = 'reg.{name} := dat({dl});'
                self.printf('        ' + line,
                    fh = start+size-1-obj.offset,
                    fl = start-obj.offset,
                    dh = start+size-1,
                    dl = start,
                    fmt = register_format(obj, False).upper(),
                    name=obj.name
                )
            self.print( '    end if;')

#######################################################################
# Main visitors
#######################################################################

class basic(Visitor):
    """Basic VHDL output.
    
    This output makes no assumptions about what the bus type is, and expects
    no support packages to be available.
    """
    
    component_generation = dedent("""
    Types
    =====
    * subtype t_addr of integer
    * subtype t_busdata of std_logic_vector, component width wide
    * t_{register}
      * subtype of std_logic_vector, unsigned, or signed OR
      * record if the register has fields
    * record tb_{registerarray} if the registerarray has multiple registers
    * array ta_{registerarray} of tb_{registerarray} or t_{register}
    * record t_{component}_regfile to hold the entire register file
    
    Constants
    =========
    * {registername}_ADDR word offsets from 0 for freestanding registers
    * {register}_ADDR word offsets from array start in a registerarray
    * {registerarray}_BASEADDR offsets the same way {register}_ADDR does
    * {registerarray}_FRAMESIZE is the number of words in each array element
    * {registerarray}_LASTADDR is the offset for the last word in the array
    * {register}_{field}_{enum} is a value for field {register}.{field}
    
    Public Subprograms
    ==================
    * function GET_ADDR(std_logic_vector or unsigned) return t_addr
      
      Rips the appropriate number of LSBs to make a word address from.
      
    * function DAT_TO_{register}(dat: t_busdata) return t_{register}
    
      Takes the correct bits from the bus data and translates them into the
      basic or record type for the register.  Used for bus writes.
      
    * function {register}_TO_DAT(reg: t_{register}) return t_busdata
    
      Takes the bits from the basic or record type for the register and puts
      them together into a bus word.  Unused bits are 0.  Used for bus reads.
      
    * procedure UPDATE_{regname}(
        dat: in t_busdata; byteen: in std_logic_vector;
        variable reg: inout t_{regname}
      );
      
      In-place update of the data in variable reg.  Used for bus writes.
      
    * procedure UPDATESIG_{regname}(...)
      
      Same as UPDATE_{regname}, but for a signal reg.
    """)
    
    extension = '.vhd'
    
    component_fileheader = dedent("""
    ------------------------------------------------------------------------
    {name} Register Map
    Defines the registers in the {name} component.
    
    {desc}
    
    Generated automatically from {source} on {time:%d %b %Y %H:%M}
    Do not modify this file directly.
    {geninfo}
    ----------------------------------------------------------------------
    """)
    
    use_packages = [
        'ieee.std_logic_1164.all',
        'ieee.numeric_std.all'
    ]
    
    def printheader(self, node, template):
        header = template.strip().format(
            name = node.name,
            desc = '\n\n'.join(wrapper.fill(d) for d in node.description),
            source = node.sourcefile,
            time = datetime.datetime.now(),
            pkg = self.pkgname,
            geninfo = self.component_generation,
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
        """Create a VHDL file for a Component."""
        
        # Comments, libraries, and boilerplate.
        self.pkgname = 'pkg_' + node.name
        self.printheader(node, self.component_fileheader)
        self.print()
        self.printlibraries()
        self.print()
        
        self.printf("package {pkg} is", pkg=self.pkgname)
        
        # Address Constants
        GenerateAddressConstants(self.output).execute(node)
        self.print()
        
        # Types
        GenerateTypes(self.output).execute(node)
        self.print()
        
        # Type conversion declarations
        GenerateFunctionDeclarations(self.output).execute(node)
        
        self.printf(dedent("""
            end package {pkg};
            ------------------------------------------------------------------------
            package body {pkg} is
            """), pkg=self.pkgname
        )
        
        # Address functions
        maxaddr = (node.size * node.width // 8) - 1
        addrbits = maxaddr.bit_length()
        high = addrbits - 1;
        self.printf(dedent("""
            ---- Address Grabbers ----
            function GET_ADDR(address: std_logic_vector) return t_addr is
                variable normal : std_logic_vector(address'length-1 downto 0);
            begin
                normal := address;
                return TO_INTEGER(UNSIGNED(normal({high} downto 0)));
            end function GET_ADDR;
            
            function GET_ADDR(address: unsigned) return t_addr is
            begin
                return TO_INTEGER(address({high} downto 0));
            end function GET_ADDR;
            
            """), high=high
        )
        
        # Type conversion functions
        GenerateFunctionBodies(self.output).execute(node)
        
        self.printf("end package body {pkg};", pkg=self.pkgname)
        self.print()
        
    def visit_MemoryMap(self, node):
        pass
    
class wishbone(basic):
    """WISHBONE bus VHDL output.
    
    This output generates specific functions and structures to interface these
    registers to WISHBONE bus.  That bus should be defined in pkg_global, which
    is taken as a prerequisite for these files.
    """
    
    component_generation = dedent("""
    Types
    =====
    * subtype t_addr of integer
    * subtype t_busdata of std_logic_vector, component width wide
    * t_{register}
      * subtype of std_logic_vector, unsigned, or signed OR
      * record if the register has fields
    * record tb_{registerarray} if the registerarray has multiple registers
    * array ta_{registerarray} of tb_{registerarray} or t_{register}
    
    Constants
    =========
    * {registername}_ADDR word offsets from 0 for freestanding registers
    * {register}_ADDR word offsets from array start in a registerarray
    * {registerarray}_BASEADDR offsets the same way {register}_ADDR does
    * {registerarray}_FRAMESIZE is the number of words in each array element
    * {registerarray}_LASTADDR is the offset for the last word in the array
    * {register}_{field}_{enum} is a value for field {register}.{field}
    
    Public Subprograms
    ==================
    * function GET_ADDR(std_logic_vector or unsigned) return t_addr
      
      Rips the appropriate number of LSBs to make a word address from.
      
    * function DAT_TO_{register}(t_busdata) return t_{register}
    
      Takes the correct bits from the bus data and translates them into the
      basic or record type for the register.  Used for bus writes.
      
    * function {register}_TO_DAT(t_{register}) return t_busdata
    
      Takes the bits from the basic or record type for the register and puts
      them together into a bus word.  Unused bits are 0.  Used for bus reads.
      
    * function WB_TO_{regname}(WB_IN : t_wb_mosi; current_dat : t_{regname}) return t_{regname};
    
      Uses the WB_IN.SEL byte enables to return a new register value that
      incorporates some of the WB_IN.DAT bus data.  Used for bus writes, but
      deprecated; this is the clunky old solution to this.
      
    * function {regname}_TO_WB(dat : t_{regname}) return t_wb_data;
    
      Takes the bits from the basic or record type for the register and puts
      them together into a bus word.  Unused bits are 0.  Used for bus reads.
      
    * procedure UPDATE_{regname}(
        dat : in t_wb_mosi; byteen : in std_logic_vector;
        variable reg : inout t_{regname}
      );
      
      In-place update of the data in variable reg.  Used for bus writes.
      
    * procedure UPDATE_SIG{regname}(...)
      
      Same as UPDATE_{regname}, but for a signal reg.
    """)
    
    use_packages = [
        'ieee.std_logic_1164.all',
        'ieee.numeric_std.all',
        'work.pkg_global.all'
    ]
