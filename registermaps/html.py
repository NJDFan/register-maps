"""Translate XML register definitions into HTML documentation."""

from os import makedirs
import os.path
from lxml.html import builder as E
from lxml.html import tostring

from .visitor import Visitor
from . import resource_bytes

def CLASS(v):
    # helper function, 'class' is a reserved word
    return {'class': v}
    
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
    """Translate into HTML documentation."""
    
    # Because we're building up a hierarchical document we'll take advantage of
    # the ability of visit_ methods to return values to pass HTML Elements back
    # up the tree.
    
    binary = True
    extension = '.html'
    
    def copyfile(self, name):
        """Copy a file from our internal resource folder to any outputdir."""
        
        try:
            if self.outputdir:
                filename = os.path.join(self.outputdir, name)
                dirname = os.path.dirname(filename)
                os.makedirs(dirname, exist_ok=True)
                with open(filename, 'wb') as f:
                    f.write(resource_bytes(name))
        except AttributeError:
            pass
    
    def visit(self, node):
        """This hook is in to help debugging, it should be null in effect."""
        val = super().visit(node)
        assert val is not None, str(node)
        return val
    
    def visit_Component(self, node):
        self.copyfile('reg.css')
        self.copyfile('reg.js')
        
        title = node.name + ' Register Map'
        
        self.wordwidth = node.width // 8
        self.offset_modifier = ''
        self.offset_class = 'offset'
        self.offset_name = 'Address'
        
        html = E.HTML(
            E.HEAD(
                E.LINK(rel="stylesheet", href="reg.css", type="text/css"),
                E.SCRIPT(src="reg.js", type='text/javascript'),
                E.TITLE(title)
            ),
            E.BODY(
                E.H1(title),
                E.DIV(id='breadcrumbs'),
                *[E.P(d) for d in node.description],
                *self.visitchildren(node)
            ),
        )
        return html
            
    def addressparagraph(self, node):
        """Return a P element for the byte address."""
        
        return E.P(
            '{} {}0x'.format(self.offset_name, self.offset_modifier),
            E.SPAN(
                '{:X}'.format(node.offset * self.wordwidth),
                CLASS(self.offset_class)
            )
        )
        
            
    def visit_RegisterArray(self, node):
        """Generate a RegisterArray DIV."""
        
        framebytes = node.framesize * self.wordwidth
        
        root = E.DIV(CLASS('regarray'), id="ARRAY_" + node.name)
        root.append(E.H2(node.name))
        root.append(self.addressparagraph(node))
        root.append(E.P(
            "Array of {} copies, repeats every {} bytes.".format(node.count, framebytes)
        ))
        for d in node.description:
            root.append(E.P(d, CLASS('description')))
            
        with self.tempvars(
            offset_modifier='N*{}+'.format(framebytes),
            offset_class='', offset_name='Offset'
            ):
            root.extend(self.visitchildren(node))
        return root
        
    def visit_Register(self, node):
        """Generate a Register DIV with heading, bitfield table, field listing,
        etc."""
        
        ap = self.addressparagraph(node)
        ap.attrib['class'] = 'registerinfo'
        ap[0].tail = ' ' + register_format(node)
        
        root = E.DIV(
            E.H3(node.name),
            ap,
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
        self.copyfile('map.css')
        
        title = node.name + ' Peripheral Map'
        body = E.BODY(
            E.H1(title),
            *[E.P(d) for d in node.description]
        )
        
        html = E.HTML(
            E.HEAD(
                E.LINK(rel="stylesheet", href="map.css", type="text/css"),
                E.TITLE(title)
            ),
            body
        )
        return html
        
    def finish(self, tree):
        self.write(tostring(tree, pretty_print=True))
        
