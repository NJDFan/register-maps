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

# Translation to VHDL requires a lot of text templates that were cluttering up
# the code, so they've been moved to individual text files in the
# resource/vhdl.basic directory, with a _TemplateLoader class to pull them in
# as needed.

import os
import os.path
import textwrap
import datetime

from .. import xml_parser
from ..util import printverbose, Outputs
from ..visitor import Visitor

class VhdlVisitor(Visitor):
    """All the VHDL outputs need access to the resource directory."""
    outputname = 'vhdl'

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
    
def commentblock(text):
    """Return text as a comment encased in comment bars."""
    
    cbar = '-' * 80
    return '\n'.join((cbar, textwrap.indent(text.strip(), '--  ', lambda x: True), cbar))

#######################################################################
# Helper visitors
#######################################################################

class FixReservedWords(VhdlVisitor):
    """Modify the tree for legal VHDL.
    
    Any names that are with illegal VHDL characters will be changed.
    
    All nodes will be given a .identifier that is related the name, but
    has a _0 appended if the name is a reserved word.
    
    Return a list of the changes, each change is (type, old, new), such as
    ('register identifier', 'MONARRAY.OUT', 'MONARRAY.OUT_0').
    """
    
    # VHDL identifiers must start with a letter and cannot end with an
    # underscore.  We'll take our definitions of letters and digits straight
    # from the 2008 LRM §15.2.  Note there is no uppercase equivalent
    # for ß or ÿ.
    
    uppercase = set('ABCDEFGHIJKLMNOPQRSTUVWXYZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ')
    lowercase = set('abcdefghijklmnopqrstuvwxyzßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ')
    letters = uppercase | lowercase
    word_chars = letters | set('0123456789_')
    
    # Again from the 2008 LRM, §15.10.
    reserved_words = set(VhdlVisitor.rt('reservedwords').split())
    
    def invalidvhdl(self, name):
        """Return None if name is valid VHDL, otherwise a new name that is."""
    
        # First character must be a letter
        it = iter(name)
        first = next(it)
        if first not in self.letters:
            raise ValueError("{} {} does not start with valid letter.".format(
                ntype, node.name
            ))
        newchars = [first]
        
        # Later characters can be anything
        changed = False
        char = first
        for char in it:
            if char not in self.word_chars:
                changed = True
                char = '_'
            newchars.append(char)
            
        # But we can't end with an underline
        if char == '_':
            newchars.append('_0')
            changed = True
            
        if changed:
            return ''.join(newchars)
        else:
            return None
    
    def defaultvisit(self, node):
        """All nodes behave the same."""
        
        ntype = type(node).__name__.lower()
        
        # First off, check to see if it's even a valid VHDL identifier.
        oldname = node.name
        newname = self.invalidvhdl(oldname)
        
        # If it wasn't even valid VHDL it can't be a reserved word.
        if newname:
            node.name = node.identifier = newname
            changes = [(ntype + ' name', oldname, newname)]
        
        # Reserved words need a new identifier but not a new name
        elif node.name.lower() in self.reserved_words:
            newname = node.name + '_0'
            node.identifier = newname
            changes = [(ntype + ' identifier', node.name, newname)]
            
        # All good here
        else:
            node.identifier = newname = oldname
            changes = []
        
        # Sweep the children too
        changes.extend(
            (ctype, oldname + '.' + old, newname + '.' + new)
                for childchanges in self.visitchildren(node)
                for ctype, old, new in childchanges
        )
        return changes
        
    def visit_Enum(self, node):
        return []

class GenerateAddressConstants(VhdlVisitor):
    """Print address constants into the package header."""
        
    def begin(self, startnode):
        self.body = []
    
    def visit_Component(self, node):
        maxaddr = node.size - 1
        self.print(commentblock('Address Constants'))
        self.printf('subtype t_addr is integer range 0 to {};', maxaddr)
        
        self.visitchildren(node)
        self.print('function GET_ADDR(address: std_logic_vector) return t_addr;')
        self.print('function GET_ADDR(address: unsigned) return t_addr;')
        
    def visit_RegisterArray(self, node):
        consts = (
            ('_BASEADDR', node.offset),
            ('_LASTADDR', node.offset+node.size-1),
            ('_FRAMESIZE', node.framesize),
            ('_FRAMECOUNT', node.framesize)
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

class GenerateTypes(VhdlVisitor):
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
        
        self.print(commentblock('Register Types'))
        self.printf('subtype t_busdata is std_logic_vector({} downto 0);', node.width-1)
        
        # First define all the registers and registerarrays
        self.visitchildren(node)
        
        # Now create a gestalt structure for the entire register file.
        self.printf('type t_{}_regfile is record', node.name)
        for child, _, _ in node.space.items():
            self.printf('    {}: {};', child.identifier, self.namer(child))
        self.printf('end record t_{}_regfile;', node.name)
        
    def visit_RegisterArray(self, node):
        """Generate the array type and, if necessary, a subsidiary record."""
        
        # First define the register types.
        self.visitchildren(node)
        
        # Now we can define the array type.
        fields = [
            (child.identifier, self.namer(child))
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
            self.printf('subtype t_{name} is {fmt};',
                name=node.name,
                fmt = register_format(node),
            )
                    
    def visit_Field(self, node):
        """Generate record field definitions, and gather enumeration constants."""
        
        with self.tempvars(field=node, fieldtype=register_format(node)):
            self.printf('    {}: {};', node.identifier, self.fieldtype)
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

class GenerateFunctionDeclarations(VhdlVisitor):
    """Print function declaration statements for the package header."""
    
    def visit_Component(self, node):
        self.print(commentblock('Accessor Functions'))
        self.visitchildren(node)
        self.printf(self.rt('fndecl_component'), name=node.name)
            
    def visit_RegisterArray(self, node):
        self.printf(self.rt('fndecl_registerarray'), name=node.name)
        self.visitchildren(node)
    
    def visit_Register(self, node):
        # Register access functions
        self.printf(self.rt('fndecl_register'), name=node.name)
        
class _fnbodyrecord:
    """
    Supports GenerateFunctionBodies by creating the "when" block
    inside of a case statement.
    
    String template arguments are for use with the format statement and will
    be passed the following keyword format elements:
        node
            The parent node
        child
            Each child node
    
    Args
    ----
        Register (str): String template to use for Register children
        RegisterArray (str): String template to use for RegisterArray children
        others (str): String template to use when lookup fails
        skipontrue (str): Fallback to others if 'readOnly' or 'writeOnly' is true.
        indent (int): Number of spaces to indent each line by.  Default is 8
        
    Returns
    -------
        A callable that turns a node into a multiline text block that can be
        inserted into the VHDL procedure, inside the case statement.
    """
    
    def __init__(self, Register, RegisterArray,
        others = "when others => success := false;",
        skipontrue = 'readOnly',
        indent=8):
        
        self.Register = dedent(Register).strip()
        self.RegisterArray = dedent(RegisterArray).strip()
        self.others = others
        self.skipontrue = skipontrue
        self.indent = 8
        
    def __call__(self, node):
        whenlines = []
        gaps = False
        for obj, _, _ in node.space:
            # Is this a thing we can't write to?
            if (not obj) or getattr(obj, self.skipontrue):
                gaps = True
                continue
            
            try:
                line = getattr(self, type(obj).__name__)
            except AttributeError:
                raise ValueError('Child node {}: {} of {} {}'.format(
                    type(obj).__name__, obj.name,
                    type(node).__name__, node.name
                ))
            whenlines.append(line.format(node=node, child=obj))
            
        # Put an others line on if the case wasn't filled.
        if gaps:
            whenlines.append(self.others.format(node=node))
            
        # Indent all those lines and slam them together into a multi-line block.
        return textwrap.indent(
            '\n'.join(whenlines),
            ' ' * self.indent
        )
        
class GenerateFunctionBodies(VhdlVisitor):
    """Print function bodies for the package body."""
    
    _component_update = _fnbodyrecord(
        Register = "when {child.name}_ADDR => UPDATE_{child.name}(dat, byteen, reg.{child.identifier});",
        RegisterArray = """
            when {child.name}_BASEADDR to {child.name}_LASTADDR =>
                UPDATE_{child.name}(dat, byteen, offset-{child.name}_BASEADDR, reg.{child.identifier}, success);
            """
    )   
    _component_updatesig = _fnbodyrecord(
        Register = "when {child.name}_ADDR => UPDATESIG_{child.name}(dat, byteen, reg.{child.identifier});",
        RegisterArray = """
            when {child.name}_BASEADDR to {child.name}_LASTADDR =>
                UPDATESIG_{child.name}(dat, byteen, offset-{child.name}_BASEADDR, reg.{child.identifier}, success);
            """
    )
    _component_read = _fnbodyrecord(
        Register = "when {child.name}_ADDR => dat := {child.name}_TO_DAT(reg.{child.identifier});",
        RegisterArray = """
            when {child.name}_BASEADDR to {child.name}_LASTADDR =>
                READ_{child.name}(offset-{child.name}_BASEADDR, reg.{child.identifier}, dat, success);
            """,
        skipontrue = 'writeOnly'
    )
    
    _regarray_update = _fnbodyrecord(
        Register = "when {child.name}_ADDR => UPDATE_{child.name}(dat, byteen, ra(idx).{child.identifier});",
        RegisterArray = """
            when {child.name}_BASEADDR to {child.name}_LASTADDR =>
                UPDATE_{child.name}(dat, byteen, offs-{child.name}_BASEADDR, ra(idx).{child.identifier}, success);
            """
    )
    _regarray_updatesig = _fnbodyrecord(
        Register = """
            when {child.name}_ADDR =>
                UPDATE_{child.name}(dat, byteen, temp.{child.identifier});
                ra(idx).{child.identifier} <= temp.{child.identifier};
            """,
        RegisterArray = """
            when {child.name}_BASEADDR to {child.name}_LASTADDR =>
                UPDATE_{child.name}(dat, byteen, offs-{child.name}_BASEADDR, ra(idx).{child.identifier}, success);
                ra(idx).{child.identifier} <= temp.{child.identifier};
            """
    )
    _regarray_read = _fnbodyrecord(
        Register = "when {child.name}_ADDR => dat := {child.name}_TO_DAT(ra(idx).{child.identifier});",
        RegisterArray = """
            when {child.name}_BASEADDR to {child.name}_LASTADDR =>
                READ_{child.name}(offs-{child.name}_BASEADDR, ra(idx).{child.identifier}, dat, success);
            """,
        skipontrue = 'writeOnly'
    )
    
    def visit_Component(self, node):
        """Print all function bodies for the Component"""
        
        self.print(commentblock('Address Grabbers'))
        maxaddr = (node.size * node.width // 8) - 1
        self.printf(self.rt('fnbody_address'), high=maxaddr.bit_length()-1)
        
        self.print(commentblock('Accessor Functions'))
        self.visitchildren(node)
        
        self.printf(self.rt('fnbody_component'),
            name = node.name,
            updatelines = self._component_update(node),
            updatesiglines = self._component_updatesig(node),
            readlines = self._component_read(node),
        )

    def visit_RegisterArray(self, node):
        """Register array access function bodies."""

        self.visitchildren(node)
        if len(node.space) == 1:
            child = next(child for child, _, _ in node.space.items())
            if node.readOnly or child.readOnly:
                t = self.rt('fnbody_registerarray_simple_ro')
            else:
                t = self.rt('fnbody_registerarray_simple_write')
            self.printf(t, name = node.name, child = child.name)
                
            if node.writeOnly or child.writeOnly:
                t = self.rt('fnbody_registerarray_simple_wo')
            else:
                t = self.rt('fnbody_registerarray_simple_read')
            self.printf(t, name = node.name, child = child.name)
                
        else:
            self.printf(self.rt('fnbody_registerarray_complex'),
                name = node.name,
                updatelines = self._regarray_update(node),
                updatesiglines = self._regarray_updatesig(node),
                readlines = self._regarray_read(node),
            )
            
    def visit_Register(self, node):
        """Print register access function bodies."""
        
        self.printf(self.rt('fnbody_register'),
            name=node.name,
            d2rlines = GenerateD2R().execute(node),
            r2dlines = GenerateR2D().execute(node),
            updatelines = GenerateRegUpdate().execute(node)
        )
     
class _Indent4Visitor(VhdlVisitor):
    def finish(self, lastvalue):
        return textwrap.indent(lastvalue, '    ')
     
class GenerateD2R(_Indent4Visitor):
    """Text for the function body for DAT_TO_register."""
    
    def visit_Register(self, node):
        if node.space:
            return dedent("""
                return(
                {children}
                );"""
            ).format(children = ',\n'.join(self.visitchildren(node)))
            
        else:
            return 'return {fmt}(dat({high} downto 0));'.format(
                fmt = register_format(node, False).upper(),
                high = node.width-1
            )
        
    def visit_Field(self, node):
        """Pull bus data to a record field."""
        if node.width == 1:
            line = '    {name} => dat({high})'
        else:
            line = '    {name} => {fmt}(dat({high} downto {low}))'
        return line.format(
            name=node.name, fmt=register_format(node, False).upper(),
            high=node.offset+node.width-1, low=node.offset
        )  
        
class GenerateR2D(_Indent4Visitor):
    """Text for the function body for register_TO_DAT."""
    
    def visit_Register(self, node):
        if node.space:
            return '\n'.join(self.visitchildren(node))
        else:
            return 'ret({high} downto 0) := STD_LOGIC_VECTOR(reg);'.format(
                high=node.width-1
            )
            
    def visit_Field(self, node):
        if node.width == 1:
            line = 'ret({high}) := reg.{identifier};'
        else:
            line = 'ret({high} downto {low}) := STD_LOGIC_VECTOR(reg.{identifier});'
        return line.format(
            identifier=node.identifier, high=node.offset+node.width-1, low=node.offset
        )
        
class GenerateRegUpdate(_Indent4Visitor):
    """Text for the function body for UPDATE_register."""
    
    def visit_Register(self, node):
        return '\n'.join(self.complex(node) if node.space else self.simple(node))
    
    def simple(self, node):
        """Assigns the register byte by byte.
        
        Yields:
            Lines of text
        """
        
        fmt = register_format(node, False).upper()
        for byte, start in enumerate(range(0, node.width, 8)):
            end = min(start+7, node.width)
            yield dedent("""
                if IS_HIGH(byteen({byte})) then
                    reg({H} downto {L}) := {fmt}(dat({H} downto {L}));
                end if;""".format(byte=byte, fmt=fmt, H=end, L=start),
            )
            
    def complex(self, node):
        """Assigns the register fields byte by byte.
        
        Yields:
            Lines of text
        """
        for byte, start in enumerate(range(0, node.width, 8)):
            subspace = node.space[start:start+8]
            if not any(obj for obj, _, _ in subspace):
                continue
                
            yield 'if IS_HIGH(byteen({})) then'.format(byte) 
            for obj, start, size in subspace:
                if not obj:
                    continue
                if size > 1 or obj.size > 1:
                    # This field is indexable.
                    line = '    reg.{identifier}({fh} downto {fl}) := {fmt}(dat({dh} downto {dl}));'
                else:
                    # This field is a bit.
                    line = '    reg.{identifier} := dat({dl});'
                yield line.format(
                    fh = start+size-1-obj.offset,
                    fl = start-obj.offset,
                    dh = start+size-1,
                    dl = start,
                    fmt = register_format(obj, False).upper(),
                    identifier=obj.identifier
                )
                
            yield 'end if;'

#######################################################################
# Main visitors
#######################################################################

@Outputs.register
class Vhdl(VhdlVisitor):
    """Basic VHDL output.
    
    This output makes no assumptions about what the bus type is, and expects
    no support packages to be available.
    """
    
    outputname = 'vhdl'
    extension = '.vhd'
    encoding = 'iso-8859-1'
    
    use_packages = [
        'ieee.std_logic_1164.all',
        'ieee.numeric_std.all'
    ]
    
    def begin(self, startnode):
        changer = FixReservedWords()
        changed_nodes = changer.execute(startnode)
        if changed_nodes:
            changes = (
                'Changes from XML:\n' +  
                '\n'.join('    {0[0]}: {0[1]} -> {0[2]}'.format(c) for c in changed_nodes)
            )
            printverbose(changes)
            self.changes = '\n' + changes + '\n'
        else:
            self.changes = ''
        
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
        
        wrapper = textwrap.TextWrapper()
        
        self.pkgname = 'pkg_' + node.name
        header = self.rt('header_component').format(
            name = node.name,
            desc = '\n\n'.join(wrapper.fill(d) for d in node.description),
            source = node.sourcefile,
            time = datetime.datetime.now(),
            pkg = self.pkgname,
            changes = self.changes
        )
        self.print(commentblock(header))
        self.print()
        self.printlibraries()
        self.print()
        
        self.print(commentblock('Package declaration'))
        self.printf("package {} is", self.pkgname)
        
        # Address Constants
        GenerateAddressConstants(self.output).execute(node)
        self.print()
        
        # Types
        GenerateTypes(self.output).execute(node)
        self.print()
        
        # Type conversion declarations
        GenerateFunctionDeclarations(self.output).execute(node)
        
        self.printf('end package {};'.format(self.pkgname))
        self.print(commentblock('Package body'))
        self.printf('package body {} is'.format(self.pkgname))
        
        # Type conversion functions
        GenerateFunctionBodies(self.output).execute(node)
        
        self.printf("end package body {};", self.pkgname)
        self.print()
        
    def visit_MemoryMap(self, node):
        pass

