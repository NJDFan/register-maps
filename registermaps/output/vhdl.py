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
from .. import xml_parser, textfn
from ..util import printverbose, Outputs, jinja
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
            ('_FRAMECOUNT', node.count)
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
        
        # And a default for it.
        self.printf('constant RESET_t_{0}_REGFILE : t_{0}_regfile := (', node.name)
        lines = (
            '    {0} => RESET_{1}'.format(child.identifier, self.namer(child))
            for child, _, _ in node.space.items()
        )
        self.print(',\n'.join(lines))
        self.print(');')
        self.print()
        
    def visit_ComplexRegisterArray(self, node):
        """Generate the subsidary record and array type."""
        
        self.visitchildren(node)
        
        # Create a base record type.
        basename = 'tb_' + node.name
        self.printf('type {} is record', basename)
        for obj, _, _ in node.space.items():
            self.printf('    {}: {};'.format(obj.identifier, self.namer(obj)))
        self.printf('end record {};', basename)
                    
        # And the array type.
        self.printf('type {} is array({} downto 0) of {};',
            self.namer(node), node.count-1, basename
        )
        
        # And the default array.
        self.printf('constant RESET_{0} : {0} := (others => (', self.namer(node))
        lines = (
            '    {0} => RESET_{1}'.format(child.identifier, self.namer(child))
            for child, _, _ in node.space.items()
        )
        self.print(',\n'.join(lines))
        self.print('));')
        self.print()
        
    def visit_SimpleRegisterArray(self, node):
        """Generate the array type."""
        
        self.visitchildren(node)
        child = next(obj for obj, _, _ in node.space.items())
        
        # Create the array type.
        self.printf('type {} is array({} downto 0) of {};',
            self.namer(node), node.count-1, self.namer(child)
        )
        
        # And a default for it.
        self.printf('constant RESET_{0} : {0} := (others => RESET_{1});',
            self.namer(node), self.namer(child)
        )
        self.print()
        
    def visit_ComplexRegister(self, node):
        """Generate the register type and enumeration constants."""
        
        # Generate the record type.
        with self.tempvars(enumlines=[], registername=node.name):
            self.printf('type t_{name} is record', name=node.name)
            self.visitchildren(node)
            self.printf('end record t_{name};', name=node.name)
        
            for line in self.enumlines:
                self.print(line)
                
        # And the reset constant.
        self.printf('constant RESET_{0} : {0} := (',
            self.namer(node)
        )
        lines = (
            "    {} => '{}'".format(child.identifier, child.reset) if size==1 else
            '    {} => "{:0{}b}"'.format(child.identifier, child.reset, size)
            for child, start, size in node.space.items()
        )
        self.print(',\n'.join(lines))
        self.print(');')
        self.print()
            
    def visit_SimpleRegister(self, node):
        """Generate the register type."""
    
        self.printf('subtype t_{name} is {fmt};',
            name=node.name,
            fmt = register_format(node),
        )
        self.printf('constant RESET_{0} : {0} :=  "{1:0{2}b}";',
              self.namer(node), node.reset, node.width
        )
        self.print()
                    
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
    
    def visit_Component(self, node):
        """Print all function bodies for the Component"""
        
        self.print(commentblock('Address Grabbers'))
        maxaddr = (node.size * node.width // 8) - 1
        self.printf(self.rt('fnbody_address'), high=maxaddr.bit_length()-1)
        
        self.print(commentblock('Accessor Functions'))
        self.visitchildren(node)
        
        self.print(self.template('fnbody_component.j2').render(
            node = node,
            name = node.name,
            updatelines = self._component_update(node),
            updatesiglines = self._component_updatesig(node),
            readlines = self._component_read(node),
        ))

    def visit_RegisterArray(self, node):
        """Register array access function bodies."""

        self.visitchildren(node)
        if node.space.itemcount > 1:
            tmpl = jinja.get_template('vhdl/fnbody_registerarray_complex.j2')
            self.print(tmpl.render(node=node)) 
        else:
            tmpl = jinja.get_template('vhdl/fnbody_registerarray_simple.j2')
            child = next(node.space.items()).obj
            self.print(tmpl.render(node=node, child=child)) 
            
    def visit_ComplexRegister(self, node):
        """Print register access function bodies."""
        
        # Start by extracting the fields from the register.
        def getrange(start, size):
            if size == 1:
                return str(start)
            else:
                return '{} downto {}'.format(start+size-1, start)
        
        def extractor(space, allow_readOnly):
            for obj, start, size in space.items():
                if (not obj.readOnly) or allow_readOnly:
                    yield {
                        'name' : obj.name,
                        'ident' : obj.identifier,
                        'srcrange' : getrange(start, size),
                        'subtype' : register_format(obj, index=False),
                        'range' : getrange(start-obj.offset, size),
                    }
            
        fields = list(extractor(node.space, True))
        subspaces = (node.space[start:start+8] for start in range(0, node.width, 8))
        byte = (list(extractor(s, False)) for s in subspaces)
        byte = [{'index' : n, 'fields': f} for n, f in enumerate(byte) if f]
        
        tmpl = jinja.get_template('vhdl/fnbody_register_complex.j2')
        self.print(tmpl.render(
            name=node.name, fields=fields, byte=byte
        ))
        
    def visit_SimpleRegister(self, node):
        """Print register access function bodies."""
            
        byte = [
            '{} downto {}'.format(min(low+7, node.width-1), low)
            for low in range(0, node.width, 8)
        ]
        
        tmpl = jinja.get_template('vhdl/fnbody_register_simple.j2')
        self.print(tmpl.render(
            name=node.name,
            subtype=register_format(node, index=False),
            srcrange='{} downto 0'.format(node.width-1),
            byte=byte
        ))

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


@Outputs.register
class VhdlAxi4Lite(Visitor):
    """VHDL component with an AXI-4 Lite interface.
    
    The code generated is meant as template code to be user-modified.
    """
    
    outputname = 'vhdl-axi4lite'
    extension = '.vhd'
    encoding = 'iso-8859-1'
    
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
        
    def visit_Component(self, node):
        """Create a VHDL template file for a Component."""
        
        if node.width not in (32, 64):
            raise ValueError(
                "AXI4-Lite components must have datawidth 32 or 64, {} has width {}"
                .format(node.name, node.width)
            )
        
        wrapper = textwrap.TextWrapper()
        header = self.rt('header_component').format(
            name = node.name,
            desc = '\n\n'.join(wrapper.fill(d) for d in node.description),
            source = node.sourcefile,
            time = datetime.datetime.now(),
            changes = self.changes
        )
        self.print(commentblock(header))
        self.print()
        
        addrhigh = (node.size - 1).bit_length() - 1
        datahigh = node.width - 1
        behigh = (node.width // 8) - 1
        self.printf(self.rt('body_component'),
            name = node.name,
            addrhigh = addrhigh,
            behigh = behigh,
            datahigh = datahigh
        )
        
    def visit_MemoryMap(self, node):
        pass

@Outputs.register
class VhdlWishboneAsync(Visitor):
    """VHDL component with an asynchronous turnaround WISHBONE interface.
    
    The code generated is meant as template code to be user-modified.
    """
    
    outputname = 'vhdl-wishbone-async'
    extension = '.vhd'
    encoding = 'iso-8859-1'
    
    def begin(self, startnode):
        changer = FixReservedWords()
        self.changed_nodes = changer.execute(startnode)
        if self.changed_nodes:
            printverbose('Changes from XML:')
            for nodetype, old, new in self.changed_nodes:
                printverbose('    {}: {} -> {}'.format(nodetype, old, new))
        
    def visit_Component(self, node):
        """Create a VHDL template file for a Component."""
        
        body = jinja.get_template('vhdl-wishbone-async/body_component.j2')
        self.print(body.render(
            node = node,
            changes = self.changed_nodes,
            time = datetime.datetime.now(),
        ))
        
    def visit_MemoryMap(self, node):
        """Create a VHDL file (probably usable as-is) providing INTERCON
        from a MemoryMap."""
        
        # Build up the self.instances array.
        self.instances = []
        self.visitchildren(node)
        
        # We can only work with arrays where all the datawidths are the same
        datawidths = set(c.binding.width for c in self.instances)
        if len(datawidths) > 1:
            raise ValueError("Must have all slaves with same data width.")
        datawidth = datawidths.pop()
        
        body = jinja.get_template('vhdl-wishbone-async/body_intercon.j2')
        self.print(body.render(
            node = node,
            instances = self.instances,
            datawidth = datawidth,
            changes = self.changed_nodes,
            time = datetime.datetime.now(),
        ))

    def visit_Instance(self, node):
        self.instances.append(node)
