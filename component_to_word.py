#!/usr/bin/env python

"""
Generate Microsoft Word (Office Open XML) documentation from HTI XML register
description documents.

This program parses two different types of XML description file.
First, a file documenting a single component, and all of the
registers that it may contain.  Second, a file documenting an
overall memory map, which instantiates and calls out various
components.

"""

import textwrap
import datetime
import argparse
import traceback
import codecs
import os
import sys
from copy import deepcopy

# These packages may not be around
try:
    from docx import *
except ImportError:
    print >>sys.stderr, "Unable to import python-docx library.  This is not a part of the standard distribution, and must"
    print >>sys.stderr, "be separately downloaded from https://github.com/mikemaccana/python-docx and installed."
    print >>sys.stderr, "python-docs also requires that lxml be installed, which also needs to be downloaded and installed,"
    print >>sys.stderr, "though this can generally be found in the package manager."
    sys.exit(1)
    
try:
    import lxml.etree as ET
    import lxml.builder
except ImportError:
    print >>sys.stderr, "Unable to lxml.  Please install this from the repository."
    sys.exit(1)

from hti_reg_xml import *
import space

class OutputterError(Exception):
    """
    An error because the outputter doesn't know what to do.
    First argument is a string description, second is the
    HtiElement where the error occurred.
    """
    pass
    
output_dir = ''
codec = codecs.lookup('utf-8')[-1]
    
########################################################################
# General purpose output formatting stuff
########################################################################

def register_format(r, default = ''):
    """Returns the format (signed, unsigned, or nothing) and access
     class ('Read-Only', 'Write-Only' or a default) of a register.
     
     Places parentheses around if the return text isn't empty.
     """
    fmt = r.get('format', '')
    if (fmt == 'signed'):
        ret = ' Signed'
    elif (fmt == 'unsigned'):
        ret = ' Unsigned'
    else:
        ret = ''
        
    ro = r['readOnly']
    wo = r['writeOnly']
    
    if (ro):
        ret = ret + ' Read-Only'
    elif (wo):
        ret = ret + ' Write-Only'
    else:
        ret = ret + default
        
    ret = ret.strip()
    if ret:
        ret = '(' + ret + ')'
        
    return ret
    
class LocalElementMaker(lxml.builder.ElementMaker):
    """
    A variation on the ElementMaker with the right namespace rules
    for attributes.
    """

    namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    
    typemap = {
        type(None) : ''
    }
    
    def __init__(self):
        super(LocalElementMaker, self).__init__(
            typemap = self.typemap,
            namespace = self.namespace,
            nsmap = {'w': self.namespace},
            makeelement = None
        )
    
    def __call__(self, tag, *children, **attrib):
        for k, v in attrib.items():
            if k[0] != '{':
                del attrib[k]
                k = '{' + self.namespace + '}' + k
                attrib[k] = v
                
        return super(LocalElementMaker, self).__call__(tag, *children, **attrib)
        
E = LocalElementMaker()
    
########################################################################
# Routines for outputting Components
########################################################################

def make_bitfield_table(src, bits):
    """Create a list of properly formatted bitfield table."""
    
    null_field_fmt = [ E.shd(fill = '888888') ]
    table_fmt = [ E.tblStyle(val="Bitfield"), E.tblW(type = 'pct', w = str(50 * 100)) ]
    
    par_fmt = E.pPr(
        E.jc(val = 'center'),
        E.keepNext()
    )
    font_fmt  = E.rPr(
        # E.rFonts(ascii="Courier New", cs="Courier New"),
        # E.sz(val = '18')
    )
    
    def make_header_cell(n):
        header_font = deepcopy(font_fmt)
        header_font.append(E.b())
        
        return E.tc(
            E.p(
                deepcopy(par_fmt),
                E.r(
                    header_font,
                    E.t(str(n))
                )
            )
        )

    def make_field_cell(obj):
        gridSpan = E.gridSpan(val = str(obj.size))
        if obj:
            pr = E.tcPr(gridSpan)
            return E.tc(
                pr,
                E.p(
                    deepcopy(par_fmt),
                    E.r(
                        deepcopy(font_fmt),
                        E.t(obj.obj['name'])
                    )
                )
            )
        else:
            proplist = deepcopy(null_field_fmt) + [gridSpan]
            pr = E.tcPr(*proplist)
            return E.tc(pr, E.p())

    # Figure out how many lines we need at 16 bits per line.
    number_of_lines = (bits + 15) / 16
    
    # Split the space of Fields onto these fieldlines
    fieldlines = [space.FiniteSpace(16) for i in range(number_of_lines)]
    
    for obj in src:
        line = obj.pos / 16
        pos = obj.pos % 16
        size = obj.size
        
        while (size > 0):
            # Write this object across as many lines as needed.
            localsize = min(size, 16 - pos)
            fieldlines[line].add(obj.obj, localsize, pos)
            size -= localsize
            line += 1
            pos = 0
            
    for f in fieldlines:
        f.compress()
        
    # Turn each fieldline into a table with two rows.
    tables = []
    
    for lineno, line in reversed(list(enumerate(fieldlines))):
        
        header_cells = [make_header_cell(n-1) for n in range((lineno + 1) * 16, lineno * 16, -1)]
        header_row = E.tr(*header_cells)
        
        borders = [
            E(b, val='single', sz='8', space='1', color='000000')
            for b in ('top', 'start', 'end', 'bottom', 'insideH', 'insideV')
        ]
        borderPr = E.tblBorders(*borders)
        
        field_cells = [make_field_cell(obj) for obj in reversed(line)]
        field_row = E.tr(
            E.trPr(
                E.tblPrEx(borderPr)
            ),
            *field_cells
        )
        
        tableprops = deepcopy(table_fmt)
        table = E.tbl(E.tblPr(*tableprops), header_row, field_row)
        
        tables.extend((table, E.p()))
        
    return tables


def make_bitfield_list(src):
    """Create a table of the bitfields and their descriptions."""
    
    def make_data_cell(text):
        def inner_dc(text):
            return E.p(
                E.r(
                    E.t(text)
                )
            )
            
        if isinstance(text, basestring):
            pars = [ inner_dc(text) ]
        else:
            pars = [ inner_dc(n) for n in text ]
            
        return E.tc(*pars)
    
    def make_header_cell(text):
        return E.tc(
            E.p(
                E.pPr(E.jc(val = 'center')),
                E.r(
                    E.rPr(E.b()),
                    E.t(text)
                )
            )
        )
    
    data_rPr = E.rPr()
    
    table = E.tbl(
        E.tblPr(
            E.tblStyle(val = "CodingTable")
        )
    )
    
    header_row = E.tr(
        E.trPr(E.tblHeader(), E.cantSplit()),
        make_header_cell('Field'),
        make_header_cell('Range'),
        make_header_cell('Description')
    )
    table.append(header_row)
    
    # Build up our table data rows.
    for f in reversed(tuple(src.getObjects())):
        if (f['size'] == 1):
            rng = '[{0}]'.format(f['offset'])
        else:
            rng = '[{0}:{1}]'.format(
                        f['offset'] + f['size'] - 1,
                        f['offset']) 
        
        desclist = f.getDescription()
        if desclist:
            desclist[-1] += ' ' + register_format(f)
        else:
            desclist = [register_format(f)]
        descdata = [
            E.p(E.r(E.t(x))) for x in desclist
        ]
        
        enums = f.getChildren()
        if enums:
            rows = [
                E.tr(
                    make_data_cell(e['name']),
                    make_data_cell(str(e['value'])),
                    make_data_cell(e.getDescription())
                ) for e in enums
            ]
            descdata.append(E.tbl(*rows))
        
        row = E.tr(
            E.rPr,
            make_data_cell(f['name']),
            make_data_cell(rng),
            E.tc(*descdata)
        )
        
        table.append(row)
        
    contents = [table, E.p()]
    return contents
    

#
# We need to generate bitfield information for our registers.
#

def generate_register(self, reg_name_fmt):

    """Generate the description bitfield table and definition list for a register."""
    contents = []
        
    contents.append(heading(reg_name_fmt(self), 3))
    for d in self.getDescription():
        contents.append(paragraph(d))
    
    ### Write the bitfield tables.
    if self.space:
        contents.extend(make_bitfield_table(self.space, self['width']))
            
    ### Write the bitfield description table.
    if self.has_fields:
        contents.extend(make_bitfield_list(self.space))
    
    return contents
    
def generate_regarray(self, reg_name_fmt):
    """Generate prototypical registers for the register array."""
    
    contents = []
    
    contents.append(heading(reg_name_fmt(self), 2))
    contents.append(paragraph(
        'Base of an array with {count} copies, each {b} bytes long.'.format(
            count = self['count'],
            b = self['framesize'] * self['width'] / 8
        )
    ))
            
    contents.append(paragraph(self.getDescription()))
        
    for obj in self.space.getObjects():
        contents.extend(obj.generate(reg_name_fmt))
    
    return contents
    
Register.generate = generate_register
RegisterArray.generate = generate_regarray
   
#
# We need to generate all of the above for a component.
#
    
def generate_single_component(comp, instance = None):
    """Render down a component tree into an XHTML file.
    
    Keyword Arguments:
    comp - A Component generate HTML from.
    
    instance - An Instance object that is binding comp if called in
    the context of a memory map.  Skip this to generate only abstract
    information about Components instead.
    
    Returns an XHTML tree.
    """

    if instance:
        mmap = instance.findParent(MemoryMap)
        comp_name = instance['name']
        base_addr = instance['offset']
        
        if (comp_name == comp['name']):
            title = '{comp} Register Map'.format(comp = comp_name)
        else:
            title = '{inst} Register Map (Instance of {comp})'.format(
                        inst = comp_name,
                        comp = comp['name'])
                
        def reg_name_fmt(reg):
            return '{reg} (BAR0 + 0x{loc:05X}) {access}'.format(
                reg = reg['name'],
                loc = (reg.findOffset() * reg.byteWidth()) + base_addr,
                access = register_format(reg, ' Read-Write'))
                
    else:
        comp_name = comp['name']
        base_addr = 0
        title = '{comp} Register Map'.format(comp = comp_name)

        def reg_name_fmt(reg):
            return '{reg} (Word Offset 0x{loc:03}) {access}'.format(
                reg = reg['name'],
                loc = reg.findOffset(),
                access = register_format(reg, ' Read-Write'))
    
    contents = []
    
    contents.append(heading(title, 1))
    if instance:
        desc = instance.getChildren(Description)
    else:
        desc = []
    contents.append(paragraph(desc))

    # Now go through and handle all of the registers.
    for reg in comp.space.getObjects():
        contents.extend(reg.generate(reg_name_fmt))
        
    return contents
        
Component.generate = generate_single_component
    
########################################################################
# Routines for outputting MemoryMaps
########################################################################

def generate_instance(self):
    """
    Generate a Component's docx file for a given instance.
    """
    
    mmap = self.findParent(MemoryMap)
    basename = mmap['name'] + "_" + self['name'] + '.docx'    
    filename = make_target_filename(output_dir, basename)
    comp = self.binding
    baseaddr = self['offset']
    
    # Default set of relationshipships - the minimum components of a document
    relationships = relationshiplist()
    # Make a new document tree - this is the main part of a Word document
    document = newdocument()
    # This xpath location is where most interesting content lives
    body = document.xpath('/w:document/w:body', namespaces=nsprefixes)[0]
           
    body.extend(comp.generate(instance = self))
    
    coreprops = coreproperties(title='', subject='', creator='',
                               keywords='')
    rshp = wordrelationships(relationships)

    # Save our document
    savedocx(document, coreprops, appproperties(), contenttypes(), websettings(),
             rshp, filename)

    return None
   
Instance.generate       = generate_instance

def generate_memory_map(mmap):
    """Render down a memory map tree into multiple HTML files.
    
    Keyword Arguments:
    mmap - A MemoryMap instance to generate HTML from.
    """
    
    for inst in mmap.space.getObjects():
        inst.generate()
        
MemoryMap.generate = generate_memory_map
        
########################################################################
# Main code
########################################################################

def make_target_filename(output_dir, sourcefile):
    """The name of a header file generated by a given source file."""
    basename = os.path.basename(sourcefile)
    (root, ext) = os.path.splitext(basename)
    basename = root + ".docx"
    
    if output_dir:
        return os.path.join(output_dir, basename)
    else:
        return basename

def output_select(output_dir, sourcefile):
    """If output_dir is non-null, produce a context manager for
    an output file, with the name derived from output_dir and sourcefile.

    Otherwise, produce a context manager that simply wraps
    the standard output stream.

    """
    class StdoutWrapper:
        def __enter__(self):
            return sys.stdout

        def __exit__(self, type, value, traceback):
            return

    if output_dir:
        return open(make_target_filename(output_dir, sourcefile), 'w')

    else:
        return StdoutWrapper()

def main(argv=None):
    ########################################################
    # Start by parsing the command line options.
    ########################################################
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', '-o', help="""
        When present, specifies a directory to write output files to.
        Output files will have the same names as the input files they
        correspond to, but with a .docx extension, rather than .xml.
        When absent, all output will be written to stdout.
        """)
    ap.add_argument('--no-mmap', '-m', action="store_false", dest = 'mmap', help="""
        Ignore any memory map files; generate only abstract component
        files.
        """)
    ap.add_argument('source', nargs = '+', help="""
        Input files in the HTI XML register or memory map description
        format.
        """)

    args = ap.parse_args(argv)

    if (args.output_dir and not os.path.isdir(args.output_dir)):
        print >>sys.stderr, "Unable to write to directory {0}".format(args.output_dir)
        sys.exit(1)
        
    global output_dir 
    output_dir = args.output_dir

    ########################################################
    # Read all the XML files
    ########################################################

    parser = XmlReader()
    components = []
    maps = []

    for source in args.source:
        try:
            root = parser.Parse(source)
            if isinstance(root, Component):
                root.finish()
                components.append(root)
            
            elif isinstance(root, MemoryMap):
                maps.append(root)
                
        except:
            print >>sys.stderr, "Error parsing {0}".format(source)
            traceback.print_exc()

    ########################################################
    # And generate all of the outputs
    ########################################################
    
    # Because whole memory maps require linkages, just ignore them
    # if we don't have a directory target.
    if maps and output_dir and args.mmap:
        cmap = MemoryMap.build_component_map(components)
        for mmap in maps:
            mmap.finish(cmap)
            mmap.generate()
            
    else:
        for comp in components:
            with output_select(output_dir, comp.sourcefile) as target:
                print >>codec(target), str(comp.generate(instance = None))

if __name__ == "__main__":
    sys.exit(main())
