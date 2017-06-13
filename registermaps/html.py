"""Translate XML register definitions into HTML documentation."""

from os import makedirs
import os.path
import datetime
from lxml.html import builder as E
from lxml.html import tostring

from .visitor import Visitor
from . import resource_bytes, printverbose, ProgramGlobals

CLASS = E.CLASS
    
def register_format(node):
    """Returns the format (signed, unsigned, or nothing) and access
     class ('Read-Only', 'Write-Only' or a default) of a register.
     
     Places parentheses around if the return text isn't empty.
     """
    
    fmt = []
    if node.format == 'signed':
        fmt.append('Signed')
    elif node.format == 'unsigned':
        fmt.append('Unsigned')
        
    if node.readOnly:
        fmt.append('Read-Only')
    elif node.writeOnly:
        fmt.append('Write-Only')
    
    if fmt:
        return '(' + ' '.join(fmt) + ')'
    else:
        return ''

class basic(Visitor):
    """Translate into HTML documentation.
    
    Data members
    ------------
        hlev   
            Current HTML heading level
        
        breadcrumbs
            If present, an A element pointing back to a source document.
            
        inst
            If present, an instance name for a Component
            
        wordwidth
            The width (in bits) of a word in a given Component
            
        offset
            int - addresses are addresses on top of a base value
            str - addresses are really offsets and should be printed with
                the offset string as a prefix.
            
        address_nibbles
            Number of hex digits to print for addresses
            
        title
            Name of the document
    
    """
    
    # Because we're building up a hierarchical document we'll take advantage of
    # the ability of visit_ methods to return values to pass HTML Elements back
    # up the tree.
    
    binary = True
    extension = '.html'
    
    hlev = 1
    breadcrumbs = None
    offset = 0
    
    styledir = ''
    
    _headings = [None, E.H1, E.H2, E.H3, E.H4, E.H5, E.H6]
    def heading(self, *args, **kwargs):
        """Create an H1-H6 for self.hlev=1-6 respectively."""
        return self._headings[self.hlev](*args, **kwargs)
        
    def footer(self, node):
        """Create a standard footer block for HTML files."""
        return E.DIV(
            E.HR(),
            E.P(
                "Generated automatically from {source} at {time:%d %b %Y %H:%M}.".format(
                    source = node.sourcefile,
                    time = datetime.datetime.now()
            ), CLASS='footer')
        )
    
    def visit(self, node):
        """This hook is in to help debugging, it should be null in effect."""
        val = super().visit(node)
        assert val is not None, str(node)
        return val
    
    def visit_Component(self, node):
        inst = getattr(self, 'inst', None)
        if inst:
            title = 'Instance {} of {} Register Map'.format(inst, node.name)
        else:
            title = 'Base {} Register Map'.format(node.name)
        self.title = title
        
        bc = E.DIV(id='breadcrumbs')
        try:
            if self.breadcrumbs is not None:
                bc.append(self.breadcrumbs)
        except AttributeError:
            pass
            
        ww = node.width // 8
        an = ((node.size-1).bit_length() + 3) // 4
        
        stylesheet = E.LINK(
            rel='stylesheet', type='text/css',
            href=os.path.join(self.styledir, 'reg.css')
        )
        with self.tempvars(wordwidth=ww, address_nibbles=an, hlev=2):
            html = E.HTML(
                E.HEAD(
                    stylesheet,
                    E.TITLE(title)
                ),
                E.BODY(
                    E.H1(title),
                    bc,
                    *[E.P(d) for d in node.description],
                    *self.visitchildren(node),
                    self.footer(node)
                ),
            )
        return html
            
    def addressparagraph(self, node):
        """Return a P element for the byte address."""
        
        offset = node.offset * self.wordwidth
        if isinstance(self.offset, str):
            text = 'Offset {prefix}0x{offset:0{nibbles}X}'
        else:
            offset += self.offset
            text = 'Address 0x{offset:0{nibbles}X}'
        
        return E.P(text.format(
            prefix = self.offset,
            offset = offset,
            nibbles = self.address_nibbles
            ), CLASS('address')
        )
            
    def visit_RegisterArray(self, node):
        """Generate a RegisterArray DIV."""
        
        framebytes = node.framesize * self.wordwidth
        
        root = E.DIV(CLASS('regarray'), id="ARRAY_" + node.name)
        root.append(self.addressparagraph(node))
        root.append(self.heading(node.name))
        root.append(E.P(
            "Array of {} copies, repeats every {} bytes.".format(node.count, framebytes)
        ))
        for d in node.description:
            root.append(E.P(d, CLASS('description')))
            
        with self.tempvars(offset='N*{}+'.format(framebytes), hlev=self.hlev+1):
            root.extend(self.visitchildren(node))
        return root
        
    def visit_Register(self, node):
        """Generate a Register DIV with heading, bitfield table, field listing,
        etc."""
        
        ap = self.addressparagraph(node)
        ap.text += ' ' + register_format(node)
        
        root = E.DIV(
            ap,
            self.heading(node.name),
            *[E.P(d, CLASS('description')) for d in node.description],
            CLASS('register'), id="REG_" + node.name
        )
        
        if node.space:
            # We need bitfield tables.
            table = E.TABLE(CLASS('bitfield'))
            rows = []
            for startbit in range(0, node.space.size, 16):
                endbit = startbit + 16
                row = E.TR(CLASS('fields'))
                cells = []
                for obj, start, size in node.space[startbit:endbit]:
                    if obj:
                        cell = E.TD(obj.name, CLASS('std_field'))
                    else:
                        cell = E.TD('.', CLASS('reserved_field'))
                    cell.attrib['colspan'] = str(size)
                    cells.append(cell)
                row.extend(reversed(cells))
                rows.append(row)
                
                rows.append(E.TR(
                    *[E.TD(str(n-1)) for n in range(endbit, startbit, -1)],
                    CLASS('bit_numbers')
                ))
            table.extend(reversed(rows))
            root.append(table)
            
            fieldlist = E.UL(
                *self.visitchildren(node, reverse=True),
                CLASS('fieldlist')
            )
            root.append(fieldlist)
        return root
                
    def visit_Field(self, node):
        """Create a LI for this field."""
        
        if node.size == 1:
            bitrange = '[{}]'.format(node.offset)
        else:
            bitrange = '[{}:{}]'.format(node.offset+node.size-1, node.offset)
        
        fmt = register_format(node)
        deftext = bitrange + ' ' + fmt if fmt else bitrange
        item = E.LI(
            E.P(
                node.name + ' ',
                E.SPAN(deftext, CLASS('fielddef'))
            )
        )
        for d in node.description:
            item.append(E.P(d, CLASS('description')))
        
        if node.space:
            # We need a definitionlist for the enums
            dl = E.DL(CLASS('enumlist'))
            dl.extend(x for itemset in self.visitchildren(node) for x in itemset)
            item.append(dl)
        return item
        
    def visit_Enum(self, node):
        """Return a list of DT/DD elements for the enum DL."""
        
        return (
            [E.DT('{} - {}'.format(node.name, node.value))] + 
            [E.DD(d) for d in node.description]
        )
         
    def visit_MemoryMap(self, node):
        """Create an HTML file for a MemoryMap."""
        self.title = title = node.name + ' Peripheral Map'
        body = E.BODY(
            E.H1(title),
            *[E.P(d) for d in node.description]
        )
        
        an = ((node.size-1).bit_length() + 3) // 4
        with self.tempvars(
            wordwidth=1, address_nibbles=an, base=node.base,
            subdir=node.name+'_instances', hlev=2):
                
            html = E.HTML(
                E.HEAD(
                    E.LINK(rel="stylesheet", href="reg.css", type="text/css"),
                    E.TITLE(title)
                ),
                E.BODY(
                    E.H1(title),
                    *[E.P(d) for d in node.description],
                    E.HR(),
                    E.TABLE(
                        E.TR(
                            E.TH('Peripheral'), E.TH('Base Address'), E.TH('Size'), E.TH('Description'),
                            *self.visitchildren(node),
                        ),
                        CLASS('component_list')
                    ),
                    self.footer(node)
                )
            )
        return html
        
    def visit_Instance(self, node):
        """
        Create a table row for this Instance and a new file giving it a
        memory map of its own.
        """
        
        # If we're writing files, write another one for the instance and
        # create an HTML link.  Otherwise just give it a name.
        try:
            relativefile = os.path.join(self.subdir, node.name + self.extension)
            filename = os.path.join(self.path, relativefile)
        
        except TypeError:
            linkelement = node.name
            
        else:
            obj = type(self)(output=filename)
            try:
                obj.offset = node.offset + self.base
            except TypeError:
                obj.offset = node.offset
                
            obj.inst = node.name
            obj.breadcrumbs = E.A(
                self.title,
                href=os.path.join('..', self.filename)
            )
            obj.styledir = os.path.join(self.styledir, '..')
            obj.execute(node.binding)
            linkelement = E.A(node.name, href=relativefile)
        
        # And provide a table row for the MemoryMap
        desc = node.description or node.binding.description
        
        if isinstance(self.base, int):
            offset = '0x{:{}X}'.format(node.offset + self.base, self.address_nibbles)
        else:
            offset = '{}+0x{:{}X}'.format(self.base, node.offset, self.address_nibbles)
            
        return E.TR(
            E.TD(linkelement, CLASS('peripheral')),
            E.TD(offset, CLASS('paddress')),
            E.TD(hex(node.size), CLASS('psize')),
            E.TD(
                *[E.P(d) for d in desc],
                CLASS('pdesc')
            )
        )
        
    def finish(self, tree):
        try:
            self.write(tostring(tree, pretty_print=True))
        except TypeError:
            self.write(tostring(tree, pretty_print=True, encoding='unicode'))
        
    @classmethod
    def preparedir(kls, directory):
        """Copy the CSS into the target directory."""
        
        os.makedirs(directory, exist_ok=True)
        target = os.path.join(directory, 'reg.css')
        printverbose(target)
        with open(target, 'wb') as f:
            f.write(resource_bytes('resource/html.basic/reg.css'))
