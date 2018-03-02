"""Translate XML register definitions into HTML documentation.

Generated HTML files have top level structure:

HTML
  HEAD
  BODY
    DIV #wrapper
      DIV #sidebar
      DIV #contents
      
Where #sidebar is a navigation table-of-contents for the document, and 
#contents is the main data being displayed.
"""

from os import makedirs
import os.path
import datetime
from lxml.html import builder as E
from lxml.html import tostring, Element
from html import escape

from ..visitor import Visitor
from ..util import resource_text, printverbose, Outputs

CLASS = E.CLASS
FOOTER = Element('footer')
    
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

@Outputs.register
class basic(Visitor):
    """Translate into HTML documentation.
    
    Attributes
    ----------
        hlev (int): Current HTML heading level
        breadcrumbs (HtmlElement): If present, an A element pointing back to a source document.
        inst (str): If present, an instance name for a Component
        wordwidth (int): The width (in bits) of a word in a given Component
            
        offset (int, str):
        
            int - addresses are addresses on top of a base value
            
            str - addresses are really offsets and should be printed with
            the offset string as a prefix.
            
        address_nibbles (int): Number of hex digits to print for addresses
        title (str): Name of the document
    
    """
    
    # Because we're building up a hierarchical document we'll take advantage of
    # the ability of visit_ methods to return values to pass HTML Elements back
    # up the tree.
    
    outputname = 'html'
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
        footer = Element('footer')
        footer.append(E.HR())
        footer.append(
            E.P(
                "Generated automatically from {source} at {time:%d %b %Y %H:%M}.".format(
                    source = node.sourcefile,
                    time = datetime.datetime.now()
            )),
        )
        return footer
    
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
        
        # Create the main content by sweeping the tree.
        bc = E.DIV(id='breadcrumbs')
        try:
            if self.breadcrumbs is not None:
                bc.append(self.breadcrumbs)
        except AttributeError:
            pass
            
        ww = node.width // 8
        an = ((node.size-1).bit_length() + 3) // 4
        with self.tempvars(wordwidth=ww, address_nibbles=an, hlev=2):
            nodes = (
                [E.H1(title, id='title'), bc] +
                [E.P(d) for d in node.description] +
                [c for c in self.visitchildren(node)] +
                [self.footer(node)]
            )
            contentnode = E.DIV(*nodes, id='content')
        
        # Add a table of contents sidebar.  We'll assume that everything that
        # wants to be in the TOC is already a heading and just work from there.
        h2list = E.UL()
        for elem in contentnode.iter('h2', 'h3'):
            id = escape(elem.text)
            elem.attrib['id'] = id
            if elem.tag == 'h2':
                h2node = E.LI(
                    E.A(
                        elem.text,
                        href='#' + id
                    )
                )
                h2list.append(h2node)
                h3list = None
            else:
                if h3list is None:
                    h3list = E.UL()
                    h2list.append(h3list)
                h3list.append(
                    E.LI(
                        E.A(
                            elem.text,
                            href='#' + id
                )))
        
        # Put it all together.
        return E.HTML(
            E.HEAD(
                E.TITLE(title),
                E.LINK(
                    rel='stylesheet', type='text/css',
                    href=os.path.join(self.styledir, 'reg.css')
                )
            ),
            E.BODY(
                E.DIV(
                    E.DIV(
                        E.P(E.A(title, href='#title')),
                        h2list,
                        id='sidebar'
                    ),
                    contentnode,
                    id='wrapper'
                )
            ),
        )
            
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
            CLASS('register'),
            *[E.P(d, CLASS('description')) for d in node.description],
            id="REG_" + node.name
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
                    CLASS('bit_numbers'),
                    *[E.TD(str(n-1)) for n in range(endbit, startbit, -1)]
                ))
            table.extend(reversed(rows))
            root.append(table)
            
            fieldlist = E.UL(
                CLASS('fieldlist'),
                *self.visitchildren(node, reverse=True)
            )
            root.append(fieldlist)
            
        elif node.width != node.parent.width:
            # We have a truncated field, i.e. not all the bits that the
            # component allows.
            root.append(E.P('Bits {}:0 only.'.format(node.width-1)))
            
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
        an = ((node.size-1).bit_length() + 3) // 4
        
        # Sweep the document tree to build up the main content
        with self.tempvars(
            wordwidth=1, address_nibbles=an, base=node.base,
            subdir=node.name+'_instances', hlev=2):
            children = list(self.visitchildren(node))
            table = E.TABLE(
                E.TR(
                    E.TH('Peripheral'), E.TH('Base Address'), E.TH('Size'), E.TH('Description'),
                    *children
                ), CLASS('component_list')
            )
            nodes = (
                [E.H1(title, id='title')] +
                [E.P(d) for d in node.description] +
                [E.HR(), table, self.footer(node)]
            )
            contentnode = E.DIV(*nodes, id='content')

        # Add a table of contents sidebar for each table row.
        instlist = E.UL()
        for elem in contentnode.xpath("//td[contains(@class, 'peripheral')]"):
            text = tostring(elem, method="text", encoding="unicode")
            id = escape(text)
            elem.attrib['id'] = id
            node = E.LI(
                E.A(
                    text,
                    href='#' + id
                )
            )
            instlist.append(node)
        
        # And put it all together.
        return E.HTML(
            E.HEAD(
                E.TITLE(title),
                E.LINK(
                    rel='stylesheet', type='text/css',
                    href=os.path.join(self.styledir, 'reg.css')
                )
            ),
            E.BODY(
                E.DIV(
                    E.DIV(
                        E.P(E.A(title, href='#title')),
                        instlist,
                        id='sidebar'
                    ),
                    contentnode,
                    id='wrapper'
                )
            ),
        )
        
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
            offset = '0x{:0{}X}'.format(node.offset + self.base, self.address_nibbles)
        else:
            offset = '{}+0x{:0{}X}'.format(self.base, node.offset, self.address_nibbles)
            
        return E.TR(
            E.TD(linkelement, CLASS('peripheral')),
            E.TD(offset, CLASS('paddress')),
            E.TD('0x{:0{}X}'.format(node.size, self.address_nibbles), CLASS('psize')),
            E.TD(
                CLASS('pdesc'),
                *[E.P(d) for d in desc]
            )
        )
        
    def finish(self, tree):
        try:
            self.write(tostring(tree, pretty_print=True))
        except TypeError:
            self.write(tostring(tree, pretty_print=True, encoding='unicode'))
        
    @classmethod
    def preparedir(kls, directory):
        """Copy static files into the target directory."""
        
        super().preparedir(directory)
        target = os.path.join(directory, 'reg.css')
        printverbose(target)
        with open(target, 'wb') as f:
            f.write(kls.rb('reg.css'))
